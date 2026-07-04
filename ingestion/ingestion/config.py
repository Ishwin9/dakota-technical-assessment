from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="", extra="ignore")

    eia_api_key: str = ""
    eia_base_url: str = "https://api.eia.gov/v2"
    enrichment_api_base_url: str = "http://localhost:8000"

    request_timeout_seconds: float = 30.0
    max_retry_attempts: int = 5
    eia_page_size: int = 5000


settings = Settings()
