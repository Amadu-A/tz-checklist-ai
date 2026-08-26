# tests/unit/infrastructure/test_ollama_answer_client.py

import json

import httpx

from app.domain.answers import (
    AnswerStatus,
    QuestionEvidence,
)
from app.domain.retrieval import (
    DocumentChunk,
    RetrievalHit,
)
from app.infrastructure.ai.ollama_answer_client import (
    OllamaAnswerClient,
)


async def test_answer_client_uses_structured_output_and_no_thinking() -> None:
    """Ответ должен приходить в строгом JSON без thinking mode."""

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
            payload["temperature"]
            if "temperature" in payload
            else payload["options"]["temperature"]
        ) == 0

        system_prompt = (
            payload[
                "messages"
            ][0]["content"]
        )

        assert (
            "ТОЛЬКО evidence "
            "внутри объекта с этим же question_id"
            in system_prompt
        )

        assert (
            "Текст вопроса НЕ является evidence"
            in system_prompt
        )

        assert (
            "Нельзя переносить значения "
            "между разными системами"
            in system_prompt
        )

        assert (
            "технологические нужды"
            in system_prompt
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
        transport=httpx.MockTransport(
            handler
        ),
    )

    evidence = QuestionEvidence(
        question_id="q1",
        question_text="Какой расход?",
        hits=(
            RetrievalHit(
                chunk=DocumentChunk(
                    chunk_id="p1-c1",
                    page_number=1,
                    chunk_index=1,
                    text="Расход составляет 3.93 т/ч.",
                ),
                lexical_score=1,
                semantic_score=1,
                hybrid_score=1,
            ),
        ),
    )

    result = await client.extract(
        (
            evidence,
        )
    )

    assert (
        result[0].status
        == AnswerStatus.FOUND
    )
