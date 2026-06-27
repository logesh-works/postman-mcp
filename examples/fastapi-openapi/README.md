# Example: FastAPI (OpenAPI path)

Same payments API as [`../fastapi-basic/`](../fastapi-basic/), but configured to use the
**OpenAPI path** — the typed, high-confidence route. FastAPI emits a full OpenAPI 3.x
document at `/openapi.json`; Postman MCP maps it directly with no framework-specific
parsing.

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
SYNC PREVIEW — 2 APIs  →  collection
+ POST /payments         [new] [openapi]
+ GET  /payments/{id}    [new] [openapi]

Write? [y / n]
```

Note the **`[openapi]`** tags — every request was derived from the typed spec, including
the `400` / `401` responses declared via `responses=` on `create_payment`. Compare with
[`../fastapi-basic/`](../fastapi-basic/), where the same routes are tagged `[code]`.
