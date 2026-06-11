"""Cart schemas."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field


class CartItemAdd(BaseModel):
    """Add item to cart."""

    product_id: UUID
    variant_id: UUID | None = None
    quantity: int = Field(1, gt=0, le=50)


class CartItemUpdate(BaseModel):
    """Update cart item quantity."""

    quantity: int = Field(..., gt=0, le=50)


class CartItemResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    product_id: UUID
    variant_id: UUID | None = None
    quantity: int
    # Populated from product relationship
    product_name: str | None = None
    product_price: Decimal | None = None
    product_image: str | None = None


class CartResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    items: list[CartItemResponse] = []
    total_items: int = 0
    subtotal: Decimal = Decimal("0.00")


class CartMergeRequest(BaseModel):
    """Merge guest cart into authenticated cart after login."""

    session_id: str
