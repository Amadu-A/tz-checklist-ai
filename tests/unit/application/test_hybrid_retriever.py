# tests/unit/application/test_hybrid_retriever.py

from app.application.services.hybrid_retriever import HybridRetriever
from app.domain.retrieval import DocumentChunk


class FakeEmbeddingClient:
    """Детерминированный embedding adapter для unit tests."""

    def __init__(
        self,
        vectors: dict[
            str,
            tuple[float, ...],
        ],
    ) -> None:
        self._vectors = vectors

        self.calls: list[
            tuple[str, ...]
        ] = []

    async def embed(
        self,
        texts: tuple[str, ...],
    ) -> tuple[
        tuple[float, ...],
        ...,
    ]:
        self.calls.append(
            texts
        )

        return tuple(
            self._vectors[text]
            for text in texts
        )


async def test_hybrid_retriever_returns_relevant_chunk_first() -> None:
    """Semantic + lexical evidence должны поднять правильный fragment."""
    query = (
        "насосная установка пожаротушения"
    )

    fire_chunk = DocumentChunk(
        chunk_id="p4-c1",
        page_number=4,
        chunk_index=1,
        text=(
            "Предусмотрена насосная установка "
            "пожаротушения с резервным насосом."
        ),
    )

    heat_chunk = DocumentChunk(
        chunk_id="p8-c1",
        page_number=8,
        chunk_index=1,
        text=(
            "Узел учета тепловой энергии "
            "оборудован тепловычислителем."
        ),
    )

    embedding_client = FakeEmbeddingClient(
        {
            query: (
                1.0,
                0.0,
            ),
            fire_chunk.text: (
                0.95,
                0.05,
            ),
            heat_chunk.text: (
                0.0,
                1.0,
            ),
        }
    )

    retriever = HybridRetriever(
        embedding_client=embedding_client,
        top_k=2,
        batch_size=16,
        semantic_weight=0.65,
        lexical_weight=0.35,
    )

    result = await retriever.retrieve(
        query,
        (
            heat_chunk,
            fire_chunk,
        ),
    )

    assert (
        result.hits[0].chunk.chunk_id
        == "p4-c1"
    )

    assert (
        result.hits[0].hybrid_score
        > result.hits[1].hybrid_score
    )


async def test_semantic_retrieval_handles_paraphrase() -> None:
    """Embeddings должны спасать вопрос без точного lexical совпадения."""
    query = (
        "Предусмотрено ли резервирование насосов?"
    )

    relevant = DocumentChunk(
        chunk_id="p3-c2",
        page_number=3,
        chunk_index=2,
        text=(
            "В составе установки принят один рабочий "
            "и один резервный агрегат."
        ),
    )

    irrelevant = DocumentChunk(
        chunk_id="p9-c1",
        page_number=9,
        chunk_index=1,
        text=(
            "Температурный график системы отопления 95/70."
        ),
    )

    embedding_client = FakeEmbeddingClient(
        {
            query: (
                1.0,
                0.0,
            ),
            relevant.text: (
                0.9,
                0.1,
            ),
            irrelevant.text: (
                0.1,
                0.9,
            ),
        }
    )

    retriever = HybridRetriever(
        embedding_client=embedding_client,
        top_k=1,
        batch_size=16,
        semantic_weight=0.8,
        lexical_weight=0.2,
    )

    result = await retriever.retrieve(
        query,
        (
            irrelevant,
            relevant,
        ),
    )

    assert len(
        result.hits
    ) == 1

    assert (
        result.hits[0].chunk
        == relevant
    )


async def test_empty_document_does_not_call_embedding_model() -> None:
    """Документ без native chunks не должен расходовать GPU."""
    embedding_client = FakeEmbeddingClient(
        {}
    )

    retriever = HybridRetriever(
        embedding_client=embedding_client,
        top_k=5,
        batch_size=16,
        semantic_weight=0.65,
        lexical_weight=0.35,
    )

    result = await retriever.retrieve(
        "Есть ли насос?",
        (),
    )

    assert (
        result.hits
        == ()
    )

    assert (
        embedding_client.calls
        == []
    )
    