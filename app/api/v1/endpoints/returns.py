"""Return/refund endpoints — customer create & view, admin actions handled in admin.py."""

from uuid import UUID

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.security import get_current_user
from app.models.user import User
from app.repositories.order_repository import OrderRepository
from app.repositories.return_repository import ReturnItemRepository, ReturnRequestRepository
from app.schemas.common import ApiResponse
from app.schemas.return_request import ReturnCreateRequest, ReturnResponse
from app.services.notification_service import NotificationService
from app.services.return_service import ReturnService

router = APIRouter()


def get_return_service() -> ReturnService:
    """Build ReturnService with its dependencies."""
    return ReturnService(
        return_repo=ReturnRequestRepository(),
        return_item_repo=ReturnItemRepository(),
        order_repo=OrderRepository(),
        notification_service=NotificationService(),
    )


@router.post("/", status_code=201)
async def create_return_request(
    body: ReturnCreateRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    return_service: ReturnService = Depends(get_return_service),
) -> ApiResponse:
    """Submit a return request for a delivered order."""
    return_request = await return_service.create_return(db, current_user.id, body)
    return ApiResponse.success(
        data=ReturnResponse.model_validate(return_request),
        message="Return request submitted",
    )


@router.get("")
async def list_my_returns(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    return_service: ReturnService = Depends(get_return_service),
) -> ApiResponse:
    """List all return requests for the current user."""
    returns = await return_service.get_user_returns(db, current_user.id)
    return ApiResponse.success(
        data=[ReturnResponse.model_validate(r) for r in returns],
        message="Returns retrieved",
    )


@router.get("/{return_id}")
async def get_return_request(
    return_id: UUID,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user),
    return_service: ReturnService = Depends(get_return_service),
) -> ApiResponse:
    """Get details of a specific return request."""
    return_request = await return_service.get_return(db, return_id)
    # Verify ownership
    from app.core.exceptions import ValidationError

    if return_request.user_id != current_user.id:
        raise ValidationError("You can only view your own return requests")
    return ApiResponse.success(
        data=ReturnResponse.model_validate(return_request),
        message="Return request retrieved",
    )
