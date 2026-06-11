"""Coupon schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.coupon import CouponStatus, CouponType


class CouponCreate(BaseModel):
    code: str = Field(..., min_length=3, max_length=50, pattern=r"^[A-Z0-9_-]+$")
    coupon_type: CouponType
    value: Decimal = Field(..., gt=0)
    min_order_value: Decimal = Field(Decimal("0"), ge=0)
    max_discount: Decimal | None = Field(None, gt=0)
    usage_limit: int = Field(0, ge=0)
    per_user_limit: int = Field(1, ge=1)
    valid_from: datetime | None = None
    valid_until: datetime


class CouponUpdate(BaseModel):
    status: CouponStatus | None = None
    usage_limit: int | None = Field(None, ge=0)
    valid_until: datetime | None = None


class CouponValidateRequest(BaseModel):
    code: str
    order_subtotal: Decimal = Field(..., gt=0)


class CouponValidateResponse(BaseModel):
    valid: bool
    discount_amount: Decimal = Decimal("0.00")
    message: str = ""


class CouponResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    code: str
    coupon_type: CouponType
    value: Decimal
    min_order_value: Decimal
    max_discount: Decimal | None = None
    usage_limit: int
    usage_count: int
    per_user_limit: int
    status: CouponStatus
    valid_from: datetime
    valid_until: datetime
