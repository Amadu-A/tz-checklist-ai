# tests/unit/application/test_result_delivery_service.py

from pathlib import Path
from uuid import UUID, uuid4

import pytest

from app.application.services.result_delivery_service import (
    ResultDeliveryService,
)
from app.domain.enums import JobStatus
from app.infrastructure.persistence.sqlite_job_repository import (
    SqliteJobRepository,
)
from app.infrastructure.storage.ephemeral_file_storage import (
    EphemeralFileStorage,
)


def test_result_is_returned_and_all_server_state_is_deleted(
    tmp_path: Path,
) -> None:
    """После успешной выдачи PDF backend не должен хранить его копию."""
    repository = SqliteJobRepository(
        tmp_path
        / "metadata"
        / "jobs.sqlite3"
    )

    storage = EphemeralFileStorage(
        tmp_path
        / "jobs"
    )

    job_id = uuid4()

    repository.create(
        job_id,
        status=JobStatus.COMPLETED,
    )

    expected_pdf = (
        b"%PDF-generated-report"
    )

    storage.save_result(
        job_id,
        expected_pdf,
    )

    service = ResultDeliveryService(
        repository=repository,
        storage=storage,
    )

    actual_pdf = service.consume(
        job_id
    )

    assert (
        actual_pdf
        == expected_pdf
    )

    assert (
        storage.has_result(
            job_id
        )
        is False
    )

    assert (
        storage.has_input(
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


class FailingResultStorage:
    """Storage, имитирующий transient filesystem read failure."""

    def __init__(self) -> None:
        self.delete_job_files_calls = 0

    def consume_result(
        self,
        job_id: UUID,
    ) -> bytes:
        del job_id

        raise OSError(
            "temporary filesystem read failure"
        )

    def delete_job_files(
        self,
        job_id: UUID,
    ) -> None:
        del job_id

        self.delete_job_files_calls += 1


def test_metadata_is_preserved_when_result_read_fails(
    tmp_path: Path,
) -> None:
    """Ошибка чтения PDF не должна уничтожать COMPLETED metadata."""
    repository = SqliteJobRepository(
        tmp_path
        / "metadata"
        / "jobs.sqlite3"
    )

    storage = FailingResultStorage()

    job_id = uuid4()

    repository.create(
        job_id,
        status=JobStatus.COMPLETED,
    )

    service = ResultDeliveryService(
        repository=repository,
        storage=storage,
    )

    with pytest.raises(
        OSError,
        match=(
            "temporary filesystem "
            "read failure"
        ),
    ):
        service.consume(
            job_id
        )

    state = repository.get(
        job_id
    )

    assert state is not None

    assert (
        state.status
        == JobStatus.COMPLETED
    )

    # Если чтение не состоялось, дополнительный cleanup тоже
    # не должен уничтожать потенциально восстанавливаемый result.
    assert (
        storage.delete_job_files_calls
        == 0
    )
