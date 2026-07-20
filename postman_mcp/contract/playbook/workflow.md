# Sync workflow (LLM-driven)

You (the LLM) analyze the project and write files to `postman/sync/`. The MCP validates
them, **re-reads your citations to verify you didn't hallucinate**, diffs against the live
Postman collection, and syncs on the user's confirm. You never call the Postman API
yourself, and the MCP never analyzes your source code — it only checks what you claim.

This works for **any** framework/language, driven by any MCP-capable LLM. There is no
parser and no framework list; your understanding of the code is the discovery engine.

## Skills

The actual discovery/building know-how lives in individually loadable skills, returned by
`get_sync_contract()`'s `skills` dict — each single-responsibility, so a command loads
only the ones it needs:

| Skill | Responsibility |
|---|---|
| `project-analysis` | Scope + service boundaries for this command |
| `api-discovery` | Find endpoints, resolve full paths, cite registration sites |
| `auth-discovery` | Find where auth is enforced, cite it |
| `dto-discovery` | Resolve request/response DTO classes + fields, cite the class |
| `request-builder` | Build `collection.json`'s `request` object |
| `response-builder` | Build `collection.json`'s `response[]` array |
| `folder-builder` | Organize requests into folders |
| `collection-builder` | Assemble the full `collection.json` |
| `metadata-builder` | Build `metadata.json` (citations) + `sync.config.json` |
| `environment-discovery` | `createenv` only — find env vars, build `environment.json` |

Each command's `.md` names exactly which skills to load — **pass that list to
`get_sync_contract(skills=[...])`** so the response contains only what you need
(`createenv` needs 2 of 10; the response's `available_skills` always lists every name).
Read this workflow doc first (cross-cutting rules below), then the named skills for the
discovery/building steps.

## Supporting tools (use them — they're cheaper and more accurate than doing it by hand)

- **`index()`** — once per session: a deterministic repo map (services, likely
  handler/DTO files). Orientation without exploratory reading.
- **`context(target, budget=8000)`** — per endpoint group: a pre-sliced bundle (handler,
  DTO closure, mount chain, witnesses), each chunk headed `file:start-end`.
- **`cite(spans=[...])`** — turns those `file:start-end` spans into complete citations
  with MCP-computed `snippet_sha256` — never hash by hand.

## The files, and where they go

All under `postman/sync/` (or `syncDir` from `postman/config.json` if configured).
**Organize by module** — one subfolder per logical module (`auth/`, `users/`, `orders/`,
...), each with its own `collection.json` (+ `metadata.json`). The MCP assembles every
module into one named Postman folder inside the target collection, so a module's
endpoints, their citations, and the code they came from all stay together in one place
on disk — smaller diffs, and `sync <module>` only ever touches that module's two files.
An ungrouped `postman/sync/collection.json` (+ `metadata.json`) is also allowed for
endpoints that don't belong to any module (or for a small API with no real modules yet);
its items land at the collection's top level instead of inside a named folder. At least
one of the two — the root pair or a module subfolder — must exist.

| File | Built by | Purpose |
|---|---|---|
| `postman/sync/<module>/collection.json` | `collection-builder` (+ request/response/folder builders) | That module's requests — becomes one named folder in the assembled collection. `info.name` is the folder's display name. |
| `postman/sync/<module>/metadata.json` | `metadata-builder` | That module's verification sidecar — citations + claimed DTO fields, keyed the same way as the flat layout |
| `postman/sync/collection.json` | `collection-builder` | Optional: ungrouped requests, land at the collection root (no wrapping folder) |
| `postman/sync/metadata.json` | `metadata-builder` | Optional: metadata for the ungrouped requests above |
| `postman/sync/sync.config.json` | `metadata-builder` | Scope/target echo (optional but recommended) — shared across all modules |
| `postman/sync/environment.json` | `environment-discovery` | `createenv` only — shared across all modules |

Pick module boundaries the same way you'd already group requests into folders — by
service/domain (auth, users, orders), not by source file. The directory name is just a
stable key (lowercase, hyphen/underscore, no spaces); `info.name` inside that module's
`collection.json` is what actually shows as the folder name in Postman.

## The severity model (governs every validation the MCP runs)

1. **Citation integrity — strict.** Every citation (endpoint identity, `body.dto`,
   `responses[].dto`, `auth.cited`) is hash-verified against the working tree. A citation
   that doesn't match the code excludes that endpoint from the write.
2. **Schema accuracy — soft.** A claimed DTO field the (correctly cited) class doesn't
   have is a named warning; the endpoint still syncs.
3. **Structural integrity — fatal.** Invalid JSON, a missing required field, duplicate
   sibling folder names — the *entire* sync is aborted, nothing written, until fixed.
4. **Missing evidence — informational.** Omitting a citation entirely (never providing
   one, as opposed to providing a wrong one) shows as unverified and never blocks anything.

Full detail on each tier lives in the skill responsible for producing that evidence
(mainly `metadata-builder`).

## `snippet_sha256`

Use the **`cite` tool** — the MCP computes the hash for the spans you name, with the
exact spec the verifier re-checks against, so citations round-trip by construction (see
`metadata-builder` for details). Manual hashing spec, if you must: exact cited lines,
joined by `\n`, each right-stripped, UTF-8, SHA-256 hex. There is no soft fallback — a
missing or wrong hash cannot verify, and on a `dto`/`auth` citation that excludes the
endpoint from the write.

## The sequence every command follows

```
1. get_sync_contract(skills=[...])        → schemas + this workflow + only the named skills
2. index()                                → repo map (once per session)
3. context(target) per endpoint group     → bounded, citation-ready code bundles
4. cite(spans=[...])                      → MCP-computed citations for the spans you used
5. write postman/sync/<module>/{collection,metadata}.json per module (+ sync.config.json,
   + environment.json for createenv) — or postman/sync/{collection,metadata}.json for
   ungrouped endpoints
6. sync_files(confirm=false)   [or sync_env for createenv]   → validate, verify, diff — writes nothing
7. show the returned preview verbatim
8. ask "Write to Postman? [y/n]"
9. only on yes: sync_files(confirm=true)  [or sync_env(confirm=true)]
10. report the result, then stop — no re-running, no unsolicited commentary
```

## The contract with the MCP

- You never call Postman. You only prepare `postman/sync/`.
- The MCP never re-derives your routes; it validates shape, re-reads your citations,
  field-grounds your DTO claims, diffs, merges (preserving human-authored test
  scripts/examples/edited descriptions already in Postman), and writes.
- Accuracy is your real reading of the code; the citation check is what keeps you honest.
