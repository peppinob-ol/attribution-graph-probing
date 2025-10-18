# Interpretation Guide

Practical guide for interpreting metrics and making decisions in the EDA app.

## 🎯 Quick Decision Trees

### "Is this feature important?"

```
START
│
├─ output_impact > 0.001? 
│  └─ YES → ✅ HIGH PRIORITY (direct causal impact)
│  └─ NO → Continue
│
├─ node_influence > 0.10?
│  └─ YES → ✅ HIGH PRIORITY (strong indirect causal)
│  └─ NO → Continue
│
├─ max_affinity > 0.75?
│  └─ YES → ✅ MEDIUM PRIORITY (strong semantic)
│  └─ NO → Continue
│
├─ mean_consistency > 0.60?
│  └─ YES → ✅ MEDIUM PRIORITY (consistent semantic)
│  └─ NO → ⚠️ LOW PRIORITY (investigate further)
```

### "Is this supernode high quality?"

```
START
│
├─ final_coherence > 0.60?
│  └─ YES → Continue
│  └─ NO → ❌ POOR QUALITY (too loose)
│
├─ edge_density > 0.20?
│  └─ YES → Continue
│  └─ NO → ⚠️ WARNING (weak causal structure)
│
├─ n_members > 5 AND n_members < 30?
│  └─ YES → ✅ GOOD SIZE
│  └─ NO → ⚠️ Too small or too large
│
└─ std_active_members < 3.0? (cross-prompt)
   └─ YES → ✅ HIGH QUALITY (robust)
   └─ NO → ⚠️ VARIABLE (prompt-dependent)
```

### "Should I adjust parameters?"

**For Phase 2 (Supernodes):**

```
Problem: Supernodes too small
Solution: 
  - Decrease threshold_normal (0.45 → 0.35)
  - Increase causal_weight (0.60 → 0.70) if graph available
  - Decrease min_coherence (0.50 → 0.40)

Problem: Supernodes too large / low coherence
Solution:
  - Increase threshold_normal (0.45 → 0.55)
  - Increase min_coherence (0.50 → 0.60)
  - Decrease tau_edge_strong (0.05 → 0.03) for stricter edges

Problem: Too few supernodes created
Solution:
  - Increase max_seeds (default 50 → 100)
  - Decrease seed selection threshold
  - Check if graph is available (causal growth needs it)
```

**For Phase 3 (Residuals):**

```
Problem: Coverage too low
Solution:
  - Decrease tau_inf (0.000194 → 0.0001)
  - Decrease tau_aff (0.65 → 0.60)
  - Decrease min_cluster_size (3 → 2)
  - Decrease jaccard_threshold (0.70 → 0.60)

Problem: Too many small clusters
Solution:
  - Increase min_cluster_size (3 → 5)
  - Decrease jaccard_threshold (0.70 → 0.60) for more merging
  - Increase layer_group_span (3 → 4) for coarser grouping

Problem: Clusters not meaningful
Solution:
  - Increase tau_inf and tau_aff (stricter admission)
  - Adjust node_inf thresholds to better separate tiers
  - Check if features are truly "computational" vs semantic
```

---

## 📊 Interpreting Specific Scenarios

### Scenario 1: High consistency, low causal influence

**Example Feature:**
- `mean_consistency`: 0.85
- `max_affinity`: 0.92
- `node_influence`: 0.002
- `output_impact`: 0.00001

**Interpretation:**
- Feature has strong, stable semantic alignment with target
- BUT minimal causal impact on output
- Likely a **semantic marker** rather than causal driver
- **Action**: Include in semantic supernodes, but don't prioritize for intervention

**Archetype**: Semantic Anchor (stable but not causal)

---

### Scenario 2: High causal influence, low consistency

**Example Feature:**
- `mean_consistency`: 0.35
- `max_affinity`: 0.48
- `node_influence`: 0.15
- `output_impact`: 0.008

**Interpretation:**
- Feature has strong causal impact on logits
- BUT weak semantic alignment with target concept
- Likely a **computational helper** (e.g., attention pattern, structural feature)
- **Action**: Include in supernodes for causal completeness, investigate mechanism

**Archetype**: Computational Helper

---

### Scenario 3: Variable consistency (high std)

**Example Feature:**
- `mean_consistency`: 0.55
- `consistency_std`: 0.45
- `conditional_consistency`: 0.72

**Interpretation:**
- Feature is **context-dependent**
- When active, it aligns well (conditional_consistency high)
- But activates in diverse contexts (high std)
- **Action**: Use `conditional_consistency` for quality assessment, investigate activation patterns

**Archetype**: Contextual Specialist

---

### Scenario 4: Supernode with declining coherence

**Example Supernode:**
- `coherence_history`: [0.85, 0.78, 0.72, 0.68, 0.55, 0.52]
- `final_coherence`: 0.52
- `n_members`: 18

**Interpretation:**
- Supernode started tight but **degraded during growth**
- Likely accepted incompatible members in later iterations
- **Action**: 
  - Check if min_coherence threshold was too low
  - Increase threshold_normal to be more selective
  - Investigate members added in last 3 iterations

**Diagnosis**: Over-grown supernode

---

### Scenario 5: Prompt-specific supernode

**Cross-Prompt Validation:**
- Prompt A: `n_active_members` = 15
- Prompt B: `n_active_members` = 14
- Prompt C: `n_active_members` = 2
- Prompt D: `n_active_members` = 1

**Interpretation:**
- Supernode is **robust on A/B** but fails on C/D
- Likely captures concept specific to A/B contexts
- **Action**:
  - Investigate what differs in prompts C/D
  - Consider if supernode is overfitted to A/B
  - Check if C/D prompts are outliers or represent important variation

**Diagnosis**: Context-dependent supernode (not necessarily bad)

---

### Scenario 6: Cluster with high Jaccard similarity

**Example Clusters:**
- Cluster A: `["L6_Dallas_HIGH", "L6_Texas_HIGH", "L7_Dallas_HIGH"]`
- Cluster B: `["L6_Dallas_HIGH", "L6_Texas_HIGH", "L6_Austin_HIGH"]`
- Jaccard(A, B) = 0.75

**Interpretation:**
- Clusters share many members (2/3 overlap)
- Likely represent **same underlying concept** with slight variation
- **Action**: Merge if jaccard_threshold ≤ 0.75

**Diagnosis**: Redundant clusters → merge recommended

---

## 🔍 Red Flags

### Feature-Level

| Red Flag | Metric Pattern | Likely Cause | Action |
|----------|----------------|--------------|--------|
| **Dead feature** | All metrics near 0 | Never activates meaningfully | Exclude (garbage) |
| **Noisy feature** | High std, low mean | Unstable, random activation | Use conditional_consistency |
| **Structural artifact** | High activation, low consistency | `<BOS>`, punctuation, etc. | Apply tau_inf_very_high filter |
| **Outlier** | One metric very high, rest low | Anomaly or edge case | Investigate manually |

### Supernode-Level

| Red Flag | Metric Pattern | Likely Cause | Action |
|----------|----------------|--------------|--------|
| **Over-grown** | coherence < 0.4, n_members > 25 | Too permissive growth | Increase thresholds |
| **Under-grown** | n_members < 5, high coherence | Too strict thresholds | Decrease thresholds |
| **Causal disconnect** | edge_density < 0.05 | Semantic-only, no causal | Check graph availability |
| **Prompt-specific** | std_active_members > 5 | Overfitted to specific prompts | Validate on more prompts |

### Cluster-Level

| Red Flag | Metric Pattern | Likely Cause | Action |
|----------|----------------|--------------|--------|
| **Singleton clusters** | Many clusters with n=2-3 | min_cluster_size too low | Increase threshold |
| **Mega-cluster** | One cluster with >50% residuals | Over-merging | Increase jaccard_threshold |
| **No causal structure** | causal_connectivity ≈ 0 | Truly computational (OK) or bad clustering | Validate cluster makes sense |

---

## 📈 Optimization Strategies

### Goal: Maximize Coverage

**Strategy:**
1. **Phase 3 first**: Lower tau_inf and tau_aff to admit more residuals
2. **Decrease min_cluster_size**: Allow smaller clusters (2-3 members)
3. **Aggressive merging**: Lower jaccard_threshold to 0.60
4. **Coarser grouping**: Increase layer_group_span to 4-5

**Trade-off**: May include lower-quality features, less interpretable clusters

**Monitor**: Quality_coverage_percentage should increase, but check that garbage_identified doesn't decrease too much

---

### Goal: Maximize Quality

**Strategy:**
1. **Stricter admission**: Increase tau_inf and tau_aff
2. **Selective growth**: Increase threshold_normal to 0.55-0.60
3. **Higher coherence**: Increase min_coherence to 0.60
4. **Conservative merging**: Increase jaccard_threshold to 0.80

**Trade-off**: Lower coverage, more features excluded

**Monitor**: Semantic_avg_coherence should increase, processable_features may increase (more residuals)

---

### Goal: Balance Coverage and Quality

**Strategy:**
1. **Two-tier approach**:
   - Strict thresholds for semantic supernodes (high quality)
   - Relaxed thresholds for computational clusters (coverage)
2. **Adaptive parameters**:
   - Phase 2: threshold_normal = 0.45, min_coherence = 0.50
   - Phase 3: tau_inf = 0.000194, min_cluster_size = 3
3. **Moderate merging**: jaccard_threshold = 0.70

**Trade-off**: Balanced, but may not excel at either extreme

**Monitor**: Both quality_coverage_percentage and semantic_avg_coherence should be acceptable

---

## 🎓 Advanced Interpretation

### Understanding Compatibility Scores

**Example Dry-Run Output:**
```
Candidate: 12_5432
  direct_edge: 0.85 (edge_weight = 0.042)
  jaccard_neighborhood: 0.40
  position_proximity: 0.80
  → causal_score: 0.65

  token_compat: 0.80 (both geographic)
  layer_proximity: 0.90 (layers 11 vs 12)
  consistency_compat: 0.75
  → semantic_score: 0.82

  TOTAL (60% causal, 40% semantic): 0.72
  Threshold: 0.45
  → ACCEPTED ✅
```

**Interpretation:**
- Strong direct edge (0.042 > tau_edge_strong=0.05? No, but still high)
- Moderate neighborhood overlap (40%)
- Very close in position (distance = 1)
- **Causal score**: 0.65 (good)
- Same token category (geographic), close layers, similar consistency
- **Semantic score**: 0.82 (excellent)
- **Combined**: 0.72 > 0.45 → accepted

**Insight**: This candidate is accepted primarily due to strong semantic compatibility, with decent causal support.

---

### Coherence Breakdown Analysis

**Example Supernode:**
```
Coherence components:
  consistency_homogeneity: 0.85 (std = 0.15)
  token_diversity: 0.60 (50% unique tokens)
  layer_span: 0.70 (span = 4.5 layers)
  causal_edge_density: 0.40

Final coherence: 0.30×0.85 + 0.20×0.60 + 0.20×0.70 + 0.30×0.40
               = 0.255 + 0.12 + 0.14 + 0.12
               = 0.635
```

**Interpretation:**
- **Strength**: Consistency homogeneity (0.85) and edge density (0.40) are excellent
- **Weakness**: Token diversity exactly at target (50%), layer span moderate
- **Overall**: 0.635 is good quality

**Action**: If we want to improve further, could:
- Tighten layer span (more selective on layer proximity)
- Ensure token diversity stays near 50% (not too homogeneous, not too diverse)

---

## 🛠️ Troubleshooting Common Issues

### Issue: "Coverage is stuck at 60%"

**Diagnosis Steps:**
1. Check `garbage_features_identified`: If high (>30% of total), many features are below thresholds
2. Check `processable_features`: If high, residuals exist but aren't clustering
3. Check cluster counts: If very few clusters, parameters too strict

**Solutions:**
- Lower tau_inf/tau_aff to admit more features
- Decrease min_cluster_size to allow smaller clusters
- Check if token classification is too aggressive (many RARE tokens)

---

### Issue: "Supernodes have low coherence (<0.5)"

**Diagnosis Steps:**
1. Check `coherence_history`: Is coherence declining during growth?
2. Check `edge_density`: Is causal structure weak?
3. Check `growth_iterations`: Are supernodes growing too much?

**Solutions:**
- Increase min_coherence to stop growth earlier
- Increase threshold_normal to be more selective
- If edge_density low, check if causal graph is available and correct

---

### Issue: "Too many small clusters (n=2-3)"

**Diagnosis Steps:**
1. Check `min_cluster_size`: Is it too low?
2. Check `jaccard_threshold`: Is merging too conservative?
3. Check residuals count: Are there enough residuals to form larger clusters?

**Solutions:**
- Increase min_cluster_size to 4-5
- Decrease jaccard_threshold to 0.60-0.65 for more aggressive merging
- If few residuals, lower admission thresholds first

---

## 📚 Further Reading

- **Metrics definitions**: `eda/METRICS_GLOSSARY.md`
- **Full methodology**: `docs/supernode_labelling/SISTEMA_LABELLING_SUPERNODI.md`
- **Code implementation**: `scripts/03_cicciotti_supernodes.py`, `scripts/04_final_optimized_clustering.py`

---

**Pro Tip**: Always compare metrics **relative to your dataset**. Absolute thresholds may vary. Use the app's interactive sliders to find optimal values for your specific data.

---

**Last Updated**: 2025-10-18  
**Version**: 1.0.0


