#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

cp -n .env.example .env 2>/dev/null || true

if ! command -v uv &>/dev/null; then
  python3 -m pip install --user uv
  export PATH="$HOME/.local/bin:$PATH"
fi

python3 -m uv sync --all-packages

cd apps/web
npm ci
