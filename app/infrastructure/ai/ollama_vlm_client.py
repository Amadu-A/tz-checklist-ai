# app/infrastructure/ai/ollama_vlm_client.py

import asyncio
import base64

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.domain.documents import (
    PageVisionResult,
    PdfPageImage,
)
from app.infrastructure.ai.errors import (
    OllamaRequestTimeoutError,
)


class _StrictModel(
    BaseModel
):
    """Строгая Pydantic-модель результата, который мы требуем от VLM."""

    model_config = ConfigDict(
        extra="forbid",
    )


class _VlmPagePayload(
    _StrictModel
):
    """JSON, который VLM обязана вернуть для одной страницы."""

    title: str | None = None

    extracted_text: str = ""

    tables: list[str] = Field(
        default_factory=list,
    )

    drawings: list[str] = Field(
        default_factory=list,
    )

    keywords: list[str] = Field(
        default_factory=list,
    )


class _OllamaProtocolModel(
    BaseModel
):
    """Протокольный ответ Ollama содержит дополнительные служебные поля."""

    model_config = ConfigDict(
        extra="ignore",
    )


class _OllamaMessage(
    _OllamaProtocolModel
):
    """Минимальная часть message из Ollama API."""

    role: str

    content: str


class _OllamaChatResponse(
    _OllamaProtocolModel
):
    """Минимально необходимая часть ответа /api/chat."""

    message: _OllamaMessage


class OllamaVlmClient:
    """Адаптер shared Ollama для чтения страниц моделью Qwen3-VL."""

    SYSTEM_PROMPT = (
        "Ты извлекаешь только факты, которые видны на одной "
        "странице строительной проектной или рабочей документации. "
        "Не дополняй документ знаниями извне, не угадывай "
        "отсутствующие значения. Сохраняй обозначения, единицы "
        "измерения, названия разделов, таблицы, подписи чертежей "
        "и штампов. Для чертежей кратко перечисляй только видимые "
        "технические подписи и параметры. Верни строго JSON "
        "по переданной схеме."
    )

    def __init__(
        self,
        *,
        base_url: str,
        model: str,
        keep_alive: str,
        timeout_seconds: float,
        num_ctx: int,
        num_predict: int,
        transport: (
            httpx.AsyncBaseTransport
            | None
        ) = None,
    ) -> None:
        if timeout_seconds <= 0:
            raise ValueError(
                "timeout_seconds must be positive"
            )

        if num_ctx <= 0:
            raise ValueError(
                "num_ctx must be positive"
            )

        if num_predict <= 0:
            raise ValueError(
                "num_predict must be positive"
            )

        if num_predict >= num_ctx:
            raise ValueError(
                "num_predict must be smaller than num_ctx"
            )

        self._base_url = (
            base_url.rstrip("/")
        )

        self._model = model

        self._keep_alive = (
            keep_alive
        )

        self._timeout_seconds = (
            timeout_seconds
        )

        self._num_ctx = num_ctx
        self._num_predict = num_predict

        self._transport = transport

    async def analyze_page(
        self,
        page: PdfPageImage,
    ) -> PageVisionResult:
        """Передать изображение в VLM и провалидировать ответ."""
        image = base64.b64encode(
            page.image_bytes
        ).decode(
            "ascii"
        )

        payload = {
            "model": self._model,
            "stream": False,
            "think": False,
            "keep_alive": (
                self._keep_alive
            ),
            "format": (
                _VlmPagePayload
                .model_json_schema()
            ),
            "options": {
                "temperature": 0,
                "num_ctx": self._num_ctx,
                "num_predict": self._num_predict,
            },
            "messages": [
                {
                    "role": "system",
                    "content": (
                        self.SYSTEM_PROMPT
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Извлеки факты "
                        f"со страницы {page.page_number}."
                    ),
                    "images": [
                        image,
                    ],
                },
            ],
        }

        try:
            async with asyncio.timeout(
                self._timeout_seconds
            ):
                async with httpx.AsyncClient(
                    base_url=self._base_url,
                    timeout=(
                        self._timeout_seconds
                    ),
                    transport=self._transport,
                ) as client:
                    response = await client.post(
                        "/api/chat",
                        json=payload,
                    )

                    response.raise_for_status()

        except (
            TimeoutError,
            httpx.TimeoutException,
        ) as exc:
            raise OllamaRequestTimeoutError(
                "Ollama VLM page request exceeded "
                f"{self._timeout_seconds:g} seconds"
            ) from exc

        ollama_response = (
            _OllamaChatResponse
            .model_validate(
                response.json()
            )
        )

        page_payload = (
            _VlmPagePayload
            .model_validate_json(
                ollama_response
                .message
                .content
            )
        )

        return PageVisionResult(
            page_number=(
                page.page_number
            ),
            title=(
                page_payload.title
            ),
            extracted_text=(
                page_payload
                .extracted_text
            ),
            tables=tuple(
                page_payload.tables
            ),
            drawings=tuple(
                page_payload.drawings
            ),
            keywords=tuple(
                page_payload.keywords
            ),
        )
