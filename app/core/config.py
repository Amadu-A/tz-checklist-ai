# app/core/config.py

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Настройки приложения, инфраструктуры и работы с GPU."""

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

    ollama_llm_model: str = "qwen3.8:27b"
    ollama_vlm_model: str = "qwen3-vl:8b-instruct"
    ollama_embedding_model: str = "qwen3-embedding:4b"

    ollama_keep_alive: str = "1m"
    ollama_request_timeout_seconds: float = 300.0

    # Для текущей RTX 3090 сознательно запрещаем поднять
    # GPU-конкурентность выше единицы только через .env.
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

    rabbitmq_url: str | None = None

    data_dir: str = "/data"


@lru_cache
def get_settings() -> Settings:
    """Вернуть единый кэшированный экземпляр настроек."""
    return Settings()
