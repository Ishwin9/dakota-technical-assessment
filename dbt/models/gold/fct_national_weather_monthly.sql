-- National monthly weather rollup, at the same grain as fct_natural_gas_imports_monthly
-- so the two can be joined on period_month for demand-vs-import-volume analysis. Note this
-- is national-average weather against country-level import volume -- the enrichment API's
-- regions are electricity balancing authorities, not the natural-gas source countries, so
-- there's no finer-grained join key between the two domains.
select
    date_trunc('month', observation_date) as period_month,
    avg(avg_temperature_f) as avg_temperature_f,
    sum(total_heating_degree_hours) as total_heating_degree_hours,
    sum(total_cooling_degree_hours) as total_cooling_degree_hours
from {{ ref('fct_weather_daily') }}
group by 1
