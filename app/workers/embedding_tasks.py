"""Product embedding sync tasks dispatched to the AI assistant service."""

from decimal import Decimal
from typing import Any

import structlog

from app.workers.celery_app import celery_app

logger = structlog.get_logger(__name__)

# Task name registered on the ai-assistant Celery worker
AI_EMBEDDING_TASK = "sync_product_embedding_task"


def _serialize_product_data(product_data: dict[str, Any]) -> dict[str, Any]:
    """Ensure all values are JSON-serializable (Decimal → str, UUID → str)."""
    sanitized: dict[str, Any] = {}
    for key, value in product_data.items():
        if isinstance(value, Decimal):
            sanitized[key] = str(value)
        else:
            sanitized[key] = value
    return sanitized


@celery_app.task(name="dispatch_product_embedding", bind=True, max_retries=3)
def dispatch_product_embedding(
    self,
    product_id: str,
    product_data: dict[str, Any],
) -> dict[str, str]:
    """Dispatch a product embedding sync to the ai-assistant Celery worker.

    This task acts as a thin relay: it serializes the product payload and
    sends it to the ai-assistant's ``sync_product_embedding_task`` via
    ``send_task`` (cross-service Celery dispatch over the shared Redis broker).

    Args:
        product_id: Stringified UUID of the product.
        product_data: Dict containing at minimum ``name`` and ``description``
            fields used by the embedding model.  Additional fields (``sku``,
            ``price``, ``category_name``) enrich the vector metadata.

    Returns:
        A status dict with ``product_id`` and dispatch confirmation.

    Raises:
        self.retry: On transient failures, retried up to 3 times with
            exponential backoff.
    """
    try:
        serialized = _serialize_product_data(product_data)

        logger.info(
            "dispatching_product_embedding",
            product_id=product_id,
            task_target=AI_EMBEDDING_TASK,
        )

        # send_task dispatches to any worker listening for the given task name,
        # regardless of which Celery app registered it.  Both services share
        # the same Redis broker so the message is routed correctly.
        celery_app.send_task(
            AI_EMBEDDING_TASK,
            args=[product_id, serialized],
            queue="ai_assistant",
        )

        logger.info(
            "product_embedding_dispatched",
            product_id=product_id,
        )
        return {"status": "dispatched", "product_id": product_id}

    except Exception as exc:
        logger.error(
            "product_embedding_dispatch_failed",
            product_id=product_id,
            error=str(exc),
        )
        raise self.retry(exc=exc, countdown=30 * (2 ** self.request.retries)) from exc
