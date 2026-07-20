# Roadmap

What Postman MCP does today, what's actively being worked on, and what's explicitly out
of scope. For what shipped in each release, see [CHANGELOG.md](CHANGELOG.md).

## What's here today

- **Setup spine**: `init` / `doctor` / `serve` / `version`, MCP-server registration,
  slash-command install.
- **Seven `/postman:*` commands**: `syncapi`, `syncchanges`, `sync`, `syncall`,
  `prompt`, `createenv`, `status` — one route, what changed, a file/module/directory,
  the whole codebase, a free-form instruction, an environment, and a read-only drift
  check, respectively.
- **A deterministic repository index and context retrieval** (`index()`/`context()`)
  that Claude uses to find and read exactly the code an endpoint needs, instead of
  reading the project unbounded — see
  [repository index & retrieval](docs/architecture/indexing.md).
- **Citation verification and field grounding.** Every fact Claude claims — a route's
  existence, its body shape, its auth — carries a `file:line` citation the MCP server
  re-reads and re-hashes; every claimed request/response field is checked against the
  real DTO/model class. A citation that doesn't match the code is excluded from the
  write unless explicitly approved.
- **Diff before every write, no flag to skip it.** Human-owned test scripts, edited
  descriptions, and manual examples are preserved on every re-sync; only the structural
  fields update from code.
- **Natural-language sync** via `/postman:prompt` — Claude reads a free-form
  instruction (a persona, extra error responses, a documentation style) and folds it
  directly into what it authors, through the same diff-then-confirm gate as every other
  command.
- **Six supported frameworks**: FastAPI, Django REST Framework, Express, NestJS, Flask,
  and Spring (Boot) — OpenAPI-first where a spec exists, code parsing as the fallback
  (and the only path for Express). See the [framework guides](docs/frameworks/fastapi.md)
  for per-framework detail.
- **A lower-level, deterministic tool surface** (`get_contract`, `submit_model`,
  `verify_model`, `plan`, `apply`, `snapshot`, `rollback`, `audit`) for MCP clients that
  want to submit a structured API model directly and get it verified, planned, and
  applied as explicit steps, with snapshot/rollback support. Reachable today only as
  direct MCP tool calls — see [the engineering handoff](docs/architecture/handoff.md).

## What's next

No version numbers or dates attached — these are the gaps we know about, roughly in
order of what would unblock the most people:

- **CI integration.** A GitHub Action to fail a PR on drift, a Newman runner for
  generated tests, and a `--check` mode for `status`.
- **Automatic handling for routes removed from code.** Today, a route deleted from your
  codebase is noted but not soft-deprecated or removed from the collection automatically
  — you clean it up by hand. Soft-delete-by-default already exists in the merge engine
  for the lower-level tool surface; wiring it into the seven slash commands is next.
  See [`/postman:syncall`](docs/commands/syncall.md).
- **A slash-command wrapper for the verify/plan/apply tool surface**, so `snapshot` and
  `rollback` are reachable without a direct MCP tool call.
- **A business-logic test-script tier**, behind a quality gate. The status and schema
  test tiers ship; a third, inferred tier exists in code but isn't wired up until
  there's a way to be confident it's asserting the right thing.
- **Named, reusable `--skill` bundles** — the same kind of guidance `/postman:prompt`
  already takes free-form (`/postman:prompt "Act as a Stripe API architect"`), as a
  named, shareable preset. See [`examples/prompts/`](examples/prompts/) for the seeds.
- **Multi-service and monorepo support.** The schema already has a `Service` model for
  it; the workspace-discovery step to find and partition multiple services in one repo
  doesn't exist yet.
- **A generated mock server, pre-commit OWASP checks, and an auto-published docs site**
  built from the live collection.

## Known limitations

- **Express and NestJS code parsing is regex/heuristic, not a full AST.** Body and auth
  detection is best-effort and flagged lower-confidence when it falls back to inferring
  from usage instead of reading an explicit type or schema.
- **A route composed through a dynamic import, a computed prefix, or across a package
  boundary can't always be traced.** When a mount genuinely can't be resolved, it's
  reported as unresolved rather than guessed at.
- **Confidence thresholds (90/75/50) in the verify/plan/apply pipeline are engineering
  defaults, not numbers validated against real outcomes yet.**
- **No documented deprecation policy or stable parser interface** for
  community-contributed framework support yet.

## Explicitly out of scope

Environment switching, GraphQL sync, gRPC/Protobuf, Postman Flows, real-time
collaborative editing, and production-traffic drift detection.

---

Found something missing that you need? Open a
[feature request](https://github.com/logesh-works/postman-mcp/issues/new?template=feature_request.yml)
or join the discussion on an existing one.
