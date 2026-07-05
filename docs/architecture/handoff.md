# Engineering handoff — how this actually works, and where the bodies are buried

If you just inherited this repo, read this before you touch anything. It's not a
tour of features. It's the reasoning behind the decisions, including the ones I'm
not fully happy with, and an honest list of what's solid versus what's duct tape.

The repo currently contains **two working pipelines**. `1.1.0` and earlier shipped
one: parser-based sync (`service/sync.py`, six commands, six frameworks, measured
accuracy). `2.0.0`, the current release, adds a second, separate pipeline
(`contract/`, `model/`, `verify/`, `confidence/`, `plan/`, `safety/`) that accepts a
structured API model from an external caller instead of extracting one from code.
The second one exists *alongside* the first, not in place of it. That's not an
accident, and it's not finished — more on that below.

## 1. The problem this project solves

Teams write API code. Someone has to keep a Postman collection in sync with it —
request shapes, auth, response examples, folder structure. In practice that sync is
done by hand, it drifts within a week, and nobody trusts the collection enough to use
it as documentation. The fix isn't "generate a collection once from OpenAPI" (plenty
of tools do that) — it's *keep it in sync as the code changes*, without clobbering
the stuff a human added by hand (test scripts, curated examples, an edited
description). That last part is why this isn't a five-file project.

## 2. The original architecture, and why it's shaped the way it is

Pipeline: parse code → `RouteModel` → `engine/builder.py` builds a Postman item →
`postman/merge.py` diffs it against the live collection → show the diff → write on
confirm.

Parser, not LLM, from day one — and the reason is boring: determinism.
`build_request_item` given the same `RouteModel` twice produces the same item, byte
for byte. `tests/test_examples.py` depends on that; it diffs generated output
against checked-in fixtures and fails on any drift. Swap in an LLM at that step and
every sync becomes a coin flip on wording, ordering, scope. You can't build a
diff-before-write safety story on top of a generator that isn't deterministic,
because "diff" only means something if the user is looking at *exactly* what gets
written, not an approximation of it.

`RouteModel` is the seam that makes six frameworks tractable. Every parser
(`input/parsers/fastapi.py`, `django.py`, `express.py`, `nestjs.py`, `flask.py`,
`spring.py`) and the OpenAPI mapper (`input/openapi.py`) emit the same normalized
shape (`models.py`). The engine doesn't know or care whether a route came from a
decorator or a spec. I'd defend this as the one abstraction in the codebase that's
non-negotiable — skip it and you're writing N×M glue instead (N input sources, M
output concerns: body building, auth headers, test scripts, examples). With it,
adding NestJS support was "write a parser that emits `RouteModel`," full stop. No
changes anywhere else.

Route identity is `METHOD:normalized_path`, nothing richer. `models.normalize_path`
collapses `/users/:id`, `/users/{id}`, `/users/<id>` down to one key, which is what
lets a re-sync avoid creating duplicate items — Express spells path params one way,
FastAPI another, and the live collection has to match either regardless of which one
wrote it last. The obvious risk: two genuinely different routes that happen to
normalize to the same key will collide. We took that tradeoff on purpose. A false
collision is loud in the diff and easy to notice; a missed one would be silent, and
silent is worse.

Merge follows one rule: code wins on structure, human wins on craft
(`postman/merge.py:_merge_item`). `method`/`url`/`header`/`body`/`auth` get
overwritten on every sync, because those come from the code and the code is the
source of truth for them. `event` (test scripts), saved `response` examples, and an
edited `description` survive if already present. Someone spent twenty minutes
writing a good example by hand — the sync should never eat that. This is probably
the single property that decides whether people trust the tool or not, and it's why
`sync` can never just recreate an item from scratch; it has to actually merge
against whatever's live.

The diff shows before every write, no exceptions, even on `syncall`. The alternative
is "trust the tool," and a tool that silently rewrites a Postman collection is one
people stop using the first time it surprises them. `_run_sync` in `service/sync.py`
has exactly one write path (`ctx.client.update_collection`), gated behind
`confirm=True`; `test_service.py::test_preview_does_not_write` exists specifically to
catch a regression here. Of everything in this codebase, this is the part I'd be
most careful not to weaken.

What's intentionally simple: the CLI (`cli.py`) is six subcommands, nothing more.
`postman-mcp.json` has two blocks — `config` and `lastUpdate` — and nothing else
ever gets written into it, no secrets, no cache. Secrets resolve by reference
(`secrets/manager.py`) through keychain/env/file, picked once at `init` time. None of
this needed to be fancier than it is.

What's intentionally complicated: `input/structural.py`, 560 lines. Route
composition — "what's the full URL for this route, given `include_router` /
`app.use` / `register_blueprint` chains across files" — is a real import-graph
resolution problem, not something a per-file regex can answer. A route mounted under
`/v1` in one file and `/v2` via a second `include_router` call needs both. If the
resolver can't trace a mount (dynamic import, computed prefix) it says so
(`ResolvedPrefix(resolved=False)`) instead of guessing. This module exists because of
an earlier failure: reading only the leaf decorator drops every prefix in the mount
chain, and it's confidently wrong in exactly the cases you'd care most about
(versioned APIs, nested routers).

## 3. What broke: the temptation to hand everything to an LLM

At some point the obvious next step looked like: skip the parsers, have Claude read
the repo, and just ask it what the routes are. That was tried as a design — the first
all-AI discovery attempt, abandoned before it shipped — and it failed for a specific
reason, not the vague "AI is unreliable" complaint people reach for first.

To know the real URL for a route you have to follow `app.use('/api', usersRouter)`
to wherever `usersRouter` is defined, then to whatever mounts *that*. That's
import/symbol resolution, the exact problem `input/structural.py` already solves
deterministically. Hand it to an LLM on a token budget and it either reads the whole
repo (doesn't scale) or reads a plausible slice and guesses the rest — confidently,
because nothing in that setup tells it the guess is incomplete. The failure mode
isn't "the model doesn't know." It's "the model doesn't know that it doesn't know,"
and it ships a wrong URL with exactly the same confidence as a right one.

The other half of the problem: there was no ground-truth oracle. A verifier that
only checks the model's output for internal consistency will happily certify
self-consistent garbage — you need something independent to disagree with. The
parsers were sitting right there, already solving this at 100% measured accuracy on
the corpus in `tests/test_accuracy.py`, and v1 discarded them instead of using them
as that oracle. That's the actual mistake. "LLMs hallucinate" is true and also not
something you can act on by itself.

## 4. The submitted-model pipeline

The fix isn't "don't use AI." It's "stop asking AI to do the one job that has a
deterministic answer, and use the thing that already solves that job as a witness
instead of throwing it away." In practice:

- The LLM (any LLM — this isn't Claude-specific, see below) reads the repo with its
  own tools and produces an **API model**: a JSON document where every fact — a
  route's existence, its body shape, its auth — carries a citation
  (`file`, `line_start`, `line_end`, `symbol`, a SHA-256 of the exact cited lines).
- The MCP server re-reads those exact lines and re-hashes them
  (`verify/evidence.py::audit_evidence`). A citation that doesn't match what's in the
  file fails, full stop, whether or not the endpoint is real. That's the whole
  anti-hallucination mechanism — not "ask the model to be careful," a hash
  comparison against the working tree.
- The parsers, unchanged, run as an **independent witness**
  (`witness/engine.py::build_witness_set`). An LLM-claimed endpoint the witness never
  found, whose citation doesn't even mention a real registration pattern
  (`@router.post(`, `include_router(`, `@Controller(`, ...), gets rejected as a
  hallucination (`verify/pipeline.py`, check V-07). One that the witness *does*
  confirm gets its confidence promoted, not because the LLM said so, but because an
  independent source agrees.
- Confidence is a number the **MCP computes**, never one the LLM reports
  (`confidence/scorer.py`). The LLM can only ever claim the bottom tier
  (`ai_inferred`, capped at 50) on its own say-so. Everything above that — up to 95
  for witness-confirmed identity, 100 for something backed by a real OpenAPI spec —
  is *earned* by agreement and by surviving the evidence audit. I was deliberate
  about this: if the LLM's self-reported confidence mattered at all for gating, a
  model that's bad at calibrating its own certainty (all of them, some days) would
  silently determine what gets auto-synced.
- Nothing writes without a **plan token**
  (`plan/compiler.py::compute_plan_id`), which binds the model id, a hash of the live
  collection, the scope, and the destination folder into one id. `apply(plan_id)`
  re-fetches the collection and refuses to write if the hash changed since the plan
  was compiled — this closes a real race (someone edits the collection in the
  Postman UI between preview and apply) that the *old* pipeline doesn't fully close
  (it re-resolves from scratch on `confirm=True`, so what gets written can differ
  from what was previewed if the underlying files changed in between).
- Every write snapshots the collection first (`safety/snapshots.py`), and a failed
  snapshot **blocks the write** rather than proceeding without a rollback path. Every
  lifecycle event is appended to `audit.jsonl` (`safety/audit.py`) — append-only, one
  line per event, never rewritten.

### Keeping it model-agnostic

`get_contract()` hands back JSON Schema plus a markdown playbook
(`contract/playbook/discovery.md` and the per-framework guides under
`contract/playbook/frameworks/`). No SDK dependency, no function-calling convention,
nothing Claude-specific. Any agent that can read JSON Schema and markdown, write a
JSON file, and call `submit_model(path)` can play. Reason: coupling the contract to
one provider's tool-calling format would mean the verification pipeline — the part
that's actually hard and actually worth having — only works behind one vendor's API.
Markdown for the playbook specifically so that improving discovery strategy is a
docs edit, not a code change.

### The parsers stayed, they didn't get deleted

They're not obsolete. They're the only part of this whole system with a measured
accuracy number — 100% on `tests/test_accuracy.py`'s corpus, cross-checked per-field
in `test_field_accuracy.py`. Replacing that with "trust the LLM" would have been a
strict downgrade for every case the parsers already handle well.
`witness/engine.py::witness_to_apim` converts their output directly into a valid
API model (`generator.provider: "witness"`) that runs through the same verification
pipeline an LLM submission does. Which is also how the old commands keep working
with zero LLM involvement: no model submitted → witness produces its own → that
sails through verification → plan → apply. One pipeline, two producers.

## 5. Where this is genuinely unfinished, and why I'm telling you now

The two pipelines don't share a write path. `service/sync.py`
(`sync_api`/`sync_target`/`sync_all`/`sync_changes`) still does its own
build → diff → merge → PUT, same as before 2.0.0. The new tools
(`get_contract`/`submit_model`/`plan`/`apply`/...) go through `service/aiplan.py`,
which does witness/model → verify → plan → apply. Two different code paths writing
to the same collection, sharing the underlying engine and merge logic but with
separate plan/confirm mechanics on top. I left it this way on purpose —
re-plumbing the legacy commands risked regressing five frameworks' worth of measured
accuracy and 186 passing tests, and nothing about adding the new capability required
breaking that. It's still duplication, though, and it shouldn't stay this way
long-term. The next real chunk of work is migrating `sync_api`/`sync_all`/etc. to
compile through `plan/compiler.py` and write through `apply`, so exactly one path
touches `update_collection`. Until that happens, a bug fixed in one merge path isn't
automatically fixed in the other — lower risk than it sounds, since both call the
same `merge.py` functions underneath, but it's two call sites to keep straight
instead of one.

The witness engine's evidence line numbers are a guess, not a fact. The parsers were
never built to track source line numbers — `code_ref` is `"file.py::symbol"`, no
line attached. `witness/engine.py::_locate_evidence` does a plain text search for the
symbol name and cites whatever line turns up first. Fine for a function named
uniquely in its file. For something like `def create` showing up in two overloaded
contexts, it can cite the wrong occurrence. So a witness-produced model's evidence
is real — the file exists, the hash is real, the content is real — but not
necessarily *precise*. It's citing a plausible line, not necessarily the decorator
line, and fixing that means adding line-tracking to six parsers, which nobody has
done yet. LLM-submitted models don't have this problem, because the LLM actually
reads the file and cites the real line. This is specifically a fallback-path
weakness.

V-07's hallucination check looks for a known registration token
(`@app.post(`, `include_router(`, `@RequestMapping`, the full list is in
`verify/pipeline.py::_REGISTRATION_SIGNALS`) inside the citation's `quote` field.
Deliberately conservative — better to reject a real endpoint whose citation happens
to land on a non-decorator line than wave a fabricated one through — but it means a
correct LLM citation pointing at, say, a handler's `return` statement instead of its
decorator gets treated as a hallucination. The real fix is walking a few lines
around the cited span looking for a signal instead of checking only the one line.
Not done. Flagged in a comment, not swallowed silently.

V-06 (route conflicts) and V-09 (framework plausibility) are minimal on purpose, not
exhaustive. V-06 only catches shadowing between two routes in the same file, same
method, with exactly one differing path segment — real, but a narrow slice of the
possible ordering bugs. V-09 checks exactly two things: a body declared on
GET/HEAD, and a duplicate path-param name in one path. A much bigger catalog is
possible — Django path-converter validity, NestJS decorators outside a
`@Controller`, Spring mapping with no context — none of which is implemented.
Smallest set that's real, rather than padding the check count with rules that never
fire.

And the big one: none of this has run against an actual LLM doing actual repository
discovery. Every test in `tests/test_verify_pipeline.py` and
`tests/test_aiplan_service.py` builds the API model by hand or through the witness engine.
Nobody has pointed a live Claude session at `get_contract()` and a real multi-file
repo to see what comes back. The playbook (`contract/playbook/discovery.md`) is a
reasonable starting point, not something calibrated against actual model behavior.
Expect the first real session to surface prompt gaps the hand-built fixtures can't.

A few smaller gaps worth knowing about:

- No monorepo or multi-service support, despite the schema having a `Service` model
  for it. `witness/engine.py` always uses `service="default"`; nothing populates more
  than one entry or partitions a collection per service. The schema won't fight you
  if you need this, but the workspace-discovery plumbing to find multiple services in
  one repo doesn't exist.
- Infra-dependent URLs aren't handled. A route whose real prefix comes from an
  environment variable should turn into a `{{postman_variable}}` with candidate
  values surfaced as environments — that was the intent, not something built.
  `unresolved` today is just a list of strings on the endpoint; nothing consumes it.
- Confidence thresholds (90/75/50) are policy defaults, not measured numbers. Unlike
  the parser accuracy corpus, which has real ground truth and a real precision/
  recall figure, the bands in `confidence/policy.py` are engineering judgment about
  what "probably fine to auto-sync" should mean. Nobody has validated that 90+
  correlates with "this was correct" at any real rate. If this goes into real use,
  watch the 75-90 band especially — that's where a badly-calibrated LLM claim that
  happens to pick up witness-agreement promotion could slip through as `auto` when
  it shouldn't.

## 6. What the system is good at

Syncing well-structured FastAPI/Django/Express/NestJS/Flask/Spring APIs — routes
registered the conventional way, decorators or `Router.register` or class-level
mapping annotations — without ever touching an LLM, at measured high accuracy, with
a diff that never lies about what it's about to write and a merge that never eats
hand-written test scripts or examples. That's the whole original value proposition,
and it works exactly as well as it did before 2.0.0. Nothing in the new pipeline
touches that path.

Where the parsers can't reach — a framework with no parser, a genuinely dynamic
routing scheme, business-semantic understanding no static analysis will ever get
("this endpoint's description should mention it's idempotent because of X") — the
new pipeline gives you an option that doesn't mean writing a seventh parser. The
LLM fills in what it can, cites what it claims, and the system either backs that
claim with independent evidence or refuses to sync it as unverified fact.

## 7. What it's not good at

A framework the witness engine doesn't parse, whose registration pattern also isn't
one of the common tokens in `_REGISTRATION_SIGNALS`, will not sync above 90%
confidence no matter how good the LLM's analysis is. That's a deliberate ceiling,
not a bug — but it means "custom framework, no LLM available" gets you `ai_inferred`
(50) at best, landing in the needs-approval band every time.

Nothing here protects you from an LLM that's systematically overconfident in a way
the witness engine can't check — inventing a plausible-but-wrong response schema for
a real, witness-confirmed endpoint, say. Route identity gets caught by the
cross-check. The *content* of an unevidenced or thinly-evidenced body/response claim
is capped low, but "low" still means it can land in the auto-sync band if it picks
up weak multi-source agreement — two citations that both happen to point at the same
wrong place, for instance. Real gap, not a solved problem.

And it does nothing for infra-level correctness: reverse proxies, gateway rewrites,
environment-specific base paths. `unresolved` at least makes this visible instead of
silently wrong, but nothing resolves it.

## 8. Assumptions baked into the design

- **Git is available and this is a git repo.** `git/reader.py` shells directly to
  `git`. `syncchanges` needs it, and so does the evidence auditor's fabricated-vs-
  stale distinction. No git means `syncchanges` degrades gracefully (points you at
  `syncall`), but the fabricated-vs-stale check falls back to "conservative stale"
  without a resolvable commit — a genuinely fabricated citation in a git-less
  environment gets treated as merely stale instead of flatly rejected. Check
  `verify/evidence.py::audit_evidence`'s fallback branch if that matters for your
  deployment.
- **One Postman collection is the target, read and written whole.** The public
  Postman API has no "patch one request" endpoint. You `GET` the whole collection,
  mutate it in memory, `PUT` the whole thing back. That's why every write is atomic
  (`_run_sync` / `service/aiplan.py::apply`), and why the collection-hash check in
  `plan/compiler.py` works at all — there's exactly one document to hash.
- **A route's identity is stable across `METHOD + normalized path`.** If two
  different underlying operations ever need to share that key, the merge logic
  conflates them. Nothing detects this specially; the diff just looks like one route
  replacing another's fields.
- **The MCP server never calls a model API, on principle.** Not "currently doesn't,"
  structurally can't without someone adding a dependency and breaking the design.
  That's why `pyproject.toml` gains no Anthropic/OpenAI SDK as part of this work, and
  why `verify/pipeline.py` takes an already-parsed `ApiModel`, never raw text.

## 9. If you're picking this up next

In priority order, based on what's actually load-bearing versus cosmetic:

1. Re-plumb `service/sync.py`'s four selectors through `plan/compiler.py` +
   `service/aiplan.py::apply`, so there's one write path. Do this carefully — the
   existing 186 tests are your regression harness, and `test_examples.py`'s
   byte-identical fixture check is the thing that will tell you if you broke
   determinism.
2. Run an actual LLM discovery session against `get_contract()` on a real multi-file
   repo and see what the playbook gets wrong. The hand-built test fixtures cannot
   tell you this.
3. Fix the V-07 registration-signal check to look at a small window around the cited
   line, not just the one line, before it starts rejecting correct-but-imprecisely-
   cited endpoints from real LLM sessions.
4. If you need multi-service support, start at `witness/engine.py`'s hardcoded
   `service="default"` and the missing workspace-discovery step (finding multiple
   services in one repo) — the schema's `Service` model already has the shape for it.
5. Leave the confidence thresholds alone until you have real data on how often a
   `warn`/`flag` band sync turned out to be wrong. Changing them without that data is
   just moving the goalposts, not fixing anything.
