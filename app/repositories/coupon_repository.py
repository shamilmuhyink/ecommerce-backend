"""Coupon repository."""

from datetime import datetime, timezone
from uuid import UUID

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.coupon import Coupon, CouponStatus, CouponUsage
from app.repositories.base import BaseRepository


class CouponRepository(BaseRepository[Coupon]):
    def __init__(self) -> None:
        super().__init__(Coupon)

    async def get_by_code(self, db: AsyncSession, code: str) -> Coupon | None:
        """Fetch coupon by code."""
        query = select(Coupon).where(Coupon.code == code)
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_active_by_code(self, db: AsyncSession, code: str) -> Coupon | None:
        """Fetch an active, non-expired coupon by code."""
        now = datetime.now(timezone.utc)
        query = select(Coupon).where(
            and_(
                Coupon.code == code,
                Coupon.status == CouponStatus.ACTIVE,
                Coupon.valid_from <= now,
                Coupon.valid_until > now,
            )
        )
        result = await db.execute(query)
        return result.scalar_one_or_none()

    async def get_user_usage_count(
        self, db: AsyncSession, coupon_id: UUID, user_id: UUID
    ) -> int:
        """Count how many times a user has used a specific coupon."""
        result = await db.execute(
            select(func.count(CouponUsage.id)).where(
                and_(
                    CouponUsage.coupon_id == coupon_id,
                    CouponUsage.user_id == user_id,
                )
            )
        )
        return result.scalar_one()

    async def increment_usage(self, db: AsyncSession, coupon: Coupon) -> None:
        """Increment the coupon's global usage counter."""
        coupon.usage_count += 1
        db.add(coupon)
        await db.flush()


class CouponUsageRepository(BaseRepository[CouponUsage]):
    def __init__(self) -> None:
        super().__init__(CouponUsage)
