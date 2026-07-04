from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field


class RegionInfo(BaseModel):
    code: str
    name: str
    timezone: str
    climate_zone: str


class WeatherObservation(BaseModel):
    region_code: str
    observation_time: datetime
    temperature_f: float = Field(..., description="Dry-bulb temperature in Fahrenheit")
    humidity_pct: float = Field(..., ge=0, le=100)
    wind_speed_mph: float = Field(..., ge=0)
    cloud_cover_pct: float = Field(..., ge=0, le=100)
    precipitation_mm: float = Field(..., ge=0)
    heating_degree_hours: float = Field(..., ge=0, description="Hourly HDH base 65F, drives heating load")
    cooling_degree_hours: float = Field(..., ge=0, description="Hourly CDH base 65F, drives cooling load")


class EventType(str, Enum):
    PLANNED_MAINTENANCE = "planned_maintenance"
    UNPLANNED_OUTAGE = "unplanned_outage"
    DEMAND_RESPONSE = "demand_response"
    EQUIPMENT_ALERT = "equipment_alert"
    CYBER_SECURITY_ALERT = "cyber_security_alert"


class EventSeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GridEvent(BaseModel):
    event_id: str
    region_code: str
    event_time: datetime
    event_type: EventType
    severity: EventSeverity
    affected_capacity_mw: float = Field(..., ge=0)
    estimated_duration_minutes: int = Field(..., ge=0)
    description: str


class HealthResponse(BaseModel):
    status: str
    service: str
    timestamp: datetime
