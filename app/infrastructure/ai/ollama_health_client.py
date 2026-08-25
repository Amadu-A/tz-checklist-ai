# app/infrastructure/ai/ollama_health_client.py

import httpx

from app.domain.models import DependencyHealth


class OllamaHealthClient:
    """HTTP-адаптер readiness-проверки shared Ollama."""

    def __init__(
        self,
        base_url: str,
        timeout_seconds: float,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout_seconds = timeout_seconds

    async def check(self) -> DependencyHealth:
        """Проверить доступность Ollama через API списка моделей."""
        try:
            async with httpx.AsyncClient(
                timeout=self._timeout_seconds,
            ) as client:
                response = await client.get(
                    f"{self._base_url}/api/tags"
                )
                response.raise_for_status()

        except httpx.HTTPError as exc:
            return DependencyHealth(
                name="ollama",
                ready=False,
                detail=exc.__class__.__name__,
            )

        return DependencyHealth(
            name="ollama",
            ready=True,
        )
    