# `/postman:status`: drift check (read-only)

Shows what would sync: new, modified, and deprecated routes, plus anything in the
collection that has drifted from the code, without writing anything. It's
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

- Before a release, to check whether the collection is in sync.
- In a code review, to see the API surface a PR actually changes.
- Any time you want a drift report with zero risk of accidentally writing something.

## Example

```text
/postman:status

Collection: Acme Backend
Plan: 1 new · 1 modified

[NEW] POST /payments/refund   → (root)   ✓ verified (app/payments.py:58)
[MODIFY] GET /orders/{id}   → (root)   ✓ verified (app/orders.py:40)

Write to Postman? Re-run with confirm=true to apply.
```

`status` calls the same discovery and verification path as every sync command, but the
turn ends after showing this preview — it never calls the tool again with `confirm: true`.
Since it never writes, it's safe to run as often as you like. It's also the basis for the
[CI drift-gate](../roadmap.md) planned down the line.
