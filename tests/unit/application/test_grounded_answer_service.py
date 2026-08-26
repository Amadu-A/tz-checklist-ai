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
    """Создать тестовый retrieved evidence."""
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
    """FOUND разрешён только при реальном supporting_text."""
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
                supporting_text=(
                    "Расход равен 3.93 т/ч."
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

    assert (
        result[0].output_answer
        == ""
    )


async def test_invented_number_is_downgraded() -> None:
    """Число в answer должно существовать в supporting evidence."""
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

    assert (
        result[0].output_answer
        == ""
    )


async def test_no_evidence_does_not_call_llm() -> None:
    """Если retrieval пуст, GPU-вызов вообще не нужен."""
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
