# Example: NestJS (OpenAPI path)

A minimal NestJS payments controller with a `class-validator` DTO and an auth guard. With
[`@nestjs/swagger`](https://docs.nestjs.com/openapi/introduction) configured, NestJS serves
a spec (commonly `/api-json`) and Postman MCP uses the high-confidence **OpenAPI path**.

> **Scaffold.** This shows the parts Postman MCP reads (controller decorators, the DTO, the
> guard). Module/bootstrap wiring is omitted; drop the controller into a NestJS app with
> `@nestjs/swagger` enabled.

## What gets read

| Aspect | From |
|---|---|
| Routes | `@Controller("payments")` + `@Post()` / `@Get()` |
| Body shape | `CreatePaymentDto` (class-validator) |
| Auth | `@UseGuards(AuthGuard)` → Bearer `{{token}}` |

## Set up + sync

```bash
postman-mcp init        # detects NestJS; uses /api-json (openapi)
```

```text
/postman:syncall

SYNC PREVIEW
+ POST /payments      [new] [openapi]
+ GET  /payments/{id} [new] [openapi]

Write? [y / n]
```

!!! note
    Without a spec, the code path uses **heuristic TypeScript parsing** (no Python TS AST)
    and may miss decorators spread across files. Prefer the `@nestjs/swagger` OpenAPI path.
    See the [NestJS guide](../../docs/frameworks/nestjs.md).
