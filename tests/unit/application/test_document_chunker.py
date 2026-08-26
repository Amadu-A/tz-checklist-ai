# tests/unit/application/test_document_chunker.py

import pytest

from app.application.services.document_chunker import DocumentChunker
from app.domain.documents import (
    DocumentTextContext,
    PdfPageText,
)


def test_chunks_preserve_source_page_and_overlap() -> None:
    """Chunking не должен терять связь с исходной PDF-страницей."""
    context = DocumentTextContext(
        pages=(
            PdfPageText(
                page_number=7,
                text=(
                    "первый второй третий четвертый пятый "
                    "шестой седьмой восьмой девятый десятый "
                    "одиннадцатый двенадцатый тринадцатый"
                ),
            ),
        )
    )

    chunker = DocumentChunker(
        max_chars=60,
        overlap_chars=20,
    )

    chunks = chunker.chunk(
        context
    )

    assert len(chunks) > 1

    assert all(
        chunk.page_number == 7
        for chunk in chunks
    )

    assert (
        chunks[0].chunk_id
        == "p7-c1"
    )

    first_words = set(
        chunks[0].text.split()
    )

    second_words = set(
        chunks[1].text.split()
    )

    assert (
        first_words
        & second_words
    )


def test_empty_pages_do_not_create_chunks() -> None:
    """Страница без native text не должна создавать пустой chunk."""
    context = DocumentTextContext(
        pages=(
            PdfPageText(
                page_number=1,
                text="",
            ),
            PdfPageText(
                page_number=2,
                text="Полезный технический текст.",
            ),
        )
    )

    chunker = DocumentChunker(
        max_chars=100,
        overlap_chars=20,
    )

    chunks = chunker.chunk(
        context
    )

    assert len(chunks) == 1

    assert (
        chunks[0].page_number
        == 2
    )


def test_overlap_cannot_be_larger_than_chunk() -> None:
    """Невалидная chunking-конфигурация должна падать сразу."""
    with pytest.raises(
        ValueError
    ):
        DocumentChunker(
            max_chars=500,
            overlap_chars=500,
        )
        