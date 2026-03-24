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

## [2026-03-24] Topic: logit-shift taxonomy and label-evidence metric design

**Question**: When a swap does not produce a perfect (T5) result, what does the
logit trajectory tell us about whether the feature labels are correct? Can we
separate "the labels pointed at the right circuits" from "the swap happened to
produce the right string"?

**Method**: Classified every labeled and random swap in the five full-scale runs
by what happens to target and source token logits at position 0 relative to
their unsteered baselines. Defined four main regimes:

| Regime | Target logit | Source logit | Flip at pos 0? | Intuition |
|--------|-------------|-------------|----------------|-----------|
| **A** | UP | DOWN | yes | Clean redirection: target gains, source loses |
| **C** | DOWN | DOWN | yes | Both disrupted, but target less so |
| **D** | DOWN | DOWN | no | Both disrupted, source still dominant |
| **E** | FLAT | DOWN | yes | Pure suppression, no target lift |

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

| Dataset | A (labeled) | A (random) | C (labeled) | C (random) | D (labeled) | D (random) |
|---------|-------------|------------|-------------|------------|-------------|------------|
| USA | 8.9% | 19.4% | 71.1% | 35.0% | 19.4% | 45.3% |
| Books | 38.8% | 40.8% | 56.2% | 23.3% | 3.3% | 34.6% |
| Products | 56.8% | 51.5% | 39.4% | 22.7% | 2.3% | 22.0% |
| Paintings | 17.8% | 23.3% | 75.6% | 33.3% | 6.7% | 42.2% |
| Sounds | 0% | 0% | 43.3% | 26.7% | 56.7% | 73.3% |

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
