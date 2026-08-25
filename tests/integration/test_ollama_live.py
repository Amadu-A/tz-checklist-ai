# tests/integration/test_ollama_live.py

import httpx

from app.core.config import Settings


def test_shared_ollama_is_available() -> None:
    settings = Settings()

    response = httpx.get(
        f"{settings.ollama_base_url.rstrip('/')}/api/tags",
        timeout=10.0,
    )

    assert response.status_code == 200


def test_required_ollama_models_are_available() -> None:
    settings = Settings()

    response = httpx.get(
        f"{settings.ollama_base_url.rstrip('/')}/api/tags",
        timeout=10.0,
    )

    response.raise_for_status()

    payload = response.json()

    available_models = {
        model["name"]
        for model in payload.get("models", [])
    }

    required_models = {
        settings.ollama_llm_model,
        settings.ollama_vlm_model,
        settings.ollama_embedding_model,
    }

    missing_models = required_models - available_models

    assert not missing_models, (
        "В shared Ollama отсутствуют модели: "
        f"{sorted(missing_models)}"
    )
