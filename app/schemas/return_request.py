"""Return/Refund schemas."""

from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.return_request import ReturnStatus


class ReturnItemRequest(BaseModel):
    order_item_id: UUID
    quantity: int = Field(..., gt=0)
    reason: str | None = None


class ReturnCreateRequest(BaseModel):
    order_id: UUID
    reason: str = Field(..., min_length=10, max_length=1000)
    items: list[ReturnItemRequest] = Field(..., min_length=1)


class ReturnItemResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    order_item_id: UUID
    quantity: int
    reason: str | None = None


class ReturnResponse(BaseModel):
    model_config = {"from_attributes": True}

    id: UUID
    order_id: UUID
    user_id: UUID
    status: ReturnStatus
    reason: str
    admin_notes: str | None = None
    refund_amount: Decimal | None = None
    items: list[ReturnItemResponse] = []


class ReturnAdminUpdate(BaseModel):
    """Admin approves/rejects a return request."""

    status: ReturnStatus
    admin_notes: str | None = None
    refund_amount: Decimal | None = Field(None, gt=0)
