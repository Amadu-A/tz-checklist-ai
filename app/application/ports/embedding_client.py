# app/application/ports/embedding_client.py

from typing import Protocol


class EmbeddingClientPort(Protocol):
    """Порт получения embeddings без зависимости от Ollama."""

    async def embed(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]:
        """Получить embedding для каждого текста в исходном порядке."""
        ...
    