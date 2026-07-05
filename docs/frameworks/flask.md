# Flask

Flask has no native OpenAPI spec and no built-in typed request/response model, so code
parsing (`input/parsers/flask.py`) is the primary path for most Flask apps.

## If you have a spec

If your app is documented with `flask-smorest`, `apiflask`, or a hand-written
`openapi.json`, point `init` at it and you get the high-confidence OpenAPI path instead:

```bash
postman-mcp init
# set openApiSource to your committed openapi.json / swagger.json
```

## Code-parsing fallback

The parser reads routes from `@app.route('/x', methods=[...])` and the Flask 2.0
shorthand (`@app.get(...)`, `@bp.post(...)`), on both a bare `Flask` app and a
`Blueprint`.

| Aspect | From |
|---|---|
| Routes | `@app.route(...)` / `@bp.route(...)`, and the `.get`/`.post`/etc. shorthand |
| Full path | The blueprint's `url_prefix` composed with `register_blueprint(..., url_prefix=...)`, resolved across files the same way FastAPI's router mounts are — reading only the leaf decorator would drop the blueprint's prefix |
| Body | Inferred from `request.json`/`request.form`/`get_json()` usage in the handler. Flask has no built-in typed body, so this is always a guess from usage, never a declared type, and is flagged lower confidence in the diff |
| Auth | `@login_required`, `@jwt_required`, or a similarly-named custom decorator |

!!! warning "Bodies are always inferred, never typed"
    Unlike FastAPI (Pydantic) or NestJS (DTOs), there's no framework-native typed body to
    read here — every Flask body comes from watching how `request.json`/`request.form`
    is accessed in the handler. It's tagged `[code]` and "lower confidence" in the
    [diff](../architecture/diff-engine.md#source-labels) every time, not just when it
    falls back. If you use a validation library (Marshmallow, Pydantic via an extension)
    that constrains the request centrally, the OpenAPI path is the more accurate option.

## Example

See
[`examples/flask-api/`](https://github.com/logesh-works/postman-mcp/tree/main/examples/flask-api),
which has the real generated Collection items checked in under `expected-output/`.
