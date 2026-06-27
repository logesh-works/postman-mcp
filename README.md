<div align="center">

<img src="assets/logo/logo.svg" alt="Postman MCP" width="96" height="96">

# Postman MCP

**Sync your API code into Postman collections — body, params, auth, responses, tests, and examples — with zero manual fill, straight from Claude Code.**

OpenAPI-first · code-parsing fallback · a diff before every write.

[![PyPI](https://img.shields.io/pypi/v/postman-mcp.svg)](https://pypi.org/project/postman-mcp/)
[![Python](https://img.shields.io/pypi/pyversions/postman-mcp.svg)](https://pypi.org/project/postman-mcp/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![CI](https://github.com/logesh-works/postman-mcp/actions/workflows/ci.yml/badge.svg)](https://github.com/logesh-works/postman-mcp/actions/workflows/ci.yml)
[![codecov](https://codecov.io/gh/logesh-works/postman-mcp/branch/main/graph/badge.svg)](https://codecov.io/gh/logesh-works/postman-mcp)
[![Docs](https://img.shields.io/badge/docs-mkdocs-blue.svg)](https://logesh-works.github.io/postman-mcp/)

[Documentation](https://logesh-works.github.io/postman-mcp/) ·
[Quickstart](https://logesh-works.github.io/postman-mcp/getting-started/quickstart/) ·
[Commands](https://logesh-works.github.io/postman-mcp/commands/) ·
[Roadmap](ROADMAP.md)

</div>

---

> **Demo** — _an animated `syncapi` → diff → write recording goes here at launch
> (see [`assets/README.md`](assets/README.md))._

```text
/postman:syncapi createPayment --into payments

SYNC PREVIEW — POST /payments  →  collection / payments   [NEW] [openapi]

+ Request    POST {{base_url}}/payments
+ Auth       Bearer {{token}}              (from require_auth middleware)
+ Body       { "amount": 4200, "currency": "USD", "method": "card" }
+ Responses  201 Created, 400, 401, 422, 500
+ Tests      status(201) · schema(PaymentResponse) · business(amount > 0)
+ Examples   1 success, 4 error

Write? [y / n]
```

## The problem

API code and Postman drift apart the moment you ship. Every new route, changed body
shape, or added error response means going back into Postman by hand — re-typing fields,
re-writing example data, re-doing test scripts. The work is mechanical, constant, and easy
to skip, so collections rot. A rotten collection is worse than none: teammates trust it,
then get burned by a stale endpoint.

The code already contains everything Postman needs — routes, types, middleware, comments.
There's no reason a human should be the copy machine between them.

## Why Postman MCP

- **Zero manual fill.** Body, params, auth headers, every response, examples, and test
  scaffolds — all generated from your code.
- **OpenAPI-first.** When your framework emits a spec, one mapper covers FastAPI, NestJS,
  and Django REST Framework. No spec? It falls back to parsing your code.
- **Diff before every write.** Nothing reaches Postman until you've seen exactly what
  changes. There is no skip flag.
- **Never destroys your work.** Test scripts, manual examples, and edited descriptions are
  read back and preserved on every sync.
- **Secrets never touch the repo.** Your Postman API key is stored by reference — OS
  keychain, env var, or a gitignored file.
- **Low token cost.** `syncchanges` parses only what you changed and reads just the
  collection's basic structure — never a full re-scan.

## Features

| | |
|---|---|
| **Five sync commands** | from one route to the whole codebase |
| **Frameworks** | FastAPI · Django REST Framework · Express · NestJS |
| **Input** | OpenAPI 3.x spec (preferred) or framework code parsing, decided per route |
| **Output** | complete Postman Collection v2.1 items — request, responses, scripts, examples, docs |
| **Tests** | status + schema tiers (deterministic); business-logic tier gated/opt-in |
| **Safety** | diff-before-write, soft deletes, preserved human work, secret masking |

## Architecture

```text
Claude Code  ──slash commands──▶  Postman MCP Server (local)
             ◀──diffs/prompts───
                                      │
   ┌──────────┬──────────┬───────────┼──────────┬───────────┐
   ▼          ▼          ▼           ▼          ▼           ▼
Command    Input      Engine     Postman      Git        Config +
router     resolver  (builder)   client      reader      Secret store
         (OpenAPI/                (REST)    (diff since
          code)                              commit)
```

The five sync commands are **one engine plus five selectors** — the engine turns a
normalized route model into a complete Postman request; the selectors decide which code
goes in and where it lands. Full write-up in the
[architecture docs](https://logesh-works.github.io/postman-mcp/architecture/overview/).

## Installation

```bash
pip install postman-mcp
```

Requires Python ≥ 3.10, [Claude Code](https://claude.com/claude-code), and a Postman
personal API key. See [Installation](https://logesh-works.github.io/postman-mcp/getting-started/installation/).

## Quick start

```bash
# 1. install
pip install postman-mcp

# 2. set up this project (once)
cd my-api-project
postman-mcp init
#   → paste your Postman API key
#   → pick workspace + collection
#   → done: server registered, commands installed

# 3. open Claude Code in this project, then:
/postman:syncall        # first full sync
/postman:syncchanges    # from now on, after each change

# anytime something looks off:
postman-mcp doctor      # checks the whole setup chain
```

## How it works

| Step | Where | What |
|---|---|---|
| `pip install postman-mcp` | terminal | CLI + MCP server + slash commands + engine |
| `postman-mcp init` | terminal | key handshake, pick workspace + collection, write config, register MCP server, install slash commands |
| `/postman:*` | Claude Code | sync APIs into the collection |

Three actions — **install**, **init**, then **use inside Claude Code**. After init, you
never touch the terminal again for normal work.

## Commands

| Command | What it does |
|---|---|
| [`/postman:syncapi`](https://logesh-works.github.io/postman-mcp/commands/syncapi/) `<fn\|"METHOD /route"\|code> [--into path]` | Sync **one** API (the kernel). |
| [`/postman:syncchanges`](https://logesh-works.github.io/postman-mcp/commands/syncchanges/) `[--last N] [--since ref]` | Sync **what changed** since last sync (daily driver). |
| [`/postman:sync`](https://logesh-works.github.io/postman-mcp/commands/sync/) `-<file\|module\|dir> [--into path]` | Sync everything in one file/module/dir. |
| [`/postman:syncall`](https://logesh-works.github.io/postman-mcp/commands/syncall/) `[--into path]` | Sync the **whole** codebase. |
| [`/postman:createenv`](https://logesh-works.github.io/postman-mcp/commands/createenv/) `[name]` | Generate a Postman environment from code. |
| [`/postman:status`](https://logesh-works.github.io/postman-mcp/commands/status/) `[--since ref]` | Read-only drift check. No writes. |

Terminal-only: `postman-mcp init`, `postman-mcp doctor`, `postman-mcp serve`,
`postman-mcp version`.

## Examples

Runnable examples per framework live in [`examples/`](examples/):

| Example | Framework | Input path |
|---|---|---|
| [`fastapi-basic/`](examples/fastapi-basic/) | FastAPI | code parsing |
| [`fastapi-openapi/`](examples/fastapi-openapi/) | FastAPI | OpenAPI spec |
| [`django-rest-framework/`](examples/django-rest-framework/) | Django REST Framework | OpenAPI |
| [`express-api/`](examples/express-api/) | Express | code parsing |
| [`nestjs-api/`](examples/nestjs-api/) | NestJS | OpenAPI |

## Configuration

All config lives in a small, committable, secret-free `postman-mcp.json` at your project
root. See [Configuration](https://logesh-works.github.io/postman-mcp/getting-started/configuration/).

## Framework support

OpenAPI-first for FastAPI, NestJS (`@nestjs/swagger`), and DRF (`drf-spectacular`);
code-parsing fallback for all four, with Express as the primary code-path case. Details and
known limits in the [framework guides](https://logesh-works.github.io/postman-mcp/frameworks/fastapi/).

## Roadmap

`0.1.0` MVP → `0.2.0` hardening → `0.3.0` CI + Newman → `1.0.0` stable. See
[ROADMAP.md](ROADMAP.md).

## Contributing

Contributions welcome! See [CONTRIBUTING.md](CONTRIBUTING.md), the
[Code of Conduct](CODE_OF_CONDUCT.md), and the
[development docs](https://logesh-works.github.io/postman-mcp/development/contributing/).

```bash
git clone https://github.com/logesh-works/postman-mcp
cd postman-mcp
python -m venv .venv && pip install -e ".[dev]"
pytest --cov
```

## Security

The API key is stored by reference only and every write is gated behind a diff. Report
vulnerabilities privately — see [SECURITY.md](SECURITY.md).

## License

[MIT](LICENSE) © Logeshkumar (logeshkumar.in).

---

<div align="center">
<sub>Built to implement <code>postman-mcp-prd-v3.md</code> (v3.1). Code is the source of
truth for what an API <em>is</em>; Postman for what <em>exists</em>.</sub>
</div>
