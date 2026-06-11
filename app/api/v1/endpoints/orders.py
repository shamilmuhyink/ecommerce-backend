"""Order endpoints — create, list, detail, cancel."""

from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.repositories.order_repository import OrderItemRepository, OrderRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.user_repository import AddressRepository
from app.schemas.common import ApiResponse
from app.schemas.order import OrderCancelRequest, OrderCreate, OrderResponse
from app.services.notification_service import NotificationService
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService

router = APIRouter()


def get_order_service() -> OrderService:
    return OrderService(
        order_repo=OrderRepository(),
        item_repo=OrderItemRepository(),
        product_repo=ProductRepository(),
        address_repo=AddressRepository(),
        notification_service=NotificationService(),
        payment_service=PaymentService(),
    )


@router.post("/", status_code=status.HTTP_201_CREATED)
async def create_order(
    order_in: OrderCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
) -> ApiResponse:
    """Place a new order."""
    order = await order_service.create_order(db, current_user.id, order_in)
    return ApiResponse.success(
        data=OrderResponse.model_validate(order),
        message="Order placed successfully",
    )


@router.get("")
async def list_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
) -> ApiResponse:
    """List the current user's orders (paginated)."""
    skip = (page - 1) * page_size
    orders, total = await order_service.get_user_orders(
        db, current_user.id, skip=skip, limit=page_size,
    )
    items = [OrderResponse.model_validate(o) for o in orders]
    return ApiResponse.paginated(items=items, total=total, page=page, page_size=page_size)


@router.get("/{order_id}")
async def get_order(
    order_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
) -> ApiResponse:
    """Get order details (only own orders unless admin/vendor)."""
    order = await order_service.get_order(db, order_id)
    # Authorization: customers can only view their own orders
    from app.models.user import UserRole

    if (
        current_user.role == UserRole.CUSTOMER
        and order.user_id != current_user.id
    ):
        from app.core.exceptions import ValidationError

        raise ValidationError("You can only view your own orders")
    return ApiResponse.success(
        data=OrderResponse.model_validate(order),
        message="Order retrieved",
    )


@router.post("/{order_id}/cancel")
async def cancel_order(
    order_id: UUID,
    body: OrderCancelRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    order_service: OrderService = Depends(get_order_service),
) -> ApiResponse:
    """Cancel a pending or confirmed order."""
    order = await order_service.cancel_order(db, order_id, current_user.id, body.reason)
    return ApiResponse.success(
        data=OrderResponse.model_validate(order),
        message="Order cancelled successfully",
    )
