# Postman MCP — Discovery Playbook (v1.0)

You are performing **repository understanding** for a Postman MCP sync. Your job is
to produce a Canonical API Model (APIM) document — a JSON file matching the schema
returned by `get_contract()` — and submit it with `submit_model`. You do **not** call
the Postman API yourself, and you never write to Postman directly: the MCP server
validates, verifies, and gates everything you submit before any write can happen.

## Use `index()` and `context()` first

Before reading files by hand, call `index()` once — it returns a framework-blind
repository map (services, languages, files with decorated/annotated symbols, an
evidence-corpus summary) built deterministically at zero cost to you. Then, for each
endpoint or handler file, call `context(target, budget=8000)` instead of opening files
yourself: `target` is a symbol/function name, `"path/to/file.py"`, `"file.py::symbol"`,
or `"METHOD /path"`. It returns exactly the code that matters — the handler, its
DTO/type closure, the service functions it calls, the router mount chain, and matching
test/OpenAPI witnesses — as chunks headed `## file:start-end [role]`. **Those headers
are your citations**: copy the file/line span directly into `Evidence` instead of
counting lines by hand, which is the single biggest source of citation mismatches.

If `context()` can't resolve a target (unusual mount styles, a framework it hasn't
seen), fall back to reading the repository directly with your own tools — the rules
below still apply either way, and `index()`'s file list is still a good starting map.
Multi-hop composed paths (a router's own prefix plus where it's mounted) are something
you're expected to compose *semantically* from the mount-chain chunks `context()`
gives you — that composition is exactly the kind of reasoning this workflow leaves to
you rather than to string-matching.

## The five rules

1. **Enumerate before you describe.** Find every route registration site first — via
   `index()`/`context()` (preferred) or, per-framework, the grep patterns in
   `frameworks/<name>.md` — then walk each mount chain upward to its entrypoint
   (`include_router`, `app.use`, `register_blueprint`, `include()`, `@Controller` +
   `@RequestMapping`, `RouterModule`, global prefixes). Never emit an endpoint whose
   full chain you have not actually read.

2. **Cite as you go.** Every fact you assert — a route's existence, its path, its
   body shape, its auth — needs an `Evidence` entry: `file`, `line_start`, `line_end`,
   `symbol`, and a `quote` (first cited line, ≤200 chars). Compute `snippet_sha256` as
   the SHA-256 of the exact lines you cited, newline-normalized to `\n` and with
   trailing whitespace stripped per line, joined with `\n`. The MCP re-reads those
   exact lines and re-hashes them — a citation that doesn't match what's actually in
   the file gets your endpoint **rejected as a hallucination**, even if the endpoint is
   real. Read the file, don't guess at line numbers.

3. **Resolve types to their definitions, not their usage.** For a request body or
   response shape, cite the DTO/serializer/Pydantic-model/struct *class definition*,
   not just the handler that references it.

4. **Say what you don't know.** A prefix built from an environment variable, a
   dynamically-computed mount path, a registration site in a file you can't reach —
   put it in `unresolved` with a short note, and emit the resolvable part of the path
   with a `{{variable}}` placeholder instead of guessing a literal. An honest
   "unresolved" is never penalized the way a wrong confident answer is.

5. **Semantics are yours alone — and that's fine.** Descriptions, business meaning,
   realistic examples, and suggested folder placement can't be cited to a single line
   of code. Leave their evidence list empty; the verification pipeline caps
   unevidenced facts at confidence 50 by design, and none of these fields ever gate a
   sync. Write good ones anyway — they're what makes the collection readable.

## Confidence — don't self-inflate

You may only assert `extraction_method: "ai_inferred"` on your own authority.
Anything higher (`framework_verified`, `ast_verified`, `openapi_verified`,
`multi_source_inferred`) is a class the MCP *promotes* your fact to, based on whether
an independent parser (the "witness engine") agrees and whether your citation audits
clean. Submitting a fabricated high confidence changes nothing — the server recomputes
every score itself and ignores what you wrote.

## The loop

1. Call `get_contract()` once per session to fetch this playbook, the schema, and the
   framework-specific guide(s) for the repo you're analyzing.
2. Call `index()` once, then `context(target)` per endpoint/file (see above). Fall back
   to reading the repo with your own tools only where `context()` can't resolve a target.
3. Write the APIM JSON to a file (`postman/models/draft.json` is a reasonable
   default) and call `submit_model(model_path=...)`.
4. Read the returned `VerificationReport`. If any endpoint was rejected or warned,
   the report names the exact file/line/check — re-read that code and resubmit a
   corrected model. Resubmission is idempotent; content-identical models get the same
   `model_id`.
5. Once verification is clean (or the remaining warnings are acceptable), call `plan`
   to get a diff, then `apply` after the user confirms. Never call `apply` without a
   diff the user has seen.

## What NOT to do

- Don't invent an endpoint because it "should" exist based on naming conventions —
  cite the registration site or leave it out.
- Don't cite a usage site when a definition site is available (prefer the DTO class
  over the handler parameter).
- Don't paraphrase a citation's line range to make it look tidier — cite exactly what
  you read.
- Don't retry a rejected endpoint with the same wrong citation — the hash check will
  fail identically.
