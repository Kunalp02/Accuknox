#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
uv run alembic -c alembic.ini upgrade head
