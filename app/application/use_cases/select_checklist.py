# app/application/use_cases/select_checklist.py

from pathlib import Path

from app.application.services.checklist_classifier import (
    ChecklistClassifier,
)
from app.application.services.document_content_service import (
    DocumentContentService,
)
from app.domain.checklists import (
    ChecklistSelectionResult,
)
from app.domain.documents import (
    DocumentTextContext,
)
from app.domain.enums import (
    ClassificationSource,
    VlmFallbackReason,
)


class SelectChecklistUseCase:
    """Выбрать наиболее вероятный чек-лист для PDF.

    Алгоритм использует progressive fallback:

    1. Сначала читается native text через PyMuPDF.
    2. Если текста достаточно и classification confidence высокая,
       VLM вообще не вызывается.
    3. При слабом text layer либо низкой confidence выбираются
       несколько конкретных страниц.
    4. Только эти страницы рендерятся и передаются в VLM.
    5. Классификация повторяется по native + visual evidence.

    Результат всё равно остаётся только рекомендацией:
    окончательный выбор подтверждает пользователь.
    """

    def __init__(
        self,
        *,
        content_service: DocumentContentService,
        classifier: ChecklistClassifier,
        classification_max_pages: int,
        min_native_chars: int,
        min_confidence: float,
        min_page_chars: int,
        vlm_fallback_max_pages: int,
    ) -> None:
        self._content_service = (
            content_service
        )

        self._classifier = (
            classifier
        )

        self._classification_max_pages = (
            classification_max_pages
        )

        self._min_native_chars = (
            min_native_chars
        )

        self._min_confidence = (
            min_confidence
        )

        self._min_page_chars = (
            min_page_chars
        )

        self._vlm_fallback_max_pages = (
            vlm_fallback_max_pages
        )

    async def execute(
        self,
        pdf_path: Path,
    ) -> ChecklistSelectionResult:
        """Выполнить native-first выбор с targeted VLM fallback."""
        native_context = (
            self._content_service
            .extract_native(
                pdf_path,
                max_pages=(
                    self
                    ._classification_max_pages
                ),
            )
        )

        native_suggestion = (
            self._classifier
            .classify(
                native_context
                .searchable_text
            )
        )

        native_text_is_enough = (
            native_context
            .total_characters
            >= self._min_native_chars
        )

        native_classification_is_confident = (
            native_suggestion
            .ranking[0]
            .score
            > 0
            and native_suggestion
            .confidence
            >= self._min_confidence
        )

        if (
            native_text_is_enough
            and
            native_classification_is_confident
        ):
            return ChecklistSelectionResult(
                suggestion=(
                    native_suggestion
                ),
                source=(
                    ClassificationSource
                    .NATIVE_TEXT
                ),
            )

        fallback_reason = (
            VlmFallbackReason
            .INSUFFICIENT_NATIVE_TEXT
            if not native_text_is_enough
            else
            VlmFallbackReason
            .LOW_CONFIDENCE
        )

        page_numbers = (
            self._select_fallback_pages(
                native_context
            )
        )

        visual_context = (
            await self
            ._content_service
            .analyze_visual_pages(
                pdf_path,
                page_numbers=(
                    page_numbers
                ),
            )
        )

        combined_text = "\n\n".join(
            part
            for part in (
                native_context
                .searchable_text,

                visual_context
                .searchable_text,
            )
            if part.strip()
        )

        final_suggestion = (
            self._classifier
            .classify(
                combined_text
            )
        )

        return ChecklistSelectionResult(
            suggestion=(
                final_suggestion
            ),
            source=(
                ClassificationSource
                .NATIVE_TEXT_AND_VLM
            ),
            fallback_reason=(
                fallback_reason
            ),
            vision_pages=(
                page_numbers
            ),
        )

    def _select_fallback_pages(
        self,
        context: DocumentTextContext,
    ) -> tuple[int, ...]:
        """Выбрать минимальный набор страниц для VLM.

        В приоритете страницы со слабым или отсутствующим text layer.
        Если все страницы имеют текст, но classification confidence
        всё равно низкая, анализируются первые страницы документа.
        """
        weak_pages = tuple(
            page.page_number
            for page in context.pages
            if (
                page.character_count
                < self._min_page_chars
            )
        )

        if weak_pages:
            return weak_pages[
                :self
                ._vlm_fallback_max_pages
            ]

        return tuple(
            page.page_number
            for page in context.pages[
                :self
                ._vlm_fallback_max_pages
            ]
        )
