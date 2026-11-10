"""ProofLine API configuration loaded from environment variables."""
from __future__ import annotations

from typing import List, Union
from pydantic import field_validator
from pydantic_settings import BaseSettings


def normalize_postgres_url(url: str) -> str:
    """Ensure PostgreSQL connection strings use the installed psycopg v3 driver."""
    raw = url.strip()
    if raw.startswith("postgres://"):
        return "postgresql+psycopg://" + raw[len("postgres://") :]
    if raw.startswith("postgresql://"):
        return "postgresql+psycopg://" + raw[len("postgresql://") :]
    return raw


class Settings(BaseSettings):
    database_url: str = "sqlite:///./proofline.db"
    test_database_url: str = "postgresql+psycopg://proofline:proofline@localhost:5432/proofline_test"
    jwt_secret: str = "change-me-in-production"
    jwt_algorithm: str = "HS256"
    jwt_expire_minutes: int = 1440
    environment: str = "development"

    # LLM Configuration (Groq / OpenAI / Gemini / OpenRouter / Ollama)
    llm_api_key: str = ""
    llm_model: str = "openai/gpt-oss-120b"
    llm_base_url: str = "https://api.groq.com/openai/v1"
    mock_ai: bool = True

    # OpenAI Embeddings Configuration (RAG Subsystem)
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimensions: int = 1536

    cors_origins: Union[str, List[str]] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    @field_validator("database_url", "test_database_url", mode="before")
    @classmethod
    def coerce_postgres_driver(cls, v: str) -> str:
        if isinstance(v, str):
            return normalize_postgres_url(v)
        return v

    @field_validator("cors_origins", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str):
            if v == "*":
                return ["*"]
            return [i.strip() for i in v.split(",") if i.strip()]
        return v

    model_config = {
        "env_file": (".env", "backend/.env", "../.env"),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
