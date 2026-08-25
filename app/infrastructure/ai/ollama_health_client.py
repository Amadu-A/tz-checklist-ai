# app/infrastructure/ai/ollama_health_client.py

import httpx
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
)

from app.domain.models import (
    DependencyHealth,
)


class _OllamaModel(
    BaseModel
):
    """Модель одного элемента /api/tags."""

    model_config = ConfigDict(
        extra="ignore",
    )

    name: str


class _OllamaTagsResponse(
    BaseModel
):
    """Структура необходимой части /api/tags."""

    model_config = ConfigDict(
        extra="ignore",
    )

    models: list[
        _OllamaModel
    ] = Field(
        default_factory=list,
    )


class OllamaHealthClient:
    """Readiness-адаптер Ollama с проверкой нужных моделей."""

    def __init__(
        self,
        *,
        base_url: str,
        timeout_seconds: float,
        required_models: tuple[
            str,
            ...,
        ] = (),
    ) -> None:
        self._base_url = (
            base_url.rstrip("/")
        )

        self._timeout_seconds = (
            timeout_seconds
        )

        self._required_models = (
            required_models
        )

    async def check(
        self,
    ) -> DependencyHealth:
        """Проверить Ollama и наличие обязательных моделей."""
        try:
            async with httpx.AsyncClient(
                timeout=(
                    self._timeout_seconds
                ),
            ) as client:
                response = (
                    await client.get(
                        f"{self._base_url}/api/tags"
                    )
                )

                response.raise_for_status()

            tags = (
                _OllamaTagsResponse
                .model_validate(
                    response.json()
                )
            )

        except (
            httpx.HTTPError,
            ValueError,
        ) as exc:
            return DependencyHealth(
                name="ollama",
                ready=False,
                detail=(
                    exc.__class__.__name__
                ),
            )

        available = {
            item.name
            for item
            in tags.models
        }

        missing = sorted(
            set(
                self._required_models
            )
            - available
        )

        if missing:
            return DependencyHealth(
                name="ollama",
                ready=False,
                detail=(
                    "Missing models: "
                    + ", ".join(missing)
                ),
            )

        return DependencyHealth(
            name="ollama",
            ready=True,
        )
