# tests/unit/application/test_checklist_answering_service.py

from app.application.services.checklist_answering_service import (
    ChecklistAnsweringService,
)
from app.domain.answers import (
    AnswerStatus,
    GroundedAnswer,
)
from app.domain.checklists import (
    ChecklistDefinition,
    ChecklistQuestion,
    ChecklistSection,
    ChecklistSheet,
)
from app.domain.enums import ChecklistCode
from app.domain.retrieval import (
    RetrievalIndex,
    RetrievalResult,
)


class FakeRetriever:
    """Фиксирует query, переданный retrieval-слою."""

    def __init__(self) -> None:
        self.queries: tuple[str, ...] = ()

    async def build_index(
        self,
        chunks,
    ) -> RetrievalIndex:
        del chunks

        return RetrievalIndex()

    async def retrieve_many(
        self,
        queries,
        index,
    ):
        del index

        self.queries = queries

        return tuple(
            RetrievalResult(
                query=query,
            )
            for query in queries
        )


class FakeAnswerService:
    """Возвращает пустой grounded answer без LLM."""

    async def extract(
        self,
        items,
    ):
        return tuple(
            GroundedAnswer(
                question_id=item.question_id,
                status=AnswerStatus.NOT_FOUND,
                confidence=0,
            )
            for item in items
        )


async def test_retrieval_query_contains_section_label_and_question() -> None:
    """Retrieval должен получать контекст, отсутствующий в Excel-вопросе."""
    retriever = FakeRetriever()

    service = ChecklistAnsweringService(
        retriever=retriever,
        answer_service=FakeAnswerService(),
        answer_batch_size=6,
    )

    checklist = ChecklistDefinition(
        code=ChecklistCode.UUTE,
        title="УУТЭ",
        description="Тест",
        source_workbook="test.xlsx",
        expected_question_count=1,
        sheets=(
            ChecklistSheet(
                id="main",
                title="2. УУТЭ",
                sections=(
                    ChecklistSection(
                        id="customer",
                        title="Сведения о Заказчике",
                        questions=(
                            ChecklistQuestion(
                                id="main-6",
                                source_number="6",
                                text=(
                                    "Какое наименование "
                                    "проектируемого объекта указано?"
                                ),
                                output_order=1,
                                label="Наименование объекта:",
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    await service.analyze(
        checklist=checklist,
        chunks=(),
    )

    assert retriever.queries == (
        (
            "Сведения о Заказчике\n"
            "Наименование объекта\n"
            "Какое наименование "
            "проектируемого объекта указано?"
        ),
    )
