# Roadmap

The canonical roadmap lives in
[`ROADMAP.md`](https://github.com/logesh-works/postman-mcp/blob/main/ROADMAP.md) at the
repo root. Here's the short version of each milestone:

## 0.1.0: the kernel works end to end

Setup commands, the deterministic engine, OpenAPI-first resolution, code-parsing fallback
for all four frameworks, all six commands, diff-before-write, and preservation of
human-owned fields. Tagged, published to PyPI, and validated with a live run against a
real Postman workspace.

## 1.0.0: the Claude-guided prompt layer

Adds `--prompt` on the four sync commands — generation guidance consumed entirely by
Claude Code, never forwarded to the deterministic MCP server — plus `examples/prompts/`
and the documented intelligence/execution layer-separation principle. No changes to the
engine, resolver, or merge logic.

## 1.1.0: foundation hardening (current)

Fixes an audit of real production-shaped output actually found: Express schema
resolution now works across files and through validation middleware (closing an empty
`{}` body bug), `init`'s collection picker sticks to what's already configured instead of
drifting, OpenAPI-first is enforced for a committed spec in any input mode, and
collection placement is fully deterministic. Django `DefaultRouter` resolution, cross-file
router-prefix resolution, `syncchanges` file-to-route mapping for pure-OpenAPI sources,
and the opt-in business-logic test tier are carried forward, unchanged.

## 1.2.0: CI and the test loop

A GitHub Actions / GitLab CI hook, Newman test-runner integration, and a `--check` mode
for `status` suitable for CI gating.

## 1.3.0: proven at scale

A documented deprecation policy on top of the existing SemVer guarantee, complete
framework guides, validated success metrics, and a stable parser interface for
community-contributed frameworks.

## Skills

`--prompt` is **Phase 1** of a skill architecture. Today you can pass Claude free-form
guidance for a sync; the next phase packages that into reusable, named skills:

```bash
--skill fintech
--skill healthcare
--skill ecommerce
```

A skill is a curated bundle of prompt guidance that Claude loads before calling the MCP
tool. The layer boundary holds: **skills are consumed by Claude, never by the MCP
server**, and the engine stays deterministic. See the
[Prompt & skill layer](architecture/overview.md#prompt-skill-layer).

## Beyond 1.3

A mock server generated from your schema, pre-commit OWASP checks, and auto-published
living docs.

---

Want to influence the roadmap? Open a
[feature request](https://github.com/logesh-works/postman-mcp/issues/new?template=feature_request.yml).
