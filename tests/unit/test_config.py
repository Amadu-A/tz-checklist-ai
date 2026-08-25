# tests/unit/test_config.py

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_ollama_model_is_unloaded_after_one_minute_by_default() -> None:
    settings = Settings(
        _env_file=None,
    )

    assert settings.ollama_keep_alive == "1m"


def test_gpu_tasks_are_serialized() -> None:
    settings = Settings(
        _env_file=None,
    )

    assert settings.gpu_task_concurrency == 1
    assert settings.vlm_pages_in_flight == 1


def test_gpu_concurrency_cannot_be_raised_accidentally() -> None:
    with pytest.raises(ValidationError):
        Settings(
            _env_file=None,
            gpu_task_concurrency=2,
        )
        