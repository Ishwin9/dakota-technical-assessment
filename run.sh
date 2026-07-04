#!/usr/bin/env bash
set -euo pipefail

log() { echo "==> $1"; }

if ! command -v docker >/dev/null 2>&1; then
    echo "docker is required but not found on PATH. Install Docker (or Colima + Homebrew's docker CLI) first." >&2
    exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
    echo "uv is required but not found on PATH. Install it: https://docs.astral.sh/uv/getting-started/installation/" >&2
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo "Docker daemon is not running. Start Docker Desktop (or 'colima start') first." >&2
    exit 1
fi

log "Setup: building images, creating .env if needed"
make setup

log "Loading EIA_API_KEY from .env"
if ! grep -q '^EIA_API_KEY=.\+' .env || grep -q '^EIA_API_KEY=your_key_here' .env; then
    echo "Warning: EIA_API_KEY in .env looks unset. Register for a free key at" >&2
    echo "https://www.eia.gov/opendata/register.php and set it in .env before continuing." >&2
fi

log "Run: starting all services and triggering the pipeline"
make run

log "Waiting for the pipeline run to finish (up to 5 minutes)"
for i in $(seq 1 60); do
    state=$(docker compose exec -T airflow-scheduler airflow dags list-runs energy_pipeline --output json 2>/dev/null \
        | python3 -c "
import json, sys
text = sys.stdin.read()
runs = json.loads(text[text.index('[{'):])
print(runs[0]['state'] if runs else 'unknown')
" 2>/dev/null || echo "unknown")
    echo "  pipeline state: $state"
    if [ "$state" = "success" ] || [ "$state" = "failed" ]; then
        break
    fi
    sleep 5
done

log "Report: generating the executive PDF report"
make report

log "Done."
echo ""
echo "Airflow UI:        http://localhost:8080/dags/energy_pipeline"
echo "Enrichment API:     http://localhost:8000/docs"
echo "Report:             reports/output/energy_report.pdf"
echo ""
echo "Run 'make test' to run the test suite, or 'make clean' to tear everything down."
