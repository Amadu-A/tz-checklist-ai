# app/domain/retrieval.py

from pydantic import BaseModel, ConfigDict, Field


class RetrievalModel(BaseModel):
    """Базовая строгая неизменяемая модель retrieval-слоя."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class DocumentChunk(RetrievalModel):
    """Один page-aware fragment пользовательского документа.

    Chunk содержит только данные текущей обработки и никогда
    не сохраняется в persistent storage.
    """

    chunk_id: str = Field(
        min_length=1,
    )

    page_number: int = Field(
        ge=1,
    )

    chunk_index: int = Field(
        ge=1,
    )

    text: str = Field(
        min_length=1,
    )


class RetrievalHit(RetrievalModel):
    """Один найденный fragment с объяснимыми компонентами score."""

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
    """TOP-K evidence для одного вопроса чек-листа."""

    query: str = Field(
        min_length=1,
    )

    hits: tuple[RetrievalHit, ...] = Field(
        default_factory=tuple,
    )

    @property
    def best_score(self) -> float:
        """Вернуть score лучшего fragment либо 0."""
        if not self.hits:
            return 0.0

        return self.hits[0].hybrid_score
