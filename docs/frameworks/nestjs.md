# NestJS

## Recommended setup (OpenAPI)

With [`@nestjs/swagger`](https://docs.nestjs.com/openapi/introduction) configured, NestJS
serves a spec (commonly at `/api-json`) and Postman MCP uses the
[OpenAPI path](../architecture/resolver.md#path-a-use-openapi):

```bash
postman-mcp init
# → detects NestJS, finds http://localhost:3000/api-json
# → inputMode = openapi
```

This captures your DTOs, decorators, and guards accurately from the generated spec.

## Code-parsing fallback

Without a spec, the NestJS parser (`input/parsers/nestjs.py`) extracts:

| Aspect | From |
|---|---|
| Routes | `@Controller` + `@Post()` / `@Get()` decorators |
| Body / response types | DTOs with `class-validator` decorators |
| Auth | `@UseGuards(AuthGuard)` |

!!! warning "Heuristic TypeScript parsing"
    There's no Python TypeScript AST, so the code path uses regex/heuristics. Decorators
    spread across files and dynamic module wiring may be missed. Prefer the OpenAPI path
    (`@nestjs/swagger`) when possible; affected routes are labeled **`[code]`** in the
    [diff](../architecture/diff-engine.md#source-labels).

## Example

See
[`examples/nestjs-api/`](https://github.com/logesh-works/postman-mcp/tree/main/examples/nestjs-api).
