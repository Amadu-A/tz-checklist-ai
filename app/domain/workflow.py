# app/domain/workflow.py

from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.domain.checklists import (
    ChecklistSelectionResult,
    ConfirmedChecklist,
)
from app.domain.enums import (
    ChecklistCode,
    ChecklistTag,
    JobStatus,
)


class WorkflowModel(BaseModel):
    """Базовая неизменяемая workflow-модель."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class WorkflowSelectionResult(WorkflowModel):
    """Результат auto-classification action=select."""

    request_id: UUID

    selection: ChecklistSelectionResult


class WorkflowTaggedSubmissionResult(WorkflowModel):
    """Результат select, когда checklist tag задан клиентом."""

    request_id: UUID

    checklist: ConfirmedChecklist

    checklist_tag: ChecklistTag

    status: JobStatus = JobStatus.QUEUED


class WorkflowConfirmationResult(WorkflowModel):
    """Результат action=confirm."""

    request_id: UUID

    checklist: ConfirmedChecklist

    status: JobStatus


class WorkflowStatusResult(WorkflowModel):
    """Текущее состояние background job."""

    request_id: UUID

    status: JobStatus

    checklist_code: ChecklistCode | None = None

    progress_percent: int = Field(
        ge=0,
        le=100,
    )

    result_ready: bool = False

    error: str | None = None
