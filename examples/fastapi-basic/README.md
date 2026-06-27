# Example: FastAPI (basic)

A minimal FastAPI payments API with typed Pydantic bodies, an auth dependency, and
declared responses. This example demonstrates the **code-parsing path** — to force it,
`init` here without pointing at the live `/openapi.json` (otherwise FastAPI's spec would
take the higher-confidence OpenAPI path; see [`../fastapi-openapi/`](../fastapi-openapi/)).

## The API

| Method | Path | Auth | Body | Notes |
|---|---|---|---|---|
| `POST` | `/payments` | ✅ | `PaymentRequest` | Create a payment → 201 |
| `GET` | `/payments/{payment_id}` | ✅ | — | Fetch one |
| `DELETE` | `/payments/{payment_id}` | ✅ | — | Refund → 204 |

## Run it

```bash
pip install -r requirements.txt
uvicorn app:app --reload          # optional — only needed for the OpenAPI path
postman-mcp init                  # connect to a throwaway Postman collection
```

## Sync it

In Claude Code, in this directory:

```text
/postman:syncapi create_payment --into payments
```

Expected diff preview:

```text
SYNC PREVIEW — POST /payments  →  collection / payments   [NEW] [code]

+ Request    POST {{base_url}}/payments
+ Auth       Bearer {{token}}              (from get_current_user dependency)
+ Body       { "amount": 4200, "currency": "USD", "method": "card" }
+ Responses  201 Created, 401, 422, 500
+ Tests      status(201) · schema(PaymentResponse)
+ Examples   1 success, 3 error

Write? [y / n]
```

Or sync the whole file at once:

```text
/postman:sync -app.py --into payments
```

The generated Collection v2.1 item is shown in
[`expected-output/post-payments.item.json`](expected-output/post-payments.item.json).
