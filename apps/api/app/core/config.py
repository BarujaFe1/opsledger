from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


def _truthy(value: str | None) -> bool:
    return bool(value) and value.strip().lower() in {"1", "true", "yes", "on"}

# apps/api/app/core/config.py -> apps/api is parents[2]
API_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = API_ROOT.parents[1]


def _default_database_url() -> str:
    # Vercel serverless FS is read-only except /tmp.
    if os.getenv("VERCEL"):
        return "sqlite:////tmp/opsledger.db"
    return f"sqlite:///{(API_ROOT / 'opsledger.db').as_posix()}"


def _default_demo_dir() -> Path:
    packaged = API_ROOT / "data" / "demo"
    if packaged.exists():
        return packaged
    return REPO_ROOT / "data" / "demo"


def _default_processed_dir() -> Path:
    if os.getenv("VERCEL"):
        return Path("/tmp/opsledger_processed")
    return API_ROOT / "data" / "processed"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )

    app_name: str = "OpsLedger API"
    database_url: str = Field(default_factory=_default_database_url, alias="DATABASE_URL")
    cors_origins: str = Field(default="", alias="CORS_ORIGINS")
    demo_dir: Path = Field(default_factory=_default_demo_dir)
    processed_dir: Path = Field(default_factory=_default_processed_dir)
    # Public demo = stateless, read-only, synthetic dataset, no uploads/mutations.
    # Defaults to True on Vercel (env VERCEL); locally it is a single-user workspace
    # unless explicitly forced via PUBLIC_DEMO_MODE.
    public_demo_mode: bool = Field(
        default_factory=lambda: bool(os.getenv("VERCEL")) or _truthy(os.getenv("PUBLIC_DEMO_MODE")),
        alias="PUBLIC_DEMO_MODE",
    )
    # Bump when the golden demo dataset or the reconciliation policy changes so the
    # in-memory public cache is invalidated.
    demo_dataset_version: str = Field(default="2026-06-monthly_closing", alias="DEMO_DATASET_VERSION")

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip():
            return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

        origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
            "http://localhost:3100",
            "http://127.0.0.1:3100",
            "https://opsledger-app.vercel.app",
            "https://opsledger-one.vercel.app",
            "https://opsledger-barujafe1s-projects.vercel.app",
        ]
        vercel_url = os.getenv("VERCEL_URL")
        if vercel_url:
            origins.append(f"https://{vercel_url}")
        return origins


@lru_cache
def get_settings() -> Settings:
    return Settings()
