# Data Flow - Anthropological Feature Analysis Pipeline

Mappa completa delle dipendenze e del flusso dei dati tra i vari script Python.

---

## 🔄 Flow Chart Complessivo

```
INPUT: gemma_sae_graph.json (from Circuit Tracer)
   │
   ├─→ anthropological_basic.py
   │   │
   │   ├─→ feature_personalities_corrected.json ──┐
   │   ├─→ feature_typology.json ──────────────┐  │
   │   ├─→ quality_scores.json                 │  │
   │   ├─→ metric_correlations.json            │  │
   │   └─→ narrative_archetypes.json           │  │
   │                                            │  │
   │   ┌───────────────────────────────────────┘  │
   │   ↓                                           │
   │   compute_thresholds.py ←─────────────────────┘
   │   │
   │   └─→ robust_thresholds.json ──┐
   │                                 │
   │   ┌─────────────────────────────┼────────────┐
   │   ↓                             │            │
   │   cicciotti_supernodes.py ←─────┘            │
   │   │                                           │
   │   └─→ cicciotti_supernodes.json ──┐          │
   │                                    │          │
   │   ┌────────────────────────────────┼──────────┘
   │   ↓                                ↓
   │   final_optimized_clustering.py ←──┴─ robust_thresholds.json
   │   │
   │   └─→ final_anthropological_optimized.json ──┐
   │                                               │
   │   ┌───────────────────────────────────────────┘
   │   ↓
   │   verify_logit_influence.py
   │   │
   │   └─→ logit_influence_validation.json
   │
   ├─→ visualize_feature_space_3d.py
   │   │   (uses: feature_typology.json, feature_personalities_corrected.json)
   │   │
   │   └─→ feature_space_3d.png
   │
   ├─→ export_to_neuronpedia_improved.py
   │   │   (uses: final_anthropological_optimized.json, feature_personalities_corrected.json)
   │   │
   │   ├─→ neuronpedia_url_improved.txt
   │   └─→ neuronpedia_supernodes_improved.json
   │
   └─→ analyze_remaining_excluded.py
       │   (uses: final_anthropological_optimized.json, robust_thresholds.json)
       │
       └─→ excluded_features_analysis.json
```

---

## 📦 File Dependencies Matrix

| Script | Input Files | Output Files | Dependencies |
|--------|-------------|--------------|--------------|
| **anthropological_basic.py** | `gemma_sae_graph.json` | `feature_personalities_corrected.json`<br>`feature_typology.json`<br>`quality_scores.json`<br>`metric_correlations.json`<br>`narrative_archetypes.json` | None (entry point) |
| **compute_thresholds.py** | `feature_personalities_corrected.json` | `robust_thresholds.json` | `anthropological_basic.py` |
| **cicciotti_supernodes.py** | `feature_personalities_corrected.json` | `cicciotti_supernodes.json` | `anthropological_basic.py` |
| **final_optimized_clustering.py** | `cicciotti_supernodes.json`<br>`robust_thresholds.json`<br>`feature_personalities_corrected.json` | `final_anthropological_optimized.json` | `cicciotti_supernodes.py`<br>`compute_thresholds.py` |
| **verify_logit_influence.py** | `final_anthropological_optimized.json`<br>`feature_personalities_corrected.json`<br>`feature_typology.json` | `logit_influence_validation.json` | `final_optimized_clustering.py` |
| **visualize_feature_space_3d.py** | `feature_typology.json`<br>`feature_personalities_corrected.json` | `feature_space_3d.png` | `anthropological_basic.py` |
| **export_to_neuronpedia_improved.py** | `final_anthropological_optimized.json`<br>`feature_personalities_corrected.json` | `neuronpedia_url_improved.txt`<br>`neuronpedia_supernodes_improved.json` | `final_optimized_clustering.py` |
| **analyze_remaining_excluded.py** | `final_anthropological_optimized.json`<br>`robust_thresholds.json`<br>`feature_personalities_corrected.json` | `excluded_features_analysis.json` | `final_optimized_clustering.py`<br>`compute_thresholds.py` |

---

## 🎯 Execution Order (Sequential)

### Critical Path

```
1. anthropological_basic.py          (no dependencies)
   └── Generates: feature_personalities_corrected.json
                 feature_typology.json
                 
2. compute_thresholds.py             (requires: step 1)
   └── Generates: robust_thresholds.json
   
3. cicciotti_supernodes.py          (requires: step 1)
   └── Generates: cicciotti_supernodes.json
   
4. final_optimized_clustering.py    (requires: steps 2, 3)
   └── Generates: final_anthropological_optimized.json
   
5. verify_logit_influence.py        (requires: step 4)
   └── Generates: logit_influence_validation.json
```

### Parallel Execution (After Step 1)

After `anthropological_basic.py` completes, these can run in parallel:

**Branch A**:
```
anthropological_basic.py
   ├→ compute_thresholds.py
   └→ cicciotti_supernodes.py
```

**Branch B** (Independent):
```
anthropological_basic.py
   └→ visualize_feature_space_3d.py
```

Then merge for:
```
compute_thresholds.py + cicciotti_supernodes.py
   └→ final_optimized_clustering.py
```

---

## 📊 Data Format Specifications

### `feature_personalities_corrected.json`

**Format**: Dictionary of features with metrics

```json
{
  "layer_featureId": {
    "layer": int,
    "feature_id": string,
    "n_observations": int,
    "mean_consistency": float (0-1),
    "max_affinity": float (0-1),
    "conditional_consistency": float (0-1),
    "activation_threshold": float,
    "logit_influence": float (0-1),
    "consistency_std": float,
    "most_common_peak": string
  }
}
```

**Used By**: Almost all downstream scripts

---

### `feature_typology.json`

**Format**: Dictionary of feature classifications

```json
{
  "layer_featureId": {
    "type": "generalist"|"specialist"|"computational"|"hybrid",
    "mean_consistency": float,
    "max_affinity": float,
    "logit_influence": float,
    "coordinates": [float, float, float]
  }
}
```

**Used By**: `verify_logit_influence.py`, `visualize_feature_space_3d.py`

---

### `robust_thresholds.json`

**Format**: Thresholds and categorization results

```json
{
  "tau_inf": float,
  "tau_aff": float,
  "tau_cons": float,
  "tau_inf_very_high": float,
  "situational_core": {
    "n_features": int,
    "influence_coverage": float,
    "features": [...]
  },
  "generalizable_scaffold": {
    "n_features": int,
    "influence_coverage": float,
    "features": [...]
  },
  "bos_leakage_pct": float,
  "bos_leakage_ok": bool
}
```

**Used By**: `final_optimized_clustering.py`, `analyze_remaining_excluded.py`

---

### `cicciotti_supernodes.json`

**Format**: Dictionary of semantic supernodes

```json
{
  "CICCIOTTO_N": {
    "seed": "layer_featureId",
    "members": ["layer_featureId", ...],
    "narrative_theme": string,
    "seed_layer": int,
    "seed_logit_influence": float,
    "total_influence_score": float,
    "coherence_history": [float, ...],
    "final_coherence": float,
    "n_members": int
  }
}
```

**Used By**: `final_optimized_clustering.py`

---

### `final_anthropological_optimized.json`

**Format**: Merged semantic + computational supernodes

```json
{
  "strategy": "anthropological_optimized",
  "timestamp": string,
  "semantic_supernodes": {
    "CICCIOTTO_N": { ... }
  },
  "computational_supernodes": {
    "COMP_N": {
      "dominant_token": string,
      "members": [...],
      "avg_layer": float,
      "n_members": int,
      "consistency_tier": string,
      "layer_range": [int, int]
    }
  }
}
```

**Used By**: `verify_logit_influence.py`, `export_to_neuronpedia_improved.py`, `analyze_remaining_excluded.py`

---

### `logit_influence_validation.json`

**Format**: Coverage validation results

```json
{
  "total_logit_influence": float,
  "covered_influence": float,
  "coverage_percentage": float,
  "rating": "EXCELLENT"|"GOOD"|"MODERATE"|"WEAK",
  "n_supernodes": int,
  "n_features_covered": int,
  "type_breakdown": {
    "specialist": {
      "count": int,
      "influence": float,
      "pct": float
    },
    ...
  }
}
```

**Used By**: Human review, reporting

---

## 🔁 Iteration Scenarios

### Scenario 1: Adjust Thresholds Only

If you want to **re-run with different thresholds**:

```bash
# Modify thresholds in compute_thresholds.py (τ_aff, etc.)
python compute_thresholds.py
python final_optimized_clustering.py
python verify_logit_influence.py
```

**Note**: No need to re-run `anthropological_basic.py` or `cicciotti_supernodes.py`

---

### Scenario 2: New Attribution Graph

If you have a **new prompt/attribution graph**:

```bash
# Replace output/gemma_sae_graph.json
# Then run full pipeline
python anthropological_basic.py
python compute_thresholds.py
python cicciotti_supernodes.py
python final_optimized_clustering.py
python verify_logit_influence.py
```

---

### Scenario 3: Refine Supernodes Only

If you want to **change supernode parameters** (compatibility, coherence):

```bash
# Modify parameters in cicciotti_supernodes.py
python cicciotti_supernodes.py
python final_optimized_clustering.py
python verify_logit_influence.py
```

**Note**: `feature_personalities_corrected.json` is reused

---

## 📈 Data Flow by Phase

### Phase 1: Foundation (Core Metrics)

```
gemma_sae_graph.json
    ↓
[anthropological_basic.py]
    │
    ├─→ Compute mean_consistency, max_affinity, conditional_consistency
    ├─→ Classify into typology (generalist/specialist/computational/hybrid)
    ├─→ Calculate quality scores
    └─→ Compute metric correlations
    ↓
Output: feature_personalities_corrected.json (foundation for all)
```

### Phase 2: Threshold Determination (Influence-First)

```
feature_personalities_corrected.json
    ↓
[compute_thresholds.py]
    │
    ├─→ Calculate τ_inf (80% cumulative OR p90)
    ├─→ Set τ_aff = 0.60
    ├─→ Calculate τ_inf_very_high (p95) for BOS filter
    ├─→ Categorize: situational_core vs generalizable_scaffold
    └─→ Check BOS leakage
    ↓
Output: robust_thresholds.json (gates for feature admission)
```

### Phase 3: Semantic Clustering (Narrative)

```
feature_personalities_corrected.json
    ↓
[cicciotti_supernodes.py]
    │
    ├─→ Select seeds: sort by logit_influence DESC
    ├─→ Grow clusters: narrative compatibility + affinity
    ├─→ Track coherence during growth
    └─→ Stop at coherence threshold
    ↓
Output: cicciotti_supernodes.json (semantic clusters)
```

### Phase 4: Computational Clustering (Residuals)

```
cicciotti_supernodes.json + robust_thresholds.json + feature_personalities_corrected.json
    ↓
[final_optimized_clustering.py]
    │
    ├─→ Identify residuals: (logit_influence >= τ_inf) OR (max_affinity >= τ_aff)
    ├─→ Filter BOS: require logit_influence >= τ_inf_very_high
    ├─→ Cluster by dominant_token + layer_range
    └─→ Merge with semantic supernodes
    ↓
Output: final_anthropological_optimized.json (complete supernodes)
```

### Phase 5: Validation (Coverage Check)

```
final_anthropological_optimized.json + feature_personalities_corrected.json + feature_typology.json
    ↓
[verify_logit_influence.py]
    │
    ├─→ Extract all features in supernodes
    ├─→ Sum logit_influence for covered features
    ├─→ Calculate coverage: covered / total
    └─→ Breakdown by feature type
    ↓
Output: logit_influence_validation.json (validation report)
```

### Phase 6: Export & Visualization

**Branch A: 3D Visualization**
```
feature_typology.json + feature_personalities_corrected.json
    ↓
[visualize_feature_space_3d.py]
    ↓
Output: feature_space_3d.png
```

**Branch B: Neuronpedia Export**
```
final_anthropological_optimized.json + feature_personalities_corrected.json
    ↓
[export_to_neuronpedia_improved.py]
    │
    ├─→ Convert to layer_feature_pos format
    ├─→ Generate distinctive names (layer ranges)
    └─→ Build Neuronpedia URL
    ↓
Output: neuronpedia_url_improved.txt, neuronpedia_supernodes_improved.json
```

**Branch C: Excluded Analysis**
```
final_anthropological_optimized.json + robust_thresholds.json
    ↓
[analyze_remaining_excluded.py]
    │
    ├─→ Identify top excluded features by influence
    ├─→ Categorize: layer_25_boundary, bos_below_p95, etc.
    └─→ Simulate threshold relaxation impact
    ↓
Output: excluded_features_analysis.json
```

---

## 🚨 Critical Data Dependencies

### Must Have Before Running Pipeline

1. **`gemma_sae_graph.json`** (from Circuit Tracer)
   - Contains: attribution nodes, edges, activation patterns, peak tokens

### Break Points (Where Pipeline Can Resume)

1. **After `anthropological_basic.py`**:
   - Can modify threshold parameters and resume from `compute_thresholds.py`
   - Can modify supernode parameters and resume from `cicciotti_supernodes.py`

2. **After `compute_thresholds.py` + `cicciotti_supernodes.py`**:
   - Can modify clustering parameters and resume from `final_optimized_clustering.py`

3. **After `final_optimized_clustering.py`**:
   - Can run validation, visualization, export independently in parallel

---

## 💾 File Size Estimates

| File | Typical Size | Notes |
|------|--------------|-------|
| `gemma_sae_graph.json` | 50-200 MB | Depends on graph complexity |
| `feature_personalities_corrected.json` | 5-20 MB | ~1K-5K features |
| `feature_typology.json` | 2-10 MB | Same # features as personalities |
| `robust_thresholds.json` | 50-500 KB | Includes feature lists |
| `cicciotti_supernodes.json` | 500 KB - 2 MB | 10-30 supernodes |
| `final_anthropological_optimized.json` | 1-5 MB | Merged supernodes |
| `logit_influence_validation.json` | 10-50 KB | Summary statistics |
| `feature_space_3d.png` | 500 KB - 2 MB | Image file |

---

## 🔧 Maintenance Notes

### Adding New Metrics

If you add a new metric in `anthropological_basic.py`:

1. **Update `feature_personalities_corrected.json` structure**
2. **Propagate to downstream**:
   - `cicciotti_supernodes.py` (if used in compatibility)
   - `final_optimized_clustering.py` (if used in filtering)
   - `verify_logit_influence.py` (if used in validation)

### Adding New Filtering Criteria

If you add a new filtering criterion:

1. **Add to `compute_thresholds.py`** (calculate threshold)
2. **Update `robust_thresholds.json` structure**
3. **Modify `final_optimized_clustering.py`** (apply filter)
4. **Update `analyze_remaining_excluded.py`** (track excluded)

---

**Last Updated**: 2025-10-08  
**Pipeline Version**: 2.0 (Influence-First)




