# tests/unit/infrastructure/test_reportlab_checklist_renderer.py

import pymupdf

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
from app.domain.enums import ChecklistCode
from app.infrastructure.reporting.reportlab_checklist_renderer import (
    ReportLabChecklistRenderer,
)


def _checklist() -> ChecklistDefinition:
    """Минимальный чек-лист для проверки renderer."""
    return ChecklistDefinition(
        code=ChecklistCode.UUTE,
        title="Тестовый чек-лист УУТЭ",
        description="Тест",
        source_workbook="test.xlsx",
        expected_question_count=2,
        sheets=(
            ChecklistSheet(
                id="main",
                title="УУТЭ",
                sections=(
                    ChecklistSection(
                        id="main-section",
                        title="Основные вопросы",
                        questions=(
                            ChecklistQuestion(
                                id="q1",
                                source_number="1",
                                text="Какой расход теплоносителя?",
                                output_order=1,
                            ),
                            ChecklistQuestion(
                                id="q2",
                                source_number="2",
                                text="Какое давление?",
                                output_order=2,
                            ),
                        ),
                    ),
                ),
            ),
        ),
    )


def test_renderer_outputs_three_column_pdf_and_blank_unresolved_answer() -> None:
    """В PDF должны попасть только grounded FOUND-ответы."""
    checklist = _checklist()

    analysis = ChecklistAnalysisResult(
        checklist_code=ChecklistCode.UUTE,
        answers=(
            GroundedAnswer(
                question_id="q1",
                status=AnswerStatus.FOUND,
                answer="3.93 т/ч",
                confidence=0.95,
                source_pages=(4,),
                supporting_text=(
                    "Расход теплоносителя составляет 3.93 т/ч."
                ),
            ),
            GroundedAnswer(
                question_id="q2",
                status=AnswerStatus.NOT_FOUND,
                confidence=0,
            ),
        ),
    )

    renderer = ReportLabChecklistRenderer()

    pdf_bytes = renderer.render(
        checklist=checklist,
        analysis=analysis,
    )

    assert pdf_bytes.startswith(
        b"%PDF"
    )

    document = pymupdf.open(
        stream=pdf_bytes,
        filetype="pdf",
    )

    text = "\n".join(
        page.get_text()
        for page in document
    )

    assert "№" in text
    assert "Вопрос" in text
    assert "Ответ" in text

    assert "Какой расход теплоносителя?" in text
    assert "3.93 т/ч" in text

    assert "Какое давление?" in text

    assert "NOT_FOUND" not in text
    assert "LOW_CONFIDENCE" not in text
    