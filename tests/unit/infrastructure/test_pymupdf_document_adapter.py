# tests/unit/infrastructure/test_pymupdf_document_adapter.py

from pathlib import Path

import fitz

from app.infrastructure.pdf.pymupdf_document_adapter import (
    PyMuPdfDocumentAdapter,
)


def _create_pdf(
    path: Path,
) -> None:
    """Создать двухстраничный PDF с нормальным text layer."""
    document = fitz.open()

    first = document.new_page()

    first.insert_text(
        (72, 72),
        "First native text page",
    )

    second = document.new_page()

    second.insert_text(
        (72, 72),
        "Second native text page",
    )

    document.save(
        path
    )

    document.close()


def test_extract_text_does_not_render_document(
    tmp_path: Path,
) -> None:
    """Fast path должен получать native text напрямую."""
    path = (
        tmp_path
        / "sample.pdf"
    )

    _create_pdf(
        path
    )

    adapter = (
        PyMuPdfDocumentAdapter(
            dpi=72
        )
    )

    context = (
        adapter.extract_text(
            path,
            max_pages=2,
        )
    )

    assert len(
        context.pages
    ) == 2

    assert (
        "First native text page"
        in context.pages[0].text
    )

    assert (
        "Second native text page"
        in context.pages[1].text
    )


def test_render_page_renders_only_requested_page(
    tmp_path: Path,
) -> None:
    """Targeted rendering должен работать с одной страницей."""
    path = (
        tmp_path
        / "sample.pdf"
    )

    _create_pdf(
        path
    )

    adapter = (
        PyMuPdfDocumentAdapter(
            dpi=72
        )
    )

    result = (
        adapter.render_page(
            path,
            page_number=2,
        )
    )

    assert (
        result.page_number
        == 2
    )

    assert (
        result.mime_type
        == "image/jpeg"
    )

    assert (
        result.image_bytes
        .startswith(
            b"\xff\xd8"
        )
    )