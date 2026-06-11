"""Payment model — separated from order.py per AGENTS.md §1 structure."""

import enum
import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class PaymentStatus(str, enum.Enum):
    PENDING = "PENDING"
    SUCCESS = "SUCCESS"
    FAILED = "FAILED"
    REFUNDED = "REFUNDED"


class PaymentGateway(str, enum.Enum):
    RAZORPAY = "RAZORPAY"
    STRIPE = "STRIPE"


class Payment(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "payments"

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id"), nullable=False, unique=True, index=True
    )
    gateway: Mapped[str] = mapped_column(String(50), nullable=False)
    gateway_order_id: Mapped[str] = mapped_column(String(100), nullable=False)
    gateway_payment_id: Mapped[str | None] = mapped_column(String(100), nullable=True)
    gateway_signature: Mapped[str | None] = mapped_column(String(255), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="INR")
    status: Mapped[PaymentStatus] = mapped_column(
        String(20), nullable=False, default=PaymentStatus.PENDING
    )
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    order: Mapped["Order"] = relationship("Order", back_populates="payment")

    __table_args__ = (
        Index("ix_payments_order", "order_id"),
        Index("ix_payments_gateway_order", "gateway_order_id"),
    )


from app.models.order import Order  # noqa: E402, F401
