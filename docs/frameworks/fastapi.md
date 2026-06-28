# FastAPI

FastAPI is the easiest case: it emits a complete OpenAPI 3.x spec out of the box, so
Postman MCP uses the [OpenAPI path](../architecture/resolver.md#path-a-use-openapi).
Fully typed, no framework-specific parsing needed.

## Recommended setup (OpenAPI)

Point `init` at your running app's spec, or let it auto-detect:

```bash
postman-mcp init
# detects FastAPI, finds http://localhost:8000/openapi.json
# sets inputMode = openapi
```

`config.openApiSource` gets saved so every later sync takes the same path. If the app
isn't running, the resolver can also read a committed `openapi.json` or generate one by
running `app.openapi()` in a short subprocess.

What the OpenAPI path gives you, for free:

- Request bodies from your Pydantic models, with `$ref` resolved against
  `components.schemas`.
- Every declared response (`response_model` and `responses={...}`).
- Security schemes mapped to `authRequired` and the auth header.
- Summaries and descriptions used as the request docs.

## Code-parsing fallback

When no spec is available, the FastAPI parser (`input/parsers/fastapi.py`) reads your
source with Python's `ast` module instead. It never imports your project or runs your
code, so it works even if your dependencies aren't installed in the environment Postman
MCP runs in.

| Aspect | From |
|---|---|
| Routes | `@app.post("/path")` / `@router.get(...)` decorators |
| Body and response types | Pydantic model class definitions, `response_model` |
| Auth | `Depends(get_current_user)` and similar patterns |
| Headers | `Header(...)` parameter defaults |

!!! note "Pydantic v1 and v2, without importing either"
    Both versions declare fields the same way in source: `name: type`. The parser reads
    that annotation directly from the AST, so it doesn't need to know or care which
    Pydantic major version your project uses, and never calls into Pydantic at runtime.
    When FastAPI serves a spec, none of this matters anyway: the spec already carries
    the resolved schema.

## Example

A runnable FastAPI example lives at
[`examples/fastapi-basic/`](https://github.com/logesh-works/postman-mcp/tree/main/examples/fastapi-basic)
(code path) and
[`examples/fastapi-openapi/`](https://github.com/logesh-works/postman-mcp/tree/main/examples/fastapi-openapi)
(spec path). Both have the real generated Collection items checked in under their
`expected-output/` directories.
