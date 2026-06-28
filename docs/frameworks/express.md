# Express

Express has no native OpenAPI spec and no native type system, so it's the primary case
for the [code-parsing path](../architecture/resolver.md#path-b-parse-code-the-fallback).
There's no TypeScript or JavaScript AST this project depends on, so the parser is
regex and heuristic based, not a real parser in the compiler sense.

## If you have a spec

If your Express app is documented with `swagger-jsdoc`, `tsoa`, or a hand-written
`openapi.json`, point `init` at it and you get the high-confidence OpenAPI path instead:

```bash
postman-mcp init
# set openApiSource to your committed openapi.json / swagger.json
```

## Code-parsing fallback

The Express parser (`input/parsers/express.py`) reads body fields in this order, falling
through to the next only if the current one finds nothing:

1. **A Joi, Zod, or Yup schema** validated against `req.body` in the route, either
   defined inline or referenced from a `const schema = Joi.object({...})` elsewhere in
   the file. Treated the same as a typed body: high confidence.
2. **JSDoc `@body {type} name` tags** on the comment block above the route. Also high
   confidence, since it's an explicit author annotation.
3. **Destructuring or dot-access on `req.body`** (`const { amount } = req.body` or
   `req.body.amount`), with no schema or JSDoc backing it up. This is inferred from
   usage, carries no type information, and is flagged lower confidence.

| Aspect | From |
|---|---|
| Routes | `app.get/post/put/patch/delete(...)`, `router.*` |
| Body | Schema validation, JSDoc, or inferred usage, in that order (above) |
| Auth | Middleware passed inline to the route, or registered globally with `app.use(mw)` / `router.use(mw)` |

!!! warning "Inferred bodies are flagged, not hidden"
    A body resolved from schema validation or JSDoc is just as trustworthy as a typed
    DTO and isn't flagged. A body inferred purely from `req.body` usage, with neither of
    those present, gets tagged `[code]` and "lower confidence" in the
    [diff](../architecture/diff-engine.md#source-labels). The fix is almost always to
    add a JSDoc `@body` tag or adopt a validation library you're probably already using.

    Routing that's spread across files, or built dynamically rather than as flat
    `app.METHOD(path, handler)` calls, may not be picked up. When that happens, sync the
    route explicitly with [`/postman:syncapi "POST /path"`](../commands/syncapi.md).

## Example

See
[`examples/express-api/`](https://github.com/logesh-works/postman-mcp/tree/main/examples/express-api),
which has the real generated Collection items checked in under `expected-output/`, and
its README walks through exactly which fields come from JSDoc versus inference.
