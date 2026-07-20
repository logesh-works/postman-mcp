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

Collection: <your collection>
Plan: 2 new · 0 modified

[NEW] POST /payments   → (root)   ✓ verified (openapi)
[NEW] GET /payments/{id}   → (root)   ✓ verified (openapi)

Write to Postman? Re-run with confirm=true to apply.
```

The response is saved by status code rather than a named type, because this controller
has no `@ApiResponse({ type: ... })` decorator. Add one if you want the spec (and the
synced response) to carry a named response shape instead.

!!! note
    Without a spec, the code path uses **heuristic TypeScript parsing** (no Python TS AST)
    and may miss decorators spread across files. Prefer the `@nestjs/swagger` OpenAPI path.
    See the [NestJS guide](../../docs/frameworks/nestjs.md).

## Generated output

[`expected-output/`](expected-output/) holds the real Collection v2.1 items the **code
path** produces for this controller (one file per route). Useful for seeing what the
TypeScript-heuristic fallback yields when no spec is present.
[`post-payments.item.json`](expected-output/post-payments.item.json) shows the
`CreatePaymentDto` fields resolved correctly even though one is decorated with a
nested-brace `@ApiProperty({ ... })`, which used to truncate DTO parsing.
