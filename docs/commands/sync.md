# `/postman:sync`: file, module, or directory

Syncs every route in one file, module, or directory. Broader than a single route,
narrower than the whole codebase.

## Usage

```text
/postman:sync -<filename|module|directory> [--into path]
```

For free-form instructions (add error responses, headers, a rewritten description, …),
use [`/postman:prompt`](prompt.md) instead.

## Targeting

The target after `-` is fuzzy-matched against your project:

- A **file**, like `-routes/payments.py`
- A **module**, like `-app.api.payments`
- A **directory**, like `-routes/`

If the target is ambiguous, the command lists the candidates and asks you to be
specific. It never guesses.

## Flags

| Flag | Effect |
|---|---|
| `--into <path>` | Folder inside the collection where the requests land. Missing folders are created automatically. If omitted, falls back to `config.defaultInto`, which defaults to the collection root. No folder gets inferred from the file or module name. |

## Example

```text
/postman:sync -routes/payments.py --into payments

| Status | Method | Route | Target | Auth | Body | Response | Source |
|---|---|---|---|---|---|---|---|
| [NEW] | POST | /payments | payments | Bearer | PaymentRequest | PaymentResponse | [code] |
| [NEW] | GET | /payments/{id} | payments | Bearer | N/A | PaymentResponse | [code] |
| [MODIFIED] | DELETE | /payments/{id} | payments | Bearer | N/A | — | [code] |

Write? [y / n]
```

Each request is matched against the live collection by `METHOD + normalized path`, so
re-running this updates routes in place instead of creating duplicates. See
[idempotency](../architecture/merge-engine.md#idempotency). Once the write result is
shown, the command ends; no further analysis or follow-on commentary.

## Free-form instructions

`sync` itself is plain and deterministic. For anything free-form (add error responses,
headers, a rewritten description, example values), use
[`/postman:prompt "<text>"`](prompt.md) — Claude targets this same file/module/dir sync
under the hood and applies the changes through the same diff-then-confirm gate. See the
[Prompt & skill layer](../architecture/overview.md#prompt-skill-layer).
