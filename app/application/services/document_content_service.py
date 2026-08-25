# app/application/services/document_content_service.py

from pathlib import Path

from app.application.ports.pdf_document import (
    PdfPageRendererPort,
    PdfTextExtractorPort,
)
from app.application.ports.vlm_client import (
    VisionLanguageModelPort,
)
from app.domain.documents import (
    DocumentTextContext,
    DocumentVisionContext,
)


class DocumentContentService:
    """Предоставляет native text и targeted visual evidence PDF.

    Сервис сознательно не рендерит документ целиком.

    VLM-вызовы выполняются строго последовательно, чтобы несколько
    страниц одного документа не конкурировали за VRAM RTX 3090.
    """

    def __init__(
        self,
        *,
        text_extractor: PdfTextExtractorPort,
        page_renderer: PdfPageRendererPort,
        vlm_client: VisionLanguageModelPort,
    ) -> None:
        self._text_extractor = text_extractor
        self._page_renderer = page_renderer
        self._vlm_client = vlm_client

    def extract_native(
        self,
        pdf_path: Path,
        *,
        max_pages: int | None = None,
    ) -> DocumentTextContext:
        """Получить native text без использования GPU."""
        return (
            self._text_extractor
            .extract_text(
                pdf_path,
                max_pages=max_pages,
            )
        )

    async def analyze_visual_pages(
        self,
        pdf_path: Path,
        *,
        page_numbers: tuple[
            int,
            ...,
        ],
    ) -> DocumentVisionContext:
        """Последовательно проанализировать только выбранные страницы."""
        if not page_numbers:
            raise ValueError(
                "page_numbers cannot be empty"
            )

        results = []

        # Намеренно не используем asyncio.gather().
        for page_number in page_numbers:
            page_image = (
                self._page_renderer
                .render_page(
                    pdf_path,
                    page_number=(
                        page_number
                    ),
                )
            )

            results.append(
                await self._vlm_client
                .analyze_page(
                    page_image
                )
            )

        return DocumentVisionContext(
            pages=tuple(
                results
            )
        )
