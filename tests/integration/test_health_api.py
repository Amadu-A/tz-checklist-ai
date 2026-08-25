# tests/integration/test_health_api.py

from fastapi.testclient import TestClient

from app.api.dependencies import get_readiness_service
from app.domain.models import DependencyHealth, ReadinessReport
from app.main import app


class ReadyServiceStub:
    """Стаб готового readiness-сервиса."""

    async def check(self) -> ReadinessReport:
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

    async def check(self) -> ReadinessReport:
        return ReadinessReport(
            ready=False,
            dependencies=(
                DependencyHealth(
                    name="ollama",
                    ready=False,
                    detail="ConnectError",
                ),
            ),
        )


def test_liveness_endpoint() -> None:
    client = TestClient(app)

    response = client.get("/health/live")

    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
    }


def test_readiness_endpoint_returns_200_when_ready() -> None:
    app.dependency_overrides[
        get_readiness_service
    ] = lambda: ReadyServiceStub()

    client = TestClient(app)

    try:
        response = client.get("/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_readiness_endpoint_returns_503_when_not_ready() -> None:
    app.dependency_overrides[
        get_readiness_service
    ] = lambda: NotReadyServiceStub()

    client = TestClient(app)

    try:
        response = client.get("/health/ready")
    finally:
        app.dependency_overrides.clear()

    assert response.status_code == 503
    assert response.json()["status"] == "not_ready"
    