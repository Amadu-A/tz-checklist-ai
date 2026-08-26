# tests/unit/infrastructure/test_ephemeral_file_storage.py

import os
from datetime import UTC, datetime, timedelta
from pathlib import Path
from uuid import uuid4

import pytest

from app.infrastructure.storage.ephemeral_file_storage import (
    EphemeralFileStorage,
)


def test_input_is_deleted_explicitly(
    tmp_path: Path,
) -> None:
    """После обработки исходного PDF серверная копия должна исчезнуть."""
    storage = EphemeralFileStorage(
        tmp_path
    )

    job_id = uuid4()

    storage.save_input(
        job_id,
        b"%PDF-input",
    )

    assert (
        storage.has_input(
            job_id
        )
        is True
    )

    storage.delete_input(
        job_id
    )

    assert (
        storage.has_input(
            job_id
        )
        is False
    )


def test_consume_result_returns_bytes_and_deletes_pdf(
    tmp_path: Path,
) -> None:
    """Результат является одноразовым и удаляется после чтения."""
    storage = EphemeralFileStorage(
        tmp_path
    )

    job_id = uuid4()

    expected = (
        b"%PDF-result"
    )

    storage.save_result(
        job_id,
        expected,
    )

    actual = storage.consume_result(
        job_id
    )

    assert (
        actual
        == expected
    )

    assert (
        storage.has_result(
            job_id
        )
        is False
    )

    with pytest.raises(
        FileNotFoundError
    ):
        storage.consume_result(
            job_id
        )


def test_delete_job_files_removes_input_and_result(
    tmp_path: Path,
) -> None:
    """Аварийная очистка должна убрать все binary-файлы."""
    storage = EphemeralFileStorage(
        tmp_path
    )

    job_id = uuid4()

    storage.save_input(
        job_id,
        b"input",
    )

    storage.save_result(
        job_id,
        b"result",
    )

    storage.delete_job_files(
        job_id
    )

    assert not storage.has_input(
        job_id
    )

    assert not storage.has_result(
        job_id
    )


def test_atomic_write_removes_tmp_after_replace_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Ошибка atomic rename не должна оставлять пользовательский .tmp."""
    storage = EphemeralFileStorage(
        tmp_path
    )

    job_id = uuid4()

    original_replace = Path.replace

    def failing_replace(
        path: Path,
        target: Path,
    ):
        if path.name.endswith(
            ".tmp"
        ):
            raise OSError(
                "simulated replace failure"
            )

        return original_replace(
            path,
            target,
        )

    monkeypatch.setattr(
        Path,
        "replace",
        failing_replace,
    )

    with pytest.raises(
        OSError,
        match="simulated replace failure",
    ):
        storage.save_input(
            job_id,
            b"%PDF-input",
        )

    job_dir = (
        tmp_path
        / str(job_id)
    )

    assert not (
        job_dir
        / "input.pdf.tmp"
    ).exists()

    assert not (
        job_dir
        / "input.pdf"
    ).exists()


def test_stale_tmp_is_removed_without_deleting_registered_job(
    tmp_path: Path,
) -> None:
    """Sweep должен удалить stale .tmp, сохранив живой input.pdf."""
    storage = EphemeralFileStorage(
        tmp_path
    )

    job_id = uuid4()

    storage.save_input(
        job_id,
        b"%PDF-live"
    )

    job_dir = (
        tmp_path
        / str(job_id)
    )

    temporary = (
        job_dir
        / "result.pdf.tmp"
    )

    temporary.write_bytes(
        b"partial"
    )

    old_timestamp = (
        datetime.now(
            UTC
        )
        - timedelta(
            hours=8
        )
    ).timestamp()

    os.utime(
        temporary,
        (
            old_timestamp,
            old_timestamp,
        ),
    )

    deleted = (
        storage.cleanup_orphaned_files(
            known_job_ids=frozenset(
                {
                    job_id,
                }
            ),
            cutoff=(
                datetime.now(
                    UTC
                )
                - timedelta(
                    hours=6
                )
            ),
        )
    )

    assert (
        deleted
        == 1
    )

    assert (
        temporary.exists()
        is False
    )

    assert (
        storage.has_input(
            job_id
        )
        is True
    )
