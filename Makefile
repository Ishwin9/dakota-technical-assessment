.PHONY: setup run test report clean

setup:
	@if [ ! -f .env ]; then \
		cp .env.example .env; \
		echo "Created .env from .env.example -- edit EIA_API_KEY before running."; \
	fi
	docker compose build

run:
	docker compose up -d
	@echo "Waiting for services to become healthy..."
	@for i in $$(seq 1 30); do \
		unhealthy=$$(docker compose ps --format '{{.Name}} {{.Health}}' | awk '$$2 != "" && $$2 != "healthy" { print }'); \
		if [ -z "$$unhealthy" ]; then echo "All services with healthchecks are healthy."; break; fi; \
		sleep 5; \
	done
	docker compose exec -T airflow-scheduler airflow dags unpause energy_pipeline
	docker compose exec -T airflow-scheduler airflow dags trigger energy_pipeline
	@echo "Triggered energy_pipeline. Watch progress at http://localhost:8080/dags/energy_pipeline"

test:
	cd api && uv run pytest ../tests/api -v
	cd ingestion && uv run pytest ../tests/ingestion -v

report:
	cd reports && uv sync --quiet && \
	DBT_POSTGRES_HOST=localhost \
	DBT_POSTGRES_PORT=$${POSTGRES_HOST_PORT:-5433} \
	DBT_POSTGRES_USER=$${POSTGRES_USER:-dakota_user} \
	DBT_POSTGRES_PASSWORD=$${POSTGRES_PASSWORD:-change_me} \
	DBT_POSTGRES_DB=$${POSTGRES_DB:-energy_analytics} \
	uv run python generate_report.py
	@echo "Report written to reports/output/energy_report.pdf"

clean:
	docker compose down -v
	find . -type d -name __pycache__ -not -path './*/.venv/*' -exec rm -rf {} +
