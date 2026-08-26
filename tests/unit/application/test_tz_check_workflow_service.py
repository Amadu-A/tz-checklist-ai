# tests/unit/application/test_tz_check_workflow_service.py

from pathlib import Path

import pytest

from app.application.errors import (
    InvalidPdfError,
    QueueSubmissionError,
    UploadTooLargeError,
)
from app.application.services.result_delivery_service import (
    ResultDeliveryService,
)
from app.application.services.tz_check_workflow_service import (
    TzCheckWorkflowService,
)
from app.domain.checklists import (
    ChecklistScore,
    ChecklistSelectionResult,
    ChecklistSuggestion,
    ConfirmedChecklist,
)
from app.domain.enums import (
    ChecklistCode,
    ClassificationSource,
    JobStatus,
)
from app.infrastructure.persistence.sqlite_job_repository import (
    SqliteJobRepository,
)
from app.infrastructure.storage.ephemeral_file_storage import (
    EphemeralFileStorage,
)


class FakeSelectUseCase:
    """Детерминированная auto-classification."""

    async def execute(
        self,
        pdf_path: Path,
    ) -> ChecklistSelectionResult:
        assert pdf_path.is_file()

        return ChecklistSelectionResult(
            suggestion=ChecklistSuggestion(
                recommended_code=(
                    ChecklistCode.UUTE
                ),
                confidence=0.95,
                ranking=(
                    ChecklistScore(
                        code=ChecklistCode.UUTE,
                        score=10,
                        matched_hints=(
                            "тепловычислитель",
                        ),
                    ),
                    ChecklistScore(
                        code=ChecklistCode.ITP,
                        score=0,
                    ),
                ),
            ),
            source=(
                ClassificationSource
                .NATIVE_TEXT
            ),
        )


class FakeConfirmUseCase:
    """Проверка существующего checklist."""

    def execute(
        self,
        code: ChecklistCode,
    ) -> ConfirmedChecklist:
        return ConfirmedChecklist(
            code=code,
            title=f"Checklist {code.value}",
        )


class FakeQueue:
    """Фиксирует отправленные Celery jobs."""

    def __init__(
        self,
        *,
        fail: bool = False,
    ) -> None:
        self.fail = fail

        self.jobs: list[
            tuple[
                object,
                ChecklistCode,
            ]
        ] = []

    def enqueue_analysis(
        self,
        job_id,
        checklist_code: ChecklistCode,
    ) -> None:
        if self.fail:
            raise RuntimeError(
                "RabbitMQ unavailable"
            )

        self.jobs.append(
            (
                job_id,
                checklist_code,
            )
        )


def _service(
    tmp_path: Path,
    *,
    queue: FakeQueue,
    max_upload_bytes: int = 1024,
):
    """Собрать настоящий lifecycle storage/repository."""
    repository = SqliteJobRepository(
        tmp_path
        / "metadata"
        / "jobs.sqlite3"
    )

    storage = EphemeralFileStorage(
        tmp_path
        / "jobs"
    )

    result_delivery = ResultDeliveryService(
        repository=repository,
        storage=storage,
    )

    service = TzCheckWorkflowService(
        select_use_case=FakeSelectUseCase(),
        confirm_use_case=FakeConfirmUseCase(),
        repository=repository,
        storage=storage,
        task_queue=queue,
        result_delivery_service=result_delivery,
        max_upload_bytes=max_upload_bytes,
    )

    return (
        service,
        repository,
        storage,
    )


async def test_full_job_lifecycle_deletes_result_after_delivery(
    tmp_path: Path,
) -> None:
    """Проверить lifecycle от upload до одноразового PDF."""
    queue = FakeQueue()

    (
        service,
        repository,
        storage,
    ) = _service(
        tmp_path,
        queue=queue,
    )

    selected = await service.select(
        b"%PDF-1.4 test document"
    )

    request_id = (
        selected.request_id
    )

    state = repository.get(
        request_id
    )

    assert state is not None

    assert (
        state.status
        == JobStatus.AWAITING_CONFIRMATION
    )

    assert storage.has_input(
        request_id
    )

    confirmed = service.confirm(
        request_id=request_id,
        checklist_code=ChecklistCode.UUTE,
    )

    assert (
        confirmed.status
        == JobStatus.QUEUED
    )

    assert queue.jobs == [
        (
            request_id,
            ChecklistCode.UUTE,
        )
    ]

    status_result = service.status(
        request_id
    )

    assert (
        status_result.progress_percent
        == 25
    )

    # Имитируем уже протестированный worker этапа 3.
    storage.delete_input(
        request_id
    )

    storage.save_result(
        request_id,
        b"%PDF-generated-result",
    )

    repository.update(
        request_id,
        status=JobStatus.COMPLETED,
        checklist_code=ChecklistCode.UUTE,
    )

    completed = service.status(
        request_id
    )

    assert (
        completed.progress_percent
        == 100
    )

    assert (
        completed.result_ready
        is True
    )

    pdf_bytes = service.result(
        request_id
    )

    assert (
        pdf_bytes
        == b"%PDF-generated-result"
    )

    assert (
        storage.has_result(
            request_id
        )
        is False
    )

    assert (
        repository.get(
            request_id
        )
        is None
    )


async def test_repeated_confirm_does_not_enqueue_duplicate_task(
    tmp_path: Path,
) -> None:
    """Повторный confirm не должен создавать второй AI job."""
    queue = FakeQueue()

    (
        service,
        _,
        _,
    ) = _service(
        tmp_path,
        queue=queue,
    )

    selected = await service.select(
        b"%PDF-1.4 test"
    )

    service.confirm(
        request_id=selected.request_id,
        checklist_code=ChecklistCode.UUTE,
    )

    second = service.confirm(
        request_id=selected.request_id,
        checklist_code=ChecklistCode.UUTE,
    )

    assert (
        second.status
        == JobStatus.QUEUED
    )

    assert len(
        queue.jobs
    ) == 1


async def test_queue_failure_returns_job_to_confirmation_state(
    tmp_path: Path,
) -> None:
    """Transient RabbitMQ failure не должен потерять input PDF."""
    queue = FakeQueue(
        fail=True
    )

    (
        service,
        repository,
        storage,
    ) = _service(
        tmp_path,
        queue=queue,
    )

    selected = await service.select(
        b"%PDF-1.4 test"
    )

    with pytest.raises(
        QueueSubmissionError
    ):
        service.confirm(
            request_id=selected.request_id,
            checklist_code=ChecklistCode.UUTE,
        )

    state = repository.get(
        selected.request_id
    )

    assert state is not None

    assert (
        state.status
        == JobStatus.AWAITING_CONFIRMATION
    )

    assert storage.has_input(
        selected.request_id
    )


async def test_non_pdf_is_rejected_before_storage(
    tmp_path: Path,
) -> None:
    """Не-PDF не должен даже попадать во temporary storage."""
    queue = FakeQueue()

    (
        service,
        _,
        storage,
    ) = _service(
        tmp_path,
        queue=queue,
    )

    with pytest.raises(
        InvalidPdfError
    ):
        await service.select(
            b"this is not pdf"
        )

    assert not any(
        (
            tmp_path
            / "jobs"
        ).iterdir()
    )


async def test_oversized_pdf_is_rejected(
    tmp_path: Path,
) -> None:
    """Большой файл должен быть отклонён до создания job."""
    queue = FakeQueue()

    (
        service,
        _,
        _,
    ) = _service(
        tmp_path,
        queue=queue,
        max_upload_bytes=10,
    )

    with pytest.raises(
        UploadTooLargeError
    ):
        await service.select(
            b"%PDF-123456789"
        )
        