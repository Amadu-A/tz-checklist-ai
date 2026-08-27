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
    DocumentChunk,
    RetrievalHit,
    RetrievalIndex,
    RetrievalResult,
)


class FakeRetriever:
    """Фиксирует query и возвращает заданные retrieval hits."""

    def __init__(
        self,
        *,
        hits: tuple[
            RetrievalHit,
            ...,
        ] = (),
    ) -> None:
        self.queries: tuple[
            str,
            ...,
        ] = ()

        self._hits = hits

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
                hits=self._hits,
            )
            for query in queries
        )


class FakeAnswerService:
    """Фиксирует evidence, переданный LLM answer layer."""

    def __init__(self) -> None:
        self.items = ()

        self.calls = 0

    async def extract(
        self,
        items,
    ):
        self.calls += 1

        self.items = items

        return tuple(
            GroundedAnswer(
                question_id=item.question_id,
                status=AnswerStatus.NOT_FOUND,
                confidence=0,
            )
            for item in items
        )


def _object_name_checklist() -> ChecklistDefinition:
    """Создать минимальный checklist с полем наименования объекта."""
    return ChecklistDefinition(
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
                                    "проектируемого объекта "
                                    "указано?"
                                ),
                                output_order=1,
                                label=(
                                    "Наименование объекта:"
                                ),
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


async def test_retrieval_and_answer_receive_question_context() -> None:
    """Section и label должны помогать retrieval и answer extraction."""
    retriever = FakeRetriever()

    answer_service = FakeAnswerService()

    service = ChecklistAnsweringService(
        retriever=retriever,
        answer_service=answer_service,
        answer_batch_size=6,
    )

    await service.analyze(
        checklist=_object_name_checklist(),
        chunks=(),
    )

    expected_context = (
        "Сведения о Заказчике\n"
        "Наименование объекта\n"
        "Какое наименование "
        "проектируемого объекта указано?"
    )

    assert (
        retriever.queries
        == (
            expected_context,
        )
    )

    assert (
        answer_service.calls
        == 1
    )

    assert (
        len(
            answer_service.items
        )
        == 1
    )

    assert (
        answer_service
        .items[0]
        .question_text
        == expected_context
    )


async def test_explicit_subscriber_object_name_skips_llm() -> None:
    """Явный Абонент должен победить название инженерной системы."""
    retriever = FakeRetriever(
        hits=(
            RetrievalHit(
                chunk=DocumentChunk(
                    chunk_id="p2-c0",
                    page_number=2,
                    chunk_index=0,
                    text=(
                        "Узел учета тепловой энергии.\n"
                        "Проектная документация.\n"
                        "Абонент: "
                        "Здание центрального склада.\n"
                        "Адрес: Московская область."
                    ),
                ),
                lexical_score=0.95,
                semantic_score=0.98,
                hybrid_score=0.9695,
            ),
        )
    )

    answer_service = FakeAnswerService()

    service = ChecklistAnsweringService(
        retriever=retriever,
        answer_service=answer_service,
        answer_batch_size=6,
    )

    result = await service.analyze(
        checklist=_object_name_checklist(),
        chunks=(),
    )

    assert (
        answer_service.calls
        == 0
    )

    assert (
        len(
            result.answers
        )
        == 1
    )

    answer = result.answers[
        0
    ]

    assert (
        answer.status
        == AnswerStatus.FOUND
    )

    assert (
        answer.output_answer
        == "Здание центрального склада"
    )

    assert (
        answer.source_pages
        == (2,)
    )

    assert (
        answer.supporting_text
        == (
            "Абонент: "
            "Здание центрального склада."
        )
    )


async def test_explicit_object_name_has_priority_over_subscriber() -> None:
    """Прямое поле Наименование объекта сильнее fallback Абонент."""
    retriever = FakeRetriever(
        hits=(
            RetrievalHit(
                chunk=DocumentChunk(
                    chunk_id="p1-c0",
                    page_number=1,
                    chunk_index=0,
                    text=(
                        "Абонент: "
                        "Эксплуатационная организация.\n"
                        "Наименование объекта: "
                        "Здание насосной станции № 2."
                    ),
                ),
                lexical_score=0.9,
                semantic_score=0.9,
                hybrid_score=0.9,
            ),
        )
    )

    answer_service = FakeAnswerService()

    service = ChecklistAnsweringService(
        retriever=retriever,
        answer_service=answer_service,
        answer_batch_size=6,
    )

    result = await service.analyze(
        checklist=_object_name_checklist(),
        chunks=(),
    )

    assert (
        result.answers[0].output_answer
        == "Здание насосной станции № 2"
    )

    assert (
        answer_service.calls
        == 0
    )


async def test_object_name_can_be_on_next_line() -> None:
    """PDF extraction может перенести value после двоеточия."""
    retriever = FakeRetriever(
        hits=(
            RetrievalHit(
                chunk=DocumentChunk(
                    chunk_id="p2-c0",
                    page_number=2,
                    chunk_index=0,
                    text=(
                        "Абонент:\n"
                        "Здание центрального склада\n"
                        "Адрес: Московская область"
                    ),
                ),
                lexical_score=0.9,
                semantic_score=0.9,
                hybrid_score=0.9,
            ),
        )
    )

    answer_service = FakeAnswerService()

    service = ChecklistAnsweringService(
        retriever=retriever,
        answer_service=answer_service,
        answer_batch_size=6,
    )

    result = await service.analyze(
        checklist=_object_name_checklist(),
        chunks=(),
    )

    assert (
        result.answers[0].output_answer
        == "Здание центрального склада"
    )

    assert (
        answer_service.calls
        == 0
    )


async def test_unrelated_question_is_not_pre_resolved() -> None:
    """Явный Абонент не должен влиять на другой вопрос."""
    checklist = ChecklistDefinition(
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
                        id="heating",
                        title="Система отопления",
                        questions=(
                            ChecklistQuestion(
                                id="main-17",
                                source_number="17",
                                text=(
                                    "Какая температура "
                                    "теплоносителя указана?"
                                ),
                                output_order=1,
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )

    retriever = FakeRetriever(
        hits=(
            RetrievalHit(
                chunk=DocumentChunk(
                    chunk_id="p2-c0",
                    page_number=2,
                    chunk_index=0,
                    text=(
                        "Абонент: "
                        "Здание центрального склада."
                    ),
                ),
                lexical_score=0.5,
                semantic_score=0.5,
                hybrid_score=0.5,
            ),
        )
    )

    answer_service = FakeAnswerService()

    service = ChecklistAnsweringService(
        retriever=retriever,
        answer_service=answer_service,
        answer_batch_size=6,
    )

    await service.analyze(
        checklist=checklist,
        chunks=(),
    )

    assert (
        answer_service.calls
        == 1
    )

    assert (
        answer_service.items[0].question_id
        == "main-17"
    )
