# app/api/dependencies.py

from app.application.services.readiness_service import ReadinessService
from app.application.services.tz_check_workflow_service import (
    TzCheckWorkflowService,
)
from app.core.container import get_container


def get_readiness_service() -> ReadinessService:
    """Получить readiness-сервис из DI-контейнера."""
    return get_container().readiness_service


def get_tz_check_workflow_service() -> TzCheckWorkflowService:
    """Получить application workflow единого tz-check endpoint."""
    return get_container().tz_check_workflow_service
