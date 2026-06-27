# Examples

Each example is a small, self-contained API plus the exact Postman MCP command you'd run
against it and the request it generates. They double as fixtures for understanding how the
[resolver](../docs/architecture/resolver.md) picks OpenAPI vs. code per framework.

| Example | Framework | Input path | Status |
|---|---|---|---|
| [`fastapi-basic/`](fastapi-basic/) | FastAPI | code parsing | ✅ runnable |
| [`fastapi-openapi/`](fastapi-openapi/) | FastAPI | OpenAPI spec | ✅ runnable |
| [`django-rest-framework/`](django-rest-framework/) | Django REST Framework | OpenAPI (drf-spectacular) | 📝 scaffold |
| [`express-api/`](express-api/) | Express | code parsing | 📝 scaffold |
| [`nestjs-api/`](nestjs-api/) | NestJS | OpenAPI (@nestjs/swagger) | 📝 scaffold |

Each directory contains:

- **source code** — a minimal but realistic API
- **`README.md`** — the command to run and the expected output
- **`expected-output/`** — the diff preview and the generated Collection v2.1 item
- *(screenshots — see [`assets/`](../assets/README.md) for the capture plan)*

## Running an example

```bash
cd examples/fastapi-basic
pip install -r requirements.txt
postman-mcp init          # connect this example to a throwaway Postman collection
# then in Claude Code:
/postman:syncall
```

> Use a **throwaway collection** for examples — they're for demonstration, not your real
> API surface.
