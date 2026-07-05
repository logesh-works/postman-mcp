# Django / DRF discovery guide

**Registration signals:** `path(`, `re_path(` in any `urls.py`; DRF
`DefaultRouter().register(`; class-based `ViewSet`/`ModelViewSet` (each generates the
full 6-action CRUD set — list/create/retrieve/update/partial_update/destroy); function
views wrapped in `@api_view([...])`.

**Mount chain:** `include('app.urls')` inside a project-level `urls.py` — the prefix is
the first arg to `path()` wrapping the `include(...)`. Follow nested `include()` chains
the same way FastAPI's `include_router` is followed.

**Request body:** DRF serializer class referenced by the view (`serializer_class = X`)
or declared inline — cite the `class X(serializers.Serializer):` definition.

**Auth:** `permission_classes = [IsAuthenticated]` (class attribute) or
`@permission_classes([IsAuthenticated])` (function decorator). `AllowAny` or absence
means `auth.required: false`.

**Responses:** DRF serializers typically double as both request and response shape
unless a distinct output serializer is used — cite whichever serializer class the view
actually returns.
