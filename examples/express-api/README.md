# Example: Express (code parsing)

Express has no native OpenAPI spec and no native type system, so this example is a good
test of Claude reading source directly. Body confidence depends on what backs the claim:
a JSDoc `@body {type} name` annotation (or a Joi/Zod/Yup schema) is an explicit author
declaration and cites cleanly, while fields only inferred from `req.body` usage carry a
weaker citation and get flagged in the diff. The `POST /payments` route here is
annotated with JSDoc, so its body is read with a solid citation: no warning.

## The API

| Method | Path | Auth | Body |
|---|---|---|---|
| `POST` | `/payments` | ✅ | `{ amount, currency, method }` (from JSDoc `@body`) |
| `GET` | `/payments/:id` | ✅ | — |

## Run it

```bash
npm install
node app.js          # listening on :3000
postman-mcp init     # detects Express, sets inputMode = code
```

## Sync it

```text
/postman:sync -app.js --into payments
```

```text
Collection: <your collection>
Plan: 2 new · 0 modified

[NEW] POST /payments   → payments   ✓ verified (app.js:14)
[NEW] GET /payments/:id   → payments   ✓ verified (app.js:22)

Write to Postman? Re-run with confirm=true to apply.   (nothing writes on n)
```

No confidence warning appears: the `POST /payments` body fields come from the route's
JSDoc `@body` tags, an explicit declaration. Strip those tags and the same fields would
still be picked up from the `req.body` destructuring, but then they'd be flagged lower
confidence, since usage alone carries no type information.

> **Tip:** adopting a spec generator (`swagger-jsdoc`, `tsoa`) upgrades Express to the
> high-confidence OpenAPI path for every route at once. See the
> [Express framework guide](../../docs/frameworks/express.md).

## Generated output

The real Collection v2.1 items the parser and engine produce for this app are checked in
under [`expected-output/`](expected-output/), one file per route.
[`post-payments.item.json`](expected-output/post-payments.item.json) carries the
`amount` / `currency` / `method` body fields read from the JSDoc `@body` tags (not an
empty `{}`), so the fixture also guards against regressing body extraction.
