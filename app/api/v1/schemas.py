# app/api/v1/schemas.py

from enum import StrEnum
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.domain.enums import (
    ChecklistCode,
    ChecklistTag,
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
    """Операции единого endpoint."""

    SELECT = "select"
    CONFIRM = "confirm"
    STATUS = "status"
    RESULT = "result"


class ChecklistSelectionMode(StrEnum):
    """Как выбран checklist."""

    PROVIDED_TAG = "provided_tag"
    AUTOMATIC = "automatic"


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
    """SELECT без checklist_tag: требуется подтверждение."""

    action: TzCheckAction = TzCheckAction.SELECT

    request_id: UUID

    status: JobStatus = (
        JobStatus.AWAITING_CONFIRMATION
    )

    selection_mode: ChecklistSelectionMode = (
        ChecklistSelectionMode.AUTOMATIC
    )

    recommended_checklist: (
        ChecklistCode
        | None
    )

    recommended_tag: (
        ChecklistTag
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


class TzCheckTaggedSelectResponse(ApiModel):
    """SELECT с checklist_tag: classification/confirmation пропущены."""

    action: TzCheckAction = TzCheckAction.SELECT

    request_id: UUID

    status: JobStatus = JobStatus.QUEUED

    selection_mode: ChecklistSelectionMode = (
        ChecklistSelectionMode.PROVIDED_TAG
    )

    checklist_code: ChecklistCode

    checklist_tag: ChecklistTag

    checklist_title: str

    requires_confirmation: bool = False


class TzCheckConfirmResponse(ApiModel):
    """Ответ action=confirm."""

    action: TzCheckAction = TzCheckAction.CONFIRM

    request_id: UUID

    status: JobStatus

    checklist_code: ChecklistCode

    checklist_tag: ChecklistTag

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

    checklist_tag: (
        ChecklistTag
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
