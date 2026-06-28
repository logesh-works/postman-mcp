# NestJS

## Recommended setup (OpenAPI)

With [`@nestjs/swagger`](https://docs.nestjs.com/openapi/introduction) configured, NestJS
serves a spec (commonly at `/api-json`) and Postman MCP uses the
[OpenAPI path](../architecture/resolver.md#path-a-use-openapi):

```bash
postman-mcp init
# detects NestJS, finds http://localhost:3000/api-json
# sets inputMode = openapi
```

This captures your DTOs, decorators, and guards accurately from the generated spec.

## Code-parsing fallback

Without a spec, the NestJS parser (`input/parsers/nestjs.py`) extracts:

| Aspect | From |
|---|---|
| Routes | `@Controller` + `@Post()` / `@Get()` decorators |
| Body and response types | DTO classes with `class-validator` decorators |
| Headers | `@Headers('x-api-key') key: string` parameters |
| Auth | `@UseGuards(AuthGuard)` |

DTO class bodies are read with a brace-depth walker rather than a regex that stops at
the first `}`, so a property decorated with an object-literal argument (for example
`@ApiProperty({ type: String })` from `@nestjs/swagger`) doesn't truncate the class or
leak `type`/`example` in as bogus fields.

!!! warning "Heuristic TypeScript parsing"
    There's no Python TypeScript AST, so this path uses regex and heuristics, not a real
    parser. Decorators spread across files and dynamic module wiring may be missed.
    Prefer the OpenAPI path (`@nestjs/swagger`) when you can; affected routes are
    labeled `[code]` in the [diff](../architecture/diff-engine.md#source-labels) so you
    can spot them.

## Example

See
[`examples/nestjs-api/`](https://github.com/logesh-works/postman-mcp/tree/main/examples/nestjs-api),
which has the real generated Collection items checked in under `expected-output/`.
