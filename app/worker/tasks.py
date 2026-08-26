# app/worker/tasks.py

from app.core.container import get_container
from app.worker.celery_app import celery_app


@celery_app.task(
    name="tz_checklist.cleanup_expired_jobs"
)
def cleanup_expired_jobs() -> int:
    """Периодически удалить забытые временные файлы."""
    container = (
        get_container()
    )

    return (
        container
        .retention_service
        .cleanup()
    )
