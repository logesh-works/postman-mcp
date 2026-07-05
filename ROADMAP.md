# Release history and known gaps

This tracks what's shipped and what's known to be missing — it isn't a commitment to
future architecture. `0.1.0` proved the kernel works end to end. `1.0.0` added the
Claude-guided `--prompt` layer on top of it. `1.1.0` hardened the extraction pipeline
against real production-shaped output. `2.0.0`, the current release, adds a second
pipeline built around a submitted, verified API model instead of only a parser
extracting one. The "Known gaps" section at the end lists what's still missing today;
it deliberately doesn't promise version numbers or dates for closing them.

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

## 1.0.0: the Claude-guided prompt layer

**Goal:** let developers steer a sync in plain English without touching the deterministic
engine.

- [x] `--prompt` on the four sync commands (`syncapi`, `sync`, `syncchanges`, `syncall`) —
      Claude-consumed generation guidance, never forwarded to or interpreted by the MCP
      server
- [x] `examples/prompts/` — ready-made guidance (fintech, healthcare, enterprise,
      ecommerce)
- [x] Documented intelligence/execution layer separation as a core design principle

## 1.1.0: foundation hardening

**Goal:** fix the extraction pipeline defects an audit of real production-shaped output
actually found.

- [x] Express schema resolution is project-wide on full scans and recognizes a named
      schema handed to validation middleware (`validate(employerSchema)`), not just
      `schema.validate()` in the same file — fixes the empty `{}` body bug
- [x] `init`'s workspace/collection picker defaults to what's already configured on a
      re-run, instead of silently drifting to whatever Postman lists first
- [x] OpenAPI-first is enforced, not just suggested: a committed spec is honored in any
      `inputMode`, and live spec-endpoint probing now covers Express and Django
      (`api-docs.json`, `swagger.json`, etc.)
- [x] Deterministic `--into` placement (explicit → configured → root, nothing inferred)
      and an explicit completion summary after every successful write

## 2.0.0: the submitted-model pipeline (current)

**Goal:** close the remaining code-parsing gaps, and add a second way to produce a
syncable API model — one submitted directly instead of extracted by a parser.

- [x] Django `DefaultRouter` / `SimpleRouter` viewset resolution, including the full
      `ModelViewSet` CRUD action set
- [x] Cross-file router-prefix resolution — a real import/mount graph
      (`input/structural.py`), not a leaf-only regex, for FastAPI, Flask, and Express.
      A mount it genuinely can't trace (dynamic import, computed prefix) is reported
      unresolved rather than guessed at.
- [x] Flask and Spring (Boot) parsers, at the same accuracy bar as the original four —
      six frameworks supported in total
- [x] A second synchronization pipeline: a caller submits a structured API model
      instead of a parser extracting one, and every claimed fact is checked against
      the actual source before anything can sync. The original parsers didn't go
      away — they now run as the independent check a submitted model is verified
      against, and as the fallback producer when no model is submitted at all. Ships
      as MCP tools (`get_contract`, `submit_model`, `verify_model`, `plan`, `apply`,
      `snapshot`, `rollback`, `audit`).

Current limitations of this release are listed under "Known gaps" below, and in full
detail in [`docs/architecture/handoff.md`](docs/architecture/handoff.md).

## Known gaps

Things that don't exist yet, in no particular order and with no version number
attached:

- `syncchanges` file-to-route mapping for pure-OpenAPI sources (currently falls back
  to syncing everything when there's no code ref to match against).
- A business-logic test-script tier behind a quality gate (the status and schema
  tiers ship; a third, inferred tier exists in code but isn't wired up).
- Richer diff output (field-level `~` rendering, consistent across all commands).
- A slash-command wrapper for the submitted-model pipeline — it's callable only as
  direct MCP tool calls today.
- CI integration: no GitHub Actions/GitLab CI hook, no Newman test-runner
  integration, no `--check` mode for `status`.
- A documented deprecation policy, a stable parser interface for
  community-contributed frameworks, and a validated success metric for how often a
  synced request needs zero manual edits.
- `--skill`: named, reusable bundles of the guidance `--prompt` already lets you pass
  free-form (`--prompt "Act as a Stripe API architect"`). Same layer boundary as
  `--prompt` — consumed by Claude, never by the MCP server.
- A generated mock server, pre-commit OWASP checks, and an auto-published docs site
  built from the live collection.

## Explicitly out of scope

Environment switching, GraphQL sync, gRPC/Protobuf, Postman Flows, real-time
collaborative editing, and production-traffic drift detection. (Snapshot/rollback
exists for the submitted-model pipeline above, since it can sync LLM-sourced content
the diff alone doesn't fully vouch for — the original six commands have no rollback
by design; re-sync is the recovery path there, and stays that way.)

---

Found something missing that you need? Open a
[feature request](https://github.com/logesh-works/postman-mcp/issues/new?template=feature_request.yml)
or join the discussion on an existing one.
