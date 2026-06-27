# Roadmap

The canonical roadmap lives in
[`ROADMAP.md`](https://github.com/logesh-works/postman-mcp/blob/main/ROADMAP.md) at the
repo root. Summary of the milestones:

## 0.1.0 — MVP: the kernel works end to end

Setup spine, the engine, OpenAPI-first resolution, code-parsing fallback for four
frameworks, all six commands, diff-before-write, and preservation of human-owned fields.
**Gated on a real test suite (>80% coverage) and a validated live run before release.**

## 0.2.0 — Hardening and parser depth

Django `DefaultRouter` resolution, stronger Express/NestJS extraction, `syncchanges`
file→route mapping for pure-OpenAPI sources, and an opt-in business-logic test tier.

## 0.3.0 — CI and the test loop

GitHub Actions / GitLab CI hook, Newman test-runner integration, and a `--check` mode for
`status` suitable for CI gating.

## 1.0.0 — Stable, documented, supported

SemVer guarantees, a documented deprecation policy, complete framework guides, validated
success metrics, and a stable parser interface for community frameworks.

## Beyond 1.0

Mock server from schema · pre-commit OWASP checks · auto-published living docs.

---

Want to influence the roadmap? Open a
[feature request](https://github.com/logesh-works/postman-mcp/issues/new?template=feature_request.yml).
