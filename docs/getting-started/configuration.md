# Configuration

All configuration lives in one file at your project root, `postman-mcp.json`. It's
small, stable, and safe to commit. It holds config and a last-update marker, nothing
else, and never a secret.

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
    "apiKeyRef": "keychain:postman-mcp",
    "responseStyle": "single",
    "generateTests": false
  },
  "lastUpdate": {
    "commit": "a1b2c3d",
    "at": "2026-06-27T10:00:00Z"
  }
}
```

| Field | Meaning |
|---|---|
| `config.framework` | Detected framework: `fastapi`, `express`, `django`, `nestjs`, `flask`, or `spring`. |
| `config.inputMode` | `openapi` or `code`. Which source the [resolver](../architecture/resolver.md) uses. Re-checked for freshness on every sync. |
| `config.openApiSource` | File path or URL of the spec, when `inputMode` is `openapi`. |
| `config.workspace` | The Postman workspace id. |
| `config.collectionId` | The project's collection, the default target for every sync. |
| `config.defaultInto` | Default folder path inside the collection when `--into` is omitted. Defaults to `/`, the collection root; nothing infers a folder for you. |
| `config.apiKeyRef` | A reference to the API key, never the key itself. |
| `config.responseStyle` | How many responses get saved per request: `single` (default, just the one best response), `minimal` (that plus one generic error), or `full` (every declared 2xx plus a standard error set). |
| `config.generateTests` | Whether to attach a test script (status + schema assertions) to each synced request. `false` by default. |
| `config.confidencePolicy` | Gate thresholds (`autoThreshold`/`flagThreshold`/`approvalThreshold`, default `90`/`75`/`50`) — see below. |
| `config.allowLowConfidence` | Whether an endpoint below `approvalThreshold` can still be synced by naming it explicitly, instead of being blocked outright. `false` by default. |
| `config.writeProtection` | `normal` (default), `readonly` (every write is refused), or `approve-all` (nothing writes unless named explicitly, even endpoints that would otherwise auto-sync) — see below. |
| `config.planTtlHours` | How long a compiled plan stays valid before it must be recompiled. `24` by default. |
| `lastUpdate.commit` | Last-synced commit. This is what `syncchanges` diffs against when you don't pass `--last` or `--since`. |
| `lastUpdate.at` | Timestamp of the last sync. |

The last four fields are read only by the `get_contract`/`submit_model`/`plan`/`apply` tool
surface (a separate, non-slash-command way to sync described in
[`docs/architecture/handoff.md`](../architecture/handoff.md)) — the six sync commands above
don't consult them. An endpoint's gate score there determines what happens on `apply`:
`auto` (≥90) syncs normally, `flag` (75–89) syncs but is marked in the diff, and below
`approvalThreshold` it's excluded from the plan entirely unless named in
`apply(approve=[...])`.

!!! tip "Why it stays small"
    Code is the source of truth for what each API *is*. Postman is the source of truth
    for what *exists*. So the tool re-reads the code on every sync and reads just the
    live collection's basic structure to find matches; it never mirrors every request id
    locally. The config can't go stale against Postman, and it doesn't grow over time.

## Where the API key lives (never in the repo)

The raw key is stored by reference only, in one of these, in order of preference:

1. **OS credential store** (Keychain, Secret Service, or Credential Manager). The
   default. Referenced as `keychain:postman-mcp`.
2. **Environment variable** `POSTMAN_API_KEY`, referenced as `env:POSTMAN_API_KEY`.
3. **Gitignored secret file** `.postman-mcp.secret`, the fallback. `init` adds it to
   `.gitignore` automatically.

You choose which one during `init`; the keychain option is offered first. The secret
resolver reads the value at run time, and the key is never written into
`postman-mcp.json`.

## The setup contract

`postman-mcp doctor` checks six things. Setup is correct when all of them hold:

1. `postman-mcp` CLI is on PATH (`postman-mcp version` works).
2. `postman-mcp.json` exists at the project root with a valid `collectionId`.
3. The API key resolves from its `apiKeyRef` and `GET /me` returns 200.
4. The MCP server is registered in Claude Code and `postman-mcp serve` boots clean.
5. The slash-command files exist under `.claude/commands/postman/`.
6. The target collection exists in Postman (`GET /collections/{uid}` returns 200).

If any one fails, `doctor` names it and gives you the one command to fix it.

## Committing it

Commit `postman-mcp.json` so your team shares the same target config. It contains no
secrets, just a reference and a collection id. Make sure `.postman-mcp.secret` is in your
`.gitignore` (`init` does this for you).
