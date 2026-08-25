# app/infrastructure/ai/ollama_vlm_client.py

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


class _StrictModel(BaseModel):
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
        transport: (
            httpx.AsyncBaseTransport
            | None
        ) = None,
    ) -> None:
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

        # Transport внедряется только для удобного unit-testing.
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

            # Важное требование для VRAM.
            "keep_alive": (
                self._keep_alive
            ),

            # Ollama получает JSON Schema,
            # созданную Pydantic.
            "format": (
                _VlmPagePayload
                .model_json_schema()
            ),

            "options": {
                "temperature": 0,
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
