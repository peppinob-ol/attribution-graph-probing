#!/usr/bin/env bash
#
# Full-scale M-search across all datasets.
#
# Runs adaptive M_amplify search on all eligible pairs (zero hits across
# all fullscale runs/variants) for each dataset, using all 8 GPUs.
#
# Datasets are processed sequentially (each uses all GPUs internally).
# Smaller datasets are processed first for fast feedback.
#
# Usage:
#   bash run_all_m_search.sh            # all datasets
#   bash run_all_m_search.sh sounds     # single dataset (prefix match)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${SCRIPT_DIR}/../../../.venv/bin/python"
GPU_IDS="0 1 2 3 4 5 6 7"

# dataset -> baseline run mapping
declare -A DATASETS
DATASETS[sounds_colors_batch]=fullscale_sounds_labeled
DATASETS[book_characters_authors_batch]=fullscale_books_labeled
DATASETS[paintings_painters_batch]=fullscale_paintings_labeled
DATASETS[products_founders_batch]=fullscale_products_labeled
DATASETS[usa_states_batch]=fullscale_usa_labeled

# Process order: smallest first for fast feedback
ORDER=(
    sounds_colors_batch
    book_characters_authors_batch
    paintings_painters_batch
    products_founders_batch
    usa_states_batch
)

FILTER="${1:-}"

echo "============================================"
echo "Full-scale M-search"
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
    echo "Baseline: ${run}"
    echo "Started: $(date)"
    echo "--------------------------------------------"

    "${PYTHON}" -u "${SCRIPT_DIR}/run_m_search.py" \
        --dataset "${ds}" \
        --baseline-run "${run}" \
        --all-runs \
        --gpu-ids ${GPU_IDS} \
        -v \
        2>&1

    echo "Finished ${ds}: $(date)"
done

echo ""
echo "============================================"
echo "All datasets complete: $(date)"
echo "============================================"
