"""A minimal FastAPI payments API: the flagship Postman MCP example.

Run it:
    pip install -r requirements.txt
    uvicorn app:app --reload

It exposes three routes with typed Pydantic bodies, an auth dependency, and declared
responses: everything the Postman MCP engine needs to build complete requests.
"""

from __future__ import annotations

from fastapi import Depends, FastAPI, HTTPException
from pydantic import BaseModel, Field

app = FastAPI(title="Acme Payments", version="1.0.0")


# --- Auth dependency (Postman MCP detects this → Bearer {{token}}) -----------------

def get_current_user(token: str = "") -> str:
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return "user_123"


# --- Models (Postman MCP reads these → request body + responses) ------------------

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


# --- Routes -----------------------------------------------------------------------

@app.post("/payments", response_model=PaymentResponse, status_code=201)
def create_payment(
    body: PaymentRequest,
    user: str = Depends(get_current_user),
) -> PaymentResponse:
    """Create a new payment.

    Charges the given amount and returns the created payment record.
    """
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


@app.delete("/payments/{payment_id}", status_code=204)
def refund_payment(payment_id: str, user: str = Depends(get_current_user)) -> None:
    """Refund (delete) a payment by id."""
    return None
