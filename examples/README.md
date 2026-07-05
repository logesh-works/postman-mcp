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
| [`flask-api/`](flask-api/) | Flask | code parsing | ✅ runnable |
| [`spring-api/`](spring-api/) | Spring (Boot) | code parsing | 📝 scaffold |

For AI-assisted syncing, [`prompts/`](prompts/) holds ready-made personas for
[`/postman:prompt`](../docs/commands/prompt.md) (fintech, healthcare, enterprise,
ecommerce) showing how an instruction steers **Claude** while the MCP server stays
deterministic.

Each framework directory contains:

- **source code**: a minimal but realistic API
- **`README.md`**: the command to run and the expected output
- **`expected-output/`**: the real generated Collection v2.1 item per route, checked in
  so you can see it without running anything
- *(screenshots: see [`assets/`](../assets/README.md) for the capture plan)*

## Running an example

```bash
cd examples/fastapi-basic
pip install -r requirements.txt
postman-mcp init          # connect this example to a throwaway Postman collection
# then in Claude Code:
/postman:syncall
```

> Use a throwaway collection for examples. They're for demonstration, not your real API
> surface.
