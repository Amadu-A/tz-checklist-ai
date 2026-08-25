# tests/unit/test_readiness_service.py

import pytest

from app.application.services.readiness_service import ReadinessService
from app.domain.models import DependencyHealth


class FakeHealthCheck:
    """Тестовая зависимость."""

    def __init__(
        self,
        name: str,
        ready: bool,
    ) -> None:
        self._name = name
        self._ready = ready

    async def check(self) -> DependencyHealth:
        return DependencyHealth(
            name=self._name,
            ready=self._ready,
        )


@pytest.mark.asyncio
async def test_readiness_is_true_when_every_dependency_is_ready() -> None:
    service = ReadinessService(
        dependencies=(
            FakeHealthCheck("ollama", True),
            FakeHealthCheck("rabbitmq", True),
        )
    )

    report = await service.check()

    assert report.ready is True
    assert len(report.dependencies) == 2


@pytest.mark.asyncio
async def test_readiness_is_false_when_dependency_is_not_ready() -> None:
    service = ReadinessService(
        dependencies=(
            FakeHealthCheck("ollama", True),
            FakeHealthCheck("rabbitmq", False),
        )
    )

    report = await service.check()

    assert report.ready is False