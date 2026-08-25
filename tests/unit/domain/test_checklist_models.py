# tests/unit/domain/test_checklist_models.py

import pytest
from pydantic import ValidationError

from app.domain.checklists import (
    ChecklistDefinition,
    ChecklistQuestion,
    ChecklistSection,
    ChecklistSheet,
)
from app.domain.enums import ChecklistCode


def test_definition_rejects_wrong_question_count() -> None:
    """Pydantic должен отклонить поврежденный checklist."""
    question = ChecklistQuestion(
        id="main-1",
        source_number="1",
        text="Вопрос",
        output_order=1,
    )

    with pytest.raises(
        ValidationError
    ):
        ChecklistDefinition(
            code=ChecklistCode.UUTE,
            title="УУТЭ",
            description="Описание",
            source_workbook=(
                "source.xlsx"
            ),
            expected_question_count=2,
            sheets=(
                ChecklistSheet(
                    id="main",
                    title="Sheet",
                    sections=(
                        ChecklistSection(
                            id="section-1",
                            title="Раздел",
                            questions=(
                                question,
                            ),
                        ),
                    ),
                ),
            ),
        )
        