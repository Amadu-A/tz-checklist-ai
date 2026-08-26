# app/application/ports/task_queue.py

from typing import Protocol
from uuid import UUID

from app.domain.enums import ChecklistCode


class TaskQueuePort(Protocol):
    """Порт постановки тяжёлого анализа в фоновую очередь."""

    def enqueue_analysis(
        self,
        job_id: UUID,
        checklist_code: ChecklistCode,
    ) -> None:
        """Поставить один анализ в очередь worker."""
        ...
    