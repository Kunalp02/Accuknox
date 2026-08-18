#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

if ! command -v uv &>/dev/null; then
  pip install uv
fi

cp -n .env.example .env 2>/dev/null || true

echo "Starting infrastructure..."
docker compose -f infra/docker-compose.yml up -d

echo "Installing Python packages..."
python3 -m uv sync --all-packages

echo "Done. Run API: python3 -m uv run --package orchestrator-api uvicorn orchestrator_api.main:app --reload --port 8000"
echo "Run worker: python3 -m uv run --package orchestrator-worker arq orchestrator_worker.tasks.WorkerSettings"
echo "Run web: cd apps/web && npm install && npm run dev"
