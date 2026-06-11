"""Order lifecycle service — create, cancel, status transitions.

Services raise AppException subclasses, never HTTPException.
"""

import uuid
from decimal import Decimal
from typing import Sequence

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import (
    InsufficientStockError,
    NotFoundError,
    OrderStateError,
    ValidationError,
)
from app.models.order import Order, OrderStatus
from app.repositories.order_repository import OrderItemRepository, OrderRepository
from app.repositories.product_repository import ProductRepository
from app.repositories.user_repository import AddressRepository
from app.schemas.order import OrderCreate
from app.services.notification_service import NotificationService
from app.services.payment_service import PaymentService
from app.utils.currency import calculate_tax, calculate_total

logger = structlog.get_logger(__name__)


class OrderService:
    """Order creation, retrieval, cancellation, and status management."""

    def __init__(
        self,
        order_repo: OrderRepository,
        item_repo: OrderItemRepository,
        product_repo: ProductRepository,
        address_repo: AddressRepository,
        notification_service: NotificationService,
        payment_service: PaymentService,
    ) -> None:
        self._order_repo = order_repo
        self._item_repo = item_repo
        self._product_repo = product_repo
        self._address_repo = address_repo
        self._notification_service = notification_service
        self._payment_service = payment_service

    async def create_order(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        order_in: OrderCreate,
    ) -> Order:
        """Place a new order after validating stock and calculating totals.

        Raises:
            NotFoundError: If product or address not found.
            InsufficientStockError: If any item is out of stock.
        """
        # 1. Validate shipping address
        address = await self._address_repo.get(db, order_in.shipping_address_id)
        if not address or address.user_id != user_id:
            raise NotFoundError("Address", str(order_in.shipping_address_id))

        # 2. Validate stock and calculate totals
        subtotal = Decimal("0.00")
        order_items_data = []

        for item_in in order_in.items:
            product = await self._product_repo.get(db, item_in.product_id)
            if not product:
                raise NotFoundError("Product", str(item_in.product_id))

            if product.stock < item_in.quantity:
                raise InsufficientStockError(
                    str(product.id), item_in.quantity, product.stock
                )

            item_total = product.price * item_in.quantity
            subtotal += item_total

            order_items_data.append(
                {
                    "product_id": product.id,
                    "variant_id": item_in.variant_id,
                    "product_name": product.name,
                    "product_sku": product.sku,
                    "quantity": item_in.quantity,
                    "price": product.price,
                    "total": item_total,
                }
            )

        # 3. Calculate pricing
        discount = Decimal("0.00")
        tax = calculate_tax(subtotal - discount)
        shipping = (
            Decimal("50.00") if subtotal < Decimal("500.00") else Decimal("0.00")
        )
        total = calculate_total(subtotal, discount=discount, shipping=shipping)

        # 4. Create order with address snapshot
        order_number = f"ORD-{uuid.uuid4().hex[:8].upper()}"
        order_data = {
            "order_number": order_number,
            "user_id": user_id,
            "status": OrderStatus.PENDING,
            "subtotal": subtotal,
            "discount": discount,
            "tax": tax,
            "shipping_charge": shipping,
            "total": total,
            "coupon_code": order_in.coupon_code,
            "shipping_name": address.label or "Shipping",
            "shipping_phone": None,
            "shipping_line1": address.line1,
            "shipping_line2": address.line2,
            "shipping_city": address.city,
            "shipping_state": address.state,
            "shipping_postal_code": address.postal_code,
            "shipping_country": address.country,
        }

        order = await self._order_repo.create(db, obj_in=order_data)

        # 5. Create order items and deduct stock
        for item_data in order_items_data:
            item_data["order_id"] = order.id
            await self._item_repo.create(db, obj_in=item_data)

            # Deduct stock
            product = await self._product_repo.get(db, item_data["product_id"])
            if product:
                await self._product_repo.update(
                    db,
                    db_obj=product,
                    obj_in={"stock": product.stock - item_data["quantity"]},
                )

        # 6. Initiate payment
        await self._payment_service.initiate_payment(order, db)

        # 7. Notification
        await self._notification_service.enqueue_order_confirmation(order)

        await db.refresh(order)
        logger.info(
            "order_created",
            order_id=str(order.id),
            order_number=order_number,
            user_id=str(user_id),
            total=str(total),
            item_count=len(order_items_data),
        )
        return order

    async def get_order(self, db: AsyncSession, order_id: uuid.UUID) -> Order:
        """Fetch order with items.

        Raises:
            NotFoundError: If order does not exist.
        """
        order = await self._order_repo.get_with_items(db, order_id)
        if not order:
            raise NotFoundError("Order", str(order_id))
        return order

    async def get_user_orders(
        self,
        db: AsyncSession,
        user_id: uuid.UUID,
        *,
        skip: int = 0,
        limit: int = 20,
    ) -> tuple[list[Order], int]:
        """Fetch paginated orders for a user."""
        return await self._order_repo.get_by_user(
            db, user_id, skip=skip, limit=limit
        )

    async def cancel_order(
        self,
        db: AsyncSession,
        order_id: uuid.UUID,
        user_id: uuid.UUID,
        reason: str,
    ) -> Order:
        """Cancel a pending/confirmed order.

        Raises:
            NotFoundError: If order does not exist.
            ValidationError: If order does not belong to user.
            OrderStateError: If order cannot be cancelled.
        """
        order = await self._order_repo.get_with_items(db, order_id)
        if not order:
            raise NotFoundError("Order", str(order_id))

        if order.user_id != user_id:
            raise ValidationError("You can only cancel your own orders")

        if not order.can_transition_to(OrderStatus.CANCELLED):
            raise OrderStateError(
                str(order_id), order.status.value, OrderStatus.CANCELLED.value
            )

        # Restore stock
        for item in order.items:
            product = await self._product_repo.get(db, item.product_id)
            if product:
                await self._product_repo.update(
                    db,
                    db_obj=product,
                    obj_in={"stock": product.stock + item.quantity},
                )

        await self._order_repo.update(
            db, db_obj=order, obj_in={"status": OrderStatus.CANCELLED}
        )
        logger.info(
            "order_cancelled",
            order_id=str(order_id),
            reason=reason,
        )
        return order

    async def update_status(
        self,
        db: AsyncSession,
        order_id: uuid.UUID,
        new_status: OrderStatus,
        tracking_number: str | None = None,
        tracking_url: str | None = None,
    ) -> Order:
        """Admin/vendor updates order status with optional tracking info.

        Raises:
            NotFoundError: If order does not exist.
            OrderStateError: If transition is invalid.
        """
        order = await self._order_repo.get(db, order_id)
        if not order:
            raise NotFoundError("Order", str(order_id))

        if not order.can_transition_to(new_status):
            raise OrderStateError(
                str(order_id), order.status.value, new_status.value
            )

        update_data: dict = {"status": new_status}
        if tracking_number:
            update_data["tracking_number"] = tracking_number
        if tracking_url:
            update_data["tracking_url"] = tracking_url

        await self._order_repo.update(db, db_obj=order, obj_in=update_data)
        await db.commit()

        logger.info(
            "order_status_updated",
            order_id=str(order_id),
            new_status=new_status.value,
        )
        return order
