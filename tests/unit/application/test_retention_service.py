# tests/unit/application/test_retention_service.py

import os
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


def _service(
    tmp_path: Path,
) -> tuple[
    RetentionService,
    SqliteJobRepository,
    EphemeralFileStorage,
]:
    """Собрать настоящий retention stack."""
    repository = SqliteJobRepository(
        tmp_path
        / "metadata"
        / "jobs.sqlite3"
    )

    storage = EphemeralFileStorage(
        tmp_path
        / "jobs"
    )

    service = RetentionService(
        repository=repository,
        storage=storage,
        result_ttl_minutes=60,
        orphan_ttl_hours=6,
        failed_state_ttl_hours=24,
    )

    return (
        service,
        repository,
        storage,
    )


def test_expired_completed_result_is_removed(
    tmp_path: Path,
) -> None:
    """Незабранный result должен быть удалён TTL-cleanup."""
    (
        service,
        repository,
        storage,
    ) = _service(
        tmp_path
    )

    job_id = uuid4()

    repository.create(
        job_id,
        status=JobStatus.COMPLETED,
    )

    storage.save_result(
        job_id,
        b"%PDF-old-result",
    )

    future = (
        datetime.now(
            UTC
        )
        + timedelta(
            hours=2
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


def test_unregistered_old_job_directory_is_removed(
    tmp_path: Path,
) -> None:
    """Filesystem orphan без SQLite metadata тоже должен исчезнуть."""
    (
        service,
        _,
        storage,
    ) = _service(
        tmp_path
    )

    orphan_id = uuid4()

    orphan_file = (
        tmp_path
        / "jobs"
        / str(orphan_id)
        / "input.pdf"
    )

    orphan_file.parent.mkdir(
        parents=True,
        exist_ok=True,
    )

    orphan_file.write_bytes(
        b"%PDF-orphan"
    )

    old_timestamp = (
        datetime.now(
            UTC
        )
        - timedelta(
            hours=8
        )
    ).timestamp()

    os.utime(
        orphan_file,
        (
            old_timestamp,
            old_timestamp,
        ),
    )

    os.utime(
        orphan_file.parent,
        (
            old_timestamp,
            old_timestamp,
        ),
    )

    deleted = service.cleanup(
        now=datetime.now(
            UTC
        )
    )

    assert (
        deleted
        == 1
    )

    assert (
        orphan_file.parent.exists()
        is False
    )

    assert (
        storage.has_input(
            orphan_id
        )
        is False
    )


def test_registered_job_directory_is_not_removed_by_filesystem_sweep(
    tmp_path: Path,
) -> None:
    """Живой SQLite job должен защищать свой temporary input."""
    (
        service,
        repository,
        storage,
    ) = _service(
        tmp_path
    )

    job_id = uuid4()

    repository.create(
        job_id,
        status=(
            JobStatus
            .AWAITING_CONFIRMATION
        ),
    )

    storage.save_input(
        job_id,
        b"%PDF-live-input",
    )

    # Cleanup выполняем через час:
    # result TTL уже не важен, а orphan TTL=6h ещё не наступил.
    service.cleanup(
        now=(
            datetime.now(
                UTC
            )
            + timedelta(
                hours=1
            )
        )
    )

    assert (
        repository.get(
            job_id
        )
        is not None
    )

    assert (
        storage.has_input(
            job_id
        )
        is True
    )
