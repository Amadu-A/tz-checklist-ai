# app/infrastructure/persistence/sqlite_job_repository.py

import sqlite3
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID

from app.domain.enums import ChecklistCode, JobStatus
from app.domain.jobs import JobState


class SqliteJobRepository:
    """SQLite repository для маленьких технических metadata.

    Здесь намеренно не сохраняются пользовательские документы,
    извлечённый текст, embeddings, ответы или PDF-отчёты.

    SQLite выбран потому, что API и один project-specific worker
    работают на одном сервере и используют общий project volume.

    При необходимости repository можно заменить PostgreSQL-адаптером,
    не меняя application layer.
    """

    def __init__(
        self,
        database_path: Path,
    ) -> None:
        self._database_path = database_path

        self._database_path.parent.mkdir(
            parents=True,
            exist_ok=True,
        )

        self._initialize()

    def create(
        self,
        job_id: UUID,
        *,
        status: JobStatus,
        checklist_code: ChecklistCode | None = None,
    ) -> JobState:
        """Создать metadata job."""
        now = datetime.now(
            UTC
        )

        with self._connect() as connection:
            connection.execute(
                """
                INSERT INTO jobs (
                    job_id,
                    status,
                    checklist_code,
                    created_at,
                    updated_at,
                    error
                )
                VALUES (?, ?, ?, ?, ?, NULL)
                """,
                (
                    str(job_id),
                    status.value,
                    (
                        checklist_code.value
                        if checklist_code is not None
                        else None
                    ),
                    now.isoformat(),
                    now.isoformat(),
                ),
            )

        return JobState(
            job_id=job_id,
            status=status,
            checklist_code=checklist_code,
            created_at=now,
            updated_at=now,
        )

    def get(
        self,
        job_id: UUID,
    ) -> JobState | None:
        """Получить job либо None."""
        with self._connect() as connection:
            row = connection.execute(
                """
                SELECT
                    job_id,
                    status,
                    checklist_code,
                    created_at,
                    updated_at,
                    error
                FROM jobs
                WHERE job_id = ?
                """,
                (
                    str(job_id),
                ),
            ).fetchone()

        if row is None:
            return None

        return self._to_state(
            row
        )

    def update(
        self,
        job_id: UUID,
        *,
        status: JobStatus,
        checklist_code: ChecklistCode | None = None,
        error: str | None = None,
    ) -> JobState:
        """Обновить metadata существующего job."""
        current = self.get(
            job_id
        )

        if current is None:
            raise KeyError(
                f"Unknown job_id: {job_id}"
            )

        now = datetime.now(
            UTC
        )

        effective_checklist = (
            checklist_code
            if checklist_code is not None
            else current.checklist_code
        )

        with self._connect() as connection:
            connection.execute(
                """
                UPDATE jobs
                SET
                    status = ?,
                    checklist_code = ?,
                    updated_at = ?,
                    error = ?
                WHERE job_id = ?
                """,
                (
                    status.value,
                    (
                        effective_checklist.value
                        if effective_checklist is not None
                        else None
                    ),
                    now.isoformat(),
                    error,
                    str(job_id),
                ),
            )

        return JobState(
            job_id=job_id,
            status=status,
            checklist_code=effective_checklist,
            created_at=current.created_at,
            updated_at=now,
            error=error,
        )

    def delete(
        self,
        job_id: UUID,
    ) -> None:
        """Удалить metadata."""
        with self._connect() as connection:
            connection.execute(
                """
                DELETE FROM jobs
                WHERE job_id = ?
                """,
                (
                    str(job_id),
                ),
            )

    def list_job_ids(
        self,
    ) -> frozenset[UUID]:
        """Вернуть ID всех существующих metadata jobs."""
        with self._connect() as connection:
            rows = connection.execute(
                """
                SELECT job_id
                FROM jobs
                """
            ).fetchall()

        return frozenset(
            UUID(
                row["job_id"]
            )
            for row in rows
        )

    def find_older_than(
        self,
        *,
        statuses: tuple[JobStatus, ...],
        cutoff: datetime,
    ) -> tuple[JobState, ...]:
        """Вернуть jobs нужных статусов старше cutoff."""
        if not statuses:
            return ()

        placeholders = ", ".join(
            "?"
            for _ in statuses
        )

        parameters = [
            status.value
            for status in statuses
        ]

        parameters.append(
            cutoff.isoformat()
        )

        query = f"""
            SELECT
                job_id,
                status,
                checklist_code,
                created_at,
                updated_at,
                error
            FROM jobs
            WHERE status IN ({placeholders})
              AND updated_at < ?
            ORDER BY updated_at ASC
        """

        with self._connect() as connection:
            rows = connection.execute(
                query,
                parameters,
            ).fetchall()

        return tuple(
            self._to_state(
                row
            )
            for row in rows
        )

    def _initialize(
        self,
    ) -> None:
        """Создать таблицу и индексы idempotently."""
        with self._connect() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    job_id TEXT PRIMARY KEY,
                    status TEXT NOT NULL,
                    checklist_code TEXT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    error TEXT NULL
                )
                """
            )

            connection.execute(
                """
                CREATE INDEX IF NOT EXISTS
                    idx_jobs_status_updated_at
                ON jobs (
                    status,
                    updated_at
                )
                """
            )

    def _connect(
        self,
    ) -> sqlite3.Connection:
        """Открыть короткоживущее соединение с безопасными настройками."""
        connection = sqlite3.connect(
            self._database_path,
            timeout=30,
        )

        connection.row_factory = sqlite3.Row

        connection.execute(
            "PRAGMA journal_mode=WAL"
        )

        connection.execute(
            "PRAGMA foreign_keys=ON"
        )

        return connection

    @staticmethod
    def _to_state(
        row: sqlite3.Row,
    ) -> JobState:
        """Преобразовать SQLite row в Pydantic domain model."""
        checklist_value = row[
            "checklist_code"
        ]

        return JobState(
            job_id=UUID(
                row["job_id"]
            ),
            status=JobStatus(
                row["status"]
            ),
            checklist_code=(
                ChecklistCode(
                    checklist_value
                )
                if checklist_value
                else None
            ),
            created_at=datetime.fromisoformat(
                row["created_at"]
            ),
            updated_at=datetime.fromisoformat(
                row["updated_at"]
            ),
            error=row[
                "error"
            ],
        )
