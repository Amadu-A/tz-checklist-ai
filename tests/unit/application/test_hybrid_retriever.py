# tests/unit/application/test_hybrid_retriever.py

from app.application.services.hybrid_retriever import HybridRetriever
from app.domain.retrieval import DocumentChunk


class FakeEmbeddingClient:
    """Детерминированный embedding adapter."""

    def __init__(
        self,
        vectors: dict[str, tuple[float, ...]],
    ) -> None:
        self._vectors = vectors

        self.calls: list[
            tuple[str, ...]
        ] = []

    async def embed(
        self,
        texts: tuple[str, ...],
    ) -> tuple[tuple[float, ...], ...]:
        self.calls.append(
            texts
        )

        return tuple(
            self._vectors[text]
            for text in texts
        )


async def test_document_embeddings_are_built_only_once() -> None:
    """Несколько вопросов должны использовать один document index."""
    first_chunk = DocumentChunk(
        chunk_id="p1-c1",
        page_number=1,
        chunk_index=1,
        text="Пожарный насос предусмотрен.",
    )

    second_chunk = DocumentChunk(
        chunk_id="p2-c1",
        page_number=2,
        chunk_index=1,
        text="Температурный график 95/70.",
    )

    first_query = "Есть пожарный насос?"
    second_query = "Какой температурный график?"

    client = FakeEmbeddingClient(
        {
            first_chunk.text: (1.0, 0.0),
            second_chunk.text: (0.0, 1.0),
            first_query: (1.0, 0.0),
            second_query: (0.0, 1.0),
        }
    )

    retriever = HybridRetriever(
        embedding_client=client,
        top_k=2,
        batch_size=16,
        semantic_weight=0.65,
        lexical_weight=0.35,
    )

    index = await retriever.build_index(
        (
            first_chunk,
            second_chunk,
        )
    )

    results = await retriever.retrieve_many(
        (
            first_query,
            second_query,
        ),
        index,
    )

    assert len(
        results
    ) == 2

    assert (
        results[0].hits[0].chunk
        == first_chunk
    )

    assert (
        results[1].hits[0].chunk
        == second_chunk
    )

    assert client.calls == [
        (
            first_chunk.text,
            second_chunk.text,
        ),
        (
            first_query,
            second_query,
        ),
    ]


async def test_empty_index_does_not_call_embedding_model() -> None:
    """Пустой документ не должен расходовать GPU."""
    client = FakeEmbeddingClient(
        {}
    )

    retriever = HybridRetriever(
        embedding_client=client,
        top_k=5,
        batch_size=16,
        semantic_weight=0.65,
        lexical_weight=0.35,
    )

    index = await retriever.build_index(
        ()
    )

    results = await retriever.retrieve_many(
        (
            "Есть ли насос?",
        ),
        index,
    )

    assert (
        results[0].hits
        == ()
    )

    assert (
        client.calls
        == []
    )
    