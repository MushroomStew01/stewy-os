from __future__ import annotations

from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    app_name: str = "Stewy OS"
    app_env: str = "production"
    app_timezone: str = "America/Toronto"
    app_refresh_seconds: int = Field(default=30, ge=10, le=3600)
    integration_cache_seconds: int = Field(default=20, ge=0, le=300)
    database_url: str = "sqlite:///./data/stewy.db"

    stewy_username: str = "andy"
    stewy_password: str = ""

    lexus_base_url: str = ""
    lexus_timeout_seconds: float = Field(default=5.0, gt=0, le=60)

    calorie_base_url: str = ""
    calorie_api_key: str = ""
    calorie_timeout_seconds: float = Field(default=5.0, gt=0, le=60)

    movie_status_url: str = (
        "https://raw.githubusercontent.com/MushroomStew01/"
        "movie-ticket-discord-monitor/main/status.json"
    )
    movie_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    movie_stale_hours: int = Field(default=36, ge=1, le=168)


@lru_cache
def get_settings() -> Settings:
    return Settings()
