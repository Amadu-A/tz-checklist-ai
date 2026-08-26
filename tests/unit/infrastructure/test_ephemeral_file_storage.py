# tests/unit/infrastructure/test_ephemeral_file_storage.py

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
    storage = (
        EphemeralFileStorage(
            tmp_path
        )
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
    storage = (
        EphemeralFileStorage(
            tmp_path
        )
    )

    job_id = uuid4()

    expected = (
        b"%PDF-result"
    )

    storage.save_result(
        job_id,
        expected,
    )

    actual = (
        storage.consume_result(
            job_id
        )
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
    storage = (
        EphemeralFileStorage(
            tmp_path
        )
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
    