"""URL wiring for the payments API.

Postman MCP reads ``path(...)`` patterns here to discover routes and links each to the
view it points at (and through that, the serializer + permission classes). A real DRF
project usually mounts a ``ViewSet`` via a router; the explicit ``as_view`` mapping below
is the form this parser reads directly without importing your project.
"""

from django.urls import path

from .views import PaymentViewSet

urlpatterns = [
    path("payments/", PaymentViewSet.as_view({"get": "list", "post": "create"})),
    path("payments/<str:pk>/", PaymentViewSet.as_view({"get": "retrieve"})),
]
