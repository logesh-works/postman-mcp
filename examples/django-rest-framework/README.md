# Example: Django REST Framework (OpenAPI path)

A minimal DRF payments viewset. With
[`drf-spectacular`](https://drf-spectacular.readthedocs.io/) installed, DRF emits an
OpenAPI 3.x schema and Postman MCP uses the high-confidence **OpenAPI path**.

> **Scaffold.** This shows the parts Postman MCP reads (serializers, viewsets, permission
> classes) plus a minimal [`urls.py`](urls.py) so the code path is self-contained. A full
> runnable Django project (settings, manage.py) is intentionally omitted; wire it into a
> project using the standard DRF + drf-spectacular setup.

## What gets read

| Aspect | From |
|---|---|
| Routes | the viewset actions / `urls.py` |
| Body & response shapes | `PaymentSerializer` |
| Auth | `permission_classes = [IsAuthenticated]` → Bearer `{{token}}` |

## Set up + sync

```bash
postman-mcp init        # detects Django; uses the drf-spectacular schema (openapi)
```

```text
/postman:syncall

Collection: <your collection>
Plan: 2 new · 0 modified

[NEW] POST /payments   → (root)   ✓ verified (schema)
[NEW] GET /payments/{id}   → (root)   ✓ verified (schema)

Write to Postman? Re-run with confirm=true to apply.
```

!!! note
    The code-parsing fallback reads explicit `path('x/', ViewSet.as_view({'get': 'list',
    'post': 'create'}))` mappings and honors exactly the methods you map. It does
    **not** yet expand `DefaultRouter`-registered viewsets; for router-driven URLs
    prefer the drf-spectacular OpenAPI path. See the
    [Django guide](../../docs/frameworks/django.md) and the
    [roadmap](../../docs/roadmap.md).

## Generated output

[`expected-output/`](expected-output/) holds the real Collection v2.1 items the **code
path** produces from [`urls.py`](urls.py) and [`views.py`](views.py), one file per
mapped route. Because the URLs use explicit `.as_view({...})` mappings, only the methods
named there appear (no invented `PUT` / `DELETE`), and
[`post-payments.item.json`](expected-output/post-payments.item.json) carries the
`PaymentSerializer` body fields.
