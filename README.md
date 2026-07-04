# Dakota Energy Analytics Pipeline

An end-to-end data pipeline: a synthetic weather/grid-event API, ingestion from that API plus
the EIA's public natural gas import statistics, a Postgres database in a bronze/silver/gold
(medallion) layout, dbt transformations, Airflow orchestration, and an automated PDF
executive report. Everything runs from one `docker compose` stack.

See [`docs/architecture.md`](docs/architecture.md) for how it fits together and
[`docs/decisions.md`](docs/decisions.md) for why it's built this way.

## Requirements

- [Docker](https://www.docker.com/) (or [Colima](https://github.com/abiosoft/colima) +
  Docker CLI on macOS) with the daemon running
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)
- A free [EIA API key](https://www.eia.gov/opendata/register.php)

## Setup

```bash
cp .env.example .env
# then edit .env and set EIA_API_KEY, and generate a value for AIRFLOW_JWT_SECRET:
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
```

## Run

```bash
./run.sh
```

This builds every image, starts the full stack, triggers the `energy_pipeline` DAG once, waits
for it to finish, and generates the executive report. It's safe to re-run — every step is
idempotent (bronze tables upsert on natural keys, `docker compose up` reuses existing
containers/volumes).

Or drive it step by step with the Makefile:

```bash
make setup    # build images, create .env if missing
make run      # start the stack, trigger the pipeline
make test     # run the API and ingestion test suites
make report   # regenerate the executive PDF report
make clean    # tear down containers and volumes
```

## Where things land

| What | Where |
|---|---|
| Airflow UI (DAG runs, logs) | http://localhost:8080/dags/energy_pipeline |
| Enrichment API docs | http://localhost:8000/docs |
| Executive report | `reports/output/energy_report.pdf` |
| Database | `localhost:${POSTGRES_HOST_PORT:-5433}` (defaults to 5433, not 5432, to avoid clashing with a locally-installed Postgres) |

The Airflow UI needs no login (`SimpleAuthManager` with `simple_auth_manager_all_admins`,
appropriate for this local-only setup).

## Project structure

```
api/            FastAPI synthetic enrichment service (weather + grid events)
ingestion/      Plain-function clients: EIA API, enrichment API
database/       Bronze-layer schema (init/) and schema docs (documentation/)
dbt/            Silver + gold dbt models (dakota_energy project)
orchestration/  Airflow DAG + Dockerfile (Astro Runtime image)
reports/        Executive PDF report generator
docs/           Architecture, decisions, ER diagram
tests/          pytest suites for api/ and ingestion/
```

## Testing

```bash
make test
```

Runs the API service's and ingestion package's test suites (generators, endpoints, retry
behavior, pagination) via `uv run pytest`. dbt's own schema tests (`not_null`, `unique`) run
as part of the pipeline itself, inside the `run_dbt` DAG task.
