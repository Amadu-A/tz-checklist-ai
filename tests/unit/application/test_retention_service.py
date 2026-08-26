# tests/unit/application/test_retention_service.py

from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

from app.application.services.retention_service import (
    RetentionService,
)
from app.domain.enums import JobStatus
from app.infrastructure.persistence.sqlite_job_repository import (
    SqliteJobRepository,
)
from app.infrastructure.storage.ephemeral_file_storage import (
    EphemeralFileStorage,
)


def test_expired_completed_result_is_removed(
    tmp_path: Path,
) -> None:
    """Незабранный result должен быть удалён TTL-cleanup."""
    repository = (
        SqliteJobRepository(
            tmp_path
            / "metadata"
            / "jobs.sqlite3"
        )
    )

    storage = (
        EphemeralFileStorage(
            tmp_path
            / "jobs"
        )
    )

    job_id = uuid4()

    repository.create(
        job_id,
        status=(
            JobStatus.COMPLETED
        ),
    )

    storage.save_result(
        job_id,
        b"%PDF-old-result",
    )

    # SQLite repository использует текущее UTC-время.
    # Передаём cleanup время далеко в будущем,
    # поэтому job гарантированно становится expired.
    future = (
        datetime.now(
            UTC
        )
        + timedelta(
            hours=2
        )
    )

    service = (
        RetentionService(
            repository=repository,
            storage=storage,
            result_ttl_minutes=60,
            orphan_ttl_hours=6,
            failed_state_ttl_hours=24,
        )
    )

    deleted = service.cleanup(
        now=future
    )

    assert (
        deleted
        == 1
    )

    assert (
        storage.has_result(
            job_id
        )
        is False
    )

    assert (
        repository.get(
            job_id
        )
        is None
    )
