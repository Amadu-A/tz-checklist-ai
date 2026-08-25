# app/domain/models.py

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class DependencyHealth:
    """Состояние одной обязательной зависимости."""

    name: str
    ready: bool
    detail: str | None = None


@dataclass(frozen=True, slots=True)
class ReadinessReport:
    """Сводное состояние готовности приложения."""

    ready: bool
    dependencies: tuple[DependencyHealth, ...]
    