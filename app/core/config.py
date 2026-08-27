# app/core/config.py

from functools import lru_cache
from pathlib import Path
from urllib.parse import quote

from pydantic import (
    Field,
    SecretStr,
    model_validator,
)
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

    max_upload_bytes: int = Field(
        default=104857600,
        ge=1,
        le=1073741824,
    )

    ollama_base_url: str = "http://ollama:11434"

    ollama_vlm_model: str = "qwen3-vl:8b-instruct"

    ollama_embedding_model: str = "qwen3-embedding:4b"

    ollama_llm_model: str = "qwen3-vl:8b-instruct"

    ollama_keep_alive: str = "1m"

    # Общий timeout остаётся для embedding/readiness adapters.
    ollama_request_timeout_seconds: float = Field(
        default=300.0,
        gt=0,
    )

    # Grounded text extraction.
    ollama_answer_timeout_seconds: float = Field(
        default=120.0,
        gt=0,
        le=600,
    )

    ollama_answer_num_ctx: int = Field(
        default=32768,
        ge=4096,
        le=131072,
    )

    ollama_answer_num_predict: int = Field(
        default=2048,
        ge=64,
        le=8192,
    )

    # Targeted visual fallback.
    ollama_vlm_timeout_seconds: float = Field(
        default=180.0,
        gt=0,
        le=600,
    )

    ollama_vlm_num_ctx: int = Field(
        default=32768,
        ge=4096,
        le=131072,
    )

    ollama_vlm_num_predict: int = Field(
        default=3072,
        ge=64,
        le=8192,
    )

    # Верхняя граница wall-clock времени одного background job.
    analysis_job_timeout_seconds: float = Field(
        default=900.0,
        ge=60,
        le=7200,
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

    retrieval_chunk_max_chars: int = Field(
        default=1800,
        ge=300,
        le=10000,
    )

    retrieval_chunk_overlap_chars: int = Field(
        default=300,
        ge=0,
        le=5000,
    )

    retrieval_top_k: int = Field(
        default=4,
        ge=1,
        le=30,
    )

    retrieval_embedding_batch_size: int = Field(
        default=16,
        ge=1,
        le=128,
    )

    retrieval_semantic_weight: float = Field(
        default=0.65,
        ge=0,
        le=1,
    )

    retrieval_lexical_weight: float = Field(
        default=0.35,
        ge=0,
        le=1,
    )

    answer_batch_size: int = Field(
        default=6,
        ge=1,
        le=20,
    )

    answer_found_min_confidence: float = Field(
        default=0.60,
        ge=0,
        le=1,
    )

    answer_vlm_fallback_max_pages: int = Field(
        default=4,
        ge=1,
        le=50,
    )

    answer_vlm_weak_page_max_chars: int = Field(
        default=80,
        ge=0,
        le=2000,
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

    rabbitmq_vhost: str = "tz_checklist_ai"

    rabbitmq_user: str = "tz_checklist_ai"

    rabbitmq_password: SecretStr = SecretStr(
        "change_me_before_use"
    )

    celery_queue_name: str = "tz-checklist-ai"

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

    @model_validator(mode="after")
    def validate_retrieval_settings(self) -> "Settings":
        """Проверить взаимосвязанные настройки приложения."""
        if (
            self.retrieval_chunk_overlap_chars
            >= self.retrieval_chunk_max_chars
        ):
            raise ValueError(
                "RETRIEVAL_CHUNK_OVERLAP_CHARS "
                "must be smaller than "
                "RETRIEVAL_CHUNK_MAX_CHARS"
            )

        if (
            self.retrieval_semantic_weight
            + self.retrieval_lexical_weight
            <= 0
        ):
            raise ValueError(
                "At least one retrieval weight must be positive"
            )

        if (
            self.ollama_answer_num_predict
            >= self.ollama_answer_num_ctx
        ):
            raise ValueError(
                "OLLAMA_ANSWER_NUM_PREDICT "
                "must be smaller than "
                "OLLAMA_ANSWER_NUM_CTX"
            )

        if (
            self.ollama_vlm_num_predict
            >= self.ollama_vlm_num_ctx
        ):
            raise ValueError(
                "OLLAMA_VLM_NUM_PREDICT "
                "must be smaller than "
                "OLLAMA_VLM_NUM_CTX"
            )

        max_ai_request_timeout = max(
            self.ollama_answer_timeout_seconds,
            self.ollama_vlm_timeout_seconds,
        )

        if (
            self.analysis_job_timeout_seconds
            <= max_ai_request_timeout
        ):
            raise ValueError(
                "ANALYSIS_JOB_TIMEOUT_SECONDS "
                "must be greater than individual "
                "Ollama request timeouts"
            )

        return self

    @property
    def rabbitmq_url(self) -> str:
        """Безопасно собрать AMQP URL."""
        user = quote(
            self.rabbitmq_user,
            safe="",
        )

        password = quote(
            self.rabbitmq_password.get_secret_value(),
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
    def jobs_dir(self) -> Path:
        """Директория временных binary-файлов."""
        return self.data_dir / "jobs"

    @property
    def job_database_path(self) -> Path:
        """SQLite с техническими metadata."""
        return (
            self.data_dir
            / "metadata"
            / "jobs.sqlite3"
        )


@lru_cache
def get_settings() -> Settings:
    """Вернуть единый кэшированный экземпляр."""
    return Settings()
