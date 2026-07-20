# Example: Flask

A minimal Flask payments API on a blueprint mounted under `/payments`. This exercises
two things at once: Flask's untyped body (inferred from `request.json` usage, not a
declared type) and cross-file-style prefix composition — the blueprint's routes are
declared at `/` and `/<payment_id>`, and only get their real `/payments/...` path because
`register_blueprint(bp, url_prefix="/payments")` is resolved, not read as a leaf
decorator.

## The API

| Method | Path | Auth | Body | Notes |
|---|---|---|---|---|
| `POST` | `/payments` | ✅ | inferred (`amount`, `currency`) | Create a payment → 201 |
| `GET` | `/payments/<payment_id>` | ✅ | — | Fetch one |
| `DELETE` | `/payments/<payment_id>` | ✅ | — | Refund → 204 |

## Run it

```bash
pip install -r requirements.txt
flask --app app run
postman-mcp init                  # connect to a throwaway Postman collection
```

## Sync it

In Claude Code, in this directory:

```text
/postman:syncapi create_payment --into payments
```

Actual diff preview:

```text
Collection: <your collection>
Plan: 1 new · 0 modified

[NEW] POST /payments   → payments   ✓ verified (app.py:18)

Write to Postman? Re-run with confirm=true to apply.   (nothing writes on n)
```

A lower-confidence note on the body is expected here — there's no Pydantic model or
schema to read, just `request.json.get("amount")` / `request.json.get("currency")` in the
handler. That's the ceiling for Flask without a validation library or an OpenAPI spec.

The real generated Collection v2.1 items are checked in under
[`expected-output/`](expected-output/):
[`post-payments.item.json`](expected-output/post-payments.item.json),
[`get-payments-payment-id.item.json`](expected-output/get-payments-payment-id.item.json), and
[`delete-payments-payment-id.item.json`](expected-output/delete-payments-payment-id.item.json).
