# tests/unit/application/test_tagged_workflow.py

from pathlib import Path

import pytest

from app.application.errors import QueueSubmissionError
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
    ChecklistTag,
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
    """Фиксирует, запускалась ли auto-classification."""

    def __init__(self) -> None:
        self.calls = 0

    async def execute(
        self,
        pdf_path: Path,
    ) -> ChecklistSelectionResult:
        assert pdf_path.is_file()

        self.calls += 1

        return ChecklistSelectionResult(
            suggestion=ChecklistSuggestion(
                recommended_code=ChecklistCode.UUTE,
                confidence=1.0,
                ranking=(
                    ChecklistScore(
                        code=ChecklistCode.UUTE,
                        score=10,
                    ),
                ),
            ),
            source=ClassificationSource.NATIVE_TEXT,
        )


class FakeConfirmUseCase:
    def execute(
        self,
        code: ChecklistCode,
    ) -> ConfirmedChecklist:
        return ConfirmedChecklist(
            code=code,
            title=(
                ChecklistTag
                .from_code(
                    code
                )
                .value
            ),
        )


class FakeQueue:
    def __init__(
        self,
        *,
        fail: bool = False,
    ) -> None:
        self.fail = fail
        self.jobs = []

    def enqueue_analysis(
        self,
        job_id,
        checklist_code,
    ) -> None:
        if self.fail:
            raise RuntimeError(
                "queue unavailable"
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
):
    repository = SqliteJobRepository(
        tmp_path
        / "metadata"
        / "jobs.sqlite3"
    )

    storage = EphemeralFileStorage(
        tmp_path
        / "jobs"
    )

    select_use_case = (
        FakeSelectUseCase()
    )

    service = TzCheckWorkflowService(
        select_use_case=select_use_case,
        confirm_use_case=FakeConfirmUseCase(),
        repository=repository,
        storage=storage,
        task_queue=queue,
        result_delivery_service=(
            ResultDeliveryService(
                repository=repository,
                storage=storage,
            )
        ),
        max_upload_bytes=1024,
    )

    return (
        service,
        repository,
        storage,
        select_use_case,
    )


async def test_tag_skips_classification_and_confirmation(
    tmp_path: Path,
) -> None:
    """tagged request сразу должен уйти в QUEUED."""
    queue = FakeQueue()

    (
        service,
        repository,
        storage,
        select_use_case,
    ) = _service(
        tmp_path,
        queue=queue,
    )

    result = await service.select(
        b"%PDF-test",
        source_filename="ТЗ МКБИ.pdf",
        checklist_tag=ChecklistTag.MKBI,
    )

    assert (
        result.status
        == JobStatus.QUEUED
    )

    assert (
        result.checklist.code
        == ChecklistCode.MKBI
    )

    assert (
        select_use_case.calls
        == 0
    )

    assert queue.jobs == [
        (
            result.request_id,
            ChecklistCode.MKBI,
        )
    ]

    assert repository.get(
        result.request_id
    ) is not None

    assert storage.source_filename(
        result.request_id
    ) == "ТЗ МКБИ.pdf"


async def test_missing_tag_keeps_automatic_confirmation_flow(
    tmp_path: Path,
) -> None:
    """Без tag сохраняется нынешний auto-detection workflow."""
    queue = FakeQueue()

    (
        service,
        repository,
        _,
        select_use_case,
    ) = _service(
        tmp_path,
        queue=queue,
    )

    result = await service.select(
        b"%PDF-test",
        source_filename="ТЗ.pdf",
    )

    state = repository.get(
        result.request_id
    )

    assert state is not None

    assert (
        state.status
        == JobStatus.AWAITING_CONFIRMATION
    )

    assert (
        select_use_case.calls
        == 1
    )

    assert (
        queue.jobs
        == []
    )


async def test_tagged_queue_failure_cleans_up_job(
    tmp_path: Path,
) -> None:
    """Direct tagged request не должен оставлять orphan job."""
    queue = FakeQueue(
        fail=True
    )

    (
        service,
        repository,
        storage,
        _,
    ) = _service(
        tmp_path,
        queue=queue,
    )

    with pytest.raises(
        QueueSubmissionError
    ):
        await service.select(
            b"%PDF-test",
            checklist_tag=ChecklistTag.SPD,
        )

    assert (
        repository.list_job_ids()
        == frozenset()
    )

    assert not any(
        (
            tmp_path
            / "jobs"
        ).iterdir()
    )
