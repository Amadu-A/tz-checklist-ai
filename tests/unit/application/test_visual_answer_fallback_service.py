# tests/unit/application/test_visual_answer_fallback_service.py

from pathlib import Path

from app.application.services.visual_answer_fallback_service import (
    VisualAnswerFallbackService,
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
    DocumentVisionContext,
    PageVisionResult,
    PdfPageText,
)
from app.domain.enums import ChecklistCode


class FakeContentService:
    """Фиксирует страницы, реально отправленные в VLM."""

    def __init__(self) -> None:
        self.page_numbers: tuple[int, ...] | None = None

    async def analyze_visual_pages(
        self,
        pdf_path: Path,
        *,
        page_numbers: tuple[int, ...],
    ) -> DocumentVisionContext:
        del pdf_path

        self.page_numbers = page_numbers

        return DocumentVisionContext(
            pages=(
                PageVisionResult(
                    page_number=2,
                    extracted_text=(
                        "Расход теплоносителя составляет 3.93 т/ч."
                    ),
                ),
            )
        )


class FakeChunker:
    """Создаёт один visual chunk."""

    def chunk(
        self,
        context: DocumentTextContext,
    ):
        from app.domain.retrieval import DocumentChunk

        return (
            DocumentChunk(
                chunk_id="vlm-p2-c1",
                page_number=2,
                chunk_index=1,
                text=context.pages[0].text,
            ),
        )


class FakeRetriever:
    """Возвращает visual fragment как лучший hit."""

    async def build_index(
        self,
        chunks,
    ):
        return chunks

    async def retrieve_many(
        self,
        queries,
        index,
    ):
        from app.domain.retrieval import (
            RetrievalHit,
            RetrievalResult,
        )

        return tuple(
            RetrievalResult(
                query=query,
                hits=(
                    RetrievalHit(
                        chunk=index[0],
                        lexical_score=1,
                        semantic_score=1,
                        hybrid_score=1,
                    ),
                ),
            )
            for query in queries
        )


class FakeAnswerService:
    """Возвращает найденный visual answer."""

    async def extract(
        self,
        items,
    ):
        return tuple(
            GroundedAnswer(
                question_id=item.question_id,
                status=AnswerStatus.FOUND,
                answer="3.93 т/ч",
                confidence=0.95,
                source_pages=(2,),
                supporting_text=(
                    "Расход теплоносителя составляет 3.93 т/ч."
                ),
            )
            for item in items
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
                                text="Какой расход теплоносителя?",
                                output_order=1,
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


async def test_unresolved_question_uses_only_weak_scan_page() -> None:
    """VLM должна получить только слабую страницу, а не весь PDF."""
    content_service = FakeContentService()

    service = VisualAnswerFallbackService(
        content_service=content_service,
        chunker=FakeChunker(),
        retriever=FakeRetriever(),
        answer_service=FakeAnswerService(),
        answer_batch_size=6,
        max_pages=12,
        weak_page_max_chars=80,
    )

    native_context = DocumentTextContext(
        pages=(
            PdfPageText(
                page_number=1,
                text=(
                    "Большой полноценный native текст страницы "
                    "с техническим описанием объекта."
                )
                * 4,
            ),
            PdfPageText(
                page_number=2,
                text="",
                image_count=1,
            ),
        )
    )

    analysis = ChecklistAnalysisResult(
        checklist_code=ChecklistCode.UUTE,
        answers=(
            GroundedAnswer(
                question_id="q1",
                status=AnswerStatus.NOT_FOUND,
                confidence=0,
            ),
        ),
    )

    result = await service.enrich(
        pdf_path=Path("/tmp/input.pdf"),
        checklist=_checklist(),
        native_context=native_context,
        analysis=analysis,
    )

    assert (
        content_service.page_numbers
        == (2,)
    )

    assert (
        result.answers[0].status
        == AnswerStatus.FOUND
    )

    assert (
        result.answers[0].output_answer
        == "3.93 т/ч"
    )


async def test_visual_model_is_not_called_when_all_answers_are_found() -> None:
    """Успешный native pipeline не должен расходовать VLM."""
    content_service = FakeContentService()

    service = VisualAnswerFallbackService(
        content_service=content_service,
        chunker=FakeChunker(),
        retriever=FakeRetriever(),
        answer_service=FakeAnswerService(),
        answer_batch_size=6,
        max_pages=12,
        weak_page_max_chars=80,
    )

    analysis = ChecklistAnalysisResult(
        checklist_code=ChecklistCode.UUTE,
        answers=(
            GroundedAnswer(
                question_id="q1",
                status=AnswerStatus.FOUND,
                answer="3.93 т/ч",
                confidence=0.95,
                source_pages=(1,),
                supporting_text="Расход 3.93 т/ч.",
            ),
        ),
    )

    result = await service.enrich(
        pdf_path=Path("/tmp/input.pdf"),
        checklist=_checklist(),
        native_context=DocumentTextContext(
            pages=(
                PdfPageText(
                    page_number=1,
                    text="Полный native text.",
                ),
            )
        ),
        analysis=analysis,
    )

    assert result == analysis

    assert (
        content_service.page_numbers
        is None
    )
    