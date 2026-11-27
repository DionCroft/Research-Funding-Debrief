#!/usr/bin/env bash
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$PROJECT_DIR/.venv/bin/python"
DATA_FILES=(
  "web/data/live-updates.json"
  "web/data/live-updates.xml"
)

cd "$PROJECT_DIR"

alert_on_failure() {
  local result=$?
  trap - EXIT
  if (( result != 0 )); then
    echo "Publication failed while $stage (exit $result)." >&2
    "$PYTHON" -m scripts.publication alert "$stage" "$result" ||
      echo "Could not deliver the Discord publication alert." >&2
  fi
  exit "$result"
}

stage="acquiring the refresh lock"
trap alert_on_failure EXIT
exec 9>"$PROJECT_DIR/.scheduled_debrief.lock"
flock -n -E 75 9 || {
  result=$?
  if (( result == 75 )); then
    echo "Another scheduled debrief refresh is already running; exiting."
    exit 0
  fi
  exit "$result"
}

stage="syncing main"
echo "Syncing latest main branch..."
git pull --ff-only origin main

stage="building the public snapshots"
echo "Refreshing Research Funding Debrief data..."
"$PYTHON" "$PROJECT_DIR/run.py" --refresh-live-json --send-discord

stage="committing the public snapshots"
changes=$(git status --porcelain -- "${DATA_FILES[@]}")
if [[ -n "$changes" ]]; then
  git add "${DATA_FILES[@]}"

  export GIT_AUTHOR_NAME="${GIT_AUTHOR_NAME:-Research Funding Debrief Bot}"
  export GIT_AUTHOR_EMAIL="${GIT_AUTHOR_EMAIL:-research-funding-debrief@example.invalid}"
  export GIT_COMMITTER_NAME="${GIT_COMMITTER_NAME:-Research Funding Debrief Bot}"
  export GIT_COMMITTER_EMAIL="${GIT_COMMITTER_EMAIL:-research-funding-debrief@example.invalid}"

  git commit -m "Refresh live funding data" -- "${DATA_FILES[@]}"
fi

stage="pushing the public snapshots"
echo "Publishing refreshed live data to GitHub Pages..."
git push origin HEAD:main

stage="verifying GitHub Pages"
echo "Waiting for both public snapshots to reach GitHub Pages..."
"$PYTHON" -m scripts.publication verify
echo "Published refreshed live data."
