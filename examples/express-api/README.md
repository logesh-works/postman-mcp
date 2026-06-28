# Example: Express (code parsing)

Express has no native OpenAPI spec and no native type system, so this example exercises
the **code-parsing path**. Every request is tagged `[code]`. Body confidence depends on
the source: a JSDoc `@body {type} name` annotation (or a Joi/Zod/Yup schema) is an
explicit author declaration and counts as **high confidence**, while fields only inferred
from `req.body` usage are flagged "lower confidence" in the diff. The `POST /payments`
route here is annotated with JSDoc, so its body is read at high confidence: no warning.

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
| Status | Method | Route | Target | Auth | Body | Response | Source |
|---|---|---|---|---|---|---|---|
| [NEW] | POST | /payments | payments | Bearer | RequestBody | 201 | [code] |
| [NEW] | GET | /payments/:id | payments | Bearer | N/A | 200 | [code] |

Summary: 2 new · 0 modified · 0 deprecated

Write? [y / n]   (nothing writes on n)
```

No "lower confidence" footnote appears: the `POST /payments` body fields come from the
route's JSDoc `@body` tags, which the parser treats as an explicit declaration. Strip
those tags and the same fields would still be picked up from the `req.body` destructuring,
but then they'd be flagged lower confidence, since usage alone carries no type
information.

> **Tip:** adopting a spec generator (`swagger-jsdoc`, `tsoa`) upgrades Express to the
> high-confidence OpenAPI path for every route at once. See the
> [Express framework guide](../../docs/frameworks/express.md).

## Generated output

The real Collection v2.1 items the parser and engine produce for this app are checked in
under [`expected-output/`](expected-output/), one file per route.
[`post-payments.item.json`](expected-output/post-payments.item.json) carries the
`amount` / `currency` / `method` body fields read from the JSDoc `@body` tags (not an
empty `{}`), so the fixture also guards against regressing body extraction.
