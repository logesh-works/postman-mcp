# Example: Django REST Framework (OpenAPI path)

A minimal DRF payments viewset. With
[`drf-spectacular`](https://drf-spectacular.readthedocs.io/) installed, DRF emits an
OpenAPI 3.x schema and Postman MCP uses the high-confidence **OpenAPI path**.

> **Scaffold.** This shows the parts Postman MCP reads (serializers, viewsets, permission
> classes). A full runnable Django project (settings, urls, manage.py) is intentionally
> omitted; wire it into a project using the standard DRF + drf-spectacular setup.

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

SYNC PREVIEW
+ POST /payments      [new] [openapi]
+ GET  /payments/{id} [new] [openapi]

Write? [y / n]
```

!!! note
    The current **code-parsing fallback** does not yet resolve `DefaultRouter`-registered
    viewsets — prefer the drf-spectacular OpenAPI path for router-driven URLs. See the
    [Django guide](../../docs/frameworks/django.md) and the
    [roadmap](../../docs/roadmap.md).
