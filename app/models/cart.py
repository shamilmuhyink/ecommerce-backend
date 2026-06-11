"""Cart model for server-side cart persistence (WORKFLOW.md §4.3)."""

import uuid
from decimal import Decimal

from sqlalchemy import ForeignKey, Index, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Cart(Base, UUIDMixin, TimestampMixin):
    """Shopping cart — one per user. Guest carts use session_id."""

    __tablename__ = "carts"

    user_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=True, unique=True, index=True
    )
    session_id: Mapped[str | None] = mapped_column(
        String(100), nullable=True, unique=True, index=True
    )

    items: Mapped[list["CartItem"]] = relationship(
        "CartItem",
        back_populates="cart",
        cascade="all, delete-orphan",
    )

    __table_args__ = (Index("ix_carts_user", "user_id"),)


class CartItem(Base, UUIDMixin, TimestampMixin):
    """Individual line item in a shopping cart."""

    __tablename__ = "cart_items"

    cart_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("carts.id"), nullable=False, index=True
    )
    product_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("products.id"), nullable=False
    )
    variant_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("product_variants.id"), nullable=True
    )
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)

    cart: Mapped[Cart] = relationship("Cart", back_populates="items")
    product: Mapped["Product"] = relationship("Product")
    variant: Mapped["ProductVariant"] = relationship("ProductVariant")

    __table_args__ = (
        Index("ix_cart_items_cart", "cart_id"),
        Index("ix_cart_items_product", "cart_id", "product_id", "variant_id", unique=True),
    )


from app.models.product import Product, ProductVariant  # noqa: E402, F401
