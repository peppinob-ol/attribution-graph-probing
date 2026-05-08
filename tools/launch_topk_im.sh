#!/usr/bin/env bash
# Launch the topk_influence_matched control across all available GPUs in
# in-process mode (one ReplacementModel cached per worker, ~10x faster than
# the subprocess+parallel backend on this codebase). Round-robin pair sharding
# via --source-slice keeps the matrix balanced across workers.
#
# Modeled on tools/launch_phase3_swaps.sh. Differences:
#   * the control mode is single-bag (one variant per pair), so we MUST NOT
#     pass --source-stop-on-hit (it would short-circuit target entities and
#     corrupt the per-pair budget comparison against the labeled best-of).
#   * one launcher, four domains, dispatched via $1.
#
# Usage:
#   bash tools/launch_topk_im.sh paintings|products|books|usa [--shards N]
#
# Workers are detached via nohup; the launcher exits as soon as they are up
# and prints PIDs. Logs land in logs/topk_im/. Run-id is shared across
# workers so they all write to the same run dir without colliding.
set -u

DOMAIN=${1:-}
if [ -z "$DOMAIN" ]; then
  echo "Usage: $0 <paintings|products|books|usa> [--shards N]" >&2
  exit 2
fi
shift

SHARDS=8
while [ $# -gt 0 ]; do
  case "$1" in
    --shards)
      SHARDS=${2:-8}
      shift 2
      ;;
    *)
      echo "Unknown arg: $1" >&2
      exit 2
      ;;
  esac
done

case "$DOMAIN" in
  paintings|products|books|usa) ;;
  *)
    echo "Unsupported domain: $DOMAIN (expected paintings|products|books|usa)" >&2
    exit 2
    ;;
esac

REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)
cd "$REPO"
if [ -f .venv/bin/activate ]; then
  # shellcheck disable=SC1091
  source .venv/bin/activate
fi

# The pipeline resolves inputs.source_config relative to the *cwd* (after the
# config-dir-relative attempt fails), so we cd into the configs' parent dir
# the same way the previous (working) runs were launched. We resolve the log
# directory to an absolute path beforehand so it is unaffected by the cd.
LOG_DIR_ABS="$REPO/logs/topk_im"
mkdir -p "$LOG_DIR_ABS"

BATCH_DIR="$REPO/scripts/experiments/batch"
CFG_REL="configs/topk_${DOMAIN}_influence_matched.yml"
if [ ! -f "$BATCH_DIR/$CFG_REL" ]; then
  echo "Config not found: $BATCH_DIR/$CFG_REL" >&2
  exit 2
fi
cd "$BATCH_DIR"

RUN_ID="topk_${DOMAIN}_influence_matched"

echo "[topk-im] domain=$DOMAIN shards=$SHARDS run_id=$RUN_ID"
echo "[topk-im] cwd=$BATCH_DIR config=$CFG_REL"
echo "[topk-im] launching $SHARDS in-process workers, one per GPU"

for ((i=0; i<SHARDS; i++)); do
  gpu=$i
  slice="${i}/${SHARDS}"
  safe_slice=$(echo "$slice" | tr '/' '-')
  log="$LOG_DIR_ABS/${DOMAIN}__shard_${safe_slice}.log"
  pidfile="$LOG_DIR_ABS/${DOMAIN}__shard_${safe_slice}.pid"

  echo "[topk-im]   GPU $gpu : slice $slice -> $log"
  CUDA_VISIBLE_DEVICES=$gpu PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True \
    nohup python -u run_batch_swaps.py \
      --config "$CFG_REL" \
      --run-id "$RUN_ID" \
      --in-process \
      --source-slice "$slice" \
      > "$log" 2>&1 &
  echo "$!" > "$pidfile"
done

echo "[topk-im] all $SHARDS workers launched. PIDs:"
for pidfile in "$LOG_DIR_ABS"/${DOMAIN}__shard_*.pid; do
  echo "  $(basename "$pidfile" .pid) -> $(cat "$pidfile")"
done
echo "[topk-im] master exits; workers run independently."
echo "[topk-im] tail logs with: tail -f $LOG_DIR_ABS/${DOMAIN}__shard_*.log"
