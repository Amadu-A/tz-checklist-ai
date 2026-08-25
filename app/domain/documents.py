# app/domain/documents.py

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DocumentModel(BaseModel):
    """Базовая неизменяемая модель данных документа."""

    model_config = ConfigDict(
        frozen=True,
        extra="forbid",
    )


class PdfPageText(DocumentModel):
    """Текстовый слой одной страницы PDF.

    image_count используется только как диагностический признак:
    наличие изображений само по себе не означает, что VLM обязательна.
    """

    page_number: int = Field(
        ge=1,
    )

    text: str = ""

    image_count: int = Field(
        default=0,
        ge=0,
    )

    @property
    def character_count(self) -> int:
        """Количество значимых символов native text."""
        return len(
            self.text.strip()
        )


class DocumentTextContext(DocumentModel):
    """Native-text представление выбранных страниц PDF."""

    pages: tuple[PdfPageText, ...] = Field(
        min_length=1,
    )

    @property
    def searchable_text(self) -> str:
        """Объединить native text всех страниц в исходном порядке."""
        return "\n\n".join(
            page.text.strip()
            for page in self.pages
            if page.text.strip()
        )

    @property
    def total_characters(self) -> int:
        """Количество значимых символов во всём контексте."""
        return sum(
            page.character_count
            for page in self.pages
        )


class PdfPageImage(DocumentModel):
    """Одна страница PDF, отрендеренная только при необходимости."""

    page_number: int = Field(
        ge=1,
    )

    image_bytes: bytes = Field(
        min_length=1,
    )

    mime_type: Literal[
        "image/jpeg",
        "image/png",
    ]


class PageVisionResult(DocumentModel):
    """Структурированный результат визуального анализа страницы."""

    page_number: int = Field(
        ge=1,
    )

    title: str | None = None

    extracted_text: str = ""

    tables: tuple[str, ...] = Field(
        default_factory=tuple,
    )

    drawings: tuple[str, ...] = Field(
        default_factory=tuple,
    )

    keywords: tuple[str, ...] = Field(
        default_factory=tuple,
    )

    @property
    def searchable_text(self) -> str:
        """Собрать VLM evidence страницы в единый текст."""
        parts = [
            self.title or "",
            self.extracted_text,
            *self.tables,
            *self.drawings,
            *self.keywords,
        ]

        return "\n".join(
            part.strip()
            for part in parts
            if part and part.strip()
        )


class DocumentVisionContext(DocumentModel):
    """Результат targeted VLM-анализа выбранных страниц."""

    pages: tuple[PageVisionResult, ...] = Field(
        min_length=1,
    )

    @property
    def searchable_text(self) -> str:
        """Объединить visual evidence страниц."""
        return "\n\n".join(
            page.searchable_text
            for page in self.pages
            if page.searchable_text
        )
    