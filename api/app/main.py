from __future__ import annotations

import logging
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import RedirectResponse

from .config import settings
from .generators import generate_events_for_range, generate_weather, generate_weather_history
from .models import GridEvent, HealthResponse, RegionInfo, WeatherObservation
from .regions import REGIONS

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
logger = logging.getLogger("dakota.enrichment")

app = FastAPI(
    title="Dakota Enrichment API",
    description=(
        "Synthetic weather and grid-event enrichment data for energy analytics, "
        "keyed on EIA-930 balancing-authority region codes."
    ),
    version=settings.version,
)


def _resolve_region(region_code: str):
    region = REGIONS.get(region_code.upper())
    if region is None:
        logger.warning("unknown region requested: %s", region_code)
        raise HTTPException(
            status_code=404,
            detail=f"Unknown region_code '{region_code}'. See GET /regions for valid codes.",
        )
    return region


def _now() -> datetime:
    return datetime.now(timezone.utc)


@app.get("/", include_in_schema=False)
def root() -> RedirectResponse:
    return RedirectResponse(url="/docs")


@app.get("/health", response_model=HealthResponse, tags=["meta"])
def health() -> HealthResponse:
    return HealthResponse(status="ok", service=settings.service_name, timestamp=_now())


@app.get("/regions", response_model=list[RegionInfo], tags=["meta"])
def list_regions() -> list[RegionInfo]:
    return [
        RegionInfo(code=r.code, name=r.name, timezone=r.timezone, climate_zone=r.climate_zone)
        for r in REGIONS.values()
    ]


@app.get("/weather", response_model=list[WeatherObservation], tags=["weather"])
def current_weather_all_regions(
    as_of: datetime | None = Query(None, description="Timestamp to generate weather for; defaults to now (UTC)."),
) -> list[WeatherObservation]:
    at = as_of or _now()
    return [generate_weather(region, at) for region in REGIONS.values()]


@app.get("/weather/{region_code}", response_model=WeatherObservation, tags=["weather"])
def current_weather(
    region_code: str,
    as_of: datetime | None = Query(None, description="Timestamp to generate weather for; defaults to now (UTC)."),
) -> WeatherObservation:
    region = _resolve_region(region_code)
    at = as_of or _now()
    return generate_weather(region, at)


@app.get("/weather/{region_code}/history", response_model=list[WeatherObservation], tags=["weather"])
def weather_history(
    region_code: str,
    hours: int = Query(24, ge=1, le=settings.max_history_hours, description="Number of hourly observations to return, most recent last."),
    as_of: datetime | None = Query(None, description="End of the history window; defaults to now (UTC)."),
) -> list[WeatherObservation]:
    region = _resolve_region(region_code)
    at = as_of or _now()
    return generate_weather_history(region, at, hours)


@app.get("/grid-events", response_model=list[GridEvent], tags=["grid-events"])
def grid_events_all_regions(
    days: int = Query(7, ge=1, le=settings.max_history_days, description="Lookback window in days."),
    as_of: datetime | None = Query(None, description="End of the lookback window; defaults to now (UTC)."),
) -> list[GridEvent]:
    at = as_of or _now()
    events: list[GridEvent] = []
    for region in REGIONS.values():
        events.extend(generate_events_for_range(region, at, days))
    return sorted(events, key=lambda e: e.event_time)


@app.get("/grid-events/{region_code}", response_model=list[GridEvent], tags=["grid-events"])
def grid_events(
    region_code: str,
    days: int = Query(7, ge=1, le=settings.max_history_days, description="Lookback window in days."),
    as_of: datetime | None = Query(None, description="End of the lookback window; defaults to now (UTC)."),
) -> list[GridEvent]:
    region = _resolve_region(region_code)
    at = as_of or _now()
    return generate_events_for_range(region, at, days)
