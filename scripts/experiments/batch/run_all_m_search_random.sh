#!/usr/bin/env bash
#
# Adaptive M-search on the matched-random control runs across all
# datasets.
#
# For each dataset, scans the fullscale_<dom>_random run for replicate
# files (to_<tgt>__r{0,1,2}.json) that miss at the default M_amplify and
# runs the two-phase M search on each. Outputs land alongside the source
# files as to_<tgt>__r{N}__m_tuned.json. The cross-run hit filter from
# labeled is intentionally ignored: random is its own null and we want
# the M-tuned replicate distribution for every pair.
#
# Datasets are processed sequentially (each uses all GPUs internally).
# Smaller datasets are processed first for fast feedback.
#
# Usage:
#   bash run_all_m_search_random.sh            # all datasets
#   bash run_all_m_search_random.sh sounds     # single dataset (prefix match)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"
PYTHON="${REPO_ROOT}/.venv/bin/python"
SLUGS_DIR="${REPO_ROOT}/output/research"
GPU_IDS="0 1 2 3 4 5 6 7"

declare -A DATASETS
DATASETS[book_characters_authors_batch]=fullscale_books_random
DATASETS[paintings_painters_batch]=fullscale_paintings_random
DATASETS[products_founders_batch]=fullscale_products_random
DATASETS[usa_states_batch]=fullscale_usa_random

# Sounds is excluded from T2_headline so we skip it here. Order is
# smallest-first for fast feedback; USA dominates the wall-clock.
ORDER=(
    book_characters_authors_batch
    paintings_painters_batch
    products_founders_batch
    usa_states_batch
)

FILTER="${1:-}"

echo "============================================"
echo "M-search on Matched-Random control runs"
echo "GPUs: ${GPU_IDS}"
echo "Started: $(date)"
echo "============================================"

for ds in "${ORDER[@]}"; do
    if [[ -n "$FILTER" ]] && [[ "$ds" != *"$FILTER"* ]]; then
        continue
    fi
    run="${DATASETS[$ds]}"
    echo ""
    echo "--------------------------------------------"
    echo "Dataset: ${ds}"
    echo "Baseline: ${run} (random)"
    echo "Started: $(date)"
    echo "--------------------------------------------"

    slugs_file="${SLUGS_DIR}/demo_intersection_slugs_${ds}.json"
    if [[ ! -f "${slugs_file}" ]]; then
        echo "ERROR: ${slugs_file} missing; run tools/dump_demo_intersection_slugs.py first."
        exit 1
    fi

    "${PYTHON}" -u "${SCRIPT_DIR}/run_m_search.py" \
        --dataset "${ds}" \
        --baseline-run "${run}" \
        --mode random \
        --in-process \
        --restrict-slugs "${slugs_file}" \
        --gpu-ids ${GPU_IDS} \
        -v \
        2>&1

    echo "Finished ${ds}: $(date)"
done

echo ""
echo "============================================"
echo "All datasets complete: $(date)"
echo "============================================"
