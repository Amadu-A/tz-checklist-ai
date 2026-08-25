# app/application/ports/vlm_client.py

from typing import Protocol

from app.domain.documents import (
    PageVisionResult,
    PdfPageImage,
)


class VisionLanguageModelPort(Protocol):
    """Порт VLM, извлекающего факты из изображения страницы документа."""

    async def analyze_page(
        self,
        page: PdfPageImage,
    ) -> PageVisionResult:
        """Прочитать одну страницу и вернуть структурированный результат."""
        ...
    