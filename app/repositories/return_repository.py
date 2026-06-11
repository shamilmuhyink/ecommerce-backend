"""Return request repository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.return_request import ReturnRequest, ReturnItem, ReturnStatus
from app.repositories.base import BaseRepository


class ReturnRequestRepository(BaseRepository[ReturnRequest]):
    def __init__(self) -> None:
        super().__init__(ReturnRequest)

    async def get_with_items(
        self, db: AsyncSession, id: UUID
    ) -> ReturnRequest | None:
        """Fetch return request with items eagerly loaded."""
        query = (
            select(ReturnRequest)
            .where(ReturnRequest.id == id)
            .options(selectinload(ReturnRequest.items))
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_order(
        self, db: AsyncSession, order_id: UUID
    ) -> ReturnRequest | None:
        """Fetch return request for a specific order."""
        query = select(ReturnRequest).where(ReturnRequest.order_id == order_id)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_by_user(
        self, db: AsyncSession, user_id: UUID
    ) -> list[ReturnRequest]:
        """Fetch all return requests for a user."""
        query = (
            select(ReturnRequest)
            .where(ReturnRequest.user_id == user_id)
            .order_by(ReturnRequest.created_at.desc())
            .options(selectinload(ReturnRequest.items))
        )
        result = await db.execute(query)
        return list(result.scalars().all())

    async def get_pending(self, db: AsyncSession) -> list[ReturnRequest]:
        """Fetch all pending return requests (for admin review)."""
        query = (
            select(ReturnRequest)
            .where(ReturnRequest.status == ReturnStatus.REQUESTED)
            .order_by(ReturnRequest.created_at.asc())
            .options(selectinload(ReturnRequest.items))
        )
        result = await db.execute(query)
        return list(result.scalars().all())


class ReturnItemRepository(BaseRepository[ReturnItem]):
    def __init__(self) -> None:
        super().__init__(ReturnItem)
