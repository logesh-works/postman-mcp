# Example: FastAPI (OpenAPI path)

Same payments API as [`../fastapi-basic/`](../fastapi-basic/), but configured to use the
OpenAPI path instead of code parsing. FastAPI emits a full OpenAPI 3.x document at
`/openapi.json`, and Postman MCP maps it directly with no framework-specific parsing.

## Run it

```bash
pip install -r requirements.txt
uvicorn app:app --reload          # serves the spec at http://localhost:8000/openapi.json
```

## Set up the OpenAPI path

```bash
postman-mcp init
#   → detects FastAPI
#   → finds http://localhost:8000/openapi.json
#   → inputMode = openapi, openApiSource = http://localhost:8000/openapi.json
```

Your `postman-mcp.json` will record:

```json
{
  "config": {
    "framework": "fastapi",
    "inputMode": "openapi",
    "openApiSource": "http://localhost:8000/openapi.json"
  }
}
```

## Sync it

```text
/postman:syncall
```

```text
| Status | Method | Route | Target | Auth | Body | Response | Source |
|---|---|---|---|---|---|---|---|
| [NEW] | POST | /payments | Root Collection | Bearer | PaymentRequest | PaymentResponse | [openapi] |
| [NEW] | GET | /payments/{id} | Root Collection | Bearer | N/A | PaymentResponse | [openapi] |

Write? [y / n]
```

Note the `[openapi]` tags: every request was derived from the typed spec, including the
`400` / `401` responses declared via `responses=` on `create_payment`. Compare with
[`../fastapi-basic/`](../fastapi-basic/), where the same routes are tagged `[code]`.

## Generated output

[`expected-output/`](expected-output/) holds the real Collection v2.1 items produced for
this app's routes (one file per route). These are generated from the **code path**
(AST parsing of [`app.py`](app.py)) so they can be checked in without a running server;
the live OpenAPI sync above yields the same requests, tagged `[openapi]` and carrying the
spec's declared response set.
