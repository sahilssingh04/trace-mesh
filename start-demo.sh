#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")"
if [ ! -x .venv/bin/python ]; then python3.12 -m venv .venv; fi
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/bootstrap.py
.venv/bin/python scripts/seed_demo.py
.venv/bin/python -m app.worker &
worker_pid=$!
trap 'kill "$worker_pid" 2>/dev/null || true' EXIT
echo 'Open http://127.0.0.1:8000; the workspace owner key is in secrets/users.json'
.venv/bin/python -m uvicorn app.main:create_app --factory --host 127.0.0.1 --port 8000
