# app/infrastructure/ai/ollama_embedding_client.py

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)


class _EmbeddingRequest(BaseModel):
    """Строгий request contract Ollama /api/embed."""

    model_config = ConfigDict(
        extra="forbid",
    )

    model: str = Field(
        min_length=1,
    )

    input: tuple[str, ...] = Field(
        min_length=1,
    )

    keep_alive: str = Field(
        min_length=1,
    )


class _EmbeddingResponse(BaseModel):
    """Минимальная часть ответа Ollama /api/embed."""

    model_config = ConfigDict(
        extra="ignore",
    )

    embeddings: list[
        list[float]
    ] = Field(
        min_length=1,
    )


class OllamaEmbeddingClient:
    """Adapter qwen3-embedding через shared Ollama."""

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
        self._keep_alive = keep_alive
        self._timeout_seconds = (
            timeout_seconds
        )

        self._transport = transport

    async def embed(
        self,
        texts: tuple[str, ...],
    ) -> tuple[
        tuple[float, ...],
        ...,
    ]:
        """Получить embeddings и проверить protocol invariants."""
        if not texts:
            raise ValueError(
                "texts cannot be empty"
            )

        cleaned = tuple(
            text.strip()
            for text in texts
        )

        if any(
            not text
            for text in cleaned
        ):
            raise ValueError(
                "Embedding input cannot contain empty text"
            )

        request = _EmbeddingRequest(
            model=self._model,
            input=cleaned,
            keep_alive=(
                self._keep_alive
            ),
        )

        async with httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout_seconds,
            transport=self._transport,
        ) as client:
            response = await client.post(
                "/api/embed",
                json=request.model_dump(
                    mode="json"
                ),
            )

            response.raise_for_status()

        payload = (
            _EmbeddingResponse
            .model_validate(
                response.json()
            )
        )

        if (
            len(payload.embeddings)
            != len(cleaned)
        ):
            raise ValueError(
                "Ollama returned unexpected number of embeddings"
            )

        vectors = tuple(
            tuple(
                float(value)
                for value in vector
            )
            for vector
            in payload.embeddings
        )

        if any(
            not vector
            for vector in vectors
        ):
            raise ValueError(
                "Ollama returned an empty embedding vector"
            )

        dimensions = {
            len(vector)
            for vector in vectors
        }

        if len(dimensions) != 1:
            raise ValueError(
                "Ollama returned embeddings with different dimensions"
            )

        return vectors
