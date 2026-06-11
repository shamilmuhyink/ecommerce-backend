"""Payment endpoints — verify and webhook."""

import json

import structlog
from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.schemas.common import ApiResponse
from app.schemas.payment import PaymentResponse, PaymentVerifyRequest
from app.services.payment_service import PaymentService

logger = structlog.get_logger(__name__)

router = APIRouter()


def get_payment_service() -> PaymentService:
    """Build PaymentService with its dependencies."""
    from app.repositories.order_repository import OrderRepository, PaymentRepository
    return PaymentService(
        payment_repo=PaymentRepository(),
        order_repo=OrderRepository(),
    )


@router.post("/verify")
async def verify_payment(
    body: PaymentVerifyRequest,
    db: AsyncSession = Depends(get_db),
    payment_service: PaymentService = Depends(get_payment_service),
) -> ApiResponse:
    """Verify payment after client-side Razorpay checkout callback."""
    payment = await payment_service.verify_payment(
        db,
        razorpay_order_id=body.razorpay_order_id,
        razorpay_payment_id=body.razorpay_payment_id,
        razorpay_signature=body.razorpay_signature,
    )
    return ApiResponse.success(
        data=PaymentResponse.model_validate(payment),
        message="Payment verified successfully",
    )


@router.post("/webhook")
async def payment_webhook(
    request: Request,
    db: AsyncSession = Depends(get_db),
    payment_service: PaymentService = Depends(get_payment_service),
) -> ApiResponse:
    """Handle payment gateway webhooks with HMAC verification."""
    raw_body = await request.body()
    signature = request.headers.get("X-Razorpay-Signature", "")
    payload = json.loads(raw_body)

    logger.info("payment_webhook_received", event=payload.get("event"))

    await payment_service.handle_webhook(db, payload, raw_body, signature)

    return ApiResponse.success(message="Webhook processed")
