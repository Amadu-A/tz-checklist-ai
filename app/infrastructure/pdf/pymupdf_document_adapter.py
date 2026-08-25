# app/infrastructure/pdf/pymupdf_document_adapter.py

from pathlib import Path

import fitz

from app.domain.documents import (
    DocumentTextContext,
    PdfPageImage,
    PdfPageText,
)


class PyMuPdfDocumentAdapter:
    """PyMuPDF-адаптер для быстрого чтения и targeted rendering.

    Основной путь работы — extract_text(), который не использует GPU
    и не переводит PDF в изображения.

    render_page() вызывается только тогда, когда application layer
    решил, что для конкретной страницы действительно нужна VLM.
    """

    def __init__(
        self,
        *,
        dpi: int = 144,
        jpeg_quality: int = 85,
    ) -> None:
        self._dpi = dpi
        self._jpeg_quality = jpeg_quality

    def extract_text(
        self,
        pdf_path: Path,
        *,
        max_pages: int | None = None,
    ) -> DocumentTextContext:
        """Получить native text первых или всех страниц PDF."""
        self._validate_pdf(
            pdf_path
        )

        if (
            max_pages is not None
            and max_pages < 1
        ):
            raise ValueError(
                "max_pages must be positive"
            )

        pages: list[
            PdfPageText
        ] = []

        with fitz.open(
            str(pdf_path)
        ) as document:
            if len(document) == 0:
                raise ValueError(
                    "PDF does not contain pages"
                )

            limit = (
                min(
                    len(document),
                    max_pages,
                )
                if max_pages is not None
                else len(document)
            )

            for index in range(
                limit
            ):
                page = document[
                    index
                ]

                # sort=True улучшает порядок чтения обычных
                # текстовых проектных документов.
                text = page.get_text(
                    "text",
                    sort=True,
                )

                image_count = len(
                    page.get_images(
                        full=True
                    )
                )

                pages.append(
                    PdfPageText(
                        page_number=index + 1,
                        text=text,
                        image_count=image_count,
                    )
                )

        return DocumentTextContext(
            pages=tuple(
                pages
            )
        )

    def render_page(
        self,
        pdf_path: Path,
        *,
        page_number: int,
    ) -> PdfPageImage:
        """Отрендерить только одну указанную страницу."""
        self._validate_pdf(
            pdf_path
        )

        if page_number < 1:
            raise ValueError(
                "page_number must be positive"
            )

        with fitz.open(
            str(pdf_path)
        ) as document:
            if page_number > len(
                document
            ):
                raise ValueError(
                    "page_number exceeds "
                    "PDF page count"
                )

            page = document[
                page_number - 1
            ]

            pixmap = page.get_pixmap(
                dpi=self._dpi,
                alpha=False,
            )

            image_bytes = (
                pixmap.tobytes(
                    "jpeg",
                    jpg_quality=(
                        self._jpeg_quality
                    ),
                )
            )

        return PdfPageImage(
            page_number=page_number,
            image_bytes=image_bytes,
            mime_type="image/jpeg",
        )

    @staticmethod
    def _validate_pdf(
        pdf_path: Path,
    ) -> None:
        """Проверить существование и расширение входного файла."""
        if not pdf_path.is_file():
            raise FileNotFoundError(
                pdf_path
            )

        if (
            pdf_path.suffix.casefold()
            != ".pdf"
        ):
            raise ValueError(
                "Only PDF files are supported"
            )
        