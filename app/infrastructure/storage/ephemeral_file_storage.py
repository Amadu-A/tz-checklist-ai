# app/infrastructure/storage/ephemeral_file_storage.py

import shutil
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID


class EphemeralFileStorage:
    """Временное файловое хранилище одного job.

    Layout:

        /data/jobs/<uuid>/input.pdf
        /data/jobs/<uuid>/result.pdf

    Никакие intermediate text/chunks/embeddings сюда не записываются.

    Нормальный lifecycle удаляет файлы максимально рано.

    cleanup_orphaned_files() является defense-in-depth и удаляет
    старые filesystem artifacts, которые могли остаться после
    аварийного завершения процесса вне нормального lifecycle.
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

        target = (
            self._job_dir(
                job_id
            )
            / self.INPUT_FILENAME
        )

        return self._atomic_write(
            target=target,
            data=pdf_bytes,
        )

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

        target = (
            self._job_dir(
                job_id
            )
            / self.RESULT_FILENAME
        )

        return self._atomic_write(
            target=target,
            data=pdf_bytes,
        )

    def consume_result(
        self,
        job_id: UUID,
    ) -> bytes:
        """Прочитать result.pdf и немедленно удалить серверную копию."""
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

        # До этой строки мы доходим только после успешного чтения.
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
        """Удалить stale filesystem artifacts вне нормального lifecycle.

        Правила:

        - зарегистрированные job directories не удаляются целиком;
        - старые *.tmp внутри них удаляются;
        - незарегистрированный каталог удаляется только после cutoff;
        - старые stray files/symlinks в root также удаляются.

        Возвращается количество удалённых artifacts.
        """
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

            # Даже у зарегистрированного job мог остаться .tmp после
            # аварийного завершения предыдущей операции записи.
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
        """Вернуть True, если результат ожидает выдачи."""
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
        """Записать файл через temporary path без оставления .tmp."""
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
            # После успешного replace() temporary уже не существует.
            # После исключения эта строка удалит partial/stale temp.
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

    @staticmethod
    def _parse_job_id(
        value: str,
    ) -> UUID | None:
        """Преобразовать имя каталога в UUID либо вернуть None."""
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
