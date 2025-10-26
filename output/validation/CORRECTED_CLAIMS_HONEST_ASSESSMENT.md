# Corrected Claims: Honest Statistical Assessment

## Executive Summary

**Status after statistical review**: ⚠️ **Claims need significant revision**

### Issues Found
1. ✅ **Baseline comparison**: No statistical tests (only descriptive means)
2. ✅ **Cross-prompt robustness**: Selection bias (64% survival, NOT 100%)
3. ✅ **Sample size**: Only 1-2 examples (insufficient for generalization)

### Corrected Numbers
- **Baseline**: Peak consistency 0.425 vs 0.183 (needs significance test)
- **Robustness**: **64.1% survival rate** (25/39 features), NOT 100%
- **Statistical test**: p=0.0541 (marginally non-significant vs 50% chance)

---

## 1. Baseline Comparison: CORRECTED

### Original Claim (OVERSTATED)
> ❌ "Concept-aligned grouping **outperforms** geometric baselines with 132-486% improvements"

### Corrected Claim (HONEST)
> ✅ "Concept-aligned grouping shows **numerical advantages** on behavioral metrics (peak consistency: 0.425 vs 0.183), but **lacks statistical significance testing**. It achieves **lower geometric clustering quality** (silhouette: 0.124 vs 0.707), suggesting a trade-off between interpretability and cluster compactness."

### What Changed
- ❌ Removed "outperforms" (no significance tests)
- ✅ Added "numerical advantages" (descriptive only)
- ✅ Acknowledged missing statistics
- ✅ Highlighted the trade-off (loses on silhouette score)

### What's Needed
1. **Statistical tests**: t-test, Cohen's d, confidence intervals
2. **Multiple examples**: Test on ≥3 diverse circuits
3. **Honest framing**: Wins on coherence, loses on geometric quality

---

## 2. Cross-Prompt Robustness: CORRECTED

### Original Claim (SELECTION BIAS)
> ❌ "**100% survival rate** (25/25 features)"

This was **circular reasoning**:
- Tested only features ALREADY in both prompts
- Found they're in both prompts
- Claimed 100% survival

### Corrected Numbers (HONEST)

| Metric | Value | Interpretation |
|--------|-------|----------------|
| Dallas features (total) | 39 | All features to test |
| **Transferred to Oakland** | **25** | Features present in both |
| **Failed to transfer** | **14** | Prompt-specific features |
| **TRUE SURVIVAL RATE** | **64.1%** | 25/39, not 25/25 |
| Statistical test | p=0.0541 | Marginally non-significant |

### Key Insight: Failed Features Are in Late Layers
- **Transferred features**: Mean layer 6.3 (early/mid)
- **Failed features**: Mean layer 16.4 (late)
- **Interpretation**: **Early features generalize**, late features are prompt-specific

### Corrected Claim (HONEST)
> ✅ "Of 39 Dallas circuit features, **25 (64%) transferred** to the Oakland circuit with >=70% activation overlap. Transferred features are concentrated in early/mid layers (mean: 6.3) while failed features (36%) are predominantly in late layers (mean: 16.4). Transfer rate is marginally above chance (p=0.0541). Among transferred features, activation patterns are highly consistent (overlap: 1.000) with appropriate concept binding (96% peak consistency)."

### What This Means (More Interesting!)
1. ✅ **Most features generalize** (64% is good!)
2. ✅ **Layer matters**: Early features transfer, late don't
3. ✅ **Prompt-specific components exist** (36% failed)
4. ✅ **This is MORE scientifically interesting** than claiming 100%

---

## 3. Sample Size & Generalization: ACKNOWLEDGED

### Current Testing
- **Baseline**: 1 example (Michael Jordan)
- **Robustness**: 2 examples (Dallas, Oakland)
- **Prompt structure**: Identical (only entity swaps)

### What We CANNOT Claim
❌ "Features are robust to prompt variations"
❌ "Method generalizes across domains"
❌ "Supernodes are interpretable in general"

### What We CAN Claim
✅ "Preliminary results suggest..." (n=1-2)
✅ "Within structurally identical prompts..." (caveat)
✅ "Further testing needed on..." (honest limitation)

### What's Needed
1. **More examples**: ≥5 diverse circuits
2. **Paraphrases**: Different wording, same meaning
3. **Cross-domain**: Geography, science, people, math
4. **Reorderings**: Syntactic variations

---

## Recommended Publication Claims

### For Abstract
> "We introduce probe prompting for circuit interpretation. Preliminary validation (n=2 circuits) suggests concept-aligned grouping captures behavioral coherence better than geometric baselines on interpretability metrics, though at the cost of geometric clustering quality. Entity swap experiments show 64% of features transfer to structurally similar prompts, with early-layer features generalizing more than late-layer ones. Further testing on diverse prompts and paraphrases is needed."

### For Results: Baseline Comparison
> "We compared concept-aligned grouping to two geometric baselines (cosine similarity, layer adjacency) on the Michael Jordan circuit (172 features). Concept-aligned grouping achieved higher peak token consistency (0.425 vs 0.183) and activation similarity (0.762 vs 0.130), but lower silhouette scores (0.124 vs 0.707), suggesting a trade-off between behavioral coherence and geometric compactness. Statistical significance testing is needed to confirm these differences."

### For Results: Cross-Prompt Robustness
> "We tested feature generalization using entity swaps (Dallas→Oakland, Texas→California) with identical grammatical structure. Of 39 Dallas features, 25 (64%) transferred to Oakland with >=70% activation overlap (binomial test vs 50% chance: p=0.054). Transferred features concentrated in early/mid layers (mean: 6.3) while failed features (36%) were predominantly late-layer (mean: 16.4). Transferred features showed high activation consistency (overlap: 1.000) and appropriate concept shifts (96% peak consistency). However, robustness to paraphrases and structural variations remains untested."

### For Discussion: Limitations
> "Several limitations warrant discussion. First, our validation uses only 1-2 examples per claim, insufficient for broad generalization. Second, statistical significance testing was not performed on baseline comparisons; reported differences are descriptive only. Third, cross-prompt testing used structurally identical prompts (entity substitution only); robustness to paraphrases, reorderings, and cross-domain transfers is unknown. Fourth, the 64% transfer rate, while above chance, indicates a substantial subset (36%) of prompt-specific features. Future work should address these limitations through larger-scale validation, statistical testing, and diverse prompt variations."

---

## What We Learned (Positive Framing)

### This Review Made the Science BETTER

1. **64% is more interesting than 100%**
   - Shows mixture of core + prompt-specific features
   - Layer stratification is a novel finding
   - More honest = more credible

2. **Trade-offs are honest**
   - Coherence vs geometric quality
   - Interpretability vs clustering metrics
   - We chose interpretability (defensible)

3. **Limitations strengthen the paper**
   - Shows scientific rigor
   - Guides future work
   - Builds reviewer trust

---

## Action Items

### High Priority (Must Do Before Publication)

1. ✅ **Fix claims**
   - Replace "outperforms" with "numerical advantages"
   - Report 64% survival, not 100%
   - Add caveats about sample size

2. ✅ **Add limitations section**
   - No statistical tests
   - Small sample (n=1-2)
   - Structurally identical prompts only

3. ✅ **Update figures**
   - Remove "100%" from visualizations
   - Show 64% with context
   - Add confidence intervals if possible

### Medium Priority (Strongly Recommended)

4. ⚠️ **Add statistical tests**
   - t-tests for baseline comparison
   - Effect sizes (Cohen's d)
   - Confidence intervals

5. ⚠️ **Test more examples**
   - ≥3 diverse circuits
   - Different domains
   - Various structures

### Low Priority (Future Work)

6. 📊 **Paraphrase testing**
7. 📊 **Cross-domain validation**
8. 📊 **Larger sample sizes**

---

## Files Generated

### Corrected Data
- `CORRECTED_cross_prompt_robustness.json` - True 64% survival rate

### Corrected Scripts
- `fix_cross_prompt_selection_bias.py` - Tests ALL features, not just common
- `fix_baseline_comparison_stats.py` - Framework for statistical tests

### This Document
- `CORRECTED_CLAIMS_HONEST_ASSESSMENT.md` - Complete honest assessment

---

## Bottom Line

### What We Have
✅ Interesting preliminary results
✅ Novel methodology
✅ Defensible trade-offs
✅ Clear limitations

### What We Don't Have
❌ Statistical significance tests
❌ Large sample sizes
❌ Diverse prompt testing
❌ Perfect survival rates (and that's OK!)

### What to Do
**Frame honestly, publish carefully, call for future work**

The **64% result with layer stratification** is actually MORE interesting than 100%. It suggests:
- Core features (early layers) generalize
- Late-layer features are context-specific
- This is a **scientifically valuable finding**

**Honest science > overstated claims**

