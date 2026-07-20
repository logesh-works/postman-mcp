# Skill: Metadata Builder

**Responsibility:** build `metadata.json` — the verification sidecar the MCP re-reads to
check you didn't hallucinate. This is what turns everything the other discovery skills
found into citations the MCP can mechanically verify.

Write one `metadata.json` per `collection.json` you wrote: `postman/sync/<module>/
metadata.json` next to that module's `collection.json`, or `postman/sync/metadata.json`
next to the ungrouped root file. Same shape either way — just the subset of endpoints
that live in that one file.

## Shape

```json
{
  "endpoints": [
    {
      "key": "POST:/api/users",
      "citations": [
        { "file": "src/users/users.controller.ts", "line_start": 20, "line_end": 23,
          "symbol": "create", "snippet_sha256": "<sha256>", "quote": "@Post()  create(@Body() dto: CreateUserDto) {" }
      ],
      "body": {
        "dto": { "file": "src/users/dto/create-user.dto.ts", "line_start": 3, "line_end": 8, "symbol": "CreateUserDto",
                 "snippet_sha256": "<sha256>", "quote": "export class CreateUserDto {" },
        "fields": ["email", "password"]
      },
      "responses": [
        { "dto": { "file": "src/users/dto/user.dto.ts", "line_start": 1, "line_end": 6, "symbol": "UserDto",
                   "snippet_sha256": "<sha256>" },
          "fields": ["id", "email", "createdAt"] }
      ],
      "auth": {
        "cited": { "file": "src/users/users.controller.ts", "line_start": 18, "line_end": 18,
                   "snippet_sha256": "<sha256>", "quote": "@UseGuards(AuthGuard)" },
        "required": true, "scheme": "bearer"
      }
    }
  ]
}
```

## Field-by-field

- **`key`** — `METHOD:/normalized-path`, and must match the request's method + URL path in
  `collection.json` exactly (path-param spelling is normalized on both sides). This is how
  the MCP joins metadata to the request; get it wrong and the endpoint shows as
  completely unverified even if every citation is correct.
- **`citations`** — from `api-discovery`: the registration-site span(s) proving the
  endpoint exists.
- **`body`/`responses[]`** — from `dto-discovery`: `dto` cites the **class declaration**
  line (not the handler), `fields` lists the real attribute names on that class.
- **`auth`** — from `auth-discovery`, or omitted entirely if no evidence was found.

## Getting `snippet_sha256` right: use the `cite` tool

**Canonical path — do not hash by hand.** Call the MCP's **`cite`** tool with the spans
you want to cite:

```json
cite(spans=[
  {"file": "src/users/users.controller.ts", "line_start": 20, "line_end": 23, "symbol": "create"},
  {"file": "src/users/dto/create-user.dto.ts", "line_start": 3, "line_end": 8, "symbol": "CreateUserDto"}
])
```

It returns complete citation objects — `snippet_sha256` and `quote` computed by the MCP
with the exact same hashing spec the verifier uses, so they round-trip by construction.
Paste them into `metadata.json` verbatim. The `file:start-end` headers on `context()`
bundles are exactly the spans this tool takes, so discovery output feeds it directly.
Batch all your spans into one call (up to 200).

This does not weaken verification: the hash's job is catching code drift between citing
and syncing (still fully enforced — the MCP re-audits at sync time), and the class/field
grounding still proves you actually read what you cite. What it removes is the one step
no model can do natively — computing SHA-256 — which was only ever an error source.

If you hash manually anyway (e.g. the tool is unavailable): exact cited lines, joined by
`\n`, each right-stripped of trailing whitespace, UTF-8, SHA-256 hex. Be aware there is
**no soft fallback**: a missing or wrong hash cannot verify, and on a `dto`/`auth`
citation that excludes the endpoint from the write.

## The severity model this feeds (know this before you cite loosely)

- **Citation integrity is strict.** Every citation here (`citations`, `body.dto`,
  `responses[].dto`, `auth.cited`) is hash-verified exactly like an identity citation. A
  citation that doesn't match the code (wrong file/line, or a hash that doesn't match
  those exact lines) **excludes that entire endpoint** from the write — not a soft
  warning, because a bad citation means nothing else claimed about that dimension can be
  trusted either.
- **Field-name accuracy is soft.** A claimed field the cited (correctly verified) class
  doesn't actually have is just a named warning; the endpoint still syncs. So: get the
  citation's file/line/hash exactly right — a wrong field name on top of a correct
  citation is forgiving, a wrong citation is not.
- **Missing evidence is informational, never punitive.** Omitting `body`, `responses`, or
  `auth` entirely (or omitting just their citation) is honest and shows as "unverified" —
  it never excludes the endpoint. Don't fabricate a citation just to avoid an unverified
  label; a fabricated one is strictly worse (it excludes the endpoint outright).
- **Duplicate `key`s are rejected.** If this `key` appears more than once anywhere under
  `postman/sync/` (this file, another module's `metadata.json`, or matches more than one
  request item across every `collection.json`), all copies are excluded — the MCP can't
  tell which is authoritative.

## `postman/sync/sync.config.json` — scope echo (optional but recommended)

Not per-endpoint, but built alongside metadata.json:
```json
{ "scope": "all", "target": null, "into": null, "collection_id": "<from postman/config.json>",
  "generator": "<your model name>", "notes": ["what you did / anything the user should know"] }
```
Use `notes` for anything you couldn't resolve (a runtime-computed prefix, an ambiguous
DTO) instead of guessing silently.
