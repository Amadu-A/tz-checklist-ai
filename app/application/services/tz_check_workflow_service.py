# app/application/services/tz_check_workflow_service.py

from uuid import UUID, uuid4

from app.application.errors import (
    InvalidJobStateError,
    InvalidPdfError,
    JobNotFoundError,
    QueueSubmissionError,
    ResultNotReadyError,
    UploadTooLargeError,
)
from app.application.ports.job_repository import JobRepositoryPort
from app.application.ports.job_storage import JobStoragePort
from app.application.ports.task_queue import TaskQueuePort
from app.application.services.result_delivery_service import (
    ResultDeliveryService,
)
from app.application.use_cases.confirm_checklist import (
    ConfirmChecklistUseCase,
)
from app.application.use_cases.select_checklist import (
    SelectChecklistUseCase,
)
from app.domain.enums import (
    ChecklistCode,
    ChecklistTag,
    JobStatus,
)
from app.domain.workflow import (
    WorkflowConfirmationResult,
    WorkflowSelectionResult,
    WorkflowStatusResult,
    WorkflowTaggedSubmissionResult,
)


class TzCheckWorkflowService:
    """Оркестрирует lifecycle единого /tz-check endpoint.

    Вариант 1:

        SELECT + checklist_tag
            -> сохранить PDF
            -> пропустить classification
            -> QUEUED

    Вариант 2:

        SELECT без checklist_tag
            -> сохранить PDF
            -> auto-classification
            -> AWAITING_CONFIRMATION
            -> CONFIRM
            -> QUEUED

    RESULT:
        одноразово возвращает JSON и удаляет backend state.
    """

    _PROGRESS_BY_STATUS = {
        JobStatus.AWAITING_CONFIRMATION: 10,
        JobStatus.QUEUED: 25,
        JobStatus.PROCESSING: 60,
        JobStatus.COMPLETED: 100,
        JobStatus.FAILED: 100,
    }

    def __init__(
        self,
        *,
        select_use_case: SelectChecklistUseCase,
        confirm_use_case: ConfirmChecklistUseCase,
        repository: JobRepositoryPort,
        storage: JobStoragePort,
        task_queue: TaskQueuePort,
        result_delivery_service: ResultDeliveryService,
        max_upload_bytes: int,
    ) -> None:
        if max_upload_bytes <= 0:
            raise ValueError(
                "max_upload_bytes must be positive"
            )

        self._select_use_case = select_use_case
        self._confirm_use_case = confirm_use_case

        self._repository = repository
        self._storage = storage
        self._task_queue = task_queue

        self._result_delivery_service = (
            result_delivery_service
        )

        self._max_upload_bytes = (
            max_upload_bytes
        )

    async def select(
        self,
        pdf_bytes: bytes,
        *,
        source_filename: str = "document.pdf",
        checklist_tag: ChecklistTag | None = None,
    ) -> (
        WorkflowSelectionResult
        | WorkflowTaggedSubmissionResult
    ):
        """Принять PDF и выбрать direct либо automatic workflow."""
        self._validate_pdf(
            pdf_bytes
        )

        safe_filename = (
            self._normalize_source_filename(
                source_filename
            )
        )

        if checklist_tag is not None:
            return self._submit_tagged(
                pdf_bytes=pdf_bytes,
                source_filename=safe_filename,
                checklist_tag=checklist_tag,
            )

        return await self._select_automatically(
            pdf_bytes=pdf_bytes,
            source_filename=safe_filename,
        )

    async def _select_automatically(
        self,
        *,
        pdf_bytes: bytes,
        source_filename: str,
    ) -> WorkflowSelectionResult:
        """Сохранить PDF и запустить нынешнюю классификацию."""
        request_id = uuid4()

        self._repository.create(
            request_id,
            status=(
                JobStatus
                .AWAITING_CONFIRMATION
            ),
        )

        try:
            pdf_path = self._storage.save_input(
                request_id,
                pdf_bytes,
                source_filename=source_filename,
            )

            selection = (
                await self._select_use_case.execute(
                    pdf_path
                )
            )

            return WorkflowSelectionResult(
                request_id=request_id,
                selection=selection,
            )

        except Exception:
            self._storage.delete_job_files(
                request_id
            )

            if (
                self._repository.get(
                    request_id
                )
                is not None
            ):
                self._repository.delete(
                    request_id
                )

            raise

    def _submit_tagged(
        self,
        *,
        pdf_bytes: bytes,
        source_filename: str,
        checklist_tag: ChecklistTag,
    ) -> WorkflowTaggedSubmissionResult:
        """Пропустить classification и сразу поставить job в очередь."""
        confirmed = (
            self._confirm_use_case
            .execute(
                checklist_tag.code
            )
        )

        request_id = uuid4()

        self._repository.create(
            request_id,
            status=JobStatus.QUEUED,
            checklist_code=confirmed.code,
        )

        try:
            self._storage.save_input(
                request_id,
                pdf_bytes,
                source_filename=source_filename,
            )
        except Exception:
            self._repository.delete(
                request_id
            )
            raise

        try:
            self._task_queue.enqueue_analysis(
                request_id,
                confirmed.code,
            )
        except Exception as exc:
            self._storage.delete_job_files(
                request_id
            )

            if (
                self._repository.get(
                    request_id
                )
                is not None
            ):
                self._repository.delete(
                    request_id
                )

            raise QueueSubmissionError(
                "Failed to submit job to RabbitMQ"
            ) from exc

        return WorkflowTaggedSubmissionResult(
            request_id=request_id,
            checklist=confirmed,
            checklist_tag=checklist_tag,
        )

    def confirm(
        self,
        *,
        request_id: UUID,
        checklist_code: ChecklistCode,
    ) -> WorkflowConfirmationResult:
        """Подтвердить auto-detected checklist либо override."""
        state = self._get_required_state(
            request_id
        )

        confirmed = self._confirm_use_case.execute(
            checklist_code
        )

        if (
            state.status
            == JobStatus.AWAITING_CONFIRMATION
        ):
            if not self._storage.has_input(
                request_id
            ):
                raise InvalidJobStateError(
                    "Temporary source PDF is missing"
                )

            self._repository.update(
                request_id,
                status=JobStatus.QUEUED,
                checklist_code=confirmed.code,
            )

            try:
                self._task_queue.enqueue_analysis(
                    request_id,
                    confirmed.code,
                )
            except Exception as exc:
                self._repository.update(
                    request_id,
                    status=(
                        JobStatus
                        .AWAITING_CONFIRMATION
                    ),
                    checklist_code=confirmed.code,
                )

                raise QueueSubmissionError(
                    "Failed to submit job to RabbitMQ"
                ) from exc

            return WorkflowConfirmationResult(
                request_id=request_id,
                checklist=confirmed,
                status=JobStatus.QUEUED,
            )

        if state.status in {
            JobStatus.QUEUED,
            JobStatus.PROCESSING,
            JobStatus.COMPLETED,
        }:
            if (
                state.checklist_code
                != confirmed.code
            ):
                raise InvalidJobStateError(
                    "Job has already been confirmed "
                    "with another checklist"
                )

            return WorkflowConfirmationResult(
                request_id=request_id,
                checklist=confirmed,
                status=state.status,
            )

        raise InvalidJobStateError(
            "Job cannot be confirmed in state: "
            f"{state.status}"
        )

    def status(
        self,
        request_id: UUID,
    ) -> WorkflowStatusResult:
        """Получить техническое состояние job."""
        state = self._get_required_state(
            request_id
        )

        return WorkflowStatusResult(
            request_id=request_id,
            status=state.status,
            checklist_code=state.checklist_code,
            progress_percent=(
                self._PROGRESS_BY_STATUS[
                    state.status
                ]
            ),
            result_ready=(
                state.status
                == JobStatus.COMPLETED
            ),
            error=(
                state.error
                if state.status
                == JobStatus.FAILED
                else None
            ),
        )

    def result(
        self,
        request_id: UUID,
    ) -> bytes:
        """Одноразово получить готовый JSON-result."""
        state = self._get_required_state(
            request_id
        )

        if state.status != JobStatus.COMPLETED:
            raise ResultNotReadyError(
                f"Result is not ready: {state.status}"
            )

        try:
            return (
                self._result_delivery_service
                .consume(
                    request_id
                )
            )
        except (
            KeyError,
            FileNotFoundError,
        ) as exc:
            raise JobNotFoundError(
                "Result no longer exists: "
                f"{request_id}"
            ) from exc

    def _get_required_state(
        self,
        request_id: UUID,
    ):
        """Получить существующий job либо domain error."""
        state = self._repository.get(
            request_id
        )

        if state is None:
            raise JobNotFoundError(
                f"Unknown request_id: {request_id}"
            )

        return state

    def _validate_pdf(
        self,
        pdf_bytes: bytes,
    ) -> None:
        """Дешёвая validation до записи файла."""
        if not pdf_bytes:
            raise InvalidPdfError(
                "Uploaded PDF is empty"
            )

        if (
            len(pdf_bytes)
            > self._max_upload_bytes
        ):
            raise UploadTooLargeError(
                "Uploaded PDF exceeds size limit"
            )

        if not pdf_bytes.lstrip().startswith(
            b"%PDF-"
        ):
            raise InvalidPdfError(
                "Uploaded file is not a PDF"
            )

    @staticmethod
    def _normalize_source_filename(
        source_filename: str,
    ) -> str:
        """Удалить клиентские пути и ограничить filename metadata."""
        value = (
            source_filename
            .replace(
                "\\",
                "/",
            )
            .rsplit(
                "/",
                1,
            )[-1]
            .replace(
                "\x00",
                "",
            )
            .strip()
        )

        if (
            not value
            or value in {
                ".",
                "..",
            }
        ):
            return "document.pdf"

        return value[:255]
