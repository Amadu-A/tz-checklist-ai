# tests/integration/test_health_api.py

import httpx
import pytest

from app.api.dependencies import (
    get_readiness_service,
)
from app.domain.models import (
    DependencyHealth,
    ReadinessReport,
)
from app.main import app


class ReadyServiceStub:
    """Стаб готового readiness-сервиса."""

    async def check(
        self,
    ) -> ReadinessReport:
        return ReadinessReport(
            ready=True,
            dependencies=(
                DependencyHealth(
                    name="ollama",
                    ready=True,
                ),
            ),
        )


class NotReadyServiceStub:
    """Стаб неготового readiness-сервиса."""

    async def check(
        self,
    ) -> ReadinessReport:
        return ReadinessReport(
            ready=False,
            dependencies=(
                DependencyHealth(
                    name="ollama",
                    ready=False,
                    detail=(
                        "ConnectError"
                    ),
                ),
            ),
        )


async def _get(
    path: str,
) -> httpx.Response:
    """Вызвать ASGI-приложение без deprecated TestClient."""
    transport = (
        httpx.ASGITransport(
            app=app
        )
    )

    async with httpx.AsyncClient(
        transport=transport,
        base_url="http://test",
    ) as client:
        return await client.get(
            path
        )


@pytest.mark.asyncio
async def test_liveness_endpoint() -> None:
    response = await _get(
        "/health/live"
    )

    assert (
        response.status_code
        == 200
    )

    assert response.json() == {
        "status": "ok",
    }


@pytest.mark.asyncio
async def test_readiness_endpoint_returns_200_when_ready() -> None:
    app.dependency_overrides[
        get_readiness_service
    ] = lambda: ReadyServiceStub()

    try:
        response = await _get(
            "/health/ready"
        )
    finally:
        app.dependency_overrides.clear()

    assert (
        response.status_code
        == 200
    )

    assert (
        response.json()["status"]
        == "ready"
    )


@pytest.mark.asyncio
async def test_readiness_endpoint_returns_503_when_not_ready() -> None:
    app.dependency_overrides[
        get_readiness_service
    ] = lambda: NotReadyServiceStub()

    try:
        response = await _get(
            "/health/ready"
        )
    finally:
        app.dependency_overrides.clear()

    assert (
        response.status_code
        == 503
    )

    assert (
        response.json()["status"]
        == "not_ready"
    )
    