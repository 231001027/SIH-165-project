"""
Central application configuration.

Source-discipline note (see project blueprint "How to Read This Document"):
Values here such as risk score weights, confidence thresholds and abstention
bands are OUR PROTOTYPE DESIGN DECISIONS, not official OIL/IOGP formulas.
They are intentionally kept here (and in risk_weights.json) so they are
configurable rather than buried in code.
"""
from functools import lru_cache
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    APP_NAME: str = "SIFGuard-OIL"
    ENV: str = "development"

    # Default to a local SQLite file so the project runs with zero external
    # infrastructure on a fresh machine. Set DATABASE_URL to a Postgres DSN
    # (e.g. postgresql+psycopg2://user:pass@localhost:5432/sifguard) to use
    # Postgres/pgvector in a pilot/production deployment (see docker-compose.yml).
    DATABASE_URL: str = "sqlite:///./sifguard.db"

    JWT_SECRET: str = "change-this-secret-in-production-CHANGE-ME"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 60 * 12  # 12 hours

    # Bounded LLM assistance is OPTIONAL. If no key is configured the system
    # runs entirely on the deterministic rule engine + local ML/embedding
    # pipeline and falls back to template-based explanations. See
    # app/services/llm_client.py and Part 7.3 of the blueprint ("Offline / API
    # failure strategy").
    LLM_PROVIDER: str = ""  # "" | "anthropic" | "ollama"
    LLM_API_KEY: str = ""
    LLM_MODEL: str = "llama3:latest"
    # Compose service DNS is http://ollama:11434; local non-Docker default below.
    OLLAMA_BASE_URL: str = "http://127.0.0.1:11434"

    EMBEDDING_MODEL: str = "tfidf-svd-local"  # or paraphrase-multilingual-MiniLM-L12-v2

    FRONTEND_URL: str = "http://localhost:5173"

    # Abstention / confidence bands (prototype thresholds, Part 3.2 of blueprint)
    CONFIDENCE_HIGH: float = 75.0
    CONFIDENCE_MEDIUM: float = 45.0
    CONFIDENCE_LOW: float = 20.0

    # English-only rule NLP gate: fraction of tokenize() tokens that must be
    # ASCII Latin-alphabet (not Devanagari / other script). Below this ratio the
    # pipeline abstains with UNSUPPORTED_LANGUAGE instead of returning an empty
    # silent analysis. 0.70 is a deliberate prototype threshold — high enough
    # that dense non-Latin narratives fail, low enough that short English
    # reports with a few numeric tokens still pass.
    PIPELINE_LATIN_TOKEN_RATIO_MIN: float = 0.70


@lru_cache
def get_settings() -> Settings:
    return Settings()
