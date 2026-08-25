# app/api/v1/schemas.py

from pydantic import BaseModel


class LivenessResponse(BaseModel):
    """Ответ liveness-проверки."""

    status: str


class DependencyHealthResponse(BaseModel):
    """Состояние одной внешней зависимости."""

    name: str
    ready: bool
    detail: str | None = None


class ReadinessResponse(BaseModel):
    """Ответ readiness-проверки."""

    status: str
    dependencies: list[DependencyHealthResponse]
    