from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# apps/api/app/core/config.py -> repo root is parents[4]
REPO_ROOT = Path(__file__).resolve().parents[4]
API_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
DEMO_DIR = DATA_DIR / "demo"
PROCESSED_DIR = DATA_DIR / "processed"
DEFAULT_DB_PATH = API_ROOT / "opsledger.db"


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        extra="ignore",
        env_file_encoding="utf-8",
        populate_by_name=True,
    )

    app_name: str = "OpsLedger API"
    database_url: str = Field(default=f"sqlite:///{DEFAULT_DB_PATH.as_posix()}", alias="DATABASE_URL")
    cors_origins: str = Field(
        default="http://localhost:3000,http://127.0.0.1:3000",
        alias="CORS_ORIGINS",
    )
    demo_dir: Path = DEMO_DIR
    processed_dir: Path = PROCESSED_DIR

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
