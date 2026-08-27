# tests/unit/infrastructure/test_ollama_vlm_client.py

import asyncio
import json

import httpx
import pytest

from app.domain.documents import (
    PdfPageImage,
)
from app.infrastructure.ai.errors import (
    OllamaRequestTimeoutError,
)
from app.infrastructure.ai.ollama_vlm_client import (
    OllamaVlmClient,
)


def _page() -> PdfPageImage:
    """Создать test page без настоящего изображения."""
    return PdfPageImage(
        page_number=1,
        image_bytes=b"fake-image",
        mime_type="image/jpeg",
    )


@pytest.mark.asyncio
async def test_vlm_client_sends_bounded_options_and_parses_json() -> None:
    """VLM request должен иметь context/output/time guards."""
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

    client = OllamaVlmClient(
        base_url="http://ollama:11434",
        model="qwen3-vl:8b-instruct",
        keep_alive="1m",
        timeout_seconds=10,
        num_ctx=32768,
        num_predict=3072,
        transport=(
            httpx.MockTransport(
                handler
            )
        ),
    )

    result = await client.analyze_page(
        _page()
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
        captured["think"]
        is False
    )

    options = captured[
        "options"
    ]

    assert isinstance(
        options,
        dict,
    )

    assert (
        options["num_ctx"]
        == 32768
    )

    assert (
        options["num_predict"]
        == 3072
    )

    assert (
        result.page_number
        == 1
    )

    assert (
        result.title
        == "УУТЭ"
    )


@pytest.mark.asyncio
async def test_vlm_client_stops_hung_page_request() -> None:
    """Зависшая VLM-страница должна завершиться по watchdog."""

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        del request

        await asyncio.sleep(
            0.05
        )

        return httpx.Response(
            200,
            json={},
        )

    client = OllamaVlmClient(
        base_url="http://ollama:11434",
        model="qwen3-vl:8b-instruct",
        keep_alive="1m",
        timeout_seconds=0.01,
        num_ctx=32768,
        num_predict=3072,
        transport=httpx.MockTransport(
            handler
        ),
    )

    with pytest.raises(
        OllamaRequestTimeoutError,
        match="VLM page request exceeded",
    ):
        await client.analyze_page(
            _page()
        )
