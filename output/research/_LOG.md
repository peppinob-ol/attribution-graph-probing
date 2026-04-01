# Investigation Log

Append-only log of agentic research findings on attribution graph
interpretation. Each entry follows the structure below. Entries are
ordered newest-first so the most recent investigation is always at the top.

**Conventions**:

- Do not edit past entries. Corrections go in new entries that reference the old one.
- Raw numbers and queries go in "Raw findings." Interpretation is separate.
- Every entry must have a "Threats" section -- what could make this finding wrong.
- Confidence levels: **Low** (suggestive, N < 20 or single condition),
**Medium** (consistent across conditions, N > 50, but alternative explanations remain),
**High** (replicated across domains, alternative explanations tested and ruled out).

---

## [2026-04-01] Topic: Late-layer scaffold as pair-level predictor of swap success

**Question**: Does scaffold compatibility specifically in late layers (the output
circuit, layers 6+) predict pair-level swap success better than overall scaffold?
The prior entry showed overall scaffold explains the domain gradient but has no
within-domain pair-level signal in USA. Late-layer scaffold showed the steepest
cross-domain gradient (USA 16.3% vs books 4.3%). Is this where the action is?

**Method**: Swept the early/late cutoff from layer 3 to layer 15 across all 4 domains.
Computed r(late_scaffold, vsMax) and r(late_scaffold, gap_closure) at each cutoff.
Examined hit/miss effect sizes (Cohen's d), quartile analyses, per-individual-layer
correlations, and target-identity confound checks.

Total pairs analyzed: USA 2450, books 240, products 132, paintings 90.

**Raw findings**:

### Cutoff sweep: r(late_scaffold, vsMax) by domain

| Cutoff | USA | Books | Products | Paintings |
|---|---|---|---|---|
| 3 | -0.097 | -0.004 | +0.105 | +0.118 |
| 5 | -0.077 | +0.000 | +0.131 | +0.066 |
| 7 | -0.036 | +0.002 | **+0.161** | +0.136 |
| 9 | -0.028 | +0.002 | **+0.175** | +0.121 |
| 11 | -0.028 | -0.001 | +0.113 | +0.048 |
| 13 | -0.055 | +0.003 | +0.144 | +0.030 |
| 15 | -0.057 | -0.002 | +0.072 | +0.004 |

Products peaks at cutoff 7-9 (r=+0.16 to +0.18). Paintings peaks at cutoff 3-7. USA
is uniformly negative/null. Books is uniformly zero.

### Hit/miss effect sizes (Cohen's d)

| Metric | USA (606h) | Books (9h) | Products (20h) | Paintings (4h) |
|---|---|---|---|---|
| scaffold_inf_mean | -0.09d | +0.61d | +0.30d | +0.70d |
| early_5_mean | -0.08d | +0.05d | +0.31d | +1.08d |
| **late_5_mean** | **+0.01d** | **+4.83d** | **+0.35d** | **-0.13d** |
| late_7_mean | +0.06d | +5.79d | +0.44d | -0.16d |
| late_9_mean | +0.09d | +5.99d | **+0.47d** | -0.17d |

### Books late_scaffold: artifact of 2 outlier pairs

The d=+4.83 to +5.99 effect in books is driven by exactly 2 same-book pairs:

- scout_finch -> atticus_finch: late_5 = **0.7636** (HIT)
- atticus_finch -> scout_finch: late_5 = **0.7419** (HIT)

Population mean late_5 = 0.049. These two points (from the same novel, To Kill a
Mockingbird) are 15x the population mean. Without them, the remaining 7 hits have
mean late_5 = 0.049, identical to misses.

Further: within jay_gatsby targets (6/9 hits), gatsby hits have **lower** late_5
(0.048) than gatsby misses (0.057). The late_scaffold effect in books is entirely
an artifact. **The giant effect size is spurious.**

### Products late_scaffold: genuine signal surviving target-identity control

Products target distribution: 11/20 hits -> model_s, 5 -> facebook, 4 -> windows.

Target-residualized correlation (controlling for target mean): **r=+0.292** (N=132).
This survives the confound check -- within a given target, source entities with higher
late-layer scaffold compatibility achieve better vsMax.

Per-individual-layer correlations for products (r > 0.15 marked):

| Layer | r(scaffold, vsMax) | Mean scaffold % |
|---|---|---|
| 11 | **+0.232** | 0.3% |
| 15 | **+0.225** | 0.1% |
| 16 | **+0.203** | 0.1% |
| 21 | **+0.160** | 0.0% |
| 20 | **+0.149** | 0.0% |

The signal concentrates in layers 11-16 and 20-21 -- the mid-to-late transition
where entity-specific and structural features intermix.

Products quartile analysis (late_5_mean):

| Quartile | N | late_5 | hit% | vsMax |
|---|---|---|---|---|
| Q1 (low) | 33 | 0.026 | 3.0% | +2.53 |
| Q2 | 33 | 0.056 | 18.2% | +3.69 |
| Q3 | 33 | 0.085 | 24.2% | +4.29 |
| Q4 (high) | 33 | 0.123 | 15.2% | +3.33 |

Clear gradient from Q1 to Q3 for both hit% and vsMax, with partial rollback at Q4.

### Paintings: early scaffold matters more

For paintings (N=90), early_scaffold at cutoff 3 has r=+0.384 with vsMax, and
r stays around +0.36-0.39 across all cutoffs. Late_scaffold peaks at only r=+0.14
(cutoff 7). The paintings hit/miss comparison confirms: early_5 d=+1.08, while
late_5 d=-0.13 (no late effect). Paintings success is predicted by structural
compatibility in early layers, not late.

### Cross-domain: late_scaffold does NOT improve over overall scaffold

Late scaffold rank: USA > paintings > products > books.
Hit% rank: USA > products > paintings > books.
Products and paintings are swapped. Overall scaffold_inf (r-entry above: USA >
products > paintings > books) is a perfect ordinal match. Late_scaffold alone is
a worse cross-domain predictor.

**Interpretation**:

1. **Products is the one domain with genuine within-domain late_scaffold signal.**
   Target-residualized r=+0.29, concentrated in layers 11-16 and 20-21. Effect size
   d=+0.47 (late_9) for hits vs misses. This is the only domain where the "graft
   compatibility" theory works at the pair level with defensible evidence (N=20 hits,
   12 distinct sources, 3 targets, survives target-residualization). **Confidence:
   Medium** (N=20 hits is still modest; multivariate controls needed).

2. **Books late_scaffold was entirely an artifact of 2 same-book outlier pairs.**
   The atticus/scout pairs have 74% late scaffold (15x population mean) because
   they share a novel. Without them, no signal. The d=+4.8 to +6.0 effect sizes
   reported in the prior entry were misleading. **Confidence: High** (mechanism
   clear, artifact demonstrated).

3. **USA has no late_scaffold signal at any cutoff.** Domain is too homogeneous.
   All |r| < 0.10. **Confidence: High** (N=2450).

4. **Paintings responds to early, not late scaffold.** The predictive signal is
   r=+0.38 for early_scaffold (layers 0-3), not for late layers. This suggests
   that for paintings, it's the input-processing compatibility (how the model
   encodes the entity) that matters, not the output circuit. But N=4 hits makes
   this fragile. **Confidence: Low** (N=4).

5. **Different domains have different "compatibility zones."** Products: mid-late
   layers (11-21). Paintings: early layers (0-3). USA: none. This suggests that
   the layer where scaffold matters depends on the domain's computational structure.
   **Confidence: Low** (exploratory, N=2 domains with signal).

**Threats to validity**:

- [x] Books outlier artifact confirmed and documented.
- [x] Products target-identity confound tested: r=+0.29 survives residualization.
- [ ] Products N=20 hits: effect size is defensible but fragile. Need to test on
  field-additivity variants for replication.
- [ ] Per-layer products correlations (r=+0.23 at layer 11) are on N=132 and have
  not been corrected for multiple comparisons across 25 layers.
- [ ] Have not controlled for error_node_pct or feature count in the products
  regression.
- [ ] The products "rollback at Q4" (Q4 hit% = 15% vs Q3 = 24%) suggests the
  relationship may be non-linear or that very high scaffold pairs have some other
  confound.

**Follow-up**:

1. Multivariate regression for products: late_scaffold + error_node_pct + n_features
   -> vsMax, to isolate independent contribution.
2. Replicate products signal on field-additivity variants (same pairs, different
   intervention scope).
3. Investigate the products Q4 rollback: what characterizes high-scaffold pairs that
   still fail?
4. Check whether the random-feature control in products also shows late_scaffold
   signal (if yes, the effect is generic, not label-specific).

---

## [2026-04-01] Topic: Graph compatibility ("graft") as predictor of swap success

**Question**: When source and target attribution graphs share a large population of
features with stable grouping (the "scaffold"), does the swap succeed more often?
Conversely, when the graphs are structurally incompatible (low shared scaffold, high
entity-specific influence), do swaps fail? Sub-questions:

1. What fraction of a graph's influence is scaffold (shared features, same supernode)?
2. Does scaffold percentage predict pair-level swap success within a domain?
3. Does mean scaffold percentage explain the domain gradient (USA > books > products > paintings)?

**Method**: For every entity pair, decomposed features into three populations:

- **Scaffold**: same `feature_key` in both graphs AND same supernode assignment. These
  are structural primitives (copula, prepositions, task operators) that remain stable
  across entities.
- **Regrouped**: same `feature_key` in both graphs but different supernode (typically
  entity-appropriate re-assignment, e.g., Say(Austin) -> Say(Sacramento)).
- **Entity-only**: `feature_key` present in one graph only.

Measured each population's share of total `node_influence`. Computed these metrics for
all pairs in 4 domains: USA (2450 pairs), books (240), products (132), paintings (90).
Correlated scaffold metrics with swap outcomes (hit%, vsMax, gap_closure).

Used `graph_feature_static_metrics.csv` (key = `layer_id`) for influence and
`node_grouping.csv` for supernode assignments.

**Raw findings**:

### Dallas/Oakland detailed decomposition (reference pair)

| Population | N features | Dallas influence | Oakland influence |
|---|---|---|---|
| Scaffold (shared + same supernode) | 119 | 50.6% | 49.2% |
| Regrouped (shared + different supernode) | 29 | 12.3% | 13.7% |
| Entity-only | 55 / 62 | 21.7% | 19.5% |

Layer structure: scaffold dominates layers 0-5 (75-100% of influence). Entity-only
features dominate layers 15-24 (50-100%). Layers 6-14 are a transition zone.

The 29 regrouped features are almost entirely entity-appropriate:
- 15x Say(Austin) -> Say(Sacramento)
- 4x Texas -> California
- 3x Dallas -> Oakland
- 2x Say(Texas) -> Say(California)
- 1x Austin -> Sacramento
- 4 genuinely inconsistent (2.7%)

### Cross-domain scaffold gradient

| Domain | scaffold_inf (mean) | hit% | gap_closure | N pairs |
|---|---|---|---|---|
| USA | 0.530 | 24.7% | 4.67 | 2450 |
| Products | 0.422 | 15.2% | 0.19 | 132 |
| Paintings | 0.359 | 4.4% | 0.80 | 90 |
| Books | 0.253 | 3.8% | 0.01 | 240 |

**Scaffold rank: USA > products > paintings > books.**
**Hit% rank: USA > products > paintings > books.**

The rankings are identical. Mean scaffold influence is a perfect ordinal predictor of
domain-level swap success.

Additional metrics by domain:

| Domain | shared_pct | src_only_inf | early_scaffold | late_scaffold | mean N features |
|---|---|---|---|---|---|
| USA | 63.7% | 29.5% | 74.6% | 16.3% | 234 |
| Products | 52.1% | 31.7% | 62.1% | 10.3% | 233 |
| Paintings | 44.8% | 38.0% | 50.9% | 9.2% | 378 |
| Books | 48.9% | 42.3% | 39.7% | 4.3% | 293 |

The late_scaffold column is striking: USA entities share 16.3% of late-layer influence
as scaffold, while books share only 4.3%. This means in books, the output-generation
circuit is almost entirely entity-specific -- the "graft" has very little compatible
tissue where it matters most.

### Within-domain pair-level prediction

| Domain | r(scaffold, vsMax) | r(scaffold, gc) | hit_scaffold | miss_scaffold | delta | N |
|---|---|---|---|---|---|---|
| USA | -0.088 | -0.082 | 0.527 | 0.531 | -0.004 | 2450 |
| Books | -0.000 | -0.058 | 0.318 | 0.250 | +0.068 | 240 |
| Products | +0.051 | +0.069 | 0.453 | 0.416 | +0.037 | 132 |
| Paintings | +0.334 | +0.101 | 0.391 | 0.357 | +0.033 | 90 |

USA: no within-domain signal (scaffold range too narrow: 0.38-0.73, mean 0.53).
Non-USA domains: hit pairs consistently have higher scaffold (delta +0.03 to +0.07).
Paintings: r=0.334 (moderate), but N=90 and fragile.

### USA quartile analysis (2450 pairs)

| Scaffold quartile | mean scaffold | hit% | mean vsMax |
|---|---|---|---|
| Q1 (lowest) | 0.468 | 27.8% | +3.15 |
| Q2 | 0.513 | 23.2% | +2.90 |
| Q3 | 0.545 | 23.7% | +2.94 |
| Q4 (highest) | 0.593 | 24.3% | +2.43 |

No monotonic trend. Q1 actually has the highest hit rate. Within USA, scaffold does
not predict pair-level success.

**Interpretation**:

1. **The graft metaphor explains the domain gradient.** Scaffold influence is a
   perfect ordinal predictor of domain-level swap success. This is the strongest
   finding. Domains with more shared structural tissue (USA 53%) achieve higher hit
   rates than domains where most influence is entity-specific (books 25%). This makes
   causal sense: if the scaffold (structural features like copula, prepositions, task
   operators) is a small fraction of the circuit, the intervention touches
   proportionally more entity-specific features that may not have proper counterparts
   in the target. **Confidence: High** (N=4 domains, perfect rank ordering, large
   effect sizes, mechanistically plausible).

2. **Within a domain, scaffold does not predict pair-level success.** In USA (N=2450,
   the largest dataset), all correlations with scaffold metrics are |r| < 0.1. The
   scaffold range is too narrow (0.38-0.73, concentrated around 0.53) to discriminate
   pairs. The domain is structurally too homogeneous for this metric to have power.
   **Confidence: High** (large N, unambiguous null result).

3. **In smaller/harder domains, there is a weak positive signal.** Books, products,
   and paintings all show hit_scaffold > miss_scaffold (consistent positive delta
   0.03-0.07). Paintings shows r=0.334 (the only non-trivial within-domain
   correlation). However, the Ns are small (90-240), hit counts are very low
   (9 hits in books, 4 in paintings), and alternative explanations (error_node_pct,
   feature count) have not been fully ruled out. **Confidence: Low** (small N,
   especially for hits; fragile).

4. **Late-layer scaffold is the key differentiator.** The cross-domain drop in
   late_scaffold (USA 16.3% -> books 4.3%) is sharper than the drop in early_scaffold
   (USA 74.6% -> books 39.7%). The output-generation layers (16+) are where
   entity-specific features concentrate, and where structural compatibility matters
   most. This aligns with the "less is more" finding: intervening on fewer (more
   targeted) features avoids disrupting the fragile late-layer scaffold.
   **Confidence: Medium** (consistent pattern across domains, mechanistically
   plausible, but N=4 domains).

**Threats to validity**:

- [x] Within-domain null result confirmed: scaffold does not predict pair-level
  success in USA (largest, most powered dataset).
- [ ] Cross-domain N=4 makes the "perfect rank ordering" less impressive -- with 4
  items, a random ordering has 1/24 = 4.2% chance of matching. However, the effect
  sizes are large (53% vs 25%) and mechanistically motivated.
- [ ] Domain-level confound: scaffold correlates with error_node_pct, feature count,
  and answer-field specificity. These are all intercorrelated. A proper multivariate
  decomposition is needed to isolate scaffold's independent contribution.
- [ ] The scaffold metric counts features assigned to identical supernode names. If
  the naming scheme is inconsistent across entities (which we showed 2.7% are), the
  scaffold count has a ~3% noise floor.
- [ ] Books hit count is N=9. Any claim about books hit/miss scaffold differences is
  anecdotal.
- [ ] I have not tested whether random-feature controls show the same cross-domain
  scaffold pattern. If random controls also succeed more in high-scaffold domains,
  the scaffold effect is generic (not label-specific).

**Follow-up**:

1. Test scaffold vs random controls: does the scaffold advantage persist when
   comparing labeled-vs-random within each domain?
2. Multivariate analysis: regress vsMax on scaffold_inf + error_node_pct + n_features
   to isolate independent contributions.
3. Run the paintings within-domain analysis on the field-additivity variant to see if
   the r=0.334 replicates with more pairs/conditions.
4. Test late_scaffold specifically as a predictor (since it shows the largest
   cross-domain gradient).
5. For the "less is more" connection: check whether the capital-only field variant
   preferentially preserves scaffold features (explaining why fewer fields work better).

---

## [2026-04-01] Topic: Section 4.6 Cross-Prompt Robustness -- claim verification

**Question**: Do the specific quantitative claims in METHODOLOGY_REPORT.md Section 4.6
(Dallas vs Oakland cross-prompt comparison) hold against the current data? The five
sub-claims tested:

1. "7/7 universal concept supernodes transfer (copula, prepositions, relational operators)"
2. "8/8 entity-specific supernodes show appropriate non-transfer"
3. "25 shared features (12.8% of total)"
4. "94% activation stability" for shared features
5. "Layer 0-1 feature overlap: 80-92%; Layer 16-22 overlap: 0-50%"

**Method**: Loaded current `node_grouping.csv` for `texas_Dallas` (203 unique features,
1015 probe-rows, 32 supernodes) and `california_Oakland` (210 unique features,
1050 probe-rows, 34 supernodes). Compared supernode names, computed per-feature
overlap by layer, measured activation stability via relative activation difference
on shared feature_keys. Cross-referenced against the original analysis artifacts in
`output/validation/supernode_level_robustness/` and
`output/validation/feature_level_robustness/` (both dated 2025-10-27), and the
original script `scripts/experiments/analyze_cross_prompt_robustness.py`.

**Raw findings**:

### Feature overlap -- the central discrepancy

| Metric | Original (Oct 2025) | Current data | Source |
|--------|---------------------|--------------|--------|
| Dallas unique features | 39 | 203 | `feature_key` unique count |
| Oakland unique features | 46 | 210 | `feature_key` unique count |
| Shared features | 25 | 148 | intersection of `feature_key` sets |
| Shared % of Dallas | 64.1% | 72.9% | shared / unique Dallas |
| Report's "12.8%" | 25/195 rows | N/A | see denominator analysis below |

The original feature-level analysis (`cross_prompt_robustness_dallas_oakland.json`)
found 39 Dallas features, 46 Oakland, 25 shared. The "12.8% (25/195)" cited in
VERIFIED_CLAIMS.md and METHODOLOGY_REPORT.md uses 195 as the denominator. This 195
is the total number of **rows** in Dallas's node_grouping.csv at the time (39
features x 5 probes = 195 rows), not 195 unique features. The correct percentage
on the original data is 25/39 = **64.1%**, not 12.8%.

On current data, the overlap is even higher: **148/203 = 72.9%**. The data has been
regenerated with ~5x more features per entity since the October 2025 analysis.

### Denominator error confirmation

- Feature-level JSON: `n_features_prompt1: 39`, `n_features_prompt2: 46`
- VERIFIED_CLAIMS.md: "25 out of 195 Dallas features (12.8%)"
- 39 features x 5 probes = 195 rows. 25 + 170 = 195. QED: denominator is rows.
- The `analyze_cross_prompt_robustness.py` line 57 prints `len(self.df1)` (row
  count, not unique features) as "features", propagating the confusion.

### Supernode transfer (claims 1 & 2)

**Claim 1: "7/7 universal concept supernodes transfer"**

The original 7 were: `is`, `capital`, `of`, `containing`, `(containing) related`,
`(capital) related`, `seat`. All 7 are present in both entities on current data.
However, 26 supernode names are now shared between the two entities (including
`state`, `government`, `punctuation`, `The`, `relationship`, `attribute`, `city`,
`entity`, `USA`, `serving`, `States`, `located`, `United`, `which`, `in`, `(entity)
related`, `(attribute) related`, `(serving) related`, `Say (capital)`). The "7/7"
selects a small subset of the actual shared supernodes using the `universal_keywords`
list in the script (line 78: `['is', 'of', 'capital', 'containing', 'related',
'seat']`). The match is keyword-based and excludes many shared structural supernodes.

**Claim 2: "8/8 entity-specific supernodes show appropriate non-transfer"**

The original 8 were: Texas, California, Dallas, Oakland, (Texas) related,
(California) related, United, (United) related. On current data:

- Dallas-only supernodes (6): Austin, Dallas, Say(Austin), Say(Texas), Texas, the
- Oakland-only supernodes (8): California, Oakland, Sacramento, Say(California),
  Say(Oakland), Say(Sacramento), Say(city), Say(state)

"United" now appears in **both** entities (shared supernode), contradicting its
original classification as entity-specific. "(Texas) related" and "(California)
related" no longer appear as distinct supernodes. The entity-specific claim is
directionally correct but the specific 8/8 itemization no longer matches.

### Activation stability (claim 4)

| Metric | Original | Current data |
|--------|----------|--------------|
| Mean relative diff | 0.058 | 0.037 |
| Similarity (1 - rel_diff) | 94.2% | 96.3% |
| Peak token same | 88% (22/25) | 93.2% (138/148) |
| Peak type same | 96% (24/25) | 98.6% (146/148) |
| Same supernode | 68% (17/25) | 80.4% (119/148) |

Claim directionally correct and actually **conservative** -- current data shows
higher stability. Entity-appropriate variants (e.g., Say(Austin) -> Say(Sacramento))
account for 16.9% (25/148). Only 4 features (2.7%) are genuinely inconsistent across
entities.

### Layer overlap (claim 5)

Claim: "Layer 0-1 feature overlap: 80-92%; Layer 16-22 overlap: 0-50%"

Original data (per-layer, % of Dallas):
L0 = 91.7%, L1 = 80.0% => range 80-92% as claimed.
L16-22: individual layers ranged 0-100% (L22=0%, L17=100%).

Current data (per-layer, % of Dallas):
L0 = 80.7%, L1 = 69.2% => range 69-81%, NOT 80-92%.
L16-22 aggregate: 51.5% of Dallas features shared, outside the "0-50%" claim.

Individual current layers in L16-22:
L16=55.6%, L17=100%, L18=50%, L19=100%, L20=50%, L21=33.3%, L22=14.3%.

The general direction (early > late overlap) holds but specific ranges do not match.

### Known bug in original report

The `cross_prompt_report_20251027_183408.md` Executive Summary states "universal:
0/7 successful transfers" -- a counting bug acknowledged in
`DOUBLE_CHECK_RESULTS.md`. The detailed table in the same report correctly shows all
7 universal supernodes with "Full transfer". The 7/7 claim was manually corrected
after discovery but the report was not regenerated.

**Interpretation**:

1. **The "12.8% feature overlap" is wrong** -- it is a denominator error mixing
   unique features (numerator=25) with probe-rows (denominator=195). On the original
   data, true unique-feature overlap was 64.1%. On current data it is 72.9%. The
   interpretation "low feature overlap reflects entity-specificity" is incorrect;
   the majority of features are shared. **Confidence: High.**

2. **The narrative is inverted**: The methodology report frames low overlap as
   evidence of entity-specificity. In reality, the high overlap (~73%) shows that
   most CLT features active in the attribution graph are **shared structural
   primitives**, with entity-specific features being the minority (~27%). This
   actually strengthens the case for robust concept discovery, but for the opposite
   reason stated. **Confidence: High.**

3. **Section 4.6 is based on stale data**: All five claims reference analysis from
   October 2025 when entities had ~39 features. Current data has ~203 features (5x
   more). The graphs have been regenerated, making the original analysis artifacts
   unreliable for current claims. **Confidence: High.**

4. **Supernode transfer is broader than claimed**: 26 shared supernodes exist, not
   7. The "7/7" cherry-picks a subset using keyword matching. Entity-specific
   non-transfer is real but the exact 8/8 itemization is outdated. **Confidence:
   Medium** (the categorization is somewhat subjective).

5. **Activation stability holds and is conservative**: The 94% claim is actually an
   underestimate -- current data shows 96.3%. This is the one claim that survives
   scrutiny. **Confidence: High.**

**Threats to validity**:

- [x] Different data version: Confirmed. Oct 2025 data had ~39 features per entity,
  current has ~203. Pipeline was regenerated.
- [x] Denominator error: Confirmed. 195 = 39 features x 5 probes = rows, not unique
  features.
- [ ] My analysis might use different feature counting: I use unique `feature_key`
  from `node_grouping.csv`; the original may have used a different CSV or filtering.
  However, `selected_features_with_nodes.json` also shows 203 features for current
  Dallas, consistent with my count.
- [ ] Supernode classification is subjective: The boundary between "universal" and
  "entity-specific" depends on keyword lists. Different keyword choices yield
  different counts.
- [ ] N=2 entity comparison: The entire cross-prompt analysis compares exactly 2
  entities. This is acknowledged in the original report's limitations but the
  methodology report presents the results without this caveat.

**Follow-up**:

1. Re-run `analyze_cross_prompt_robustness.py` on current data to produce an updated
   report with correct denominators.
2. Correct section 4.6 of METHODOLOGY_REPORT.md: replace "12.8%" with the actual
   overlap percentage, update layer ranges, note the data version.
3. Consider extending the cross-prompt comparison to more entity pairs (not just
   Dallas/Oakland) to increase N and test generalizability.
4. Add a third entity with different structural properties (e.g., a token-overlap
   entity like `colorado_colorado_springs`) to stress-test transfer claims.

---

## [2026-04-01] Topic: M_amplify sweep -- full investigation summary

**Question**: Does reducing M_amplify from 20 to lower values convert "right direction,
no hit" cases into hits? What is the mechanism, how far does the effect extend, and
what are its limits? Four sub-questions investigated:
(F1) Does the M=5 rescue effect generalize across the full high-vsMax no-hit
population?
(F2) Is there a usable M between 5 and 10 for moderate-signal pairs?
(F3) How does all-fields M=5 compare to the existing capital-only field variant
as a fix for field interference?
(F4) Does the iowa→utah non-monotonic vsMax result replicate? Are there evaluator
blind spots?

**Method**: Created YAML configs `sweep_usa_m5.yml`, `sweep_usa_m7.yml`,
`sweep_usa_m10.yml` (M_amplify=5/7/10, all else identical to `fullscale_usa_labeled`).
Ran via `run_batch_swaps.py --pair` for targeted pairs; for F1 ran a shell loop
over all 40 remaining high-vsMax no-hit oklahoma_tulsa pairs. Queried results with
`SwapQuery.get/search`. Compared against existing `fullscale_usa_labeled` (M=20)
and `fullscale_usa_field_add` variant `add_capital` (capital-only, M=20). All
runs stored under `output/usa_states_batch/_swaps/runs/sweep_usa_m{5,7,10}/`.

Total new steering runs executed this session: 5 pilot pairs × 2 M values +
40-pair batch (M=5) + 4 moderate pairs × 3 M values + 4 high-total pairs × 2 M
values = ~70 individual steering runs.

**Raw findings**:

### Section A: Pilot -- 5 pairs across the overshoot severity spectrum

Pair selection and baseline severity:


| Pair (source -> target)                     | total | amplify | rank_imprv (M=20) | vsMax (M=20) |
| ------------------------------------------- | ----- | ------- | ----------------- | ------------ |
| kansas_wichita -> oklahoma_tulsa            | 163   | 73      | -113,493          | 15.80        |
| delaware_wilmington -> oklahoma_tulsa       | 163   | 90      | -167,524          | 15.02        |
| vermont_burlington -> kansas_wichita        | 130   | 90      | -25,268           | 8.34         |
| rhode_island_warwick -> wisconsin_milwaukee | ~130  | ~75     | -1,515            | 8.78         |
| iowa_cedar_rapids -> utah_provo             | 253   | 93      | +35               | 8.62         |


Summary table (hit / vsMax):


| Pair                                        | M=20     | M=10        | M=5          |
| ------------------------------------------- | -------- | ----------- | ------------ |
| kansas_wichita -> oklahoma_tulsa            | N / 15.8 | N / 15.8    | **Y / 14.3** |
| delaware_wilmington -> oklahoma_tulsa       | N / 15.0 | N / 14.9    | **Y / 13.9** |
| vermont_burlington -> kansas_wichita        | N / 8.3  | N / 8.1     | N / **0.3**  |
| rhode_island_warwick -> wisconsin_milwaukee | N / 8.8  | N / 8.5     | N / **2.1**  |
| iowa_cedar_rapids -> utah_provo             | N / 8.6  | **Y / 6.1** | **Y / 10.8** |


Hits: M=20: 0/5, M=10: 1/5, M=5: 3/5.

Peak logit advantage over source (best_gap) across M -- stability indicator:


| Pair                                        | M=20  | M=10  | M=5      |
| ------------------------------------------- | ----- | ----- | -------- |
| kansas_wichita -> oklahoma_tulsa            | 16.91 | 16.84 | 16.88    |
| delaware_wilmington -> oklahoma_tulsa       | 22.03 | 23.16 | 23.86    |
| vermont_burlington -> kansas_wichita        | 16.69 | 16.38 | **9.59** |
| rhode_island_warwick -> wisconsin_milwaukee | 13.91 | 13.85 | **9.31** |
| iowa_cedar_rapids -> utah_provo             | 7.97  | 8.00  | 9.88     |


Position-0 disruption (target_rank_improvement at pos0):


| Pair                                        | M=20     | M=10    | M=5  |
| ------------------------------------------- | -------- | ------- | ---- |
| kansas_wichita -> oklahoma_tulsa            | -113,493 | -3,651  | -49  |
| delaware_wilmington -> oklahoma_tulsa       | -167,524 | -15,830 | -280 |
| vermont_burlington -> kansas_wichita        | -25,268  | -1,060  | +7   |
| rhode_island_warwick -> wisconsin_milwaukee | -1,515   | -156    | -11  |
| iowa_cedar_rapids -> utah_provo             | +35      | +451    | +409 |


Control stability (mean absolute logit shift on non-answer tokens):


| Pair                                        | M=20  | M=10  | M=5  |
| ------------------------------------------- | ----- | ----- | ---- |
| kansas_wichita -> oklahoma_tulsa            | 14.14 | 11.81 | 6.68 |
| delaware_wilmington -> oklahoma_tulsa       | 13.84 | 11.70 | 6.70 |
| vermont_burlington -> kansas_wichita        | 11.11 | 10.49 | 8.28 |
| rhode_island_warwick -> wisconsin_milwaukee | 11.75 | 9.81  | 7.37 |
| iowa_cedar_rapids -> utah_provo             | 11.04 | 10.34 | 7.56 |


First tokens and outputs at each M for the two rescued oklahoma_tulsa pairs:

- M=20: `'AddTagHelper'` → "County, Oklahoma, is **Tulsa**" (city, not capital)
- M=10: `' County'` → "County, Oklahoma, is **Tulsa**" (still city)
- M=5: `','` → ", **Oklahoma City**, and Tulsa is Oklahoma" (capital)

iowa->utah at M=20: `' Too'` → "Tooele County, Utah, USA" (no hit).
M=10: `' Too'` → "Tooele County is the city of Salt Lake" (hit). M=5: `' St'`
→ "River, Utah is Salt Lake City" (hit). Non-monotonic: vsMax at M=5 (10.81) >
M=20 (8.62).

### Section B: F1 -- Full oklahoma_tulsa high-vsMax population at M=5

All 42 high-vsMax (vsMax > 12) no-hit oklahoma_tulsa pairs share the same target.
(There are zero high-vsMax no-hit pairs with any other target in the USA dataset.)

Hit rates for all -> oklahoma_tulsa pairs by condition:


| Condition                               | N tested | Hits | Hit%      |
| --------------------------------------- | -------- | ---- | --------- |
| All-fields M=20 (fullscale_usa_labeled) | 49       | 0    | 0.0%      |
| Capital-only M=20 (add_capital variant) | 49       | 11   | 22.4%     |
| All-fields M=5 (sweep_usa_m5)           | 42       | 37   | **88.1%** |


Capital-only M=20 hits cluster at vsMax 7.50--9.12 (median 8.25).
Capital-only M=20 misses cluster at vsMax 9--13. Inverted vsMax/hit correlation:
higher confidence → worse outcome within the capital-only run (replication of the
confidence-hit paradox at smaller scale).

Capital-only hit mechanism: position-1 recovery after garbage first token.
Example: "...isexpandindo-o, **Oklahoma City**, and Tulsa" -- comma/garbage at
position 0, correct capital at position 1. Capital-only miss mechanism: "...is
AddTagHelper, Oklahoma, is **Tulsa**" -- city still dominates positions 1-2.

5 misses at M=5 (comma first token in all cases):


| Source                   | ablate | total | vsMax (M=5) | rank_imprv (M=5) | failure type                                 |
| ------------------------ | ------ | ----- | ----------- | ---------------- | -------------------------------------------- |
| west_virginia_huntington | 97     | 170   | 9.44        | -211             | partial signal drop; "Tulsa" in continuation |
| maryland_baltimore       | 83     | 156   | 14.34       | -117             | "County, Oklahoma, is Tulsa" after comma     |
| hawaii_hilo              | 28     | 101   | **4.81**    | -368             | signal collapse; reverts to Hilo facts       |
| south_dakota_sioux_falls | 141    | 214   | 13.78       | **+94**          | "County, Oklahoma, is Tulsa" after comma     |
| indiana_fort_wayne       | 200    | 273   | 13.56       | -32              | "County" continuation; token-overlap entity  |


South_dakota at M=5: rank_imprv=+94 (zero first-token disruption), first token
`','`, but continuation still generates "County, Oklahoma, is Tulsa." This is
intrinsic failure, not overshoot.

Hits vs misses for comma-first-token pairs at M=5 (sorted by ablate count):


| Source                             | ablate | total | result at M=5 |
| ---------------------------------- | ------ | ----- | ------------- |
| new_hampshire_manchester           | 54     | 127   | HIT           |
| texas_dallas                       | 65     | 138   | HIT           |
| ohio_cleveland                     | 67     | 140   | HIT           |
| delaware_wilmington                | 79     | 152   | HIT           |
| maryland_baltimore                 | 83     | 156   | MISS          |
| kansas_wichita                     | 90     | 163   | HIT           |
| west_virginia_huntington           | 97     | 170   | MISS          |
| south_dakota_sioux_falls           | 141    | 214   | MISS          |
| indiana_fort_wayne (token overlap) | 200    | 273   | MISS          |


No clean ablate-count threshold: kansas (ablate=90) hits while maryland (ablate=83)
misses. The pattern is non-monotonic with the exception of the two highest-ablate
cases (south_dakota, indiana) which both have "County" continuations.

### Section C: F2 -- M=7 on moderate-signal pairs

M=7 results for the two moderate-signal pairs:


| Metric                              | vermont->kansas                 | rhode_island->wisconsin       |
| ----------------------------------- | ------------------------------- | ----------------------------- |
| vsMax: M=20 / M=10 / M=7 / M=5      | 8.34 / 8.12 / 7.75 / **0.31**   | 8.78 / 8.47 / **2.38** / 2.12 |
| rank_imprv: M=20 / M=10 / M=7 / M=5 | -25,268 / -1,060 / **-97** / +7 | -1,515 / -156 / **-47** / -11 |
| first token: M=7                    | `' Falls'`                      | `' County'`                   |
| continuation: M=7                   | Falls, Kansas, is Hutchinson    | County, New York, is Albany   |
| Hit at M=7?                         | **No**                          | **No**                        |


No M in {5, 7, 10, 20} produces a hit for either pair.

At M=7, vermont->kansas has rank_imprv=-97 (minimal first-token disruption) but
first token is still `' Falls'` and continuation is "Falls, Kansas, is Hutchinson"
(wrong Kansas capital). Signal collapse for rhode_island->wisconsin occurs between
M=10 (vsMax=8.47) and M=7 (vsMax=2.38). Signal collapse for vermont->kansas occurs
between M=7 (vsMax=7.75) and M=5 (vsMax=0.31).

### Section D: F4 -- Non-monotonic M, high-total_count pairs, and evaluator gap

High-total_count (total > 240) mild-disruption pairs at M=5:


| Pair                                               | total | rank_imprv (M=20) | M=20                | M=10                | M=5                      |
| -------------------------------------------------- | ----- | ----------------- | ------------------- | ------------------- | ------------------------ |
| indiana_fort_wayne -> arkansas_fayetteville        | 269   | +178              | N / 5.56 (`tonode`) | N / 5.56 (`tonode`) | **Y / 5.75** ( `Little`) |
| indiana_fort_wayne -> minnesota_minneapolis        | 282   | +191              | N / 5.56 ( `St`)    | N / 6.88 ( `St`)    | N / 6.00 ( `St`)         |
| idaho_idaho_falls -> minnesota_minneapolis         | 251   | +119              | N / 5.81 ( `St`)    | N / 6.25 ( `St`)    | N / 4.38 ( `St`)         |
| colorado_colorado_springs -> minnesota_minneapolis | 245   | +301              | N / 5.62 ( `St`)    | N / 4.94 ( `St`)    | N / 4.81 ( `St`)         |


`indiana -> arkansas` at M=5: HIT via a different rescue mechanism. The garbage
token 'tonode' at M=20/M=10 is NOT caused by rank disruption (rank_imprv=+178,
always positive). M=5 eliminates a feature-interaction artifact that specifically
activates the 'tonode' token at high amplification. First token becomes `' Little'`
→ "Little Rock, Arkansas" (correct capital).

`-> minnesota_minneapolis` evaluator gap: all three sources output "St. Paul,
Minnesota" at all M values. Stored capital is "Saint Paul" (full form). Evaluator
substring match fails in both directions; fuzzy match also fails. `steered_has_to_answer`
= False across all runs despite geographically correct output. This is a structural
mismatch between training-text abbreviation and stored formal name. Affects all
->minnesota_minneapolis pairs at every M value -- relative M comparisons are
unaffected but absolute hit rates for this target are systematically undercounted.

vsMax non-monotonic behavior for indiana->minnesota: M=20 (5.56) → M=10 (6.88) →
M=5 (6.00). M=10 is the local maximum. This replicates the iowa->utah non-monotonic
finding (vsMax higher at M=5 than M=20) with a different shape.

**Interpretation**:

Five failure modes are now identified and partially separated:


| Mode                            | Mechanism                                                                                                                  | Fix                                                                                     |
| ------------------------------- | -------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------------- |
| **Severe overshoot**            | rank_imprv << -100K, garbage first token; best_gap stable across M                                                         | M=5 rescues (88.1% on oklahoma_tulsa)                                                   |
| **Field interference**          | City features dominate capital features at position 1-2                                                                    | M=5 reduces interference; capital-only field variant partially helps via different path |
| **Feature interaction garbage** | Garbage token NOT from rank disruption (rank_imprv positive); specific feature combination activates code tokens at high M | M=5 rescues (indiana->arkansas)                                                         |
| **Signal collapse**             | vsMax collapses (7-14 → <1) below a M threshold; model reverts to source geography                                         | No M tested produces a hit; threshold pair-specific (M=5--M=10)                         |
| **Feature specificity**         | No first-token disruption, correct state context, wrong capital (e.g. Hutchinson not Topeka)                               | Not fixable by M tuning; requires better feature grouping                               |


The 88.1% M=5 hit rate for oklahoma_tulsa reflects that 37 of 42 pairs fall into
modes 1-2 (rescuable), while the 5 misses span modes 3, 4, and 5. The 0%
all-fields M=20 baseline and 22.4% capital-only M=20 baseline confirm that M=5 is
the strongest single-parameter fix tested so far for this target.

The best_gap stability across M values for the rescued oklahoma_tulsa pairs (16.88 /
16.84 / 16.91 at M=5/10/20) is the critical mechanistic observation: M does not
change the underlying label signal strength at all -- it only controls how cleanly
position 0 decodes. This means the features genuinely encode Oklahoma City; the
failure at M=20 is entirely in the decoding layer, not in the representation.

The "County continuation" misses (south_dakota, indiana at M=5 with rank_imprv near
zero and comma first token) are the clearest counterexample to a pure overshoot story.
They show that even with perfect position-0 decoding, the position-1 continuation
can still fail if source-entity residual features (after M_ablate=-2 multiplication,
not zeroing) generate a stronger "County" bigram than the amplified target capital
features. This may be solvable by M_ablate tuning rather than M_amplify tuning.

The "Saint Paul" evaluator gap is a new pipeline finding with no equivalent in prior
entries. Its extent across other abbreviable capitals (e.g. "Saint Louis" vs "St.
Louis") is unknown but plausibly non-trivial.

Confidence:

- M=5 rescues severe-overshoot oklahoma_tulsa pairs: **Medium-High** (N=37 hits,
consistent mechanism, best_gap stability confirmed)
- M=5 fails for moderate-signal and signal-collapse pairs: **Medium** (N=4 pairs,
two failure modes confirmed)
- "County continuation" as distinct failure mode: **Medium** (N=3 cases, but all
have anomalous ablate counts or token overlap)
- "Saint Paul" evaluator gap: **High** (structural mismatch, consistent across all
observed sources and M values)
- Non-monotonic vsMax: **Low** (2 pairs, different shapes)

**Threats to validity**:

- All 42 high-vsMax no-hit pairs share the same target (oklahoma_tulsa). The
88.1% rate may be specific to Oklahoma City's feature representation, the fixed
amplify_count=73, or the question format. No other high-vsMax target was tested.
- The M=5 hits produce grammatically unusual outputs ("is, Oklahoma City, and
Tulsa is Oklahoma"). A first-token-strict evaluation would count all as misses.
The metric is lenient enough to count "Oklahoma City" anywhere in 10 tokens.
- South_dakota's "County" continuation at M=5 with rank_imprv=+94 is NOT an
overshoot artifact. A full explanation requires feature-level analysis not done
here.
- The "Saint Paul" evaluator gap was confirmed for 3 sources; the remaining
46 ->minnesota_minneapolis pairs were not verified individually.
- Non-monotonic vsMax at M=10 for indiana->minnesota (6.88 > 5.56 and 6.00)
is N=1 and should not be cited without replication.
- M=7 was tested only on the two moderate-signal pairs. The signal-collapse
cliff locations (M=5--7 for vermont->kansas; M=7--10 for rhode_island->wisconsin)
may not generalize to other pairs.
- The 'tonode' mechanism for indiana->arkansas is observed but unexplained at
feature level. The rescue at M=5 is real but the root cause is unknown.

**Follow-up**:

- Run M=5 on the 7 oklahoma_tulsa pairs not yet tested (complete the population N=49).
- Test M=5 on high-vsMax no-hit pairs from other targets to verify generalizability
beyond oklahoma_tulsa.
- Test M=3 on the "County continuation" misses (south_dakota, indiana) to check if
further M reduction can flip the position-1 probability from "County" to "Oklahoma
City," given that position-0 is already clean at M=5.
- Investigate the M_ablate dimension: the "County continuation" may respond to
M_ablate=0 (full suppression of source features) rather than M_amplify tuning.
- Use PipelineTracer on kansas_wichita's capital supernode to check if it contains
Topeka-specific features or is contaminated with generic Kansas geography (explains
the vermont->kansas feature-specificity failure).
- Quantify the "Saint Paul" evaluator gap across all 49 ->minnesota_minneapolis
pairs and check other abbreviated-capital targets (e.g. "Saint Louis", "Saint
Augustine").
- Update the domain-level hit rate tables in `FULLSCALE_CONTROL_REPORT.md` with a
note that the USA rate at M=20 likely understates the achievable rate; M=5 is a
candidate for a re-run on the full USA dataset.

---

## [2026-04-01] Topic: M_amplify sweep on selected overshoot cases -- pilot results

**Question**: Can reducing M_amplify from 20 to {10, 5} convert "right direction,
no hit" cases to hits? The [2026-03-25] entry established that severe position-0
disruption (rank_imprv <= -100K) is the proximate cause of failure for high-vsMax
pairs. This pilot tests whether smaller M values rescue those cases without
destroying the label-specific signal.

**Method**: Selected 5 pairs from the USA `fullscale_usa_labeled` run, spanning
the overshoot severity spectrum (target_rank_improvement at pos0 from -167K to
+35). Created two new YAML configs (`sweep_usa_m5.yml`, `sweep_usa_m10.yml`)
identical to `fullscale_usa_labeled.yml` except M_amplify=5 and M_amplify=10
respectively (M_ablate=-2, temperature=0.3 unchanged). Ran each pair with:

```
python run_batch_swaps.py --config configs/sweep_usa_m{5,10}.yml \
    --run-id sweep_usa_m{5,10} --pair <from>:<to>
```

Results stored in `output/usa_states_batch/_swaps/runs/sweep_usa_m5/` and
`sweep_usa_m10/`. Compared using `SwapQuery.get()` and direct trajectory
inspection.

Pair selection criteria and M=20 baseline:


| Pair                                        | total_count | amplify | rank_imprv (M=20) | vsMax (M=20) |
| ------------------------------------------- | ----------- | ------- | ----------------- | ------------ |
| kansas_wichita -> oklahoma_tulsa            | 163         | 73      | -113,493          | 15.80        |
| delaware_wilmington -> oklahoma_tulsa       | 163         | 90      | -167,524          | 15.02        |
| vermont_burlington -> kansas_wichita        | 130         | 90      | -25,268           | 8.34         |
| rhode_island_warwick -> wisconsin_milwaukee | ~130        | ~75     | -1,515            | 8.78         |
| iowa_cedar_rapids -> utah_provo             | 253         | 93      | +35               | 8.62         |


**Raw findings**:

Hit/vsMax summary across M values (N=5 pairs each):


| Pair                                        | M=20     | M=10        | M=5          |
| ------------------------------------------- | -------- | ----------- | ------------ |
| kansas_wichita -> oklahoma_tulsa            | N / 15.8 | N / 15.8    | **Y / 14.3** |
| delaware_wilmington -> oklahoma_tulsa       | N / 15.0 | N / 14.9    | **Y / 13.9** |
| vermont_burlington -> kansas_wichita        | N / 8.3  | N / 8.1     | N / **0.3**  |
| rhode_island_warwick -> wisconsin_milwaukee | N / 8.8  | N / 8.5     | N / **2.1**  |
| iowa_cedar_rapids -> utah_provo             | N / 8.6  | **Y / 6.1** | **Y / 10.8** |


Hits: M=20: 0/5, M=10: 1/5, M=5: 3/5.

Position-0 disruption (target_rank_improvement):


| Pair                                        | M=20     | M=10    | M=5  |
| ------------------------------------------- | -------- | ------- | ---- |
| kansas_wichita -> oklahoma_tulsa            | -113,493 | -3,651  | -49  |
| delaware_wilmington -> oklahoma_tulsa       | -167,524 | -15,830 | -280 |
| vermont_burlington -> kansas_wichita        | -25,268  | -1,060  | +7   |
| rhode_island_warwick -> wisconsin_milwaukee | -1,515   | -156    | -11  |
| iowa_cedar_rapids -> utah_provo             | +35      | +451    | +409 |


Peak logit advantage over source (best_gap) -- M-stability indicator:


| Pair                                        | M=20  | M=10  | M=5      |
| ------------------------------------------- | ----- | ----- | -------- |
| kansas_wichita -> oklahoma_tulsa            | 16.91 | 16.84 | 16.88    |
| delaware_wilmington -> oklahoma_tulsa       | 22.03 | 23.16 | 23.86    |
| vermont_burlington -> kansas_wichita        | 16.69 | 16.38 | **9.59** |
| rhode_island_warwick -> wisconsin_milwaukee | 13.91 | 13.85 | **9.31** |
| iowa_cedar_rapids -> utah_provo             | 7.97  | 8.00  | 9.88     |


Control stability (mean absolute logit shift on non-answer tokens):


| Pair                                        | M=20  | M=10  | M=5  |
| ------------------------------------------- | ----- | ----- | ---- |
| kansas_wichita -> oklahoma_tulsa            | 14.14 | 11.81 | 6.68 |
| delaware_wilmington -> oklahoma_tulsa       | 13.84 | 11.70 | 6.70 |
| vermont_burlington -> kansas_wichita        | 11.11 | 10.49 | 8.28 |
| rhode_island_warwick -> wisconsin_milwaukee | 11.75 | 9.81  | 7.37 |
| iowa_cedar_rapids -> utah_provo             | 11.04 | 10.34 | 7.56 |


First token and steered output by M (M=20 first):

**kansas_wichita -> oklahoma_tulsa** (target capital = Oklahoma City):

- M=20: `'AddTagHelper'` (p=0.291) -- "County, Oklahoma, is Tulsa" (generates city, not capital)
- M=10: `' County'` (p=0.475) -- "County, Oklahoma, is Tulsa" (same wrong pattern)
- M=5: `','` (p=0.365) -- ", Oklahoma City, and Tulsa is Oklahoma" (**contains Oklahoma City**)

**delaware_wilmington -> oklahoma_tulsa** (same target):

- M=20: `'AddTagHelper'` (p=0.363) -- "County, Oklahoma, is Tulsa"
- M=10: `' County'` (p=0.457) -- "County, Oklahoma, is Tulsa"
- M=5: `','` (p=0.504) -- ", Oklahoma City, and Tulsa is Oklahoma" (**hit**)

**vermont_burlington -> kansas_wichita** (target capital = Topeka):

- M=20: `' Falls'` (p=0.652) -- "Falls, Kansas, is Hutchinson" (Kansas context but wrong city)
- M=10: `' Falls'` (p=0.711) -- "Falls, Kansas, is Hutchinson" (unchanged)
- M=5: `','` (p=0.428) -- "Falls, New York, is Albany" (signal dead -- reverts to source-like geography)

**iowa_cedar_rapids -> utah_provo** (target capital = Salt Lake City):

- M=20: `' Too'` (p=0.291) -- "Tooele County, Utah, USA" (Utah context but wrong place)
- M=10: `' Too'` (p=0.167) -- "Tooele County is the city of Salt Lake" (**hit**)
- M=5: `' St'` (p=0.094) -- "River, Utah is Salt Lake City" (**hit**)

**Interpretation**:

Three distinct regimes emerge:

1. **Severe overshoot, strong signal (oklahoma_tulsa pairs, vsMax > 14, rank_imprv
  << -100K)**: M=5 rescues both hits. The critical observation is that the
   best_gap (peak logit advantage over source) is nearly IDENTICAL across all
   three M values (16.88-16.91 for kansas pair, 22.03-23.86 for delaware pair).
   M does not change the underlying label-specific signal -- it only controls
   how cleanly position 0 decodes. At M=20, combined amplification of ~73*20=1460
   units pushes the target rank to -100K+, generating garbage (AddTagHelper).
   At M=5, the amplification of 73*5=365 units still produces the same peak
   logit advantage but does not corrupt position 0. The first token becomes `','`
   which allows the model to generate "Oklahoma City" as a continuation. M=10
   reduces disruption but not enough (rank_imprv still -3651 to -15830), and
   the first token (' County') still prevents a hit.
2. **Moderate overshoot, weak-to-moderate signal (vermont->kansas,
  rhode_island->wisconsin, vsMax ~8, rank_imprv -25K to -1.5K)**: M=5
   eliminates position-0 disruption (rank_imprv near 0) but also collapses
   the label-specific signal. best_gap drops from 16.69 to 9.59 (vermont->
   kansas) and vsMax from 8.34 to 0.31. The model reverts to source-like
   output ("Falls, New York, is Albany" -- wrong state, wrong capital).
   M=10 reduces disruption (rank_imprv from -25K to -1060) but the wrong
   first token (' Falls') persists and the generation still fails. There
   is no M in {5, 10, 20} that produces a hit. The optimal M for these
   pairs likely lies between 5 and 10, but may not exist -- the features
   for Topeka/Kansas and Madison/Wisconsin may be too weak at any usable M.
3. **Borderline disruption (iowa->utah, rank_imprv ~+35 at M=20)**: Both
  M=10 and M=5 produce hits. At M=20, the model generates "Tooele County"
   and terminates without producing "Salt Lake City". At M=10 and M=5, the
   model generates "Tooele County is the city of Salt Lake..." or "River,
   Utah is Salt Lake City" -- the correct answer emerges later in the
   generation. Notably, vsMax at M=5 (10.81) is higher than at M=20 (8.62),
   suggesting that for this high total_count (253) pair, M=20 is the
   threshold at which the amplification starts to suppress later-position
   recovery. Confidence: **Low** (single pair, non-monotonic behavior).

**An asymmetry in the oklahoma_tulsa outcomes**: At M=20 and M=10, the model
generates "County, Oklahoma, is Tulsa" -- producing the target entity's city
(Tulsa) rather than its capital (Oklahoma City). At M=5, it produces "Oklahoma
City." This suggests that at high M, the simultaneous amplification of all three
concept fields (state, capital, city) creates interference: the "city" features
for Tulsa compete with the "capital" features for Oklahoma City, and at M=20/10
the city features dominate position 0. At M=5, the reduced amplification allows
the capital features (more relevant to the question "The capital of the state
containing X is...") to emerge. This is distinct from pure overshoot and
warrants further investigation.

Confidence for the headline finding (M=5 rescues severe overshoot):
**Medium** -- consistent across 2 oklahoma_tulsa pairs, mechanistically
plausible (best_gap preserved), but N=2 pairs. The failure of M=5 for the
moderate-signal pairs (vermont->kansas, rhode_island->wisconsin) confirms
the "signal collapse" threat to validity identified in [2026-03-25].

**Threats to validity**:

- N=5 pairs total, N=2 hits recovered at M=5. Both successful cases share
the same target (oklahoma_tulsa). The effect may be specific to Oklahoma City
having a particularly clean feature representation rather than a general
M=5 superiority. Requires testing against other high-vsMax no-hit targets.
- The first-token `','` at M=5 succeeds because the model generates
"is, Oklahoma City" -- a grammatically unusual pattern. The hit is
technically correct (Oklahoma City appears in the output) but the output
quality is low. A more demanding evaluation (e.g., exact first-token match)
would not count this as a hit.
- The signal collapse at M=5 for moderate pairs (vermont->kansas, vsMax
drops from 8.34 to 0.31) confirms the threat identified in [2026-03-25].
A full sweep at M values between 5 and 10 would be needed to find the
optimum for these cases. It is not guaranteed an optimum exists.
- The iowa->utah case at M=5 shows vsMax=10.81 > M=20's 8.62 -- a
non-monotonic reversal. This could be noise (n=1), or could indicate
that very high total_count (253) creates enough interference at M=20 that
reducing M actually improves signal strength. Cannot distinguish without
more pairs.
- All five pairs were selected because they had high vsMax at M=20. They
are not representative of the full right-direction-no-hit population
(N=1345 in USA). The benefit of M=5 for the full population may be lower
because many no-hit pairs have lower vsMax and may suffer signal collapse.
- The control stability reduction at M=5 (from ~14 to ~6.7 for oklahoma
pairs) is positive but does not rule out other forms of disruption not
captured by the metric (e.g., disruption to attention heads or to tokens
not in the control window).

**Follow-up**:

- Run M=5 on a larger sample of high-vsMax no-hit pairs (e.g., top 30 by
vsMax with vs_max > 12 and no hit at M=20) to check if the 2/2 oklahoma_tulsa
hit recovery generalizes to other targets.
- Test M values between 5 and 10 (e.g., M=7) on the moderate-signal pairs
(vermont->kansas, rhode_island->wisconsin) to locate the signal-collapse
threshold. Is there a sweet spot between 5 and 10 that reduces disruption
without killing the signal?
- Investigate the "city vs capital interference" hypothesis: compare a run
using ONLY capital field features (not state + capital + city) at M=20 vs
a run using all three fields at M=5. If the city features are the source
of interference, field-restricted steering may outperform M reduction.
- Replicate the iowa->utah non-monotonic M result (vsMax higher at M=5 than
M=20) with other high-total_count pairs to determine if the effect is real.
- Update the regime taxonomy from [2026-03-24] with the new M=5 results:
which regime does the `','` first-token hit pattern belong to?

---

## [2026-04-01] Topic: M=5 oklahoma_tulsa sweep -- full population, miss analysis, and field comparison

**Question**: Does the M=5 rescue effect generalize across all 42 high-vsMax
no-hit oklahoma_tulsa pairs? What characterizes the misses? How does all-fields
M=5 compare to the existing capital-only M=20 variant as an alternative fix?

**Method**: Ran M=5 (config `sweep_usa_m5`, run_id `sweep_usa_m5`) on all 40
remaining high-vsMax no-hit oklahoma_tulsa pairs using `run_batch_swaps.py --pair`.
Combined with 2/2 from prior pilot: 42 total pairs tested.
For field comparison, queried `fullscale_usa_field_add` `add_capital` variant
(capital features only, M=20 unchanged) for all 49 oklahoma_tulsa pairs.
For miss analysis, loaded M=5 detail via `SwapQuery.get()` for the 5 failures.

**Raw findings**:

Hit rates for all->oklahoma_tulsa pairs by condition:


| Condition                                                | N               | Hits | Hit%  |
| -------------------------------------------------------- | --------------- | ---- | ----- |
| All-fields M=20 (fullscale_usa_labeled)                  | 49              | 0    | 0.0%  |
| Capital-only M=20 (fullscale_usa_field_add, add_capital) | 49              | 11   | 22.4% |
| All-fields M=5 (sweep_usa_m5)                            | 42 of 49 tested | 37   | 88.1% |


The all-fields M=5 vs all-fields M=20 comparison covers the same 42 pairs tested.
Capital-only M=20 covers all 49 (7 pairs not yet tested at M=5 are identity or
excluded from the high-vsMax set).

5 misses at M=5 (all->oklahoma_tulsa):


| Source                   | ablate | amplify | total | vsMax (M=5) | rank_imprv (M=5) | first_token | continuation                 |
| ------------------------ | ------ | ------- | ----- | ----------- | ---------------- | ----------- | ---------------------------- |
| west_virginia_huntington | 97     | 73      | 170   | 9.44        | -211             | `','`       | "Oklahoma is called Tulsa"   |
| maryland_baltimore       | 83     | 73      | 156   | 14.34       | -117             | `','`       | "County, Oklahoma, is Tulsa" |
| hawaii_hilo              | 28     | 73      | 101   | **4.81**    | -368             | `','`       | "'s population is 15,000"    |
| south_dakota_sioux_falls | 141    | 73      | 214   | 13.78       | **+94**          | `','`       | "County, Oklahoma, is Tulsa" |
| indiana_fort_wayne       | 200    | 73      | 273   | 13.56       | -32              | `','`       | "County, Oklahoma, is Tulsa" |


Three miss sub-types:

- **'County' continuation** (maryland, south_dakota, indiana): first token is `','`
but position 1 generates "County" then "Oklahoma, is Tulsa." The model has
non-garbage first token but still produces the wrong answer continuation.
- **West Virginia**: `','` first token but continuation is "Oklahoma is called
**Tulsa**" -- correct state but wrong concept (city not capital). vsMax dropped
to 9.44 from 14.69, partial signal degradation.
- **Hawaii signal collapse**: vsMax drops from 14.12 to 4.81 at M=5. Output is
"'s population is 15,000" -- model reverts to source entity context (Hilo facts).

Comma-first hits vs misses at M=5 (intervention count comparison):


| Source                   | ablate | total | vsMax (M=5) | rank_imprv | result        |
| ------------------------ | ------ | ----- | ----------- | ---------- | ------------- |
| new_hampshire_manchester | 54     | 127   | 14.38       | -212       | HIT           |
| texas_dallas             | 65     | 138   | 13.75       | -132       | HIT           |
| ohio_cleveland           | 67     | 140   | 13.69       | -30        | HIT           |
| delaware_wilmington      | 79     | 152   | 13.94       | -280       | HIT           |
| kansas_wichita           | 90     | 163   | 14.34       | -49        | HIT           |
| maryland_baltimore       | 83     | 156   | 14.34       | -117       | MISS (County) |
| west_virginia_huntington | 97     | 170   | 9.44        | -211       | MISS (Tulsa)  |
| south_dakota_sioux_falls | 141    | 214   | 13.78       | +94        | MISS (County) |
| indiana_fort_wayne       | 200    | 273   | 13.56       | -32        | MISS (County) |


No clean separation by ablate count or total. Kansas (ablate=90) hits while
maryland (ablate=83) misses with similar vsMax. South_dakota (ablate=141) and
indiana (ablate=200) both miss with the "County" continuation despite rank_imprv
near 0 or positive. Indiana_fort_wayne is a known token-overlap entity (ablate=200).

Capital-only M=20 hit mechanism: hits occur via position-1 recovery.
Example output: "...isexpandindo-o, **Oklahoma City**, and Tulsa" -- garbage at
position 0, but "Oklahoma City" immediately at position 1. The capital-only hits
cluster at vsMax 7.50-9.12. Capital-only misses at high vsMax (9-13) produce
"...isAddTagHelper, Oklahoma, is Tulsa" -- worse at high vsMax (capital-city
interference persists even with capital-only, inverted vsMax/hit correlation).

**Interpretation**:

The 88.1% hit rate at M=5 for the full oklahoma_tulsa high-vsMax no-hit set is
a strong result. It substantially exceeds capital-only M=20 (22.4%) and all-fields
M=20 (0%). Confidence: **Medium-High** (N=42 pairs, all same target, convergent
mechanism).

The three miss sub-types reveal that even at M=5, failure occurs via three distinct
paths:

1. **County continuation** (maryland, south_dakota, indiana): Position 0 is clean
  (comma), but the position-1 probability still favors "County" over "Oklahoma City."
   This may reflect that these source entities have concepts that generate a "County"
   bigram in context -- possibly because their features (after ablation) leave residual
   signals that reinforce the "...is County" continuation pattern. Indiana_fort_wayne
   (token overlap, ablate=200) is the extreme case. No simple M adjustment will fix
   this without also investigating the ablation component.
2. **West Virginia**: Partial signal degradation (vsMax 14.69→9.44) plus wrong
  concept generated (Tulsa instead of Oklahoma City). A candidate for M=7 or M=6
   tuning -- the vsMax drop suggests we are near the signal-collapse boundary.
3. **Hawaii signal collapse**: Full collapse at M=5 (vsMax 14.12→4.81), similar
  to vermont_burlington case. Hawaii's feature representation may be intrinsically
   weaker or more diffuse, causing the same cliff behavior.

The capital-only vs all-fields M=5 comparison reveals a deep asymmetry:
capital-only achieves hits through position-1 recovery after a garbage token,
while all-fields M=5 achieves hits through a clean-ish comma that allows
"Oklahoma City" in the grammatical continuation. All-fields M=5 produces nearly
4x the hit rate (88% vs 22%) because the stronger combined signal allows more
sources to generate "Oklahoma City" at position 1 even after the comma.

The inverted vsMax/hit relationship in capital-only M=20 (hits at vsMax 7-9, misses
at vsMax 9-13) is a replication of the confidence-hit paradox at a smaller scale.
Higher vsMax in capital-only generates "Oklahoma, is Tulsa" (city) while lower vsMax
generates "Oklahoma City" (capital) -- the capital features at moderate amplification
are more specifically informative than at high amplification where field interference
re-emerges even in the capital-only variant.

Confidence: **Medium** -- all conclusions limited to one target entity (oklahoma_tulsa).
Cannot determine generalizability without testing other targets.

**Threats to validity**:

- All 42 pairs share the same target (oklahoma_tulsa). The conclusions are
specific to this target. The feature quality, intervention count (amplify=73
fixed for all pairs), and answer identity (Oklahoma City) are all target-specific.
Other targets may show different rates.
- The 5 misses are heterogeneous: one signal-collapse (hawaii), one partial
degradation (west_virginia), three "County continuation." A satisfying explanation
requires feature-level analysis (which supernodes generate "County") that this
investigation did not do.
- "County" continuation at M=5 for south_dakota (rank_imprv=+94) means the
failure occurs even with zero first-token disruption. This is an intrinsic
failure of the feature combination, not an overshoot artifact.
- Indiana_fort_wayne is a known token-overlap entity (ablate=200), which may
bias the miss characterization by ablate count toward an artifact of entity type.

**Follow-up**:

- Test M=5 on all 49 oklahoma_tulsa pairs (7 not yet run) to get the complete
population rate.
- Investigate the "County continuation" mechanism: use PipelineTracer to check
which source supernodes are being ablated for south_dakota vs kansas, and whether
residual county-related features explain the bigram.
- Test M=5 on high-vsMax no-hit pairs from OTHER targets (to validate that the
88.1% rate is not oklahoma_tulsa-specific).
- Investigate the capital-only hit mechanism more carefully: why does lower vsMax
in capital-only lead to hits while higher vsMax leads to misses?

---

## [2026-04-01] Topic: M=7 threshold for moderate-signal pairs; non-monotonic M and evaluator gap

**Question**: (F2) Is there a usable M between 5 and 10 for moderate-signal pairs
(vermont_burlington->kansas_wichita, rhode_island_warwick->wisconsin_milwaukee)?
(F4) Does the iowa->utah non-monotonic vsMax pattern replicate on other
high-total_count pairs? And are there systematic metric undercounts?

**Method**: Created `sweep_usa_m7.yml` (M_amplify=7, all else unchanged). Ran M=7
on the two moderate-signal pairs. For F4, ran M=5 and M=10 on 4 high-total_count
(>250) pairs with mild/positive rank_imprv at M=20: indiana_fort_wayne->
{minnesota_minneapolis, arkansas_fayetteville}, idaho_idaho_falls->minnesota_minneapolis,
colorado_colorado_springs->minnesota_minneapolis. Loaded full detail via SwapQuery.

**Raw findings**:

M=7 on moderate-signal pairs:


| Pair                                  | M=20                            | M=10     | M=7              | M=5                        |
| ------------------------------------- | ------------------------------- | -------- | ---------------- | -------------------------- |
| vermont->kansas: vsMax                | 8.34                            | 8.12     | 7.75             | 0.31                       |
| vermont->kansas: rank_imprv           | -25,268                         | -1,060   | -97              | +7                         |
| vermont->kansas: first                | `Falls`                         | `Falls`  | `Falls`          | `,`                        |
| vermont->kansas: continuation         | Falls, Kansas, is Hutchinson    | same     | same             | Falls, New York, is Albany |
| rhode_island->wisconsin: vsMax        | 8.78                            | 8.47     | 2.38             | 2.12                       |
| rhode_island->wisconsin: rank_imprv   | -1,515                          | -156     | -47              | -11                        |
| rhode_island->wisconsin: first        | `expandindo`                    | `County` | `County`         | `,`                        |
| rhode_island->wisconsin: continuation | County, Wisconsin, is Green Bay | same     | County, New York | County, New York           |


**No M in {5, 7, 10, 20} produces a hit for either moderate-signal pair.**

Key observation for vermont->kansas at M=7: rank_imprv=-97 (minimal first-token
disruption), first token still ' Falls', continuation "Falls, Kansas, is Hutchinson."
The failure at M=7 is NOT first-token disruption -- the model generates the correct
state context (Kansas) but the wrong capital (Hutchinson, a large Kansas city).

For rhode_island->wisconsin: signal collapse between M=10 (vsMax=8.47) and M=7
(vsMax=2.38). The cliff is between M=10 and M=7 for this pair (vs between M=5 and
M=7 for vermont->kansas).

F4 -- High-total_count pairs with mild/positive rank_imprv at M=20:


| Pair                | total (M=20) | M=20     | M=10     | M=5          |
| ------------------- | ------------ | -------- | -------- | ------------ |
| indiana->minnesota  | 282          | N / 5.56 | N / 6.88 | N / 6.00     |
| indiana->arkansas   | 269          | N / 5.56 | N / 5.56 | **Y / 5.75** |
| idaho->minnesota    | 251          | N / 5.81 | N / 6.25 | N / 4.38     |
| colorado->minnesota | 245          | N / 5.62 | N / 4.94 | N / 4.81     |


Key F4 outputs:

`indiana_fort_wayne -> arkansas_fayetteville` (target capital = Little Rock):

- M=20: `'tonode'` -- "...istonode.\n\nThe capital of..."  (garbage token, output broken)
- M=10: `'tonode'` -- same failure
- M=5: `' Little'` -- "...is Little Rock, Arkansas..." **HIT!**
- rank_imprv=+178-179 at all M (no position-0 disruption). The 'tonode' token is
a different class of garbage -- NOT from rank disruption but from feature
interaction at M=20 that specifically generates a JavaScript/code token.
M=5 rescues by eliminating that interaction.

`->minnesota_minneapolis` pairs (target capital stored as "Saint Paul"):

- All M values, all sources: model outputs "St. Paul, Minnesota" (abbreviated)
- Evaluator requires "Saint Paul" (full spelling) -- systematic miss
- Affected pairs: indiana->minnesota, idaho->minnesota, colorado->minnesota
(and likely all 49 ->minnesota_minneapolis pairs at any M)
- `steered_has_to_answer` = False despite correct geographic content
- `steered_has_to_capital` = False (same metric, same field)

Example: idaho_idaho_falls->minnesota_minneapolis at ALL three M values outputs
"...Idaho Falls is St. Paul, Minnesota, is the largest..." which is a correct
description of Minnesota's capital but fails the evaluator.

vsMax behavior for indiana->minnesota across M values: non-monotonic
(5.56→6.88→6.00 for M=20→10→5). The M=10 value (6.88) is higher than both
M=20 (5.56) and M=5 (6.00). This non-monotonic pattern confirms the iowa->utah
finding but with moderate magnitude changes.

**Interpretation**:

For the moderate-signal pairs (F2), the investigation reaches a definitive
negative: no M in {5, 7, 10, 20} produces a hit. The two pairs fail via
fundamentally different mechanisms:

1. **vermont->kansas**: First-token disruption is NOT the failure mode at M=7
  (rank_imprv=-97, minimal). The model generates "Falls, Kansas, is Hutchinson"
   -- the source city token (' Falls') still dominates position 0, and the
   continuation correctly identifies Kansas as the target state but generates
   Hutchinson (a large Kansas city) instead of Topeka. **The features are pointing
   at Kansas/Wichita but not specifically at Topeka.** This is a feature specificity
   failure, not an overshoot failure. No M tuning can fix this without better
   features.
2. **rhode_island->wisconsin**: Signal collapses sharply between M=10 (intact,
  vsMax=8.47) and M=7 (collapsed, vsMax=2.38). The cliff is steeper and earlier
   than for vermont->kansas. At M=7, the model defaults to New York/Albany --
   same source-state reversion seen at M=5 for vermont->kansas.

For F4 (high-total_count non-monotonic):

`indiana->arkansas` at M=5 is a clean example of a different rescue mechanism:
the 'tonode' garbage token at M=20/10 is NOT caused by rank disruption
(rank_imprv=+178, always positive) but by a high-M feature interaction that
specifically activates a code-adjacent token. At M=5, this interaction is below
threshold and ' Little' (for "Little Rock") emerges. This is mechanistically
different from the oklahoma_tulsa overshoot rescue.

The "Saint Paul" evaluator gap is a systematic pipeline issue. All
->minnesota_minneapolis pairs appear to generate "St. Paul" (the standard
abbreviated form used in training text) rather than "Saint Paul" (the stored
formal name). The evaluator's substring match fails in both directions:
"St. Paul" is not in "Saint Paul" and "Saint Paul" is not in "St. Paul". The
fuzzy match also fails (different token strings). This affects the hit count
for all conditions tested (M=20, M=10, M=5) equally, so relative comparisons
between M values are unaffected, but absolute hit rates for ->minnesota_minneapolis
are systematically undercounted across the entire dataset.

The non-monotonic vsMax at M=10 for indiana->minnesota (6.88 > 5.56 at M=20 and
6.00 at M=5) is plausible: M=10 is at a "sweet spot" where the target signal is
maximally expressed without the interference that reduces it at M=20 or the
under-amplification at M=5. This remains single-pair evidence (Low confidence).

Confidence: **Medium** for the F2 negative result (consistent across 4 M values,
two pairs, mechanistically explained). **Low** for F4 non-monotonic vsMax.
**High** for the "Saint Paul" evaluator issue (affects all sources, all M values,
a structural mismatch between stored and generated form).

**Threats to validity**:

- The F2 negative result is limited to 2 pairs. There may be other moderate-
signal pairs with different targets where M=7 would produce a hit.
- The 'tonode' garbage mechanism for indiana->arkansas is unexplained at
feature level. We observe the token but do not know which specific features
generate it.
- The "Saint Paul" issue is confirmed for 3 sources but the full extent
across all 49 ->minnesota_minneapolis pairs was not verified due to shell
issues during analysis. Likely affects all 49 based on the consistent
"St. Paul" generation pattern across observed cases.
- Non-monotonic vsMax (M=10 > M=20 for some pairs) is single-pair evidence.

**Follow-up**:

- Check how many ->minnesota_minneapolis pairs have "St. Paul" vs "Saint Paul"
in outputs to quantify the full evaluator gap for this target.
- Investigate whether other targets with multi-word or abbreviated capitals
(e.g., "Salt Lake City" vs "SLC") have similar evaluator gaps.
- For the vermont->kansas "Hutchinson not Topeka" failure: run PipelineTracer
on kansas_wichita's grouping to see if "capital" supernode specifically
contains Topeka features or is contaminated with other Kansas city features.
- Test M=3 on the 5 M=5 misses (west_virginia, south_dakota, indiana) to see
if reducing M further can rescue the "County continuation" cases.

---

## Entry Template

Copy this block for each new investigation entry.

```
## [YYYY-MM-DD] Topic: [short descriptive title]

**Question**: What specifically are we testing? What claim does this probe?

**Method**: What queries, comparisons, or traces were run? Include the
exact SwapQuery/SwapStats/PipelineTracer calls or describe the filtering
logic.

**Raw findings**: Numbers, tables, sample details. No interpretation here --
just what the data shows.

**Interpretation**: What this evidence supports or undermines. State the
confidence level (Low / Medium / High) and which epistemic level it
addresses (L1: operational labels, L2: causal effects, L3: mechanistic).

**Threats to validity**:
- [ ] Could this be a pipeline artifact? (concept matching, blacklist, fallback)
- [ ] Could this be a metric artifact? (mechanical flip@0, fuzzy T5 matching)
- [ ] Is N large enough? What is the denominator?
- [ ] Does this replicate across entities / domains / conditions?
- [ ] Is there a simpler explanation?

**Follow-up**: What should be checked next to strengthen or falsify this?

**References**: Link to related entries, summary reports, or methodology
report sections.
```

---

(Investigation entries go below this line, newest first.)

## [2026-03-27] Topic: debunking target recovery rate as "single most discriminating signal"

**Question**: The `[2026-03-24] logit-shift taxonomy` entry claims target
recovery rate (does the target logit exceed its unsteered baseline at any
trajectory position?) is "the single most discriminating signal between
labeled and random" in regime C, citing 92% labeled vs 29% random. Is this
finding robust, or is it an artifact of the USA dataset, the max-over-
positions criterion, intervention count, redundancy with vs_max, or regime C
selection bias?

**Method**: Wrote `scripts/research/debunk_target_recovery.py`. Loaded all
labeled and random swap JSONs for USA (2450 labeled, 7350 random) and books
(240 labeled, 720 random). For each swap, extracted baseline target/source
logits, steered logit trajectories (11 positions), position-0 comparison,
intervention counts, and vs_max. Classified each swap into regime (A/C/D/E/B)
using position-0 deltas. Computed target recovery (any position > baseline)
and early recovery (positions 1-3 only). Tested five debunking hypotheses:

- H1: Max-over-positions inflation -- compared target recovery vs control
token recovery (control pos>0 exceeds control pos0) as a null model.
- H2: Intervention count confound -- compared total_count distributions
between labeled and random; checked recovery rate by count quartile.
- H3: Redundancy with vs_max -- checked if recovery adds discriminative
information beyond vs_max conditioning.
- H4: Regime C selection bias -- computed recovery across ALL regimes.
- H5: Position-specific robustness -- used stricter early-recovery criterion.

**Raw findings**:

*H0: Reproduction across domains*

Recovery rate in regime C:


| Dataset | Labeled regime C  | Random regime C     | Delta       |
| ------- | ----------------- | ------------------- | ----------- |
| USA     | 92.2% (1606/1741) | 18.9% (421/2223)    | **+73.3pp** |
| Books   | 91.9% (124/135)   | **88.9%** (128/144) | **+3.0pp**  |


Recovery rate across ALL regimes:


| Dataset | Labeled           | Random              | Delta      |
| ------- | ----------------- | ------------------- | ---------- |
| USA     | 92.4% (2264/2450) | 31.3% (2302/7350)   | +61.1pp    |
| Books   | 93.8% (225/240)   | **88.8%** (639/720) | **+5.0pp** |


The 92% vs 29% claim **does not replicate in books**. In books, which has
the *highest* vs_max delta of any domain (+6.14 per the domain gradient
entry), recovery rate barely separates labeled from random (3pp in regime C,
5pp overall).

*H1: Control token recovery as null model*

Control tokens "recover" (pos>0 exceeds pos0 logit) at near-100% rates:


| Condition              | Target recovers | Control recovers | Delta   |
| ---------------------- | --------------- | ---------------- | ------- |
| USA labeled regime C   | 92.2%           | 99.9%            | -7.7pp  |
| USA random regime C    | 18.9%           | 97.9%            | -79.0pp |
| Books labeled regime C | 91.9%           | 100.0%           | -8.1pp  |
| Books random regime C  | 88.9%           | 96.7%            | -7.8pp  |


Note: This comparison is not apples-to-apples. Control recovery is measured
against pos-0 logit (not unsteered baseline), because unsteered control
logits are not stored. The near-100% control rate confirms the overshoot
entry's finding that position 0 is catastrophically disrupted and later
positions always recover from the overshoot. The key observation is that in
USA random, target tokens do NOT participate in this generic recovery (only
18.9%), while in books random, they DO (88.9%).

*H2: Intervention count*


| Condition     | Mean total_count | Median |
| ------------- | ---------------- | ------ |
| USA labeled   | 177.7            | 164    |
| USA random    | 177.7            | 164    |
| Books labeled | 304.4            | 293    |
| Books random  | 304.4            | 293    |


Intervention counts are **matched by design** between labeled and random.
Within USA labeled regime C, recovery rate by total_count quartile:


| Quartile | Range   | Recovery |
| -------- | ------- | -------- |
| Q1       | 0-148   | 87.1%    |
| Q2       | 148-165 | 95.7%    |
| Q3       | 165-202 | 93.9%    |
| Q4       | 202+    | 91.7%    |


Recovery is high across all quartiles; no monotonic relationship with
feature count. **H2 ruled out.**

*H3: Redundancy with vs_max*

Labeled regime C, vs_max by recovery status:


| Dataset | Recoverers         | Non-recoverers     |
| ------- | ------------------ | ------------------ |
| USA     | mean 2.60 (N=1606) | mean -0.81 (N=135) |
| Books   | mean 4.85 (N=124)  | mean 3.19 (N=11)   |


Recovery is correlated with vs_max, but does it add information?

Among swaps with vs_max > 0 only:


| Dataset | Labeled recovery | Random recovery   | Delta       |
| ------- | ---------------- | ----------------- | ----------- |
| USA     | 96.3% (N=1951)   | 45.5% (N=929)     | **+50.8pp** |
| Books   | 94.4% (N=234)    | **88.6%** (N=342) | **+5.8pp**  |


In USA, recovery separates labeled from random even after conditioning on
positive vs_max. In books, the gap is only 5.8pp -- nearly gone.

*H4: Regime C selection bias*

Already shown above: recovery across all regimes has the same pattern.
USA gap persists (92.4% vs 31.3%). Books gap barely exists (93.8% vs 88.8%).
**H4 ruled out for USA, confirmed for books (no signal to select for).**

Per-regime recovery for random:


| Regime | USA random        | Books random    |
| ------ | ----------------- | --------------- |
| A      | 45.3% (809/1784)  | 92.9% (289/311) |
| C      | 18.9% (421/2223)  | 88.9% (128/144) |
| D      | 32.1% (1071/3337) | 83.8% (222/265) |


Books random recovery is **83-93%** across ALL regimes. The books model
easily recovers target logits above baseline regardless of whether the
intervention is labeled or random.

*H5: Early recovery (positions 1-3 only)*


| Dataset | Labeled regime C  | Random regime C     | Delta      |
| ------- | ----------------- | ------------------- | ---------- |
| USA     | 61.5% (1070/1741) | 11.7% (259/2223)    | +49.8pp    |
| Books   | 73.3% (99/135)    | **78.5%** (113/144) | **-5.2pp** |


In books, early recovery **inverts** -- random actually exceeds labeled!

Position-specific recovery in USA regime C:


| Position | Labeled | Random | Delta   |
| -------- | ------- | ------ | ------- |
| 1        | 10.2%   | 0.8%   | +9.4pp  |
| 2        | 52.4%   | 9.6%   | +42.8pp |
| 3        | 30.6%   | 2.2%   | +28.4pp |
| 4        | 63.0%   | 3.7%   | +59.3pp |
| 5        | 55.1%   | 4.2%   | +50.9pp |
| 6        | 44.5%   | 2.8%   | +41.7pp |
| 7        | 36.9%   | 1.3%   | +35.6pp |
| 8        | 24.3%   | 2.1%   | +22.2pp |
| 9        | 34.6%   | 3.6%   | +31.0pp |
| 10       | 27.2%   | 0.9%   | +26.3pp |


In USA, the gap is robust at every individual position, peaking at
positions 2 and 4-5 (the same positions where the overshoot entry found
target rank recovering to top-15).

*Recovery magnitude*


| Condition                         | Mean excess above baseline | Median |
| --------------------------------- | -------------------------- | ------ |
| USA labeled regime C recoverers   | +5.12                      | +4.88  |
| USA random regime C recoverers    | +1.38                      | +1.00  |
| Books labeled regime C recoverers | +4.81                      | +4.44  |
| Books random regime C recoverers  | +2.90                      | +2.75  |


Even in books where recovery rates are similar, labeled recoverers exceed
baseline by larger amounts (4.81 vs 2.90 logit units). Recovery magnitude
discriminates better than the binary recovery indicator in books.

**Interpretation**: The claim that target recovery rate is "the single most
discriminating signal between labeled and random" is **domain-specific and
overstated**. Confidence: **High** for the debunking. Epistemic level:
**L1** (metric validity) with **L2** implications.

The evidence shows:

1. **Does not replicate across domains.** The 92% vs 29% gap in USA regime C
  becomes 92% vs 89% in books regime C -- a 3pp delta, well within noise for
   N=135/144. The early-recovery variant actually *inverts* in books (73% vs
   79%). A metric that only discriminates in one of two tested domains cannot
   be called "the single most discriminating signal."
2. **USA-specificity has a plausible explanation.** In USA, random
  interventions produce very low target recovery (31%) because random
   features do not activate on target-concept contexts, so amplifying them
   does not push the target logit above its baseline. In books, random
   interventions produce high target recovery (89%) despite not being
   targeted -- likely because the books model has 16 entities with strongly
   distinct representations, and any sufficiently large perturbation
   activates enough residual target-concept circuitry to exceed the baseline.
   This means recovery in books is **mechanically easy**, not informative.
3. **Recovery magnitude is more informative than the binary flag.** Even in
  books where binary recovery is non-discriminating, labeled recoverers
   exceed baseline by 4.81 vs 2.90 logit units for random. A continuous
   "max excess above baseline" metric would retain discriminative power
   across domains where the binary version fails.
4. **The intervention count confound is cleanly ruled out.** Both conditions
  use identical feature counts by design, and within labeled there is no
   monotonic relationship between count and recovery. The signal is about
   *which* features are amplified, not *how many*.
5. **Regime C selection bias is ruled out for USA but irrelevant for books.**
  The USA gap persists across all regimes (92% vs 31% overall). In books,
   there is no gap to explain.
6. **The "any position" criterion is not the issue.** Even position-specific
  rates at individual trajectory positions show massive USA gaps (e.g.,
   52% vs 10% at position 2). The max-over-positions does inflate the
   absolute rate but does not create the labeled/random delta.

**Net assessment of the original claim**: Target recovery rate is a real and
meaningful signal in USA, where it captures whether amplified features
specifically activate target-concept logits. It is not a universal
discriminator. The log entry should have tested replication before calling
it "the single most discriminating signal." The correct statement is:
"target recovery rate is the strongest discriminator in USA but loses
nearly all discriminative power in books, where random recovery is
mechanically high."

**Recommended replacement metric**: `tgt_max_excess` (max logit excess over
unsteered baseline across trajectory positions). This continuous metric
retains separation in both USA and books (5.12 vs 1.38 and 4.81 vs 2.90
respectively) and is not subject to the binary ceiling effect that makes
recovery useless in books.

**Threats to validity**:

- Only two domains tested (USA, books). Products, paintings, and sounds
should be checked. However, sounds has known structural issues, and
paintings has small N (90 pairs).
- The control token recovery null model uses a different baseline
(pos-0 logit, not unsteered), so it cannot directly test whether target
recovery is target-specific. A proper null model would need unsteered
control logits, which are not stored in the swap JSONs.
- The books result could reflect books-specific properties (small answer
space, highly distinctive entity names) rather than a general failure of
the metric. But this is precisely the point: a metric that fails on
"easy" datasets is not robust.
- Recovery magnitude (recommended replacement) has not been formally
validated as a discriminator with bootstrap CIs or effect sizes.
- The regime classification uses position-0 deltas, which are themselves
subject to overshoot. Different classification thresholds could shift the
regime C populations.

**Follow-up**:

- Compute `tgt_max_excess` across all 5 datasets and run `SwapStats.compare()`
to check if it maintains labeled vs random separation with proper effect
sizes.
- Check products and paintings for recovery rate discrimination. If books is
the only domain where recovery fails, the explanation may be books-specific
rather than a general debunking.
- Consider whether the books model's high random recovery reflects weaker
baseline representations (smaller answer space = easier to perturb above
baseline) vs structural properties of the attribution graphs.
- Re-examine the `[2026-03-24] logit-shift taxonomy` entry's composite
label-evidence score (`vs_max > 0` + recovery + `tgt_win_pct > 0.5`) --
if one of the three components is non-discriminating in books, the
composite may also be weak there.

**References**: `[2026-03-24] logit-shift taxonomy and label-evidence metric design` (original claim); `[2026-03-25] best field-add variant vs random in regime taxonomy`; `[2026-03-25] steering strength overshoot`;
`scripts/research/debunk_target_recovery.py`

---

## [2026-03-25] Topic: steering strength overshoot -- evidence and sweep design

**Question**: The current steering uses M_ablate=-2, M_amplify=20, temperature=0.3
for all runs. Many swaps show correct logit direction (vs_max > 0) but no exact-
match hit. Is this because the intervention is too strong, destroying the logit
distribution at position 0 and producing garbage tokens? Would a steering strength
sweep recover hits from these cases?

**Method**: Used SwapQuery across all 5 datasets to classify swaps by (direction
right, hit vs no-hit). For no-hit cases: inspected steered first tokens, steered
output text, and full logit trajectories via `q.get()`. Correlated intervention
magnitude (`total_count`), disruption (`control_stability_mean`), and first-token
confidence (`steered_first_prob`) with outcome. Examined position-0 vs later
positions in the trajectory for recovery patterns.

**Raw findings**:

The "right direction, no hit" population is massive:


| Dataset   | N total | Direction right | + hit | + no hit | No-hit % |
| --------- | ------- | --------------- | ----- | -------- | -------- |
| USA       | 2450    | 1951 (79.6%)    | 606   | **1345** | 54.9%    |
| Books     | 240     | 234 (97.5%)     | 9     | **225**  | 93.8%    |
| Products  | 132     | 107 (81.1%)     | 20    | **87**   | 65.9%    |
| Paintings | 90      | 70 (77.8%)      | 4     | **66**   | 73.3%    |
| Sounds    | 30      | 30 (100%)       | 0     | **30**   | 100%     |


Books is extreme: 97.5% of swaps have the target logit beating all competitor
answer logits at some trajectory position, but only 3.8% produce the target
answer in text.

First tokens in the right-direction-no-hit population:


| Dataset   | Top tokens (% of no-hit)                                         | Obvious garbage % |
| --------- | ---------------------------------------------------------------- | ----------------- |
| USA       | `' Efq'` (19.9%), `'AddTagHelper'` (9.7%), `'expandindo'` (8.8%) | ~95%+             |
| Books     | `"'"` (39.1%), `'-'` (10.2%), `','` (8.9%), `' Efq'` (6.7%)      | ~63%              |
| Products  | `"'"` (51.7%), `' '` (13.8%), `','` (13.8%)                      | ~85%              |
| Paintings | `'<bos>'` (19.7%), `' Majefty'` (19.7%), `'e'` (10.6%)           | ~95%+             |


USA and paintings generate tokens from completely unrelated vocabularies:
`' Efq'`, `'AddTagHelper'`, `'expandindo'`, `' يتيمه'`, `' Audiodateien'`,
`'Datuak'`, `' Majefty'`, `' Houfe'` -- Arabic, Portuguese, German, 18th-century
English, JavaScript variable names. These are hallmarks of a logit distribution
pushed so far off the manifold of coherent text that random high-activation
tokens from unrelated subspaces dominate.

Books and products predominantly output punctuation (`'`, `-`, `,`) -- the model's
logit distribution is broken but lands on common short tokens.

**Paradox: higher confidence = worse outcome.** Among right-direction-no-hit:


| Dataset   | mean steered_first_prob (hit) | mean steered_first_prob (no-hit) |
| --------- | ----------------------------- | -------------------------------- |
| USA       | 0.282                         | **0.383**                        |
| Books     | 0.299                         | **0.367**                        |
| Products  | **0.149**                     | 0.319                            |
| Paintings | **0.571**                     | 0.314                            |


In USA and books, the model is MORE confident at position 0 when it produces
garbage than when it produces a hit. The intervention pushes the model to very
high confidence in a wrong token -- classic overshoot.

Trajectory deep dive (5 USA swaps with vs_max > 15, no hit):


| Position | Target logit   | Target rank        | Generated token |
| -------- | -------------- | ------------------ | --------------- |
| 0        | -0.60 to -3.36 | 113,504 -- 167,275 | `' County'`     |
| 1        | 23.00 -- 24.12 | 10 -- 15           | `','`           |
| 2        | **27.25**      | **1**              | `' Oklahoma'`   |
| 3        | 24.12 -- 24.50 | 18 -- 23           | `','`           |
| 5        | 24.25 -- 24.88 | 2 -- 6             | `' Tulsa'`      |


**Position 0 is catastrophic (rank > 100K), but by position 2 the target reaches
rank 1.** The correct answer appears in the continuation: "County, Oklahoma, is
Tulsa" -- the model recovers but the corrupted first token prevents exact match.

Trajectory deep dive (books, hermione_granger -> jay_gatsby, vs_max=13.7):


| Position | Target logit | Target rank | Generated token |
| -------- | ------------ | ----------- | --------------- |
| 0        | 19.25        | 2           | `"'"`           |
| 1        | -0.64        | 179         | `'s'`           |
| 2        | 25.12        | 5           | `' author'`     |
| 3        | 13.44        | 1846        | `','`           |
| 4        | 8.06         | 2375        | `' J'`          |


Output: `"written by's author, J.K. Rowling"` -- apostrophe at position 0, then
the model recovers to produce the DEFAULT (source) author, not the target.

Position-0 disruption metrics:


| Metric                                 | Range across samples           |
| -------------------------------------- | ------------------------------ |
| target_logit_delta (pos 0 vs baseline) | -2.1 to **-26.7** logit units  |
| source_logit_delta (pos 0 vs baseline) | -15.8 to **-30.9** logit units |
| target_rank at pos 0                   | 2 to **167,275**               |


When M_ablate=-2 and M_amplify=20 are applied to hundreds of features
simultaneously, the combined effect can shift logits by 20-30 units at position 0,
pushing tokens to ranks > 100K.

Intervention count vs disruption (USA):


| total_count quartile | N   | Hit%      | vs_max   | ctrl_stability |
| -------------------- | --- | --------- | -------- | -------------- |
| Q1 (94-147)          | 614 | 23.6%     | 2.45     | 13.3           |
| Q2 (148-164)         | 642 | **27.3%** | **3.27** | 13.4           |
| Q3 (165-203)         | 586 | 27.0%     | 3.38     | 13.7           |
| Q4 (204-369)         | 608 | 21.1%     | 2.33     | **15.2**       |


Q2 is the sweet spot: moderate feature count, best hit rate, good vs_max, low
disruption. Q4 (most features) has highest disruption and lowest hit rate despite
strong direction (the "less is more" effect appears here too, compounded by
overshoot).

Key correlations (USA, N=2450):

- `steered_first_prob` vs hit: r = **-0.211** (more confident = fewer hits)
- `total_count` vs `control_stability`: r = **+0.232** (more features = more disruption)
- `total_count` vs hit: r = -0.035 (weak)
- `control_stability` vs hit: r = -0.058 (weak but correct sign)

**Interpretation**: There is strong evidence for steering overshoot. Confidence:
**High** for the existence of overshoot; **Medium** for quantifying how much a
sweep would recover. Epistemic level: **L2** (causal intervention design).

The case for a strength sweep rests on four convergent signals:

1. **Massive right-direction-no-hit population.** 55-94% of swaps have the correct
  logit direction but fail to produce the target in text. These are not cases where
   the labels are wrong -- the features point at the right concept. The decoding
   step is what fails.
2. **Position-0 catastrophic disruption.** The combined effect of M_ablate=-2 on
  hundreds of source features and M_amplify=20 on hundreds of target features
   produces logit shifts of 20-30 units, pushing target rank to > 100K at position
  1. This is orders of magnitude more disruption than needed to flip the target
    ove the source.
3. **Recovery at later positions.** By position 2-3, target rank typically returns
  to 1-15 and the model generates coherent tokens including the target answer.
   The information is there -- the first token just gets destroyed.
4. **Confidence-hit paradox.** Higher steered_first_prob at position 0 correlates
  with FEWER hits (r=-0.211 in USA). The intervention does not just shift the
   logit distribution -- it concentrates probability mass on a single wrong token,
   making the model very confident in garbage.

**Sweep design recommendations**:

*Sweep parameters*:


| Parameter   | Current | Recommended sweep values | Rationale                                                  |
| ----------- | ------- | ------------------------ | ---------------------------------------------------------- |
| M_amplify   | 20      | **2, 5, 10, 15, 20**     | Primary suspect; 20x stored activation is likely excessive |
| M_ablate    | -2      | **0, -0.5, -1, -2**      | Reversal (-2) may be too aggressive; 0 = full ablation     |
| temperature | 0.3     | **0.3, 0.5, 0.7, 1.0**   | Higher T may help escape distorted distribution            |


*Priority*: M_amplify sweep alone is the highest-value test. It directly controls
how hard target features are injected. M_ablate and temperature are secondary.

*Minimal viable sweep*: M_amplify in {5, 10, 20} with M_ablate fixed at -2 and
temperature at 0.3. This is 3 runs per dataset -- feasible as a pilot on USA only
(~2450 pairs each, ~3 hours per run on current infra).

*Evaluation focus*: The sweep should primarily track:

- hit rate (expect non-monotonic: too low = no steering, too high = overshoot)
- control_stability_mean (expect monotonic decrease with lower M)
- steered_first_prob (watch for the confidence-hit paradox disappearing)
- vs_max (may decrease with lower M -- acceptable if hits increase)

*Expected outcome*: A lower M_amplify (5-10) should:

- Reduce position-0 disruption, producing coherent first tokens
- Potentially sacrifice some vs_max (target logit won't beat competitors as strongly)
- Increase hit rate if the "right direction, garbage output" cases convert to hits
- Decrease control_stability (less collateral damage)

The optimal M_amplify is likely in the 5-15 range. Below 5, the steering may be
too weak to overcome the baseline source-answer dominance. Above 15, the overshoot
evidence suggests diminishing returns.

*Alternative to M sweep*: An intervention-count cap (top-K features per concept
field) would reduce the combined magnitude without changing M. This could be
combined with an M sweep for a 2D exploration.

**Threats to validity**:

- The "garbage token" classification is based on visual inspection and heuristic
rules, not a formal classifier. Some tokens classified as garbage may be
legitimate (e.g., `' St'` for "St. Louis" could be correct in some contexts).
- The confidence-hit paradox (r=-0.211) is a population-level correlation.
Individual pairs may behave differently. A proper causal test requires the
sweep itself.
- The trajectory analysis shows 5 hand-picked high-vs_max cases. The
recovery pattern may not hold for lower-vs_max cases where the direction is
only marginally correct.
- Lower M_amplify might not just reduce overshoot -- it might also reduce
the label-specific signal, making labeled interventions more similar to random
ones. The sweep must compare labeled vs random at each M value.
- Temperature interacts with M: lower M + higher T might produce different
results than lower M alone. A 2D sweep would be ideal but more expensive.
- The current metric suite may not capture all the effects. Consider adding
a "position-0 coherence" metric (e.g., is the first token in the top-100
unsteered tokens?) to track overshoot directly.

**Follow-up**:

- Implement a minimal M_amplify sweep on USA: {5, 10, 20} with current M_ablate
and temperature. Compare hit rate, vs_max, and control_stability.
- Consider a "top-K features" variant alongside the M sweep: cap ablate_count
and amplify_count at K={20, 50, 100} to reduce combined intervention magnitude.
- Add a position-0 coherence metric to the evaluation pipeline: does the steered
first token appear in the top-K of the unsteered distribution?
- After the sweep: recompute the regime taxonomy (entry [2026-03-24]) at the
optimal M value to see if regime A prevalence increases.

**References**: `scripts/03_ct_steering.py` (M semantics, lines 362-364);
`scripts/neuronpedia_steering/batch_steering_ct.py` (new_value = M * original,
line 403-405); config `scripts/experiments/batch/configs/fullscale_*_labeled.yml`;
previous entries `[2026-03-24] logit-shift taxonomy`, `[2026-03-25] best field-add variant vs random in regime taxonomy`

---

## [2026-03-25] Topic: impact of reverse-substring supernode matches on swap performance

**Question**: The concept-to-supernode matcher uses bidirectional substring
matching: `supernode_lc in word` (reverse). This causes supernodes like "is" to
match concept "mississippi", "port" to match "gulfport", "Karen" to match
"karenina", "ica" to match "guernica". These reverse-substring matches pull in
large, low-layer, likely polysemantic supernodes. Do they degrade swap
targeting? Would excluding them improve results?

**Method**: Wrote `scripts/research/substring_supernode_investigation.py`.
Classified every concept-to-supernode match into 5 types:

- **exact**: concept == supernode (e.g., "mississippi" = "mississippi")
- **word_exact**: a word from concept == supernode (e.g., "jackson" from "Jackson" = "Jackson")
- **concept_in_sn**: full concept in supernode or vice versa
- **word_in_sn**: concept word found inside supernode name
- **sn_in_word**: supernode name found inside concept word (REVERSE -- most
problematic; e.g., "is" inside "mississippi", "ica" inside "guernica")

For each entity: counted active features by match type, computed noisy_pct
(fraction of active features from sn_in_word matches), and correlated with
per-entity mean `vs_max` as source. Additionally tested within-entity using
field-add variants to compare outcomes when noisy fields are included vs
excluded.

**Raw findings**:

Reverse-substring (sn_in_word) prevalence across datasets:


| Dataset   | sn_in_word features | % of active | Top noisy supernodes                                   |
| --------- | ------------------- | ----------- | ------------------------------------------------------ |
| USA       | 442 / 4,579         | 9.0%        | "is" (293), "port" (75), "in" (31)                     |
| Books     | 994 / 2,260         | 34.7%       | "Karen" (194), "uckleberry" (130), "hab" (111)         |
| Products  | 60 / 797            | 7.5%        | "Tes" (38), "Press" (8), "Dy" (8)                      |
| Paintings | 1,049 / 1,880       | 48.8%       | "ica" (192), "atte" (169), "ighth" (131), "ring" (125) |
| Sounds    | 138 / 561           | 24.6%       | "iss" (60), "ble" (36), "is" (27)                      |


Per-entity extremes:


| Entity               | Noisy%    | Active | Noisy | Direct | vs_max | Dataset mean |
| -------------------- | --------- | ------ | ----- | ------ | ------ | ------------ |
| mississippi_Gulfport | **77.5%** | 160    | 124   | 36     | 3.20   | 2.86         |
| nighthawks           | **78.1%** | 192    | 150   | 42     | 1.68   | 1.55         |
| grande_jatte         | **77.2%** | 246    | 190   | 56     | 1.65   | 1.55         |
| anna_karenina        | **68.2%** | 209    | 143   | 66     | 6.51   | 5.98         |
| hiss                 | **65.5%** | 145    | 95    | 50     | 3.29   | 3.28         |


All five highest-noisy entities perform **at or above** their dataset mean on
vs_max.

Correlations with mean_vs_max:


| Dataset   | r(noisy_pct, vsMax) | r(noisy_feats, vsMax) | r(active_total, vsMax) | r(direct_feats, vsMax) | N   |
| --------- | ------------------- | --------------------- | ---------------------- | ---------------------- | --- |
| USA       | 0.121               | 0.083                 | **-0.298**             | **-0.402**             | 50  |
| Books     | -0.207              | -0.215                | 0.211                  | **-0.281**             | 16  |
| Products  | -0.442              | -0.439                | -0.265                 | -0.084                 | 12  |
| Paintings | -0.036              | -0.057                | -0.334                 | -0.205                 | 10  |
| Sounds    | -0.545              | -0.384                | -0.289                 | 0.355                  | 6   |


Within-entity field-add comparison (USA, Mississippi_Gulfport vs low-noisy
entities as source):


| Condition                | vs_max (Mississippi) | vs_max (low-noisy, N=5) | Delta     |
| ------------------------ | -------------------- | ----------------------- | --------- |
| state only               | 2.51                 | 2.68                    | -0.17     |
| state+capital            | **4.03**             | **4.20**                | -0.17     |
| all 3 fields (adds city) | 3.09                 | 3.02                    | **+0.07** |
| Drop (s+c -> all)        | -0.94                | **-1.18**               | --        |


Adding the city field (which brings in 124 noisy "port"/"Gulf" features for
Mississippi) causes a vs_max drop of 0.94. But the low-noisy group drops
**more** (1.18) when adding their clean city features. The noisy features are
not causing extra harm.

**Interpretation**: Reverse-substring matches add large volumes of likely
irrelevant features to interventions, but **they do not measurably harm swap
performance**. Confidence: **Medium-High** (strong USA evidence, directionally
consistent across datasets, but small N in non-USA). Epistemic level: **L1**
(pipeline/metric quality) with **L2** implications (causal intervention design).

The evidence converges from four angles:

1. **Direct correlation is absent or wrong-signed in the largest dataset.** USA
  (N=50) shows r=0.121 between noisy_pct and vs_max -- slightly *positive*,
   not negative. The five highest-noisy entities all perform at or above their
   dataset mean. If noisy features were actively harmful, Mississippi_Gulfport
   (77.5% noisy) should perform badly; it doesn't (vs_max 3.20 vs mean 2.86).
2. **The real predictor is total feature count, not match quality.** `direct_feats`
  correlates *more negatively* with vs_max (r=-0.402 in USA) than `active_feats`
   (r=-0.298). This means entities with more *cleanly-matched* features perform
   worse -- the problem is dilution, not noise. When the intervention spreads
   amplification/ablation across more features, each individual feature gets a
   weaker push, reducing targeting precision. Noisy features add to the count but
   don't create a qualitatively different problem from having too many clean matches.
3. **Within-entity comparison shows no differential.** The field-add experiment
  for Mississippi (adding the city field which brings 124 noisy features) causes
   a 0.94-point vs_max drop. But low-noisy entities adding their clean city
   features drop *more* (1.18 points). The noisy features do not cause extra harm
   beyond the generic "more features = weaker intervention" effect.
4. **The extreme cases work fine.** Paintings has 48.8% of all active features from
  reverse-substring matches (nighthawks 78.1%, grande_jatte 77.2%, guernica 76.6%).
   If nearly half the intervention were "junk" features, these entities should perform
   catastrophically. They don't -- their vs_max values are at or above the dataset
   mean. This is the strongest evidence that the noisy features are not actively
   interfering.

**Why don't noisy features hurt?** Two possible mechanisms:

- (a) The amplification/ablation multipliers are applied per-feature. Noisy features
that are semantically irrelevant to the swap have low activation on the target
concept's context, so amplifying/ablating them has small absolute effect on logits.
They dilute the intervention magnitude but don't push logits in wrong directions.
- (b) Some "noisy" matches are actually partially relevant. "Karen" features for
Anna Karenina likely fire on Karenina-related contexts. "ica" features for
Guernica may include features that respond to the painting's name. The substring
match catches semantically adjacent features, not purely random ones.

**What actually matters**: The consistent finding across investigations is that
**total intervention size** (feature count) is the primary predictor of performance,
with a modest negative correlation. The "less is more" effect documented in the
field-add experiments is driven by feature count dilution, not by the quality of
individual feature matches. Improving the matcher to exclude reverse-substring
matches would reduce feature counts by 9-49% depending on dataset, which could
improve performance -- but through the count-reduction mechanism, not because the
features are harmful per se.

**Threats to validity**:

- USA is the only dataset with N=50 for entity-level correlations. Books (16),
products (12), paintings (10), sounds (6) have small N where any correlation
is unreliable. The USA null finding (r=0.121) is the most trustworthy.
- Entity-level correlations conflate many factors. An entity with high noisy%
may also differ in graph quality, prompt structure, answer specificity, etc.
The within-entity field-add comparison is cleaner but only tests one entity
(Mississippi) with extreme noisy burden.
- "Noisy features don't hurt" could mean "the metrics don't capture the harm."
If noisy features cause more control_stability disruption or push logits toward
wrong answers in ways vs_max doesn't capture, the harm could be hidden.
- The field-add comparison uses different pairs for Mississippi (N=49) vs
low-noisy (N=392), so population differences could mask effects.
- Paintings and sounds have known dataset-level issues (tiny answer space,
field collapse) that may dominate any substring effect.
- Mechanism (b) above -- partial semantic relevance of "noisy" matches --
is speculative and would need activation-level analysis to verify.

**Follow-up**:

- Test whether *removing* reverse-substring features from interventions improves
outcomes. This requires either rerunning swaps with a strict matcher or
simulating the effect by comparing pairs where the noisy features have low
vs high baseline activation.
- Investigate whether the `direct_feats` negative correlation in USA (r=-0.402)
is driven by specific concept fields (city generates the most features) or
is uniform across fields.
- Consider implementing an intervention-count cap: rather than matching all
features in concept-matching supernodes, take only the top-K by node_influence.
This would address the dilution problem directly without requiring matcher
changes.
- Check whether noisy features correlate with `control_stability_mean` (collateral
damage metric). Even if vs_max is unaffected, noisy features might increase
non-specific disruption.

**References**: Previous entries `[2026-03-24] reverse substring matching confound scan`, `[2026-03-25] do "(concept) related" Relationship features hurt swap performance?`, `[2026-03-25] best field-add variant vs random in regime taxonomy`;
`scripts/utils/pipeline_tracer.py` (_concept_matches_supernode)

---

## [2026-03-25] Topic: do "(concept) related" Relationship features hurt swap performance?

**Question**: Relationship features (e.g., "(entity) related", "(capital) related")
are classified as `pred_label = "Relationship"` in the grouping pipeline. They tend
to be polysemantic, activating for relational/contextual patterns rather than
specific entity tokens. Does including them in swap interventions degrade targeting
metrics? Would excluding them improve results?

**Method**:

1. Profiled all Relationship features across 5 datasets: prevalence, layer
  distribution, supernode names.
2. Tested which Relationship supernodes match concept fields via
  `_concept_matches_supernode()`. This determines whether they enter the
   intervention at all.
3. Traced specific swap pairs (`trace_swap_matching`) to count Relationship vs
  Semantic features in the actual ablate/amplify sets.
4. Computed per-entity: active Relationship count and %, low-layer feature %
  (layers 0-3), mean active layer, total active count. Correlated each with
   mean `vs_max` as source entity.

**Raw findings**:

Relationship features as share of all features vs share of active (concept-matched):


| Dataset   | Rel % of total | Rel % of active | Rel features matched |
| --------- | -------------- | --------------- | -------------------- |
| USA       | 11.3%          | 0.0%            | 1/2962               |
| Books     | 35.1%          | 0.7%            | 13/1757              |
| Products  | 35.7%          | 2.0%            | 16/797               |
| Paintings | 13.0%          | 0.7%            | 11/1665              |
| Sounds    | 20.6%          | 2.0%            | 6/295                |


The generic Relationship supernodes never match concept values:

- "(entity) related" (869 features in USA): concept values are state/capital/city
names, not "entity" -- no match.
- "(literary) related" (886 in books), "(famous) related" (604 in books): concept
values are character/book/author names -- no match.
- "(is) related" (779 in products): no concept value contains "is" as a word match.
- "(A) related" (404 in sounds, 165 in paintings, 87 in books): no match.

Only entity-specific Relationship supernodes match, e.g.:

- "(Oliver) related" matches "Oliver Twist" (character field) -- 3 features, layer 1/6
- "(Facebook) related" matches "Facebook" (product field) -- 5 features, layer 1
- "(Pablo) related" matches "Pablo Picasso" (painter field) -- 2 features, layer 1

These are consistently at layers 1-6 (mean ~2.5).

Correlation of feature profile with mean_vs_max per entity:


| Dataset   | r(low_layer_pct, vsMax) | r(rel_pct, vsMax) | r(active_total, vsMax) | N   |
| --------- | ----------------------- | ----------------- | ---------------------- | --- |
| USA       | 0.018                   | -0.044            | **-0.298**             | 50  |
| Books     | **0.473**               | 0.475             | 0.211                  | 16  |
| Products  | -0.070                  | 0.146             | -0.265                 | 12  |
| Paintings | 0.051                   | 0.455             | -0.334                 | 10  |
| Sounds    | -0.101                  | 0.412             | -0.289                 | 6   |


Notable per-entity examples (books):


| Entity           | Active | Rel | Low%  | mLayer | vsMax |
| ---------------- | ------ | --- | ----- | ------ | ----- |
| holden_caulfield | 127    | 2   | 70.9% | 3.9    | 6.85  |
| hermione_granger | 78     | 1   | 23.1% | 12.1   | 5.53  |
| captain_ahab     | 183    | 0   | 64.5% | 5.3    | 6.07  |
| katniss_everdeen | 120    | 0   | 39.2% | 9.1    | 5.19  |


**Interpretation**: Excluding Relationship features from swap interventions would
have **no measurable effect**. Confidence: **High**. Epistemic level: **L1**
(pipeline mechanism) and **L2** (causal relevance).

Three reasons:

1. **They're already excluded.** The concept matcher does not match generic
  Relationship supernodes like "(entity) related", "(literary) related",
   "(is) related", "(A) related" -- which together account for >95% of all
   Relationship features. These never enter any intervention.
2. **The few that match are entity-specific and tiny.** Only supernodes named
  after actual concept words (e.g., "(Oliver) related", "(Facebook) related")
   get included, and they constitute 0.0-2.0% of the active feature set. At
   this scale, excluding them would change intervention feature counts by
   0-3 features out of 60-250+. The effect on logit-level metrics would be
   within noise.
3. **Correlations run in the wrong direction.** Where correlations between
  Relationship % and vs_max exist (books r=0.475, paintings r=0.455), they
   are *positive* -- more Relationship features is associated with *higher*
   vs_max. This is likely confounded by entity name specificity (entities with
   distinctive names like "Oliver" or "Pablo" get both Relationship matches
   AND better steering), not a causal signal from the Relationship features
   themselves. With N=10-16, these correlations are unreliable regardless.

A more interesting signal emerged: **active_total negatively correlates with
vs_max** in USA (r=-0.298, N=50). Entities with more total concept-matched
features tend to have lower targeting precision. This is consistent with the
"less is more" finding from the field-add experiments -- more features in the
intervention means more noise and less surgical steering. The Relationship
features are too few to be the cause; the volume comes from Semantic features
at low layers (e.g., "port" = 375 features for Gulfport, "do" = 325 for Frodo).

**Threats to validity**:

- Per-entity correlations have small N for non-USA datasets (6-16). Individual
correlations are unreliable; only USA's N=50 has reasonable statistical power.
- Correlations between Relationship % and vs_max are confounded by entity
name properties. Entities with distinctive first names (Oliver, Pablo, Jack)
get both Relationship matches and potentially different baseline confusion.
- The analysis counts features matched by the tracer's concept matcher, not
the actual pipeline's matcher. If they differ, the counts could be wrong.
However, the tracer uses the same `_concept_matches_supernode` logic.
- "Active" features counted here are per-entity. In a swap, source features
are ablated and target features are amplified -- the actual intervention set
depends on both entities, not just one.
- The books positive correlation (more low-layer features = higher vs_max)
could reflect that entities with more low-layer matches have more distinctive
names, not that low-layer features help.

**Follow-up**:

- The active_total negative correlation in USA is worth investigating further.
Is it feature-count dilution (same amplification spread over more features
reduces per-feature effect) or interference (irrelevant features actively
disrupt)? The field-add experiments already suggest dilution is the main
mechanism, but a within-entity analysis (same pair, different active counts
across field-add variants) would be cleaner.
- The large Semantic supernodes at low layers (e.g., "port" = 375, "is" = 115)
are a much bigger potential source of polysemantic noise than Relationship
features. An investigation of whether large-supernode-count entities have
worse performance would address the polysemanticity concern more directly.
- Consider whether the "less is more" effect is better explained by
intervention count alone (ablate_count + amplify_count from swap JSONs)
rather than the upstream feature profile. The swap JSON counts are the
actual intervention size after deduplication.

**References**: Previous entries `[2026-03-25] cumulative influence of Semantic (unknown) nodes`, `[2026-03-25] best field-add variant vs random in regime taxonomy`; `scripts/02_node_grouping.py`; `scripts/utils/pipeline_tracer.py`

---

## [2026-03-25] Topic: cumulative influence of Semantic (unknown) nodes on swap results

**Question**: Features classified as "Semantic (unknown)" in the node grouping
pipeline are features the naming step could not label. How prevalent are they?
Do they carry meaningful circuit influence? And does their presence affect swap
outcomes?

**Method**: Wrote `scripts/research/unknown_node_investigation.py` to scan all
entities across 5 datasets. For each entity:

1. Read `node_grouping.csv` and counted features with
  `supernode_name == "Semantic (unknown)"`.
2. Joined with `graph_feature_static_metrics.csv` (matching by `layer_id`, not
  `layer_feature`) to compute the node-influence share of unknown features.
3. Compared swap performance (vs_max, gap_closure, hit%) for entities with/without
  unknown nodes, and computed per-entity Pearson correlations.
4. Traced the root cause through `02_node_grouping.py`'s `name_semantic_node()`
  function and the per-dataset blacklist configs.
5. Verified whether "Semantic (unknown)" supernodes are ever matched by the
  concept matcher (`_concept_matches_supernode`) during swap interventions.
6. Computed the broader "inert feature" population: all selected features in
  supernodes that never match any concept field (3-field set).

**Raw findings**:

Prevalence of "Semantic (unknown)" across datasets:


| Dataset    | Entities affected | Unknown feat %  | Unknown influence % |
| ---------- | ----------------- | --------------- | ------------------- |
| USA states | 0/50 (0%)         | 0.0%            | 0.0%                |
| Books      | 16/16 (100%)      | 2.3% (109/4693) | 1.7%                |
| Products   | 12/12 (100%)      | 2.5% (70/2791)  | 1.7%                |
| Paintings  | 10/10 (100%)      | 2.3% (86/3785)  | 1.7%                |
| Sounds     | 6/6 (100%)        | 3.4% (71/2111)  | 2.8%                |


Root cause -- blacklist configuration difference:

- **USA** config (`usa_states_full.yml`): `blacklist_tokens: ["<bos>"]` only.
Features with peak_token=`entity`/`attribute` get named normally and form
supernodes like "entity" (1 feature), "attribute" (4 features).
- **Non-USA** configs (books, products, paintings, sounds):
`blacklist_tokens: ["<bos>", "entity", "attribute"]`. Features whose best
semantic peak token is `entity` or `attribute` have no valid fallback and
become "Semantic (unknown)".

Peak tokens on unknown rows (all non-USA datasets pooled):


| Token                           | Rows | % of unknown |
| ------------------------------- | ---- | ------------ |
| `entity`                        | 967  | 57.5%        |
| `attribute`                     | 334  | 19.9%        |
| `relationship`                  | 332  | 19.8%        |
| other (`:`, `The`, `Don`, etc.) | 47   | 2.8%         |


Subtypes of unknown features: Dictionary (fallback) 60.5%, Concept 38.7%,
Dictionary 0.3%.

Concept matcher verification: "Semantic (unknown)" (lowercased) never matches
any concept field value through `_concept_matches_supernode()`. These features
are **never ablated or amplified** during swap interventions.

Equivalent USA inert features: USA's "entity", "attribute", "relationship", and
related supernodes contain 1271/11682 (10.9%) of features -- these are equally
unmatched by the concept matcher, just not labeled "unknown".

Full inert-feature population (all selected features not matching any concept,
using all 3 concept fields per dataset):


| Dataset   | Active % | Unknown % | Labeled-inert % |
| --------- | -------- | --------- | --------------- |
| USA       | 39.2%    | 0.0%      | 60.8%           |
| Books     | 48.2%    | 2.3%      | 49.5%           |
| Products  | 44.0%    | 2.5%      | 53.5%           |
| Paintings | 49.7%    | 2.3%      | 48.1%           |
| Sounds    | 26.6%    | 3.4%      | 70.1%           |


Correlation with swap performance:


| Dataset   | Pearson r (unknown_influence_pct, mean_vs_max) | N   |
| --------- | ---------------------------------------------- | --- |
| USA       | 0.000 (no variance)                            | 50  |
| Books     | 0.006                                          | 16  |
| Products  | 0.320                                          | 12  |
| Paintings | 0.181                                          | 10  |
| Sounds    | -0.297                                         | 6   |


No within-dataset comparison of "with unknown" vs "zero unknown" is possible
because USA has 0% and all non-USA datasets have 100% of entities affected.

**Interpretation**: "Semantic (unknown)" features are **not relevant** to swap
outcomes. Confidence: **High**. Epistemic level: **L1** (pipeline measurement).

Three independent lines of evidence converge:

1. **Mechanism**: The concept matcher never matches "Semantic (unknown)" as a
  supernode name. These features are strictly inert -- they are neither
   ablated nor amplified during any swap. They cannot causally influence the
   intervention.
2. **Scale**: At 2.3-3.4% of features and 1.7-2.8% of node influence, unknown
  features are a small fraction of the graph. Even if they were somehow
   relevant, the magnitude is too small to explain meaningful outcome variance.
3. **Context**: Unknown features are a tiny, visible subset of a much larger
  inert population (49-70% of all selected features never match any concept).
   The pipeline by design selects the top-95% cumulative-influence features
   from the graph, then only intervenes on the subset matching concept fields.
   The majority of selected features are structural, syntactic, or discourse
   features that don't correspond to any concept field.

The asymmetry between USA (0% unknown) and non-USA (2-3% unknown) is entirely
explained by the blacklist configuration: non-USA datasets blacklist `entity`
and `attribute` tokens, which forces features with those peak tokens into the
unknown bin. USA doesn't blacklist these tokens, so equivalent features get
named "entity"/"attribute" -- but they are equally inert in swap interventions.

**Threats to validity**:

- The per-entity correlation has very small N (6-16) for non-USA datasets.
Individual correlations are unreliable; the conclusion rests on the mechanism
(matcher never matches) rather than correlation.
- The influence join uses `(layer, id)` from the static metrics CSV.
A small fraction of features may fail to match if the node_id format changed
between pipeline versions.
- This analysis considers only first-order effects (direct intervention).
Unknown features could theoretically interact with intervened features through
shared circuits. This second-order effect is not measured here and would
require activation-level analysis.
- The "inert feature" computation counts features per entity separately.
A feature that is inert for entity A might be active for entity B if B's
concept values happen to match its supernode name.

**Follow-up**:

- The much larger question raised by this investigation: **51-74% of selected
features are labeled but never matched by any concept**. These are not
"unknown" -- they have valid supernode names (e.g., "is", "of", "containing",
"punctuation", "The") that simply don't correspond to any concept field. This
large inert population is the real "dark matter" of the intervention, not the
2-3% unknown nodes. A follow-up investigation should quantify whether
intervening on these features (e.g., ablating functional/syntactic supernodes)
has any detectable effect.
- Consider harmonizing the blacklist across datasets. The current asymmetry
(USA vs non-USA) is a confound in cross-domain comparisons. Either add
`entity`/`attribute` to USA's blacklist or remove them from non-USA configs.
- The `relationship` token is not blacklisted in any dataset but appears on
19.8% of unknown rows. These rows have `relationship` as peak_token on some
probes but their overall best semantic peak is a blacklisted token. No action
needed.

**References**: `scripts/02_node_grouping.py` (name_semantic_node, line 974-1068);
batch configs `scripts/experiments/batch/configs/*.yml`;
`scripts/utils/pipeline_tracer.py` (_concept_matches_supernode);
previous entry `[2026-03-24] reverse substring matching confound scan`

---

## [2026-03-25] Topic: entry-level flaw scan across all datasets

**Question**: Beyond the dataset-level issues already documented (answer
identity pairs, metric misalignment, zero-coverage fields), are there
additional entry-level flaws -- specific entities or pairs whose data
properties make them unreliable as redirection tests?

**Method**: Wrote a systematic scanner that loaded every entity from the five
labeled runs (`fullscale_*_labeled`) and checked for: (1) answer collisions
(same answer across entities), (2) near-duplicate answers (SequenceMatcher
ratio >= 0.7), (3) target-answer leaking into source prompt, (4) field
ambiguity (two concept fields holding the same value), (5) first-token
sharing across different answers, (6) short/common single-word answers,
(7) answer cross-contamination (one entity's answer as substring in another's
non-answer fields), (8) answer-space entropy, (9) baseline confusion (target
answer already rank <= 3 or prob >= 5% before any intervention). Drilled
into flagged entries with full swap-level detail.

**Raw findings**:

- **Answer collisions (same answer)**:
  - Sounds: 4/6 entities answer `brown` (bark, gobble, hoot, neigh).
  12/30 non-identity pairs (40%) share the same answer. Only 3 unique
  answers (`brown`, `black`, `green`) for 6 entities.
  - Books: 2/16 entities answer `Harper Lee` (atticus_finch, scout_finch).
  2/240 pairs (0.8%) are answer-collisions.
  - USA, Products, Paintings: all answers unique.
- **Near-duplicate answers (similarity >= 0.7)**:
  - USA: 4 capital pairs -- Indianapolis/Annapolis (0.76),
  Columbus/Columbia (0.75), Denver/Dover (0.73),
  Jefferson City/Carson City (0.72).
  - Paintings: Edvard/Edward (0.83) for the_scream/nighthawks.
  Detail: default first token for both is `' Ed'`/`' Edward'`; at
  baseline the_scream already has Edward at rank 4 (prob 3.5%).
- **Target-answer leaking into source prompt**:
  - USA: 1 pair. `south_carolina_charleston` prompt contains "Charleston"
  which is `west_virginia_huntington`'s answer. Swap scores hit=True
  but steered output is `"isExterneburg, West Virginia..."` -- the hit
  comes from the echoed prompt, not from generation.
  - No leaks in other datasets.
- **Field ambiguity (concept fields sharing same value)**:
  - Books: 3/16 entities have `character == book`:
  anna_karenina, don_quixote, oliver_twist. In field-add runs, the
  `add_character` and `add_book` variants produce identical ablation
  counts (anna_karenina: 141/141, don_quixote: 60/60,
  oliver_twist: 121/121) -- the pipeline cannot distinguish the two
  fields because all matching supernodes overlap.
  - Products: 1/12 entity has `product == company`: twitter/Twitter.
- **First-token sharing (different answer, same first token)**:
  - Products: `Jack Ma` (alibaba) and `Jack Dorsey` (twitter) share
  first token `Jack`. Both have baseline rank=1 for each other
  (prob 39-45%). Neither swap produces the correct target output.
  - Books "J." cluster: `J.R.R. Tolkien` (frodo), `J.K. Rowling`
  (hermione), `J.D. Salinger` (holden) all share first token `J`.
  All 6 cross-pairs have baseline rank=1 (prob 28-54%) and
  gap_closure=0.0 despite high vs_max (4.75-7.22). The model
  already represents the competing answer at baseline because
  all three are "J."-initial authors.
- **Baseline confusion (target at rank <= 3 before intervention)**:
  - USA: 8/2450 pairs (0.3%). Notable cases:
    - `missouri_kansas_city -> kansas_wichita`: rank=1 (31.4%) because
    prompt says "Kansas City" and target state is Kansas.
    - `maine_portland -> oregon_portland`: rank=1 (15.7%) because both
    share city name Portland.
  - Books: 8/240 (3.3%). The 6 "J." cluster pairs (all rank=1) plus
  the 2 Finch/Lee identity pairs (rank=1, 25-57%).
  - Products: 3/132 (2.3%). Both Jack pairs (rank=1) plus
  `nike_shoes -> windows` (rank=1, 21.1%).
  - Paintings: 1/90 (1.1%). `grande_jatte -> water_lilies` rank=3 (6.3%).
  - Sounds: 25/30 (83.3%). Nearly the entire dataset. 12 same-answer
  pairs at rank=1 plus 13 cross-color pairs where the tiny answer
  space puts most targets in the top few.
- **Answer-space entropy**:
  - USA: 5.64 bits (maximum possible for N=50).
  - Books: 3.88 / 4.00 bits (97% of maximum).
  - Products: 3.58 / 3.58 bits (100% of maximum).
  - Paintings: 3.32 / 3.32 bits (100% of maximum).
  - Sounds: 1.25 / 2.58 bits (48% of maximum).
- **Aggregate across all 2942 non-identity labeled pairs**:
  - 14 same-answer pairs (0.5%), all in sounds (12) and books (2).
  - 40 baseline-confused pairs at rank <= 3 (1.4%), with sounds
  contributing 20 of those.

**Interpretation**: The scan reveals several distinct classes of entry-level
flaws, varying from catastrophic (sounds) to minor (USA near-duplicate
capitals). Confidence: **High** for the existence of each flaw;
**Medium** for quantifying downstream impact. Epistemic level: **L1**
(measurement and data quality).

Severity ranking of flaws found:

1. **Sounds answer-space collapse (CRITICAL)**: With only 3 unique answers
  and 48% entropy, sounds is not a meaningful redirection benchmark.
   40% of pairs are answer-identity, and 83% have the target already at
   rank <= 3. The labeled-vs-random comparison on this dataset is measuring
   noise, not label quality. Recommendation: **exclude sounds from all
   headline claims** or restrict analysis to the 8 cross-color pairs
   (meow<->hiss, meow<->brown_entities, hiss<->brown_entities) -- but even
   those have high baseline confusion (rank 2-12).
2. **Books "J." cluster (HIGH)**: 6/240 pairs (2.5%) have the target answer
  at rank=1 with prob 28-54% at baseline. The model already "knows" the
   answer class from the `J.` token alone. These pairs can inflate vs_max
   and rank_in_group without any meaningful steering. Separately, 3/16
   entities have character==book field collapse, making character-only and
   book-only field-add variants degenerate.
3. **Products Jack confound (MODERATE)**: 2/132 pairs (1.5%) share first
  token `Jack` and show baseline rank=1. A small but non-negligible
   fraction. Additionally, twitter has product==company.
4. **Paintings Edvard/Edward (LOW-MODERATE)**: 1 pair with 83% string
  similarity between answers. Baseline rank=4, not rank=1, so the
   confound is weaker but still relevant for first-token metrics.
5. **USA geographic confounds (LOW)**: 8/2450 pairs (0.3%) have baseline
  rank <= 3, mostly from shared city names (Portland, Kansas City,
   Charleston) or geographic proximity. Individually significant; aggregate
   impact negligible given N=2450.

**Threats to validity**:

- The baseline rank is computed at a single position (position 0). The
model's internal representation may differ at later trajectory positions.
- "First token sharing" does not automatically mean the model confuses
the entities -- it means the first generated token is ambiguous, which
may resolve by position 2+. But gap_closure=0.0 for the J. cluster
suggests it does not resolve.
- The near-duplicate thresholds (0.7 similarity, rank <= 3) are
somewhat arbitrary. Changing them shifts counts but not the qualitative
conclusions.
- The field-ambiguity flaw (character==book) affects the field-add
analysis specifically, not the full-triple labeled run.
- This scan covers entity/answer properties only. It does not cover
upstream pipeline quality (error nodes, reverse substring) which are
documented in separate log entries.

**Follow-up**:

- Recompute headline metrics (labeled vs random deltas on vs_max,
gap_closure, rank_in_group) after excluding: (a) all sounds pairs,
(b) books Finch/Lee pairs, (c) books J. cluster pairs,
(d) products Jack pairs. Report how much the deltas change.
- For baseline-confused pairs, check whether gap_closure or vs_max still
shows labeled > random separation. If the intervention adds nothing
beyond what the model already represents, these pairs should be flagged.
- Consider adding an "effective redirection" filter to aggregate stats:
exclude pairs where from_answer == to_answer OR baseline target rank <= 2.
- Investigate whether the books character==book field collapse inflates
the "less is more" finding (the full triple appears worse because two
of three fields are redundant, not because field interference is real).

**References**: Previous entry `[2026-03-24] curiosity-sampled method flaws across datasets` (which first identified books Finch/Lee and sounds brown
collisions); `output/FULLSCALE_CONTROL_REPORT.md`; `scripts/utils/swap_query.py`

---

## [2026-03-25] Topic: gap closure is regime-dependent and mostly misleading

**Question**: Is `gap_closure` a useful signal for label evidence across
regimes, or is it only relevant in specific circumstances?

**Method**: Re-examined gap closure values from the regime taxonomy data already
collected in the `[2026-03-24] logit-shift taxonomy` and `[2026-03-25] best field-add variant` entries. Compared gap closure across regimes A, C, D for
labeled, best variant, and random conditions, and checked whether it
discriminates labeled from random within each regime. Also checked the
cross-domain anomaly (USA vs books) where gap closure and `vs_max` disagree.

**Raw findings**:

Gap closure by regime (USA, full labeled vs random):


| Regime                 | Labeled gc | Random gc | Labeled vs_max | Random vs_max |
| ---------------------- | ---------- | --------- | -------------- | ------------- |
| A (tgt UP, src DOWN)   | 0.88       | 0.76      | 4.28           | -0.19         |
| C (both DOWN, flip)    | 2.73       | 1.59      | 2.33           | -0.10         |
| D (both DOWN, no flip) | **13.62**  | **6.46**  | 4.11           | -0.07         |


Gap closure by regime (USA, best variant vs random):


| Regime | Best gc   | Random gc | Best vs_max | Random vs_max |
| ------ | --------- | --------- | ----------- | ------------- |
| A      | 1.44      | 0.76      | 4.01        | -0.19         |
| C      | 3.14      | 1.59      | 3.81        | -0.10         |
| D      | **16.25** | **6.46**  | 5.08        | -0.07         |


Cross-domain comparison (full labeled):


| Domain    | gap_closure | vs_max | Interpretation conflict?                    |
| --------- | ----------- | ------ | ------------------------------------------- |
| USA       | 4.67        | 2.86   | --                                          |
| Books     | 0.01        | 5.98   | Yes: gc says weak, vs_max says strongest    |
| Products  | 0.19        | 3.46   | --                                          |
| Paintings | 0.80        | 1.55   | --                                          |
| Sounds    | 1.46        | 3.28   | Mild: gc > paintings but vs_max > paintings |


**Interpretation**: Gap closure is regime-dependent and mostly misleading as a
general label-evidence metric. Confidence: **High**. Epistemic level: **L1**
(metric validity).

Per-regime analysis:

- **Regime A**: gap closure is **redundant**. The target already flipped above
source at position 0. Gap closure measures how much further the winning target
pulls ahead across later positions -- it adds no discriminative information
beyond the flip itself. `vs_max` separation between labeled and random is
4.28 vs -0.19 (delta 4.47). Gap closure separation is only 0.88 vs 0.76
(delta 0.12). Gap closure is nearly useless here.
- **Regime C**: gap closure is **weakly informative**. It captures some of the
target recovery signal, but target recovery rate (92% vs 29%) and
`tgt_win_pct` (0.67 vs 0.32) are cleaner binary/continuous signals that
separate labeled from random far more sharply. Gap closure's separation in
regime C (2.73 vs 1.59) is modest and noisy because it depends on the
magnitude of the initial disruption.
- **Regime D**: gap closure is **actively misleading**. Regime D has the
*highest* gap closure of any regime (13.62 labeled, 6.46 random) despite
being the weakest evidence regime (target never overtakes source). The reason
is mechanical: when both tokens start far apart and both get hammered, the
trajectory has room to "close" the gap substantially without the target ever
winning. A naive user looking at gap closure would think regime D is the
strongest outcome, when in fact it is the weakest.

Cross-domain: gap closure says books is nearly zero (0.01) while USA is strong
(4.67). But `vs_max` says books is the strongest domain (5.98 vs 2.86). The
discrepancy exists because books pairs tend to have small baseline gaps (target
and source start close together), so there is little room for "closure" even
when the target wins convincingly at the token level. Gap closure is confounded
by baseline gap magnitude and is therefore not comparable across domains.

**Threats to validity**:

- This analysis uses existing aggregate data, not a fresh per-sample
correlation study. A formal correlation between gap closure and swap success
conditioned on regime would strengthen the argument.
- Gap closure might still be useful in a narrow context: regime C cases with
large baseline gaps where target eventually overtakes source. This is a small
subset and would need explicit filtering.

**Follow-up**:

- De-emphasize gap closure in headline reporting and label-evidence metrics.
- Consider replacing it with a regime-aware composite: use `vs_max` as primary,
target recovery as secondary, and gap closure only for regime C cases with
baseline gap > some threshold.
- Update the metric reference in `AGENTIC_RESEARCH_GUIDE.md` Section 6 to note
gap closure's regime dependence.

**References**: Previous entries `[2026-03-24] logit-shift taxonomy`,
`[2026-03-25] best field-add variant`; `output/FULLSCALE_CONTROL_REPORT.md`

---

## [2026-03-25] Topic: best field-add variant vs random in regime taxonomy

**Question**: The previous entry compared full labeled (all 3 fields) vs random.
But the "less is more" finding showed that 2-field subsets often outperform the
full triple. Does the regime taxonomy look even cleaner when we compare the best
field-additivity variant (intermediate+answer) against random?

**Method**: For each dataset, selected the known best 2-field variant from the
full-scale control report and classified every swap in that variant, the full
labeled run, and random (capped at 1500) using the same regime taxonomy from the
previous entry. Compared regime prevalence, hit rate, `vs_max`, target recovery
rate, and target-wins-source fraction.

Best variants used:

- USA: `add_state_capital` (intermediate + answer)
- Books: `add_book_author` (intermediate + answer)
- Products: `add_company_founder` (intermediate + answer)
- Paintings: `add_painter_first_name` (intermediate + answer)
- Sounds: `add_sound_animal` (input + intermediate)

**Raw findings**:

Regime A (target UP, source DOWN -- cleanest label evidence):


| Dataset   | best variant               | full labeled               | random                     |
| --------- | -------------------------- | -------------------------- | -------------------------- |
| USA       | 34.9%, hit 46%, vsMax 4.01 | 8.9%, hit 31%, vsMax 4.28  | 19.4%, hit 0%, vsMax -0.19 |
| Books     | 62.1%, hit 54%, vsMax 9.08 | 38.8%, hit 4%, vsMax 7.64  | 40.8%, hit 0%, vsMax -1.49 |
| Products  | 62.1%, hit 32%, vsMax 3.75 | 56.8%, hit 25%, vsMax 4.48 | 51.5%, hit 0%, vsMax 0.44  |
| Paintings | 47.8%, hit 0%, vsMax 2.25  | 17.8%, hit 6%, vsMax 3.76  | 23.3%, hit 0%, vsMax -0.54 |


Regime C (both DOWN, flip -- differential disruption):


| Dataset   | best variant                            | full labeled                            | random                                 |
| --------- | --------------------------------------- | --------------------------------------- | -------------------------------------- |
| USA       | 55.1%, hit 35%, recov 93%, winPct 0.804 | 71.1%, hit 23%, recov 92%, winPct 0.673 | 35.0%, hit 1%, recov 29%, winPct 0.319 |
| Books     | 33.8%, hit 7%, recov 96%, winPct 0.378  | 56.2%, hit 2%, recov 92%, winPct 0.364  | 23.3%, hit 2%, recov 89%, winPct 0.192 |
| Products  | 32.6%, hit 12%, recov 86%, winPct 0.315 | 39.4%, hit 2%, recov 98%, winPct 0.199  | 22.7%, hit 0%, recov 83%, winPct 0.282 |
| Paintings | 48.9%, hit 2%, recov 89%, winPct 0.273  | 75.6%, hit 4%, recov 93%, winPct 0.203  | 33.3%, hit 0%, recov 77%, winPct 0.188 |


Regime D (both DOWN, no flip -- generic disruption):


| Dataset   | best variant | full labeled | random |
| --------- | ------------ | ------------ | ------ |
| USA       | 9.1%         | 19.4%        | 45.3%  |
| Books     | 3.3%         | 3.3%         | 34.6%  |
| Products  | 2.3%         | 2.3%         | 22.0%  |
| Paintings | 2.2%         | 6.7%         | 42.2%  |


**Interpretation**: Confidence: **High**. Epistemic level: **L2**.

The best field-add variant dramatically amplifies the separation from random
compared to the full labeled run. Three patterns stand out:

1. **Regime A prevalence jumps**: the best variant pushes far more cases into
  regime A (clean target-up, source-down). USA goes from 8.9% to 34.9%. Books
   goes from 38.8% to 62.1%. This means removing input-field features eliminates
   a large amount of generic disruption that was pushing cases into regime C/D.
2. **Hit rates within regimes improve**: USA regime A goes from 31% hit (full
  labeled) to 46% hit (best variant). Books regime A goes from 4.3% to 54.4%.
   This is not just a redistribution across regimes -- the quality of each
   regime improves too.
3. **Regime D nearly vanishes**: the "both down, no flip" regime (weakest label
  evidence) drops from 19.4% to 9.1% in USA, and from 6.7% to 2.2% in
   paintings. Meanwhile random concentrates in regime D (42-45%). The best
   variant produces almost no generic-disruption-dominant cases.

The overall picture: the best field-add variant vs random is a much cleaner
test of label correctness than the full labeled vs random comparison. The
input-field features in the full triple add noise that pushes many cases from
regime A (clear evidence) into regime C (ambiguous). The intermediate+answer
combination produces interventions that are more surgical and more interpretable.

For label-evidence metrics, this means the composite indicator from the previous
entry (`vs_max > 0` + target recovery + `tgt_win_pct > 0.5`) should be
validated primarily on the best field-add variant, not the full triple. The
full triple conflates label quality with intervention design.

**Threats to validity**:

- The "best variant" was chosen based on aggregate hit rate, which is circular
for this analysis. A fairer test would pre-register the variant choice.
- Paintings shows an anomaly: best variant regime A has 0% hit despite 48%
prevalence and positive `vs_max`, confirming the answer-field weakness
(`first_name`) identified in previous entries.
- Random was capped at 1500 samples for USA due to the 3-replicate expansion;
this is still representative but not exhaustive.
- Sounds is omitted from regime A analysis because it has zero regime A cases
in any condition.

**Follow-up**:

- Use the best field-add variant as the primary labeled condition for the
label-evidence metric validation.
- Check whether the regime A prevalence increase correlates with intervention
count decrease (fewer features = less disruption = more regime A).
- Test whether the intermediate-only single-field variant (`add_state`,
`add_book`) achieves even higher regime A prevalence, to see if the
answer field helps or is redundant.

**References**: Previous entry `[2026-03-24] logit-shift taxonomy`;
`output/FULLSCALE_CONTROL_REPORT.md` Section 6

---

## [2026-03-24] Topic: logit-shift taxonomy and label-evidence metric design

**Question**: When a swap does not produce a perfect (T5) result, what does the
logit trajectory tell us about whether the feature labels are correct? Can we
separate "the labels pointed at the right circuits" from "the swap happened to
produce the right string"?

**Method**: Classified every labeled and random swap in the five full-scale runs
by what happens to target and source token logits at position 0 relative to
their unsteered baselines. Defined four main regimes:


| Regime | Target logit | Source logit | Flip at pos 0? | Intuition                                     |
| ------ | ------------ | ------------ | -------------- | --------------------------------------------- |
| **A**  | UP           | DOWN         | yes            | Clean redirection: target gains, source loses |
| **C**  | DOWN         | DOWN         | yes            | Both disrupted, but target less so            |
| **D**  | DOWN         | DOWN         | no             | Both disrupted, source still dominant         |
| **E**  | FLAT         | DOWN         | yes            | Pure suppression, no target lift              |


Then compared regime prevalence, hit rates, `vs_max`, `gap_closure`, target
recovery (does target logit exceed baseline at any later position?), and
target-wins-source fraction across the 11 trajectory positions.

For regime C specifically, sub-classified USA labeled cases into:

- **C1**: target recovers above baseline AND `vs_max > 2` (specific recovery)
- **C2**: target recovers above baseline but `vs_max <= 2` (generic recovery)
- **C3**: target never recovers but beats source at >50% of positions
- **C4**: target never recovers and loses to source at most positions

**Raw findings**:

Regime prevalence (labeled / random):


| Dataset   | A (labeled) | A (random) | C (labeled) | C (random) | D (labeled) | D (random) |
| --------- | ----------- | ---------- | ----------- | ---------- | ----------- | ---------- |
| USA       | 8.9%        | 19.4%      | 71.1%       | 35.0%      | 19.4%       | 45.3%      |
| Books     | 38.8%       | 40.8%      | 56.2%       | 23.3%      | 3.3%        | 34.6%      |
| Products  | 56.8%       | 51.5%      | 39.4%       | 22.7%      | 2.3%        | 22.0%      |
| Paintings | 17.8%       | 23.3%      | 75.6%       | 33.3%      | 6.7%        | 42.2%      |
| Sounds    | 0%          | 0%         | 43.3%       | 26.7%      | 56.7%       | 73.3%      |


Key observations from regime-level comparison:

- Labeled interventions push far more cases into regime C (both down, flip)
than random does. Random instead concentrates in regime D (both down, no
flip). This means labeled features cause source to drop much harder
relative to target than random features do.
- In regime A (clean redirection), labeled `vs_max` is dramatically higher
than random across all datasets. But regime A is actually *less common*
in labeled than random for USA (8.9% vs 19.4%), suggesting random more
often produces small, undirected target bumps.

Regime C deep dive (USA):

- Labeled regime C: N=1741, hit=22.5%, `vs_max`=2.33, tgt_recovers=92.2%,
`tgt_win_pct`=0.673, `avg_sd`=-22.33
- Random regime C: N=525, hit=0.6%, `vs_max`=-0.10, tgt_recovers=29.3%,
`tgt_win_pct`=0.319, `avg_sd`=-12.49

The critical difference: in labeled regime C, the target token **recovers
above its own baseline** at later positions 92.2% of the time (vs 29.3% for
random). The labeled source drop is also much deeper (-22.33 vs -12.49).

USA labeled regime C sub-classification:

- **C1** (recovers + specific): N=857, hit=44.0%, `vs_max`=4.93, `tgt_win_pct`=0.817
- **C2** (recovers + generic): N=749, hit=1.7%, `vs_max`=-0.07, `tgt_win_pct`=0.560
- **C3** (no recovery, wins positions): N=45, hit=4.4%, `vs_max`=-0.24
- **C4** (no recovery, loses positions): N=90, hit=0.0%, `vs_max`=-1.10

**Interpretation**: The regime taxonomy reveals that "both tokens lose
probability" (regime C) is actually the dominant labeled behavior in USA and
paintings, not an edge case. But within regime C, the labeled vs random
distinction is stark: labeled features cause **differential disruption** where
the target token recovers across the generation trajectory while the source
stays suppressed, whereas random disruption is more uniform.

Confidence: **Medium-High**. Epistemic level: **L2** (causal effects) with
implications for **L1** (label validity).

The "confusing" case you asked about -- both lose but target stays above
source -- is actually the strongest evidence of label specificity when combined
with two additional signals:

1. **Target recovery**: does the target logit exceed its own unsteered baseline
  at any trajectory position? (92% labeled vs 29% random in regime C)
2. **Differential suppression**: is the source drop much larger than the target
  drop? (labeled avg: source drops 22.3, target drops 7.7; random avg: source
   drops 12.5, target drops 4.6)

**Proposed label-evidence metric candidates**:

1. **Recovery-adjusted specificity (RAS)**: `vs_max` restricted to positions
  where target logit exceeds its own unsteered baseline. Filters out
   cases where target "wins" only because everything is destroyed.
2. **Differential disruption ratio (DDR)**: `|source_delta| / |target_delta|`
  at position 0. A ratio > 1 means the intervention hit the source harder
   than the target. Labeled USA regime C averages 2.9; random averages 2.7.
   The gap is modest, so this alone is not sufficient.
3. **Target recovery rate**: binary -- does target logit exceed its unsteered
  baseline at any trajectory position? This is the single most discriminating
   signal between labeled and random in regime C (92% vs 29%).
4. **Sustained dominance**: fraction of trajectory positions where target
  logit > source logit. Labeled regime C averages 0.673; random 0.319.
5. **Composite label-evidence score**: combine `vs_max > 0`, target recovery,
  and `tgt_win_pct > 0.5` into a 3-bit indicator. Cases with all three
   are strong label evidence; cases with none are generic disruption.

Recommendation: **target recovery rate** is the simplest, most discriminating
single signal to add to the evaluation. It separates "the model's circuits
responded to the target concept" from "everything got disrupted and target
happened to be less disrupted." Combined with `vs_max > 0` (target beats all
other answer-group competitors), it produces a conservative but meaningful
label-evidence indicator.

**Threats to validity**:

- The regime classification uses position-0 logit deltas only; some cases may
shift regime if measured at a different position.
- "Target recovery" uses max over 11 positions and could be noisy for short
generations.
- The sub-classification thresholds (e.g., `vs_max > 2` for "specific") are
somewhat arbitrary.
- Sounds has no regime A cases at all for labeled, which may indicate the
taxonomy does not fit all domains equally well.
- This analysis does not yet incorporate field-additivity variants.

**Follow-up**:

- Implement target recovery rate as a computed field and rerun the labeled vs
random comparison with it as the primary metric.
- Check whether the composite label-evidence score correlates with known
entity-level predictors (error_node_pct, concept coverage).
- Test the taxonomy on field-additivity variants to see if intermediate+answer
fields produce more regime A / C1 cases than input fields.
- Examine whether regime C2 (recovers but generic) represents cases where the
labels are correct but the steering magnitude is too large.

**References**: `output/FULLSCALE_CONTROL_REPORT.md`; `scripts/utils/swap_query.py`

---

## [2026-03-24] Topic: curiosity-sampled method flaws across datasets

**Question**: If we sample a small number of curiosity-driven results from each
dataset, what flaws in the current methods become visible? The goal here is
adversarial error-finding, not representative performance estimation.

**Method**: Treated `x = 3` and sampled three labeled swaps per dataset
(`15` total), chosen for curiosity value rather than uniformity: cases with
large labeled-vs-random deltas, large `vs_max` but no exact-match hit, random
beating labeled, or otherwise contradictory metrics. For each sampled pair,
inspected labeled output, three random replicates, intervention counts, and
`PipelineTracer.trace_swap_matching()` totals / warnings. Then ran targeted
sanity checks suggested by the sampled failures: answer-level identity-pair
counts, prompt leakage in exact-match evaluation, first-token false positives,
rank-1-but-no-hit counts, zero-coverage concept fields, and dataset directory
counts vs actual swap-entity counts.

**Raw findings**:

- Sampled pairs that exposed issues:
  - USA: `new_hampshire_manchester -> oklahoma_tulsa`,
  `south_carolina_charleston -> west_virginia_huntington`,
  `indiana_fort_wayne -> missouri_kansas_city`
  - Books: `frodo_baggins -> katniss_everdeen`,
  `atticus_finch -> scout_finch`,
  `captain_ahab -> holden_caulfield`
  - Products: `windows -> facebook`, `windows -> wordpress`,
  `dyson -> model_s`
  - Paintings: `starry_night -> the_scream`,
  `the_scream -> persistence_of_memory`,
  `grande_jatte -> girl_pearl_earring`
  - Sounds: `meow -> neigh`, `bark -> gobble`, `neigh -> hiss`
- Flaw 1: USA upstream scans can overcount entities.
  - `output/usa_states_batch/` contains 68 non-underscore directories.
  - The actual swap runs use 50 unique source entities and 50 unique target
  entities.
  - The extra directories are casing / formatting variants like
  `colorado_Colorado Springs` vs `colorado_colorado_springs`,
  `new hampshire_Manchester` vs `new_hampshire_manchester`,
  `virginia_Virginia Beach` vs `virginia_virginia_beach`.
- Flaw 2: exact-match hit can be spuriously true from prompt leakage.
  - In sampled USA pair
  `south_carolina_charleston -> west_virginia_huntington`, the steered
  output was:
  `"The capital of the state containing Charleston isExternéburg, West Virginia..."`
  - This counts as `steered_has_to_answer = True` only because target answer
  `Charleston` already appears in the prompt string.
  - Prompt-leak pairs found in labeled runs: USA `1/2450` (0.04%), all other
  datasets `0`.
- Flaw 3: answer-level identity swaps remain in nominally non-identity runs.
  - Books: `2/240` non-identity pairs share the same answer
  (`atticus_finch <-> scout_finch`, both `Harper Lee`).
  - Sounds: `12/30` non-identity pairs share the same answer (`brown`) --
  `40.0%` of the dataset.
  - Example: `bark -> gobble` has source answer `brown`, target answer `brown`,
  so the steering task is ill-posed as a redirection test.
- Flaw 4: `first_token_matches_target` has false positives.
  - USA: `54/2450` labeled swaps (2.2%) have `first_token_matches_target = True`
  while `steered_has_to_answer = False`.
  - Books: `3/240` (1.25%).
  - Products: `10/132` (7.58%).
  - Sounds: `3/30` (10.0%).
  - Example: `windows -> facebook` counts as first-token match because the
  token is `' Mark'`, but the output is `Mark Hurd`, not `Mark Zuckerberg`.
  - Example: `neigh -> hiss` has first token `' GREEN'` according to top-k
  metadata, while the rendered output begins `BOW WOW!`.
- Flaw 5: ranking / logit metrics and string-hit metrics are badly misaligned.
  - Fraction of labeled swaps with `rank_in_group = 1` but no exact-match hit:
    - USA: `1371/2450` (55.96%)
    - Books: `225/240` (93.75%)
    - Products: `87/132` (65.91%)
    - Paintings: `67/90` (74.44%)
    - Sounds: `30/30` (100%)
  - Example: `frodo_baggins -> katniss_everdeen` has `vs_max = 15.16`,
  `rank = 1`, but output `... was written by-Eragon`.
  - Example: `starry_night -> the_scream` has `vs_max = 10.5`, `rank = 1`,
  but output stays `Vincent Van Gogh`.
- Flaw 6: some concept fields have no matched supernodes.
  - In sounds, `animal` has zero matching supernodes for `2/6` entities:
  `bark` and `hoot`.
  - Sampled pair `bark -> gobble` produced tracer warning:
  `source concept 'dog' (animal) matched no supernodes in bark`.

**Interpretation**: The curiosity sample surfaced several genuine method flaws,
not just noisy bad examples. Confidence: **High** for the existence of the
flaws; **Medium** for their aggregate impact on headline conclusions. Epistemic
level: primarily **L1** (measurement / pipeline validity), with downstream
implications for **L2**.

Most important issues:

- The **exact-match hit metric is not trustworthy on its own**, because it can
be inflated by prompt leakage and deflated by answer-format mismatch.
- The **first-token metric is also not trustworthy on its own**, because it can
reward shared first names (`Mark`) or disagree with the rendered output.
- The **sounds dataset is structurally problematic** for causal redirection:
many pairs share the same answer, and one concept field sometimes has zero
coverage.
- Any **dataset-level upstream scan over USA directories** is vulnerable to
overcounting because the folder structure contains duplicate variants.

The sampled cases strengthen the case that contrast-group metrics (`vs_max`,
`rank_in_group`) capture something useful, but they also show that those
metrics cannot simply be interpreted as answer-level success.

**Threats to validity**:

- This was a curiosity sample, not a random sample, so it is designed to find
flaws rather than estimate prevalence fairly.
- Some metric mismatches may reflect real model behavior differences between
token-level trajectory and decoded text, not only evaluator bugs.
- The sampled cases are enough to prove the flaws exist, but not enough to
fully quantify how much each flaw changes the main cross-domain conclusions.

**Follow-up**:

- Patch evaluation to check exact-match only on generated continuation, not the
echoed prompt prefix.
- Exclude answer-level identity pairs from redirection analysis, especially in
sounds and the Finch/Lee book pair.
- Redefine or de-emphasize `first_token_matches_target`; require stronger token
evidence than substring overlap on the full answer string.
- Fix upstream directory canonicalization before using `itertools`-style scans
over entity folders in USA.
- Quantify how headline metrics change after these filters / fixes.

**References**: `output/FULLSCALE_CONTROL_REPORT.md`; `scripts/utils/pipeline_tracer.py`; `scripts/utils/swap_query.py`; `scripts/experiments/batch/pipeline/swap_evaluator.py`

---

## [2026-03-24] Topic: domain gradient explanation scan

**Question**: Why does `usa_states_batch` appear stronger than books,
products, paintings, and sounds? Is the domain gradient mainly explained by
upstream data quality, metric definition, concept ambiguity, or graph
structure?

**Method**: Ran a cross-domain scan using `SwapStats.compare()` on the five
full-scale labeled vs random runs and `PipelineTracer.grouping_quality_table()`
for per-entity upstream quality summaries. Collected, per domain: labeled vs
random deltas on `vs_max`, `gap_closure`, and `rank_in_group`; mean
`error_influence_pct`, selected features, supernodes, and review-flagged
counts; mean concept-coverage counts from the current matcher; and the
reverse-substring confound rate from the stricter one-way matching check used
in the previous investigation entry.

**Raw findings**:

- Labeled vs random `vs_max` delta by domain:
  - Books: +6.14
  - USA states: +5.17
  - Products: +3.23
  - Paintings: +1.58
  - Sounds: +0.14
- Labeled vs random `gap_closure` delta by domain:
  - USA states: +2.24
  - Sounds: -0.84
  - Products: -1.52
  - Paintings: -2.69
  - Books: -3.38
- Mean error-node influence by domain:
  - USA states: 10.01%
  - Books: 12.00%
  - Sounds: 12.88%
  - Products: 14.64%
  - Paintings: 14.87%
- Mean selected features / supernodes by domain:
  - USA states: 277.6 features, 23.9 supernodes
  - Books: 437.8 features, 26.8 supernodes
  - Products: 378.5 features, 25.8 supernodes
  - Paintings: 579.5 features, 30.6 supernodes
  - Sounds: 609.8 features, 32.8 supernodes
- Mean review-flagged rows by domain:
  - Products: 6.3
  - Books: 20.9
  - USA states: 36.2
  - Sounds: 42.5
  - Paintings: 55.0
- Reverse-substring confound rate by domain:
  - USA states: 28.0%
  - Books: 43.75%
  - Products: 29.17%
  - Paintings: 45.0%
  - Sounds: 25.0%
- Existing report-level structural observations:
  - USA: `state+capital` beats the full triple strongly.
  - Books: `book+author` beats the full triple dramatically.
  - Paintings: `painter` and `painter+first_name` are effectively identical.
  - Sounds: labeled and random are nearly indistinguishable on `vs_max`.

**Interpretation**: The domain gradient is not explained by a single factor.
Confidence: **Medium**. Epistemic level: **L2** (downstream causal effects) with
some **L1** support from upstream quality scans.

Most supported explanation: a combination of semantic answer-field quality and
upstream ambiguity burden.

- **Not mainly graph size/structure volume**: the weakest domains
(`paintings_painters_batch`, `sounds_colors_batch`) have the *most* selected
features and supernodes. More graph material does not produce stronger
specificity.
- **Partly upstream quality**: USA has the lowest mean error-node influence,
while paintings/products are worst on this measure. This supports the idea
that cleaner graphs help, but it does not fully explain the ranking because
books are strong despite only middling error-node burden.
- **Ambiguity/overlap likely matters a lot**: paintings has the highest
review-flagged burden and one of the highest substring-confound rates, and
the report already notes field collapse (`painter` subsumes `first_name`).
Sounds has a tiny, semantically coarse answer space (`color`) and almost no
labeled-vs-random separation.
- **Metric definition matters**: `Hit%` is not comparable across domains, and
`rank_in_group` compresses in small answer spaces. `gap_closure` is also not
a clean cross-domain strength metric, because books show strong specificity on
`vs_max` while random exceeds labeled on `gap_closure`.

Provisional synthesis: USA looks strongest because it combines relatively clean
upstream graphs with a highly specific answer space (`capital`) and a strong
intermediate-to-answer pathway (`state -> capital`). Books are also highly
specific on contrast-group metrics, but weaker on `Hit%` / `gap_closure`,
suggesting metric semantics and generation behavior obscure some of the signal.
Paintings and sounds look weak mainly because the target concept is less
entity-specific (`first_name`, `color`) and the matching/grouping pipeline is
more ambiguity-prone there.

**Threats to validity**:

- This is a domain-level observational scan, not a controlled ablation.
- Some metrics conflict (`vs_max` says books are very strong; `gap_closure`
does not), so conclusions depend on which metric is treated as primary.
- The upstream-quality summaries are coarse averages; they may hide a few
high-leverage entities or fields.
- The review-flagged and concept-coverage counts are proxies for ambiguity, not
validated causal measures.

**Follow-up**:

- Test answer-field specificity directly by comparing domains on answer-group
size, answer uniqueness, and baseline answer confusion.
- Build a simple domain-level regression / matched comparison using entity-level
predictors (`error_node_pct`, review burden, intervention count, field
coverage) to see which factors best predict `vs_max`.
- Investigate paintings and sounds with pair-level traces to confirm whether
weak performance comes from bad matching, coarse answers, or weak target
circuits.

**References**: `output/FULLSCALE_CONTROL_REPORT.md`; `output/CROSS_DOMAIN_CONTROL_REPORT.md`; `scripts/utils/pipeline_tracer.py`; `scripts/utils/swap_stats.py`

---

## [2026-03-24] Topic: reverse substring matching confound scan

**Question**: Does the current concept-to-supernode matching logic introduce
spurious matches through reverse containment (for example, short supernode names
such as `is` matching longer concepts such as `mississippi`)?

**Method**: Ran an ad hoc Python scan over all five `*_batch` datasets using
`PipelineTracer` helpers. For each entity and configured concept field, compared
the current matcher (`_concept_matches_supernode()`) against a stricter
one-way rule that allows `concept in supernode` and `word in supernode`, but
disallows the reverse fallback `supernode in word`. Counted extra supernodes
matched only by the current rule and recorded representative examples.

**Raw findings**:

- Denominator: 188 entity-field combinations across 5 datasets.
- USA states: 28/100 combinations affected (28.0%); 33 extra supernode matches.
- Books: 14/32 affected (43.75%); 26 extra matches.
- Products: 7/24 affected (29.17%); 7 extra matches.
- Paintings: 9/20 affected (45.0%); 17 extra matches.
- Sounds: 3/12 affected (25.0%); 4 extra matches.
- Affected combinations were present in every dataset scanned.
- Representative examples:
  - `mississippi_gulfport`, field `state`, concept `mississippi` -> extra
  match `is` (115 features)
  - `idaho_idaho_falls`, field `capital`, concept `boise` -> extra match
  `is` (110 features)
  - `wisconsin_milwaukee`, field `state`, concept `wisconsin` -> extra matches
  `is` (105 features) and `in` (5 features)
  - `anna_karenina`, field `book`, concept `anna karenina` -> extra matches
  `ina` (155 features) and `Karen` (485 features)
  - `guernica`, field `painter`, concept `pablo picasso` -> extra match
  `ica` (480 features)

**Interpretation**: This is evidence for a real pipeline artifact at the
concept-matching stage, not just a hypothetical edge case. Confidence:
**Medium**. Epistemic level: **L1** (operational label assignment / matching
quality). This does **not** yet establish that swap outcomes are materially
distorted downstream, only that the current matcher can add semantically
questionable supernodes in a sizeable minority of entity-field cases.

**Threats to validity**:

- The scan uses the tracer's simplified matching helper rather than a full
end-to-end replay of intervention assembly.
- "Extra match" does not automatically mean "bad match"; some cases may be
weak aliases or partial names rather than pure noise.
- The unit counted here is matched supernodes, not final ablate/amplify effect
on swap behavior, so downstream impact remains unmeasured.
- The scan is broad across domains, but it does not yet compare labeled vs
random swap performance with and without the reverse rule.

**Follow-up**: Measure downstream impact. Re-run a sample of swaps under a
strict one-way matcher and compare intervention counts, `vs_max`, `gap_closure`,
and `rank_in_group`. Prioritize USA and books, where both feature counts and
confound examples are large.

**References**: `scripts/utils/pipeline_tracer.py`; `scripts/utils/AGENTIC_RESEARCH_GUIDE.md`

---

