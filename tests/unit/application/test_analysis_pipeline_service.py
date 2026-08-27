# tests/unit/application/test_analysis_pipeline_service.py

import asyncio
import json
from pathlib import Path
from uuid import uuid4

import pytest

from app.application.services.analysis_pipeline_service import (
    AnalysisPipelineService,
)
from app.application.services.answer_dimension_validator import (
    AnswerDimensionValidator,
)
from app.application.services.checklist_result_builder import (
    ChecklistResultBuilder,
)
from app.domain.answers import (
    AnswerStatus,
    ChecklistAnalysisResult,
    GroundedAnswer,
)
from app.domain.checklists import (
    ChecklistDefinition,
    ChecklistQuestion,
    ChecklistSection,
    ChecklistSheet,
)
from app.domain.documents import (
    DocumentTextContext,
    PdfPageText,
)
from app.domain.enums import (
    ChecklistCode,
    JobStatus,
)
from app.infrastructure.persistence.sqlite_job_repository import (
    SqliteJobRepository,
)
from app.infrastructure.reporting.json_checklist_result_serializer import (
    JsonChecklistResultSerializer,
)
from app.infrastructure.storage.ephemeral_file_storage import (
    EphemeralFileStorage,
)


def _checklist() -> ChecklistDefinition:
    return ChecklistDefinition(
        code=ChecklistCode.UUTE,
        title="УУТЭ",
        description=(
            "Узел учета тепловой энергии "
            "и теплоносителя."
        ),
        source_workbook="test.xlsx",
        expected_question_count=1,
        sheets=(
            ChecklistSheet(
                id="main",
                title="УУТЭ",
                sections=(
                    ChecklistSection(
                        id="section",
                        title="Основные вопросы",
                        questions=(
                            ChecklistQuestion(
                                id="q1",
                                source_number="1",
                                text=(
                                    "Какой расход "
                                    "теплоносителя?"
                                ),
                                output_order=1,
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


class FakeChecklistRepository:
    def get(
        self,
        code: ChecklistCode,
    ) -> ChecklistDefinition:
        assert (
            code
            == ChecklistCode.UUTE
        )

        return _checklist()


class FakeContentService:
    def extract_native(
        self,
        pdf_path: Path,
        *,
        max_pages: int | None = None,
    ) -> DocumentTextContext:
        del pdf_path
        del max_pages

        return DocumentTextContext(
            pages=(
                PdfPageText(
                    page_number=1,
                    text=(
                        "Расход составляет "
                        "3.93 т/ч."
                    ),
                ),
            )
        )


class FakeChunker:
    def chunk(
        self,
        context: DocumentTextContext,
    ):
        del context

        return ()


class FakeAnsweringService:
    async def analyze(
        self,
        *,
        checklist,
        chunks,
    ) -> ChecklistAnalysisResult:
        del checklist
        del chunks

        return ChecklistAnalysisResult(
            checklist_code=ChecklistCode.UUTE,
            answers=(
                GroundedAnswer(
                    question_id="q1",
                    status=AnswerStatus.FOUND,
                    answer="3.93 т/ч",
                    confidence=0.95,
                    source_pages=(1,),
                    supporting_text=(
                        "Расход составляет "
                        "3.93 т/ч."
                    ),
                ),
            ),
        )


class SlowAnsweringService:
    async def analyze(
        self,
        *,
        checklist,
        chunks,
    ) -> ChecklistAnalysisResult:
        del checklist
        del chunks

        await asyncio.sleep(
            0.05
        )

        return ChecklistAnalysisResult(
            checklist_code=ChecklistCode.UUTE,
            answers=(),
        )


class FakeVisualFallback:
    async def enrich(
        self,
        *,
        pdf_path,
        checklist,
        native_context,
        analysis,
    ) -> ChecklistAnalysisResult:
        del pdf_path
        del checklist
        del native_context

        return analysis


class FailingSerializer:
    def serialize(
        self,
        result,
    ) -> bytes:
        del result

        raise RuntimeError(
            "serialize failed"
        )


def _result_builder() -> ChecklistResultBuilder:
    return ChecklistResultBuilder(
        dimension_validator=(
            AnswerDimensionValidator()
        )
    )


def _create_job(
    *,
    repository: SqliteJobRepository,
    storage: EphemeralFileStorage,
    source_filename: str,
):
    job_id = uuid4()

    repository.create(
        job_id,
        status=JobStatus.QUEUED,
        checklist_code=ChecklistCode.UUTE,
    )

    storage.save_input(
        job_id,
        b"%PDF-user-input",
        source_filename=source_filename,
    )

    return job_id


def _service(
    *,
    repository: SqliteJobRepository,
    storage: EphemeralFileStorage,
    answering_service,
    result_serializer,
    job_timeout_seconds: float,
) -> AnalysisPipelineService:
    return AnalysisPipelineService(
        repository=repository,
        storage=storage,
        checklist_repository=(
            FakeChecklistRepository()
        ),
        content_service=FakeContentService(),
        chunker=FakeChunker(),
        answering_service=answering_service,
        visual_fallback_service=FakeVisualFallback(),
        result_builder=_result_builder(),
        result_serializer=result_serializer,
        job_timeout_seconds=job_timeout_seconds,
    )


async def test_success_deletes_input_and_keeps_json_until_delivery(
    tmp_path: Path,
) -> None:
    """Worker удаляет PDF, но оставляет temporary result.json."""
    repository = SqliteJobRepository(
        tmp_path
        / "metadata"
        / "jobs.sqlite3"
    )

    storage = EphemeralFileStorage(
        tmp_path
        / "jobs"
    )

    job_id = _create_job(
        repository=repository,
        storage=storage,
        source_filename="ТЗ УУТЭ.pdf",
    )

    service = _service(
        repository=repository,
        storage=storage,
        answering_service=FakeAnsweringService(),
        result_serializer=(
            JsonChecklistResultSerializer()
        ),
        job_timeout_seconds=30,
    )

    await service.process(
        job_id=job_id,
        checklist_code=ChecklistCode.UUTE,
    )

    state = repository.get(
        job_id
    )

    assert state is not None

    assert (
        state.status
        == JobStatus.COMPLETED
    )

    assert (
        storage.has_input(
            job_id
        )
        is False
    )

    assert (
        storage.has_result(
            job_id
        )
        is True
    )

    payload = json.loads(
        storage.consume_result(
            job_id
        )
    )

    assert (
        payload["metadata"][
            "source_filename"
        ]
        == "ТЗ УУТЭ.pdf"
    )

    assert (
        payload["metadata"][
            "checklist_tag"
        ]
        == "УУТЭ"
    )

    assert (
        payload["questions"][0][
            "answer"
        ]
        == "3.93 т/ч"
    )

    assert (
        storage.has_result(
            job_id
        )
        is False
    )


async def test_failure_removes_all_temporary_files(
    tmp_path: Path,
) -> None:
    """Ошибка сериализации удаляет input/result artifacts."""
    repository = SqliteJobRepository(
        tmp_path
        / "metadata"
        / "jobs.sqlite3"
    )

    storage = EphemeralFileStorage(
        tmp_path
        / "jobs"
    )

    job_id = _create_job(
        repository=repository,
        storage=storage,
        source_filename="ТЗ.pdf",
    )

    service = _service(
        repository=repository,
        storage=storage,
        answering_service=FakeAnsweringService(),
        result_serializer=FailingSerializer(),
        job_timeout_seconds=30,
    )

    with pytest.raises(
        RuntimeError,
        match="serialize failed",
    ):
        await service.process(
            job_id=job_id,
            checklist_code=ChecklistCode.UUTE,
        )

    state = repository.get(
        job_id
    )

    assert state is not None

    assert (
        state.status
        == JobStatus.FAILED
    )

    assert (
        storage.has_input(
            job_id
        )
        is False
    )

    assert (
        storage.has_result(
            job_id
        )
        is False
    )


async def test_job_watchdog_marks_failed_and_cleans_files(
    tmp_path: Path,
) -> None:
    """Полный analysis job не должен выполняться бесконечно."""
    repository = SqliteJobRepository(
        tmp_path
        / "metadata"
        / "jobs.sqlite3"
    )

    storage = EphemeralFileStorage(
        tmp_path
        / "jobs"
    )

    job_id = _create_job(
        repository=repository,
        storage=storage,
        source_filename="slow.pdf",
    )

    service = _service(
        repository=repository,
        storage=storage,
        answering_service=SlowAnsweringService(),
        result_serializer=(
            JsonChecklistResultSerializer()
        ),
        job_timeout_seconds=0.01,
    )

    with pytest.raises(
        RuntimeError,
        match="Analysis exceeded 0.01 seconds",
    ):
        await service.process(
            job_id=job_id,
            checklist_code=ChecklistCode.UUTE,
        )

    state = repository.get(
        job_id
    )

    assert state is not None

    assert (
        state.status
        == JobStatus.FAILED
    )

    assert (
        state.error
        == (
            "RuntimeError: "
            "Analysis exceeded 0.01 seconds"
        )
    )

    assert (
        storage.has_input(
            job_id
        )
        is False
    )

    assert (
        storage.has_result(
            job_id
        )
        is False
    )
