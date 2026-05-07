#!/usr/bin/env bash
# Sleep until the Neuronpedia 60-min sliding window has refreshed, then
# relaunch the resume job. The first batch of successful graph_gen calls
# happened around 17:36 UTC, so we conservatively wait until 18:42 UTC.
#
# Re-running tools/launch_phase3_resume.sh is safe and cheap because
# force=false in the YAML skips all states whose selected_features.json
# already exists (~30 of 44). Only the ~20 missing states will hit the
# Neuronpedia API, which fits comfortably under the 30-req/hour cap.
set -u
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)
cd "$REPO"

TARGET="${RESUME_TARGET_UTC:-18:42}"
TARGET_TS=$(date -u -d "today $TARGET" +%s)
NOW_TS=$(date +%s)
DELTA=$((TARGET_TS - NOW_TS))

mkdir -p logs/phase3
WATCH_LOG=logs/phase3/_resume_window_wait.log
{
  echo "[wait] target relaunch: ${TARGET} UTC"
  echo "[wait] current:         $(date -u +%H:%M) UTC"
  echo "[wait] sleeping ${DELTA}s"
} > "$WATCH_LOG"

if [ "$DELTA" -gt 0 ]; then
  sleep "$DELTA"
fi
echo "[wait] woke up at $(date -u +%H:%M) UTC, relaunching..." >> "$WATCH_LOG"
exec bash tools/launch_phase3_resume.sh
