# `/postman:status` — drift check (read-only)

Shows what *would* sync — new, modified, and deprecated routes, plus anything in the
collection that has drifted from code — **without writing anything**. It's
[`syncall`](syncall.md)'s diff minus the write.

## Usage

```text
/postman:status [--since commit|date|last]
```

| Flag | Effect |
|---|---|
| *(none)* | Compare the whole codebase against the live collection. |
| `--since <commit\|date>` | Limit the check to changes since a ref. |
| `--since last` | Check changes since the last sync marker. |

## When to use it

- Before a release, to see whether the collection is in sync.
- In a code review, to understand the API surface a PR changes.
- Any time you want a drift report with **zero risk** of a write.

## Example

```text
/postman:status

DRIFT REPORT — collection "Acme Backend"
+ POST /payments/refund     in code, not in collection      [new]
~ GET  /orders/{id}         body drift: + include_items     [modified]
- DELETE /legacy/import     in collection, not in code      [deprecated]

3 items would change. Run /postman:syncall or /postman:syncchanges to apply.
```

Because `status` never writes, it's safe to run as often as you like — and it's the basis
of a future [CI drift-gate](../roadmap.md).
