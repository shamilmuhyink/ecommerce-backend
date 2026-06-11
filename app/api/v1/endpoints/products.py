"""Product endpoints — list, detail, create, update, search."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user, require_role
from app.models.user import User, UserRole
from app.repositories.product_repository import (
    CategoryRepository,
    ProductRepository,
    ProductVariantRepository,
)
from app.schemas.common import ApiResponse
from app.schemas.product import (
    CategoryResponse,
    ProductCreate,
    ProductResponse,
    ProductUpdate,
)
from app.services.product_service import ProductService

router = APIRouter()


def get_product_service() -> ProductService:
    return ProductService(ProductRepository(), ProductVariantRepository(), CategoryRepository())


@router.get("")
async def list_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    product_service: Annotated[ProductService, Depends(get_product_service)],
    category_id: Annotated[UUID | None, Query()] = None,
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse:
    """List active products (paginated)."""
    skip = (page - 1) * page_size
    products, total = await product_service.list_active_products(db, category_id=category_id, skip=skip, limit=page_size)
    items = [ProductResponse.model_validate(p) for p in products]
    return ApiResponse.paginated(items=items, total=total, page=page, page_size=page_size)


@router.get("/search")
async def search_products(
    db: Annotated[AsyncSession, Depends(get_db)],
    product_service: Annotated[ProductService, Depends(get_product_service)],
    q: Annotated[str, Query(min_length=2)],
    page: Annotated[int, Query(ge=1)] = 1,
    page_size: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse:
    """Search products by name or description."""
    skip = (page - 1) * page_size
    products, total = await product_service.search_products(db, q, skip=skip, limit=page_size)
    items = [ProductResponse.model_validate(p) for p in products]
    return ApiResponse.paginated(items=items, total=total, page=page, page_size=page_size)


@router.get("/categories")
async def list_categories(
    db: Annotated[AsyncSession, Depends(get_db)],
) -> ApiResponse:
    """List all product categories."""
    repo = CategoryRepository()
    categories = await repo.get_all(db)
    return ApiResponse.success(
        data=[CategoryResponse.model_validate(c) for c in categories],
        message="Categories retrieved",
    )


@router.get("/{product_id}")
async def get_product(
    product_id: UUID,
    db: Annotated[AsyncSession, Depends(get_db)],
    product_service: Annotated[ProductService, Depends(get_product_service)],
) -> ApiResponse:
    """Get a specific product by ID."""
    product = await product_service.get_product(db, product_id)
    return ApiResponse.success(
        data=ProductResponse.model_validate(product),
        message="Product retrieved",
    )


@router.post("", status_code=status.HTTP_201_CREATED)
async def create_product(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        User, Depends(require_role(UserRole.VENDOR, UserRole.ADMIN, UserRole.SUPER_ADMIN))
    ],
    product_service: Annotated[ProductService, Depends(get_product_service)],
    product_in: ProductCreate,
) -> ApiResponse:
    """Create a new product (Vendor only)."""
    from app.core.exceptions import ValidationError

    if not current_user.vendor_profile:
        raise ValidationError("User has no vendor profile")
    product = await product_service.create_product(db, current_user.vendor_profile.id, product_in)
    return ApiResponse.success(
        data=ProductResponse.model_validate(product),
        message="Product created successfully",
    )


@router.patch("/{product_id}")
async def update_product(
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[
        User, Depends(require_role(UserRole.VENDOR, UserRole.ADMIN, UserRole.SUPER_ADMIN))
    ],
    product_service: Annotated[ProductService, Depends(get_product_service)],
    product_id: UUID,
    product_in: ProductUpdate,
) -> ApiResponse:
    """Update a product (vendor can only update their own)."""
    from app.core.exceptions import ValidationError

    if not current_user.vendor_profile:
        raise ValidationError("User has no vendor profile")
    product = await product_service.update_product(
        db,
        product_id,
        current_user.vendor_profile.id,
        product_in,
    )
    return ApiResponse.success(
        data=ProductResponse.model_validate(product),
        message="Product updated successfully",
    )
