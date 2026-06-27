---
hide:
  - navigation
---

# Postman MCP

**Sync your API code into Postman collections — body, params, auth, responses, tests, and
examples — with zero manual fill, straight from Claude Code.**

OpenAPI-first, code-parsing fallback, and a diff before every write.

[Get started](getting-started/installation.md){ .md-button .md-button--primary }
[View on GitHub](https://github.com/logesh-works/postman-mcp){ .md-button }

---

## The problem

API code and Postman drift apart the moment you ship. Every new route, changed body
shape, or added error response means going back into Postman by hand — re-typing fields,
re-writing example data, re-doing test scripts. The work is mechanical, constant, and
easy to skip, so collections rot. A rotten collection is worse than none: teammates trust
it, then get burned by a stale endpoint.

The code already contains everything Postman needs — routes, types, middleware, comments.
There's no reason a human should be the copy machine between them.

## What Postman MCP does

It's an [MCP](https://modelcontextprotocol.io) server for Claude Code that reads your
codebase and writes **fully-populated** Postman requests. Five sync commands cover the
range from "one route" to "the whole project":

```text
/postman:syncapi createPayment --into payments
```

```text
SYNC PREVIEW — POST /payments  →  collection / payments   [NEW] [openapi]

+ Request    POST {{base_url}}/payments
+ Auth       Bearer {{token}}              (from require_auth middleware)
+ Body       { "amount": 4200, "currency": "USD", "method": "card" }
+ Responses  201 Created, 400, 401, 422, 500
+ Tests      status(201) · schema(PaymentResponse) · business(amount > 0)
+ Examples   1 success, 4 error

Write? [y / n]
```

## Why developers use it

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
- **Low token cost.** `syncchanges` parses only the files you changed and reads just the
  collection's basic structure — never a full re-scan.

## The three-action journey

| Step | Where | What |
|---|---|---|
| `pip install postman-mcp` | terminal | CLI + MCP server + slash commands + engine |
| `postman-mcp init` | terminal | key handshake, pick workspace + collection, write config, register MCP server, install slash commands |
| `/postman:*` | Claude Code | sync APIs into the collection |

Three actions — **install**, **init**, then **use inside Claude Code**. After init, you
never touch the terminal again for normal work.

[Install Postman MCP →](getting-started/installation.md){ .md-button .md-button--primary }
