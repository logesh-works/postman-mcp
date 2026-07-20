# Skill: Request Builder

**Responsibility:** turn one discovered endpoint (from `api-discovery`/`auth-discovery`/
`dto-discovery`) into a Postman `request` object — the part of a `collection.json` item
under `"request": {...}`. Not the response (`response-builder`), not where it sits in the
collection tree (`folder-builder`/`collection-builder`), not the citation sidecar
(`metadata-builder`).

## Shape

```json
{
  "method": "POST",
  "url": {
    "raw": "{{base_url}}/api/users/:id",
    "host": ["{{base_url}}"],
    "path": ["api", "users", ":id"]
  },
  "header": [{ "key": "Content-Type", "value": "application/json" }],
  "auth": { "type": "bearer", "bearer": [{ "key": "token", "value": "{{token}}" }] },
  "body": {
    "mode": "raw",
    "raw": "{\n  \"email\": \"user@example.com\",\n  \"password\": \"...\"\n}",
    "options": { "raw": { "language": "json" } }
  },
  "description": "<from the handler's docstring/comment, if any>"
}
```

## Rules

- **`method`** — uppercase, exactly as discovered.
- **`url.raw`/`host`** — always `{{base_url}}`, never a literal host, so the collection
  is environment-portable.
- **Path params** — keep them literal in the path, either `{id}` or `:id` spelling; the
  MCP normalizes either when matching against the live collection, so use whichever
  matches how the framework itself spells them.
- **`header`** — from discovered headers (a `@Headers('x-api-key')`-style parameter, a
  required custom header) plus `Content-Type: application/json` whenever there's a body.
- **`auth`** — from `auth-discovery`'s finding: `{"type": "bearer", "bearer": [{"key": "token", "value": "{{token}}"}]}`
  for bearer auth; omit the `auth` key entirely if the endpoint has no auth.
- **`body`** — from `dto-discovery`'s resolved request DTO fields: build a realistic
  example JSON object using the *real* field names and *plausible* values matching each
  field's real type (a string field named `email` gets an email-shaped string, an `int`
  gets a number, not a placeholder like `"string"` unless nothing better is inferable).
  Omit `body` entirely for methods that don't have one (GET/HEAD, or a DTO-less endpoint).
- **`description`** — carry over the handler's docstring/leading comment if there is one;
  leave it empty otherwise. Never invent a description not grounded in the code — a
  human editing this later in Postman is a "craft" edit the MCP preserves on the next
  sync, so an empty description isn't a problem.

## What you're not doing here

Not deciding folder placement (that's `collection-builder`, driven by `folder-builder`),
not writing the `response[]` array (that's `response-builder`), not writing the
`metadata.json` citation for this endpoint (that's `metadata-builder`).
