"""Minimal Django REST Framework payments API — OpenAPI path via drf-spectacular.

This is a scaffold focused on what Postman MCP reads: serializers, viewsets, and
permission classes. With drf-spectacular installed, the generated OpenAPI schema is the
high-confidence input path.

Wire-up (settings/urls) is omitted for brevity; see the DRF + drf-spectacular docs.
"""

from rest_framework import serializers, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response


class PaymentSerializer(serializers.Serializer):
    amount = serializers.IntegerField(min_value=1, help_text="Amount in minor units")
    currency = serializers.CharField(default="USD", help_text="ISO 4217 code")
    method = serializers.ChoiceField(choices=["card", "bank", "wallet"])


class PaymentViewSet(viewsets.ViewSet):
    """CRUD for payments. Auth is required (IsAuthenticated → Bearer {{token}})."""

    permission_classes = [IsAuthenticated]

    def create(self, request):
        """POST /payments — create a payment."""
        serializer = PaymentSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(
            {
                "id": "pay_abc123",
                "amount": serializer.validated_data["amount"],
                "currency": serializer.validated_data["currency"],
                "status": "succeeded",
                "created_at": "2026-06-27T10:00:00Z",
            },
            status=201,
        )

    def retrieve(self, request, pk=None):
        """GET /payments/{id} — fetch a payment."""
        return Response(
            {"id": pk, "amount": 4200, "currency": "USD", "status": "succeeded"}
        )
