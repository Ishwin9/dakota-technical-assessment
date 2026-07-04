from __future__ import annotations

import hashlib
import math
import random
import uuid
from datetime import date, datetime, timedelta

from .models import EventSeverity, EventType, GridEvent, WeatherObservation
from .regions import RegionProfile

# EIA-930 style balancing authorities skew coastal/southern -> humid climates
# get a higher ambient humidity baseline than arid/mediterranean ones.
_HUMIDITY_BASE_BY_CLIMATE = {
    "mediterranean": 55.0,
    "humid_subtropical": 72.0,
    "humid_continental": 65.0,
    "semi_arid": 40.0,
}

_EVENT_DAILY_PROBABILITY = {
    EventType.PLANNED_MAINTENANCE: 0.08,
    EventType.UNPLANNED_OUTAGE: 0.04,
    EventType.DEMAND_RESPONSE: 0.05,
    EventType.EQUIPMENT_ALERT: 0.06,
    EventType.CYBER_SECURITY_ALERT: 0.01,
}

_SEVERITY_WEIGHTS_BY_EVENT_TYPE = {
    EventType.PLANNED_MAINTENANCE: {EventSeverity.LOW: 0.7, EventSeverity.MEDIUM: 0.3},
    EventType.UNPLANNED_OUTAGE: {
        EventSeverity.MEDIUM: 0.4,
        EventSeverity.HIGH: 0.4,
        EventSeverity.CRITICAL: 0.2,
    },
    EventType.DEMAND_RESPONSE: {EventSeverity.LOW: 0.5, EventSeverity.MEDIUM: 0.5},
    EventType.EQUIPMENT_ALERT: {
        EventSeverity.LOW: 0.4,
        EventSeverity.MEDIUM: 0.4,
        EventSeverity.HIGH: 0.2,
    },
    EventType.CYBER_SECURITY_ALERT: {EventSeverity.HIGH: 0.6, EventSeverity.CRITICAL: 0.4},
}

_CAPACITY_RANGE_MW_BY_SEVERITY = {
    EventSeverity.LOW: (5.0, 50.0),
    EventSeverity.MEDIUM: (50.0, 250.0),
    EventSeverity.HIGH: (250.0, 800.0),
    EventSeverity.CRITICAL: (800.0, 2500.0),
}

_DURATION_MINUTES_RANGE_BY_EVENT_TYPE = {
    EventType.PLANNED_MAINTENANCE: (120, 720),
    EventType.UNPLANNED_OUTAGE: (15, 480),
    EventType.DEMAND_RESPONSE: (30, 240),
    EventType.EQUIPMENT_ALERT: (10, 180),
    EventType.CYBER_SECURITY_ALERT: (30, 360),
}


def _seeded_random(*parts: str) -> random.Random:
    digest = hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()
    return random.Random(int(digest[:16], 16))


def _floor_to_hour(ts: datetime) -> datetime:
    return ts.replace(minute=0, second=0, microsecond=0)


def _weighted_choice(rng: random.Random, weights: dict) -> object:
    keys = list(weights.keys())
    cumulative, roll = [], rng.random()
    total = 0.0
    for key in keys:
        total += weights[key]
        cumulative.append(total)
    for key, threshold in zip(keys, cumulative):
        if roll <= threshold:
            return key
    return keys[-1]


def generate_weather(region: RegionProfile, at: datetime) -> WeatherObservation:
    """Generate one hourly weather observation for a region at a given timestamp."""
    hour_ts = _floor_to_hour(at)
    rng = _seeded_random(region.code, hour_ts.isoformat(), "weather")

    day_of_year = hour_ts.timetuple().tm_yday
    seasonal = math.cos(2 * math.pi * (day_of_year - 172) / 365.25)
    diurnal = math.cos(2 * math.pi * (hour_ts.hour - 15) / 24)

    temperature_f = (
        region.base_temp_f
        + seasonal * region.temp_swing_f * 0.65
        + diurnal * region.temp_swing_f * 0.35
        + rng.gauss(0, 2.5)
    )

    humidity_base = _HUMIDITY_BASE_BY_CLIMATE.get(region.climate_zone, 55.0)
    humidity_pct = _clamp(humidity_base - diurnal * 12 + rng.gauss(0, 6), 5.0, 100.0)

    wind_speed_mph = max(0.0, rng.gammavariate(2.0, 3.5))
    cloud_cover_pct = _clamp(rng.betavariate(2.0, 2.2) * 100, 0.0, 100.0)

    precipitation_mm = 0.0
    if cloud_cover_pct > 55:
        precipitation_mm = round(rng.expovariate(1 / 2.5), 2)

    heating_degree_hours = max(0.0, 65.0 - temperature_f)
    cooling_degree_hours = max(0.0, temperature_f - 65.0)

    return WeatherObservation(
        region_code=region.code,
        observation_time=hour_ts,
        temperature_f=round(temperature_f, 1),
        humidity_pct=round(humidity_pct, 1),
        wind_speed_mph=round(wind_speed_mph, 1),
        cloud_cover_pct=round(cloud_cover_pct, 1),
        precipitation_mm=precipitation_mm,
        heating_degree_hours=round(heating_degree_hours, 2),
        cooling_degree_hours=round(cooling_degree_hours, 2),
    )


def generate_weather_history(
    region: RegionProfile, end: datetime, hours: int
) -> list[WeatherObservation]:
    end_hour = _floor_to_hour(end)
    return [
        generate_weather(region, end_hour - timedelta(hours=offset))
        for offset in range(hours - 1, -1, -1)
    ]


def _build_event(
    region: RegionProfile, day: date, event_type: EventType, index: int, rng: random.Random
) -> GridEvent:
    severity = _weighted_choice(rng, _SEVERITY_WEIGHTS_BY_EVENT_TYPE[event_type])
    capacity_low, capacity_high = _CAPACITY_RANGE_MW_BY_SEVERITY[severity]
    duration_low, duration_high = _DURATION_MINUTES_RANGE_BY_EVENT_TYPE[event_type]

    event_id = str(
        uuid.uuid5(uuid.NAMESPACE_DNS, f"{region.code}|{day.isoformat()}|{event_type.value}|{index}")
    )
    event_hour = rng.randint(0, 23)
    event_minute = rng.randint(0, 59)
    event_time = datetime.combine(day, datetime.min.time()).replace(
        hour=event_hour, minute=event_minute
    )

    return GridEvent(
        event_id=event_id,
        region_code=region.code,
        event_time=event_time,
        event_type=event_type,
        severity=severity,
        affected_capacity_mw=round(rng.uniform(capacity_low, capacity_high), 1),
        estimated_duration_minutes=rng.randint(duration_low, duration_high),
        description=_describe_event(region, event_type, severity),
    )


def _describe_event(region: RegionProfile, event_type: EventType, severity: EventSeverity) -> str:
    labels = {
        EventType.PLANNED_MAINTENANCE: "Scheduled maintenance window",
        EventType.UNPLANNED_OUTAGE: "Unplanned generation/transmission outage",
        EventType.DEMAND_RESPONSE: "Demand response event triggered",
        EventType.EQUIPMENT_ALERT: "Equipment health alert raised",
        EventType.CYBER_SECURITY_ALERT: "Cyber security alert issued",
    }
    return f"{labels[event_type]} in {region.name} ({severity.value} severity)"


def generate_events_for_day(region: RegionProfile, day: date) -> list[GridEvent]:
    """Deterministically generate zero or more grid events for a region/day."""
    rng = _seeded_random(region.code, day.isoformat(), "events")
    events: list[GridEvent] = []
    for index, (event_type, probability) in enumerate(_EVENT_DAILY_PROBABILITY.items()):
        if rng.random() < probability:
            events.append(_build_event(region, day, event_type, index, rng))
    return sorted(events, key=lambda e: e.event_time)


def generate_events_for_range(
    region: RegionProfile, end: datetime, days: int
) -> list[GridEvent]:
    end_day = end.date()
    events: list[GridEvent] = []
    for offset in range(days - 1, -1, -1):
        events.extend(generate_events_for_day(region, end_day - timedelta(days=offset)))
    return events


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))
