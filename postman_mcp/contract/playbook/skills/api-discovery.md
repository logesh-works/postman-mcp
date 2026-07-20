# Skill: API Discovery

**Responsibility:** find every endpoint in scope, and cite where each one is registered.
Not request/response bodies (`dto-discovery`), not auth (`auth-discovery`), not JSON
output (`request-builder`/`response-builder`/`collection-builder`) — just: what
endpoints exist, at what method + full path, and what proves it.

This works for any framework/language. There is no parser and no framework list —
your understanding of the code is the discovery engine.

## Bounded retrieval (use this first)

Before reading files free-form, use the MCP's deterministic retrieval tools — they cost
the server nothing to build and cap what you must read:

1. **`index()`** — once per session. Returns a compact repo map: services, languages, and
   the files containing decorated symbols (the likely handlers/DTOs). Use it to know
   *where* to look instead of grepping.
2. **`context(target, budget=8000)`** — per endpoint group. `target` is a file path, a
   handler name, or `"METHOD /path"`. Returns a pre-sliced bundle: the handler, its DTO
   type closure, its mount chain (who registers this router and under what prefix), and
   matching test/OpenAPI witnesses — each chunk headed `file:start-end`. **Those headers
   are exactly the spans the `cite` tool takes as input**, so discovery output is
   citation-ready by construction.

Fall back to reading files directly only when a bundle is insufficient — it lists what it
cut, so ask for the specific missing piece rather than re-reading broadly. On a large
repo this is the difference between a bounded few-K tokens per endpoint and unbounded
whole-repo reading.

## Finding registration sites

Look for whatever your target language/framework uses to register an HTTP handler:
a decorator (`@app.get(...)`, `@GetMapping`, `@Get()`), a route-table call
(`router.get(path, handler)`, `app.use(...)`), or a mapping annotation/config entry. There
is no fixed list to pattern-match — read the code and use your own understanding of the
framework, the same way you would explaining the code to a colleague.

## Resolving the full path

A route's *full* path is rarely just its own literal — trace the mount/prefix chain:
- A router/blueprint/module mounted under a prefix in another file
  (`app.include_router(users.router, prefix="/api/v1")`,
  `app.use('/api', usersRouter)`, `app.setGlobalPrefix('api')` in a separate `main.ts`).
- A controller-level prefix combined with a method-level path
  (`@Controller('users')` + `@Get(':id')`, or a class-level `@RequestMapping` with bare
  method-level `@GetMapping`).
- Chained/nested mounts (a router mounted into another router, mounted into the app).

Compose all levels. If a prefix is computed at runtime from config/env in a way you
genuinely cannot resolve statically, say so in `sync.config.json`'s `notes` rather than
guessing a path — a wrong path is worse than an admitted gap.

## Citing existence

For every endpoint, cite the registration site: the decorator/route-call/mapping line
itself (not just the handler function's `def`/`function` line, though a symbol spanning
both is fine). This citation goes into `metadata.json`'s `citations` — see
`metadata-builder` for the exact shape and hashing. The MCP re-reads and re-hashes this
exact span, so cite precisely: the real file, the real line range.

## Output of this skill

A list of `(method, full_path, registration_citation)` per endpoint in scope, ready for
`auth-discovery` and `dto-discovery` to attach their own findings to, and for
`metadata-builder`/`collection-builder` to turn into artifacts.
