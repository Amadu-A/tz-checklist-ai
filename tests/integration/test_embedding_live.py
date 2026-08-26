# tests/integration/test_embedding_live.py

import pytest

from app.core.config import Settings
from app.infrastructure.ai.ollama_embedding_client import (
    OllamaEmbeddingClient,
)


@pytest.mark.asyncio
async def test_real_shared_ollama_returns_embeddings() -> None:
    """Проверить настоящий qwen3-embedding через shared Ollama."""
    settings = Settings()

    client = OllamaEmbeddingClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embedding_model,
        keep_alive=settings.ollama_keep_alive,
        timeout_seconds=settings.ollama_request_timeout_seconds,
    )

    vectors = await client.embed(
        (
            "насосная установка пожаротушения",
            "индивидуальный тепловой пункт",
        )
    )

    assert len(
        vectors
    ) == 2

    assert len(
        vectors[0]
    ) > 100

    assert len(
        vectors[0]
    ) == len(
        vectors[1]
    )

    assert any(
        value != 0
        for value in vectors[0]
    )
    