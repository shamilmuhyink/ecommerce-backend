"""Order and OrderItem models."""

import enum
import uuid
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class OrderStatus(str, enum.Enum):
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PACKED = "PACKED"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    RETURN_REQUESTED = "RETURN_REQUESTED"
    RETURN_APPROVED = "RETURN_APPROVED"
    REFUND_INITIATED = "REFUND_INITIATED"
    REFUND_COMPLETE = "REFUND_COMPLETE"
    CLOSED = "CLOSED"


# Valid status transitions per WORKFLOW.md §5.1
ORDER_TRANSITIONS: dict[OrderStatus, set[OrderStatus]] = {
    OrderStatus.PENDING: {OrderStatus.CONFIRMED, OrderStatus.CANCELLED},
    OrderStatus.CONFIRMED: {OrderStatus.PACKED, OrderStatus.CANCELLED},
    OrderStatus.PACKED: {OrderStatus.SHIPPED, OrderStatus.CANCELLED},
    OrderStatus.SHIPPED: {OrderStatus.DELIVERED},
    OrderStatus.DELIVERED: {OrderStatus.RETURN_REQUESTED, OrderStatus.CLOSED},
    OrderStatus.RETURN_REQUESTED: {OrderStatus.RETURN_APPROVED, OrderStatus.CLOSED},
    OrderStatus.RETURN_APPROVED: {OrderStatus.REFUND_INITIATED},
    OrderStatus.REFUND_INITIATED: {OrderStatus.REFUND_COMPLETE},
    OrderStatus.REFUND_COMPLETE: {OrderStatus.CLOSED},
    OrderStatus.CANCELLED: set(),
    OrderStatus.CLOSED: set(),
}


class Order(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "orders"

    order_number: Mapped[str] = mapped_column(
        String(32), unique=True, nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    status: Mapped[OrderStatus] = mapped_column(
        String(20), nullable=False, default=OrderStatus.PENDING
    )

    # Pricing
    subtotal: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    discount: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    tax: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False, default=0)
    shipping_charge: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    # Coupon
    coupon_code: Mapped[str | None] = mapped_column(String(50), nullable=True)

    # Shipping address snapshot (immutable copy at order time)
    shipping_name: Mapped[str] = mapped_column(String(255), nullable=False)
    shipping_phone: Mapped[str | None] = mapped_column(String(20), nullable=True)
    shipping_line1: Mapped[str] = mapped_column(String(255), nullable=False)
    shipping_line2: Mapped[str | None] = mapped_column(String(255), nullable=True)
    shipping_city: Mapped[str] = mapped_column(String(100), nullable=False)
    shipping_state: Mapped[str] = mapped_column(String(100), nullable=False)
    shipping_postal_code: Mapped[str] = mapped_column(String(20), nullable=False)
    shipping_country: Mapped[str] = mapped_column(String(100), nullable=False)

    # Tracking
    tracking_number: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tracking_url: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Relationships
    user: Mapped["User"] = relationship("User")
    items: Mapped[list["OrderItem"]] = relationship(
        "OrderItem",
        back_populates="order",
        cascade="all, delete-orphan",
    )
    payment: Mapped["Payment"] = relationship(
        "Payment", back_populates="order", uselist=False
    )

    __table_args__ = (
        Index("ix_orders_user_status", "user_id", "status"),
        Index("ix_orders_number", "order_number"),
    )

    def can_transition_to(self, new_status: OrderStatus) -> bool:
        """Check if a status transition is valid."""
        return new_status in ORDER_TRANSITIONS.get(self.status, set())


class OrderItem(Base, UUIDMixin, TimestampMixin):
    __tablename__ = "order_items"

    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id"), nullable=False, index=True
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_variants.id"), nullable=True
    )
    product_name: Mapped[str] = mapped_column(String(200), nullable=False)
    product_sku: Mapped[str] = mapped_column(String(50), nullable=False)

    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    price: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False
    )  # Price at time of order
    total: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)

    product: Mapped["Product"] = relationship("Product")
    variant: Mapped["ProductVariant"] = relationship("ProductVariant")
    order: Mapped[Order] = relationship("Order", back_populates="items")

    __table_args__ = (Index("ix_order_items_order", "order_id"),)


from app.models.payment import Payment  # noqa: E402, F401
from app.models.product import Product, ProductVariant  # noqa: E402, F401
from app.models.user import User  # noqa: E402, F401