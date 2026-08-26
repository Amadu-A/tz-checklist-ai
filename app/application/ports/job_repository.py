# app/application/ports/job_repository.py

from datetime import datetime
from typing import Protocol
from uuid import UUID

from app.domain.enums import ChecklistCode, JobStatus
from app.domain.jobs import JobState


class JobRepositoryPort(Protocol):
    """Порт хранения только технического состояния задания."""

    def create(
        self,
        job_id: UUID,
        *,
        status: JobStatus,
        checklist_code: ChecklistCode | None = None,
    ) -> JobState:
        """Создать metadata новой задачи."""
        ...

    def get(
        self,
        job_id: UUID,
    ) -> JobState | None:
        """Получить текущее состояние."""
        ...

    def update(
        self,
        job_id: UUID,
        *,
        status: JobStatus,
        checklist_code: ChecklistCode | None = None,
        error: str | None = None,
    ) -> JobState:
        """Изменить состояние."""
        ...

    def delete(
        self,
        job_id: UUID,
    ) -> None:
        """Полностью удалить metadata задания."""
        ...

    def find_older_than(
        self,
        *,
        statuses: tuple[JobStatus, ...],
        cutoff: datetime,
    ) -> tuple[JobState, ...]:
        """Найти старые задания для retention cleanup."""
        ...
    