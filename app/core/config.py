# app/core/config.py

from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Единая конфигурация приложения.

    Все параметры runtime и инфраструктуры приходят из environment
    variables и валидируются Pydantic при старте приложения.

    Ограничения GPU намеренно запрещают увеличить конкуренцию
    на текущей RTX 3090 выше одного параллельного задания.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    app_name: str = "TZ Checklist AI"
    app_version: str = "0.1.0"
    app_env: str = "dev"
    docs_enabled: bool = True

    api_host: str = "0.0.0.0"
    api_port: int = 8000

    ollama_base_url: str = "http://ollama:11434"

    # На этапе 2 требуется только одна multimodal-модель.
    ollama_vlm_model: str = "qwen3-vl:8b-instruct"

    ollama_keep_alive: str = "1m"

    ollama_request_timeout_seconds: float = Field(
        default=300.0,
        gt=0,
    )

    gpu_task_concurrency: int = Field(
        default=1,
        ge=1,
        le=1,
    )

    vlm_pages_in_flight: int = Field(
        default=1,
        ge=1,
        le=1,
    )

    classification_max_pages: int = Field(
        default=2,
        ge=1,
        le=10,
    )

    classification_min_native_chars: int = Field(
        default=120,
        ge=0,
    )

    classification_min_confidence: float = Field(
        default=0.70,
        ge=0,
        le=1,
    )

    classification_min_page_chars: int = Field(
        default=40,
        ge=0,
    )

    vlm_fallback_max_pages: int = Field(
        default=2,
        ge=1,
        le=10,
    )

    pdf_render_dpi: int = Field(
        default=144,
        ge=72,
        le=200,
    )

    pdf_jpeg_quality: int = Field(
        default=85,
        ge=50,
        le=95,
    )

    checklist_resources_dir: Path = Path(
        "/app/resources/checklists"
    )

    test_data_dir: Path = Path(
        "/test-data"
    )

    rabbitmq_url: str | None = None

    data_dir: Path = Path(
        "/data"
    )


@lru_cache
def get_settings() -> Settings:
    """Вернуть единый кэшированный экземпляр настроек."""
    return Settings()
