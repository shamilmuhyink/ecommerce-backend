"""Return/refund service — create, review, process refunds.

Services raise AppException subclasses, never HTTPException.
"""

from decimal import Decimal
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, OrderStateError, ValidationError
from app.models.order import OrderStatus
from app.models.return_request import ReturnRequest, ReturnStatus
from app.repositories.order_repository import OrderRepository
from app.repositories.return_repository import ReturnItemRepository, ReturnRequestRepository
from app.schemas.return_request import ReturnCreateRequest
from app.services.notification_service import NotificationService

logger = structlog.get_logger(__name__)


class ReturnService:
    """Return request lifecycle — creation, admin review, refund processing."""

    def __init__(
        self,
        return_repo: ReturnRequestRepository,
        return_item_repo: ReturnItemRepository,
        order_repo: OrderRepository,
        notification_service: NotificationService,
    ) -> None:
        self._return_repo = return_repo
        self._return_item_repo = return_item_repo
        self._order_repo = order_repo
        self._notification_service = notification_service

    async def create_return(
        self,
        db: AsyncSession,
        user_id: UUID,
        request_in: ReturnCreateRequest,
    ) -> ReturnRequest:
        """Submit a return request for a delivered order.

        Raises:
            NotFoundError: If order does not exist.
            ValidationError: If order does not belong to user.
            OrderStateError: If order is not in DELIVERED status.
            ValidationError: If a return already exists for this order.
        """
        # 1. Validate order exists and belongs to user
        order = await self._order_repo.get_with_items(db, request_in.order_id)
        if not order:
            raise NotFoundError("Order", str(request_in.order_id))

        if order.user_id != user_id:
            raise ValidationError("You can only return your own orders")

        # 2. Order must be DELIVERED to be returnable
        if order.status != OrderStatus.DELIVERED:
            raise OrderStateError(
                str(order.id), order.status.value, "Return requires DELIVERED status"
            )

        # 3. Check no existing return for this order
        existing = await self._return_repo.get_by_order(db, request_in.order_id)
        if existing:
            raise ValidationError("A return request already exists for this order")

        # 4. Validate return items belong to the order
        order_item_ids = {item.id for item in order.items}
        for return_item in request_in.items:
            if return_item.order_item_id not in order_item_ids:
                raise ValidationError(
                    f"Order item {return_item.order_item_id} does not belong to this order"
                )

            # Validate quantity
            matching_item = next(i for i in order.items if i.id == return_item.order_item_id)
            if return_item.quantity > matching_item.quantity:
                raise ValidationError(
                    f"Return quantity ({return_item.quantity}) exceeds ordered quantity "
                    f"({matching_item.quantity}) for item {return_item.order_item_id}"
                )

        # 5. Create return request
        return_data = {
            "order_id": request_in.order_id,
            "user_id": user_id,
            "status": ReturnStatus.REQUESTED,
            "reason": request_in.reason,
        }
        return_request = await self._return_repo.create(db, obj_in=return_data)

        # 6. Create return items
        for item in request_in.items:
            item_data = {
                "return_request_id": return_request.id,
                "order_item_id": item.order_item_id,
                "quantity": item.quantity,
                "reason": item.reason,
            }
            await self._return_item_repo.create(db, obj_in=item_data)

        await db.refresh(return_request)
        logger.info(
            "return_request_created",
            return_id=str(return_request.id),
            order_id=str(request_in.order_id),
            user_id=str(user_id),
        )
        return return_request

    async def get_return(self, db: AsyncSession, return_id: UUID) -> ReturnRequest:
        """Fetch a return request with items.

        Raises:
            NotFoundError: If return request does not exist.
        """
        return_request = await self._return_repo.get_with_items(db, return_id)
        if not return_request:
            raise NotFoundError("ReturnRequest", str(return_id))
        return return_request

    async def get_user_returns(
        self, db: AsyncSession, user_id: UUID
    ) -> list[ReturnRequest]:
        """Fetch all return requests for a user."""
        return await self._return_repo.get_by_user(db, user_id)

    async def admin_update_return(
        self,
        db: AsyncSession,
        return_id: UUID,
        new_status: ReturnStatus,
        admin_notes: str | None = None,
        refund_amount: Decimal | None = None,
    ) -> ReturnRequest:
        """Admin approves/rejects a return request.

        Raises:
            NotFoundError: If return request does not exist.
            ValidationError: If status transition is invalid.
        """
        return_request = await self._return_repo.get_with_items(db, return_id)
        if not return_request:
            raise NotFoundError("ReturnRequest", str(return_id))

        # Validate status transition
        valid_transitions = {
            ReturnStatus.REQUESTED: {ReturnStatus.APPROVED, ReturnStatus.REJECTED},
            ReturnStatus.APPROVED: {ReturnStatus.REFUND_INITIATED},
            ReturnStatus.REFUND_INITIATED: {ReturnStatus.REFUND_COMPLETED},
        }
        allowed = valid_transitions.get(return_request.status, set())
        if new_status not in allowed:
            raise ValidationError(
                f"Cannot transition from {return_request.status.value} to {new_status.value}"
            )

        update_data: dict = {"status": new_status}
        if admin_notes:
            update_data["admin_notes"] = admin_notes
        if refund_amount is not None:
            update_data["refund_amount"] = refund_amount

        updated = await self._return_repo.update(
            db, db_obj=return_request, obj_in=update_data
        )
        await db.commit()

        logger.info(
            "return_request_updated",
            return_id=str(return_id),
            new_status=new_status.value,
            refund_amount=str(refund_amount) if refund_amount else None,
        )
        return updated
