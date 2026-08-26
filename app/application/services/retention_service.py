# app/application/services/retention_service.py

from datetime import UTC, datetime, timedelta

from app.application.ports.job_repository import (
    JobRepositoryPort,
)
from app.application.ports.job_storage import (
    JobStoragePort,
)
from app.domain.enums import JobStatus


class RetentionService:
    """Страховочная очистка временных файлов и job metadata.

    Нормальный lifecycle удаляет пользовательские файлы раньше TTL.

    Cleanup работает в два слоя:

    1. удаляет просроченные jobs, известные repository;
    2. выполняет filesystem sweep для artifacts без metadata.

    Благодаря второму слою авария между filesystem и SQLite
    не может оставить пользовательский PDF навсегда.
    """

    def __init__(
        self,
        *,
        repository: JobRepositoryPort,
        storage: JobStoragePort,
        result_ttl_minutes: int,
        orphan_ttl_hours: int,
        failed_state_ttl_hours: int,
    ) -> None:
        self._repository = repository
        self._storage = storage

        self._result_ttl = timedelta(
            minutes=result_ttl_minutes
        )

        self._orphan_ttl = timedelta(
            hours=orphan_ttl_hours
        )

        self._failed_state_ttl = timedelta(
            hours=failed_state_ttl_hours
        )

    def cleanup(
        self,
        *,
        now: datetime | None = None,
    ) -> int:
        """Удалить просроченные jobs/artifacts и вернуть их количество."""
        effective_now = (
            now
            if now is not None
            else datetime.now(
                UTC
            )
        )

        expired_completed = (
            self._repository
            .find_older_than(
                statuses=(
                    JobStatus.COMPLETED,
                ),
                cutoff=(
                    effective_now
                    - self._result_ttl
                ),
            )
        )

        expired_orphans = (
            self._repository
            .find_older_than(
                statuses=(
                    JobStatus.AWAITING_CONFIRMATION,
                    JobStatus.QUEUED,
                    JobStatus.PROCESSING,
                ),
                cutoff=(
                    effective_now
                    - self._orphan_ttl
                ),
            )
        )

        expired_failed = (
            self._repository
            .find_older_than(
                statuses=(
                    JobStatus.FAILED,
                ),
                cutoff=(
                    effective_now
                    - self._failed_state_ttl
                ),
            )
        )

        expired = {
            item.job_id: item
            for item in (
                *expired_completed,
                *expired_orphans,
                *expired_failed,
            )
        }

        for job_id in expired:
            self._storage.delete_job_files(
                job_id
            )

            self._repository.delete(
                job_id
            )

        # После удаления expired metadata получаем только действительно
        # живые IDs. Любая старая filesystem directory вне этого набора
        # является orphan artifact.
        known_job_ids = (
            self._repository
            .list_job_ids()
        )

        filesystem_deleted = (
            self._storage
            .cleanup_orphaned_files(
                known_job_ids=known_job_ids,
                cutoff=(
                    effective_now
                    - self._orphan_ttl
                ),
            )
        )

        return (
            len(expired)
            + filesystem_deleted
        )
