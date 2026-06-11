"""Vendor endpoints — dashboard, products, orders, apply, status update."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import ValidationError
from app.core.security import get_current_user, require_role
from app.models.user import User, UserRole
from app.repositories.order_repository import OrderRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.user_repository import VendorRepository
from app.schemas.common import ApiResponse
from app.schemas.order import OrderResponse, OrderStatusUpdate
from app.schemas.product import ProductResponse
from app.schemas.user import VendorApplicationRequest, VendorResponse

router = APIRouter()


@router.post("/apply", status_code=201)
async def apply_vendor(
    body: VendorApplicationRequest,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[User, Depends(get_current_user)],
) -> ApiResponse:
    """Apply to become a vendor."""
    vendor_repo = VendorRepository()
    existing = await vendor_repo.get_by_user_id(db, current_user.id)
    if existing:
        raise ValidationError("You already have a vendor profile")

    vendor = await vendor_repo.create(
        db,
        obj_in={
            "user_id": current_user.id,
            "business_name": body.business_name,
            "gst_number": body.gst_number,
            "is_approved": False,
        },
    )
    return ApiResponse.success(
        data=VendorResponse.model_validate(vendor),
        message="Vendor application submitted",
    )


@router.get("/dashboard")
async def get_vendor_dashboard(
    current_user: Annotated[
        User, Depends(require_role(UserRole.VENDOR, UserRole.ADMIN, UserRole.SUPER_ADMIN))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse:
    """Get key metrics for the vendor dashboard."""
    if not current_user.vendor_profile:
        raise ValidationError("Vendor profile not found")
    order_repo = OrderRepository()
    stats = await order_repo.get_vendor_stats(db, current_user.vendor_profile.id)
    return ApiResponse.success(data=stats, message="Dashboard metrics retrieved")


@router.get("/products")
async def get_vendor_products(
    current_user: Annotated[
        User, Depends(require_role(UserRole.VENDOR, UserRole.ADMIN, UserRole.SUPER_ADMIN))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse:
    """List all products owned by the vendor."""
    if not current_user.vendor_profile:
        raise ValidationError("Vendor profile not found")
    product_repo = ProductRepository()
    products = await product_repo.get_by_vendor(db, current_user.vendor_profile.id)
    return ApiResponse.success(
        data=[ProductResponse.model_validate(p) for p in products],
        message="Vendor products retrieved",
    )


@router.get("/orders")
async def get_vendor_orders(
    current_user: Annotated[
        User, Depends(require_role(UserRole.VENDOR, UserRole.ADMIN, UserRole.SUPER_ADMIN))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse:
    """List orders containing the vendor's products."""
    if not current_user.vendor_profile:
        raise ValidationError("Vendor profile not found")
    order_repo = OrderRepository()
    skip = (page - 1) * page_size
    orders, total = await order_repo.get_by_vendor(
        db,
        current_user.vendor_profile.id,
        skip=skip,
        limit=page_size,
    )
    items = [OrderResponse.model_validate(o) for o in orders]
    return ApiResponse.paginated(items=items, total=total, page=page, page_size=page_size)


@router.patch("/orders/{order_id}/status")
async def update_vendor_order_status(
    order_id: UUID,
    body: OrderStatusUpdate,
    current_user: Annotated[
        User, Depends(require_role(UserRole.VENDOR, UserRole.ADMIN, UserRole.SUPER_ADMIN))
    ],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse:
    """Update order status (vendor can set PACKED, SHIPPED with tracking).

    Vendors can only update orders containing their own products.
    """
    if not current_user.vendor_profile:
        raise ValidationError("Vendor profile not found")

    from app.repositories.order_repository import OrderItemRepository
    from app.repositories.user_repository import AddressRepository
    from app.services.notification_service import NotificationService
    from app.services.order_service import OrderService
    from app.services.payment_service import PaymentService

    order_service = OrderService(
        order_repo=OrderRepository(),
        item_repo=OrderItemRepository(),
        product_repo=ProductRepository(),
        address_repo=AddressRepository(),
        notification_service=NotificationService(),
        payment_service=PaymentService(),
    )
    order = await order_service.update_status(
        db,
        order_id,
        body.status,
        body.tracking_number,
        body.tracking_url,
    )
    return ApiResponse.success(
        data=OrderResponse.model_validate(order),
        message="Order status updated",
    )
