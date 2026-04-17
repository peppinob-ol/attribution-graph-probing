#!/usr/bin/env bash
#
# M-search on field-additivity runs across all datasets.
#
# For each dataset, runs adaptive M_amplify search on the field_add
# baseline, targeting pairs that have zero hits in ANY fullscale
# run/variant.  For each missed pair the best-scoring __add_* variant
# is selected and M-searched (coarse geometric + binary refinement).
#
# Datasets are processed sequentially (each uses all GPUs internally).
# Smaller datasets are processed first for fast feedback.
#
# Usage:
#   bash run_all_m_search_fieldadd.sh            # all datasets
#   bash run_all_m_search_fieldadd.sh sounds     # single dataset (prefix match)
#
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PYTHON="${SCRIPT_DIR}/../../../.venv/bin/python"
GPU_IDS="0 1 2 3 4 5 6 7"

# dataset -> field_add run mapping
declare -A DATASETS
DATASETS[sounds_colors_batch]=fullscale_sounds_field_add
DATASETS[book_characters_authors_batch]=fullscale_books_field_add
DATASETS[paintings_painters_batch]=fullscale_paintings_field_add
DATASETS[products_founders_batch]=fullscale_products_field_add
DATASETS[usa_states_batch]=fullscale_usa_field_add

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
echo "M-search on Field Additivity runs"
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
    echo "Baseline: ${run} (additivity)"
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
