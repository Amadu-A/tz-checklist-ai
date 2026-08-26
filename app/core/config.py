# app/core/config.py

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Единая Pydantic-конфигурация приложения."""

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

    ollama_vlm_model: str = (
        "qwen3-vl:8b-instruct"
    )

    ollama_embedding_model: str = (
        "qwen3-embedding:4b"
    )

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

    rabbitmq_host: str = "rabbitmq"

    rabbitmq_port: int = Field(
        default=5672,
        ge=1,
        le=65535,
    )

    rabbitmq_vhost: str = (
        "tz_checklist_ai"
    )

    rabbitmq_user: str = (
        "tz_checklist_ai"
    )

    rabbitmq_password: SecretStr = SecretStr(
        "change_me_before_use"
    )

    celery_queue_name: str = (
        "tz-checklist-ai"
    )

    result_file_ttl_minutes: int = Field(
        default=60,
        ge=1,
    )

    orphan_job_ttl_hours: int = Field(
        default=6,
        ge=1,
    )

    failed_job_state_ttl_hours: int = Field(
        default=24,
        ge=1,
    )

    cleanup_interval_seconds: int = Field(
        default=600,
        ge=60,
    )

    checklist_resources_dir: Path = Path(
        "/app/resources/checklists"
    )

    test_data_dir: Path = Path(
        "/test-data"
    )

    data_dir: Path = Path(
        "/data"
    )

    @property
    def rabbitmq_url(
        self,
    ) -> str:
        """Безопасно собрать AMQP URL из отдельных settings."""
        user = quote(
            self.rabbitmq_user,
            safe="",
        )

        password = quote(
            self.rabbitmq_password
            .get_secret_value(),
            safe="",
        )

        vhost = quote(
            self.rabbitmq_vhost,
            safe="",
        )

        return (
            f"amqp://{user}:{password}"
            f"@{self.rabbitmq_host}:"
            f"{self.rabbitmq_port}/{vhost}"
        )

    @property
    def jobs_dir(
        self,
    ) -> Path:
        """Директория только временных binary-файлов."""
        return (
            self.data_dir
            / "jobs"
        )

    @property
    def job_database_path(
        self,
    ) -> Path:
        """SQLite содержит только маленькие metadata."""
        return (
            self.data_dir
            / "metadata"
            / "jobs.sqlite3"
        )


@lru_cache
def get_settings() -> Settings:
    """Вернуть единый кэшированный экземпляр настроек."""
    return Settings()
