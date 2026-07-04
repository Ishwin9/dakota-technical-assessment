import httpx

from . import _http
from .config import settings


def _client() -> httpx.Client:
    return httpx.Client(base_url=settings.enrichment_api_base_url, timeout=settings.request_timeout_seconds)


def fetch_regions() -> list[dict]:
    with _client() as client:
        return _http.get(client, "/regions").json()


def fetch_current_weather(region_code: str | None = None) -> object:
    path = f"/weather/{region_code}" if region_code else "/weather"
    with _client() as client:
        return _http.get(client, path).json()


def fetch_weather_history(region_code: str, hours: int = 24) -> list[dict]:
    with _client() as client:
        return _http.get(client, f"/weather/{region_code}/history", {"hours": hours}).json()


def fetch_grid_events(region_code: str | None = None, days: int = 7) -> list[dict]:
    path = f"/grid-events/{region_code}" if region_code else "/grid-events"
    with _client() as client:
        return _http.get(client, path, {"days": days}).json()
