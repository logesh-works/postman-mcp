# Example: Express (code parsing)

Express has no native OpenAPI spec and no native type system, so this example exercises
the **code-parsing path**. Bodies are inferred best-effort from JSDoc `@body` annotations
and inline usage, and every request is tagged `[code]` and flagged "lower confidence" in
the diff.

## The API

| Method | Path | Auth | Body |
|---|---|---|---|
| `POST` | `/payments` | ✅ | `{ amount, currency, method }` (from JSDoc) |
| `GET` | `/payments/:id` | ✅ | — |

## Run it

```bash
npm install
node app.js          # listening on :3000
postman-mcp init     # detects Express → inputMode = code
```

## Sync it

```text
/postman:sync -app.js --into payments
```

```text
SYNC PREVIEW — 2 APIs in app.js  →  collection / payments
+ POST /payments      [new] [code]   ⚠ body lower-confidence (no native types)
+ GET  /payments/{id} [new] [code]

Write? [y / n]
```

> **Tip:** richer JSDoc `@body` annotations, or adopting a spec generator
> (`swagger-jsdoc`, `tsoa`), upgrades Express to the high-confidence OpenAPI path. See the
> [Express framework guide](../../docs/frameworks/express.md).
