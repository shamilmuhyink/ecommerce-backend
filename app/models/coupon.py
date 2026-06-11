"""Coupon model for promotion management (WORKFLOW.md §10.2)."""

import enum
import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class CouponType(str, enum.Enum):
    PERCENTAGE = "PERCENTAGE"
    FIXED = "FIXED"


class CouponStatus(str, enum.Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    EXPIRED = "EXPIRED"


class Coupon(Base, UUIDMixin, TimestampMixin):
    """Discount coupon with usage limits and validity window."""

    __tablename__ = "coupons"

    code: Mapped[str] = mapped_column(
        String(50), unique=True, nullable=False, index=True
    )
    coupon_type: Mapped[CouponType] = mapped_column(String(20), nullable=False)
    value: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    min_order_value: Mapped[Decimal] = mapped_column(
        Numeric(12, 2), nullable=False, default=0
    )
    max_discount: Mapped[Decimal | None] = mapped_column(
        Numeric(12, 2), nullable=True
    )
    usage_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    usage_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    per_user_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    status: Mapped[CouponStatus] = mapped_column(
        String(20), nullable=False, default=CouponStatus.ACTIVE
    )
    valid_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    valid_until: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )

    usages: Mapped[list["CouponUsage"]] = relationship(
        "CouponUsage", back_populates="coupon", cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index("ix_coupons_code_status", "code", "status"),
    )


class CouponUsage(Base, UUIDMixin, TimestampMixin):
    """Tracks per-user coupon usage to enforce limits."""

    __tablename__ = "coupon_usages"

    coupon_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("coupons.id"), nullable=False, index=True
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id"), nullable=False, index=True
    )
    order_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("orders.id"), nullable=False
    )

    coupon: Mapped[Coupon] = relationship("Coupon", back_populates="usages")

    __table_args__ = (
        Index("ix_coupon_usage_user", "coupon_id", "user_id"),
    )
