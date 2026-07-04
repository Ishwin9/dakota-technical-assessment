# Schema

Medallion architecture: `bronze` (landing), `silver` (typed, dbt views), `gold` (analytical
tables, dbt tables). See `er_diagram.png` for the full picture.

## bronze (raw landing, created by `database/init/bronze.sql`)

### bronze.eia_natural_gas_imports

One row per EIA series per month. `series` is EIA's own series identifier (one per
country/import-method/measure combination); `period` is kept as EIA's native `"YYYY-MM"` text
rather than cast to a date, so the landing table never has to guess at EIA's format — casting
happens in `silver.stg_eia_natural_gas_imports`.

| column | type | notes |
|---|---|---|
| series | text | part of primary key |
| period | text | part of primary key, "YYYY-MM" |
| duoarea | text | EIA area code |
| area_name | text | e.g. "CAN", "MEX", "U.S." |
| product / product_name | text | always natural gas here |
| process / process_name | text | import method: pipeline, LNG, CNG, or price series |
| series_description | text | |
| value | numeric | nullable — a small number of EIA rows omit it |
| units | text | "MMCF" for volumes, "$/MCF" for price series |
| ingested_at | timestamptz | set by the loader, default `now()` |

Primary key: `(series, period)`. Indexed on `period` for range scans.

### bronze.enrichment_weather

One row per region per hour.

| column | type | notes |
|---|---|---|
| region_code | text | part of primary key, EIA-930 balancing-authority code |
| observation_time | timestamptz | part of primary key |
| temperature_f, humidity_pct, wind_speed_mph, cloud_cover_pct, precipitation_mm | numeric | |
| heating_degree_hours, cooling_degree_hours | numeric | hourly HDH/CDH, base 65°F |
| ingested_at | timestamptz | set by the loader |

Primary key: `(region_code, observation_time)`. Indexed on `observation_time` for range scans.

## silver (dbt views)

- **stg_eia_natural_gas_imports** — bronze columns, plus `period_month` (a real `date`, parsed
  from bronze's `period` text).
- **stg_enrichment_weather** — bronze columns, renamed/passed through unchanged; typing was
  already correct at landing.

## gold (dbt tables)

- **fct_natural_gas_imports_monthly** — `(period_month, area_name)`, total import volume in
  MMCF. Filtered to `units = 'MMCF'` so volume and price series (different units) aren't summed
  together.
- **fct_weather_daily** — `(region_code, observation_date)`, daily averages/sums rolled up from
  hourly bronze data.
- **fct_national_weather_monthly** — `(period_month)`, national monthly weather rollup at the
  same grain as `fct_natural_gas_imports_monthly`. The two gold tables can be joined on
  `period_month` for demand-vs-import-volume analysis; there's no finer shared key, since gas
  imports are tracked by source country and weather by electricity balancing-authority region.

## Time-series considerations

Both bronze tables are naturally append-mostly and time-ordered (`period` / `observation_time`),
which is why each has a range-scan index on its time column in addition to the natural-key
primary key. At the current data volume (tens of thousands of rows total) that's sufficient;
partitioning `bronze.enrichment_weather` by month would be the natural next step if hourly
ingestion ran for years rather than days.

## Idempotency

Every bronze load is an upsert (`INSERT ... ON CONFLICT (natural key) DO UPDATE`), not an
append. Re-running a load for a period that's already landed overwrites it with the latest
values rather than creating a duplicate row — this is what makes it safe for the Airflow DAG to
re-pull a window of already-loaded data (done deliberately for the EIA extract, to catch
revisions to recently published figures).
