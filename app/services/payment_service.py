"""Payment service — gateway integration and webhook handling."""

import hashlib
import hmac
import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, PaymentVerificationError
from app.models.order import Order, OrderStatus
from app.models.payment import Payment, PaymentStatus
from app.repositories.order_repository import OrderRepository, PaymentRepository
from app.schemas.payment import PaymentInitiateResponse

logger = structlog.get_logger(__name__)


class PaymentService:
    """Payment initiation, verification, and webhook handling."""

    def __init__(
        self,
        payment_repo: PaymentRepository | None = None,
        order_repo: OrderRepository | None = None,
    ) -> None:
        self._payment_repo = payment_repo or PaymentRepository()
        self._order_repo = order_repo or OrderRepository()
        self._settings = get_settings()

    async def initiate_payment(self, order: Order, db: AsyncSession) -> PaymentInitiateResponse:
        """Create payment record and initiate with gateway."""
        gateway_order_id = f"order_{uuid.uuid4().hex[:12]}"
        payment = Payment(
            order_id=order.id, gateway="RAZORPAY",
            gateway_order_id=gateway_order_id,
            amount=order.total, currency="INR", status=PaymentStatus.PENDING,
        )
        db.add(payment)
        await db.flush()
        logger.info("payment_initiated", order_id=str(order.id), gateway_order_id=gateway_order_id)
        return PaymentInitiateResponse(
            gateway_order_id=gateway_order_id, amount=order.total,
            currency="INR", key=self._settings.RAZORPAY_KEY_ID,
        )

    async def verify_payment(
        self, db: AsyncSession, razorpay_order_id: str,
        razorpay_payment_id: str, razorpay_signature: str,
    ) -> Payment:
        """Verify Razorpay payment signature from client callback."""
        payment = await self._payment_repo.get_by_gateway_order_id(db, razorpay_order_id)
        if not payment:
            raise NotFoundError("Payment", razorpay_order_id)

        message = f"{razorpay_order_id}|{razorpay_payment_id}"
        expected = hmac.new(
            self._settings.RAZORPAY_KEY_SECRET.encode(), message.encode(), hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, razorpay_signature):
            logger.error("payment_verification_failed", gateway_order_id=razorpay_order_id)
            raise PaymentVerificationError()

        payment.gateway_payment_id = razorpay_payment_id
        payment.gateway_signature = razorpay_signature
        payment.status = PaymentStatus.SUCCESS
        db.add(payment)

        order = await self._order_repo.get(db, payment.order_id)
        if order:
            order.status = OrderStatus.CONFIRMED
            db.add(order)
        await db.commit()
        logger.info("payment_verified", gateway_order_id=razorpay_order_id)
        return payment

    async def handle_webhook(
        self, db: AsyncSession, payload: dict, raw_body: bytes, signature: str,
    ) -> None:
        """Handle Razorpay webhook with HMAC verification."""
        expected = hmac.new(
            self._settings.RAZORPAY_WEBHOOK_SECRET.encode(), raw_body, hashlib.sha256,
        ).hexdigest()
        if not hmac.compare_digest(expected, signature):
            raise PaymentVerificationError()

        event = payload.get("event", "")
        logger.info("webhook_received", event=event)

        if event == "payment.captured":
            entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
            gw_order_id = entity.get("order_id")
            if gw_order_id:
                payment = await self._payment_repo.get_by_gateway_order_id(db, gw_order_id)
                if payment:
                    payment.gateway_payment_id = entity.get("id")
                    payment.status = PaymentStatus.SUCCESS
                    db.add(payment)
                    order = await self._order_repo.get(db, payment.order_id)
                    if order and order.status == OrderStatus.PENDING:
                        order.status = OrderStatus.CONFIRMED
                        db.add(order)
                    await db.commit()
        elif event == "payment.failed":
            entity = payload.get("payload", {}).get("payment", {}).get("entity", {})
            gw_order_id = entity.get("order_id")
            if gw_order_id:
                payment = await self._payment_repo.get_by_gateway_order_id(db, gw_order_id)
                if payment:
                    payment.status = PaymentStatus.FAILED
                    payment.failure_reason = entity.get("error_description", "Payment failed")
                    db.add(payment)
                    await db.commit()
