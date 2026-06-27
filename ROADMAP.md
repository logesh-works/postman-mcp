# Roadmap

Postman MCP ships in deliberate milestones. The MVP proves the kernel — *point at one
route, watch a complete Postman request materialize* — and each release widens coverage
from there.

> Dates are targets, not promises. The ordering is firm.

## 0.1.0 — MVP: the kernel works end to end

**Goal:** `pip install` → populated collection in under five minutes, no manual config
editing.

- [x] Setup spine — `init` / `doctor` / `serve` / `version`, MCP registration, slash-command install
- [x] The engine — `RouteModel` → Postman Collection v2.1 item
- [x] OpenAPI-first input resolution (FastAPI / NestJS / DRF via one mapper)
- [x] Code-parsing fallback (FastAPI, Express, Django REST Framework, NestJS)
- [x] All six commands (`syncapi`, `syncchanges`, `sync`, `syncall`, `createenv`, `status`)
- [x] Diff-before-write, preservation of human-owned fields, soft deletes
- [x] **Real test suite (>80% coverage)** — 120 tests · 83% coverage (`respx`-mocked)
- [ ] First validated end-to-end run against a live Postman workspace
- [ ] Published to PyPI

## 0.2.0 — Hardening and parser depth

**Goal:** trustworthy on real codebases, not just clean ones.

- [ ] Django `DefaultRouter` / nested `include()` viewset resolution
- [ ] Stronger Express/NestJS extraction (cross-file routers, decorator chains)
- [ ] `syncchanges` file→route mapping for pure-OpenAPI sources
- [ ] Business-logic test tier behind a quality gate (opt-in)
- [ ] Richer diff output (field-level `~` rendering parity across all commands)

## 0.3.0 — CI and the test loop

**Goal:** the collection stays in sync without a human in the loop.

- [ ] GitHub Actions / GitLab CI hook (sync on push, fail on drift)
- [ ] Newman test-runner integration (run the generated tests in CI)
- [ ] `--check` mode for `status` suitable for CI gating

## 1.0.0 — Stable, documented, supported

**Goal:** a tool teams adopt and depend on.

- [ ] Semantic-versioning guarantees and a documented deprecation policy
- [ ] Complete documentation site with per-framework guides and screenshots
- [ ] Validated success metrics: ≥80% of synced requests need zero manual edits
- [ ] Stable plugin/parser interface for community-contributed frameworks

## Beyond 1.0

- [ ] Mock server generated from schema
- [ ] Pre-commit OWASP security checks
- [ ] Auto-published living docs

## Explicitly out of scope (MVP)

Environment switching · rollback/snapshot system · GraphQL sync · gRPC/Protobuf ·
Postman Flows · real-time collaborative editing · production-traffic drift detection.

---

Want to influence the roadmap? Open a
[feature request](https://github.com/logesh-works/postman-mcp/issues/new?template=feature_request.yml)
or join the discussion on an existing one.
