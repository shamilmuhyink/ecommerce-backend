"""Order lifecycle background tasks."""

import asyncio
from datetime import datetime, timedelta, timezone

import structlog
from sqlalchemy import select, update

from app.core.database import AsyncSessionLocal
from app.models.order import Order, OrderStatus
from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)


@celery_app.task(name="cancel_stale_orders")
def cancel_stale_orders() -> int:
    """Cancel orders that remained PENDING for more than 30 minutes.

    Runs every 30 minutes via Celery Beat.
    """
    return asyncio.run(_cancel_stale_orders_async())


async def _cancel_stale_orders_async() -> int:
    """Async implementation of stale order cancellation."""
    cutoff = datetime.now(timezone.utc) - timedelta(minutes=30)

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            select(Order).where(
                Order.status == OrderStatus.PENDING,
                Order.created_at < cutoff,
            )
        )
        stale_orders = result.scalars().all()

        count = 0
        for order in stale_orders:
            order.status = OrderStatus.CANCELLED
            db.add(order)
            count += 1

        if count > 0:
            await db.commit()

    logger.info("stale_orders_cancelled", count=count)
    return count


@celery_app.task(name="process_inventory_restock")
def process_inventory_restock(product_id: str, quantity: int) -> bool:
    """Handle automated inventory restocking alerts."""
    logger.info(
        "processing_inventory_restock", product_id=product_id, qty=quantity
    )
    return True
