#!/bin/bash
# Example: Compare Grouping Methods with Neuronpedia Upload
#
# This script demonstrates how to compare concept-aligned grouping
# against geometric baselines (cosine similarity and layer adjacency)
# by uploading all methods to Neuronpedia and retrieving scores.
#
# Prerequisites:
# 1. Completed Step 1 (Graph Generation) and Step 3 (Node Grouping)
# 2. Have the following files ready:
#    - Node grouping CSV (output from Step 3)
#    - Graph JSON (output from Step 1)
#    - Selected nodes JSON (output from Step 1)
# 3. Neuronpedia API key

# ============================================================================
# CONFIGURATION
# ============================================================================

# Input files (update these paths with your actual files)
INPUT_CSV="output/node_grouping_final_20241106_123456.csv"
GRAPH_JSON="output/st1_graph_20241106_123456.json"
SELECTED_NODES_JSON="output/st1_feat_node_subset_20241106_123456.json"

# Neuronpedia API key (set via environment variable or replace here)
# IMPORTANT: Do not commit your API key to git!
API_KEY="${NEURONPEDIA_API_KEY}"

# Output file
OUTPUT_JSON="output/comparison_neuronpedia_$(date +%Y%m%d_%H%M%S).json"

# ============================================================================
# OPTION 1: LOCAL COMPARISON ONLY (NO UPLOAD)
# ============================================================================

echo "Option 1: Running local comparison (no Neuronpedia upload)..."
echo "This computes coherence, stability, and interpretability metrics locally."
echo ""

python scripts/experiments/compare_grouping_methods.py \
    --input_csv "$INPUT_CSV" \
    --output_json "output/comparison_local.json"

echo ""
echo "Local comparison complete. Results saved to: output/comparison_local.json"
echo ""

# ============================================================================
# OPTION 2: FULL COMPARISON WITH NEURONPEDIA UPLOAD
# ============================================================================

echo "Option 2: Running full comparison with Neuronpedia upload..."
echo "This uploads all three methods to Neuronpedia for score comparison."
echo ""

# Check if API key is set
if [ -z "$API_KEY" ]; then
    echo "ERROR: NEURONPEDIA_API_KEY environment variable not set"
    echo "Set it with: export NEURONPEDIA_API_KEY='your-api-key-here'"
    echo "Or edit this script to set API_KEY directly"
    exit 1
fi

# Upload all methods
python scripts/experiments/compare_grouping_methods.py \
    --input_csv "$INPUT_CSV" \
    --graph_json "$GRAPH_JSON" \
    --selected_nodes_json "$SELECTED_NODES_JSON" \
    --api_key "$API_KEY" \
    --upload_to_neuronpedia \
    --output_json "$OUTPUT_JSON"

echo ""
echo "Full comparison complete. Results saved to: $OUTPUT_JSON"
echo ""
echo "Next steps:"
echo "1. Open Neuronpedia: https://www.neuronpedia.org/"
echo "2. Navigate to each uploaded subgraph"
echo "3. Note the completeness and replacement scores"
echo "4. Compare scores across methods:"
echo "   - Concept-Aligned Grouping"
echo "   - Cosine Similarity Baseline"
echo "   - Layer Adjacency Baseline"
echo ""

# ============================================================================
# OPTION 3: UPLOAD SPECIFIC METHODS ONLY
# ============================================================================

echo "Option 3: Upload only specific methods..."
echo "Example: Upload only concept-aligned and cosine similarity baselines"
echo ""

python scripts/experiments/compare_grouping_methods.py \
    --input_csv "$INPUT_CSV" \
    --graph_json "$GRAPH_JSON" \
    --selected_nodes_json "$SELECTED_NODES_JSON" \
    --api_key "$API_KEY" \
    --upload_to_neuronpedia \
    --upload_concept_aligned \
    --upload_cosine \
    --output_json "output/comparison_partial.json"

echo ""
echo "Partial upload complete."
echo ""

# ============================================================================
# TIPS
# ============================================================================

echo "============================================================================"
echo "TIPS FOR BEST RESULTS"
echo "============================================================================"
echo ""
echo "1. File paths:"
echo "   - Use the final CSV from Step 3 (after naming)"
echo "   - Use the same graph JSON from Step 1"
echo "   - Include selected_nodes_json for accurate pinnedIds"
echo ""
echo "2. Neuronpedia scores:"
echo "   - Higher completeness = better behavior explanation"
echo "   - Higher replacement = more coherent functional groups"
echo "   - Concept-aligned should outperform geometric baselines"
echo ""
echo "3. Comparison metrics:"
echo "   - Coherence: semantic consistency within clusters"
echo "   - Stability: geometric quality of clustering"
echo "   - Interpretability: cluster size and balance"
echo ""
echo "4. Expected results:"
echo "   - Cosine similarity: highest activation_similarity"
echo "   - Layer adjacency: most balanced cluster sizes"
echo "   - Concept-aligned: highest peak_token_consistency and Neuronpedia scores"
echo ""
echo "============================================================================"

