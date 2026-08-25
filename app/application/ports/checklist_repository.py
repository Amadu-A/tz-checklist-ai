# app/application/ports/checklist_repository.py

from typing import Protocol

from app.domain.checklists import (
    ChecklistCatalog,
    ChecklistDefinition,
)
from app.domain.enums import ChecklistCode


class ChecklistRepositoryPort(Protocol):
    """Порт доступа к неизменяемым определениям чек-листов."""

    def get(
        self,
        code: ChecklistCode,
    ) -> ChecklistDefinition:
        """Получить один чек-лист по стабильному коду."""
        ...

    def list(
        self,
    ) -> tuple[ChecklistDefinition, ...]:
        """Получить все доступные чек-листы."""
        ...

    def get_catalog(
        self,
    ) -> ChecklistCatalog:
        """Получить каталог признаков для классификации."""
        ...
    