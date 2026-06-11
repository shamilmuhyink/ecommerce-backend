"""Coupon validation and application service."""

from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import InvalidCouponError
from app.models.coupon import CouponType
from app.repositories.coupon_repository import CouponRepository, CouponUsageRepository
from app.schemas.coupon import CouponValidateResponse

logger = structlog.get_logger(__name__)


class CouponService:
    """Coupon validation and discount calculation."""

    def __init__(
        self,
        coupon_repo: CouponRepository,
        usage_repo: CouponUsageRepository,
    ) -> None:
        self._coupon_repo = coupon_repo
        self._usage_repo = usage_repo

    async def validate_coupon(
        self, db: AsyncSession, code: str, order_subtotal: Decimal, user_id: UUID,
    ) -> CouponValidateResponse:
        """Validate and calculate discount for a coupon code."""
        coupon = await self._coupon_repo.get_active_by_code(db, code)
        if not coupon:
            return CouponValidateResponse(valid=False, message="Coupon not found or expired")

        if coupon.usage_limit > 0 and coupon.usage_count >= coupon.usage_limit:
            return CouponValidateResponse(valid=False, message="Coupon usage limit reached")

        user_usage = await self._coupon_repo.get_user_usage_count(db, coupon.id, user_id)
        if user_usage >= coupon.per_user_limit:
            return CouponValidateResponse(valid=False, message="You have already used this coupon")

        if order_subtotal < coupon.min_order_value:
            return CouponValidateResponse(
                valid=False,
                message=f"Minimum order value is ₹{coupon.min_order_value}",
            )

        if coupon.coupon_type == CouponType.PERCENTAGE:
            discount = (order_subtotal * coupon.value) / Decimal("100")
            if coupon.max_discount and discount > coupon.max_discount:
                discount = coupon.max_discount
        else:
            discount = coupon.value

        discount = min(discount, order_subtotal)

        return CouponValidateResponse(
            valid=True, discount_amount=discount,
            message=f"Coupon applied! You save ₹{discount}",
        )

    async def apply_coupon(
        self, db: AsyncSession, code: str, order_subtotal: Decimal,
        user_id: UUID, order_id: UUID,
    ) -> Decimal:
        """Apply coupon to an order and record usage.

        Raises:
            InvalidCouponError: If coupon is invalid.
        """
        result = await self.validate_coupon(db, code, order_subtotal, user_id)
        if not result.valid:
            raise InvalidCouponError(result.message)

        coupon = await self._coupon_repo.get_active_by_code(db, code)
        if not coupon:
            raise InvalidCouponError("Coupon not found")

        await self._usage_repo.create(db, obj_in={
            "coupon_id": coupon.id, "user_id": user_id, "order_id": order_id,
        })
        await self._coupon_repo.increment_usage(db, coupon)

        logger.info("coupon_applied", code=code, discount=str(result.discount_amount), order_id=str(order_id))
        return result.discount_amount
