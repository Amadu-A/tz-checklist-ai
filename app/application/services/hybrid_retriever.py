# app/application/services/hybrid_retriever.py

import math
import re

from app.application.ports.embedding_client import (
    EmbeddingClientPort,
)
from app.domain.retrieval import (
    DocumentChunk,
    RetrievalHit,
    RetrievalResult,
)


class HybridRetriever:
    """Ищет evidence одновременно lexical и semantic способами.

    Semantic retrieval хорошо находит смысловые переформулировки.

    Lexical retrieval полезен для:
    - маркировок оборудования;
    - чисел;
    - единиц измерения;
    - аббревиатур;
    - точных технических терминов.

    Поэтому использовать только embeddings здесь нежелательно.
    """

    _WORD_RE = re.compile(
        r"[0-9a-zа-я]+",
        flags=re.IGNORECASE,
    )

    _STOP_WORDS = {
        "а",
        "без",
        "бы",
        "был",
        "была",
        "были",
        "быть",
        "в",
        "где",
        "для",
        "до",
        "есть",
        "и",
        "из",
        "или",
        "к",
        "как",
        "ли",
        "на",
        "не",
        "о",
        "об",
        "от",
        "по",
        "под",
        "при",
        "с",
        "со",
        "у",
        "что",
    }

    def __init__(
        self,
        *,
        embedding_client: EmbeddingClientPort,
        top_k: int,
        batch_size: int,
        semantic_weight: float,
        lexical_weight: float,
    ) -> None:
        if top_k <= 0:
            raise ValueError(
                "top_k must be positive"
            )

        if batch_size <= 0:
            raise ValueError(
                "batch_size must be positive"
            )

        if semantic_weight < 0:
            raise ValueError(
                "semantic_weight cannot be negative"
            )

        if lexical_weight < 0:
            raise ValueError(
                "lexical_weight cannot be negative"
            )

        total_weight = (
            semantic_weight
            + lexical_weight
        )

        if total_weight <= 0:
            raise ValueError(
                "At least one retrieval weight must be positive"
            )

        self._embedding_client = embedding_client
        self._top_k = top_k
        self._batch_size = batch_size

        # Нормализуем веса, поэтому config не обязан давать ровно 1.0.
        self._semantic_weight = (
            semantic_weight
            / total_weight
        )

        self._lexical_weight = (
            lexical_weight
            / total_weight
        )

    async def retrieve(
        self,
        query: str,
        chunks: tuple[DocumentChunk, ...],
    ) -> RetrievalResult:
        """Вернуть наиболее релевантные fragments документа."""
        normalized_query = query.strip()

        if not normalized_query:
            raise ValueError(
                "query cannot be empty"
            )

        if not chunks:
            return RetrievalResult(
                query=normalized_query,
            )

        query_embeddings = (
            await self._embedding_client.embed(
                (
                    normalized_query,
                )
            )
        )

        query_vector = query_embeddings[0]

        chunk_vectors: list[
            tuple[float, ...]
        ] = []

        for start in range(
            0,
            len(chunks),
            self._batch_size,
        ):
            batch = chunks[
                start:
                start + self._batch_size
            ]

            vectors = (
                await self._embedding_client.embed(
                    tuple(
                        chunk.text
                        for chunk in batch
                    )
                )
            )

            chunk_vectors.extend(
                vectors
            )

        if len(chunk_vectors) != len(chunks):
            raise ValueError(
                "Embedding client returned unexpected vector count"
            )

        hits: list[RetrievalHit] = []

        for chunk, vector in zip(
            chunks,
            chunk_vectors,
            strict=True,
        ):
            lexical_score = (
                self._lexical_score(
                    normalized_query,
                    chunk.text,
                )
            )

            semantic_score = (
                self._cosine_similarity(
                    query_vector,
                    vector,
                )
            )

            hybrid_score = (
                self._semantic_weight
                * semantic_score
                + self._lexical_weight
                * lexical_score
            )

            hits.append(
                RetrievalHit(
                    chunk=chunk,
                    lexical_score=round(
                        lexical_score,
                        6,
                    ),
                    semantic_score=round(
                        semantic_score,
                        6,
                    ),
                    hybrid_score=round(
                        hybrid_score,
                        6,
                    ),
                )
            )

        hits.sort(
            key=lambda item: (
                -item.hybrid_score,
                item.chunk.page_number,
                item.chunk.chunk_index,
            )
        )

        return RetrievalResult(
            query=normalized_query,
            hits=tuple(
                hits[
                    :self._top_k
                ]
            ),
        )

    @classmethod
    def _lexical_score(
        cls,
        query: str,
        text: str,
    ) -> float:
        """Оценить долю значимых query tokens в fragment."""
        query_tokens = cls._tokenize(
            query
        )

        if not query_tokens:
            return 0.0

        text_tokens = set(
            cls._tokenize(
                text
            )
        )

        matched = sum(
            1
            for token in set(
                query_tokens
            )
            if token in text_tokens
        )

        unique_query_tokens = set(
            query_tokens
        )

        if not unique_query_tokens:
            return 0.0

        return min(
            1.0,
            matched
            / len(
                unique_query_tokens
            ),
        )

    @classmethod
    def _tokenize(
        cls,
        value: str,
    ) -> tuple[str, ...]:
        """Получить значимые lexical tokens."""
        normalized = (
            value
            .casefold()
            .replace(
                "ё",
                "е",
            )
        )

        return tuple(
            token
            for token in cls._WORD_RE.findall(
                normalized
            )
            if (
                token
                not in cls._STOP_WORDS
            )
        )

    @staticmethod
    def _cosine_similarity(
        first: tuple[float, ...],
        second: tuple[float, ...],
    ) -> float:
        """Вычислить cosine similarity и привести к диапазону 0..1."""
        if len(first) != len(second):
            raise ValueError(
                "Embedding dimensions do not match"
            )

        if not first:
            raise ValueError(
                "Embedding vector cannot be empty"
            )

        dot = sum(
            left * right
            for left, right in zip(
                first,
                second,
                strict=True,
            )
        )

        first_norm = math.sqrt(
            sum(
                value * value
                for value in first
            )
        )

        second_norm = math.sqrt(
            sum(
                value * value
                for value in second
            )
        )

        if (
            first_norm == 0
            or second_norm == 0
        ):
            return 0.0

        cosine = (
            dot
            / (
                first_norm
                * second_norm
            )
        )

        return max(
            0.0,
            min(
                1.0,
                cosine,
            ),
        )
    