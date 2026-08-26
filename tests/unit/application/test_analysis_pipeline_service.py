# tests/unit/application/test_analysis_pipeline_service.py

from pathlib import Path
from uuid import uuid4

import pytest

from app.application.services.analysis_pipeline_service import (
    AnalysisPipelineService,
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
from app.infrastructure.storage.ephemeral_file_storage import (
    EphemeralFileStorage,
)


def _checklist() -> ChecklistDefinition:
    return ChecklistDefinition(
        code=ChecklistCode.UUTE,
        title="УУТЭ",
        description="Тест",
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
                                text="Какой расход?",
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
        assert code == ChecklistCode.UUTE

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
                    text="Расход составляет 3.93 т/ч.",
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
                        "Расход составляет 3.93 т/ч."
                    ),
                ),
            ),
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


class FakeRenderer:
    def __init__(
        self,
        *,
        fail: bool = False,
    ) -> None:
        self._fail = fail

    def render(
        self,
        *,
        checklist,
        analysis,
    ) -> bytes:
        del checklist
        del analysis

        if self._fail:
            raise RuntimeError(
                "render failed"
            )

        return b"%PDF-generated-report"


async def test_success_deletes_input_but_keeps_result_until_delivery(
    tmp_path: Path,
) -> None:
    """После worker исходный ТЗ должен исчезнуть."""
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
        status=JobStatus.QUEUED,
        checklist_code=ChecklistCode.UUTE,
    )

    storage.save_input(
        job_id,
        b"%PDF-user-input",
    )

    service = AnalysisPipelineService(
        repository=repository,
        storage=storage,
        checklist_repository=FakeChecklistRepository(),
        content_service=FakeContentService(),
        chunker=FakeChunker(),
        answering_service=FakeAnsweringService(),
        visual_fallback_service=FakeVisualFallback(),
        report_renderer=FakeRenderer(),
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

    result = storage.consume_result(
        job_id
    )

    assert (
        result
        == b"%PDF-generated-report"
    )

    assert (
        storage.has_result(
            job_id
        )
        is False
    )


async def test_failure_removes_all_user_binary_files(
    tmp_path: Path,
) -> None:
    """При ошибке на сервере не должен остаться ни input, ни result."""
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
        status=JobStatus.QUEUED,
        checklist_code=ChecklistCode.UUTE,
    )

    storage.save_input(
        job_id,
        b"%PDF-user-input",
    )

    service = AnalysisPipelineService(
        repository=repository,
        storage=storage,
        checklist_repository=FakeChecklistRepository(),
        content_service=FakeContentService(),
        chunker=FakeChunker(),
        answering_service=FakeAnsweringService(),
        visual_fallback_service=FakeVisualFallback(),
        report_renderer=FakeRenderer(
            fail=True
        ),
    )

    with pytest.raises(
        RuntimeError,
        match="render failed",
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
