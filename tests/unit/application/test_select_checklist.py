# tests/unit/application/test_select_checklist.py

from pathlib import Path

import pytest

from app.application.services.checklist_classifier import (
    ChecklistClassifier,
)
from app.application.use_cases.select_checklist import (
    SelectChecklistUseCase,
)
from app.domain.checklists import (
    ChecklistCatalog,
    ChecklistCatalogEntry,
    ClassifierHint,
)
from app.domain.documents import (
    DocumentTextContext,
    DocumentVisionContext,
    PageVisionResult,
    PdfPageText,
)
from app.domain.enums import (
    ChecklistCode,
    ClassificationSource,
    VlmFallbackReason,
)

CATALOG = ChecklistCatalog(
    checklists=(
        ChecklistCatalogEntry(
            code=(
                ChecklistCode.UUTE
            ),
            title="УУТЭ",
            description="Узел учета",
            classifier_hints=(
                ClassifierHint(
                    text=(
                        "узел учета "
                        "тепловой энергии"
                    ),
                    weight=10,
                ),
            ),
        ),
        ChecklistCatalogEntry(
            code=(
                ChecklistCode.AUPT
            ),
            title="АУПТ",
            description=(
                "Пожаротушение"
            ),
            classifier_hints=(
                ClassifierHint(
                    text=(
                        "насосная установка "
                        "пожаротушения"
                    ),
                    weight=10,
                ),
            ),
        ),
    )
)


class FakeContentService:
    """Fake document service с контролем VLM-вызовов."""

    def __init__(
        self,
        *,
        native_context: DocumentTextContext,
        visual_context: DocumentVisionContext,
    ) -> None:
        self.native_context = (
            native_context
        )

        self.visual_context = (
            visual_context
        )

        self.visual_calls = 0

        self.requested_pages: tuple[
            int,
            ...,
        ] = ()

    def extract_native(
        self,
        pdf_path: Path,
        *,
        max_pages: int | None = None,
    ) -> DocumentTextContext:
        del pdf_path
        del max_pages

        return (
            self.native_context
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
        del pdf_path

        self.visual_calls += 1

        self.requested_pages = (
            page_numbers
        )

        return (
            self.visual_context
        )


def _build_use_case(
    service: FakeContentService,
) -> SelectChecklistUseCase:
    """Создать сценарий с одинаковыми threshold для тестов."""
    return SelectChecklistUseCase(
        content_service=service,
        classifier=(
            ChecklistClassifier(
                CATALOG
            )
        ),
        classification_max_pages=2,
        min_native_chars=50,
        min_confidence=0.70,
        min_page_chars=20,
        vlm_fallback_max_pages=2,
    )


@pytest.mark.asyncio
async def test_confident_native_text_does_not_call_vlm() -> None:
    """Нормальный PDF не должен расходовать GPU."""
    service = FakeContentService(
        native_context=(
            DocumentTextContext(
                pages=(
                    PdfPageText(
                        page_number=1,
                        text=(
                            "Коммерческий узел "
                            "учета тепловой энергии. "
                            "Узел учета тепловой энергии. "
                            "Рабочая документация."
                        ),
                    ),
                )
            )
        ),
        visual_context=(
            DocumentVisionContext(
                pages=(
                    PageVisionResult(
                        page_number=1,
                    ),
                )
            )
        ),
    )

    result = (
        await _build_use_case(
            service
        ).execute(
            Path("document.pdf")
        )
    )

    assert (
        result
        .suggestion
        .recommended_code
        == ChecklistCode.UUTE
    )

    assert (
        result.source
        == ClassificationSource.NATIVE_TEXT
    )

    assert (
        service.visual_calls
        == 0
    )

    assert (
        result.vision_pages
        == ()
    )


@pytest.mark.asyncio
async def test_insufficient_native_text_calls_vlm_only_for_weak_page() -> None:
    """Scan-like PDF должен перейти в targeted VLM fallback."""
    service = FakeContentService(
        native_context=(
            DocumentTextContext(
                pages=(
                    PdfPageText(
                        page_number=1,
                        text="",
                        image_count=1,
                    ),
                    PdfPageText(
                        page_number=2,
                        text=(
                            "Небольшой текст"
                        ),
                    ),
                )
            )
        ),
        visual_context=(
            DocumentVisionContext(
                pages=(
                    PageVisionResult(
                        page_number=1,
                        extracted_text=(
                            "Опросный лист на "
                            "насосную установку "
                            "пожаротушения"
                        ),
                    ),
                )
            )
        ),
    )

    result = (
        await _build_use_case(
            service
        ).execute(
            Path("scan.pdf")
        )
    )

    assert (
        result
        .suggestion
        .recommended_code
        == ChecklistCode.AUPT
    )

    assert (
        result.source
        == (
            ClassificationSource
            .NATIVE_TEXT_AND_VLM
        )
    )

    assert (
        result.fallback_reason
        == (
            VlmFallbackReason
            .INSUFFICIENT_NATIVE_TEXT
        )
    )

    assert (
        1
        in service.requested_pages
    )

    assert (
        service.visual_calls
        == 1
    )


@pytest.mark.asyncio
async def test_low_confidence_native_text_triggers_vlm() -> None:
    """Даже большой текст должен перейти в VLM при слабой классификации."""
    service = FakeContentService(
        native_context=(
            DocumentTextContext(
                pages=(
                    PdfPageText(
                        page_number=1,
                        text=(
                            "Общие сведения "
                            "о строительном объекте. "
                            "Технические решения. "
                            "Описание оборудования. "
                            "Рабочая документация."
                        ),
                    ),
                )
            )
        ),
        visual_context=(
            DocumentVisionContext(
                pages=(
                    PageVisionResult(
                        page_number=1,
                        title=(
                            "Насосная установка "
                            "пожаротушения"
                        ),
                    ),
                )
            )
        ),
    )

    result = (
        await _build_use_case(
            service
        ).execute(
            Path("unclear.pdf")
        )
    )

    assert (
        result
        .suggestion
        .recommended_code
        == ChecklistCode.AUPT
    )

    assert (
        result.fallback_reason
        == (
            VlmFallbackReason
            .LOW_CONFIDENCE
        )
    )

    assert (
        service.visual_calls
        == 1
    )
