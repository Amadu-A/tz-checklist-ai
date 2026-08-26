# tests/unit/infrastructure/test_sqlite_job_repository.py

from pathlib import Path
from uuid import uuid4

from app.domain.enums import (
    ChecklistCode,
    JobStatus,
)
from app.infrastructure.persistence.sqlite_job_repository import (
    SqliteJobRepository,
)


def test_repository_stores_only_job_metadata(
    tmp_path: Path,
) -> None:
    """Создать, обновить и удалить metadata job."""
    repository = (
        SqliteJobRepository(
            tmp_path
            / "jobs.sqlite3"
        )
    )

    job_id = uuid4()

    created = repository.create(
        job_id,
        status=(
            JobStatus
            .AWAITING_CONFIRMATION
        ),
    )

    assert (
        created.job_id
        == job_id
    )

    assert (
        created.checklist_code
        is None
    )

    updated = repository.update(
        job_id,
        status=JobStatus.QUEUED,
        checklist_code=(
            ChecklistCode.UUTE
        ),
    )

    assert (
        updated.status
        == JobStatus.QUEUED
    )

    assert (
        updated.checklist_code
        == ChecklistCode.UUTE
    )

    repository.delete(
        job_id
    )

    assert (
        repository.get(
            job_id
        )
        is None
    )
    