CREATE SCHEMA IF NOT EXISTS bronze;

-- EIA natural-gas/move/impc (imports by country, monthly). period kept as EIA's native
-- "YYYY-MM" text rather than cast to date here; dbt silver models handle typing.
CREATE TABLE IF NOT EXISTS bronze.eia_natural_gas_imports (
    series              text NOT NULL,
    period              text NOT NULL,
    duoarea             text NOT NULL,
    area_name           text NOT NULL,
    product             text NOT NULL,
    product_name        text NOT NULL,
    process             text NOT NULL,
    process_name        text NOT NULL,
    series_description  text NOT NULL,
    value               numeric,
    units               text NOT NULL,
    ingested_at         timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (series, period)
);

CREATE INDEX IF NOT EXISTS idx_eia_natural_gas_imports_period ON bronze.eia_natural_gas_imports (period);

-- Synthetic hourly weather from the enrichment API, one row per region per hour.
CREATE TABLE IF NOT EXISTS bronze.enrichment_weather (
    region_code           text NOT NULL,
    observation_time      timestamptz NOT NULL,
    temperature_f         numeric NOT NULL,
    humidity_pct          numeric NOT NULL,
    wind_speed_mph        numeric NOT NULL,
    cloud_cover_pct       numeric NOT NULL,
    precipitation_mm      numeric NOT NULL,
    heating_degree_hours  numeric NOT NULL,
    cooling_degree_hours  numeric NOT NULL,
    ingested_at           timestamptz NOT NULL DEFAULT now(),
    PRIMARY KEY (region_code, observation_time)
);

CREATE INDEX IF NOT EXISTS idx_enrichment_weather_observation_time ON bronze.enrichment_weather (observation_time);
