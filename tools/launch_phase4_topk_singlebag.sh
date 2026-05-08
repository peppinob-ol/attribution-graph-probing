#!/usr/bin/env bash
# Phase-4: fair Dallas top-K saturation re-run.
#
# Re-runs the top-K Dallas conditions as single-bag interventions (no
# field-additivity, no concept-field semantics) with adaptive M-search,
# isolating the target-side feature selection as the only varying
# quantity vs. the phase3v3 ours/human/shuffled markers.
#
# Layout: 4 conditions, 1 GPU each, in-process model loading. The other
# 4 GPUs (4-7) are left free.
set -u
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)
cd "$REPO"
source .venv/bin/activate
mkdir -p logs/phase4_topk_singlebag

RUN_ID=${RUN_ID:-phase4_topk_singlebag_$(date +%Y%m%d_%H%M)}
echo "[phase4-topk-singlebag] run_id=$RUN_ID"
echo "[phase4-topk-singlebag] in-process model + adaptive M-search, single bag"
echo "[phase4-topk-singlebag] launching 4 worker processes (one K per GPU)"

declare -a JOBS=(
  # gpu | K
  "0    | 10"
  "1    | 21"
  "2    | 100"
  "3    | 200"
)

for spec in "${JOBS[@]}"; do
  gpu=$(echo "$spec" | awk -F'|' '{gsub(/ /,"",$1); print $1}')
  K=$(echo "$spec" | awk -F'|' '{gsub(/ /,"",$2); print $2}')

  cfg=scripts/experiments/batch/configs/phase4_topk_${K}_dallas_singlebag.yml
  log=logs/phase4_topk_singlebag/swap_top${K}.log
  pidfile=logs/phase4_topk_singlebag/swap_top${K}.pid

  echo "[phase4-topk-singlebag]   GPU $gpu : top-${K} -> $log"
  CUDA_VISIBLE_DEVICES=$gpu nohup python -u scripts/experiments/batch/run_batch_swaps.py \
      --config "$cfg" \
      --in-process \
      --run-id "$RUN_ID" \
      > "$log" 2>&1 &
  echo "$!" > "$pidfile"
done

echo "[phase4-topk-singlebag] all 4 workers launched. PIDs:"
for pidfile in logs/phase4_topk_singlebag/swap_*.pid; do
  echo "  $(basename "$pidfile" .pid) -> $(cat "$pidfile")"
done
echo "[phase4-topk-singlebag] master exits; workers run independently."
echo "[phase4-topk-singlebag] tail logs at logs/phase4_topk_singlebag/"
