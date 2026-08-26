# app/api/v1/schemas.py

from enum import StrEnum
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import (
    ChecklistCode,
    ClassificationSource,
    JobStatus,
    VlmFallbackReason,
)


class ApiModel(BaseModel):
    """Строгая базовая модель публичного API."""

    model_config = ConfigDict(
        extra="forbid",
    )


class LivenessResponse(ApiModel):
    """Ответ liveness-проверки."""

    status: str


class DependencyHealthResponse(ApiModel):
    """Состояние одной внешней зависимости."""

    name: str

    ready: bool

    detail: str | None = None


class ReadinessResponse(ApiModel):
    """Ответ readiness-проверки."""

    status: str

    dependencies: list[
        DependencyHealthResponse
    ]


class TzCheckAction(StrEnum):
    """Допустимые операции единого endpoint."""

    SELECT = "select"
    CONFIRM = "confirm"
    STATUS = "status"
    RESULT = "result"


class ChecklistRankingResponse(ApiModel):
    """Один кандидат auto-classification."""

    code: ChecklistCode

    score: float = Field(
        ge=0,
    )

    matched_hints: list[str] = Field(
        default_factory=list,
    )


class TzCheckSelectResponse(ApiModel):
    """Ответ action=select."""

    action: TzCheckAction = TzCheckAction.SELECT

    request_id: UUID

    status: JobStatus = (
        JobStatus.AWAITING_CONFIRMATION
    )

    recommended_checklist: (
        ChecklistCode
        | None
    )

    confidence: float = Field(
        ge=0,
        le=1,
    )

    requires_confirmation: bool = True

    ranking: list[
        ChecklistRankingResponse
    ]

    classification_source: ClassificationSource

    fallback_reason: (
        VlmFallbackReason
        | None
    ) = None

    vision_pages: list[int] = Field(
        default_factory=list,
    )


class TzCheckConfirmResponse(ApiModel):
    """Ответ action=confirm."""

    action: TzCheckAction = TzCheckAction.CONFIRM

    request_id: UUID

    status: JobStatus

    checklist_code: ChecklistCode

    checklist_title: str


class TzCheckStatusResponse(ApiModel):
    """Ответ action=status."""

    action: TzCheckAction = TzCheckAction.STATUS

    request_id: UUID

    status: JobStatus

    checklist_code: (
        ChecklistCode
        | None
    ) = None

    progress_percent: int = Field(
        ge=0,
        le=100,
    )

    result_ready: bool

    error: str | None = None


class ErrorResponse(ApiModel):
    """Публичная форма ожидаемой ошибки workflow."""

    detail: str
    