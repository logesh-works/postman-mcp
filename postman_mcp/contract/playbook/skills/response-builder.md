# Skill: Response Builder

**Responsibility:** turn each declared response (from `api-discovery`/`dto-discovery`)
into one entry of a Postman item's `"response": [...]` array — a saved example. Not the
request (`request-builder`), not the citation sidecar (`metadata-builder`).

## Shape

```json
{
  "name": "201 Created",
  "code": 201,
  "header": [{ "key": "Content-Type", "value": "application/json" }],
  "body": "{\n  \"id\": 1,\n  \"email\": \"user@example.com\",\n  \"createdAt\": \"2026-01-01T00:00:00Z\"\n}"
}
```

## Rules

- **One entry per distinct status code** the handler can actually return, as discovered
  from its return-type annotation, `@ApiResponse`/`response_model` decorators, explicit
  status-setting calls, or raised exceptions mapped to error codes by the framework.
  Don't invent status codes that aren't grounded in the code.
- **`code`** — the real numeric status (`201` for a typical create, `200` for a typical
  read/update, `204` for a no-body success, `404`/`400`/`401`/`403`/`422`/`500` for common
  error paths *only if the handler's code actually produces them* — a generic "standard
  error set" you add speculatively should be avoided unless asked for via
  `/postman:prompt`, since it isn't grounded and will show as unverified).
- **`body`** — a realistic JSON example built from the resolved response DTO's real field
  names/types (from `dto-discovery`), stringified. For a `204`/no-content response, omit
  `body` entirely.
- **`name`** — short and descriptive, e.g. `"201 Created"`, `"404 Not Found"`.

## What you're not doing here

Not deciding which endpoints exist or what their DTOs are (upstream skills), not building
the request half of the item (`request-builder`), not citing where any of this comes from
in `metadata.json` (`metadata-builder` — note that response DTO citations there are
per-response and hash-verified exactly like the request body's).
