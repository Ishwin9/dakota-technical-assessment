select
    region_code,
    observation_time,
    temperature_f,
    humidity_pct,
    wind_speed_mph,
    cloud_cover_pct,
    precipitation_mm,
    heating_degree_hours,
    cooling_degree_hours,
    ingested_at
from {{ source('bronze', 'enrichment_weather') }}
