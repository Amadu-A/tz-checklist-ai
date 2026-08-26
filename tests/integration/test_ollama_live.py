# tests/integration/test_ollama_live.py

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.core.config import Settings


class OllamaModel(BaseModel):
    """Минимальная модель элемента Ollama /api/tags."""

    model_config = ConfigDict(
        extra="ignore",
    )

    name: str


class OllamaTags(BaseModel):
    """Минимальный Pydantic contract /api/tags."""

    model_config = ConfigDict(
        extra="ignore",
    )

    models: list[
        OllamaModel
    ] = Field(
        default_factory=list,
    )


def test_shared_ollama_is_available() -> None:
    """Shared Ollama должна быть доступна из project network."""
    settings = Settings()

    response = httpx.get(
        (
            settings
            .ollama_base_url
            .rstrip("/")
            + "/api/tags"
        ),
        timeout=10,
    )

    assert (
        response.status_code
        == 200
    )


def test_required_stage_three_models_are_available() -> None:
    """На этапе 3 нужны одна VLM и одна embedding model."""
    settings = Settings()

    response = httpx.get(
        (
            settings
            .ollama_base_url
            .rstrip("/")
            + "/api/tags"
        ),
        timeout=10,
    )

    response.raise_for_status()

    tags = OllamaTags.model_validate(
        response.json()
    )

    available = {
        model.name
        for model in tags.models
    }

    required = {
        settings.ollama_vlm_model,
        settings.ollama_embedding_model,
    }

    missing = (
        required
        - available
    )

    assert not missing, (
        "Missing Ollama models: "
        f"{sorted(missing)}"
    )
