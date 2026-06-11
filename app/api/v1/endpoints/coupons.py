"""Coupon validation endpoint (public-facing for checkout)."""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.repositories.coupon_repository import CouponRepository, CouponUsageRepository
from app.schemas.common import ApiResponse
from app.schemas.coupon import CouponValidateRequest, CouponValidateResponse
from app.services.coupon_service import CouponService

router = APIRouter()


def get_coupon_service() -> CouponService:
    return CouponService(CouponRepository(), CouponUsageRepository())


@router.post("/validate")
async def validate_coupon(
    body: CouponValidateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    coupon_service: CouponService = Depends(get_coupon_service),
) -> ApiResponse:
    """Validate a coupon code at checkout."""
    result = await coupon_service.validate_coupon(
        db, body.code, body.order_subtotal, current_user.id,
    )
    return ApiResponse.success(data=result, message="Coupon validated")
