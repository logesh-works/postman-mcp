# Skill: Collection Builder

**Responsibility:** assemble the outputs of `request-builder`, `response-builder`, and
`folder-builder` into one valid `collection.json` — either `postman/sync/<module>/
collection.json` for one module, or the ungrouped `postman/sync/collection.json`. This
is the last step before `metadata-builder` builds that same directory's `metadata.json`.

You write one of these files **per module**, not one giant document for the whole API —
`folder-builder` tells you which module (directory) a resource's requests belong to.

## Shape

Identical whether it's a module's file or the ungrouped root's:

```json
{
  "info": {
    "name": "<this module's folder name in Postman, e.g. \"Users\" — or, for the ungrouped root file, any non-empty placeholder; it's required but unused there>",
    "schema": "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  "item": [
    { "name": "Create user", "request": { "...": "from request-builder" }, "response": ["...from response-builder"] },
    { "name": "Get user", "request": { "...": "..." }, "response": ["..."] }
  ]
}
```

A module's `item[]` can itself nest sub-folders (per `folder-builder`) if that module has
real internal structure — most modules are fine as one flat list.

## Rules

- **`info.name`** — required in every `collection.json`, module or root. For a module
  file, this becomes that module's folder name in the assembled Postman collection — keep
  it stable across re-syncs (`folder-builder`). For the ungrouped root file it's validated
  but discarded; any non-empty string is fine.
- **`item`** — required, and must contain at least one request.
- **Every request item** needs a `name`, a `request` object (from `request-builder`) with
  a resolvable `method` + `url`, and a `response` array (from `response-builder`, may be
  empty for a request with no discovered responses — never invent one just to avoid an
  empty array).
- **No duplicate `METHOD + path`** — checked across *every* module's `collection.json`
  plus the ungrouped root, not just within the one file you're writing. Two request items
  that resolve to the same method+normalized-path anywhere are both excluded from the
  sync as an unresolvable ambiguity — make sure every endpoint you authored appears
  exactly once across the whole `postman/sync/` tree.
- **Scope discipline**: for a narrow-scope command (`syncapi`, `sync <file>`), only
  include the request(s) actually in scope — don't pad the module's collection with
  unrelated endpoints just because you noticed them while reading the code. Only rewrite
  the module(s) actually touched; leave every other module's files untouched.

## Validation this file will get from the MCP

Before anything is diffed or written, the MCP checks each `collection.json` it finds
(module and root): `info.name` present, `item[]` present and non-empty, every request
item resolvable to a method+url key, and no two sibling folders sharing a name — then,
once every file is assembled into one document, that no two modules produced the same
folder name and no method+path repeats across modules. Any failure here blocks the
*entire* sync (nothing is safely readable) — distinct from a per-endpoint citation
problem, which only excludes that one endpoint.
