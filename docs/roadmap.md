# Release history and known gaps

The canonical version of this lives in
[`ROADMAP.md`](https://github.com/logesh-works/postman-mcp/blob/main/ROADMAP.md) at the
repo root. This tracks what's shipped and what's known to be missing — not a commitment
to future architecture.

## 0.1.0: the kernel works end to end

Setup commands, the deterministic engine, OpenAPI-first resolution, code-parsing fallback
for four frameworks, all six commands, diff-before-write, and preservation of
human-owned fields. Tagged, published to PyPI, and validated with a live run against a
real Postman workspace.

## 1.0.0: the Claude-guided prompt layer

Adds `--prompt` on the four sync commands — generation guidance consumed entirely by
Claude Code, never forwarded to the deterministic MCP server — plus `examples/prompts/`
and the documented intelligence/execution layer-separation principle. No changes to the
engine, resolver, or merge logic.

## 1.1.0: foundation hardening

Fixes an audit of real production-shaped output actually found: Express schema
resolution now works across files and through validation middleware (closing an empty
`{}` body bug), `init`'s collection picker sticks to what's already configured instead of
drifting, OpenAPI-first is enforced for a committed spec in any input mode, and
collection placement is fully deterministic.

## 2.0.0: the submitted-model pipeline (current)

Closes the two gaps left open by 1.1.0 — Django `DefaultRouter` resolution and
cross-file router-prefix resolution (a real import/mount graph, not a leaf-only regex)
— and adds Flask and Spring (Boot) parsers, bringing framework support to six. Alongside
that, a second synchronization pipeline: a caller submits a structured API model instead
of a parser extracting one, and every claimed fact is checked against the actual source
before anything can sync. The original parsers didn't go away — they now double as the
independent check a submitted model is verified against, and as the fallback producer
when no model is submitted. Ships as MCP tools (`get_contract`, `submit_model`,
`verify_model`, `plan`, `apply`, `snapshot`, `rollback`, `audit`), reachable only as
direct tool calls today — no slash-command wrapper yet.

## Known gaps

No CI integration (no GitHub Actions/GitLab CI hook, no Newman test-runner, no
`--check` mode for `status`), no business-logic test tier, no slash command for the
submitted-model pipeline, and no named `--skill` bundles yet — `--prompt` already lets
you pass the same kind of guidance free-form. Full list, with no version numbers
attached, in [`ROADMAP.md`](https://github.com/logesh-works/postman-mcp/blob/main/ROADMAP.md).

## Explicitly out of scope

Environment switching, GraphQL sync, gRPC/Protobuf, Postman Flows, real-time
collaborative editing, and production-traffic drift detection.

---

Want to raise something that's missing? Open a
[feature request](https://github.com/logesh-works/postman-mcp/issues/new?template=feature_request.yml).
