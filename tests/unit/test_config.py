# tests/unit/test_config.py

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_ollama_model_is_unloaded_after_one_minute_by_default() -> None:
    """AI-запросы проекта должны использовать keep_alive=1m."""
    settings = Settings(
        _env_file=None,
    )

    assert (
        settings.ollama_keep_alive
        == "1m"
    )


def test_gpu_tasks_are_serialized() -> None:
    """RTX 3090 не должна получать несколько наших GPU jobs одновременно."""
    settings = Settings(
        _env_file=None,
    )

    assert (
        settings.gpu_task_concurrency
        == 1
    )

    assert (
        settings.vlm_pages_in_flight
        == 1
    )


def test_gpu_concurrency_cannot_be_raised_accidentally() -> None:
    """Pydantic запрещает опасную конфигурацию concurrency > 1."""
    with pytest.raises(
        ValidationError
    ):
        Settings(
            _env_file=None,
            gpu_task_concurrency=2,
        )


def test_rabbitmq_url_is_built_from_validated_settings() -> None:
    """Пароль и vhost должны корректно URL-encode."""
    settings = Settings(
        _env_file=None,
        rabbitmq_host="rabbitmq",
        rabbitmq_vhost=(
            "tz_checklist_ai"
        ),
        rabbitmq_user=(
            "tz_checklist_ai"
        ),
        rabbitmq_password=(
            "pass@word"
        ),
    )

    assert (
        settings.rabbitmq_url
        == (
            "amqp://"
            "tz_checklist_ai:"
            "pass%40word"
            "@rabbitmq:5672/"
            "tz_checklist_ai"
        )
    )
    