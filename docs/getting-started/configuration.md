# Configuration

All configuration lives in a single file at your project root: **`postman-mcp.json`**.
It is small, stable, and **safe to commit** — it holds only config and a last-update
marker, never secrets.

## `postman-mcp.json`

```json
{
  "version": 1,
  "config": {
    "framework": "fastapi",
    "inputMode": "openapi",
    "openApiSource": "http://localhost:8000/openapi.json",
    "workspace": "<workspace-id>",
    "collectionId": "<collection-uid>",
    "defaultInto": "/",
    "apiKeyRef": "keychain:postman-mcp"
  },
  "lastUpdate": {
    "commit": "a1b2c3d",
    "at": "2026-06-27T10:00:00Z"
  }
}
```

| Field | Meaning |
|---|---|
| `config.framework` | Detected framework: `fastapi`, `express`, `django`, or `nestjs`. |
| `config.inputMode` | `openapi` or `code` — which source the [resolver](../architecture/resolver.md) uses. Re-checked for freshness each sync. |
| `config.openApiSource` | File path or URL of the spec, when `inputMode` is `openapi`. |
| `config.workspace` | The Postman workspace id. |
| `config.collectionId` | The project's one collection — the default target for every sync. |
| `config.defaultInto` | Default folder path inside the collection when `--into` is omitted. |
| `config.apiKeyRef` | A **reference** to the API key — never the key itself. |
| `lastUpdate.commit` | Last-synced commit; powers `syncchanges`' zero-arg default. |
| `lastUpdate.at` | Timestamp of the last sync. |

!!! tip "Why it stays small"
    The **code** is the truth for what each API *is*, and **Postman** is the truth for
    what *exists*. So the tool re-reads the code when syncing and reads the live
    collection's basic structure to find matches — it never mirrors every request id
    locally. The config never goes stale against Postman and never bloats.

## Where the API key lives — never in the repo

The raw key is stored by **reference only**, in one of these (by preference):

1. **OS credential store** (Keychain / Secret Service / Credential Manager) — the
   default. Referenced as `keychain:postman-mcp`.
2. **Environment variable** `POSTMAN_API_KEY` — referenced as `env:POSTMAN_API_KEY`.
3. **Gitignored secret file** `.postman-mcp.secret` — fallback. `init` adds it to
   `.gitignore` automatically.

You choose which during `init`; keychain ships first. The secret resolver reads the value
at run time and the key is **never** written into `postman-mcp.json`.

## The setup contract

`postman-mcp doctor` validates all six conditions. The setup is correct when **all** hold:

1. `postman-mcp` CLI is on PATH (`postman-mcp version` works).
2. `postman-mcp.json` exists at the project root with a valid `collectionId`.
3. The API key resolves from its `apiKeyRef` and `GET /me` returns 200.
4. The MCP server is registered in Claude Code and `postman-mcp serve` boots clean.
5. The six slash-command files exist under `.claude/commands/postman/`.
6. The target collection exists in Postman (`GET /collections/{uid}` → 200).

Fail any one → `doctor` names it and gives the one command to fix it.

## Committing it

Commit `postman-mcp.json` so your team shares the same target config. It contains no
secrets — only a reference and a collection id. Make sure `.postman-mcp.secret` is in
your `.gitignore` (`init` does this for you).
