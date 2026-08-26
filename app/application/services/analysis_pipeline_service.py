# app/application/services/analysis_pipeline_service.py

from uuid import UUID

from app.application.ports.checklist_repository import (
    ChecklistRepositoryPort,
)
from app.application.ports.job_repository import JobRepositoryPort
from app.application.ports.job_storage import JobStoragePort
from app.application.ports.report_renderer import ChecklistReportRendererPort
from app.application.services.checklist_answering_service import (
    ChecklistAnsweringService,
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
    """Полный lifecycle фоновой обработки одного ТЗ.

    Binary retention policy:

    success:
        input.pdf  -> удаляется
        result.pdf -> временно остаётся до GET result либо TTL

    failure:
        input.pdf  -> удаляется
        result.pdf -> удаляется

    Native text, chunks, embeddings и AI evidence существуют только
    в памяти worker и никогда не сохраняются в persistent storage.
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
        report_renderer: ChecklistReportRendererPort,
    ) -> None:
        self._repository = repository
        self._storage = storage
        self._checklist_repository = checklist_repository

        self._content_service = content_service
        self._chunker = chunker
        self._answering_service = answering_service
        self._visual_fallback_service = visual_fallback_service

        self._report_renderer = report_renderer

    async def process(
        self,
        *,
        job_id: UUID,
        checklist_code: ChecklistCode,
    ) -> None:
        """Обработать подтверждённое фоновое задание."""
        state = self._repository.get(
            job_id
        )

        # Возможен безопасный redelivery после того, как result уже
        # был выдан и metadata удалена.
        if state is None:
            return

        # task_acks_late может привести к повторной доставке уже
        # успешно завершённой задачи.
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

        try:
            pdf_path = self._storage.input_path(
                job_id
            )

            checklist = self._checklist_repository.get(
                checklist_code
            )

            native_context = (
                self._content_service.extract_native(
                    pdf_path
                )
            )

            chunks = self._chunker.chunk(
                native_context
            )

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

            report_bytes = self._report_renderer.render(
                checklist=checklist,
                analysis=final_analysis,
            )

            self._storage.save_result(
                job_id,
                report_bytes,
            )

            self._repository.update(
                job_id,
                status=JobStatus.COMPLETED,
                checklist_code=checklist_code,
            )

        except Exception as exc:
            # Ни исходный пользовательский файл, ни частично
            # сформированный report после ошибки оставаться не должны.
            self._storage.delete_job_files(
                job_id
            )

            if self._repository.get(
                job_id
            ) is not None:
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
            # На success удаляется только input.pdf.
            # result.pdf остаётся для одноразовой выдачи клиенту.
            self._storage.delete_input(
                job_id
            )

    @staticmethod
    def _safe_error(
        exc: Exception,
    ) -> str:
        """Сохранить небольшую диагностическую ошибку без payload."""
        text = (
            f"{type(exc).__name__}: "
            f"{exc}"
        )

        return text[:1000]
