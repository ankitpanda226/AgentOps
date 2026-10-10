"""Application configuration loaded from environment variables."""

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime settings for AgentOps Copilot."""

    app_name: str = "AgentOps Copilot"
    app_version: str = "0.1.0"
    app_env: str = "local"
    log_level: str = "INFO"

    embedding_provider: str = "sentence-transformers"
    openai_api_key: str | None = None
    openai_base_url: str | None = None
    openai_embedding_model: str = "text-embedding-3-small"
    sentence_transformer_model: str = "all-MiniLM-L6-v2"

    chroma_persist_dir: str = ".data/chroma"
    sqlite_memory_path: str = ".data/memory.sqlite3"

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )


@lru_cache
def get_settings() -> Settings:
    """Return cached application settings."""
    return Settings()
