# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).


## [3.0.0] - 2026-07-21

Every slash command now has Claude read your code directly — any framework, any
language it understands — and author the Postman request itself, instead of routing
through a framework-specific parser. The MCP server's job shifts accordingly: it no
longer needs to parse your source to do its work; it validates what Claude wrote,
re-reads the exact lines Claude cited to catch hallucinations, checks every claimed
field against your real DTO/model classes, diffs against live Postman, and writes only
on confirm. This is what makes the tool work on a framework with no dedicated parser,
while catching a wrong route or a made-up field before it reaches Postman.

The original parser-based pipeline isn't gone — it's retained as the deterministic,
LLM-free tool surface for direct MCP callers, and as an independent verification source
elsewhere in the codebase. See "Deprecated" and "Migration notes" below.

### Added
- **A deterministic repository index and context retrieval**, exposed as `index()` and
  `context()`. Claude uses these to find and read exactly the code an endpoint needs —
  the handler, its DTO/type closure, the functions it calls, its router mount chain —
  instead of reading the project unbounded. Cost scales with the endpoint, not the size
  of the repository.
- **Citation verification and field-level grounding.** Every fact Claude claims — a
  route's existence, its body shape, its auth — carries a `file:line` citation the MCP
  server re-reads and re-hashes against your actual source; every claimed
  request/response field is checked against the real DTO/model class. Results surface
  per endpoint in the diff as `✓ verified`, `~ stale`, or `⚠ CITATION DOES NOT MATCH
  CODE`. An endpoint that fails verification is excluded from the write unless approved
  explicitly.
- **New MCP tools**: `get_sync_contract` (publishes the schema and authoring playbook
  every slash command follows) and `sync_files`/`sync_env`, the validate → verify →
  diff → write tools every slash command now calls.
- **New configuration fields**: `config.syncDir` (default `postman/sync`),
  `config.environmentId` (tracks a managed Postman environment across renames), and
  `config.engine` — an advanced setting for which deterministic source backs the
  lower-level tool surface's fallback path; most users never need to touch it. See
  [Configuration](docs/getting-started/configuration.md).

### Changed
- **Everything this tool creates now lives under one top-level `postman/` folder** —
  config, secret reference, sync artifacts, and internal cache/state — instead of being
  spread across `postman-mcp.json`, `.postman-mcp.secret`, and a hidden `.postman-mcp/`
  directory. Existing projects migrate automatically on the first config read after
  upgrading; no manual step is required. See "Migration notes" below.
- **`/postman:createenv` no longer creates a duplicate environment on every re-run.** It
  now finds the existing managed environment (by a tracked id, falling back to an exact
  name match) and updates it in place.
- **The original six-command, parser-based tool surface is now clearly labeled
  `[Legacy]`** in its MCP tool docstrings — it remains fully functional for direct MCP
  callers that want deterministic, LLM-free parsing with no citations, but no slash
  command has ever called it.

### Improved
- **The diff now correctly reports "unchanged."** Previously, re-running a sync on an
  already-synced, unmodified route could report it as modified indefinitely. A true
  no-op now reports `UNCHANGED`, and the summary line shows an `N unchanged` count.
- **Array-typed OpenAPI responses keep their real DTO name** (e.g. `UserDto[]`) instead
  of falling back to a generic label.
- **`postman-mcp init`'s API-key prompt no longer hangs** in non-interactive contexts
  (CI, piped input) — it now detects the session and fails fast with a clear message,
  or reads `POSTMAN_API_KEY` from the environment if set.
- **The installed version can no longer drift from `pyproject.toml`.** `__version__` is
  now read from package metadata instead of a second hardcoded literal.

### Fixed
- **The `cite` tool's path-confinement check was platform-dependent.** A Windows
  drive-letter path (`C:/...`) is not "absolute" under POSIX `pathlib`, so on
  Linux/macOS it could slip past the confinement check instead of being rejected as
  outside the project root. The check is now explicit and behaves identically on every
  host OS.

### Deprecated
- **The original six-command tool surface** (`syncapi`/`sync`/`syncall`/`syncchanges`/
  `status`/`createenv` called as direct MCP tools, bypassing a slash command) is
  deprecated in favor of the Claude-driven flow above. It is not removed, has no
  planned removal date, and remains fully supported for MCP clients that specifically
  want deterministic, LLM-free parsing.

### Removed
- Nothing. The framework parsers (`input/parsers/`) were evaluated for removal and
  kept: a measured comparison showed the index-based alternative doesn't yet match
  parser accuracy on route identity, with no schema/auth extraction at all. They
  continue to back the legacy tool surface and independent verification.

### Known limitations
- Express and NestJS code parsing (used by the legacy tool surface) is regex/heuristic,
  not a full AST — best-effort, and flagged lower-confidence in the diff when it falls
  back to inferring from usage.
- A route removed from your code isn't yet auto-deprecated in the collection when
  synced through a slash command — clean up a stale request by hand for now.
- Confidence thresholds in the lower-level verify/plan/apply pipeline are engineering
  defaults, not yet validated against real-world outcomes.

See [ROADMAP.md](ROADMAP.md) for the full, current list of known gaps and what's next.

### Migration notes

**No action is required to upgrade.** There are no breaking changes to the seven
`/postman:*` slash commands, their flags, or `postman/config.json`'s existing fields.

- If your project was set up under an older release, the first time you use the tool
  after upgrading, it moves `postman-mcp.json`, `.postman-mcp.secret`, and the hidden
  `.postman-mcp/` cache directory into the new `postman/` layout automatically. Nothing
  to run by hand.
- If you call `syncapi`/`sync`/`syncall`/`syncchanges`/`status`/`createenv` directly as
  MCP tools (not through a `/postman:*` slash command), they're unchanged and continue
  to work exactly as before — now explicitly marked `[Legacy]` in their descriptions.
- New config fields (`syncDir`, `environmentId`, `engine`) are added with safe defaults
  the first time they're needed; you don't need to add them yourself.

## [2.0.0] - 2026-07-05

`1.1.0` shipped the code-parsing pipeline everything before it was built on. `2.0.0`
adds a second, separate pipeline alongside it: instead of a parser extracting routes
from code, a caller submits a structured API model directly, and the server verifies
every claimed fact against the actual source before anything is allowed to sync. The
original parsers didn't go away — they now double as the independent check a
submitted model is verified against, and as the fallback producer when no model is
submitted at all. The original six commands are unchanged and don't route through
this; it's reachable only as direct MCP tool calls for now (see "Known limitations"
below).

### Added
- **A second synchronization pipeline** built around a submitted, verified API
  model: schema validation, an evidence-hashing check that re-reads and re-verifies
  every citation against the working tree, cross-checks against the parsers, a
  confidence score computed from that agreement, and a plan/apply step that only
  writes what was previewed. Ships as MCP tools (`get_contract`, `submit_model`,
  `verify_model`, `plan`, `apply`, `snapshot`, `rollback`, `audit`).
- **Cross-file router-prefix resolution.** A real import/mount graph
  (`input/structural.py`) composes full route paths across files
  (`APIRouter(prefix=...)` + `include_router(...)`, `Blueprint` + `register_blueprint`,
  `app.use(prefix, router)`), for FastAPI, Flask, and Express. A mount that genuinely
  can't be traced (dynamic import, computed prefix) is reported unresolved rather than
  guessed at. Closes the gap noted in 1.1.0's "Known gaps" below.
- **Django `DefaultRouter`/`SimpleRouter` resolution.** Router-registered viewsets now
  expand into the full `ModelViewSet` CRUD action set, not just explicit `path()` calls.
  Closes the other item noted in 1.1.0's "Known gaps" below.
- **Flask and Spring (Boot) parsers**, at the same accuracy bar as the original four
  frameworks — six frameworks supported in total.

### Known limitations
- The submitted-model pipeline has no slash-command wrapper — it's called directly as
  MCP tools, not through `/postman:*`.
- It hasn't been exercised against a live LLM doing real repository discovery; every
  test constructs the submitted model by hand or via the parser fallback.
- Confidence thresholds (90/75/50) are engineering defaults, not numbers validated
  against real outcomes yet.
- No multi-service/monorepo support and no handling for infrastructure-dependent URL
  prefixes. Full detail in [`docs/architecture/handoff.md`](docs/architecture/handoff.md).

## [1.1.0] - 2026-06-29

Foundation hardening: fixes to the extraction pipeline found by auditing real
production-shaped Express output (an empty `{}` request body, a setup that silently drifted
to the wrong collection). No breaking changes — `RouteModel`, the engine, and the merge
contract are unchanged.

### Fixed
- **Express parser produced an empty body (`{}`) for the dominant real-world validation
  pattern** — a schema imported from another file and handed to validation middleware
  (`router.post('/x', validate(employerSchema), handler)`). Schema resolution is now
  project-wide on full scans and recognizes a named schema referenced anywhere near the
  route, not just `schema.validate(...)` in the same file.
- **`postman-mcp init` didn't stick to the already-configured workspace/collection on a
  re-run.** The picker ignored the existing config and defaulted to whatever Postman
  listed first, which could silently create or select a different collection (the root
  cause of duplicate "API Collection" entries on repeated `init` runs). It now defaults to
  the workspace/collection already in `postman-mcp.json`.
- **OpenAPI was skipped even when a spec existed.** `detect_openapi_source` only knew live
  spec endpoints for FastAPI/NestJS, so an Express (or Django) app serving a spec (e.g.
  `/api-docs.json`) was invisible to detection and `init` fell back to code parsing. Live
  endpoint probing now covers Express and Django, `api-docs.json` is recognized as a
  committed filename, and the resolver honors a committed spec file in *any* `inputMode` —
  "if OpenAPI exists, use OpenAPI" is now enforced, not just suggested.
- **A successful sync had no clear end state.** Writes now return an explicit completion
  summary (`✓ N API(s) added`, `✓ Collection updated`, `✓ lastUpdate recorded`,
  `✓ Sync completed`) instead of a single terse line.

### Changed
- **Collection placement is fully deterministic.** `--into` → configured `defaultInto` →
  collection root, in that order — nothing is ever inferred from a route/file/module name.
  Removed the dormant non-default-collection write guard (`is_default_collection`) that
  had no effect in practice.

### Known gaps
- Cross-file **router-prefix** resolution (`app.use('/api', router)` in one file, routes
  registered in another) is still unsolved — this release fixed *body* resolution, not
  *path* resolution. Doing this correctly needs a module-import graph, not regex.
- Django `DefaultRouter`-registered viewsets, `syncchanges` file-to-route mapping for
  pure-OpenAPI sources, and the opt-in business-logic test tier are unchanged — carried
  forward. See [ROADMAP.md](ROADMAP.md).

## [1.0.0] - 2026-06-28

Builds on `0.1.0` with a new Claude-side guidance layer. No changes to the engine,
resolver, merge logic, or any of the six commands' core behavior.

### Added
- **`--prompt`** on the four sync commands (`syncapi`, `sync`, `syncchanges`, `syncall`):
  free-form generation guidance consumed entirely by Claude Code before it calls the MCP
  tool. The MCP server has no `prompt` parameter and stays fully deterministic — see the
  [Prompt & skill layer](docs/architecture/overview.md#prompt-skill-layer).
- `examples/prompts/`: ready-made `--prompt` guidance (fintech, healthcare, enterprise,
  ecommerce) showing the Claude/MCP responsibility split in practice.
- Documentation: the intelligence/execution layer-separation principle, updated
  architecture and command-reference diagrams, and a `--prompt` section on every sync
  command's docs page.

## [0.1.0] - 2026-06-27

First MVP release. Tagged, published to PyPI, and validated with a live `init` →
`syncall` run against a real Postman workspace.

### Added
- **Setup chain**: `postman-mcp init` (API-key handshake, workspace/collection pick,
  config write, MCP-server registration, slash-command install), `postman-mcp doctor`,
  `postman-mcp serve`, `postman-mcp version`.
- **The engine**: `RouteModel` to Postman Collection v2.1 item, covering method and URL,
  params, request body with realistic examples, auth headers, success and error
  responses, and a three-tier test scaffold (status and schema shipped; business-logic
  gated off). Fully deterministic — no LLM in the engine.
- **Input resolution**: OpenAPI-first (one mapper for FastAPI, NestJS, and DRF), with
  framework code-parsing fallback (FastAPI, Express, Django REST Framework, NestJS) and
  per-route mixing.
- **Commands**: `/postman:syncapi`, `/postman:syncchanges`, `/postman:sync`,
  `/postman:syncall`, `/postman:createenv`, `/postman:status`.
- **Safety**: diff before every write, human-owned scripts and examples preserved
  across syncs, soft deletes by default, secrets stored by reference only.
- Open-source repository foundation: `LICENSE`, `CONTRIBUTING`, `CODE_OF_CONDUCT`,
  `SECURITY`, `SUPPORTED_VERSIONS`, `ROADMAP`, GitHub issue/PR templates, CI and release
  workflows, MkDocs Material documentation site, and `examples/`.
- **Test suite** under `tests/`: 141 tests, 85% coverage, all Postman REST calls mocked
  with `respx`. Covers the engine, OpenAPI mapper, all four code parsers, merge
  idempotency and preservation, the diff renderer, the two-phase confirm contract end to
  end, the Postman client (auth and retry), setup install and registration, and the CLI
  `doctor`.
- Markdown-table diff preview (`Status | Method | Route | Target | Auth | Body |
  Response | Source`) replacing the old free-text preview blocks.
- A `single` response style (one best response, no speculative errors), now the default.
- Express body extraction now reads Joi/Zod/Yup schema validation and JSDoc `@body`
  tags before falling back to inferring fields from `req.body` usage.
- FastAPI `Header(...)` parameters, NestJS `@Headers()` parameters, and Django
  `@api_view` function-based views are now detected by their respective code parsers.
- NestJS DTO parsing now handles nested-brace decorator arguments (`@ApiProperty({...})`)
  without truncating the class.
- Django's code parser now reads `.as_view({'get': 'list', ...})` method mappings
  instead of assuming every HTTP method a viewset class supports.
- Route-collision detection: two code-sourced routes registering the same method and
  path now produce a warning instead of one silently overwriting the other.
- `syncchanges` now parses only the changed files instead of the whole project.

### Fixed
- Express parser no longer shares one merged body-field list across every route in a
  file; fields are now scoped to each route's own handler.

### Known gaps
- TS parsers (Express, NestJS) are heuristic; Django router-registered viewsets aren't
  resolved yet. See [ROADMAP.md](ROADMAP.md).

[Unreleased]: https://github.com/logesh-works/postman-mcp/compare/v3.0.0...HEAD
[3.0.0]: https://github.com/logesh-works/postman-mcp/compare/v2.0.0...v3.0.0
[2.0.0]: https://github.com/logesh-works/postman-mcp/compare/v1.1.0...v2.0.0
[1.1.0]: https://github.com/logesh-works/postman-mcp/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/logesh-works/postman-mcp/releases/tag/v1.0.0
[0.1.0]: https://github.com/logesh-works/postman-mcp/releases/tag/v0.1.0
