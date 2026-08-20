#!/usr/bin/env bash
# End-to-end API smoke test (requires Postgres; Redis optional with inline worker fallback).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

export LLM_MOCK_MODE=true
export SYNC_WORKER=true
export JWT_SECRET=test-jwt-secret
export ENCRYPTION_KEY=test-encryption-key-32-bytes!!

echo "== Running unit + integration tests =="
uv run pytest tests/ -v --tb=short "$@"

echo ""
echo "All tests passed."
