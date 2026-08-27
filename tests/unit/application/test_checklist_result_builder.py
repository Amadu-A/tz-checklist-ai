# tests/unit/application/test_checklist_result_builder.py

from uuid import uuid4

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
from app.domain.enums import (
    ChecklistCode,
    ChecklistTag,
)


def _checklist() -> ChecklistDefinition:
    return ChecklistDefinition(
        code=ChecklistCode.SPD,
        title="СПД",
        description="Станция повышения давления.",
        source_workbook="test.xlsx",
        expected_question_count=3,
        sheets=(
            ChecklistSheet(
                id="main",
                title="СПД",
                sections=(
                    ChecklistSection(
                        id="section",
                        title="Тест",
                        questions=(
                            ChecklistQuestion(
                                id="q1",
                                source_number="12",
                                text=(
                                    "Какое рабочее давление "
                                    "СПД указано?"
                                ),
                                output_order=1,
                            ),
                            ChecklistQuestion(
                                id="q2",
                                source_number="19",
                                text=(
                                    "Какой диаметр "
                                    "трубопровода указан?"
                                ),
                                output_order=2,
                            ),
                            ChecklistQuestion(
                                id="q3",
                                source_number="18",
                                text=(
                                    "Какой материал "
                                    "проточной части указан?"
                                ),
                                output_order=3,
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def _found(
    question_id: str,
    answer: str,
) -> GroundedAnswer:
    return GroundedAnswer(
        question_id=question_id,
        status=AnswerStatus.FOUND,
        answer=answer,
        confidence=1.0,
        source_pages=(1,),
        supporting_text=answer,
    )


def test_builder_blanks_dimensionally_invalid_answers() -> None:
    """Очевидно неправильные размерности не выходят клиенту."""
    builder = ChecklistResultBuilder(
        dimension_validator=(
            AnswerDimensionValidator()
        )
    )

    result = builder.build(
        request_id=uuid4(),
        source_filename="ТЗ СПД.pdf",
        checklist=_checklist(),
        analysis=ChecklistAnalysisResult(
            checklist_code=ChecklistCode.SPD,
            answers=(
                _found(
                    "q1",
                    "3~400В 50Гц",
                ),
                _found(
                    "q2",
                    (
                        "Трубопровод окрашен "
                        "эмалью ПФ-115"
                    ),
                ),
                _found(
                    "q3",
                    "нержавеющая сталь",
                ),
            ),
        ),
        processing_seconds=12.3456,
        search_seconds=10.1111,
    )

    assert (
        result.metadata.checklist_tag
        == ChecklistTag.SPD
    )

    assert (
        result.metadata.source_filename
        == "ТЗ СПД.pdf"
    )

    assert [
        item.answer
        for item in result.questions
    ] == [
        "",
        "",
        "нержавеющая сталь",
    ]


def test_builder_preserves_question_numbers() -> None:
    """JSON должен использовать номера исходного checklist."""
    builder = ChecklistResultBuilder(
        dimension_validator=(
            AnswerDimensionValidator()
        )
    )

    result = builder.build(
        request_id=uuid4(),
        source_filename="test.pdf",
        checklist=_checklist(),
        analysis=ChecklistAnalysisResult(
            checklist_code=ChecklistCode.SPD,
            answers=(),
        ),
        processing_seconds=1,
        search_seconds=0.5,
    )

    assert [
        item.number
        for item in result.questions
    ] == [
        "12",
        "19",
        "18",
    ]
    