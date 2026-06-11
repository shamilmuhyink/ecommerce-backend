"""Cart repository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.cart import Cart, CartItem
from app.repositories.base import BaseRepository


class CartRepository(BaseRepository[Cart]):
    def __init__(self) -> None:
        super().__init__(Cart)

    async def get_by_user(self, db: AsyncSession, user_id: UUID) -> Cart | None:
        """Fetch cart for an authenticated user."""
        query = (
            select(Cart)
            .where(Cart.user_id == user_id)
            .options(selectinload(Cart.items))
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_session(self, db: AsyncSession, session_id: str) -> Cart | None:
        """Fetch cart for a guest session."""
        query = (
            select(Cart)
            .where(Cart.session_id == session_id)
            .options(selectinload(Cart.items))
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_or_create(
        self, db: AsyncSession, *, user_id: UUID | None = None, session_id: str | None = None
    ) -> Cart:
        """Get existing cart or create a new one."""
        if user_id:
            cart = await self.get_by_user(db, user_id)
        elif session_id:
            cart = await self.get_by_session(db, session_id)
        else:
            raise ValueError("Either user_id or session_id must be provided")

        if not cart:
            data = {}
            if user_id:
                data["user_id"] = user_id
            if session_id:
                data["session_id"] = session_id
            cart = await self.create(db, obj_in=data)
            # Re-fetch with relationships
            if user_id:
                cart = await self.get_by_user(db, user_id)
            else:
                cart = await self.get_by_session(db, session_id)

        return cart


class CartItemRepository(BaseRepository[CartItem]):
    def __init__(self) -> None:
        super().__init__(CartItem)

    async def get_existing_item(
        self,
        db: AsyncSession,
        cart_id: UUID,
        product_id: UUID,
        variant_id: UUID | None,
    ) -> CartItem | None:
        """Check if the product/variant is already in the cart."""
        conditions = [
            CartItem.cart_id == cart_id,
            CartItem.product_id == product_id,
        ]
        if variant_id:
            conditions.append(CartItem.variant_id == variant_id)
        else:
            conditions.append(CartItem.variant_id.is_(None))

        query = select(CartItem).where(*conditions)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_items_by_cart(
        self, db: AsyncSession, cart_id: UUID
    ) -> list[CartItem]:
        """Fetch all items in a cart."""
        query = select(CartItem).where(CartItem.cart_id == cart_id)
        result = await db.execute(query)
        return list(result.scalars().all())

    async def clear_cart(self, db: AsyncSession, cart_id: UUID) -> None:
        """Remove all items from a cart."""
        items = await self.get_items_by_cart(db, cart_id)
        for item in items:
            await db.delete(item)
        await db.flush()
