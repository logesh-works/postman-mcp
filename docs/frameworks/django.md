# Django REST Framework

## Recommended setup (OpenAPI)

With [`drf-spectacular`](https://drf-spectacular.readthedocs.io/) installed, DRF emits a
valid OpenAPI 3.x schema and Postman MCP uses the
[OpenAPI path](../architecture/resolver.md#path-a-use-openapi):

```bash
postman-mcp init
# detects Django, finds the schema endpoint or a committed openapi.yaml
# sets inputMode = openapi
```

This is the most accurate path. Serializers, responses, and auth all come straight from
the generated schema.

## Code-parsing fallback

Without a spec, the DRF parser (`input/parsers/django.py`) reads your source with
Python's `ast` module:

| Aspect | From |
|---|---|
| Routes | `urls.py` `path(...)` patterns, both class-based views and function-based `@api_view([...])` views |
| Which HTTP methods a URL serves | The `.as_view({'get': 'list', 'post': 'create'})` mapping, when a viewset uses one |
| Body and response types | `serializer_class` on the view, or a serializer instantiated directly in an `@api_view` function body |
| Auth | `permission_classes = [IsAuthenticated]` on a class, or `@permission_classes([IsAuthenticated])` on a function |

If a `path(...)` call passes an explicit `.as_view({...})` mapping, the parser only
generates routes for the methods named in that mapping. It won't invent a `PUT` or
`DELETE` route just because the viewset class happens to define those actions.

## Known limits

!!! warning "Router-registered viewsets"
    `DefaultRouter`-registered viewsets and nested `include()` chains aren't resolved by
    the code parser yet; see the [roadmap](../roadmap.md). If your URLs are
    router-driven rather than explicit `path()` calls, use the OpenAPI path
    (`drf-spectacular`), which captures them correctly regardless of how the router
    wires them up.

## Example

See
[`examples/django-rest-framework/`](https://github.com/logesh-works/postman-mcp/tree/main/examples/django-rest-framework),
which has the real generated Collection items checked in under `expected-output/`.
