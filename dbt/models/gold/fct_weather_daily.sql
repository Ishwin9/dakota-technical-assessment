select
    region_code,
    date_trunc('day', observation_time) as observation_date,
    avg(temperature_f) as avg_temperature_f,
    avg(humidity_pct) as avg_humidity_pct,
    sum(heating_degree_hours) as total_heating_degree_hours,
    sum(cooling_degree_hours) as total_cooling_degree_hours,
    sum(precipitation_mm) as total_precipitation_mm
from {{ ref('stg_enrichment_weather') }}
group by 1, 2
