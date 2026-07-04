# Architecture

## Overview

This is a small energy-analytics pipeline built around two data sources: the EIA's public
natural gas import statistics, and a synthetic weather/grid-event API I built alongside it.
Both land in Postgres, get transformed through a bronze/silver/gold (medallion) layering in
dbt, and are orchestrated by Airflow. Everything runs as one `docker compose` stack.

```
EIA API (real)  ──┐
                   ├──> Airflow DAG (extract, load) ──> Postgres: bronze ──> dbt: silver ──> dbt: gold
enrichment-api  ──┘         (energy_pipeline)
(synthetic, mine)
```

## Components

### FastAPI enrichment service (`api/`)

Generates synthetic hourly weather and grid-event data for 8 US electricity balancing
authorities (CISO, ERCO, PJM, MISO, SWPP, NYIS, ISNE, SOCO), using EIA's own EIA-930
balancing-authority codes so the data is compatible with EIA's electricity datasets if the
pipeline is extended to pull those later.

Generation is deterministic: every value is seeded from a hash of `(region, hour)` or
`(region, day)`, not global randomness. Calling `/weather/CISO` twice for the same hour returns
identical numbers. This matters for two reasons: it keeps the DAG idempotent (re-running a
load doesn't produce different numbers for the same period), and it mimics how a real weather
feed behaves — you don't get a different reading for an hour that's already passed.

Built with FastAPI + `uv`, containerized, with a `/health` endpoint and OpenAPI docs at `/docs`.

### Ingestion (`ingestion/`)

Two plain-function modules, `eia.py` and `enrichment.py`, sharing one small HTTP helper
(`_http.py`) that wraps `httpx` with `tenacity`-based retry: retryable statuses (429, 5xx,
connection/timeout errors) get retried with exponential backoff; everything else (4xx) fails
immediately.

`eia.fetch_natural_gas_imports()` hits EIA's `natural-gas/move/impc` route (imports by country,
monthly) and paginates through EIA's 5000-row-per-request cap. `enrichment.py` calls the
enrichment endpoint the DAG uses: `/weather` (the API also exposes `/grid-events`, built and
tested, not currently part of the pipeline — see `decisions.md`).

Ingestion code does not talk to Postgres. It only fetches and validates (via Pydantic models)
and returns plain data structures. Persistence is the orchestration layer's job.

### Database (`database/`)

Postgres, one schema per medallion layer:

- **bronze** — landing tables, close to the source shape. `bronze.eia_natural_gas_imports` and
  `bronze.enrichment_weather`, created by `database/init/bronze.sql`. Both have a unique
  constraint matching their natural key so loads are idempotent upserts, not blind appends.
- **silver** — dbt views that type and rename bronze columns (e.g. EIA's `"2026-04"` period
  string parsed into a real date).
- **gold** — dbt tables at the actual analytical grain: monthly import volume by country, daily
  weather by region, and a national monthly weather rollup.

See `database/documentation/` for the full schema writeup and ER diagram.

### Transformation (`dbt/`)

A dbt project (`dakota_energy`) with a `generate_schema_name` macro override so a model tagged
`+schema: gold` lands in a schema literally named `gold`, not `<target_schema>_gold`. Silver
models are views (cheap, no reason to materialize a 1:1 typed copy of a table that's already
small); gold models are tables (aggregates worth persisting). Every model has `not_null` (and
one `unique`) schema tests, documented in `_sources.yml` / `_staging.yml` / `_marts.yml`.

### Orchestration (`orchestration/`)

One Airflow DAG (`energy_pipeline`, `@daily`), running on the Astro Runtime image
(`quay.io/astronomer/astro-runtime`, Astronomer's maintained Airflow distribution — see
`decisions.md` for why). Five tasks:

```
extract_eia ──> load_eia ──────────────┐
                                        ├──> run_dbt (dbt build: silver + gold + tests)
extract_enrichment_weather ──> load_enrichment_weather ┘
```

`load_eia` and `load_enrichment_weather` upsert into their bronze tables
(`INSERT ... ON CONFLICT DO UPDATE`) using each table's natural key, so re-running a load for
a period that's already there overwrites rather than duplicates. `run_dbt` is a `BashOperator`
running `dbt build` against the mounted `dbt/` project, using the same Postgres.

Airflow's own metadata lives in a separate Postgres instance (`airflow-postgres`) from the
application data (`postgres`) — mixing the two would put the DAG scheduling history in the
same database as the numbers being analyzed, which invites confusion later even if it works
fine today.

### Reporting (`reports/`)

See `reports/README.md` and the generated report for what's produced and how.

## Data flow, end to end

1. `extract_eia` queries `MAX(period)` from `bronze.eia_natural_gas_imports` as a watermark
   (empty table on first run → full history pull, ~16k rows, cheap enough to just do). Later
   runs subtract a 2-month overlap from the watermark before calling the EIA API, to pick up
   revisions EIA sometimes publishes to recent months.
2. `extract_enrichment_weather` calls the enrichment API's `/weather` endpoint once, returning
   one row per region for the current hour.
3. Both loads upsert into their bronze tables.
4. `run_dbt` runs `dbt build`, which re-runs the silver views and rebuilds the gold tables from
   whatever's currently in bronze, then runs the schema tests.

## Scalability considerations

This is sized for a demo, not production load, but the seams are in the right places:

- **Ingestion** already paginates and retries; scaling to more EIA routes or more enrichment
  endpoints is adding more functions to the same two files, not new infrastructure.
- **Bronze tables upsert on natural keys**, so re-running a load (or backfilling a wider date
  range) is safe — it converges rather than duplicates.
- **dbt gold tables are full-refresh, not incremental** — reasonable at ~16k EIA rows and ~200
  weather rows/day, but the first thing I'd change if either grew by orders of magnitude would
  be switching the gold models to `materialized: incremental`.
- **Airflow's metadata Postgres is already separate from the application Postgres**, so scaling
  either one (or eventually moving to managed Postgres/Cloud Composer/MWAA) doesn't require
  re-architecting the other.
- The weather generator is **deterministic and stateless** — it could be horizontally scaled
  behind a load balancer with zero coordination, since no instance needs to know what another
  instance returned.
