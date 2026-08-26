# app/infrastructure/ai/ollama_answer_client.py

import json

import httpx
from pydantic import BaseModel, ConfigDict, Field

from app.domain.answers import (
    AnswerCandidate,
    AnswerStatus,
    QuestionEvidence,
)


class _StrictModel(BaseModel):
    """Строгая модель structured output."""

    model_config = ConfigDict(
        extra="forbid",
    )


class _AnswerPayload(_StrictModel):
    """Один ответ модели до deterministic validation."""

    question_id: str = Field(
        min_length=1
    )

    status: AnswerStatus

    answer: str | None = None

    confidence: float = Field(
        ge=0,
        le=1,
    )

    supporting_text: str | None = None


class _AnswerBatchPayload(_StrictModel):
    """Structured response для группы вопросов."""

    answers: list[_AnswerPayload]


class _OllamaProtocolModel(BaseModel):
    """Протокольные поля Ollama."""

    model_config = ConfigDict(
        extra="ignore",
    )


class _OllamaMessage(_OllamaProtocolModel):
    """Минимальный Ollama message."""

    role: str

    content: str


class _OllamaChatResponse(_OllamaProtocolModel):
    """Минимальный ответ /api/chat."""

    message: _OllamaMessage


class OllamaAnswerClient:
    """Grounded text extraction через shared Ollama."""

    SYSTEM_PROMPT = (
        "Ты извлекаешь ответы для технического чек-листа "
        "только из переданного evidence. "
        "Каждый question_id независим: для него разрешено использовать "
        "только evidence этого же question_id. "
        "Сам текст вопроса и варианты ответа в нём не являются evidence. "
        "Не переноси значения между разными инженерными системами "
        "или параметрами. "
        "Для status=found ответ должен прямо следовать из evidence. "
        "supporting_text должен быть дословным непрерывным фрагментом "
        "одного из evidence.text. "
        "Не исправляй числа, единицы измерения и обозначения. "
        "Если прямого ответа нет — status=not_found. "
        "Если evidence неоднозначен или недостаточен — "
        "status=low_confidence. "
        "Для not_found и low_confidence answer и supporting_text "
        "должны быть null. "
        "Верни строго JSON по переданной схеме."
    )

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        keep_alive: str,
        timeout_seconds: float,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._base_url = (
            base_url.rstrip("/")
        )

        self._model = model
        self._keep_alive = keep_alive
        self._timeout_seconds = (
            timeout_seconds
        )

        self._transport = transport

    async def extract(
        self,
        items: tuple[QuestionEvidence, ...],
    ) -> tuple[AnswerCandidate, ...]:
        """Извлечь кандидаты ответов из ограниченного evidence."""
        if not items:
            return ()

        user_payload = [
            {
                "question_id": item.question_id,
                "question": item.question_text,
                "evidence": [
                    {
                        "page": hit.chunk.page_number,
                        "text": hit.chunk.text,
                    }
                    for hit in item.hits
                ],
            }
            for item in items
        ]

        request_payload = {
            "model": self._model,
            "stream": False,
            "think": False,
            "keep_alive": self._keep_alive,
            "format": (
                _AnswerBatchPayload
                .model_json_schema()
            ),
            "options": {
                "temperature": 0,
            },
            "messages": [
                {
                    "role": "system",
                    "content": self.SYSTEM_PROMPT,
                },
                {
                    "role": "user",
                    "content": json.dumps(
                        user_payload,
                        ensure_ascii=False,
                    ),
                },
            ],
        }

        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_seconds,
            transport=self._transport,
        ) as client:
            response = await client.post(
                "/api/chat",
                json=request_payload,
            )

            response.raise_for_status()

        ollama_response = (
            _OllamaChatResponse
            .model_validate(
                response.json()
            )
        )

        payload = (
            _AnswerBatchPayload
            .model_validate_json(
                ollama_response
                .message
                .content
            )
        )

        return tuple(
            AnswerCandidate(
                question_id=item.question_id,
                status=item.status,
                answer=item.answer,
                confidence=item.confidence,
                supporting_text=(
                    item.supporting_text
                ),
            )
            for item in payload.answers
        )
