"""Admin endpoints — product approval, order management, user management,
vendor approval, coupon CRUD, return management, and platform dashboard.

All endpoints require ADMIN or SUPER_ADMIN role.
"""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.exceptions import NotFoundError
from app.core.security import require_role
from app.models.order import OrderStatus
from app.models.product import ProductStatus
from app.models.user import User, UserRole, UserStatus
from app.repositories.coupon_repository import CouponRepository, CouponUsageRepository
from app.repositories.order_repository import OrderItemRepository, OrderRepository
from app.repositories.product_repository import (
    CategoryRepository,
    ProductRepository,
    ProductVariantRepository,
)
from app.repositories.return_repository import ReturnItemRepository, ReturnRequestRepository
from app.repositories.user_repository import AddressRepository, UserRepository, VendorRepository
from app.schemas.common import ApiResponse
from app.schemas.coupon import CouponCreate, CouponResponse, CouponUpdate
from app.schemas.order import OrderResponse, OrderStatusUpdate
from app.schemas.product import CategoryCreate, CategoryResponse, ProductResponse
from app.schemas.return_request import ReturnAdminUpdate, ReturnResponse
from app.schemas.user import UserResponse, VendorResponse
from app.services.notification_service import NotificationService
from app.services.order_service import OrderService
from app.services.payment_service import PaymentService
from app.services.product_service import ProductService
from app.services.return_service import ReturnService

router = APIRouter()

AdminUser = require_role(UserRole.ADMIN, UserRole.SUPER_ADMIN)


def get_product_service() -> ProductService:
    """Build ProductService with its dependencies."""
    return ProductService(ProductRepository(), ProductVariantRepository(), CategoryRepository())


def get_order_service() -> OrderService:
    """Build OrderService with its dependencies."""
    return OrderService(
        order_repo=OrderRepository(),
        item_repo=OrderItemRepository(),
        product_repo=ProductRepository(),
        address_repo=AddressRepository(),
        notification_service=NotificationService(),
        payment_service=PaymentService(),
    )


def get_return_service() -> ReturnService:
    """Build ReturnService with its dependencies."""
    return ReturnService(
        return_repo=ReturnRequestRepository(),
        return_item_repo=ReturnItemRepository(),
        order_repo=OrderRepository(),
        notification_service=NotificationService(),
    )


# ---------------------------------------------------------------------------
# Product moderation
# ---------------------------------------------------------------------------


@router.get("/products/pending")
async def get_pending_products(
    current_user: User = Depends(AdminUser),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """List all products pending approval."""
    repo = ProductRepository()
    products = await repo.get_by_status(db, ProductStatus.PENDING)
    return ApiResponse.success(
        data=[ProductResponse.model_validate(p) for p in products],
        message="Pending products retrieved",
    )


@router.patch("/products/{product_id}/approve")
async def approve_product(
    product_id: UUID,
    current_user: User = Depends(AdminUser),
    db: AsyncSession = Depends(get_db),
    product_service: ProductService = Depends(get_product_service),
) -> ApiResponse:
    """Approve a vendor product listing."""
    product = await product_service.approve_product(db, product_id)
    return ApiResponse.success(
        data=ProductResponse.model_validate(product),
        message="Product approved",
    )


@router.patch("/products/{product_id}/reject")
async def reject_product(
    product_id: UUID,
    reason: str = Query(..., min_length=5),
    current_user: User = Depends(AdminUser),
    db: AsyncSession = Depends(get_db),
    product_service: ProductService = Depends(get_product_service),
) -> ApiResponse:
    """Reject a vendor product listing with reason."""
    await product_service.reject_product(db, product_id, reason)
    return ApiResponse.success(message=f"Product {product_id} rejected")


# ---------------------------------------------------------------------------
# Order management
# ---------------------------------------------------------------------------


@router.patch("/orders/{order_id}/status")
async def update_order_status(
    order_id: UUID,
    body: OrderStatusUpdate,
    current_user: User = Depends(AdminUser),
    db: AsyncSession = Depends(get_db),
    order_service: OrderService = Depends(get_order_service),
) -> ApiResponse:
    """Update order status with optional tracking info."""
    order = await order_service.update_status(
        db, order_id, body.status, body.tracking_number, body.tracking_url,
    )
    return ApiResponse.success(
        data=OrderResponse.model_validate(order),
        message="Order status updated",
    )


@router.get("/orders")
async def list_all_orders(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: OrderStatus | None = None,
    current_user: User = Depends(AdminUser),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """List all orders with optional status filter (admin only)."""
    order_repo = OrderRepository()
    skip = (page - 1) * page_size
    from sqlalchemy import select, func
    from sqlalchemy.orm import selectinload
    from app.models.order import Order

    base = select(Order)
    if status:
        base = base.where(Order.status == status)

    count_query = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_query)).scalar_one()

    query = (
        base.order_by(Order.created_at.desc())
        .offset(skip)
        .limit(page_size)
        .options(selectinload(Order.items))
    )
    result = await db.execute(query)
    orders = list(result.scalars().all())

    items = [OrderResponse.model_validate(o) for o in orders]
    return ApiResponse.paginated(items=items, total=total, page=page, page_size=page_size)


# ---------------------------------------------------------------------------
# Category management
# ---------------------------------------------------------------------------


@router.post("/categories", status_code=201)
async def create_category(
    body: CategoryCreate,
    current_user: Annotated[User, Depends(AdminUser)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse:
    """Create a new product category."""
    repo = CategoryRepository()
    category = await repo.create(db, obj_in=body.model_dump())
    return ApiResponse.success(
        data=CategoryResponse.model_validate(category),
        message="Category created successfully",
    )


# ---------------------------------------------------------------------------
# Coupon management
# ---------------------------------------------------------------------------


@router.post("/coupons", status_code=201)
async def create_coupon(
    body: CouponCreate,
    current_user: User = Depends(AdminUser),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Create a new coupon."""
    repo = CouponRepository()
    coupon = await repo.create(db, obj_in=body.model_dump())
    return ApiResponse.success(
        data=CouponResponse.model_validate(coupon),
        message="Coupon created successfully",
    )


@router.get("/coupons")
async def list_coupons(
    current_user: User = Depends(AdminUser),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """List all coupons."""
    repo = CouponRepository()
    coupons = await repo.get_multi(db, limit=200)
    return ApiResponse.success(
        data=[CouponResponse.model_validate(c) for c in coupons],
        message="Coupons retrieved",
    )


@router.patch("/coupons/{coupon_id}")
async def update_coupon(
    coupon_id: UUID,
    body: CouponUpdate,
    current_user: User = Depends(AdminUser),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Update coupon status or limits."""
    repo = CouponRepository()
    coupon = await repo.get(db, coupon_id)
    if not coupon:
        raise NotFoundError("Coupon", str(coupon_id))
    updated = await repo.update(db, db_obj=coupon, obj_in=body.model_dump(exclude_unset=True))
    return ApiResponse.success(
        data=CouponResponse.model_validate(updated),
        message="Coupon updated successfully",
    )


# ---------------------------------------------------------------------------
# User management
# ---------------------------------------------------------------------------


@router.get("/users")
async def list_users(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    role: UserRole | None = None,
    current_user: User = Depends(AdminUser),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """List all users with optional role filter."""
    from sqlalchemy import select, func
    from app.models.user import User as UserModel

    base = select(UserModel)
    if role:
        base = base.where(UserModel.role == role)

    count_query = select(func.count()).select_from(base.subquery())
    total = (await db.execute(count_query)).scalar_one()

    skip = (page - 1) * page_size
    query = base.order_by(UserModel.created_at.desc()).offset(skip).limit(page_size)
    result = await db.execute(query)
    users = list(result.scalars().all())

    items = [UserResponse.model_validate(u) for u in users]
    return ApiResponse.paginated(items=items, total=total, page=page, page_size=page_size)


@router.patch("/users/{user_id}/status")
async def update_user_status(
    user_id: UUID,
    status: UserStatus = Query(...),
    current_user: User = Depends(AdminUser),
    db: AsyncSession = Depends(get_db),
) -> UserResponse:
    """Suspend, activate, or delete a user account."""
    user_repo = UserRepository()
    user = await user_repo.get(db, user_id)
    if not user:
        raise NotFoundError("User", str(user_id))
    updated = await user_repo.update(db, db_obj=user, obj_in={"status": status})
    return ApiResponse.success(
        data=UserResponse.model_validate(updated),
        message="User status updated",
    )


# ---------------------------------------------------------------------------
# Vendor management
# ---------------------------------------------------------------------------


@router.get("/vendors/pending")
async def get_pending_vendors(
    current_user: User = Depends(AdminUser),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """List all vendors pending approval."""
    vendor_repo = VendorRepository()
    vendors = await vendor_repo.get_pending_vendors(db)
    return ApiResponse.success(
        data=[VendorResponse.model_validate(v) for v in vendors],
        message="Pending vendors retrieved",
    )


@router.patch("/vendors/{vendor_id}/approve")
async def approve_vendor(
    vendor_id: UUID,
    current_user: User = Depends(AdminUser),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Approve a vendor application and upgrade user role to VENDOR."""
    vendor_repo = VendorRepository()
    user_repo = UserRepository()

    vendor = await vendor_repo.get(db, vendor_id)
    if not vendor:
        raise NotFoundError("Vendor", str(vendor_id))

    await vendor_repo.update(db, db_obj=vendor, obj_in={"is_approved": True})
    user = await user_repo.get(db, vendor.user_id)
    if user:
        await user_repo.update(db, db_obj=user, obj_in={"role": UserRole.VENDOR})

    return ApiResponse.success(
        data=VendorResponse.model_validate(vendor),
        message="Vendor approved",
    )


@router.patch("/vendors/{vendor_id}/reject")
async def reject_vendor(
    vendor_id: UUID,
    reason: str = Query(..., min_length=5),
    current_user: User = Depends(AdminUser),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Reject a vendor application."""
    vendor_repo = VendorRepository()
    vendor = await vendor_repo.get(db, vendor_id)
    if not vendor:
        raise NotFoundError("Vendor", str(vendor_id))

    await vendor_repo.remove(db, id=vendor_id)
    return ApiResponse.success(message=f"Vendor application rejected: {reason}")


# ---------------------------------------------------------------------------
# Return management
# ---------------------------------------------------------------------------


@router.get("/returns/pending")
async def get_pending_returns(
    current_user: User = Depends(AdminUser),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """List all return requests pending review."""
    return_repo = ReturnRequestRepository()
    returns = await return_repo.get_pending(db)
    return ApiResponse.success(
        data=[ReturnResponse.model_validate(r) for r in returns],
        message="Pending returns retrieved",
    )


@router.patch("/returns/{return_id}")
async def update_return_request(
    return_id: UUID,
    body: ReturnAdminUpdate,
    current_user: User = Depends(AdminUser),
    db: AsyncSession = Depends(get_db),
    return_service: ReturnService = Depends(get_return_service),
) -> ApiResponse:
    """Approve or reject a return request."""
    return_request = await return_service.admin_update_return(
        db, return_id, body.status, body.admin_notes, body.refund_amount,
    )
    return ApiResponse.success(
        data=ReturnResponse.model_validate(return_request),
        message="Return request updated",
    )


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------


@router.get("/dashboard")
async def get_admin_dashboard(
    current_user: User = Depends(AdminUser),
    db: AsyncSession = Depends(get_db),
) -> ApiResponse:
    """Get platform-level KPI dashboard metrics."""
    from sqlalchemy import select, func
    from app.models.order import Order
    from app.models.user import User as UserModel
    from app.models.product import Product

    user_count = (await db.execute(select(func.count(UserModel.id)))).scalar_one()
    order_count = (await db.execute(select(func.count(Order.id)))).scalar_one()
    revenue = (
        await db.execute(
            select(func.coalesce(func.sum(Order.total), 0)).where(
                Order.status.in_([OrderStatus.DELIVERED, OrderStatus.CLOSED])
            )
        )
    ).scalar_one()
    product_count = (await db.execute(select(func.count(Product.id)))).scalar_one()
    pending_count = (
        await db.execute(
            select(func.count(Order.id)).where(Order.status == OrderStatus.PENDING)
        )
    ).scalar_one()

    from app.models.return_request import ReturnRequest, ReturnStatus
    pending_returns = (
        await db.execute(
            select(func.count(ReturnRequest.id)).where(
                ReturnRequest.status == ReturnStatus.REQUESTED
            )
        )
    ).scalar_one()

    return ApiResponse.success(
        data={
            "total_users": user_count,
            "total_orders": order_count,
            "total_revenue": str(revenue),
            "total_products": product_count,
            "pending_orders": pending_count,
            "pending_returns": pending_returns,
        },
        message="Dashboard metrics retrieved",
    )
