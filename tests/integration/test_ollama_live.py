# tests/integration/test_ollama_live.py

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings


class OllamaModel(BaseModel):
    """Минимальная тестовая модель элемента /api/tags."""

    model_config = ConfigDict(
        extra="ignore",
    )

    name: str


class OllamaTags(BaseModel):
    """Минимальная структура ответа Ollama /api/tags."""

    model_config = ConfigDict(
        extra="ignore",
    )

    models: list[OllamaModel] = Field(
        default_factory=list,
    )


def test_shared_ollama_is_available() -> None:
    """Shared Ollama должен быть доступен из application network."""
    settings = Settings()

    response = httpx.get(
        (
            settings
            .ollama_base_url
            .rstrip("/")
            + "/api/tags"
        ),
        timeout=10.0,
    )

    assert response.status_code == 200


def test_configured_vlm_is_available() -> None:
    """Проверяется только модель, реально необходимая на этапе 2."""
    settings = Settings()

    response = httpx.get(
        (
            settings
            .ollama_base_url
            .rstrip("/")
            + "/api/tags"
        ),
        timeout=10.0,
    )

    response.raise_for_status()

    tags = OllamaTags.model_validate(
        response.json()
    )

    available_models = {
        model.name
        for model in tags.models
    }

    assert (
        settings.ollama_vlm_model
        in available_models
    ), (
        "Configured VLM is missing in Ollama: "
        f"{settings.ollama_vlm_model}"
    )
    