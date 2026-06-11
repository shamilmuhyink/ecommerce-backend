"""Order, OrderItem, and Payment repositories."""

from typing import Sequence
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.order import Order, OrderItem, OrderStatus
from app.models.payment import Payment, PaymentStatus
from app.models.product import Product
from app.repositories.base import BaseRepository


class OrderRepository(BaseRepository[Order]):
    def __init__(self) -> None:
        super().__init__(Order)

    async def get_with_items(self, db: AsyncSession, id: UUID) -> Order | None:
        """Fetch order with items eagerly loaded."""
        query = (
            select(Order)
            .where(Order.id == id)
            .options(selectinload(Order.items), selectinload(Order.payment))
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_number(self, db: AsyncSession, order_number: str) -> Order | None:
        """Fetch order by its display number."""
        query = select(Order).where(Order.order_number == order_number)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_user(
        self,
        db: AsyncSession,
        user_id: UUID,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Order], int]:
        """Fetch paginated orders for a user."""
        base = select(Order).where(Order.user_id == user_id)

        count_query = select(func.count()).select_from(base.subquery())
        total = (await db.execute(count_query)).scalar_one()

        query = (
            base.order_by(Order.created_at.desc())
            .offset(skip)
            .limit(limit)
            .options(selectinload(Order.items))
        )
        result = await db.execute(query)
        return list(result.scalars().all()), total

    async def get_by_vendor(
        self,
        db: AsyncSession,
        vendor_id: UUID,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Order], int]:
        """Fetch orders containing products from a vendor."""
        base = (
            select(Order)
            .join(OrderItem)
            .join(Product)
            .where(Product.vendor_id == vendor_id)
            .distinct()
        )

        count_query = select(func.count()).select_from(base.subquery())
        total = (await db.execute(count_query)).scalar_one()

        query = (
            base.order_by(Order.created_at.desc())
            .offset(skip)
            .limit(limit)
            .options(selectinload(Order.items))
        )
        result = await db.execute(query)
        return list(result.scalars().all()), total

    async def get_vendor_stats(self, db: AsyncSession, vendor_id: UUID) -> dict:
        """Fetch summary statistics for a vendor dashboard."""
        # Total orders for this vendor
        order_count = await db.execute(
            select(func.count(Order.id.distinct()))
            .select_from(Order)
            .join(OrderItem)
            .join(Product)
            .where(Product.vendor_id == vendor_id)
        )
        total_orders = order_count.scalar_one()

        # Pending orders
        pending_count = await db.execute(
            select(func.count(Order.id.distinct()))
            .select_from(Order)
            .join(OrderItem)
            .join(Product)
            .where(
                and_(
                    Product.vendor_id == vendor_id,
                    Order.status.in_([OrderStatus.PENDING, OrderStatus.CONFIRMED]),
                )
            )
        )
        pending_orders = pending_count.scalar_one()

        # Revenue (from delivered orders)
        revenue_result = await db.execute(
            select(func.coalesce(func.sum(OrderItem.total), 0))
            .join(Order)
            .join(Product)
            .where(
                and_(
                    Product.vendor_id == vendor_id,
                    Order.status == OrderStatus.DELIVERED,
                )
            )
        )
        total_revenue = revenue_result.scalar_one()

        return {
            "total_orders": total_orders,
            "pending_orders": pending_orders,
            "total_revenue": str(total_revenue),
        }

    async def count_all(self, db: AsyncSession) -> int:
        """Count total orders (admin)."""
        result = await db.execute(select(func.count(Order.id)))
        return result.scalar_one()


class OrderItemRepository(BaseRepository[OrderItem]):
    def __init__(self) -> None:
        super().__init__(OrderItem)


class PaymentRepository(BaseRepository[Payment]):
    def __init__(self) -> None:
        super().__init__(Payment)

    async def get_by_order(self, db: AsyncSession, order_id: UUID) -> Payment | None:
        """Fetch payment record for an order."""
        query = select(Payment).where(Payment.order_id == order_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_gateway_order_id(
        self, db: AsyncSession, gateway_order_id: str
    ) -> Payment | None:
        """Fetch payment by gateway order ID (for webhook handling)."""
        query = select(Payment).where(Payment.gateway_order_id == gateway_order_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()
