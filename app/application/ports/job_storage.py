# app/application/ports/job_storage.py

from pathlib import Path
from typing import Protocol
from uuid import UUID


class JobStoragePort(Protocol):
    """Порт временного хранения пользовательских binary-файлов.

    Все файлы в этом storage являются временными.

    Backend никогда не должен использовать это хранилище
    как архив пользовательской документации.
    """

    def save_input(
        self,
        job_id: UUID,
        pdf_bytes: bytes,
    ) -> Path:
        """Временно сохранить исходный PDF."""
        ...

    def input_path(
        self,
        job_id: UUID,
    ) -> Path:
        """Получить путь к временному входному PDF."""
        ...

    def delete_input(
        self,
        job_id: UUID,
    ) -> None:
        """Удалить исходный пользовательский PDF."""
        ...

    def save_result(
        self,
        job_id: UUID,
        pdf_bytes: bytes,
    ) -> Path:
        """Временно сохранить сформированный PDF-отчёт."""
        ...

    def consume_result(
        self,
        job_id: UUID,
    ) -> bytes:
        """Прочитать результат и сразу удалить серверную копию."""
        ...

    def delete_job_files(
        self,
        job_id: UUID,
    ) -> None:
        """Удалить все binary-файлы задания."""
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
        """Проверить наличие результирующего PDF."""
        ...
    