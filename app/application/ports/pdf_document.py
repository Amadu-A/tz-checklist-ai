# app/application/ports/pdf_document.py

from pathlib import Path
from typing import Protocol

from app.domain.documents import (
    DocumentTextContext,
    PdfPageImage,
)


class PdfTextExtractorPort(Protocol):
    """Порт быстрого чтения native text из PDF."""

    def extract_text(
        self,
        pdf_path: Path,
        *,
        max_pages: int | None = None,
    ) -> DocumentTextContext:
        """Извлечь text layer без рендеринга страниц."""
        ...


class PdfPageRendererPort(Protocol):
    """Порт targeted-рендеринга одной конкретной PDF-страницы."""

    def render_page(
        self,
        pdf_path: Path,
        *,
        page_number: int,
    ) -> PdfPageImage:
        """Отрендерить только запрошенную страницу для VLM."""
        ...
    