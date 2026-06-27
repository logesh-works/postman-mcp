# Postman MCP — Implementation Plan (Phase 0 Analysis)

> Source of truth: `postman-mcp-prd-v3.md` (v3.1). This document is the Phase 0
> deliverable required by the execution prompt: architecture summary, dependency map,
> package structure, config requirements, external integrations, and risk analysis.

## 1. Architecture summary (PRD §5)

A local stdio MCP server (`postman-mcp serve`) registered in Claude Code by
`postman-mcp init`. Seven components:

```
Claude Code  ──slash commands──▶  Postman MCP Server (local)
             ◀──diffs/prompts───
                                       │
   ┌──────────┬──────────┬────────────┼───────────┬────────────┐
   ▼          ▼          ▼            ▼           ▼            ▼
Command    Input      Engine     Postman      Git         Config +
router     resolver  (builder)   client      reader       Secret store
         (OpenAPI/                (REST)     (diff since
          code)                              commit)
```

- **Command router** — `server.py`: maps each slash command to one MCP tool → a
  service-layer call. No business logic here.
- **Input resolver** — `input/resolver.py`: decides OpenAPI vs code per route (§9),
  produces a normalized `RouteModel`.
- **Engine** — `engine/builder.py`: `RouteModel` → Postman Collection v2.1 item (§8).
- **Postman client** — `postman/client.py` + `merge.py`: REST + whole-collection
  read/merge/write (§6).
- **Git reader** — `git/reader.py`: "what changed since X" for `syncchanges` (§5).
- **Config store** — `config/store.py`: `postman-mcp.json` (§7).
- **Secret resolver** — `secrets/manager.py`: key by reference, never on disk (§6.2).

The hard problem is isolated in one place (the engine); the five sync commands are
"one engine + five selectors" (PRD §2).

## 2. Dependency map (PRD §B)

| Dependency | Used by | Purpose |
|---|---|---|
| `mcp` | `server.py` | stdio MCP server + tool registration |
| `httpx` | `postman/client.py` | Postman REST calls (`api.getpostman.com`) |
| `pydantic` v2 | `models.py`, `input/parsers/fastapi.py` | contracts + Pydantic introspection |
| `keyring` | `secrets/manager.py` | OS credential store (default key location) |
| `typer` | `cli.py` | `postman-mcp` CLI (init/doctor/serve/version) |
| `pyyaml` | `input/openapi.py` | parse OpenAPI YAML specs |
| `git` (subprocess) | `git/reader.py` | diff since commit (no gitpython dep) |
| `pytest`/`pytest-cov`/`respx` (dev) | `tests/` | tests + httpx mocking |

## 3. Package structure

See the package layout in the approved plan / PRD §B. Layers: `cli` · `server` ·
`service` · `engine` · `input` (`resolver`/`openapi`/`parsers`) · `postman` · `git` ·
`config` · `secrets` · `diff` · `commands`.

## 4. Config / data requirements (PRD §7)

`postman-mcp.json` at project root — small, committable, secret-free:

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
  "lastUpdate": { "commit": "a1b2c3d", "at": "2026-06-27T10:00:00Z" }
}
```

Secret never stored here — only `apiKeyRef`. Key lives in: OS keychain (default) /
`env:POSTMAN_API_KEY` / gitignored `.postman-mcp.secret` (§6.2). `init` adds the
secret file to `.gitignore`.

## 5. External integrations

1. **Postman REST API** (`https://api.getpostman.com`, `X-Api-Key`): `/me`,
   `/workspaces`, `/collections`, `/collections/{uid}` (GET/PUT), `POST /collections`,
   `/environments` (§6.4). Writes are whole-collection: read → merge → PUT.
2. **Claude Code**: MCP registration via project `.mcp.json` (+ `claude mcp add` if
   present); slash commands copied to `.claude/commands/postman/` (§C.2).
3. **OS credential store** via `keyring` (Keychain / Secret Service / Credential
   Manager) (§6.2).
4. **Local `git`** binary for diffs (§5).
5. **Optional live app endpoint** (`/openapi.json`, `/api-json`) for OpenAPI detection
   (§9.2).

## 6. Risk analysis

| Risk | Impact | Mitigation |
|---|---|---|
| MCP has no interactive y/n | can't prompt inside a tool | two-phase `confirm` contract: tool returns diff first, writes only on `confirm=True` (§13/§17 intent) |
| TS parsing (Express/NestJS) — no Python TS AST | weaker body inference | regex/heuristics per §9.4; flag "lower confidence" in diff |
| Business-logic test tier non-deterministic | bad assertions | gated/flagged; status+schema are the trusted tiers (§8.6/§14/§22) |
| Whole-collection PUT race (two devs) | last-write-wins | acceptable for MVP (§22); each write reads live collection first |
| Postman 5xx / rate limit | partial write | retry+backoff then clean abort, no partial write (§18) |
| Secret leakage | key in repo | stored by reference only; `.gitignore` updated; masked env vars (§16) |
| OpenAPI spec stale/unreachable | wrong/missing routes | per-route fallback to code parsing, noted in diff (§9.5/§18) |

## 7. Assumptions (documented per execution-prompt rule 4)

- The two-phase `confirm` mechanism is the chosen realization of "diff before every
  write" within MCP's stateless tool model.
- TS frameworks parsed heuristically (no native TS toolchain dependency).
- `keyring` is available; if its backend is missing, `init` offers env/file fallback.
- Single collection per project (PRD §4).
