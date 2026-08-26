# tests/unit/application/test_result_delivery_service.py

from pathlib import Path
from uuid import uuid4

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
    """После выдачи PDF backend не должен хранить его копию."""
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

    expected_pdf = (
        b"%PDF-generated-report"
    )

    storage.save_result(
        job_id,
        expected_pdf,
    )

    service = (
        ResultDeliveryService(
            repository=(
                repository
            ),
            storage=(
                storage
            ),
        )
    )

    actual_pdf = (
        service.consume(
            job_id
        )
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
    