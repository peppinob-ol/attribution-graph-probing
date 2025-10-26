#!/bin/bash

# =============================================================================
# Circuit Tracer + Prompt Rover: Full Anthropological Analysis Pipeline
# =============================================================================

set -e  # Exit on error

echo ""
echo "========================================================================"
echo "ANTHROPOLOGICAL FEATURE ANALYSIS PIPELINE"
echo "========================================================================"
echo ""
echo "Starting full pipeline execution..."
echo ""

# Check if output directory exists
if [ ! -d "output" ]; then
    echo "Creating output directory..."
    mkdir -p output
fi

# Check for input file
if [ ! -f "output/gemma_sae_graph.json" ]; then
    echo "ERROR: Required input file not found: output/gemma_sae_graph.json"
    echo ""
    echo "Please generate the attribution graph using Circuit Tracer first:"
    echo ""
    echo "  from circuit_tracer import AttributionTracer"
    echo "  tracer = AttributionTracer(model='gemma-2-2b')"
    echo "  graph = tracer.trace(prompt='Your prompt', target='target_token')"
    echo "  graph.save('output/gemma_sae_graph.json')"
    echo ""
    exit 1
fi

echo "Input file found: output/gemma_sae_graph.json"
echo ""

# =============================================================================
# PHASE 1: Feature Personalities Analysis
# =============================================================================

echo "========================================================================"
echo "PHASE 1: Feature Personalities Analysis"
echo "========================================================================"
echo ""
echo "Computing metrics:"
echo "  - mean_consistency (generalizability)"
echo "  - max_affinity (specialization)"
echo "  - conditional_consistency (active patterns)"
echo "  - logit_influence (causal importance)"
echo ""

python anthropological_basic.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Phase 1 completed successfully"
    echo "  Generated: feature_personalities_corrected.json"
    echo "  Generated: feature_typology.json"
    echo "  Generated: quality_scores.json"
    echo "  Generated: metric_correlations.json"
    echo ""
else
    echo ""
    echo "✗ Phase 1 failed"
    exit 1
fi

# =============================================================================
# PHASE 2: Robust Thresholds Computation
# =============================================================================

echo "========================================================================"
echo "PHASE 2: Robust Thresholds Computation (Influence-First)"
echo "========================================================================"
echo ""
echo "Computing thresholds:"
echo "  - τ_inf (logit influence threshold)"
echo "  - τ_aff (max affinity threshold)"
echo "  - τ_cons (consistency threshold)"
echo "  - τ_inf_very_high (BOS filter threshold)"
echo ""

python compute_thresholds.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Phase 2 completed successfully"
    echo "  Generated: robust_thresholds.json"
    echo ""
else
    echo ""
    echo "✗ Phase 2 failed"
    exit 1
fi

# =============================================================================
# PHASE 3: Semantic Supernodes (Cicciotti)
# =============================================================================

echo "========================================================================"
echo "PHASE 3: Semantic Supernodes Construction (Cicciotti)"
echo "========================================================================"
echo ""
echo "Building semantic clusters with:"
echo "  - Seed selection: influence-first (logit_influence desc)"
echo "  - Growth: narrative compatibility + affinity"
echo "  - Coherence tracking"
echo ""

python cicciotti_supernodes.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Phase 3 completed successfully"
    echo "  Generated: cicciotti_supernodes.json"
    echo ""
else
    echo ""
    echo "✗ Phase 3 failed"
    exit 1
fi

# =============================================================================
# PHASE 4: Computational Clustering
# =============================================================================

echo "========================================================================"
echo "PHASE 4: Computational Clustering (Residuals)"
echo "========================================================================"
echo ""
echo "Clustering residual features with:"
echo "  - Influence-first filtering (τ_inf OR τ_aff)"
echo "  - BOS leakage control"
echo "  - Dominant token grouping"
echo ""

python final_optimized_clustering.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Phase 4 completed successfully"
    echo "  Generated: final_anthropological_optimized.json"
    echo ""
else
    echo ""
    echo "✗ Phase 4 failed"
    exit 1
fi

# =============================================================================
# PHASE 5: Validation
# =============================================================================

echo "========================================================================"
echo "PHASE 5: Logit Influence Validation"
echo "========================================================================"
echo ""
echo "Validating coverage:"
echo "  - Total logit influence coverage"
echo "  - Breakdown by feature type"
echo "  - BOS leakage check"
echo ""

python verify_logit_influence.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Phase 5 completed successfully"
    echo "  Generated: logit_influence_validation.json"
    echo ""
else
    echo ""
    echo "✗ Phase 5 failed"
    exit 1
fi

# =============================================================================
# PHASE 6: Visualizations
# =============================================================================

echo "========================================================================"
echo "PHASE 6: Visualizations and Export"
echo "========================================================================"
echo ""
echo "Generating:"
echo "  - 3D feature space plot"
echo "  - Neuronpedia export URL"
echo ""

# 3D Visualization
python visualize_feature_space_3d.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ 3D visualization generated"
    echo "  Generated: feature_space_3d.png"
    echo ""
else
    echo ""
    echo "⚠ 3D visualization failed (non-critical)"
fi

# Neuronpedia Export
python export_to_neuronpedia_improved.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Neuronpedia export generated"
    echo "  Generated: neuronpedia_url_improved.txt"
    echo "  Generated: neuronpedia_supernodes_improved.json"
    echo ""
else
    echo ""
    echo "⚠ Neuronpedia export failed (non-critical)"
fi

# =============================================================================
# PHASE 7: Analysis of Excluded Features (Optional)
# =============================================================================

echo "========================================================================"
echo "PHASE 7: Excluded Features Analysis (Optional)"
echo "========================================================================"
echo ""

python analyze_remaining_excluded.py

if [ $? -eq 0 ]; then
    echo ""
    echo "✓ Excluded features analysis completed"
    echo "  Generated: excluded_features_analysis.json"
    echo ""
else
    echo ""
    echo "⚠ Excluded features analysis failed (non-critical)"
fi

# =============================================================================
# SUMMARY
# =============================================================================

echo ""
echo "========================================================================"
echo "PIPELINE EXECUTION SUMMARY"
echo "========================================================================"
echo ""

# Check if validation file exists and extract key metrics
if [ -f "output/logit_influence_validation.json" ]; then
    echo "Key Results:"
    echo ""
    
    # Extract metrics using grep and sed (works on most systems)
    coverage=$(grep -o '"coverage_percentage": [0-9.]*' output/logit_influence_validation.json | sed 's/"coverage_percentage": //')
    rating=$(grep -o '"rating": "[A-Z]*"' output/logit_influence_validation.json | sed 's/"rating": "\(.*\)"/\1/')
    n_supernodes=$(grep -o '"n_supernodes": [0-9]*' output/logit_influence_validation.json | sed 's/"n_supernodes": //')
    n_features=$(grep -o '"n_features_covered": [0-9]*' output/logit_influence_validation.json | sed 's/"n_features_covered": //')
    
    echo "  Logit Influence Coverage: ${coverage}%"
    echo "  Coverage Rating: ${rating}"
    echo "  Total Supernodes: ${n_supernodes}"
    echo "  Features Covered: ${n_features}"
    echo ""
fi

# Check for threshold info
if [ -f "output/robust_thresholds.json" ]; then
    tau_inf=$(grep -o '"tau_inf": [0-9.]*' output/robust_thresholds.json | sed 's/"tau_inf": //')
    tau_aff=$(grep -o '"tau_aff": [0-9.]*' output/robust_thresholds.json | sed 's/"tau_aff": //')
    bos_leakage=$(grep -o '"bos_leakage_pct": [0-9.]*' output/robust_thresholds.json | sed 's/"bos_leakage_pct": //')
    
    echo "Thresholds Used:"
    echo "  τ_inf (influence): ${tau_inf}"
    echo "  τ_aff (affinity): ${tau_aff}"
    echo "  BOS leakage: ${bos_leakage}%"
    echo ""
fi

echo "Output Directory: output/"
echo ""
echo "Generated Files:"
echo "  ✓ feature_personalities_corrected.json"
echo "  ✓ feature_typology.json"
echo "  ✓ robust_thresholds.json"
echo "  ✓ cicciotti_supernodes.json"
echo "  ✓ final_anthropological_optimized.json"
echo "  ✓ logit_influence_validation.json"
echo "  ✓ feature_space_3d.png"
echo "  ✓ neuronpedia_url_improved.txt"
echo ""

echo "Next Steps:"
echo ""
echo "  1. Review results in output/ directory"
echo "  2. Open output/neuronpedia_url_improved.txt and copy URL to browser"
echo "  3. Check feature_space_3d.png for typology visualization"
echo "  4. Read logit_influence_validation.json for coverage breakdown"
echo ""

echo "========================================================================"
echo "PIPELINE COMPLETED SUCCESSFULLY!"
echo "========================================================================"
echo ""

exit 0




