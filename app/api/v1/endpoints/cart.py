"""Cart endpoints — view, add, update, remove, merge."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.repositories.cart_repository import CartItemRepository, CartRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.cart import CartItemAdd, CartItemUpdate, CartMergeRequest, CartResponse
from app.schemas.common import ApiResponse
from app.services.cart_service import CartService

router = APIRouter()


def get_cart_service() -> CartService:
    return CartService(CartRepository(), CartItemRepository(), ProductRepository())


@router.get("")
async def get_cart(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    cart_service: CartService = Depends(get_cart_service),
) -> ApiResponse:
    """Get the current user's cart."""
    cart = await cart_service.get_cart(db, user_id=current_user.id)
    return ApiResponse.success(data=cart, message="Cart retrieved")


@router.post("/items")
async def add_to_cart(
    body: CartItemAdd,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    cart_service: CartService = Depends(get_cart_service),
) -> ApiResponse:
    """Add an item to the cart."""
    cart = await cart_service.add_item(
        db, user_id=current_user.id,
        product_id=body.product_id, variant_id=body.variant_id,
        quantity=body.quantity,
    )
    return ApiResponse.success(data=cart, message="Item added to cart")


@router.patch("/items/{item_id}")
async def update_cart_item(
    item_id: UUID,
    body: CartItemUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    cart_service: CartService = Depends(get_cart_service),
) -> ApiResponse:
    """Update the quantity of a cart item."""
    cart = await cart_service.update_item(
        db, item_id, body.quantity, user_id=current_user.id,
    )
    return ApiResponse.success(data=cart, message="Cart item updated")


@router.delete("/items/{item_id}")
async def remove_cart_item(
    item_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    cart_service: CartService = Depends(get_cart_service),
) -> ApiResponse:
    """Remove an item from the cart."""
    cart = await cart_service.remove_item(db, item_id, user_id=current_user.id)
    return ApiResponse.success(data=cart, message="Item removed from cart")


@router.post("/merge")
async def merge_cart(
    body: CartMergeRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    cart_service: CartService = Depends(get_cart_service),
) -> ApiResponse:
    """Merge guest cart into authenticated cart after login."""
    cart = await cart_service.merge_guest_cart(db, current_user.id, body.session_id)
    return ApiResponse.success(data=cart, message="Cart merged successfully")


@router.delete("/", status_code=204)
async def clear_cart(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    cart_service: CartService = Depends(get_cart_service),
) -> None:
    """Remove all items from the cart."""
    await cart_service.clear_cart(db, user_id=current_user.id)
