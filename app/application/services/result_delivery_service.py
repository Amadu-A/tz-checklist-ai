# app/application/services/result_delivery_service.py

from uuid import UUID

from app.application.ports.job_repository import (
    JobRepositoryPort,
)
from app.application.ports.job_storage import (
    JobStoragePort,
)
from app.domain.enums import JobStatus


class ResultDeliveryService:
    """Одноразово выдаёт PDF-результат и удаляет backend-копию.

    Сервис ничего не знает о FastAPI или 1С.

    На этапе 4 HTTP endpoint:

        1. вызовет consume();
        2. получит PDF bytes;
        3. положит bytes в HTTP Response.

    Сам binary-файл к этому моменту уже удалён с диска.
    """

    def __init__(
        self,
        *,
        repository: JobRepositoryPort,
        storage: JobStoragePort,
    ) -> None:
        self._repository = repository
        self._storage = storage

    def consume(
        self,
        job_id: UUID,
    ) -> bytes:
        """Получить завершённый result и удалить файлы/metadata."""
        state = self._repository.get(
            job_id
        )

        if state is None:
            raise KeyError(
                f"Unknown job_id: {job_id}"
            )

        if (
            state.status
            != JobStatus.COMPLETED
        ):
            raise RuntimeError(
                "Result is not ready"
            )

        try:
            return (
                self._storage
                .consume_result(
                    job_id
                )
            )
        finally:
            # После выдачи backend больше не обязан помнить job.
            self._storage.delete_job_files(
                job_id
            )

            self._repository.delete(
                job_id
            )
            