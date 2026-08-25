# app/application/use_cases/confirm_checklist.py

from app.application.ports.checklist_repository import (
    ChecklistRepositoryPort,
)
from app.domain.checklists import ConfirmedChecklist
from app.domain.enums import ChecklistCode


class ConfirmChecklistUseCase:
    """Подтверждает рекомендацию или выбранный пользователем другой чек-лист."""

    def __init__(
        self,
        repository: ChecklistRepositoryPort,
    ) -> None:
        self._repository = repository

    def execute(
        self,
        code: ChecklistCode,
    ) -> ConfirmedChecklist:
        """Проверить существование выбранного чек-листа."""
        definition = self._repository.get(
            code
        )

        return ConfirmedChecklist(
            code=definition.code,
            title=definition.title,
        )
