# app/application/ports/health.py

from typing import Protocol

from app.domain.models import DependencyHealth


class HealthCheckPort(Protocol):
    """Порт проверки внешней зависимости."""

    async def check(self) -> DependencyHealth:
        """Вернуть текущее состояние зависимости."""
        ...
    