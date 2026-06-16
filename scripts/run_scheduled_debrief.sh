#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/cadmus/Projects/Debrief/research-funding-debrief"
cd "$PROJECT_DIR"

exec "$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/run.py" --refresh-live-json --send-discord
