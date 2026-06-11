#!/usr/bin/env bash
set -euo pipefail

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON_BIN="${PYTHON_BIN:-$PROJECT_ROOT/.venv/bin/python}"
HOST="${HOST:-127.0.0.1}"
PORT="${PORT:-8000}"

export NO_PROXY=127.0.0.1,localhost,127.0.0.0/8
export no_proxy=127.0.0.1,localhost,127.0.0.0/8

cd "$PROJECT_ROOT"
exec "$PYTHON_BIN" -m uvicorn server.main:app --host "$HOST" --port "$PORT"
