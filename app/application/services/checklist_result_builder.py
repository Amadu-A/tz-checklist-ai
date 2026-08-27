# app/application/services/checklist_result_builder.py

from datetime import UTC, datetime
from uuid import UUID

from app.application.services.answer_dimension_validator import (
    AnswerDimensionValidator,
)
from app.domain.answers import ChecklistAnalysisResult
from app.domain.checklists import ChecklistDefinition
from app.domain.enums import ChecklistTag
from app.domain.results import (
    ChecklistJsonResult,
    ChecklistResultMetadata,
    ChecklistResultQuestion,
)


class ChecklistResultBuilder:
    """Строит публичный JSON из проверенных answer-моделей."""

    def __init__(
        self,
        *,
        dimension_validator: AnswerDimensionValidator,
    ) -> None:
        self._dimension_validator = (
            dimension_validator
        )

    def build(
        self,
        *,
        request_id: UUID,
        source_filename: str,
        checklist: ChecklistDefinition,
        analysis: ChecklistAnalysisResult,
        processing_seconds: float,
        search_seconds: float,
    ) -> ChecklistJsonResult:
        """Собрать итоговый API-result в исходном порядке вопросов."""
        answers_by_id = {
            answer.question_id: answer
            for answer in analysis.answers
        }

        questions = []

        for question in checklist.questions:
            grounded = answers_by_id.get(
                question.id
            )

            answer = (
                grounded.output_answer
                if grounded is not None
                else ""
            )

            if (
                answer
                and not self._dimension_validator.is_valid(
                    question=question.text,
                    answer=answer,
                )
            ):
                answer = ""

            questions.append(
                ChecklistResultQuestion(
                    number=question.source_number,
                    question=question.text,
                    answer=answer,
                )
            )

        return ChecklistJsonResult(
            metadata=ChecklistResultMetadata(
                request_id=request_id,
                checklist_type=checklist.description,
                checklist_tag=(
                    ChecklistTag.from_code(
                        checklist.code
                    )
                ),
                checklist_code=checklist.code,
                source_filename=source_filename,
                processing_seconds=round(
                    processing_seconds,
                    3,
                ),
                search_seconds=round(
                    search_seconds,
                    3,
                ),
                completed_at=datetime.now(
                    UTC
                ),
                question_count=len(
                    questions
                ),
            ),
            questions=tuple(
                questions
            ),
        )
    