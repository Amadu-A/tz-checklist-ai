# tests/acceptance/test_checklist_detection_samples.py

from pathlib import Path

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
from app.domain.enums import ChecklistCode
from app.infrastructure.ai.ollama_vlm_client import (
    OllamaVlmClient,
)
from app.infrastructure.checklists.yaml_checklist_repository import (
    YamlChecklistRepository,
)
from app.infrastructure.pdf.pymupdf_document_adapter import (
    PyMuPdfDocumentAdapter,
)


SAMPLES = {
    (
        "Пример ТЗ для проверки 2 "
        "(УУТЭ).pdf"
    ): ChecklistCode.UUTE,

    (
        "Пример ТЗ для проверки 3 "
        "(МКБИ).pdf"
    ): ChecklistCode.MKBI,

    (
        "Пример ТЗ для проверки 4 "
        "(ИТП).pdf"
    ): ChecklistCode.ITP,

    (
        "Пример ТЗ для проверки 5 "
        "(СПД).pdf"
    ): ChecklistCode.SPD,

    (
        "Пример ТЗ для проверки 6 "
        "(АУПТ).pdf"
    ): ChecklistCode.AUPT,
}


def _build_use_case(
    settings: Settings,
) -> SelectChecklistUseCase:
    """Собрать реальный production pipeline для acceptance test."""
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

    vlm_client = (
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

    content_service = (
        DocumentContentService(
            text_extractor=(
                pdf_adapter
            ),
            page_renderer=(
                pdf_adapter
            ),
            vlm_client=(
                vlm_client
            ),
        )
    )

    return SelectChecklistUseCase(
        content_service=(
            content_service
        ),
        classifier=(
            ChecklistClassifier(
                repository
                .get_catalog()
            )
        ),
        classification_max_pages=(
            settings
            .classification_max_pages
        ),
        min_native_chars=(
            settings
            .classification_min_native_chars
        ),
        min_confidence=(
            settings
            .classification_min_confidence
        ),
        min_page_chars=(
            settings
            .classification_min_page_chars
        ),
        vlm_fallback_max_pages=(
            settings
            .vlm_fallback_max_pages
        ),
    )


def test_all_five_private_acceptance_fixtures_are_present() -> None:
    """Этап 2 нельзя завершить без всех пяти эталонных PDF."""
    settings = Settings()

    missing = [
        name
        for name in SAMPLES
        if not (
            settings.test_data_dir
            / name
        ).is_file()
    ]

    assert not missing, (
        "Не хватает acceptance-файлов в "
        f"{settings.test_data_dir}: "
        f"{missing}"
    )


@pytest.mark.asyncio
@pytest.mark.parametrize(
    (
        "filename",
        "expected_code",
    ),
    SAMPLES.items(),
)
async def test_selects_expected_checklist_for_real_sample(
    filename: str,
    expected_code: ChecklistCode,
) -> None:
    """Проверить native-first/VLM-fallback pipeline на реальном ТЗ."""
    settings = Settings()

    use_case = (
        _build_use_case(
            settings
        )
    )

    pdf_path: Path = (
        settings.test_data_dir
        / filename
    )

    result = (
        await use_case.execute(
            pdf_path
        )
    )

    assert (
        result
        .suggestion
        .recommended_code
        == expected_code
    ), (
        f"Для {filename} выбран "
        f"{result.suggestion.recommended_code}; "
        f"ожидался {expected_code}. "
        f"source={result.source}; "
        f"fallback={result.fallback_reason}; "
        f"vision_pages={result.vision_pages}; "
        f"ranking={result.suggestion.ranking}"
    )
    