# FastAPI

FastAPI is the smoothest experience: it emits a complete OpenAPI 3.x spec out of the box,
so Postman MCP uses the [OpenAPI path](../architecture/resolver.md#path-a-use-openapi) —
fully typed, no framework-specific parsing required.

## Recommended setup (OpenAPI)

Point `init` at your running app's spec, or let it auto-detect:

```bash
postman-mcp init
# → detects FastAPI, finds http://localhost:8000/openapi.json
# → inputMode = openapi
```

`config.openApiSource` is saved so every later sync takes the same path. If the app isn't
running, the resolver can also read a committed `openapi.json` or generate one via
`app.openapi()`.

What the OpenAPI path gives you, for free:

- Request bodies from your **Pydantic models** (`$ref` resolved into `components.schemas`)
- All declared **responses** (`response_model` and `responses={...}`)
- **Security** schemes → `authRequired` + the auth header
- **Summaries / descriptions** → request docs

## Code-parsing fallback

When no spec is available, the FastAPI parser
(`input/parsers/fastapi.py`) extracts:

| Aspect | From |
|---|---|
| Routes | `@app.post("/path")` / `@router.get(...)` decorators |
| Body / response types | Pydantic models, `response_model` |
| Auth | `Depends(get_current_user)` and similar |

!!! note "Pydantic v1 and v2"
    The code parser supports **both**. It detects the installed major version and uses the
    matching introspection API (`model_fields` / `model_json_schema` on v2, `__fields__` /
    `schema()` on v1). When FastAPI serves the spec (the OpenAPI path), this is moot — the
    spec already carries the resolved schema.

## Example

A runnable FastAPI example lives at
[`examples/fastapi-basic/`](https://github.com/logesh-works/postman-mcp/tree/main/examples/fastapi-basic)
(code path) and
[`examples/fastapi-openapi/`](https://github.com/logesh-works/postman-mcp/tree/main/examples/fastapi-openapi)
(spec path).
