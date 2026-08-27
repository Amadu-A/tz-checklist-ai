# app/infrastructure/storage/ephemeral_file_storage.py

import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID


class EphemeralFileStorage:
    """Временное файловое хранилище одного job.

    Layout:

        /data/jobs/<uuid>/input.pdf
        /data/jobs/<uuid>/source_filename.txt
        /data/jobs/<uuid>/result.json

    Native text, chunks и embeddings сюда не записываются.
    """

    INPUT_FILENAME = "input.pdf"
    SOURCE_FILENAME = "source_filename.txt"
    RESULT_FILENAME = "result.json"

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
        *,
        source_filename: str = "document.pdf",
    ) -> Path:
        """Атомарно сохранить PDF и temporary filename metadata."""
        if not pdf_bytes:
            raise ValueError(
                "Input PDF cannot be empty"
            )

        job_dir = self._job_dir(
            job_id
        )

        pdf_target = (
            job_dir
            / self.INPUT_FILENAME
        )

        filename_target = (
            job_dir
            / self.SOURCE_FILENAME
        )

        try:
            result = self._atomic_write(
                target=pdf_target,
                data=pdf_bytes,
            )

            self._atomic_write(
                target=filename_target,
                data=source_filename.encode(
                    "utf-8"
                ),
            )

            return result

        except Exception:
            self.delete_job_files(
                job_id
            )
            raise

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

    def source_filename(
        self,
        job_id: UUID,
    ) -> str:
        """Получить исходное имя либо безопасный fallback."""
        path = (
            self._job_dir(
                job_id
            )
            / self.SOURCE_FILENAME
        )

        if not path.is_file():
            return "document.pdf"

        value = (
            path.read_text(
                encoding="utf-8"
            )
            .strip()
        )

        return (
            value
            or "document.pdf"
        )

    def delete_input(
        self,
        job_id: UUID,
    ) -> None:
        """Idempotently удалить исходный PDF и filename metadata."""
        directory = self._job_dir(
            job_id
        )

        (
            directory
            / self.INPUT_FILENAME
        ).unlink(
            missing_ok=True
        )

        (
            directory
            / self.SOURCE_FILENAME
        ).unlink(
            missing_ok=True
        )

        self._remove_empty_job_dir(
            job_id
        )

    def save_result(
        self,
        job_id: UUID,
        result_bytes: bytes,
    ) -> Path:
        """Атомарно сохранить временный JSON-result."""
        if not result_bytes:
            raise ValueError(
                "Result JSON cannot be empty"
            )

        target = (
            self._job_dir(
                job_id
            )
            / self.RESULT_FILENAME
        )

        return self._atomic_write(
            target=target,
            data=result_bytes,
        )

    def consume_result(
        self,
        job_id: UUID,
    ) -> bytes:
        """Прочитать result.json и удалить серверную копию."""
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

        # Удаляем только после успешного read_bytes().
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

    def cleanup_orphaned_files(
        self,
        *,
        known_job_ids: frozenset[UUID],
        cutoff: datetime,
    ) -> int:
        """Удалить stale filesystem artifacts вне lifecycle."""
        if cutoff.tzinfo is None:
            raise ValueError(
                "cutoff must be timezone-aware"
            )

        deleted = 0

        for entry in tuple(
            self._root_dir.iterdir()
        ):
            if entry.is_symlink():
                if self._is_older_than(
                    entry,
                    cutoff,
                ):
                    entry.unlink(
                        missing_ok=True
                    )
                    deleted += 1

                continue

            if entry.is_file():
                if self._is_older_than(
                    entry,
                    cutoff,
                ):
                    entry.unlink(
                        missing_ok=True
                    )
                    deleted += 1

                continue

            if not entry.is_dir():
                continue

            job_id = self._parse_job_id(
                entry.name
            )

            registered = (
                job_id is not None
                and job_id in known_job_ids
            )

            if (
                not registered
                and self._directory_is_older_than(
                    entry,
                    cutoff,
                )
            ):
                shutil.rmtree(
                    entry,
                    ignore_errors=True,
                )

                deleted += 1
                continue

            for temporary in tuple(
                entry.rglob(
                    "*.tmp"
                )
            ):
                if (
                    temporary.is_file()
                    and self._is_older_than(
                        temporary,
                        cutoff,
                    )
                ):
                    temporary.unlink(
                        missing_ok=True
                    )

                    deleted += 1

            if not registered:
                try:
                    entry.rmdir()
                except OSError:
                    pass

        return deleted

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
        """Вернуть True, если JSON ожидает выдачи."""
        return (
            self._job_dir(
                job_id
            )
            / self.RESULT_FILENAME
        ).is_file()

    def _atomic_write(
        self,
        *,
        target: Path,
        data: bytes,
    ) -> Path:
        """Записать artifact через temporary path."""
        target.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        temporary = (
            target.parent
            / f"{target.name}.tmp"
        )

        try:
            temporary.write_bytes(
                data
            )

            temporary.replace(
                target
            )
        finally:
            temporary.unlink(
                missing_ok=True
            )

        return target

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
        """Удалить directory, если artifacts больше нет."""
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

    @staticmethod
    def _parse_job_id(
        value: str,
    ) -> UUID | None:
        """Преобразовать имя каталога в UUID."""
        try:
            return UUID(
                value
            )
        except ValueError:
            return None

    @classmethod
    def _directory_is_older_than(
        cls,
        directory: Path,
        cutoff: datetime,
    ) -> bool:
        """Проверить возраст каталога по самому свежему artifact."""
        latest_timestamp = (
            directory.stat()
            .st_mtime
        )

        for child in directory.rglob(
            "*"
        ):
            try:
                timestamp = (
                    child.stat()
                    .st_mtime
                )
            except FileNotFoundError:
                continue

            latest_timestamp = max(
                latest_timestamp,
                timestamp,
            )

        latest = datetime.fromtimestamp(
            latest_timestamp,
            UTC,
        )

        return latest < cutoff

    @staticmethod
    def _is_older_than(
        path: Path,
        cutoff: datetime,
    ) -> bool:
        """Проверить filesystem mtime относительно UTC cutoff."""
        try:
            modified = datetime.fromtimestamp(
                path.stat().st_mtime,
                UTC,
            )
        except FileNotFoundError:
            return False

        return modified < cutoff
