"""Celery application configuration."""

from celery import Celery
from celery.schedules import crontab

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "ecommerce_workers",
    broker=str(settings.REDIS_URL),
    backend=str(settings.REDIS_URL),
    include=[
        "app.workers.email_tasks",
        "app.workers.order_tasks",
        "app.workers.payout_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    broker_connection_timeout=1.0,
    broker_connection_retry_on_startup=False,
    task_always_eager=settings.APP_ENV == "development",
)

# Celery Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    "cancel-stale-orders": {
        "task": "cancel_stale_orders",
        "schedule": 1800.0,  # Every 30 minutes
    },
    "weekly-vendor-payouts": {
        "task": "process_weekly_payouts",
        "schedule": crontab(hour=0, minute=0, day_of_week=0),  # Sunday midnight IST
    },
}
