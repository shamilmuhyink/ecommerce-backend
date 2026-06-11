"""Order schemas."""

from datetime import datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.order import OrderStatus


class OrderItemBase(BaseModel):
    product_id: UUID
    variant_id: UUID | None = None
    quantity: int = Field(..., gt=0)


class OrderItemResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    product_id: UUID
    variant_id: UUID | None = None
    product_name: str
    product_sku: str
    quantity: int
    price: Decimal
    total: Decimal


class OrderCreate(BaseModel):
    items: list[OrderItemBase] = Field(..., min_length=1)
    shipping_address_id: UUID
    coupon_code: str | None = None


class OrderResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    order_number: str
    status: OrderStatus
    subtotal: Decimal
    discount: Decimal
    tax: Decimal
    shipping_charge: Decimal
    total: Decimal
    coupon_code: str | None = None
    tracking_number: str | None = None
    tracking_url: str | None = None
    items: list[OrderItemResponse] = []
    created_at: datetime | None = None


class OrderCancelRequest(BaseModel):
    reason: str = Field(..., min_length=5, max_length=500)


class OrderStatusUpdate(BaseModel):
    """Admin/vendor status update."""

    status: OrderStatus
    tracking_number: str | None = None
    tracking_url: str | None = None
