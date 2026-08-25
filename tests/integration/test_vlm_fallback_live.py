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


def _create_scan_like_aupt_pdf(
    path: Path,
) -> None:
    """Создать PDF, где русский текст существует только внутри изображения."""
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

    pixmap = page.get_pixmap(
        dpi=144,
        alpha=False,
    )

    image_bytes = (
        pixmap.tobytes(
            "jpeg",
            jpg_quality=90,
        )
    )

    source.close()

    scan = fitz.open()

    scan_page = scan.new_page(
        width=1000,
        height=1400,
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
    """Полный fallback должен работать на настоящем shared Ollama."""
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

    # Сначала автоматически доказываем,
    # что text layer действительно отсутствует.
    native = (
        pdf_adapter.extract_text(
            pdf_path
        )
    )

    assert (
        native.total_characters
        == 0
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

    assert (
        result
        .suggestion
        .recommended_code
        == ChecklistCode.AUPT
    )
