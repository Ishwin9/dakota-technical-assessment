from datetime import datetime, timedelta

from airflow.sdk import dag, task
from airflow.providers.postgres.hooks.postgres import PostgresHook
from airflow.providers.standard.operators.bash import BashOperator
from psycopg2.extras import execute_values

from ingestion import eia, enrichment

POSTGRES_CONN_ID = "dakota_postgres"
OVERLAP_MONTHS = 2

# Bronze (medallion) table shapes, see database/init/bronze.sql:
#   bronze.eia_natural_gas_imports (series, period, duoarea, area_name, product, product_name,
#       process, process_name, series_description, value, units) unique on (series, period)
#   bronze.enrichment_weather (region_code, observation_time, temperature_f, humidity_pct,
#       wind_speed_mph, cloud_cover_pct, precipitation_mm, heating_degree_hours,
#       cooling_degree_hours) unique on (region_code, observation_time)


def _upsert(conn_id: str, table: str, conflict_cols: list[str], rows: list[dict]) -> int:
    if not rows:
        return 0
    columns = list(rows[0].keys())
    update_cols = [c for c in columns if c not in conflict_cols]
    sql = f"""
        INSERT INTO {table} ({", ".join(columns)}) VALUES %s
        ON CONFLICT ({", ".join(conflict_cols)}) DO UPDATE SET
        {", ".join(f"{c} = EXCLUDED.{c}" for c in update_cols)}
    """
    values = [tuple(row[c] for c in columns) for row in rows]
    hook = PostgresHook(postgres_conn_id=conn_id)
    with hook.get_conn() as conn, conn.cursor() as cur:
        execute_values(cur, sql, values)
        conn.commit()
    return len(values)


@dag(
    dag_id="energy_pipeline",
    schedule="@daily",
    start_date=datetime(2026, 1, 1),
    catchup=False,
    max_active_runs=1,
    default_args={"retries": 3, "retry_delay": timedelta(minutes=5)},
    tags=["eia", "enrichment", "dbt"],
)
def energy_pipeline():
    @task
    def extract_eia() -> list[dict]:
        hook = PostgresHook(postgres_conn_id=POSTGRES_CONN_ID)
        try:
            watermark = hook.get_first("SELECT max(period) FROM bronze.eia_natural_gas_imports")
        except Exception:
            watermark = None
        start = None
        if watermark and watermark[0]:
            watermark_date = datetime.strptime(watermark[0], "%Y-%m")
            start = (watermark_date - timedelta(days=OVERLAP_MONTHS * 30)).strftime("%Y-%m")
        records = eia.fetch_natural_gas_imports(start=start)
        return [r.model_dump(by_alias=False) for r in records]

    @task
    def load_eia(records: list[dict]) -> int:
        return _upsert(POSTGRES_CONN_ID, "bronze.eia_natural_gas_imports", ["series", "period"], records)

    @task
    def extract_enrichment_weather() -> list[dict]:
        return enrichment.fetch_current_weather()

    @task
    def load_enrichment_weather(records: list[dict]) -> int:
        return _upsert(POSTGRES_CONN_ID, "bronze.enrichment_weather", ["region_code", "observation_time"], records)

    loaded_eia = load_eia(extract_eia())
    loaded_weather = load_enrichment_weather(extract_enrichment_weather())

    run_dbt = BashOperator(
        task_id="run_dbt",
        bash_command="dbt build --project-dir /usr/local/airflow/dbt --profiles-dir /usr/local/airflow/dbt",
    )

    generate_report = BashOperator(
        task_id="generate_report",
        bash_command="python /usr/local/airflow/reports/generate_report.py",
    )

    [loaded_eia, loaded_weather] >> run_dbt >> generate_report


energy_pipeline()
