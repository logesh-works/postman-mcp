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

`router.register('users', UserViewSet)` (`DefaultRouter`/`SimpleRouter`) is also
resolved, and expands into the full standard action set a `ModelViewSet` provides —
list, create, retrieve, update, partial update, destroy — even when the viewset itself
doesn't define those methods explicitly.

## Known limits

Nested `include()` chains that mix router-registered and explicitly-`path()`-declared
URLs in ways that shadow each other (same prefix, different registration order across
files) aren't specifically flagged — the parser resolves each registration it finds,
but doesn't detect ordering conflicts between them. If your URL configuration is
unusually indirect, the OpenAPI path (`drf-spectacular`) is still the higher-confidence
option, since it reflects what Django actually serves rather than what the parser infers
from source.

## Example

See
[`examples/django-rest-framework/`](https://github.com/logesh-works/postman-mcp/tree/main/examples/django-rest-framework),
which has the real generated Collection items checked in under `expected-output/`.
