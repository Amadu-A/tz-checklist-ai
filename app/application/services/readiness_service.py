# app/application/services/readiness_service.py

import asyncio
from collections.abc import Sequence

from app.application.ports.health import HealthCheckPort
from app.domain.models import ReadinessReport


class ReadinessService:
    """Проверить зависимости без привязки к конкретной инфраструктуре."""

    def __init__(
        self,
        dependencies: Sequence[HealthCheckPort],
    ) -> None:
        self._dependencies = tuple(dependencies)

    async def check(self) -> ReadinessReport:
        """Проверить зависимости и собрать общий readiness."""
        if not self._dependencies:
            return ReadinessReport(
                ready=True,
                dependencies=(),
            )

        results = tuple(
            await asyncio.gather(
                *(
                    dependency.check()
                    for dependency in self._dependencies
                )
            )
        )

        return ReadinessReport(
            ready=all(item.ready for item in results),
            dependencies=results,
        )
    