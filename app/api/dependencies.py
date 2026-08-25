# app/api/dependencies.py

from app.application.services.readiness_service import ReadinessService
from app.core.container import get_container


def get_readiness_service() -> ReadinessService:
    """Получить readiness-сервис из DI-контейнера."""
    return get_container().readiness_service
