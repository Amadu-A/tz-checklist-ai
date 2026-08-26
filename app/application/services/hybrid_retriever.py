# app/application/services/hybrid_retriever.py

import math
import re

from app.application.ports.embedding_client import EmbeddingClientPort
from app.domain.retrieval import (
    DocumentChunk,
    EmbeddedChunk,
    RetrievalHit,
    RetrievalIndex,
    RetrievalResult,
)


class HybridRetriever:
    """Hybrid retrieval с одноразовой индексацией документа.

    Embeddings chunks вычисляются один раз на job.

    После этого любое количество вопросов использует один
    RetrievalIndex, существующий исключительно в RAM.
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

        self._semantic_weight = (
            semantic_weight
            / total_weight
        )

        self._lexical_weight = (
            lexical_weight
            / total_weight
        )

    async def build_index(
        self,
        chunks: tuple[DocumentChunk, ...],
    ) -> RetrievalIndex:
        """Вычислить embeddings chunks ровно один раз."""
        if not chunks:
            return RetrievalIndex()

        vectors = await self._embed_texts(
            tuple(
                chunk.text
                for chunk in chunks
            )
        )

        if len(vectors) != len(chunks):
            raise ValueError(
                "Embedding client returned unexpected vector count"
            )

        return RetrievalIndex(
            items=tuple(
                EmbeddedChunk(
                    chunk=chunk,
                    embedding=vector,
                )
                for chunk, vector in zip(
                    chunks,
                    vectors,
                    strict=True,
                )
            )
        )

    async def retrieve_many(
        self,
        queries: tuple[str, ...],
        index: RetrievalIndex,
    ) -> tuple[RetrievalResult, ...]:
        """Найти evidence сразу для нескольких вопросов."""
        normalized_queries = tuple(
            query.strip()
            for query in queries
        )

        if any(
            not query
            for query in normalized_queries
        ):
            raise ValueError(
                "queries cannot contain empty strings"
            )

        if not normalized_queries:
            return ()

        if not index.items:
            return tuple(
                RetrievalResult(
                    query=query
                )
                for query in normalized_queries
            )

        query_vectors = await self._embed_texts(
            normalized_queries
        )

        return tuple(
            self._rank(
                query=query,
                query_vector=query_vector,
                index=index,
            )
            for query, query_vector in zip(
                normalized_queries,
                query_vectors,
                strict=True,
            )
        )

    async def retrieve(
        self,
        query: str,
        chunks: tuple[DocumentChunk, ...],
    ) -> RetrievalResult:
        """Совместимый helper для поиска одного вопроса.

        Production pipeline должен предпочитать build_index()
        + retrieve_many(), чтобы chunks не embedding-ились повторно.
        """
        index = await self.build_index(
            chunks
        )

        results = await self.retrieve_many(
            (
                query,
            ),
            index,
        )

        return results[0]

    async def _embed_texts(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]:
        """Получить embeddings батчами с сохранением порядка."""
        result: list[
            tuple[float, ...]
        ] = []

        for start in range(
            0,
            len(texts),
            self._batch_size,
        ):
            batch = texts[
                start:
                start + self._batch_size
            ]

            vectors = await self._embedding_client.embed(
                batch
            )

            if len(vectors) != len(batch):
                raise ValueError(
                    "Embedding client returned unexpected vector count"
                )

            result.extend(
                vectors
            )

        return tuple(result)

    def _rank(
        self,
        *,
        query: str,
        query_vector: tuple[float, ...],
        index: RetrievalIndex,
    ) -> RetrievalResult:
        """Посчитать hybrid score для одного query."""
        hits: list[RetrievalHit] = []

        for item in index.items:
            lexical_score = self._lexical_score(
                query,
                item.chunk.text,
            )

            semantic_score = self._cosine_similarity(
                query_vector,
                item.embedding,
            )

            hybrid_score = (
                self._semantic_weight
                * semantic_score
                + self._lexical_weight
                * lexical_score
            )

            hits.append(
                RetrievalHit(
                    chunk=item.chunk,
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
            query=query,
            hits=tuple(
                hits[:self._top_k]
            ),
        )

    @classmethod
    def _lexical_score(
        cls,
        query: str,
        text: str,
    ) -> float:
        """Оценить долю значимых query tokens в fragment."""
        query_tokens = set(
            cls._tokenize(
                query
            )
        )

        if not query_tokens:
            return 0.0

        text_tokens = set(
            cls._tokenize(
                text
            )
        )

        matched = len(
            query_tokens
            & text_tokens
        )

        return min(
            1.0,
            matched
            / len(query_tokens),
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
            if token not in cls._STOP_WORDS
        )

    @staticmethod
    def _cosine_similarity(
        first: tuple[float, ...],
        second: tuple[float, ...],
    ) -> float:
        """Вычислить cosine similarity в диапазоне 0..1."""
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
    