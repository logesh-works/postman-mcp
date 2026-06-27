# Changelog

All notable changes to this project are documented here.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Open-source repository foundation: `LICENSE`, `CONTRIBUTING`, `CODE_OF_CONDUCT`,
  `SECURITY`, `SUPPORTED_VERSIONS`, `ROADMAP`, GitHub issue/PR templates, CI and release
  workflows, MkDocs Material documentation site, and `examples/`.
- **Test suite** under `tests/` — 120 tests, 83% coverage, all Postman REST calls mocked
  with `respx`. Covers the engine, OpenAPI mapper, all four code parsers, merge
  idempotency/preservation, the diff renderer, the two-phase confirm contract end to end,
  the Postman client (auth/retry), setup install/registration, and the CLI `doctor`.

## [0.1.0] — Unreleased (MVP)

First MVP release.

### Added
- **Setup chain** — `postman-mcp init` (API-key handshake, workspace/collection pick,
  config write, MCP-server registration, slash-command install), `postman-mcp doctor`,
  `postman-mcp serve`, `postman-mcp version`.
- **The engine** — `RouteModel` → Postman Collection v2.1 item: method/URL, params,
  request body with realistic examples, auth headers, success + error responses, and a
  three-tier test scaffold (status + schema shipped; business-logic gated off).
- **Input resolution** — OpenAPI-first (one mapper for FastAPI / NestJS / DRF), with
  framework code-parsing fallback (FastAPI, Express, Django REST Framework, NestJS) and
  per-route mixing.
- **Commands** — `/postman:syncapi`, `/postman:syncchanges`, `/postman:sync`,
  `/postman:syncall`, `/postman:createenv`, `/postman:status`.
- **Safety** — diff before every write, human-owned scripts/examples preserved across
  syncs, soft deletes by default, secrets stored by reference only.

### Known gaps
- A live end-to-end run against a real Postman workspace is still pending (tests mock the
  REST API) — a release gate for `0.1.0`. See [ROADMAP.md](ROADMAP.md).
- TS parsers (Express/NestJS) are heuristic; Django router-registered viewsets are not
  yet fully resolved.

[Unreleased]: https://github.com/logesh-works/postman-mcp/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/logesh-works/postman-mcp/releases/tag/v0.1.0
