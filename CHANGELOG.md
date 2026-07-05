# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/logesh-works/postman-mcp/compare/v2.0.0...HEAD
[2.0.0]: https://github.com/logesh-works/postman-mcp/compare/v1.1.0...v2.0.0
[1.1.0]: https://github.com/logesh-works/postman-mcp/compare/v1.0.0...v1.1.0
[1.0.0]: https://github.com/logesh-works/postman-mcp/releases/tag/v1.0.0
[0.1.0]: https://github.com/logesh-works/postman-mcp/releases/tag/v0.1.0
