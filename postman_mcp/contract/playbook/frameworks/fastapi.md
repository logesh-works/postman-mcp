# FastAPI discovery guide

**Registration signals** (grep for these to enumerate routes):
`@app.get(`, `@app.post(`, `@app.put(`, `@app.patch(`, `@app.delete(`,
`@router.get(`, `@router.post(`, ... (any HTTP-method decorator on an `APIRouter` or
`FastAPI` instance).

**Mount chain:** `app.include_router(child_router, prefix="...")` — follow `child_router`
to its import site, then to its own `APIRouter(prefix=...)` construction or further
nested `include_router` calls. A router mounted under two prefixes (API versioning)
means two distinct endpoints, one per prefix — emit both.

**Request body:** the `Depends`-free parameter typed as a Pydantic `BaseModel` subclass
(or a plain function/class param with a `BaseModel` annotation). Cite the `class
Foo(BaseModel):` definition and its field lines, not the handler signature.

**Auth:** `Depends(get_current_user)` or similar — cite the `Depends(...)` call site.
Absence of any `Depends(...)` with an auth-sounding name means `auth.required: false`.

**Responses:** `response_model=` on the decorator, or the return-type annotation if it's
a `BaseModel` subclass. Status code from `status_code=` kwarg, else the FastAPI default
(200, or 201 only if you have evidence of an explicit override).

**Known unresolved cases:** a prefix computed from `settings.API_PREFIX` or similar —
emit `{{api_prefix}}` and note it in `unresolved`.
