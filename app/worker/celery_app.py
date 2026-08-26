# app/worker/celery_app.py

from celery import Celery

from app.core.config import get_settings


settings = get_settings()

celery_app = Celery(
    "tz_checklist_ai",
    broker=settings.rabbitmq_url,
    include=[
        "app.worker.tasks",
    ],
)

celery_app.conf.update(
    task_default_queue=(
        settings.celery_queue_name
    ),

    task_acks_late=True,

    worker_prefetch_multiplier=1,

    task_ignore_result=True,

    broker_connection_retry_on_startup=True,

    timezone="UTC",

    beat_schedule={
        "cleanup-expired-jobs": {
            "task": (
                "tz_checklist.cleanup_expired_jobs"
            ),
            "schedule": (
                settings.cleanup_interval_seconds
            ),
        },
    },
)
