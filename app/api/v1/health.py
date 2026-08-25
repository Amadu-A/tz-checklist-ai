# app/api/v1/health.py

from typing import Annotated

from fastapi import APIRouter, Depends, Response, status

from app.api.dependencies import get_readiness_service
from app.api.v1.schemas import (
    DependencyHealthResponse,
    LivenessResponse,
    ReadinessResponse,
)
from app.application.services.readiness_service import ReadinessService

router = APIRouter(tags=["health"])


@router.get(
    "/health/live",
    response_model=LivenessResponse,
)
async def liveness() -> LivenessResponse:
    """Проверить, что процесс API запущен."""
    return LivenessResponse(status="ok")


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
)
async def readiness(
    response: Response,
    service: Annotated[
        ReadinessService,
        Depends(get_readiness_service),
    ],
) -> ReadinessResponse:
    """Проверить готовность API и обязательных внешних зависимостей."""
    report = await service.check()

    if not report.ready:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

    return ReadinessResponse(
        status="ready" if report.ready else "not_ready",
        dependencies=[
            DependencyHealthResponse(
                name=item.name,
                ready=item.ready,
                detail=item.detail,
            )
            for item in report.dependencies
        ],
    )
