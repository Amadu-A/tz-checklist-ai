# app/core/container.py

from dataclasses import dataclass
from functools import lru_cache

from app.application.services.readiness_service import ReadinessService
from app.core.config import get_settings
from app.infrastructure.ai.ollama_health_client import OllamaHealthClient


@dataclass(frozen=True, slots=True)
class Container:
    """Composition root приложения."""

    readiness_service: ReadinessService


@lru_cache
def get_container() -> Container:
    """Собрать зависимости приложения в одном месте."""
    settings = get_settings()

    ollama_health = OllamaHealthClient(
        base_url=settings.ollama_base_url,
        timeout_seconds=min(
            settings.ollama_request_timeout_seconds,
            10.0,
        ),
    )

    return Container(
        readiness_service=ReadinessService(
            dependencies=(ollama_health,),
        ),
    )
