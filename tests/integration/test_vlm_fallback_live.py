# tests/integration/test_vlm_fallback_live.py

from pathlib import Path

import fitz
import pytest

from app.application.services.checklist_classifier import (
    ChecklistClassifier,
)
from app.application.services.document_content_service import (
    DocumentContentService,
)
from app.application.use_cases.select_checklist import (
    SelectChecklistUseCase,
)
from app.core.config import Settings
from app.domain.documents import (
    PageVisionResult,
    PdfPageImage,
)
from app.domain.enums import (
    ChecklistCode,
    ClassificationSource,
)
from app.infrastructure.ai.ollama_vlm_client import (
    OllamaVlmClient,
)
from app.infrastructure.checklists.yaml_checklist_repository import (
    YamlChecklistRepository,
)
from app.infrastructure.pdf.pymupdf_document_adapter import (
    PyMuPdfDocumentAdapter,
)


class RecordingVlmClient:
    """Декоратор VLM-клиента для диагностического integration test.

    Production-поведение не изменяется: вызов делегируется настоящему
    OllamaVlmClient.

    Дополнительно сохраняется структурированный PageVisionResult,
    чтобы при падении теста pytest автоматически показал текст,
    реально извлечённый VLM.
    """

    def __init__(
        self,
        delegate: OllamaVlmClient,
    ) -> None:
        self._delegate = delegate

        self.results: list[
            PageVisionResult
        ] = []

    async def analyze_page(
        self,
        page: PdfPageImage,
    ) -> PageVisionResult:
        """Вызвать реальную VLM и сохранить её результат."""
        result = (
            await self._delegate
            .analyze_page(
                page
            )
        )

        self.results.append(
            result
        )

        return result


def _create_scan_like_aupt_pdf(
    path: Path,
) -> None:
    """Создать PDF, где русский текст существует только внутри изображения.

    Сначала создаётся обычная страница с текстом и рендерится в JPEG.
    Затем JPEG помещается в новый PDF как единое изображение.

    Поэтому итоговый PDF визуально содержит технический текст,
    но PyMuPDF не может получить его через native text layer.
    """
    source = fitz.open()

    page = source.new_page(
        width=1000,
        height=1400,
    )

    font_path = Path(
        "/usr/share/fonts/truetype/"
        "dejavu/DejaVuSans.ttf"
    )

    page.insert_font(
        fontname="dejavu",
        fontfile=str(
            font_path
        ),
    )

    page.insert_text(
        (80, 150),
        (
            "ОПРОСНЫЙ ЛИСТ НА НАСОСНУЮ "
            "УСТАНОВКУ ПОЖАРОТУШЕНИЯ"
        ),
        fontsize=24,
        fontname="dejavu",
    )

    page.insert_text(
        (80, 220),
        (
            "Подача воды в систему "
            "противопожарного водопровода"
        ),
        fontsize=20,
        fontname="dejavu",
    )

    pixmap = (
        page.get_pixmap(
            dpi=144,
            alpha=False,
        )
    )

    image_bytes = (
        pixmap.tobytes(
            "jpeg",
            jpg_quality=90,
        )
    )

    source.close()

    scan = fitz.open()

    scan_page = (
        scan.new_page(
            width=1000,
            height=1400,
        )
    )

    scan_page.insert_image(
        scan_page.rect,
        stream=image_bytes,
    )

    scan.save(
        path
    )

    scan.close()


@pytest.mark.asyncio
async def test_real_vlm_is_used_for_scan_without_text_layer(
    tmp_path: Path,
) -> None:
    """Проверить настоящий native-text -> VLM fallback через shared Ollama."""
    settings = Settings()

    pdf_path = (
        tmp_path
        / "scan.pdf"
    )

    _create_scan_like_aupt_pdf(
        pdf_path
    )

    repository = (
        YamlChecklistRepository(
            settings
            .checklist_resources_dir
        )
    )

    pdf_adapter = (
        PyMuPdfDocumentAdapter(
            dpi=(
                settings
                .pdf_render_dpi
            ),
            jpeg_quality=(
                settings
                .pdf_jpeg_quality
            ),
        )
    )

    # Сначала тест автоматически доказывает,
    # что native text layer действительно отсутствует.
    native = (
        pdf_adapter.extract_text(
            pdf_path
        )
    )

    assert (
        native.total_characters
        == 0
    )

    recording_vlm = (
        RecordingVlmClient(
            OllamaVlmClient(
                base_url=(
                    settings
                    .ollama_base_url
                ),
                model=(
                    settings
                    .ollama_vlm_model
                ),
                keep_alive=(
                    settings
                    .ollama_keep_alive
                ),
                timeout_seconds=(
                    settings
                    .ollama_request_timeout_seconds
                ),
            )
        )
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
                recording_vlm
            ),
        )
    )

    use_case = (
        SelectChecklistUseCase(
            content_service=(
                service
            ),
            classifier=(
                ChecklistClassifier(
                    repository
                    .get_catalog()
                )
            ),
            classification_max_pages=1,
            min_native_chars=50,
            min_confidence=0.70,
            min_page_chars=20,
            vlm_fallback_max_pages=1,
        )
    )

    result = (
        await use_case.execute(
            pdf_path
        )
    )

    assert (
        result.source
        == (
            ClassificationSource
            .NATIVE_TEXT_AND_VLM
        )
    )

    assert (
        result.vision_pages
        == (1,)
    )

    visual_text = "\n\n".join(
        item.searchable_text
        for item
        in recording_vlm.results
    )

    assert (
        result
        .suggestion
        .recommended_code
        == ChecklistCode.AUPT
    ), (
        "VLM fallback выбрал неверный чек-лист. "
        f"VLM text={visual_text!r}; "
        f"ranking={result.suggestion.ranking}"
    )
