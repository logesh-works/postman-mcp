# Skill: DTO Discovery

**Responsibility:** for each endpoint, resolve the request body's and each declared
response's actual model/DTO class, including nested and inherited fields, and cite the
**class declaration**, not the handler. This is the single highest-leverage skill for
accuracy — get this right and `metadata-builder`'s field-grounding check will confirm it
mechanically; get it wrong (or cite the wrong location) and the endpoint gets excluded.

## Bounded retrieval (use this first)

`context("<handler or file>")` already includes the DTO **type closure** for a handler —
the request/response model classes it references, nested models, and base classes, each
chunk headed `file:start-end`. Prefer that over hunting imports by hand; the header of
the DTO's chunk is exactly the span to pass to the `cite` tool for the `dto` citation.
Read the DTO file directly only if the bundle trimmed something you need (it says what
it cut).

## Finding the request body's DTO

From the handler's parameter list (or equivalent), find the type/class bound to the
request body (`@Body() dto: CreateUserDto`, `def create(body: CreateUserDto)`,
`@RequestBody CreateUserDto dto`). Follow that type to its **class declaration** —
not a re-export, not a type alias, the actual `class CreateUserDto { ... }` (or
equivalent) with its field list.

## Resolving nested and inherited fields

- **Inheritance**: if the DTO extends a base class, its fields belong to the DTO too.
  Walk the inheritance chain and include every inherited field, not just the DTO's own
  declared ones. Stop at a base you don't control (a library class like `BaseModel`
  itself) — that's the terminal, not a field source.
- **Nesting**: if a field's type is itself another class in your codebase (not a
  primitive/array-of-primitive), that's a real nested shape — note it, but the citation
  and `fields` list you build (see `metadata-builder`) describe **one class's own
  attribute names at a time**; nested object shapes are a known simplification of this
  flow's metadata format, not something to flatten incorrectly.

## Finding response DTOs

From the handler's return type annotation, a `response_model=`/`@ApiResponse` decorator,
a serializer, or the literal shape of what's returned (`return { ... }` with no explicit
type) — resolve the same way as the request body. If a response has no typed model at
all (a framework that serializes an ORM object directly, or a dynamically-built dict),
say so rather than inventing a class citation for something that doesn't exist as a class.

## The citation rule that matters most

**Cite the class's own declaration line** (e.g. `class CreateUserDto {` or
`class CreateUserDto(BaseModel):`), not the handler function, not an import line. The
MCP resolves the class at your cited span and checks every field you claim against its
real attributes (including inherited ones) — citing the handler instead means that check
can't run at all (informational only), and citing the wrong line or a fabricated
file/line excludes the whole endpoint. When in doubt, cite tighter (just the class header
line) rather than a large span.

## What you're producing

Per endpoint: the request body's DTO citation + real field names (`dto-discovery`'s
output), and the same for each response. `metadata-builder` turns this into the
`body`/`responses[]` shape; `request-builder`/`response-builder` turn the real field
names + types into example JSON.
