# Flask discovery guide

**Registration signals:** `@app.route(..., methods=[...])`, `@bp.get(`, `@bp.post(`
(Blueprint method shortcuts), on any `Flask` or `Blueprint` instance.

**Mount chain:** `app.register_blueprint(bp, url_prefix='...')` — resolve `bp` to its
`Blueprint(...)` construction, following imports the same way FastAPI routers are
followed. Nested blueprint registration composes prefixes in order.

**Request body:** Flask has no built-in typed body — infer from `request.json`,
`request.get_json()`, or `request.form` usage inside the handler. This is always
`ai_inferred` at best (mark `low_confidence`-equivalent) unless a schema library
(Marshmallow, Pydantic via an extension) is used, in which case cite that schema class.

**Auth:** `@login_required`, `@jwt_required()`, or a custom decorator with an
auth-sounding name, applied to the view function.
