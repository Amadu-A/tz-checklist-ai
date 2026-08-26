# app/domain/jobs.py

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.domain.enums import ChecklistCode, JobStatus


class JobModel(BaseModel):
    """Базовая строгая неизменяемая Pydantic-модель задания."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class JobState(JobModel):
    """Минимальное техническое состояние пользовательского задания.

    Модель специально не содержит:

    - имени исходного файла;
    - текста документа;
    - извлечённых chunks;
    - embeddings;
    - ответов;
    - содержимого результата.

    Поэтому SQLite используется только как маленькое metadata-хранилище.
    """

    job_id: UUID

    status: JobStatus

    checklist_code: ChecklistCode | None = None

    created_at: datetime

    updated_at: datetime

    error: str | None = Field(
        default=None,
        max_length=1000,
    )
    