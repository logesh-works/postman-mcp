# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/logesh-works/postman-mcp/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/logesh-works/postman-mcp/compare/v0.1.0...v1.0.0
[0.1.0]: https://github.com/logesh-works/postman-mcp/releases/tag/v0.1.0
