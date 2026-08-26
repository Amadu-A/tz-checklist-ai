# app/worker/tasks.py

import asyncio
from uuid import UUID

from app.core.container import get_container
from app.domain.enums import ChecklistCode
from app.worker.celery_app import celery_app


@celery_app.task(
    name="tz_checklist.process_analysis"
)
def process_analysis(
    job_id: str,
    checklist_code: str,
) -> None:
    """Запустить полный AI pipeline для одного подтверждённого ТЗ."""
    container = get_container()

    asyncio.run(
        container.analysis_pipeline_service.process(
            job_id=UUID(
                job_id
            ),
            checklist_code=ChecklistCode(
                checklist_code
            ),
        )
    )


@celery_app.task(
    name="tz_checklist.cleanup_expired_jobs"
)
def cleanup_expired_jobs() -> int:
    """Периодически удалить забытые временные файлы."""
    container = get_container()

    return (
        container
        .retention_service
        .cleanup()
    )
