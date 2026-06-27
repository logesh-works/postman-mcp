# Express

Express has **no native OpenAPI spec and no native type system**, so it's the primary
case for the [code-parsing path](../architecture/resolver.md#path-b-parse-code-fallback).
Body inference is best-effort and clearly flagged.

## If you have a spec

If your Express app is documented with `swagger-jsdoc`, `tsoa`, or a hand-written
`openapi.json`, point `init` at it and you'll get the high-confidence OpenAPI path:

```bash
postman-mcp init
# → set openApiSource to your committed openapi.json / swagger.json
```

## Code-parsing fallback

The Express parser (`input/parsers/express.py`) extracts:

| Aspect | From |
|---|---|
| Routes | `app.get/post/...`, `router.*`, and router mounts |
| Body / response types | JSDoc annotations or inline shapes (weaker — no native types) |
| Auth | auth middleware in the handler chain |

!!! warning "Lower confidence by design"
    Because Express has no type system, body inference is **best-effort** and every
    affected request is labeled **`[code]`** and flagged "lower confidence" in the
    [diff](../architecture/diff-engine.md#source-labels). Add JSDoc `@body` annotations to
    improve results, or adopt a spec generator for the high-confidence path.

    Complex routing — dynamic mounts, routers spread across files — may be missed. When
    that happens, sync the route explicitly with
    [`/postman:syncapi "POST /path"`](../commands/syncapi.md).

## Example

See
[`examples/express-api/`](https://github.com/logesh-works/postman-mcp/tree/main/examples/express-api).
