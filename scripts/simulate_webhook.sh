#!/bin/bash

SCRIPT_DIR="$(dirname "$0")"
PROJECT_ROOT="$(realpath "$SCRIPT_DIR/..")"
source "$PROJECT_ROOT/.venv/bin/activate"
python "$PROJECT_ROOT/main.py" &

curl -X POST "http://127.0.0.1:8000/webhook" \
  -H "Content-Type: application/json" \
  -d '{"event_type": "test_event", "message": "Hello from simulate_webhook.sh"}'