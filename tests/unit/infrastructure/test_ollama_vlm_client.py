# tests/unit/infrastructure/test_ollama_vlm_client.py

import json

import httpx
import pytest

from app.domain.documents import (
    PdfPageImage,
)
from app.infrastructure.ai.ollama_vlm_client import (
    OllamaVlmClient,
)


@pytest.mark.asyncio
async def test_vlm_client_sends_keep_alive_and_parses_pydantic_json() -> None:
    """Проверить contract с Ollama без запуска настоящей нейросети."""
    captured: dict[
        str,
        object,
    ] = {}

    def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        captured.update(
            json.loads(
                request.content
            )
        )

        return httpx.Response(
            200,
            json={
                "model": (
                    "qwen3-vl:8b-instruct"
                ),
                "done": True,
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "title": "УУТЭ",
                            "extracted_text": (
                                "Узел учета "
                                "тепловой энергии"
                            ),
                            "tables": [],
                            "drawings": [],
                            "keywords": [
                                "УУТЭ",
                            ],
                        },
                        ensure_ascii=False,
                    ),
                },
            },
        )

    client = (
        OllamaVlmClient(
            base_url=(
                "http://ollama:11434"
            ),
            model=(
                "qwen3-vl:8b-instruct"
            ),
            keep_alive="1m",
            timeout_seconds=10,
            transport=(
                httpx.MockTransport(
                    handler
                )
            ),
        )
    )

    result = (
        await client.analyze_page(
            PdfPageImage(
                page_number=1,
                image_bytes=(
                    b"fake-image"
                ),
                mime_type=(
                    "image/jpeg"
                ),
            )
        )
    )

    assert (
        captured["model"]
        == "qwen3-vl:8b-instruct"
    )

    assert (
        captured["keep_alive"]
        == "1m"
    )

    assert (
        captured["stream"]
        is False
    )

    assert (
        result.page_number
        == 1
    )

    assert (
        result.title
        == "УУТЭ"
    )
