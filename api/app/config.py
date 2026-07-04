from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="ENRICHMENT_")

    service_name: str = "dakota-enrichment-api"
    version: str = "0.1.0"
    max_history_hours: int = 24 * 30
    max_history_days: int = 90


settings = Settings()
