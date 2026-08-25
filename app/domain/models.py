# app/domain/models.py

from pydantic import BaseModel, ConfigDict, Field


class HealthModel(BaseModel):
    """Базовая неизменяемая Pydantic-модель health/readiness домена."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class DependencyHealth(HealthModel):
    """Состояние одной обязательной внешней зависимости."""

    name: str = Field(min_length=1)

    ready: bool

    detail: str | None = None


class ReadinessReport(HealthModel):
    """Сводное состояние готовности приложения."""

    ready: bool

    dependencies: tuple[DependencyHealth, ...] = Field(
        default_factory=tuple,
    )
