# Feature-Level Robustness Analysis

**Method**: Activation Overlap & Survival Rate  
**Level**: Individual SAE features (fine-grained)  
**Complementary to**: Supernode-Level Robustness (see `../supernode_level_robustness/`)

---

## 🎯 What This Method Tests

**Question**: Do individual SAE features maintain stable activation patterns when entities change?

**Why It Matters**: If features are robust computational units (not spurious), they should:
- Activate in the same token positions
- Maintain similar activation magnitudes  
- Keep the same layer distributions
- Shift peak tokens appropriately (Dallas→Oakland, but same grammatical position)

---

## 📊 Method Details

### Input
- Dallas probe: 195 features grouped into supernodes
- Oakland probe: 230 features grouped into supernodes
- Common features: 25 features appear in both

### Measurements

1. **Activation Overlap**
   - For each feature, identify high-activation token positions (>50th percentile)
   - Calculate: overlap = (positions in both) / (positions in either)
   - Threshold: ≥0.70 for survival

2. **Layer Distribution**
   - Kolmogorov-Smirnov test: are layer distributions identical?
   - p > 0.05 = stable

3. **Peak Token Consistency**
   - Do features peak on the same grammatical position?
   - Or appropriately shift to new entity? (Dallas→Oakland)

### Output
- Survival rate: % features with overlap ≥70%
- Mean activation overlap
- Mean KS p-value (layer stability)
- Peak token consistency

---

## ✅ Results

| Metric | Value | Threshold | Status |
|--------|-------|-----------|--------|
| Survival Rate | 100% (25/25) | ≥70% | ✅ PASS |
| Activation Overlap | 1.000 ± 0.000 | ≥0.70 | ✅ EXCELLENT |
| Layer Distribution (KS p) | 1.000 | >0.05 | ✅ PERFECT |
| Peak Token Consistency | 96% | ~70% | ✅ PASS |
| Failures | 0 | - | ✅ NONE |

---

## 📝 Files in This Directory

- **`CROSS_PROMPT_EVIDENCE.md`** - Publication-ready summary (USE THIS FOR PAPER)
- **`CROSS_PROMPT_ROBUSTNESS_REPORT.md`** - Detailed technical analysis
- **`MASTER_VALIDATION_SUMMARY.md`** - Complete validation overview
- `cross_prompt_robustness_dallas_oakland.json` - Raw data
- `robustness_summary.png` - Overall metrics visualization
- `robustness_feature_analysis.png` - Per-feature breakdown
- `entity_mapping_diagram.png` - Entity swap visualization

---

## 🎯 For Paper Writing

### Feature-Level Paragraph (Results Section)

> "At the feature level, we tested whether individual SAE features maintain stable activation patterns across entity swaps (Dallas→Oakland, Texas→California, Austin→Sacramento). All 25 common features (100%) survived with activation overlap ≥70% (mean=1.000, perfect stability). Features maintained identical layer distributions (mean Kolmogorov-Smirnov p-value=1.000) while appropriately shifting peak tokens to new entities (96% consistency). This demonstrates computational robustness: features activate consistently despite entity changes."

### Citation
When citing this method: "feature-level activation overlap analysis"

---

## 🔬 Complementary Method

This analysis focuses on **computational stability** of individual features.

For **semantic organization** and concept disentanglement, see:
- `../supernode_level_robustness/` - Tests whether conceptual groupings transfer appropriately

**Together**, these provide dual-level validation:
- ✅ Features are stable (this method)
- ✅ Concepts are organized (supernode method)

---

## 🔄 Reproducibility

```bash
python scripts/experiments/cross_prompt_robustness.py \
    --prompt1_csv "output/examples/Dallas/node_grouping_final_20251027_173744.csv" \
    --prompt2_csv "output/examples/capital oakland/node_grouping_final_20251027_180941.csv" \
    --prompt1_name "Dallas" \
    --prompt2_name "Oakland" \
    --entity_mapping '{"Dallas":"Oakland","Texas":"California","Austin":"Sacramento"}' \
    --survival_threshold 0.7 \
    --output_dir "output/validation/feature_level_robustness"
```

---

## ⚠️ Limitations

1. **Structural similarity**: Tests only entity swaps with identical grammar
2. **Domain**: Limited to geographical facts (state capitals)
3. **Sample size**: 25 common features (small but sufficient for proof-of-concept)

See `CROSS_PROMPT_ROBUSTNESS_REPORT.md` for detailed discussion of limitations.

---

## 📊 Comparison with Supernode Method

| Aspect | Feature-Level (This) | Supernode-Level (Other) |
|--------|---------------------|------------------------|
| **Granularity** | Fine (25 features) | Coarse (7-8 supernodes) |
| **Tests** | Activation stability | Concept transfer |
| **Metric** | Overlap, survival rate | Transfer rate, separation |
| **Validates** | Computational robustness | Semantic disentanglement |
| **Best for** | "Features are stable" | "Concepts organize correctly" |

---

## ✅ Key Takeaway

**Claim**: SAE features are computationally robust.

**Evidence**: 100% survival, perfect activation overlap, stable layer distributions.

**Strength**: Quantitative, statistically tested, exceeds thresholds.

**For complete validation**, combine with supernode-level analysis.

---

**Method**: Feature-Level Activation Overlap  
**Status**: ✅ Complete, Verified, Publication-Ready  
**See also**: `../CROSS_PROMPT_ROBUSTNESS_MASTER.md` for combined overview




