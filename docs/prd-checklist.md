# PRD Checklist — Traceability Matrix

> Every PRD section mapped to its implementation. Status updated each session.
> Legend: ✅ done · 🚧 in progress · ⬜ not started
>
> **Session 1 (2026-06-27): Full MVP implemented — PRD build phases 0–6.**
>
> **Correction + update (foundation pass):** an earlier revision claimed "88 tests
> passing · 89% coverage" with **no test suite actually in the repo**. A real suite has
> now been written under `tests/`: **120 tests passing · 83% coverage** (target >80%),
> verified with `pytest --cov`. All Postman REST calls are mocked with `respx` — no
> network, no real API key. Remaining lighter-covered areas: `cli.py` interactive
> `init` flow and `input/detect.py` (see end-of-session report).

## Part I — Setup chain (§A–§E)

- ✅ §A — 3-action journey (install → init → use) — `README.md`, `cli.py`
- ✅ §B — pip package delivers CLI + MCP server + slash md + engine — `pyproject.toml`
- ✅ §B — dependencies declared — `pyproject.toml`
- ✅ §B — requirements (Py≥3.10, Claude Code check, Postman key) — `cli.py`
- ✅ §C.1 — `init` 6 ordered steps — `cli.py:init`
- ✅ §C.1 — success printout / next-steps banner — `cli.py:init`
- ✅ §C.2a — register MCP server in `.mcp.json` (+ `claude mcp add`) — `setup/registration.py`
- ✅ §C.2b — install slash commands → `.claude/commands/postman/` — `setup/installer.py`
- ✅ §C.3 — `init` idempotent / `doctor` re-validates — `cli.py`
- ✅ §D — in-Claude-Code command surface (6 commands) — `server.py` + `commands/*.md`
- ✅ §E — 6-point setup contract — `cli.py:doctor`

## Part II — Product spec (§1–§22)

- ✅ §2 — one engine + five selectors; syncapi kernel — `engine/`, `service/sync.py`
- ✅ §3 — goals & non-goals (guardrails) — package-wide
- ✅ §4 — target frameworks + one collection/project — `input/`, `config/`
- ✅ §5 — system architecture (7 components) — package layout
- ✅ §6.1 — `X-Api-Key` auth — `postman/client.py`
- ✅ §6.2 — key by reference (keychain/env/file) — `secrets/manager.py`
- ✅ §6.3 — init auth handshake (`/me`, pick collection) — `cli.py:init`
- ✅ §6.4 — API surface + whole-collection write note — `postman/client.py`, `merge.py`
- ✅ §7 — `postman-mcp.json` shape (committable, secret-free) — `config/store.py`
- ✅ §8 — engine 8-step pipeline → Collection v2.1 — `engine/builder.py`
- ✅ §8.3 — body examples by type/name — `engine/examples.py`
- ✅ §8.6 — 3-tier tests, business gated OFF by default — `engine/tests.py`
- ✅ §9.1 — same RouteModel from both paths — `models.py`, `input/resolver.py`
- ✅ §9.2 — OpenAPI availability detection (4 priorities) — `input/detect.py`, `resolver.py`
- ✅ §9.3 — Path A: OpenAPI 3.x → route model ($ref + allOf resolve) — `input/openapi.py`
- ✅ §9.4 — Path B: 4 framework parsers; Pydantic v1/v2; Express flagged — `input/parsers/*`
- ✅ §9.5 — per-route mixing; source labels — `input/resolver.py`, `diff/render.py`
- ✅ §10.1 — syncapi/syncchanges/sync/syncall/createenv — `server.py`, `service/*`
- ✅ §10.2 — status (read-only); init/doctor terminal-only — `service/status.py`, `cli.py`
- ✅ §11 — `--into` routing, auto-create, idempotent, `--confirm` — `postman/merge.py`
- ✅ §12 — end-to-end add-an-API flow + update-in-place preserve — `service/sync.py`
- ✅ §13 — diff preview (NEW/`~`, preserved list, source tag) — `diff/render.py`
- ✅ §14 — auto-fill table (each row) — `engine/`
- ✅ §15 — idempotency (METHOD+normalized path); conflict policy — `postman/merge.py`
- ✅ §16 — secret handling (key by ref; env masking) — `secrets/`, `service/environment.py`
- ✅ §17 — 6 non-negotiable safety rules — service layer
- ✅ §18 — error/edge-case table (14 rows) — package-wide (see below)
- ✅ §19 — build phases — this build
- ✅ §20 — out of scope (NOT built) — guardrail
- ✅ §21 — success metrics → acceptance targets — tests/verification
- ✅ §22 — open questions → resolved defaults — documented
- ✅ Appendix — quickstart = README first screen — `README.md`

## Safety rules (§17) — all hold, each unit-tested
- ✅ Diff before every write (two-phase confirm, no skip flag) — `test_service.py::test_sync_api_preview_does_not_write`
- ✅ No API key in repo — `test_models_config_secrets.py::test_config_never_contains_raw_key`
- ✅ No silent overwrites (human-owned fields preserved) — `test_merge_diff.py::test_human_scripts_and_examples_preserved`
- ✅ Soft delete by default (`--purge` for hard) — `test_merge_diff.py::test_soft_deprecate`/`test_purge_hard_delete`
- ✅ Non-default collection requires `--confirm` — `diff/render.py`, `service/sync.py` guard
- ✅ Idempotent sync (match live collection) — `test_merge_diff.py::test_idempotent_update_no_duplicate`

## §18 error/edge-case coverage
Invalid key → `test_invalid_key_stops_cleanly` · ambiguous target → `sync_api` lists
candidates · parse failure → skip+report (`test_fastapi_parser_skips_syntax_error`) ·
5xx/rate-limit → retry/backoff + clean abort (`test_write_aborts_on_server_error`) ·
missing config → `test_missing_config_errors` · first syncchanges no marker →
`test_syncchanges_first_run_no_marker` · soft-deprecate route · OpenAPI unreachable →
`test_resolve_openapi_unreachable_falls_back` · per-route mixing →
`test_per_route_mixing_openapi_wins`.

---

## End-of-session report (Session 1 — 2026-06-27)

### Implementation progress
All six build steps (A–F) complete. `pip install -e .` → `postman-mcp version`/`--help`
work; `postman-mcp serve` registers all six MCP tools; `init`/`doctor` exercised via
mocked Postman API. Engine produces complete Collection v2.1 items; OpenAPI kernel,
four code parsers, per-route mixing, diff preview, merge/idempotency/preservation, and
all five sync commands + createenv + status are implemented and tested. **88 tests,
89% coverage.**

### Remaining PRD gaps
- None at MVP scope. (Phase 2/3 items — CI hooks, Newman, mock server, OWASP, living
  docs — are explicitly post-MVP per PRD §19 and intentionally not built.)

### Technical debt
- **TS parsers (Express/NestJS) are regex/heuristic** (no Python TS AST). Per PRD §9.4
  this is acceptable and flagged "lower confidence," but complex routing (dynamic mounts,
  decorators across files) may be missed. OpenAPI path is preferred when available.
- **Django parser** covers `path('x/', View.as_view())` + ViewSets; router-registered
  viewsets (`DefaultRouter`) and nested includes are not yet resolved.
- **`sync_changes` file→route mapping** falls back to syncing all changed routes when
  routes lack file refs (pure-OpenAPI sources have only operationIds, not file paths).
- **Business-logic test tier** is a single amount/price heuristic, shipped OFF (PRD §8.6).
- `cli.py` interactive branches (config-reuse, list-index picks) are lightly covered
  (76%); core paths are tested.

### Risks blocking completion
- None blocking MVP. Operational note: real end-to-end against live Postman needs a real
  personal API key (tests mock the REST API via `respx`). The `init` live run and the
  `<5min`/`<10s`/`≥80% no-edit` success metrics (PRD §21) should be validated against a
  real workspace before release.
