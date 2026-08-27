# app/application/services/analysis_pipeline_service.py

from time import perf_counter
from uuid import UUID

from app.application.ports.checklist_repository import (
    ChecklistRepositoryPort,
)
from app.application.ports.job_repository import JobRepositoryPort
from app.application.ports.job_storage import JobStoragePort
from app.application.ports.result_serializer import (
    ChecklistResultSerializerPort,
)
from app.application.services.checklist_answering_service import (
    ChecklistAnsweringService,
)
from app.application.services.checklist_result_builder import (
    ChecklistResultBuilder,
)
from app.application.services.document_chunker import DocumentChunker
from app.application.services.document_content_service import (
    DocumentContentService,
)
from app.application.services.visual_answer_fallback_service import (
    VisualAnswerFallbackService,
)
from app.domain.enums import ChecklistCode, JobStatus


class AnalysisPipelineService:
    """Полный lifecycle фоновой обработки ТЗ.

    success:

        input.pdf
            -> удаляется после обработки

        result.json
            -> временно хранится до action=result либо TTL

    failure:

        все temporary artifacts удаляются

    PDF report generation сейчас отключён.
    ReportLab implementation остаётся в проекте и может быть
    повторно подключён позже.
    """

    def __init__(
        self,
        *,
        repository: JobRepositoryPort,
        storage: JobStoragePort,
        checklist_repository: ChecklistRepositoryPort,
        content_service: DocumentContentService,
        chunker: DocumentChunker,
        answering_service: ChecklistAnsweringService,
        visual_fallback_service: VisualAnswerFallbackService,
        result_builder: ChecklistResultBuilder,
        result_serializer: ChecklistResultSerializerPort,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._checklist_repository = (
            checklist_repository
        )

        self._content_service = content_service
        self._chunker = chunker
        self._answering_service = answering_service
        self._visual_fallback_service = (
            visual_fallback_service
        )

        self._result_builder = result_builder
        self._result_serializer = (
            result_serializer
        )

    async def process(
        self,
        *,
        job_id: UUID,
        checklist_code: ChecklistCode,
    ) -> None:
        """Обработать подтверждённое либо tagged задание."""
        state = self._repository.get(
            job_id
        )

        if state is None:
            return

        if state.status == JobStatus.COMPLETED:
            return

        if state.status not in {
            JobStatus.QUEUED,
            JobStatus.PROCESSING,
        }:
            raise RuntimeError(
                "Job is not ready for background processing: "
                f"{state.status}"
            )

        self._repository.update(
            job_id,
            status=JobStatus.PROCESSING,
            checklist_code=checklist_code,
        )

        processing_started = perf_counter()

        try:
            pdf_path = self._storage.input_path(
                job_id
            )

            source_filename = (
                self._storage
                .source_filename(
                    job_id
                )
            )

            checklist = (
                self._checklist_repository
                .get(
                    checklist_code
                )
            )

            native_context = (
                self._content_service
                .extract_native(
                    pdf_path
                )
            )

            chunks = self._chunker.chunk(
                native_context
            )

            search_started = perf_counter()

            native_analysis = (
                await self._answering_service.analyze(
                    checklist=checklist,
                    chunks=chunks,
                )
            )

            final_analysis = (
                await self._visual_fallback_service.enrich(
                    pdf_path=pdf_path,
                    checklist=checklist,
                    native_context=native_context,
                    analysis=native_analysis,
                )
            )

            search_seconds = (
                perf_counter()
                - search_started
            )

            processing_seconds = (
                perf_counter()
                - processing_started
            )

            result = self._result_builder.build(
                request_id=job_id,
                source_filename=source_filename,
                checklist=checklist,
                analysis=final_analysis,
                processing_seconds=processing_seconds,
                search_seconds=search_seconds,
            )

            result_bytes = (
                self._result_serializer
                .serialize(
                    result
                )
            )

            self._storage.save_result(
                job_id,
                result_bytes,
            )

            self._repository.update(
                job_id,
                status=JobStatus.COMPLETED,
                checklist_code=checklist_code,
            )

        except Exception as exc:
            self._storage.delete_job_files(
                job_id
            )

            if (
                self._repository.get(
                    job_id
                )
                is not None
            ):
                self._repository.update(
                    job_id,
                    status=JobStatus.FAILED,
                    checklist_code=checklist_code,
                    error=self._safe_error(
                        exc
                    ),
                )

            raise

        finally:
            # После success остаётся только result.json.
            self._storage.delete_input(
                job_id
            )

    @staticmethod
    def _safe_error(
        exc: Exception,
    ) -> str:
        """Сохранить короткую ошибку без пользовательского payload."""
        text = (
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return text[:1000]
