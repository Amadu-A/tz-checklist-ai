# app/application/ports/job_storage.py

from datetime import datetime
from pathlib import Path
from typing import Protocol
from uuid import UUID


class JobStoragePort(Protocol):
    """Порт временного хранения пользовательских artifacts.

    В storage могут существовать только:

        input.pdf
        source_filename.txt
        result.json

    Все они временные.
    """

    def save_input(
        self,
        job_id: UUID,
        pdf_bytes: bytes,
        *,
        source_filename: str = "document.pdf",
    ) -> Path:
        """Временно сохранить исходный PDF и его имя."""
        ...

    def input_path(
        self,
        job_id: UUID,
    ) -> Path:
        """Получить путь к временному входному PDF."""
        ...

    def source_filename(
        self,
        job_id: UUID,
    ) -> str:
        """Получить исходное имя пользовательского файла."""
        ...

    def delete_input(
        self,
        job_id: UUID,
    ) -> None:
        """Удалить исходный PDF и временное имя файла."""
        ...

    def save_result(
        self,
        job_id: UUID,
        result_bytes: bytes,
    ) -> Path:
        """Временно сохранить JSON-результат."""
        ...

    def consume_result(
        self,
        job_id: UUID,
    ) -> bytes:
        """Прочитать JSON и сразу удалить серверную копию."""
        ...

    def delete_job_files(
        self,
        job_id: UUID,
    ) -> None:
        """Удалить все temporary artifacts задания."""
        ...

    def cleanup_orphaned_files(
        self,
        *,
        known_job_ids: frozenset[UUID],
        cutoff: datetime,
    ) -> int:
        """Удалить старые filesystem artifacts без живого job."""
        ...

    def has_input(
        self,
        job_id: UUID,
    ) -> bool:
        """Проверить наличие исходного PDF."""
        ...

    def has_result(
        self,
        job_id: UUID,
    ) -> bool:
        """Проверить наличие JSON-результата."""
        ...
