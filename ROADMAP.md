# Roadmap

Postman MCP ships in deliberate milestones. `0.1.0` proved the kernel works end to end,
tagged and published, with a live run against a real Postman workspace. **`1.0.0` adds
the Claude-guided `--prompt` layer** on top of that proven kernel. Each release after that
widens coverage.

> Dates are targets, not promises. The ordering is firm.

## 0.1.0: MVP, the kernel works end to end (released 2026-06-27)

**Goal:** `pip install` to a populated collection in under five minutes, no manual
config editing.

- [x] Setup spine: `init` / `doctor` / `serve` / `version`, MCP registration,
      slash-command install
- [x] The engine: `RouteModel` to Postman Collection v2.1 item — fully deterministic,
      no LLM
- [x] OpenAPI-first input resolution (FastAPI / NestJS / DRF via one mapper)
- [x] Code-parsing fallback (FastAPI, Express, Django REST Framework, NestJS)
- [x] All six commands (`syncapi`, `syncchanges`, `sync`, `syncall`, `createenv`, `status`)
- [x] Diff-before-write, preservation of human-owned fields, soft deletes
- [x] **Real test suite**: 141 tests, 85% coverage (`respx`-mocked, no live API calls)
- [x] Validated end-to-end run against a live Postman workspace
- [x] Published to PyPI

## 1.0.0: the Claude-guided prompt layer (current)

**Goal:** let developers steer a sync in plain English without touching the deterministic
engine.

- [x] `--prompt` on the four sync commands (`syncapi`, `sync`, `syncchanges`, `syncall`) —
      Claude-consumed generation guidance, never forwarded to or interpreted by the MCP
      server
- [x] `examples/prompts/` — ready-made guidance (fintech, healthcare, enterprise,
      ecommerce)
- [x] Documented intelligence/execution layer separation as a core design principle

## 1.1.0: hardening and parser depth

**Goal:** trustworthy on real codebases, not just clean ones.

- [ ] Django `DefaultRouter` / nested `include()` viewset resolution
- [ ] Stronger Express/NestJS extraction across files (cross-file routers spread over
      multiple modules, decorator chains)
- [ ] `syncchanges` file-to-route mapping for pure-OpenAPI sources (currently falls back
      to syncing everything when there's no code ref to match against)
- [ ] Business-logic test tier behind a quality gate (opt-in)
- [ ] Richer diff output (field-level `~` rendering, consistent across all commands)

## 1.2.0: CI and the test loop

**Goal:** the collection stays in sync without a human in the loop.

- [ ] GitHub Actions / GitLab CI hook (sync on push, fail on drift)
- [ ] Newman test-runner integration (run the generated tests in CI)
- [ ] `--check` mode for `status` suitable for CI gating

## 1.3.0: proven at scale

**Goal:** a tool teams adopt and depend on, backed by evidence rather than design intent.

- [ ] Documented deprecation policy on top of the existing SemVer guarantee
- [ ] Complete documentation site with per-framework guides and screenshots
- [ ] Validated success metric: at least 80% of synced requests need zero manual edits
- [ ] Stable plugin/parser interface for community-contributed frameworks

## Skills

`--prompt` is **Phase 1** of a skill architecture. It already lets you hand Claude
free-form guidance for a sync (`--prompt "Act as a Stripe API architect"`). The next phase
packages that guidance into reusable, named skills:

```bash
/postman:syncapi createPayment --skill fintech
/postman:syncall --skill healthcare
/postman:sync -orders/ --skill ecommerce
```

A `--skill` is a curated bundle of prompt guidance (persona, terminology, example style,
documentation conventions) that Claude loads before calling the MCP tool. The layer
boundary is unchanged: **skills are consumed by Claude, never by the MCP server.** The
engine stays deterministic and LLM-agnostic. See
[`examples/prompts/`](examples/prompts/) for the seed guidance these skills will grow from.

## Beyond 1.3

- [ ] Mock server generated from schema
- [ ] Pre-commit OWASP security checks
- [ ] Auto-published living docs

## Explicitly out of scope

Environment switching, a rollback/snapshot system, GraphQL sync, gRPC/Protobuf, Postman
Flows, real-time collaborative editing, and production-traffic drift detection.

---

Want to influence the roadmap? Open a
[feature request](https://github.com/logesh-works/postman-mcp/issues/new?template=feature_request.yml)
or join the discussion on an existing one.
