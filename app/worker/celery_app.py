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

    # Задача подтверждается после фактического выполнения.
    # При аварийном падении самого worker RabbitMQ сможет
    # вернуть неподтверждённую задачу в очередь.
    task_acks_late=True,

    # Если приложение штатно завершило задачу исключением
    # (например, сработал AI/job watchdog), Celery ACK'ает
    # сообщение. Это предотвращает бесконечный requeue.
    task_acks_on_failure_or_timeout=True,

    # Worker заранее получает только одну задачу.
    # Это необходимо для последовательной работы с GPU.
    worker_prefetch_multiplier=1,

    # Celery result backend не используется.
    # Состояние задания хранится через JobRepositoryPort.
    task_ignore_result=True,

    # Worker восстанавливает соединение после перезапуска RabbitMQ.
    broker_connection_retry_on_startup=True,

    timezone="UTC",

    # Celery Beat периодически запускает страховочную очистку
    # временных пользовательских файлов.
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
