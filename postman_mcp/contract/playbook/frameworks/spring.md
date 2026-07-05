# Spring (Boot) discovery guide

**Registration signals:** class-level `@RequestMapping("prefix")` or `@RestController`,
with method-level `@GetMapping`, `@PostMapping`, `@PutMapping`, `@PatchMapping`,
`@DeleteMapping`, or the generic `@RequestMapping(value=..., method=...)`.

**Mount chain:** the class-level `@RequestMapping` prefix, plus
`server.servlet.context-path` from `application.properties` / `application.yml` if
present — cite the properties/yml line as evidence for that segment.

**Request body:** `@RequestBody Dto param` — cite the `Dto` class definition, including
`List<Dto>` collection bodies (cite the element type's class, not just `List`).

**Auth:** Spring Security annotations (`@PreAuthorize`, `@Secured`) or a
`SecurityFilterChain`/`WebSecurityConfigurerAdapter` rule matching this path. If neither
is found, mark `auth.required: false` at `ai_inferred` confidence rather than asserting
certainty — auth is commonly configured centrally and easy to miss from a single
controller file.

**Responses:** the method's return type if it's a DTO class, or `ResponseEntity<Dto>`'s
type parameter.
