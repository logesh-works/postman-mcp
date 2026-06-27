"""FastAPI example for the OpenAPI path.

Identical surface to ../fastapi-basic, but here we point Postman MCP at the live spec
(`/openapi.json`) so it uses the typed, high-confidence OpenAPI path instead of code
parsing. Note the explicit `responses=` declarations — they flow straight into saved
Postman responses via the spec.

Run it:
    pip install -r requirements.txt
    uvicorn app:app --reload          # serves /openapi.json at :8000
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Acme Payments", version="1.0.0")


def get_current_user(token: str = "") -> str:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return "user_123"


class PaymentRequest(BaseModel):
    amount: int = Field(..., gt=0, description="Amount in minor units (cents)")
    currency: str = Field("USD", description="ISO 4217 currency code")
    method: str = Field(..., description="card | bank | wallet")


class PaymentResponse(BaseModel):
    id: str
    amount: int
    currency: str
    status: str
    created_at: str


class ErrorResponse(BaseModel):
    detail: str


@app.post(
    "/payments",
    response_model=PaymentResponse,
    status_code=201,
    responses={
        400: {"model": ErrorResponse, "description": "Invalid request"},
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    },
)
def create_payment(
    body: PaymentRequest,
    user: str = Depends(get_current_user),
) -> PaymentResponse:
    """Create a new payment."""
    return PaymentResponse(
        id="pay_abc123",
        amount=body.amount,
        currency=body.currency,
        status="succeeded",
        created_at="2026-06-27T10:00:00Z",
    )


@app.get("/payments/{payment_id}", response_model=PaymentResponse)
def get_payment(payment_id: str, user: str = Depends(get_current_user)) -> PaymentResponse:
    """Fetch a single payment by id."""
    return PaymentResponse(
        id=payment_id,
        amount=4200,
        currency="USD",
        status="succeeded",
        created_at="2026-06-27T10:00:00Z",
    )
