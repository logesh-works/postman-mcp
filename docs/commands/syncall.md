# `/postman:syncall`: the whole codebase

Reads every route, controller, and model in the project and syncs all of it. Use it for
first-time setup or after a big refactor. Always diffs first, same as every other
write-capable command.

## Usage

```text
/postman:syncall [--into path]
```

For free-form instructions (add error responses, headers, a rewritten description, …),
use [`/postman:prompt`](prompt.md) instead.

## Flags

| Flag | Effect |
|---|---|
| `--into <path>` | Folder inside the collection every synced route lands in. If omitted, falls back to `config.defaultInto`, which defaults to the collection root. There's no automatic per-route folder inference; every route in the run goes to the same target. |

## When to use it

- **First run after `init`**, to populate an empty or partial collection from scratch.
- **After a refactor**, to reconcile the collection with sweeping code changes.

For everyday work, prefer [`/postman:syncchanges`](syncchanges.md). It's much cheaper
because it only looks at what changed instead of re-reading the whole project.

## Example

```text
/postman:syncall

| Status | Method | Route | Target | Auth | Body | Response | Source |
|---|---|---|---|---|---|---|---|
| [NEW] | POST | /payments | Root Collection | Bearer | PaymentRequest | PaymentResponse | [code] |
| [MODIFIED] | GET | /orders/{id} | Root Collection | Bearer | N/A | OrderResponse | [code] |
| [DEPRECATED] | DELETE | /legacy/import | Root Collection | — | N/A | — | [code] |

Summary: 21 new · 2 modified · 1 deprecated

Write? [y / n]
```

Every route in a run lands in the same target: the collection root by default, or
`--into <path>` if you gave one. Routes are resolved
[OpenAPI-first with per-route fallback to code parsing](../architecture/resolver.md), and
each request is tagged `[openapi]` or `[code]` in the diff so you can see at a glance
which ones came from the lower-confidence path.

## Free-form instructions

`syncall` itself is plain and deterministic. For anything free-form (add error responses,
headers, a rewritten description), use [`/postman:prompt "<text>"`](prompt.md) — Claude
drives this same whole-codebase sync under the hood and applies the changes through the
same diff-then-confirm gate. Because one instruction applies to every route in the run,
keep it broad (e.g. "add the standard error set to everything"). See the
[Prompt & skill layer](../architecture/overview.md#prompt-skill-layer).
