# app/infrastructure/storage/ephemeral_file_storage.py

import shutil
from pathlib import Path
from uuid import UUID


class EphemeralFileStorage:
    """Временное файловое хранилище одного job.

    Layout:

        /data/jobs/<uuid>/input.pdf
        /data/jobs/<uuid>/result.pdf

    Никакие intermediate text/chunks/embeddings сюда не записываются.

    Входной файл удаляет worker после завершения анализа либо ошибки.

    Результат удаляется методом consume_result() сразу после чтения
    bytes для передачи клиенту.

    delete_job_files() является страховочным аварийным механизмом.
    """

    INPUT_FILENAME = "input.pdf"
    RESULT_FILENAME = "result.pdf"

    def __init__(
        self,
        root_dir: Path,
    ) -> None:
        self._root_dir = root_dir

        self._root_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

    def save_input(
        self,
        job_id: UUID,
        pdf_bytes: bytes,
    ) -> Path:
        """Атомарно сохранить временный входной PDF."""
        if not pdf_bytes:
            raise ValueError(
                "Input PDF cannot be empty"
            )

        job_dir = self._job_dir(
            job_id
        )

        job_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        target = (
            job_dir
            / self.INPUT_FILENAME
        )

        temporary = (
            job_dir
            / f"{self.INPUT_FILENAME}.tmp"
        )

        temporary.write_bytes(
            pdf_bytes
        )

        temporary.replace(
            target
        )

        return target

    def input_path(
        self,
        job_id: UUID,
    ) -> Path:
        """Получить существующий входной PDF."""
        path = (
            self._job_dir(
                job_id
            )
            / self.INPUT_FILENAME
        )

        if not path.is_file():
            raise FileNotFoundError(
                path
            )

        return path

    def delete_input(
        self,
        job_id: UUID,
    ) -> None:
        """Idempotently удалить исходный PDF."""
        path = (
            self._job_dir(
                job_id
            )
            / self.INPUT_FILENAME
        )

        path.unlink(
            missing_ok=True
        )

        self._remove_empty_job_dir(
            job_id
        )

    def save_result(
        self,
        job_id: UUID,
        pdf_bytes: bytes,
    ) -> Path:
        """Атомарно сохранить временный PDF-результат."""
        if not pdf_bytes:
            raise ValueError(
                "Result PDF cannot be empty"
            )

        job_dir = self._job_dir(
            job_id
        )

        job_dir.mkdir(
            parents=True,
            exist_ok=True,
        )

        target = (
            job_dir
            / self.RESULT_FILENAME
        )

        temporary = (
            job_dir
            / f"{self.RESULT_FILENAME}.tmp"
        )

        temporary.write_bytes(
            pdf_bytes
        )

        temporary.replace(
            target
        )

        return target

    def consume_result(
        self,
        job_id: UUID,
    ) -> bytes:
        """Прочитать result.pdf и немедленно удалить серверную копию.

        После возврата из этого метода binary-файла результата
        на filesystem уже нет.

        API на этапе 4 передаст полученные bytes клиенту/1С.
        """
        path = (
            self._job_dir(
                job_id
            )
            / self.RESULT_FILENAME
        )

        if not path.is_file():
            raise FileNotFoundError(
                path
            )

        data = path.read_bytes()

        path.unlink()

        self._remove_empty_job_dir(
            job_id
        )

        return data

    def delete_job_files(
        self,
        job_id: UUID,
    ) -> None:
        """Удалить всю temporary directory задания."""
        shutil.rmtree(
            self._job_dir(
                job_id
            ),
            ignore_errors=True,
        )

    def has_input(
        self,
        job_id: UUID,
    ) -> bool:
        """Вернуть True, если исходный PDF ещё существует."""
        return (
            self._job_dir(
                job_id
            )
            / self.INPUT_FILENAME
        ).is_file()

    def has_result(
        self,
        job_id: UUID,
    ) -> bool:
        """Вернуть True, если результат ожидает выдачи."""
        return (
            self._job_dir(
                job_id
            )
            / self.RESULT_FILENAME
        ).is_file()

    def _job_dir(
        self,
        job_id: UUID,
    ) -> Path:
        """Получить безопасную директорию UUID job."""
        return (
            self._root_dir
            / str(job_id)
        )

    def _remove_empty_job_dir(
        self,
        job_id: UUID,
    ) -> None:
        """Удалить директорию job, если binary-файлов больше нет."""
        directory = self._job_dir(
            job_id
        )

        try:
            directory.rmdir()
        except (
            FileNotFoundError,
            OSError,
        ):
            return
