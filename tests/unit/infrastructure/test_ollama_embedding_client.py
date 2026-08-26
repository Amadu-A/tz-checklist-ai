# tests/unit/infrastructure/test_ollama_embedding_client.py

import json

import httpx
import pytest

from app.infrastructure.ai.ollama_embedding_client import (
    OllamaEmbeddingClient,
)


@pytest.mark.asyncio
async def test_embedding_client_sends_model_and_keep_alive() -> None:
    """Adapter должен соблюдать shared Ollama runtime policy."""

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        payload = json.loads(
            request.content
        )

        assert (
            request.url.path
            == "/api/embed"
        )

        assert (
            payload["model"]
            == "qwen3-embedding:4b"
        )

        assert (
            payload["keep_alive"]
            == "1m"
        )

        assert payload["input"] == [
            "первый текст",
            "второй текст",
        ]

        return httpx.Response(
            200,
            json={
                "model": (
                    "qwen3-embedding:4b"
                ),
                "embeddings": [
                    [
                        1.0,
                        0.0,
                    ],
                    [
                        0.0,
                        1.0,
                    ],
                ],
            },
        )

    client = OllamaEmbeddingClient(
        base_url="http://ollama:11434",
        model="qwen3-embedding:4b",
        keep_alive="1m",
        timeout_seconds=30,
        transport=httpx.MockTransport(
            handler
        ),
    )

    vectors = await client.embed(
        (
            "первый текст",
            "второй текст",
        )
    )

    assert vectors == (
        (
            1.0,
            0.0,
        ),
        (
            0.0,
            1.0,
        ),
    )


@pytest.mark.asyncio
async def test_embedding_client_rejects_wrong_vector_count() -> None:
    """Protocol corruption не должна незаметно проходить дальше."""

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        del request

        return httpx.Response(
            200,
            json={
                "embeddings": [
                    [
                        1.0,
                        0.0,
                    ],
                ],
            },
        )

    client = OllamaEmbeddingClient(
        base_url="http://ollama:11434",
        model="qwen3-embedding:4b",
        keep_alive="1m",
        timeout_seconds=30,
        transport=httpx.MockTransport(
            handler
        ),
    )

    with pytest.raises(
        ValueError,
        match=(
            "unexpected number"
        ),
    ):
        await client.embed(
            (
                "one",
                "two",
            )
        )
        