# app/domain/retrieval.py

from pydantic import BaseModel, ConfigDict, Field


class RetrievalModel(BaseModel):
    """Базовая строгая неизменяемая retrieval-модель."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class DocumentChunk(RetrievalModel):
    """Один page-aware fragment документа."""

    chunk_id: str = Field(min_length=1)

    page_number: int = Field(ge=1)

    chunk_index: int = Field(ge=1)

    text: str = Field(min_length=1)


class EmbeddedChunk(RetrievalModel):
    """Chunk вместе с embedding, существующим только в RAM."""

    chunk: DocumentChunk

    embedding: tuple[float, ...] = Field(
        min_length=1,
    )


class RetrievalIndex(RetrievalModel):
    """Временный in-memory индекс одного пользовательского PDF.

    Он никогда не записывается в SQLite, файловое хранилище
    или другую persistent database.
    """

    items: tuple[EmbeddedChunk, ...] = Field(
        default_factory=tuple,
    )


class RetrievalHit(RetrievalModel):
    """Один найденный fragment с компонентами ranking score."""

    chunk: DocumentChunk

    lexical_score: float = Field(
        ge=0,
        le=1,
    )

    semantic_score: float = Field(
        ge=0,
        le=1,
    )

    hybrid_score: float = Field(
        ge=0,
        le=1,
    )


class RetrievalResult(RetrievalModel):
    """TOP-K evidence для одного вопроса."""

    query: str = Field(min_length=1)

    hits: tuple[RetrievalHit, ...] = Field(
        default_factory=tuple,
    )

    @property
    def best_score(self) -> float:
        """Вернуть лучший hybrid score."""
        if not self.hits:
            return 0.0

        return self.hits[0].hybrid_score
    