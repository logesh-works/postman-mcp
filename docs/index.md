---
hide:
  - navigation
---

# Postman MCP

**Generate and update Postman requests from your API code, from inside Claude Code.**

[Get started](getting-started/installation.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/logesh-works/postman-mcp){ .md-button }

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

## What it does

It's an [MCP](https://modelcontextprotocol.io) server for Claude Code. You run a slash
command, it builds the Postman request from your code, shows you a diff, and writes only
if you confirm.

```text
/postman:syncapi create_payment --into payments
```

```text
| Status | Method | Route | Target | Auth | Body | Response | Source |
|---|---|---|---|---|---|---|---|
| [NEW] | POST | /payments | payments | Bearer | PaymentRequest | 201 | [code] |

Summary: 1 new · 0 modified · 0 deprecated

Write? [y / n]
```

There are seven commands in total, five of them variations on "sync" — covering
everything from one route to the whole codebase — plus `createenv` and `status`.
See [Commands](commands/index.md) for all of them, and [The engine](architecture/engine.md)
for the actual JSON this produces.

## AI-assisted, but deterministic

Postman MCP keeps two layers cleanly separated: **Claude Code is the intelligence layer;
the MCP server is the deterministic execution layer.** For free-form, natural-language
sync use [`/postman:prompt`](commands/prompt.md):

```text
/postman:prompt "Sync createPayment as a Stripe API architect"
```

Claude reads the instruction — persona, terminology, example style, concrete additions —
picks the right tool and target, and expresses the "how" as a structured `overrides`
patch the deterministic engine merges before the diff. The instruction is **consumed by
Claude, never by the MCP server**: it influences reasoning, not engine structure. The
server runs no LLM and depends on no AI provider API. See the
[Prompt & skill layer](architecture/overview.md#prompt-skill-layer).

## How it decides what to read

Two sources feed the same pipeline, picked per route:

- **OpenAPI spec**, when your framework can emit one. FastAPI does this natively; NestJS
  needs `@nestjs/swagger`; Django REST Framework needs `drf-spectacular`. This is the
  high-confidence path, since the spec is already typed and validated by the framework.
- **Direct code parsing**, when there's no spec. This works for all six supported
  frameworks and is the only path for Express, which has no native type system or spec
  generator.

Whichever source a route comes from, it gets normalized into the same `RouteModel` before
the engine ever sees it, so the rest of the pipeline doesn't care where the route came
from. See [Architecture](architecture/overview.md) for the full breakdown.

## What you get without lifting a finger

- Request body, with realistic example values, built from your Pydantic model / DTO /
  serializer / JSDoc annotation, whichever your framework gives the parser to work with.
- Auth headers, when the route sits behind a dependency, guard, or middleware the parser
  recognizes.
- One saved response by default (the declared success response), with `minimal` and
  `full` available if you want error responses saved too.
- A diff before every write, with no flag to skip it. If a route is ambiguous, you get a
  list of candidates instead of a guess.
- Your hand-edited test scripts, examples, and descriptions, preserved on every re-sync
  instead of overwritten.
- Your Postman API key stored by reference (OS keychain, env var, or a gitignored file),
  never written into the repo or the committed config.

## Setup, in three steps

| Step | Where | What happens |
|---|---|---|
| `pip install postman-mcp` | terminal | Installs the CLI, the MCP server, and the slash-command templates. |
| `postman-mcp init` | terminal | Handshakes your API key, lets you pick a workspace and collection, writes `postman-mcp.json`, registers the MCP server, installs the slash commands. |
| `/postman:*` | Claude Code | Day-to-day syncing. |

After `init`, you don't go back to the terminal for normal use.

[Install Postman MCP →](getting-started/installation.md){ .md-button .md-button--primary }
