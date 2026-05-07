#!/usr/bin/env bash
# Phase B (v3): in-process + early-stop + 8-GPU layout.
#
# Each Python process keeps ONE ReplacementModel in RAM and handles all
# its assigned source pairs (every M-search probe reuses the cached
# model -> ~3 s/probe instead of the ~50 s/probe of the subprocess
# backend). Each process also short-circuits on the first hit per source
# (--source-stop-on-hit).
#
# Workload distribution: we have 6 conditions and 8 GPUs. Two of the
# conditions are split in half via --source-slice so that the pair of
# halves runs on its own GPU each. All 8 GPUs end up busy.
set -u
REPO=$(cd "$(dirname "${BASH_SOURCE[0]}")"/.. && pwd)
cd "$REPO"
source .venv/bin/activate
mkdir -p logs/phase3

RUN_ID=${RUN_ID:-full_50states_phase3_$(date +%Y%m%d_%H%M)}
echo "[phase3-swaps] run_id=$RUN_ID"
echo "[phase3-swaps] in-process model + early-stop on first hit per source"
echo "[phase3-swaps] launching 8 worker processes (one per GPU)"

declare -a JOBS=(
  # gpu | condition              | source-slice
  "0    | human_dallas            | 0/2"
  "1    | human_dallas            | 1/2"
  "2    | auto_dallas             | 0/2"
  "3    | auto_dallas             | 1/2"
  "4    | auto_top21_dallas       | full"
  "5    | auto_top100_dallas      | full"
  "6    | auto_top200_dallas      | full"
  "7    | shuffled_labels_dallas  | full"
)

for spec in "${JOBS[@]}"; do
  gpu=$(echo "$spec" | awk -F'|' '{gsub(/ /,"",$1); print $1}')
  cond=$(echo "$spec" | awk -F'|' '{gsub(/ /,"",$2); print $2}')
  slice=$(echo "$spec" | awk -F'|' '{gsub(/ /,"",$3); print $3}')

  cfg=scripts/experiments/batch/configs/full_swap_${cond}.yml
  if [ "$slice" = "full" ]; then
    log=logs/phase3/swap_${cond}.log
    pidfile=logs/phase3/swap_${cond}.pid
    slice_args=()
  else
    safe_slice=$(echo "$slice" | tr '/' '-')
    log=logs/phase3/swap_${cond}__slice_${safe_slice}.log
    pidfile=logs/phase3/swap_${cond}__slice_${safe_slice}.pid
    slice_args=(--source-slice "$slice")
  fi

  echo "[phase3-swaps]   GPU $gpu : ${cond} (${slice}) -> $log"
  CUDA_VISIBLE_DEVICES=$gpu nohup python -u scripts/experiments/batch/run_batch_swaps.py \
      --config "$cfg" \
      --in-process \
      --source-stop-on-hit \
      --run-id "$RUN_ID" \
      "${slice_args[@]}" \
      > "$log" 2>&1 &
  echo "$!" > "$pidfile"
done

echo "[phase3-swaps] all 8 workers launched. PIDs:"
for pidfile in logs/phase3/swap_*.pid; do
  echo "  $(basename $pidfile .pid) -> $(cat $pidfile)"
done
echo "[phase3-swaps] master exits; workers run independently."
