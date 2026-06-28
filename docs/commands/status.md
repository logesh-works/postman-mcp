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

DRIFT CHECK (read-only, nothing will be written)

| Status | Method | Route | Target | Auth | Body | Response | Source |
|---|---|---|---|---|---|---|---|
| [NEW] | POST | /payments/refund | Root Collection | Bearer | RefundRequest | RefundResponse | [code] |
| [MODIFIED] | GET | /orders/{id} | Root Collection | Bearer | N/A | OrderResponse | [openapi] |
| [DEPRECATED] | DELETE | /legacy/import | Root Collection | — | N/A | — | [code] |

Summary: 1 new · 1 modified · 1 deprecated
```

Since `status` never writes, it's safe to run as often as you like. It's also the basis
for the [CI drift-gate](../roadmap.md) planned down the line.
