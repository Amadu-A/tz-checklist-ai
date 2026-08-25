# app/core/container.py

from dataclasses import dataclass
from functools import lru_cache

from app.application.services.checklist_classifier import (
    ChecklistClassifier,
)
from app.application.services.document_content_service import (
    DocumentContentService,
)
from app.application.services.readiness_service import (
    ReadinessService,
)
from app.application.use_cases.confirm_checklist import (
    ConfirmChecklistUseCase,
)
from app.application.use_cases.select_checklist import (
    SelectChecklistUseCase,
)
from app.core.config import get_settings
from app.infrastructure.ai.ollama_health_client import (
    OllamaHealthClient,
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


@dataclass(
    frozen=True,
    slots=True,
)
class Container:
    """Composition Root приложения.

    Только здесь concrete infrastructure adapters связываются
    с application services и use cases.
    """

    readiness_service: ReadinessService

    checklist_repository: (
        YamlChecklistRepository
    )

    select_checklist_use_case: (
        SelectChecklistUseCase
    )

    confirm_checklist_use_case: (
        ConfirmChecklistUseCase
    )


@lru_cache
def get_container() -> Container:
    """Собрать dependency graph приложения."""
    settings = get_settings()

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

    classifier = (
        ChecklistClassifier(
            repository.get_catalog()
        )
    )

    # На этапе 2 readiness проверяет только ту AI-модель,
    # которую проект действительно использует.
    ollama_health = (
        OllamaHealthClient(
            base_url=(
                settings
                .ollama_base_url
            ),
            timeout_seconds=min(
                settings
                .ollama_request_timeout_seconds,
                10.0,
            ),
            required_models=(
                settings
                .ollama_vlm_model,
            ),
        )
    )

    return Container(
        readiness_service=(
            ReadinessService(
                dependencies=(
                    ollama_health,
                ),
            )
        ),

        checklist_repository=(
            repository
        ),

        select_checklist_use_case=(
            SelectChecklistUseCase(
                content_service=(
                    content_service
                ),
                classifier=(
                    classifier
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
        ),

        confirm_checklist_use_case=(
            ConfirmChecklistUseCase(
                repository
            )
        ),
    )
