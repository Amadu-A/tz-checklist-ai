# tests/unit/application/test_grounded_answer_service.py

from app.application.services.grounded_answer_service import (
    GroundedAnswerService,
)
from app.domain.answers import (
    AnswerCandidate,
    AnswerStatus,
    QuestionEvidence,
)
from app.domain.retrieval import (
    DocumentChunk,
    RetrievalHit,
)


class FakeAnswerClient:
    """Детерминированный ответ LLM для unit tests."""

    def __init__(
        self,
        candidates: tuple[AnswerCandidate, ...],
    ) -> None:
        self._candidates = candidates
        self.calls = 0

    async def extract(
        self,
        items: tuple[QuestionEvidence, ...],
    ) -> tuple[AnswerCandidate, ...]:
        del items

        self.calls += 1

        return self._candidates


def _evidence() -> QuestionEvidence:
    """Создать retrieved evidence."""
    return QuestionEvidence(
        question_id="q1",
        question_text="Какой расход теплоносителя?",
        hits=(
            RetrievalHit(
                chunk=DocumentChunk(
                    chunk_id="p4-c1",
                    page_number=4,
                    chunk_index=1,
                    text=(
                        "Расход теплоносителя "
                        "составляет 3.93 т/ч."
                    ),
                ),
                lexical_score=0.8,
                semantic_score=0.9,
                hybrid_score=0.865,
            ),
        ),
    )


async def test_exact_supporting_text_allows_found_answer() -> None:
    """FOUND разрешён при реальном supporting_text."""
    client = FakeAnswerClient(
        (
            AnswerCandidate(
                question_id="q1",
                status=AnswerStatus.FOUND,
                answer="3.93 т/ч",
                confidence=0.95,
                supporting_text=(
                    "Расход теплоносителя "
                    "составляет 3.93 т/ч."
                ),
            ),
        )
    )

    service = GroundedAnswerService(
        answer_client=client,
        found_min_confidence=0.75,
    )

    result = await service.extract(
        (
            _evidence(),
        )
    )

    assert (
        result[0].status
        == AnswerStatus.FOUND
    )

    assert (
        result[0].output_answer
        == "3.93 т/ч"
    )

    assert (
        result[0].source_pages
        == (4,)
    )


async def test_invented_support_is_downgraded() -> None:
    """LLM не может подтвердить ответ придуманным evidence."""
    client = FakeAnswerClient(
        (
            AnswerCandidate(
                question_id="q1",
                status=AnswerStatus.FOUND,
                answer="3.93 т/ч",
                confidence=0.99,
                supporting_text="Расход равен 3.93 т/ч.",
            ),
        )
    )

    service = GroundedAnswerService(
        answer_client=client,
        found_min_confidence=0.75,
    )

    result = await service.extract(
        (
            _evidence(),
        )
    )

    assert (
        result[0].status
        == AnswerStatus.LOW_CONFIDENCE
    )

    assert (
        result[0].output_answer
        == ""
    )


async def test_invented_number_is_downgraded() -> None:
    """Число answer должно существовать в supporting evidence."""
    client = FakeAnswerClient(
        (
            AnswerCandidate(
                question_id="q1",
                status=AnswerStatus.FOUND,
                answer="5.0 т/ч",
                confidence=0.99,
                supporting_text=(
                    "Расход теплоносителя "
                    "составляет 3.93 т/ч."
                ),
            ),
        )
    )

    service = GroundedAnswerService(
        answer_client=client,
        found_min_confidence=0.75,
    )

    result = await service.extract(
        (
            _evidence(),
        )
    )

    assert (
        result[0].status
        == AnswerStatus.LOW_CONFIDENCE
    )


async def test_no_evidence_does_not_call_llm() -> None:
    """Без retrieval evidence GPU-вызов не нужен."""
    client = FakeAnswerClient(
        ()
    )

    service = GroundedAnswerService(
        answer_client=client,
        found_min_confidence=0.75,
    )

    result = await service.extract(
        (
            QuestionEvidence(
                question_id="q1",
                question_text="Какой расход?",
            ),
        )
    )

    assert (
        result[0].status
        == AnswerStatus.NOT_FOUND
    )

    assert (
        client.calls
        == 0
    )


async def test_value_from_another_system_is_downgraded() -> None:
    """Нагрузка отопления не является нагрузкой тех. нужд."""
    evidence = QuestionEvidence(
        question_id="main-11",
        question_text=(
            "Какая максимальная тепловая нагрузка "
            "на технологические нужды указана?"
        ),
        hits=(
            RetrievalHit(
                chunk=DocumentChunk(
                    chunk_id="p6-c1",
                    page_number=6,
                    chunk_index=1,
                    text=(
                        "Подключаемая тепловая нагрузка: "
                        "Q = 0,098288 Гкал/ч - на отопление."
                    ),
                ),
                lexical_score=0.6,
                semantic_score=0.9,
                hybrid_score=0.8,
            ),
        ),
    )

    client = FakeAnswerClient(
        (
            AnswerCandidate(
                question_id="main-11",
                status=AnswerStatus.FOUND,
                answer="0,098288 Гкал/ч",
                confidence=0.99,
                supporting_text=(
                    "Подключаемая тепловая нагрузка: "
                    "Q = 0,098288 Гкал/ч - на отопление."
                ),
            ),
        )
    )

    service = GroundedAnswerService(
        answer_client=client,
        found_min_confidence=0.75,
    )

    result = await service.extract(
        (
            evidence,
        )
    )

    assert (
        result[0].status
        == AnswerStatus.LOW_CONFIDENCE
    )


async def test_value_from_requested_system_is_allowed() -> None:
    """Нагрузка отопления проходит для вопроса об отоплении."""
    evidence = QuestionEvidence(
        question_id="main-8",
        question_text=(
            "Какая максимальная тепловая нагрузка "
            "на систему отопления указана?"
        ),
        hits=(
            RetrievalHit(
                chunk=DocumentChunk(
                    chunk_id="p6-c1",
                    page_number=6,
                    chunk_index=1,
                    text=(
                        "Подключаемая тепловая нагрузка: "
                        "Q = 0,098288 Гкал/ч - на отопление."
                    ),
                ),
                lexical_score=0.8,
                semantic_score=0.95,
                hybrid_score=0.9,
            ),
        ),
    )

    client = FakeAnswerClient(
        (
            AnswerCandidate(
                question_id="main-8",
                status=AnswerStatus.FOUND,
                answer="0,098288 Гкал/ч",
                confidence=0.99,
                supporting_text=(
                    "Подключаемая тепловая нагрузка: "
                    "Q = 0,098288 Гкал/ч - на отопление."
                ),
            ),
        )
    )

    service = GroundedAnswerService(
        answer_client=client,
        found_min_confidence=0.75,
    )

    result = await service.extract(
        (
            evidence,
        )
    )

    assert (
        result[0].status
        == AnswerStatus.FOUND
    )


async def test_generic_support_without_subject_is_not_blocked() -> None:
    """Нейтральный evidence для системы не должен блокироваться."""
    evidence = QuestionEvidence(
        question_id="main-17",
        question_text=(
            "Какая температура теплоносителя "
            "в системе отопления указана?"
        ),
        hits=(
            RetrievalHit(
                chunk=DocumentChunk(
                    chunk_id="p7-c1",
                    page_number=7,
                    chunk_index=1,
                    text=(
                        "Температурный график теплоснабжения: "
                        "95 °С в подающем трубопроводе; "
                        "70 °С в обратном трубопроводе."
                    ),
                ),
                lexical_score=0.8,
                semantic_score=0.95,
                hybrid_score=0.9,
            ),
        ),
    )

    client = FakeAnswerClient(
        (
            AnswerCandidate(
                question_id="main-17",
                status=AnswerStatus.FOUND,
                answer="95 °С / 70 °С",
                confidence=0.98,
                supporting_text=(
                    "Температурный график теплоснабжения: "
                    "95 °С в подающем трубопроводе; "
                    "70 °С в обратном трубопроводе."
                ),
            ),
        )
    )

    service = GroundedAnswerService(
        answer_client=client,
        found_min_confidence=0.75,
    )

    result = await service.extract(
        (
            evidence,
        )
    )

    assert (
        result[0].status
        == AnswerStatus.FOUND
    )


async def test_common_accounting_requires_explicit_relation() -> None:
    """Простое упоминание отопления не доказывает общий учёт."""
    evidence = QuestionEvidence(
        question_id="main-13",
        question_text=(
            "Какие системы для общего учета указаны "
            "(отопление, ГВС, вентиляция)?"
        ),
        hits=(
            RetrievalHit(
                chunk=DocumentChunk(
                    chunk_id="p37-c1",
                    page_number=37,
                    chunk_index=1,
                    text=(
                        "Отопление Qот = 0,098288 Гкал/ч. "
                        "ГВС Qгвс = 0,000 Гкал/ч."
                    ),
                ),
                lexical_score=0.8,
                semantic_score=0.9,
                hybrid_score=0.85,
            ),
        ),
    )

    client = FakeAnswerClient(
        (
            AnswerCandidate(
                question_id="main-13",
                status=AnswerStatus.FOUND,
                answer="отопление",
                confidence=1.0,
                supporting_text=(
                    "Отопление Qот = 0,098288 Гкал/ч."
                ),
            ),
        )
    )

    service = GroundedAnswerService(
        answer_client=client,
        found_min_confidence=0.60,
    )

    result = await service.extract(
        (
            evidence,
        )
    )

    assert (
        result[0].status
        == AnswerStatus.LOW_CONFIDENCE
    )

    assert (
        result[0].output_answer
        == ""
    )


async def test_separate_accounting_requires_explicit_relation() -> None:
    """Простое упоминание системы не доказывает отдельный учёт."""
    evidence = QuestionEvidence(
        question_id="main-14",
        question_text=(
            "Какие системы для отдельного учета указаны "
            "(отопление, ГВС, ХВС)?"
        ),
        hits=(
            RetrievalHit(
                chunk=DocumentChunk(
                    chunk_id="p37-c1",
                    page_number=37,
                    chunk_index=1,
                    text=(
                        "Отопление Qот = 0,098288 Гкал/ч. "
                        "ГВС Qгвс = 0,000 Гкал/ч."
                    ),
                ),
                lexical_score=0.8,
                semantic_score=0.9,
                hybrid_score=0.85,
            ),
        ),
    )

    client = FakeAnswerClient(
        (
            AnswerCandidate(
                question_id="main-14",
                status=AnswerStatus.FOUND,
                answer="отопление",
                confidence=1.0,
                supporting_text=(
                    "Отопление Qот = 0,098288 Гкал/ч."
                ),
            ),
        )
    )

    service = GroundedAnswerService(
        answer_client=client,
        found_min_confidence=0.60,
    )

    result = await service.extract(
        (
            evidence,
        )
    )

    assert (
        result[0].status
        == AnswerStatus.LOW_CONFIDENCE
    )


async def test_explicit_common_accounting_is_allowed() -> None:
    """Явно указанный общий учёт должен проходить."""
    evidence = QuestionEvidence(
        question_id="main-13",
        question_text=(
            "Какие системы для общего учета указаны?"
        ),
        hits=(
            RetrievalHit(
                chunk=DocumentChunk(
                    chunk_id="p5-c1",
                    page_number=5,
                    chunk_index=1,
                    text=(
                        "Общий учет тепловой энергии "
                        "предусмотрен для системы отопления."
                    ),
                ),
                lexical_score=1.0,
                semantic_score=1.0,
                hybrid_score=1.0,
            ),
        ),
    )

    client = FakeAnswerClient(
        (
            AnswerCandidate(
                question_id="main-13",
                status=AnswerStatus.FOUND,
                answer="отопление",
                confidence=0.95,
                supporting_text=(
                    "Общий учет тепловой энергии "
                    "предусмотрен для системы отопления."
                ),
            ),
        )
    )

    service = GroundedAnswerService(
        answer_client=client,
        found_min_confidence=0.60,
    )

    result = await service.extract(
        (
            evidence,
        )
    )

    assert (
        result[0].status
        == AnswerStatus.FOUND
    )

    assert (
        result[0].output_answer
        == "отопление"
    )
