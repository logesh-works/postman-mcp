# Example: FastAPI (basic)

A minimal FastAPI payments API with typed Pydantic bodies, an auth dependency, and
declared responses. This example demonstrates the code-parsing path. To force it, run
`init` here without pointing at the live `/openapi.json`; otherwise FastAPI's spec would
take the higher-confidence OpenAPI path (see [`../fastapi-openapi/`](../fastapi-openapi/)).

## The API

| Method | Path | Auth | Body | Notes |
|---|---|---|---|---|
| `POST` | `/payments` | ✅ | `PaymentRequest` | Create a payment → 201 |
| `GET` | `/payments/{payment_id}` | ✅ | — | Fetch one |
| `DELETE` | `/payments/{payment_id}` | ✅ | — | Refund → 204 |

## Run it

```bash
pip install -r requirements.txt
uvicorn app:app --reload          # optional, only needed for the OpenAPI path
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

[NEW] POST /payments   → payments   ✓ verified (app.py:12)

Write to Postman? Re-run with confirm=true to apply.   (nothing writes on n)
```

Or sync the whole file at once:

```text
/postman:sync -app.py --into payments
```

The real generated Collection v2.1 items are checked in under
[`expected-output/`](expected-output/), one file per route:
[`post-payments.item.json`](expected-output/post-payments.item.json),
[`get-payments-payment-id.item.json`](expected-output/get-payments-payment-id.item.json), and
[`delete-payments-payment-id.item.json`](expected-output/delete-payments-payment-id.item.json).
