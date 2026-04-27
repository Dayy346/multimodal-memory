"""Application settings (env + .env)."""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=str(PROJECT_ROOT / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    database_url: str = Field(
        default="postgresql+psycopg://mm:mm@localhost:5432/multimodal_memory",
        alias="DATABASE_URL",
    )

    allowed_scan_roots: str = Field(
        default=str(PROJECT_ROOT / "data" / "samples"),
        alias="ALLOWED_SCAN_ROOTS",
        description="Comma-separated absolute directory paths the API may scan.",
    )

    cors_origins: str = Field(
        default="http://localhost:5173,http://127.0.0.1:5173",
        alias="CORS_ORIGINS",
    )

    embedding_vector_dim: int = Field(default=3072, alias="EMBEDDING_VECTOR_DIM")

    gemini_embedding_model: str = Field(
        default="gemini-embedding-2-preview",
        alias="GEMINI_EMBEDDING_MODEL",
    )

    gemini_embedding_dimensionality: int | None = Field(
        default=None,
        alias="GEMINI_EMBEDDING_DIMENSIONALITY",
    )

    @field_validator("gemini_embedding_dimensionality", mode="before")
    @classmethod
    def blank_dim_none(cls, v: object) -> object:
        if v == "" or v is None:
            return None
        return v

    def roots_list(self) -> list[Path]:
        parts = [p.strip() for p in self.allowed_scan_roots.split(",") if p.strip()]
        return [Path(p).expanduser().resolve() for p in parts]

    def cors_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()


def clear_settings_cache() -> None:
    get_settings.cache_clear()
