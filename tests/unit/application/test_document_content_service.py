# tests/unit/application/test_document_content_service.py

import asyncio
from pathlib import Path

import pytest

from app.application.services.document_content_service import (
    DocumentContentService,
)
from app.domain.documents import (
    DocumentTextContext,
    PageVisionResult,
    PdfPageImage,
    PdfPageText,
)


class FakePdfAdapter:
    """Fake PDF adapter для проверки application service."""

    def __init__(
        self,
    ) -> None:
        self.rendered_pages: list[
            int
        ] = []

    def extract_text(
        self,
        pdf_path: Path,
        *,
        max_pages: int | None = None,
    ) -> DocumentTextContext:
        """Вернуть fake native text."""
        del pdf_path
        del max_pages

        return DocumentTextContext(
            pages=(
                PdfPageText(
                    page_number=1,
                    text="native text",
                ),
            )
        )

    def render_page(
        self,
        pdf_path: Path,
        *,
        page_number: int,
    ) -> PdfPageImage:
        """Запомнить только реально запрошенную страницу."""
        del pdf_path

        self.rendered_pages.append(
            page_number
        )

        return PdfPageImage(
            page_number=page_number,
            image_bytes=(
                f"page-{page_number}"
                .encode()
            ),
            mime_type="image/jpeg",
        )


class ConcurrencyTrackingVlm:
    """Fake VLM, измеряющая параллелизм вызовов."""

    def __init__(
        self,
    ) -> None:
        self.active = 0
        self.max_active = 0

    async def analyze_page(
        self,
        page: PdfPageImage,
    ) -> PageVisionResult:
        self.active += 1

        self.max_active = max(
            self.max_active,
            self.active,
        )

        await asyncio.sleep(
            0
        )

        self.active -= 1

        return PageVisionResult(
            page_number=(
                page.page_number
            ),
            extracted_text=(
                f"visual page "
                f"{page.page_number}"
            ),
        )


@pytest.mark.asyncio
async def test_only_requested_pages_are_rendered_and_vlm_is_sequential() -> None:
    """Не должно быть полного render PDF или параллельных VLM calls."""
    pdf_adapter = (
        FakePdfAdapter()
    )

    vlm = (
        ConcurrencyTrackingVlm()
    )

    service = (
        DocumentContentService(
            text_extractor=(
                pdf_adapter
            ),
            page_renderer=(
                pdf_adapter
            ),
            vlm_client=(
                vlm
            ),
        )
    )

    result = (
        await service
        .analyze_visual_pages(
            Path(
                "ignored.pdf"
            ),
            page_numbers=(
                2,
                5,
            ),
        )
    )

    assert (
        pdf_adapter
        .rendered_pages
        == [
            2,
            5,
        ]
    )

    assert [
        page.page_number
        for page in result.pages
    ] == [
        2,
        5,
    ]

    assert (
        vlm.max_active
        == 1
    )
    