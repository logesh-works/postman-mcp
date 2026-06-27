# `/postman:sync` — file / module / directory

Sync every API in one file, module, or directory — broader than a single route, narrower
than the whole codebase.

## Usage

```text
/postman:sync -<filename|module|directory> [--into path]
```

## Targeting

The target after `-` is fuzzy-matched against your project:

- A **file** — `-routes/payments.py`
- A **module** — `-app.api.payments`
- A **directory** — `-routes/`

If the target is ambiguous, the command **lists candidates and asks** — it never guesses
silently.

## Flags

| Flag | Effect |
|---|---|
| `--into <path>` | Folder inside the collection where the requests land. Missing folders auto-created. Omitted → `config.defaultInto`. |

## Example

```text
/postman:sync -routes/payments.py --into payments

SYNC PREVIEW — 3 APIs in routes/payments.py  →  collection / payments
+ POST   /payments            [new]      [openapi]
+ GET    /payments/{id}       [new]      [openapi]
~ DELETE /payments/{id}       [modified] [openapi]

Write? [y / n]
```

Each request is matched against the live collection by `METHOD + normalized path`, so
re-running updates in place — no duplicates. See
[idempotency](../architecture/merge-engine.md#idempotency).
