# Technical Decisions

## Why Postgres

**Decision:** Postgres for both the application database and Airflow's own metadata store (as
two separate instances).

**Alternatives considered:** A managed cloud warehouse (Snowflake, BigQuery) or a
time-series-specialized database (TimescaleDB) for the weather data specifically.

**Trade-offs:** A cloud warehouse would scale further and has better native support for very
large time-series volumes, but requires an external account and adds cost and setup for
something meant to run entirely from `docker compose` on a laptop. TimescaleDB would give
better performance on high-volume time-series inserts, but at this data volume (tens of
thousands of rows) that's not a real constraint yet, and plain Postgres is one fewer moving
part to install and explain.

**Rationale:** Postgres is free, runs as a single container, has first-class dbt support, and
is the natural fit for a project that needs to be cloned and run by anyone with Docker
installed. It's also the tool the assessment names first as the expected choice.

## Why Airflow

**Decision:** Apache Airflow as the orchestrator, running on Astronomer's Astro Runtime image.

**Alternatives considered:** Dagster and Prefect (both listed as options in the assessment).

**Trade-offs:** Dagster's asset-based model is arguably a better conceptual fit for a pipeline
that's really about producing a set of tables (bronze → silver → gold) rather than running a
sequence of tasks, and its local dev experience is generally smoother out of the box. Prefect
is lighter-weight to stand up than either. Airflow's task-based DAG model is more verbose for
what's a fairly linear pipeline, and multi-container Airflow 3.x has more moving parts to wire
correctly (a dedicated metadata database, a separate DAG-processor process, a shared JWT
signing secret between components) than either alternative.

**Rationale:** Airflow remains the most widely deployed orchestrator in production data teams,
which makes it the safer default to demonstrate for a role where the team may already run it.
It's also explicitly named first in the assessment's list of options.

## Why dbt for transformation

**Decision:** dbt (dbt-core, local, `dbt-postgres` adapter) for the silver and gold layers.

**Alternatives considered:** Plain SQL scripts run from Airflow, or transforming in Python
(pandas) inside the DAG itself.

**Trade-offs:** Python/pandas transforms would avoid adding a second tool to the stack, but
lose dbt's built-in testing, documentation, and dependency graph — things that matter more as
the number of models grows. Plain SQL scripts get the SQL but none of the testing or lineage.

**Rationale:** dbt is what the assessment explicitly asks for, and it's the standard tool for
exactly this layer of the stack — version-controlled, tested, documented SQL transformations
with a clear model dependency graph.

## Why FastAPI for the enrichment service

**Decision:** FastAPI for the synthetic weather/grid-event data service.

**Alternatives considered:** Flask, or a static/pre-generated dataset instead of a live service.

**Trade-offs:** A static dataset would remove the need for a running service at all, but the
assessment specifically asks for a live API the ingestion layer calls. Flask would work
similarly to FastAPI here but without built-in request validation or automatic OpenAPI docs.

**Rationale:** FastAPI gives request/response validation via Pydantic and interactive API docs
for free, and is explicitly named in the assessment.

## Medallion architecture: bronze / silver / gold

**Decision:** Postgres schemas named literally `bronze`, `silver`, `gold`, matching the
assessment's request for a Medallion-architecture database design.

**Trade-offs:** None functionally versus the equivalent `raw`/`staging`/`marts` naming used in
many dbt example projects — this is a naming choice, not a structural one.

**Rationale:** Using the assessment's own vocabulary directly makes the design immediately
recognizable rather than requiring a reader to map generic names onto the pattern being asked
for.

## Local dbt, not dbt Cloud

**Decision:** dbt runs locally inside the Airflow image via `BashOperator`, not through a dbt
Cloud job.

**Trade-offs:** dbt Cloud offers a managed UI, job scheduling, and CI integration out of the
box. It also requires the database it's transforming to be reachable from the public internet,
since it's a SaaS product running outside this Docker network.

**Rationale:** The whole pipeline is designed to run self-contained from one
`docker-compose.yml` with no external accounts required — a private, locally-networked
Postgres instance rules out dbt Cloud as an option regardless of its other merits.
