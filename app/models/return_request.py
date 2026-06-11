"""Return/Refund model for return request flow (WORKFLOW.md §8)."""

import enum
import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class ReturnStatus(str, enum.Enum):
    REQUESTED = "REQUESTED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    PICKUP_SCHEDULED = "PICKUP_SCHEDULED"
    PICKED_UP = "PICKED_UP"
    RECEIVED = "RECEIVED"
    REFUND_INITIATED = "REFUND_INITIATED"
    REFUND_COMPLETE = "REFUND_COMPLETE"
    CLOSED = "CLOSED"


class ReturnRequest(Base, UUIDMixin, TimestampMixin):
    """Customer return request against an order."""

    __tablename__ = "return_requests"

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    status: Mapped[ReturnStatus] = mapped_column(
        String(30), nullable=False, default=ReturnStatus.REQUESTED
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    admin_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    refund_amount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    refund_payment_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True
    )

    order: Mapped["Order"] = relationship("Order")
    items: Mapped[list["ReturnItem"]] = relationship(
        "ReturnItem", back_populates="return_request", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_returns_order", "order_id"),
        Index("ix_returns_user_status", "user_id", "status"),
    )


class ReturnItem(Base, UUIDMixin, TimestampMixin):
    """Individual item within a return request."""

    __tablename__ = "return_items"

    return_request_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("return_requests.id"), nullable=False, index=True
    )
    order_item_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("order_items.id"), nullable=False
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    reason: Mapped[str | None] = mapped_column(Text, nullable=True)

    return_request: Mapped[ReturnRequest] = relationship(
        "ReturnRequest", back_populates="items"
    )


from app.models.order import Order  # noqa: E402, F401
