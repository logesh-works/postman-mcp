# Django REST Framework

## Recommended setup (OpenAPI)

With [`drf-spectacular`](https://drf-spectacular.readthedocs.io/) installed, DRF emits a
valid OpenAPI 3.x schema and Postman MCP uses the
[OpenAPI path](../architecture/resolver.md#path-a-use-openapi):

```bash
postman-mcp init
# → detects Django, finds the schema endpoint / committed openapi.yaml
# → inputMode = openapi
```

This is the most accurate path: serializers, responses, and auth all come straight from
the generated schema.

## Code-parsing fallback

Without a spec, the DRF parser (`input/parsers/django.py`) extracts:

| Aspect | From |
|---|---|
| Routes | `urls.py` patterns, viewsets |
| Body / response types | serializers |
| Auth | `permission_classes` |

## Known limits

!!! warning "Router-registered viewsets"
    The current parser covers `path('x/', View.as_view())` and explicit viewsets.
    **`DefaultRouter`-registered viewsets and nested `include()` chains are not yet fully
    resolved** in the code path — see the [roadmap](../roadmap.md). If your URLs are
    router-driven, prefer the OpenAPI path (`drf-spectacular`), which captures them all.

## Example

See
[`examples/django-rest-framework/`](https://github.com/logesh-works/postman-mcp/tree/main/examples/django-rest-framework).
