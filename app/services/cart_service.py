"""Cart service — add/update/remove items, merge guest carts."""

from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.repositories.cart_repository import CartItemRepository, CartRepository
from app.repositories.product_repository import ProductRepository
from app.schemas.cart import CartItemResponse, CartResponse

logger = structlog.get_logger(__name__)


class CartService:
    """Shopping cart lifecycle management."""

    def __init__(
        self,
        cart_repo: CartRepository,
        item_repo: CartItemRepository,
        product_repo: ProductRepository,
    ) -> None:
        self._cart_repo = cart_repo
        self._item_repo = item_repo
        self._product_repo = product_repo

    async def get_cart(
        self, db: AsyncSession, *, user_id: UUID | None = None, session_id: str | None = None
    ) -> CartResponse:
        """Fetch or create cart, computing totals from product data."""
        cart = await self._cart_repo.get_or_create(db, user_id=user_id, session_id=session_id)
        items_response = []
        subtotal = Decimal("0.00")
        total_items = 0

        for item in cart.items:
            product = await self._product_repo.get(db, item.product_id)
            price = product.price if product else Decimal("0.00")
            items_response.append(CartItemResponse(
                id=item.id, product_id=item.product_id, variant_id=item.variant_id,
                quantity=item.quantity, product_name=product.name if product else "Unknown",
                product_price=price, product_image=product.images if product else None,
            ))
            subtotal += price * item.quantity
            total_items += item.quantity

        return CartResponse(
            id=cart.id, items=items_response, total_items=total_items, subtotal=subtotal,
        )

    async def add_item(
        self, db: AsyncSession, *, user_id: UUID | None = None,
        session_id: str | None = None, product_id: UUID,
        variant_id: UUID | None = None, quantity: int = 1,
    ) -> CartResponse:
        """Add an item to cart or increment quantity if it exists."""
        product = await self._product_repo.get(db, product_id)
        if not product:
            raise NotFoundError("Product", str(product_id))
        if product.stock < quantity:
            raise ValidationError(f"Only {product.stock} units available")

        cart = await self._cart_repo.get_or_create(db, user_id=user_id, session_id=session_id)
        existing = await self._item_repo.get_existing_item(db, cart.id, product_id, variant_id)

        if existing:
            new_qty = existing.quantity + quantity
            if new_qty > product.stock:
                raise ValidationError(f"Only {product.stock} units available")
            await self._item_repo.update(db, db_obj=existing, obj_in={"quantity": new_qty})
        else:
            await self._item_repo.create(db, obj_in={
                "cart_id": cart.id, "product_id": product_id,
                "variant_id": variant_id, "quantity": quantity,
            })
        logger.info("cart_item_added", product_id=str(product_id), quantity=quantity)
        return await self.get_cart(db, user_id=user_id, session_id=session_id)

    async def update_item(
        self, db: AsyncSession, item_id: UUID, quantity: int,
        *, user_id: UUID | None = None, session_id: str | None = None,
    ) -> CartResponse:
        """Update quantity of a cart item."""
        item = await self._item_repo.get(db, item_id)
        if not item:
            raise NotFoundError("CartItem", str(item_id))
        await self._item_repo.update(db, db_obj=item, obj_in={"quantity": quantity})
        return await self.get_cart(db, user_id=user_id, session_id=session_id)

    async def remove_item(
        self, db: AsyncSession, item_id: UUID,
        *, user_id: UUID | None = None, session_id: str | None = None,
    ) -> CartResponse:
        """Remove an item from the cart."""
        await self._item_repo.remove(db, id=item_id)
        return await self.get_cart(db, user_id=user_id, session_id=session_id)

    async def clear_cart(
        self, db: AsyncSession, *, user_id: UUID | None = None, session_id: str | None = None,
    ) -> None:
        """Remove all items from the cart."""
        cart = await self._cart_repo.get_or_create(db, user_id=user_id, session_id=session_id)
        await self._item_repo.clear_cart(db, cart.id)

    async def merge_guest_cart(self, db: AsyncSession, user_id: UUID, session_id: str) -> CartResponse:
        """Merge a guest session cart into an authenticated user's cart."""
        guest_cart = await self._cart_repo.get_by_session(db, session_id)
        if not guest_cart or not guest_cart.items:
            return await self.get_cart(db, user_id=user_id)

        user_cart = await self._cart_repo.get_or_create(db, user_id=user_id)
        for item in guest_cart.items:
            existing = await self._item_repo.get_existing_item(
                db, user_cart.id, item.product_id, item.variant_id
            )
            if existing:
                new_qty = existing.quantity + item.quantity
                await self._item_repo.update(db, db_obj=existing, obj_in={"quantity": new_qty})
            else:
                await self._item_repo.create(db, obj_in={
                    "cart_id": user_cart.id, "product_id": item.product_id,
                    "variant_id": item.variant_id, "quantity": item.quantity,
                })

        await self._item_repo.clear_cart(db, guest_cart.id)
        await self._cart_repo.remove(db, id=guest_cart.id)
        logger.info("cart_merged", user_id=str(user_id), session_id=session_id)
        return await self.get_cart(db, user_id=user_id)
