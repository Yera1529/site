"""Application configuration loaded from environment variables."""

from pydantic_settings import BaseSettings
from functools import lru_cache


class Settings(BaseSettings):
    database_url: str = "postgresql+asyncpg://postgres:postgres@db:5432/legalassist"
    secret_key: str = "change-me-to-a-random-secret-key"
    access_token_expire_minutes: int = 1440

    ai_api_key: str = ""
    ai_model: str = "gemini-2.5-flash"
    embedding_model: str = "intfloat/multilingual-e5-base"

    # AI-powered semantic reranking of retrieved legal norms.
    # When enabled, Gemini reorders FAISS candidates by true relevance to the
    # case, filtering out lexical false-positives. Backfill guarantees results
    # are never empty even if the model over-filters.
    enable_ai_rerank: bool = True
    ai_rerank_candidates: int = 40   # how many FAISS candidates to send to the reranker
    ai_rerank_min_keep: int = 6      # floor: always keep at least this many results

    # L1 Domain Router (Фаза 3): классифицирует дело в домен и ограничивает
    # подбор норм пулом источников этого домена — убирает кросс-доменные «магниты»
    # (напр. Трудовой кодекс на делах охраны). На ошибке — fallback к полному поиску.
    enable_domain_router: bool = True

    # Vertex AI settings (used when ai_api_key is empty)
    vertex_ai_project: str = ""
    vertex_ai_location: str = "us-central1"
    google_application_credentials: str = ""

    storage_dir: str = "./storage"
    max_upload_bytes: int = 50 * 1024 * 1024  # 50 MB
    cors_origins: str = "http://localhost:3000,http://127.0.0.1:3000"

    class Config:
        env_file = ".env"
        extra = "ignore"


@lru_cache()
def get_settings() -> Settings:
    return Settings()
