# tests/unit/application/test_grounded_subject_context.py

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
    """Возвращает один заранее заданный LLM candidate."""

    def __init__(
        self,
        candidate: AnswerCandidate,
    ) -> None:
        self._candidate = candidate

    async def extract(
        self,
        items,
    ):
        del items

        return (
            self._candidate,
        )


def _heating_evidence(
    *,
    question_id: str,
    question_text: str,
) -> QuestionEvidence:
    """Evidence, в котором значения явно принадлежат отоплению."""
    return QuestionEvidence(
        question_id=question_id,
        question_text=question_text,
        hits=(
            RetrievalHit(
                chunk=DocumentChunk(
                    chunk_id="p6-c1",
                    page_number=6,
                    chunk_index=1,
                    text=(
                        "Система отопления – зависимая. "
                        "Температурный график теплоснабжения: "
                        "95 °С в подающем трубопроводе; "
                        "70 °С в обратном трубопроводе. "
                        "Давление в подающем трубопроводе "
                        "58 м.в.ст., в обратном 35 м.в.ст."
                    ),
                ),
                lexical_score=0.8,
                semantic_score=0.9,
                hybrid_score=0.865,
            ),
        ),
    )


async def test_heating_temperature_is_allowed_for_heating_question() -> None:
    """Нейтральная цитата должна использовать ближайший heating context."""
    candidate = AnswerCandidate(
        question_id="main-17",
        status=AnswerStatus.FOUND,
        answer="95 °С; 70 °С",
        confidence=1.0,
        supporting_text=(
            "95 °С в подающем трубопроводе; "
            "70 °С в обратном трубопроводе."
        ),
    )

    service = GroundedAnswerService(
        answer_client=FakeAnswerClient(
            candidate
        ),
        found_min_confidence=0.60,
    )

    result = await service.extract(
        (
            _heating_evidence(
                question_id="main-17",
                question_text=(
                    "Сведения о системе отопления\n"
                    "Какая температура теплоносителя "
                    "в подающем и обратном трубопроводах "
                    "системы отопления указана?"
                ),
            ),
        )
    )

    assert (
        result[0].status
        == AnswerStatus.FOUND
    )


async def test_heating_temperature_is_rejected_for_ventilation() -> None:
    """Heating context нельзя использовать как ventilation answer."""
    candidate = AnswerCandidate(
        question_id="main-23",
        status=AnswerStatus.FOUND,
        answer="95 °С; 70 °С",
        confidence=1.0,
        supporting_text=(
            "95 °С в подающем трубопроводе; "
            "70 °С в обратном трубопроводе."
        ),
    )

    service = GroundedAnswerService(
        answer_client=FakeAnswerClient(
            candidate
        ),
        found_min_confidence=0.60,
    )

    result = await service.extract(
        (
            _heating_evidence(
                question_id="main-23",
                question_text=(
                    "Сведения о системе вентиляции\n"
                    "Какая температура теплоносителя "
                    "в подающем и обратном трубопроводах "
                    "системы вентиляции указана?"
                ),
            ),
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


async def test_heating_pressure_is_rejected_for_ventilation() -> None:
    """Heating pressure нельзя переносить в ventilation section."""
    candidate = AnswerCandidate(
        question_id="main-24",
        status=AnswerStatus.FOUND,
        answer="58 м.в.ст.; 35 м.в.ст.",
        confidence=1.0,
        supporting_text=(
            "Давление в подающем трубопроводе "
            "58 м.в.ст., в обратном 35 м.в.ст."
        ),
    )

    service = GroundedAnswerService(
        answer_client=FakeAnswerClient(
            candidate
        ),
        found_min_confidence=0.60,
    )

    result = await service.extract(
        (
            _heating_evidence(
                question_id="main-24",
                question_text=(
                    "Сведения о системе вентиляции\n"
                    "Какое давление теплоносителя "
                    "в подающем и обратном трубопроводах "
                    "системы вентиляции указано?"
                ),
            ),
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
