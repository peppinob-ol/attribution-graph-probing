# Cross-Prompt Robustness: Scalable Validation Across 5 Domains

**Status**: Concluded
**Confidence**: High (for activation stability, feature overlap significance); Medium (for supernode consistency, cross-domain gradient)
**Date**: 2026-04-15
**Claim tested**: Section 4.7 of METHODOLOGY_REPORT.md -- "CLT features active in the attribution graph are shared structural primitives... The pipeline identifies a stable scaffold of structural features that transfer across entities."

---

## Summary

Cross-prompt robustness was validated across 1,607 entity pairs spanning all 5 domains (USA, books, products, paintings, sounds), replacing the original N=2 (Dallas/Oakland) analysis. The core findings hold: activation stability is >90% in all domains (mean 0.903--0.947), feature overlap is significantly above chance (p < 0.001 at all pool sizes tested), and early-layer overlap exceeds late-layer overlap in 4/5 domains. However, the original Dallas/Oakland pair was an outlier (~93rd percentile for USA), making the published specific numbers non-representative. The most important new finding is domain-dependent supernode consistency: USA achieves 76.6% same-supernode assignment, but books only 47.5%. Feature overlap does not predict swap success within USA (r = +0.024) but shows weak positive correlation in smaller domains (books r = +0.233, paintings r = +0.311). Confidence is high for activation stability (narrow CIs, 5 domains) and medium for the cross-domain gradient interpretation (N=5 domains, sounds anomaly).

---

## 1. Question

**Hypothesis**: CLT features selected from attribution graphs are shared structural primitives that generalize across entities filling the same syntactic slot. Specifically:
- Most features (~60-80%) should be shared between any two entities in the same domain
- Shared features should have stable activations (>90% stability)
- Early-layer features should be more shared than late-layer features
- Supernode assignments should be consistent for shared features

**Null hypothesis**: Feature overlap between entities is no greater than expected by chance (random selection from the CLT feature pool), and any observed overlap reflects prompt template structure rather than genuine shared computation.

**Confirmation**: Overlap significantly above chance, consistent across domains, with the predicted early>late gradient.

**Falsification**: Overlap near chance levels, no layer gradient, or Dallas/Oakland is a cherry-picked outlier not representative of the population.

## 2. Method

### Data scope

- Datasets: all 5 (usa_states_batch, book_characters_authors_batch, products_founders_batch, paintings_painters_batch, sounds_colors_batch)
- Entities: 103 total (50 + 21 + 14 + 12 + 6)
- Pairs: 1,607 total (1,225 + 210 + 91 + 66 + 15)
- Data source: `02 Node Grouping/node_grouping.csv` (deduplicated to unique feature_key)
- Influence: mapped through `graph.json` nodes via `selected_features_with_nodes.json`
- Swap performance: `fullscale_<domain>_labeled` runs, canonical variant

### Queries and comparisons

Built `CrossPromptComparator` class (`scripts/experiments/cross_prompt_robustness_scalable.py`) that:

1. Loads `node_grouping.csv` for two entities, deduplicates multi-probe rows to one record per `feature_key` (max `activation_max` across probes)
2. Computes set-level overlap (Jaccard, directional), per-feature activation stability, peak token agreement, supernode consistency
3. Entity-specific keyword detection: union of slug tokens and concept field values (from swap JSONs), used to classify supernodes as structural vs entity-specific
4. Per-layer overlap computed individually and in buckets (early 0-5, mid 6-14, late 15+)

Ran `run_scalable_cross_prompt.py` which:
1. Iterates all intra-domain pairs via `itertools.combinations`
2. Computes bootstrap 95% CIs (5,000 resamples)
3. Runs permutation test (2,000 draws from pools of 1k/5k/10k/50k features)
4. Correlates Jaccard overlap with vsMax, gap_closure, and hit rate from `SwapQuery.search()`

## 3. Evidence

### Aggregate results

#### Feature overlap (Jaccard) across domains

| Domain | N pairs | N entities | Jaccard mean | 95% CI | Std | Min | Max |
|--------|---------|------------|-------------|--------|-----|-----|-----|
| USA | 1,225 | 50 | 0.465 | [0.462, 0.468] | 0.059 | 0.331 | 0.995 |
| Books | 210 | 21 | 0.308 | [0.302, 0.315] | 0.046 | 0.197 | 0.507 |
| Products | 91 | 14 | 0.364 | [0.356, 0.374] | 0.044 | 0.277 | 0.569 |
| Paintings | 66 | 12 | 0.286 | [0.279, 0.292] | 0.028 | 0.230 | 0.360 |
| Sounds | 15 | 6 | 0.621 | [0.597, 0.648] | 0.051 | 0.537 | 0.736 |

#### Activation stability

| Domain | Mean | 95% CI | Std | Min | Max |
|--------|------|--------|-----|-----|-----|
| USA | 0.947 | [0.946, 0.948] | 0.018 | 0.872 | 0.981 |
| Books | 0.908 | [0.905, 0.911] | 0.020 | 0.856 | 0.983 |
| Products | 0.903 | [0.898, 0.907] | 0.022 | 0.826 | 0.951 |
| Paintings | 0.916 | [0.911, 0.921] | 0.020 | 0.854 | 0.953 |
| Sounds | 0.944 | [0.938, 0.949] | 0.011 | 0.924 | 0.960 |

#### Peak token agreement

| Domain | Same token | Same type |
|--------|-----------|-----------|
| USA | 89.0% | 96.6% |
| Books | 89.1% | 97.0% |
| Products | 93.3% | 98.8% |
| Paintings | 85.1% | 92.8% |
| Sounds | 98.2% | 99.0% |

#### Supernode consistency (shared features only)

| Domain | Same SN | Entity-regrouped | Inconsistent |
|--------|---------|-----------------|-------------|
| USA | 76.6% | 16.2% | 7.3% |
| Books | 47.5% | 12.8% | 39.7% |
| Products | 65.2% | 16.5% | 18.4% |
| Paintings | 71.0% | 9.9% | 19.1% |
| Sounds | 85.6% | 8.9% | 5.6% |

#### Layer gradient in overlap

| Domain | Early (L0-5) | Mid (L6-14) | Late (L15+) | Early/Late ratio |
|--------|-------------|-------------|-------------|-----------------|
| USA | 0.543 | 0.440 | 0.293 | 1.85x |
| Books | 0.347 | 0.340 | 0.184 | 1.89x |
| Products | 0.496 | 0.308 | 0.164 | 3.02x |
| Paintings | 0.302 | 0.311 | 0.212 | 1.43x |
| Sounds | 0.684 | 0.544 | 0.440 | 1.56x |

#### Permutation test (chance baseline)

All 5 domains: p < 0.001 at pool sizes 1k, 5k, 10k, 50k (2,000 permutations each). Observed Jaccard significantly exceeds chance at any plausible CLT feature pool size.

#### Correlation with swap performance

| Domain | N matched | r(Jaccard, vsMax) | r(Jaccard, GC) | r(Jaccard, hit) |
|--------|-----------|-------------------|----------------|-----------------|
| USA | 2,450 | +0.024 | +0.014 | -0.016 |
| Books | 210 | +0.233 | +0.004 | +0.021 |
| Products | 174 | +0.087 | -0.023 | +0.070 |
| Paintings | 124 | +0.311 | +0.089 | +0.119 |
| Sounds | 30 | -0.135 | +0.079 | 0.000 |

### Representative samples

**High overlap (USA)**: virginia_virginia_beach vs new_york_new_york_city: Jaccard=0.995 (near-identical feature sets due to token overlap in entity names). These pairs inflate the USA upper tail.

**Typical overlap (USA)**: texas_Dallas vs california_Oakland: Jaccard=0.558, directional=0.729. This is the original pair reported in Section 4.7 and sits at ~93rd percentile for USA, making it a high-end outlier, not representative.

**Low overlap (Paintings)**: American Gothic vs Water Lilies: Jaccard ~0.23 (different artistic traditions, different entity-specific features). Still well above chance.

### Edge cases and outliers

- **Books inconsistency**: 39.7% of shared features have "inconsistent" supernode assignments. Investigation suggests keyword detection limitations: literary character names and book titles are multi-word strings that may not tokenize cleanly for supernode matching (e.g., "Frodo" vs "Baggins" vs "Lord of the Rings").
- **Paintings inverted gradient**: Early overlap (0.302) is slightly lower than mid (0.311) and not much higher than late (0.212). This is the only domain where the early>late gradient is weak.
- **Sounds high overlap but 0% hit rate**: Sounds has the highest Jaccard (0.621) and 0% hit rate, confirming that feature overlap is a structural property of graphs, not a predictor of swap success. The sounds domain has known structural issues (Section 6.5).

## 4. Alternative Explanations

| Finding | Proposed explanation | Alternative explanation | How to distinguish |
|---------|---------------------|----------------------|-------------------|
| High feature overlap (0.29--0.62) | Shared structural primitives encode task template | Prompt template forces same features regardless of entity | Cross-domain comparison: if USA entity vs books entity shows near-zero overlap, the within-domain overlap is entity-template-specific, not generic |
| Activation stability >90% | Features have consistent computational roles | Ceiling effect: most activations cluster in a narrow range, making relative diffs small mechanically | Check distribution of activation_max values; if bimodal (many near zero and many near max), ceiling effect is plausible |
| Early > late layer gradient | Early layers encode task structure, late encode entity content | Feature selection bias: more features selected from early layers, inflating overlap by frequency | Check n_features per layer bucket; if early has 3x more features, the higher overlap is partly mechanical |
| Books high inconsistency (39.7%) | Entity-specific content dominates graph, supernode naming is unstable | Keyword detection fails on literary names, misclassifying genuine regrouping as inconsistency | Manual audit of 20 "inconsistent" features: are they genuinely wrong or entity-appropriate? |
| Overlap does not predict USA swap success | USA is structurally too homogeneous (narrow overlap range: 0.33--0.47 Jaccard interquartile) | Feature overlap is not the right metric; scaffold influence (Section 4.8) captures something different | Compare overlap vs scaffold as predictors; scaffold also has null signal in USA, so both metrics fail for the same reason |

## 5. Threats to Validity

- **Pipeline artifacts**: The `node_grouping.csv` uses bidirectional substring matching for concept-to-supernode assignment (Section 4, Known Confounds). This could systematically inflate the "entity-regrouped" category by matching substrings that happen to appear in entity names.
- **Metric artifacts**: Jaccard overlap is sensitive to total feature count. Domains with more features per entity (paintings: ~366, books: ~301) tend to have lower Jaccard than domains with fewer features (USA: ~234), partly because the denominator grows faster.
- **Sample size**: Sounds (N=15 pairs, 6 entities) is too small for reliable conclusions. Paintings (N=66) and products (N=91) are adequate for aggregate statistics but not for within-domain subgroup analysis.
- **Selection bias**: The original Dallas/Oakland pair was selected for the methodology report and turns out to be ~93rd percentile. This is a documented selection bias -- future reporting should use population means.
- **Confounds**: Token overlap entities in USA (6 states) may have artificially high overlap because their names share tokens with the prompt, forcing the same features to fire. The maximum Jaccard of 0.995 in USA confirms this.
- **Supernode keyword detection**: The entity-specific keyword set is constructed from slug tokens and swap JSON concept fields. This is a heuristic that may fail for entities with common-word names (e.g., "ford" in both Ford Cars and many English words).

## 6. Conclusion

### What this supports

1. **Feature overlap is genuine and substantial across all domains.** Even the lowest-overlap domain (paintings, Jaccard=0.286) is massively above chance (p < 0.001). Approximately 45-80% of features (directional overlap) are shared between any two entities in the same domain.

2. **Activation stability is a strong, generalizable finding.** All 5 domains show >90% stability, with narrow confidence intervals. Shared features activate at similar magnitudes regardless of which entity is being processed.

3. **The early>late layer gradient holds in 4/5 domains.** Early-layer features are 1.4x--3.0x more likely to be shared than late-layer features, consistent with the architectural hypothesis that early layers encode task structure and late layers encode entity-specific content.

4. **The original N=2 claims were directionally correct but quantitatively non-representative.** The Dallas/Oakland pair showed higher overlap (Jaccard 0.558) than the population mean (0.465), though all core findings (stability, gradient, significance) hold at scale.

### What this does not support

1. **Feature overlap does NOT predict within-domain swap success** (at least in USA, the most powered domain). r(Jaccard, vsMax) = +0.024. Overlap is a necessary but not sufficient condition for successful feature steering.

2. **Supernode consistency is NOT uniformly high.** The 76.6% rate in USA is reasonable, but books' 47.5% and paintings' 19.1% inconsistent rate suggest that supernode naming is domain-dependent and may require domain-specific validation.

3. **The cross-domain overlap gradient does NOT cleanly predict the hit-rate gradient.** Sounds has the highest overlap (0.621) and 0% hit rate. Excluding sounds, the ranking is: USA > Products > Books > Paintings for overlap vs USA > Products > Paintings > Books for hit rate (paintings and books are swapped).

### Remaining uncertainties

1. Whether books' high inconsistency reflects genuine supernode instability or keyword detection failure
2. Why paintings lacks the early>late gradient
3. Whether cross-domain entity comparison (USA vs books) would show near-zero overlap (negative control)
4. Whether influence-weighted overlap (which is systematically lower) is a better predictor than unweighted Jaccard

## 7. Follow-up

- [ ] Audit 20 "inconsistent" features in books to distinguish keyword failure from genuine instability
- [ ] Run cross-domain negative control (USA entity vs books entity pairs)
- [ ] Investigate paintings' layer gradient anomaly with per-entity layer distribution analysis
- [ ] Multivariate regression: overlap + error_node_pct + n_features -> vsMax for products/paintings
- [ ] Test whether influence-weighted Jaccard predicts swap success better than unweighted

---

*Generated from investigation log entry: [2026-04-15] Scalable Cross-Prompt Robustness (N=1607 pairs, 5 domains)*

*Data files: `output/research/cross_prompt_scalable/` (pairs_*.csv, aggregates.json, per_layer_curves.json, permutation_baselines.json, swap_correlations.json)*

*Scripts: `scripts/experiments/cross_prompt_robustness_scalable.py`, `scripts/experiments/run_scalable_cross_prompt.py`*
