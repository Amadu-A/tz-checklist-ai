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

    Безопасный lifecycle выдачи:

        1. проверить состояние COMPLETED;
        2. успешно прочитать result.pdf в bytes;
        3. удалить оставшиеся binary-файлы job;
        4. удалить metadata;
        5. вернуть bytes HTTP-слою.

    Если result.pdf не удалось прочитать, metadata намеренно
    сохраняется. Это позволяет повторить выдачу после устранения
    transient filesystem-проблемы и не превращает job в потерянный.
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
        """Получить завершённый result и удалить backend-состояние."""
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

        # Важно: metadata нельзя удалять в finally.
        #
        # Если чтение result.pdf упадёт, исключение выйдет наружу,
        # а JobState останется COMPLETED и сможет быть повторно
        # запрошен после восстановления filesystem.
        pdf_bytes = (
            self._storage
            .consume_result(
                job_id
            )
        )

        # consume_result() уже удаляет сам result.pdf после успешного
        # чтения. Этот вызов idempotent и страхует от оставшихся
        # temporary binary-файлов конкретного job.
        self._storage.delete_job_files(
            job_id
        )

        # Metadata удаляем только после успешного получения bytes.
        self._repository.delete(
            job_id
        )

        return pdf_bytes
