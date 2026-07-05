# Spring (Boot)

Spring has no OpenAPI spec unless you've added `springdoc-openapi` yourself, so code
parsing (`input/parsers/spring.py`) is the primary path.

## If you have a spec

With [`springdoc-openapi`](https://springdoc.org/) configured, Spring Boot serves a spec
(commonly at `/v3/api-docs`). Point `init` at it for the higher-confidence path:

```bash
postman-mcp init
# set openApiSource to http://localhost:8080/v3/api-docs (or your configured path)
```

## Code-parsing fallback

There's no Python-accessible Java AST, so this parser is regex-based over `.java`
source, not a real compiler frontend.

| Aspect | From |
|---|---|
| Full path | Class-level `@RequestMapping("/api")` (or the class annotated `@RestController`) joined with the method-level `@GetMapping`/`@PostMapping`/etc. or `@RequestMapping(value=..., method=...)`, plus `server.servlet.context-path` read from `application.properties`/`.yml` if present |
| Body | `@RequestBody Dto param` — the parser resolves `Dto` against its class definition anywhere in the project, including collection types like `List<Dto>` |
| Auth | Not currently detected. Spring Security is usually configured centrally (a `SecurityFilterChain` bean, `@PreAuthorize`), not per-controller, so there's no single-file signal to read reliably yet — every route parses as `auth_required: false`. |

!!! warning "Auth defaults to false, always"
    This is the one framework where auth detection isn't attempted at all rather than
    attempted-and-sometimes-wrong. If your endpoints are actually protected, add the
    Bearer header by hand after syncing, or use `/postman:prompt` to add it as an
    override. Fixing this properly means reading Spring Security's central
    configuration, not the controller file — not done yet.

## Example

See
[`examples/spring-api/`](https://github.com/logesh-works/postman-mcp/tree/main/examples/spring-api),
which has the real generated Collection items checked in under `expected-output/`.
