# app/worker/celery_app.py

from app.core.config import get_settings
from celery import Celery


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

    # Задача подтверждается только после фактического выполнения.
    # Если worker аварийно завершится во время обработки,
    # RabbitMQ сможет вернуть задачу в очередь.
    task_acks_late=True,

    # Worker заранее получает только одну задачу.
    # Это особенно важно для GPU-нагрузки.
    worker_prefetch_multiplier=1,

    # Celery result backend нам не нужен:
    # состояние задания хранится через JobRepositoryPort.
    task_ignore_result=True,

    # После перезапуска RabbitMQ worker должен восстановить соединение.
    broker_connection_retry_on_startup=True,

    timezone="UTC",

    # Периодическая страховочная очистка забытых временных файлов.
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
