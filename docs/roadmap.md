# Roadmap

The canonical version of this lives in
[`ROADMAP.md`](https://github.com/logesh-works/postman-mcp/blob/main/ROADMAP.md) at the
repo root. This is a condensed summary; see that file for the full detail.

## What's here today

Setup commands, seven `/postman:*` slash commands, a deterministic repository index with
citation verification and field grounding, diff-before-write with human-owned-field
preservation, natural-language sync via `/postman:prompt`, six supported frameworks
(FastAPI, Django REST Framework, Express, NestJS, Flask, Spring), and a lower-level
tool surface with an explicit verify/plan/apply/rollback flow for direct MCP callers.

## What's next

No version numbers attached: CI integration (a GitHub Action, a Newman runner, a
`--check` mode for `status`), automatic handling for routes removed from code, a
slash-command wrapper for the verify/plan/apply tool surface, a business-logic test
tier, named `--skill` bundles, multi-service/monorepo support, a generated mock server,
pre-commit OWASP checks, and an auto-published docs site built from the live collection.

## Known limitations

Express/NestJS code parsing is regex/heuristic rather than a full AST; some dynamic
route composition can't be statically traced and is reported unresolved instead of
guessed at; verify/plan/apply confidence thresholds are engineering defaults, not yet
validated against real outcomes.

## Explicitly out of scope

Environment switching, GraphQL sync, gRPC/Protobuf, Postman Flows, real-time
collaborative editing, and production-traffic drift detection.

---

Want to raise something that's missing? Open a
[feature request](https://github.com/logesh-works/postman-mcp/issues/new?template=feature_request.yml).
