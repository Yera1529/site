"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/legalassist"
    secret_key: str = "change-me-to-a-random-secret-key"
    access_token_expire_minutes: int = 1440

    ai_api_url: str = "http://host.docker.internal:11434/v1/chat/completions"
    ai_api_key: str = ""
    ai_model: str = "qwen3:30b-a3b"
    ai_thinking_mode: str = "enabled"
    embedding_model: str = "intfloat/multilingual-e5-base"

    storage_dir: str = "./storage"
    max_upload_bytes: int = 50 * 1024 * 1024  # 50 MB
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    class Config:
        env_file = ".env"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
