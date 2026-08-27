# tests/unit/infrastructure/test_ollama_answer_client.py

import asyncio
import json

import httpx
import pytest

from app.domain.answers import (
    AnswerStatus,
    QuestionEvidence,
)
from app.domain.retrieval import (
    DocumentChunk,
    RetrievalHit,
)
from app.infrastructure.ai.errors import (
    OllamaRequestTimeoutError,
)
from app.infrastructure.ai.ollama_answer_client import (
    OllamaAnswerClient,
)


def _evidence() -> QuestionEvidence:
    """Создать один grounded evidence item."""
    return QuestionEvidence(
        question_id="q1",
        question_text="Какой расход?",
        hits=(
            RetrievalHit(
                chunk=DocumentChunk(
                    chunk_id="p1-c1",
                    page_number=1,
                    chunk_index=1,
                    text=(
                        "Расход составляет 3.93 т/ч."
                    ),
                ),
                lexical_score=1,
                semantic_score=1,
                hybrid_score=1,
            ),
        ),
    )


async def test_answer_client_uses_bounded_grounded_prompt() -> None:
    """Extraction request должен иметь context/output limits."""

    async def handler(
        request: httpx.Request,
    ) -> httpx.Response:
        payload = json.loads(
            request.content
        )

        assert (
            request.url.path
            == "/api/chat"
        )

        assert (
            payload["model"]
            == "qwen3.8:27b"
        )

        assert (
            payload["think"]
            is False
        )

        assert (
            payload["options"]["temperature"]
            == 0
        )

        assert (
            payload["options"]["num_ctx"]
            == 32768
        )

        assert (
            payload["options"]["num_predict"]
            == 2048
        )

        system_prompt = (
            payload[
                "messages"
            ][0]["content"]
        )

        assert (
            "Каждый question_id независим"
            in system_prompt
        )

        assert (
            "текст вопроса"
            in system_prompt.casefold()
        )

        assert (
            "Не переноси значения между"
            in system_prompt
        )

        assert (
            len(system_prompt)
            < 1800
        )

        return httpx.Response(
            200,
            json={
                "message": {
                    "role": "assistant",
                    "content": json.dumps(
                        {
                            "answers": [
                                {
                                    "question_id": "q1",
                                    "status": "found",
                                    "answer": "3.93 т/ч",
                                    "confidence": 0.95,
                                    "supporting_text": (
                                        "Расход составляет "
                                        "3.93 т/ч."
                                    ),
                                }
                            ]
                        },
                        ensure_ascii=False,
                    ),
                }
            },
        )

    client = OllamaAnswerClient(
        base_url="http://ollama:11434",
        model="qwen3.8:27b",
        keep_alive="1m",
        timeout_seconds=30,
        num_ctx=32768,
        num_predict=2048,
        transport=httpx.MockTransport(
            handler
        ),
    )

    result = await client.extract(
        (
            _evidence(),
        )
    )

    assert (
        result[0].status
        == AnswerStatus.FOUND
    )


async def test_answer_client_stops_hung_request() -> None:
    """Один зависший text request должен завершиться по watchdog."""

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

    client = OllamaAnswerClient(
        base_url="http://ollama:11434",
        model="qwen3-vl:8b-instruct",
        keep_alive="1m",
        timeout_seconds=0.01,
        num_ctx=32768,
        num_predict=2048,
        transport=httpx.MockTransport(
            handler
        ),
    )

    with pytest.raises(
        OllamaRequestTimeoutError,
        match="grounded-answer request exceeded",
    ):
        await client.extract(
            (
                _evidence(),
            )
        )
