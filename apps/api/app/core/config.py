from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

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

    @property
    def cors_origin_list(self) -> list[str]:
        if self.cors_origins.strip():
            return [o.strip() for o in self.cors_origins.split(",") if o.strip()]

        origins = [
            "http://localhost:3000",
            "http://127.0.0.1:3000",
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
