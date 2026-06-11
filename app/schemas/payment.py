"""Payment schemas."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.payment import PaymentStatus


class PaymentInitiateRequest(BaseModel):
    order_id: UUID
    gateway: str = Field("RAZORPAY", pattern="^(RAZORPAY|STRIPE)$")


class PaymentInitiateResponse(BaseModel):
    gateway_order_id: str
    amount: Decimal
    currency: str = "INR"
    key: str | None = None


class PaymentVerifyRequest(BaseModel):
    """Client sends this after Razorpay checkout success."""

    razorpay_order_id: str
    razorpay_payment_id: str
    razorpay_signature: str


class PaymentWebhookRequest(BaseModel):
    event: str
    payload: dict
    signature: str | None = None


class PaymentResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    order_id: UUID
    gateway: str
    gateway_order_id: str
    gateway_payment_id: str | None = None
    amount: Decimal
    currency: str
    status: PaymentStatus
