# app/core/container.py

from dataclasses import dataclass
from functools import lru_cache

from app.application.services.checklist_classifier import ChecklistClassifier
from app.application.services.document_chunker import DocumentChunker
from app.application.services.document_content_service import DocumentContentService
from app.application.services.hybrid_retriever import HybridRetriever
from app.application.services.readiness_service import ReadinessService
from app.application.services.result_delivery_service import ResultDeliveryService
from app.application.services.retention_service import RetentionService
from app.application.use_cases.confirm_checklist import ConfirmChecklistUseCase
from app.application.use_cases.select_checklist import SelectChecklistUseCase
from app.core.config import get_settings
from app.infrastructure.ai.ollama_embedding_client import OllamaEmbeddingClient
from app.infrastructure.ai.ollama_health_client import OllamaHealthClient
from app.infrastructure.ai.ollama_vlm_client import OllamaVlmClient
from app.infrastructure.checklists.yaml_checklist_repository import (
    YamlChecklistRepository,
)
from app.infrastructure.pdf.pymupdf_document_adapter import PyMuPdfDocumentAdapter
from app.infrastructure.persistence.sqlite_job_repository import SqliteJobRepository
from app.infrastructure.queue.celery_task_queue import CeleryTaskQueue
from app.infrastructure.storage.ephemeral_file_storage import EphemeralFileStorage


@dataclass(
    frozen=True,
    slots=True,
)
class Container:
    """Composition Root приложения."""

    readiness_service: ReadinessService

    checklist_repository: YamlChecklistRepository

    select_checklist_use_case: SelectChecklistUseCase

    confirm_checklist_use_case: ConfirmChecklistUseCase

    document_chunker: DocumentChunker

    retriever: HybridRetriever

    job_repository: SqliteJobRepository

    job_storage: EphemeralFileStorage

    task_queue: CeleryTaskQueue

    result_delivery_service: ResultDeliveryService

    retention_service: RetentionService


@lru_cache
def get_container() -> Container:
    """Собрать dependency graph приложения."""
    settings = get_settings()

    checklist_repository = YamlChecklistRepository(
        settings.checklist_resources_dir
    )

    pdf_adapter = PyMuPdfDocumentAdapter(
        dpi=settings.pdf_render_dpi,
        jpeg_quality=settings.pdf_jpeg_quality,
    )

    vlm_client = OllamaVlmClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_vlm_model,
        keep_alive=settings.ollama_keep_alive,
        timeout_seconds=settings.ollama_request_timeout_seconds,
    )

    embedding_client = OllamaEmbeddingClient(
        base_url=settings.ollama_base_url,
        model=settings.ollama_embedding_model,
        keep_alive=settings.ollama_keep_alive,
        timeout_seconds=settings.ollama_request_timeout_seconds,
    )

    content_service = DocumentContentService(
        text_extractor=pdf_adapter,
        page_renderer=pdf_adapter,
        vlm_client=vlm_client,
    )

    classifier = ChecklistClassifier(
        checklist_repository.get_catalog()
    )

    document_chunker = DocumentChunker(
        max_chars=settings.retrieval_chunk_max_chars,
        overlap_chars=settings.retrieval_chunk_overlap_chars,
    )

    retriever = HybridRetriever(
        embedding_client=embedding_client,
        top_k=settings.retrieval_top_k,
        batch_size=settings.retrieval_embedding_batch_size,
        semantic_weight=settings.retrieval_semantic_weight,
        lexical_weight=settings.retrieval_lexical_weight,
    )

    ollama_health = OllamaHealthClient(
        base_url=settings.ollama_base_url,
        timeout_seconds=min(
            settings.ollama_request_timeout_seconds,
            10.0,
        ),
        required_models=(
            settings.ollama_vlm_model,
            settings.ollama_embedding_model,
        ),
    )

    job_repository = SqliteJobRepository(
        settings.job_database_path
    )

    job_storage = EphemeralFileStorage(
        settings.jobs_dir
    )

    result_delivery_service = ResultDeliveryService(
        repository=job_repository,
        storage=job_storage,
    )

    retention_service = RetentionService(
        repository=job_repository,
        storage=job_storage,
        result_ttl_minutes=settings.result_file_ttl_minutes,
        orphan_ttl_hours=settings.orphan_job_ttl_hours,
        failed_state_ttl_hours=settings.failed_job_state_ttl_hours,
    )

    task_queue = CeleryTaskQueue(
        broker_url=settings.rabbitmq_url,
        queue_name=settings.celery_queue_name,
    )

    return Container(
        readiness_service=ReadinessService(
            dependencies=(
                ollama_health,
            ),
        ),
        checklist_repository=checklist_repository,
        select_checklist_use_case=SelectChecklistUseCase(
            content_service=content_service,
            classifier=classifier,
            classification_max_pages=settings.classification_max_pages,
            min_native_chars=settings.classification_min_native_chars,
            min_confidence=settings.classification_min_confidence,
            min_page_chars=settings.classification_min_page_chars,
            vlm_fallback_max_pages=settings.vlm_fallback_max_pages,
        ),
        confirm_checklist_use_case=ConfirmChecklistUseCase(
            checklist_repository
        ),
        document_chunker=document_chunker,
        retriever=retriever,
        job_repository=job_repository,
        job_storage=job_storage,
        task_queue=task_queue,
        result_delivery_service=result_delivery_service,
        retention_service=retention_service,
    )