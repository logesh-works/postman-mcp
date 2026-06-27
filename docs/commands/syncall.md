# `/postman:syncall` — full codebase

Reads every route, controller, and model in the project and syncs the lot. Use it for
**first-time setup** or **after a refactor**. Always diffs first.

## Usage

```text
/postman:syncall [--into path]
```

## Flags

| Flag | Effect |
|---|---|
| `--into <path>` | Base folder inside the collection for everything synced. Per-route folder structure still applies beneath it. Omitted → `config.defaultInto`. |

## When to use it

- **First run after `init`** — populate an empty (or partial) collection from scratch.
- **After a refactor** — reconcile the collection with sweeping code changes.

For everyday work, prefer [`/postman:syncchanges`](syncchanges.md), which is far cheaper
because it only looks at what changed.

## Example

```text
/postman:syncall

SYNC PREVIEW — 24 APIs across the codebase
+ 21 new
~  2 modified
-  1 deprecated (DELETE /legacy/import — not found in code)

Folders: auth, payments, orders, webhooks

Write? [y / n]
```

Routes are resolved [OpenAPI-first with per-route fallback to code parsing](../architecture/resolver.md);
each request is tagged `[openapi]` or `[code]` in the diff so lower-confidence
code-parsed routes are visible at a glance.
