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


async def test_answer_client_uses_compact_grounded_prompt() -> None:
    """Extraction prompt должен оставаться коротким и строгим."""

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

        # Защита от повторного превращения extraction prompt
        # в длинную экспертную инструкцию.
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

    result = await client.extract(
        (
            evidence,
        )
    )

    assert (
        result[0].status
        == AnswerStatus.FOUND
    )
