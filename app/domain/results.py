# app/domain/results.py

from datetime import datetime
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.domain.enums import (
    ChecklistCode,
    ChecklistTag,
)


class ResultModel(BaseModel):
    """Базовая неизменяемая модель публичного результата."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class ChecklistResultMetadata(ResultModel):
    """Метаданные одного анализа ТЗ."""

    request_id: UUID

    checklist_type: str = Field(
        min_length=1,
    )

    checklist_tag: ChecklistTag

    checklist_code: ChecklistCode

    source_filename: str = Field(
        min_length=1,
        max_length=255,
    )

    processing_seconds: float = Field(
        ge=0,
    )

    search_seconds: float = Field(
        ge=0,
    )

    completed_at: datetime

    question_count: int = Field(
        ge=1,
    )


class ChecklistResultQuestion(ResultModel):
    """Один вопрос итогового JSON."""

    number: str = Field(
        min_length=1,
    )

    question: str = Field(
        min_length=1,
    )

    answer: str


class ChecklistJsonResult(ResultModel):
    """Полный JSON-результат анализа."""

    metadata: ChecklistResultMetadata

    questions: tuple[
        ChecklistResultQuestion,
        ...,
    ] = Field(
        min_length=1,
    )
