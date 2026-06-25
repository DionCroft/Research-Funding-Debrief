#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="/home/cadmus/Projects/Debrief/research-funding-debrief"
DATA_FILES=(
  "web/data/live-updates.json"
  "web/data/live-updates.xml"
)

cd "$PROJECT_DIR"

exec 9>"$PROJECT_DIR/.scheduled_debrief.lock"
if ! flock -n 9; then
  echo "Another scheduled debrief refresh is already running; exiting."
  exit 0
fi

echo "Syncing latest main branch..."
git pull --ff-only origin main

echo "Refreshing Research Funding Debrief data..."
"$PROJECT_DIR/.venv/bin/python" "$PROJECT_DIR/run.py" --refresh-live-json --send-discord

if git diff --quiet -- "${DATA_FILES[@]}"; then
  echo "No live data changes to publish."
  exit 0
fi

echo "Publishing refreshed live data to GitHub Pages..."
git add "${DATA_FILES[@]}"

export GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-Research Funding Debrief Bot}"
export GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-research-funding-debrief@example.invalid}"
export GIT_COMMITTER_NAME="${GIT_COMMITTER_NAME:-Research Funding Debrief Bot}"
export GIT_COMMITTER_EMAIL="${GIT_COMMITTER_EMAIL:-research-funding-debrief@example.invalid}"

git commit -m "Refresh live funding data" -- "${DATA_FILES[@]}"
git push origin HEAD:main

echo "Published refreshed live data."
