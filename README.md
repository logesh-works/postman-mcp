<div align="center">

<img src="https://raw.githubusercontent.com/logesh-works/postman-mcp/main/assets/logo/logo.svg" alt="Postman MCP" width="96" height="96">

# Postman MCP

**Generate and update Postman requests from your API code, from inside Claude Code.**

[![PyPI](https://img.shields.io/pypi/v/postman-mcp.svg)](https://pypi.org/project/postman-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/postman-mcp.svg)](https://pypi.org/project/postman-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/logesh-works/postman-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/logesh-works/postman-mcp/actions/workflows/ci.yml)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://logesh-works.github.io/postman-mcp/)

[Documentation](https://logesh-works.github.io/postman-mcp/) ·
[Quickstart](https://logesh-works.github.io/postman-mcp/getting-started/quickstart/) ·
[Commands](https://logesh-works.github.io/postman-mcp/commands/) ·
[Roadmap](ROADMAP.md)

</div>

---

## Why does this exist?

Once you ship an endpoint, the Postman collection for it starts going stale immediately.
You add a field, Postman doesn't know. You add a new error response, Postman doesn't
know. Nobody updates Postman by hand consistently, because it's pure busywork: open the
request, retype the body you already wrote in code, guess at example values, repeat for
every route.

The information Postman needs already exists in your code: the route, the request body
type, the auth dependency, the declared responses. Postman MCP reads that and writes the
request for you, so the only thing you do by hand is review a diff and say yes.

## How does it work?

Postman MCP runs two things: a CLI (`postman-mcp`) for one-time setup, and an MCP server
that Claude Code talks to while you work. You install it once per machine, run `init`
once per project, and after that you only ever type slash commands inside Claude Code.

**Claude does the reading and reasoning; Postman MCP does the checking and writing.**
When you run a sync command, Claude reads your code — any framework, any language it
understands — and writes three files into `postman/sync/`:

- **`collection.json`** — a Postman Collection v2.1 it authors directly (folders,
  requests, auth, examples).
- **`metadata.json`** — a citation for every request: the exact `file:line` the endpoint
  and each DTO field come from, hashed.
- **`sync.config.json`** — the scope and target of this run.

The MCP server then does the parts that must be deterministic and trustworthy: it
**validates** the collection is well-formed, **verifies** Claude didn't hallucinate by
re-reading the exact lines it cited (and grounding every claimed request/response field
against the real DTO class), **diffs** the result against your live Postman collection,
and — only after you say yes — **merges and writes** it, preserving any test scripts and
saved examples you added by hand. The MCP never parses your source or calls a model; it
checks claims and writes. This is what makes it work on *any* framework without a
per-framework parser, while still catching a wrong route or a made-up field before it
reaches Postman.

The seven slash commands differ only in *what* Claude analyzes (one endpoint, one file,
the whole repo, what changed in git); they all funnel through the same
validate → verify → diff → confirm → write pipeline. The contract Claude follows to do
this is published by the MCP server itself, so any MCP-capable client can drive it, not
just Claude Code.

## What happens when I run syncapi?

Say you have this FastAPI route:

```python
@app.post("/payments", response_model=PaymentResponse, status_code=201)
def create_payment(body: PaymentRequest, user: str = Depends(get_current_user)) -> PaymentResponse:
    """Create a new payment.

    Charges the given amount and returns the created payment record.
    """
    ...
```

You run:

```text
/postman:syncapi create_payment --into payments
```

Claude reads `create_payment` and its `PaymentRequest`/`PaymentResponse` DTOs, writes the
request into `postman/sync/collection.json` with citations in `metadata.json`, and calls
the `sync_files` tool. The MCP re-reads the cited lines to confirm the route and every
field are real, diffs against your live collection, and shows you the result without
writing anything:

```text
Collection: Acme Backend
Plan: 1 new · 0 modified

[NEW] POST /payments   → payments   ✓ verified (app/payments.py:12)

Write to Postman? Re-run with confirm=true to apply.
```

Each endpoint is labelled `✓ verified` (citation matches the code), `~ stale` (code moved
since cited), or `⚠ unverified` / `⚠ CITATION DOES NOT MATCH` — so you can see at a glance
which requests are backed by real code before you say yes. A request whose citation
doesn't match the code is excluded from the write unless you explicitly approve it. Say
`y` and it writes; say `n` and nothing happens. There's no flag to skip the diff.

## What gets generated?

This is the actual Collection v2.1 item the engine builds for `create_payment` above
(`build_request_item()`, default settings, nothing hand-edited):

```json
{
  "name": "POST /payments",
  "request": {
    "method": "POST",
    "header": [{ "key": "Content-Type", "value": "application/json" }],
    "url": {
      "raw": "{{base_url}}/payments",
      "host": ["{{base_url}}"],
      "path": ["payments"]
    },
    "description": "Create a new payment.\n\nCharges the given amount and returns the created payment record.",
    "body": {
      "mode": "raw",
      "raw": "{\n  \"amount\": 4200,\n  \"currency\": \"USD\",\n  \"method\": \"string\"\n}",
      "options": { "raw": { "language": "json" } }
    },
    "auth": {
      "type": "bearer",
      "bearer": [{ "key": "token", "value": "{{token}}", "type": "string" }]
    }
  },
  "response": [
    {
      "name": "201 201",
      "code": 201,
      "header": [{ "key": "Content-Type", "value": "application/json" }],
      "body": "{\n  \"id\": 1,\n  \"amount\": 4200,\n  \"currency\": \"USD\",\n  \"status\": \"active\",\n  \"created_at\": \"2026-06-27T10:00:00Z\"\n}"
    }
  ]
}
```

A few things worth pointing out, because they're not obvious from the JSON:

- `amount` got the example value `4200` because the engine recognizes the field name
  pattern and picks a plausible number, the same way it picks an email-looking string for
  a field called `email`. It has no idea what your API actually returns; these are
  realistic placeholders, not live data.
- `method` got the generic value `"string"` because its name doesn't match any pattern
  the example generator knows about. You'll see this a lot for fields named things like
  `note`, `tag`, or anything domain-specific. Fill those in by hand, the same as you
  would in any new Postman request.
- There's exactly one saved response: the `201` declared by `response_model`. No `400` or
  `401` was invented and attached. That's the default (`responseStyle: single`) and it's
  deliberate, not a gap: a Postman collection full of speculative error responses nobody
  asked for is worse than one with none. You can opt into `minimal` (success + one error)
  or `full` (every declared 2xx plus a standard error set) in `postman/config.json` if you
  want more.
- No test script is attached. Test generation is off by default
  (`generateTests: false`); turn it on if you want status/schema assertions added
  automatically.

## What does not work yet?

Being upfront about the current gaps:

- **Express and NestJS code parsing is regex/heuristic, not a real AST.** Neither
  language has a parser this project depends on, so body and auth detection is
  best-effort and flagged "lower confidence" in the diff when it falls back to inferring
  from usage instead of reading an explicit type or schema.
- **Business-logic test assertions are gated off.** The status and schema test tiers are
  reliable and ship; a third tier that asserts on actual response values exists in code
  but isn't wired up yet, because the quality bar for "guessed the right assertion" isn't
  there.
- **A route registered through a dynamic import, a computed prefix, or across a package
  boundary can't be traced.** Route composition (`app.use('/api', router)` in one file,
  routes registered in another) resolves through a real import graph now, not a leaf-only
  regex — see [`input/structural.py`](postman_mcp/input/structural.py) — but a mount the
  resolver genuinely can't follow (the prefix comes from a variable, not a literal) is
  reported as unresolved rather than guessed at.
- **No CI integration yet.** No GitHub Action to fail a PR on drift, no Newman runner for
  the generated tests. See [ROADMAP.md](ROADMAP.md) for the full list of known gaps.
- **An additional, verification-focused tool surface has no slash command yet.**
  Alongside the seven commands above, the MCP server also exposes a lower-level tool
  surface for MCP clients that want to submit an API model directly and get it verified,
  planned, and applied as separate steps, with snapshot/rollback support. It's callable
  today as direct MCP tool calls; there's no `/postman:*` wrapper for it yet. See
  [`docs/architecture/handoff.md`](docs/architecture/handoff.md) for what it does and its
  other current limitations.

## Architecture

Two layers, cleanly separated. **Claude Code does the reading and reasoning; Postman MCP
does the checking and writing.**

```text
You
 │  slash command (/postman:prompt for free-form instructions)
 ▼
Claude Code            ← reads your code, authors collection.json + metadata.json
 │  sync_files(confirm)
 ▼
Postman MCP Server (local)   ← deterministic: validate, verify citations, ground
 │                              fields, diff, merge, write
 ┌──────────┬──────────┬───────────┬──────────┐
 ▼          ▼          ▼           ▼          ▼
Repo       Citation   Postman     Merge      Config +
index      + field    client      engine     Secret store
           verify     (REST)
```

The sync commands (`syncapi`, `sync`, `syncall`, `syncchanges`, and `prompt` as a
natural-language front-end for all four) aren't separate implementations. They're
different ways of picking *which* routes Claude analyzes (one route, a whole file,
everything changed since your last sync, the whole codebase); all of them go through the
same validate → verify → diff → confirm → write pipeline on the MCP side. Fix a bug there
and every command gets the fix at once. Full write-up in the
[architecture docs](https://logesh-works.github.io/postman-mcp/architecture/overview/).

The MCP server runs **no LLM** and interprets no natural language. Anything you write in
`/postman:prompt` is read by Claude *before* it calls the tool — it never reaches the
server as prose. See [AI-assisted synchronization](#ai-assisted-synchronization) below.

## AI-assisted synchronization

For free-form, natural-language sync, use the **`/postman:prompt`** command. Claude reads
the instruction, not the MCP server.

```bash
/postman:prompt "Sync createPayment as a Stripe API architect"
```

Claude reads the instruction while preparing the synchronization — it picks the right
scope (`syncapi` / `sync` / `syncchanges` / `syncall`) and target, shapes how it frames
the diff and which examples it favors, and folds concrete asks (extra error responses,
headers, an edited description) directly into the `collection.json`/`metadata.json` it
authors. Then it calls the deterministic tool. The flow is:

```text
You → Claude Code (reads instruction + code, authors the collection) → MCP tool call → Postman MCP
```

What this means in practice:

- **The instruction influences Claude.** Reasoning, terminology, persona, target
  selection, and the request/response content Claude writes for matched items.
- **It never influences verification.** Citations either match your code or they don't;
  route identity, auth detection, and field grounding are computed deterministically from
  your code, regardless of what the instruction says. Content the instruction adds with
  no citation is shown as unverified in the diff — honestly, not silently trusted.
- **Postman MCP stays deterministic and LLM-agnostic.** It does not run a model, has no
  `prompt` parameter, and depends on no Anthropic/OpenAI API.

A few more examples:

```bash
/postman:prompt "Sync createOrder using Indian ecommerce examples"
/postman:prompt "Sync what changed and write full descriptions and error documentation"
/postman:prompt "Sync the whole codebase with complete request/response docs on every route"
```

See [`examples/prompts/`](examples/prompts/) for ready-made guidance you can adapt.

## Installation

```bash
pip install postman-mcp
```

Requires Python 3.10 or newer, [Claude Code](https://claude.com/claude-code), and a
Postman personal API key. See
[Installation](https://logesh-works.github.io/postman-mcp/getting-started/installation/)
for the full walkthrough.

## Quick start

```bash
# 1. install
pip install postman-mcp

# 2. set up this project (once)
cd my-api-project
postman-mcp init
#   → paste your Postman API key
#   → pick workspace + collection
#   → done: server registered, slash commands installed

# 3. open Claude Code in this project, then:
/postman:syncall        # first full sync
/postman:syncchanges    # from now on, after each change

# if something looks wrong:
postman-mcp doctor      # checks the whole setup chain
```

After `init`, you don't go back to the terminal for day-to-day use. Everything happens
through slash commands.

## Commands

| Command | What it does |
|---|---|
| [`/postman:syncapi`](https://logesh-works.github.io/postman-mcp/commands/syncapi/) `<fn\|"METHOD /route"\|code> [--into path]` | Sync one route. |
| [`/postman:syncchanges`](https://logesh-works.github.io/postman-mcp/commands/syncchanges/) `[--last N] [--since ref]` | Sync what changed since the last sync. The one you run most. |
| [`/postman:sync`](https://logesh-works.github.io/postman-mcp/commands/sync/) `-<file\|module\|dir> [--into path]` | Sync everything in one file, module, or directory. |
| [`/postman:syncall`](https://logesh-works.github.io/postman-mcp/commands/syncall/) `[--into path]` | Sync the whole codebase. Usually a first-run thing. |
| [`/postman:prompt`](https://logesh-works.github.io/postman-mcp/commands/prompt/) `"<plain-English instruction>"` | Natural-language sync — add error responses, headers, personas, etc. |
| [`/postman:createenv`](https://logesh-works.github.io/postman-mcp/commands/createenv/) `[name]` | Generate a Postman environment from your code. |
| [`/postman:status`](https://logesh-works.github.io/postman-mcp/commands/status/) `[--since ref]` | Show drift without writing anything. |

Terminal-only commands: `postman-mcp init`, `postman-mcp doctor`, `postman-mcp serve`,
`postman-mcp version`.

Every slash command above goes through the same validate → verify → diff → confirm →
write pipeline described in [How does it work?](#how-does-it-work). MCP clients that
prefer deterministic parsing over Claude-driven discovery can call the underlying
tools directly instead of going through a slash command; both paths share the exact
same diff/merge engine, so "new / modified / unchanged" is decided identically either
way. See [Architecture](https://logesh-works.github.io/postman-mcp/architecture/overview/)
for the full tool surface.

## Examples

Each example is a small, runnable app. Clone the repo and look at the README in any of
these to see the exact diff output and the real generated Collection item for that
framework:

| Example | Framework | Input path |
|---|---|---|
| [`fastapi-basic/`](examples/fastapi-basic/) | FastAPI | code parsing |
| [`fastapi-openapi/`](examples/fastapi-openapi/) | FastAPI | OpenAPI spec |
| [`django-rest-framework/`](examples/django-rest-framework/) | Django REST Framework | OpenAPI |
| [`express-api/`](examples/express-api/) | Express | code parsing |
| [`nestjs-api/`](examples/nestjs-api/) | NestJS | OpenAPI |
| [`flask-api/`](examples/flask-api/) | Flask | code parsing |
| [`spring-api/`](examples/spring-api/) | Spring (Boot) | code parsing |

## Configuration

Setup writes a `postman/config.json` to your project root. It's small, meant to be
committed, and never holds a secret directly, just a reference to where the key lives
(OS keychain, an env var, or a gitignored file). See
[Configuration](https://logesh-works.github.io/postman-mcp/getting-started/configuration/)
for every field.

## Framework support

| Framework | OpenAPI path | Code-parsing fallback |
|---|---|---|
| FastAPI | yes (native `/openapi.json`) | yes, AST-based |
| NestJS | yes, with `@nestjs/swagger` | yes, heuristic (no TS AST) |
| Django REST Framework | yes, with `drf-spectacular` | yes, including `DefaultRouter`/`SimpleRouter`-registered viewsets |
| Express | no native spec support | yes, this is the primary path |
| Flask | no native spec support | yes, AST-based |
| Spring (Boot) | no native spec support | yes, annotation-based |

Details and the specific known limits for each are in the
[framework guides](https://logesh-works.github.io/postman-mcp/frameworks/fastapi/).

## Release notes

See [CHANGELOG.md](CHANGELOG.md) for what shipped in each release, and
[ROADMAP.md](ROADMAP.md) for what's next and the current list of known gaps.

## Contributing

```bash
git clone https://github.com/logesh-works/postman-mcp
cd postman-mcp
python -m venv .venv && pip install -e ".[dev]"
pytest --cov
```

See [CONTRIBUTING.md](CONTRIBUTING.md) and the
[Code of Conduct](CODE_OF_CONDUCT.md) before opening a PR.

## Security

Your Postman API key is stored by reference, never written into the repo, and every
write to Postman goes through the diff-confirm step described above. To report a
vulnerability, don't open a public issue, see [SECURITY.md](SECURITY.md) for how to
reach the maintainer privately.

## License

[MIT](LICENSE) © Logesh Kumar (logeshkumar.in).
