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

    ha_base_url: str = ""
    ha_token: str = ""
    ha_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    ha_temperature_entities: str = ""
    ha_presence_entities: str = ""
    ha_selected_entities: str = ""
    ha_max_temperature_sensors: int = Field(default=6, ge=1, le=20)

    github_owner: str = "MushroomStew01"
    github_repositories: str = (
        "stewy-os,lexus-personal-hub,chatgpt-calorie-bridge,"
        "movie-ticket-discord-monitor"
    )
    github_token: str = ""
    github_timeout_seconds: float = Field(default=5.0, gt=0, le=60)
    github_poll_seconds: int = Field(default=600, ge=60, le=3600)

    docker_socket_path: str = "/var/run/docker.sock"
    docker_timeout_seconds: float = Field(default=3.0, gt=0, le=30)

    notifications_enabled: bool = False
    discord_webhook_url: str = ""
    discord_user_id: str = ""
    notification_discord_username: str = "Stewy OS"
    notification_min_severity: str = "warning"
    notification_quiet_start: str = "23:00"
    notification_quiet_end: str = "07:00"
    notification_dedupe_minutes: int = Field(default=60, ge=0, le=1440)
    notification_retry_minutes: int = Field(default=5, ge=1, le=120)
    notification_max_attempts: int = Field(default=3, ge=1, le=10)
    notification_event_max_age_minutes: int = Field(default=10, ge=1, le=1440)
    notification_timeout_seconds: float = Field(default=5.0, gt=0, le=30)


@lru_cache
def get_settings() -> Settings:
    return Settings()
