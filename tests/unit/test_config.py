# tests/unit/test_config.py

import pytest
from pydantic import ValidationError

from app.core.config import Settings


def test_ollama_model_is_unloaded_after_one_minute_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """AI-запросы проекта должны использовать keep_alive=1m."""
    monkeypatch.delenv(
        "OLLAMA_KEEP_ALIVE",
        raising=False,
    )

    settings = Settings(
        _env_file=None,
    )

    assert (
        settings.ollama_keep_alive
        == "1m"
    )


def test_default_ai_pipeline_uses_single_vlm_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Text extraction и visual fallback используют одну 8B VLM."""
    for variable in (
        "OLLAMA_LLM_MODEL",
        "OLLAMA_VLM_MODEL",
        "OLLAMA_REQUEST_TIMEOUT_SECONDS",
        "ANSWER_FOUND_MIN_CONFIDENCE",
        "ANSWER_VLM_FALLBACK_MAX_PAGES",
    ):
        monkeypatch.delenv(
            variable,
            raising=False,
        )

    settings = Settings(
        _env_file=None,
    )

    assert (
        settings.ollama_llm_model
        == "qwen3-vl:8b-instruct"
    )

    assert (
        settings.ollama_vlm_model
        == "qwen3-vl:8b-instruct"
    )

    assert (
        settings.ollama_request_timeout_seconds
        == 300.0
    )

    assert (
        settings.answer_found_min_confidence
        == 0.60
    )

    assert (
        settings.answer_vlm_fallback_max_pages
        == 4
    )


def test_gpu_tasks_are_serialized(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """RTX 3090 не должна получать несколько наших GPU jobs одновременно."""
    monkeypatch.delenv(
        "GPU_TASK_CONCURRENCY",
        raising=False,
    )

    monkeypatch.delenv(
        "VLM_PAGES_IN_FLIGHT",
        raising=False,
    )

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
        rabbitmq_vhost="tz_checklist_ai",
        rabbitmq_user="tz_checklist_ai",
        rabbitmq_password="pass@word",
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


def test_upload_limit_is_100_mib_by_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """API должен иметь явный ограничитель размера PDF."""
    monkeypatch.delenv(
        "MAX_UPLOAD_BYTES",
        raising=False,
    )

    settings = Settings(
        _env_file=None,
    )

    assert (
        settings.max_upload_bytes
        == 100 * 1024 * 1024
    )
