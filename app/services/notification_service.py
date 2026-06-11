"""Notification service — dispatches async tasks via Celery."""

import structlog

from app.models.order import Order
from app.models.user import User

logger = structlog.get_logger(__name__)


class NotificationService:
    """Enqueues notification tasks to Celery workers."""

    async def enqueue_registration_email(self, user: User, token: str) -> None:
        """Enqueue email verification task."""
        from app.workers.email_tasks import send_verification_email

        send_verification_email.delay(user.email, token)
        logger.info("enqueued_verification_email", email=user.email)

    async def enqueue_password_reset_email(self, user: User, token: str) -> None:
        """Enqueue password reset email task."""
        from app.workers.email_tasks import send_password_reset_email

        send_password_reset_email.delay(user.email, token)
        logger.info("enqueued_password_reset_email", email=user.email)

    async def enqueue_order_confirmation(self, order: Order) -> None:
        """Enqueue order confirmation email/SMS tasks."""
        from app.workers.email_tasks import send_order_confirmation

        send_order_confirmation.delay(str(order.id))
        logger.info("enqueued_order_confirmation", order_id=str(order.id))

    async def enqueue_low_stock_alert(self, product_id: str, stock: int) -> None:
        """Notify vendor about low stock."""
        logger.warning("low_stock_alert", product_id=product_id, stock=stock)

    async def enqueue_order_shipped(self, order: Order) -> None:
        """Notify customer that order has shipped."""
        from app.workers.email_tasks import send_order_shipped

        send_order_shipped.delay(str(order.id))
        logger.info("enqueued_order_shipped", order_id=str(order.id))
