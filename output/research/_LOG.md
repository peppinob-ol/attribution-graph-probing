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

| Dataset | Labeled regime C | Random regime C | Delta |
|---------|-----------------|----------------|-------|
| USA     | 92.2% (1606/1741) | 18.9% (421/2223) | **+73.3pp** |
| Books   | 91.9% (124/135) | **88.9%** (128/144) | **+3.0pp** |

Recovery rate across ALL regimes:

| Dataset | Labeled | Random | Delta |
|---------|---------|--------|-------|
| USA     | 92.4% (2264/2450) | 31.3% (2302/7350) | +61.1pp |
| Books   | 93.8% (225/240) | **88.8%** (639/720) | **+5.0pp** |

The 92% vs 29% claim **does not replicate in books**. In books, which has
the *highest* vs_max delta of any domain (+6.14 per the domain gradient
entry), recovery rate barely separates labeled from random (3pp in regime C,
5pp overall).

*H1: Control token recovery as null model*

Control tokens "recover" (pos>0 exceeds pos0 logit) at near-100% rates:

| Condition | Target recovers | Control recovers | Delta |
|-----------|----------------|-----------------|-------|
| USA labeled regime C | 92.2% | 99.9% | -7.7pp |
| USA random regime C  | 18.9% | 97.9% | -79.0pp |
| Books labeled regime C | 91.9% | 100.0% | -8.1pp |
| Books random regime C  | 88.9% | 96.7% | -7.8pp |

Note: This comparison is not apples-to-apples. Control recovery is measured
against pos-0 logit (not unsteered baseline), because unsteered control
logits are not stored. The near-100% control rate confirms the overshoot
entry's finding that position 0 is catastrophically disrupted and later
positions always recover from the overshoot. The key observation is that in
USA random, target tokens do NOT participate in this generic recovery (only
18.9%), while in books random, they DO (88.9%).

*H2: Intervention count*

| Condition | Mean total_count | Median |
|-----------|-----------------|--------|
| USA labeled | 177.7 | 164 |
| USA random  | 177.7 | 164 |
| Books labeled | 304.4 | 293 |
| Books random  | 304.4 | 293 |

Intervention counts are **matched by design** between labeled and random.
Within USA labeled regime C, recovery rate by total_count quartile:

| Quartile | Range | Recovery |
|----------|-------|----------|
| Q1 | 0-148 | 87.1% |
| Q2 | 148-165 | 95.7% |
| Q3 | 165-202 | 93.9% |
| Q4 | 202+ | 91.7% |

Recovery is high across all quartiles; no monotonic relationship with
feature count. **H2 ruled out.**

*H3: Redundancy with vs_max*

Labeled regime C, vs_max by recovery status:

| Dataset | Recoverers | Non-recoverers |
|---------|-----------|---------------|
| USA | mean 2.60 (N=1606) | mean -0.81 (N=135) |
| Books | mean 4.85 (N=124) | mean 3.19 (N=11) |

Recovery is correlated with vs_max, but does it add information?

Among swaps with vs_max > 0 only:

| Dataset | Labeled recovery | Random recovery | Delta |
|---------|-----------------|----------------|-------|
| USA | 96.3% (N=1951) | 45.5% (N=929) | **+50.8pp** |
| Books | 94.4% (N=234) | **88.6%** (N=342) | **+5.8pp** |

In USA, recovery separates labeled from random even after conditioning on
positive vs_max. In books, the gap is only 5.8pp -- nearly gone.

*H4: Regime C selection bias*

Already shown above: recovery across all regimes has the same pattern.
USA gap persists (92.4% vs 31.3%). Books gap barely exists (93.8% vs 88.8%).
**H4 ruled out for USA, confirmed for books (no signal to select for).**

Per-regime recovery for random:

| Regime | USA random | Books random |
|--------|-----------|-------------|
| A | 45.3% (809/1784) | 92.9% (289/311) |
| C | 18.9% (421/2223) | 88.9% (128/144) |
| D | 32.1% (1071/3337) | 83.8% (222/265) |

Books random recovery is **83-93%** across ALL regimes. The books model
easily recovers target logits above baseline regardless of whether the
intervention is labeled or random.

*H5: Early recovery (positions 1-3 only)*

| Dataset | Labeled regime C | Random regime C | Delta |
|---------|-----------------|----------------|-------|
| USA | 61.5% (1070/1741) | 11.7% (259/2223) | +49.8pp |
| Books | 73.3% (99/135) | **78.5%** (113/144) | **-5.2pp** |

In books, early recovery **inverts** -- random actually exceeds labeled!

Position-specific recovery in USA regime C:

| Position | Labeled | Random | Delta |
|----------|---------|--------|-------|
| 1 | 10.2% | 0.8% | +9.4pp |
| 2 | 52.4% | 9.6% | +42.8pp |
| 3 | 30.6% | 2.2% | +28.4pp |
| 4 | 63.0% | 3.7% | +59.3pp |
| 5 | 55.1% | 4.2% | +50.9pp |
| 6 | 44.5% | 2.8% | +41.7pp |
| 7 | 36.9% | 1.3% | +35.6pp |
| 8 | 24.3% | 2.1% | +22.2pp |
| 9 | 34.6% | 3.6% | +31.0pp |
| 10 | 27.2% | 0.9% | +26.3pp |

In USA, the gap is robust at every individual position, peaking at
positions 2 and 4-5 (the same positions where the overshoot entry found
target rank recovering to top-15).

*Recovery magnitude*

| Condition | Mean excess above baseline | Median |
|-----------|--------------------------|--------|
| USA labeled regime C recoverers | +5.12 | +4.88 |
| USA random regime C recoverers  | +1.38 | +1.00 |
| Books labeled regime C recoverers | +4.81 | +4.44 |
| Books random regime C recoverers  | +2.90 | +2.75 |

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
- [x] Only two domains tested (USA, books). Products, paintings, and sounds
  should be checked. However, sounds has known structural issues, and
  paintings has small N (90 pairs).
- [x] The control token recovery null model uses a different baseline
  (pos-0 logit, not unsteered), so it cannot directly test whether target
  recovery is target-specific. A proper null model would need unsteered
  control logits, which are not stored in the swap JSONs.
- [x] The books result could reflect books-specific properties (small answer
  space, highly distinctive entity names) rather than a general failure of
  the metric. But this is precisely the point: a metric that fails on
  "easy" datasets is not robust.
- [x] Recovery magnitude (recommended replacement) has not been formally
  validated as a discriminator with bootstrap CIs or effect sizes.
- [x] The regime classification uses position-0 deltas, which are themselves
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

**References**: `[2026-03-24] logit-shift taxonomy and label-evidence metric
design` (original claim); `[2026-03-25] best field-add variant vs random in
regime taxonomy`; `[2026-03-25] steering strength overshoot`;
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

| Dataset | N total | Direction right | + hit | + no hit | No-hit % |
|---------|---------|----------------|-------|----------|----------|
| USA | 2450 | 1951 (79.6%) | 606 | **1345** | 54.9% |
| Books | 240 | 234 (97.5%) | 9 | **225** | 93.8% |
| Products | 132 | 107 (81.1%) | 20 | **87** | 65.9% |
| Paintings | 90 | 70 (77.8%) | 4 | **66** | 73.3% |
| Sounds | 30 | 30 (100%) | 0 | **30** | 100% |

Books is extreme: 97.5% of swaps have the target logit beating all competitor
answer logits at some trajectory position, but only 3.8% produce the target
answer in text.

First tokens in the right-direction-no-hit population:

| Dataset | Top tokens (% of no-hit) | Obvious garbage % |
|---------|--------------------------|-------------------|
| USA | `' Efq'` (19.9%), `'AddTagHelper'` (9.7%), `'expandindo'` (8.8%) | ~95%+ |
| Books | `"'"` (39.1%), `'-'` (10.2%), `','` (8.9%), `' Efq'` (6.7%) | ~63% |
| Products | `"'"` (51.7%), `' '` (13.8%), `','` (13.8%) | ~85% |
| Paintings | `'<bos>'` (19.7%), `' Majefty'` (19.7%), `'e'` (10.6%) | ~95%+ |

USA and paintings generate tokens from completely unrelated vocabularies:
`' Efq'`, `'AddTagHelper'`, `'expandindo'`, `' يتيمه'`, `' Audiodateien'`,
`'Datuak'`, `' Majefty'`, `' Houfe'` -- Arabic, Portuguese, German, 18th-century
English, JavaScript variable names. These are hallmarks of a logit distribution
pushed so far off the manifold of coherent text that random high-activation
tokens from unrelated subspaces dominate.

Books and products predominantly output punctuation (`'`, `-`, `,`) -- the model's
logit distribution is broken but lands on common short tokens.

**Paradox: higher confidence = worse outcome.** Among right-direction-no-hit:

| Dataset | mean steered_first_prob (hit) | mean steered_first_prob (no-hit) |
|---------|-------------------------------|----------------------------------|
| USA | 0.282 | **0.383** |
| Books | 0.299 | **0.367** |
| Products | **0.149** | 0.319 |
| Paintings | **0.571** | 0.314 |

In USA and books, the model is MORE confident at position 0 when it produces
garbage than when it produces a hit. The intervention pushes the model to very
high confidence in a wrong token -- classic overshoot.

Trajectory deep dive (5 USA swaps with vs_max > 15, no hit):

| Position | Target logit | Target rank | Generated token |
|----------|-------------|-------------|-----------------|
| 0 | -0.60 to -3.36 | 113,504 -- 167,275 | `' County'` |
| 1 | 23.00 -- 24.12 | 10 -- 15 | `','` |
| 2 | **27.25** | **1** | `' Oklahoma'` |
| 3 | 24.12 -- 24.50 | 18 -- 23 | `','` |
| 5 | 24.25 -- 24.88 | 2 -- 6 | `' Tulsa'` |

**Position 0 is catastrophic (rank > 100K), but by position 2 the target reaches
rank 1.** The correct answer appears in the continuation: "County, Oklahoma, is
Tulsa" -- the model recovers but the corrupted first token prevents exact match.

Trajectory deep dive (books, hermione_granger -> jay_gatsby, vs_max=13.7):

| Position | Target logit | Target rank | Generated token |
|----------|-------------|-------------|-----------------|
| 0 | 19.25 | 2 | `"'"` |
| 1 | -0.64 | 179 | `'s'` |
| 2 | 25.12 | 5 | `' author'` |
| 3 | 13.44 | 1846 | `','` |
| 4 | 8.06 | 2375 | `' J'` |

Output: `"written by's author, J.K. Rowling"` -- apostrophe at position 0, then
the model recovers to produce the DEFAULT (source) author, not the target.

Position-0 disruption metrics:

| Metric | Range across samples |
|--------|---------------------|
| target_logit_delta (pos 0 vs baseline) | -2.1 to **-26.7** logit units |
| source_logit_delta (pos 0 vs baseline) | -15.8 to **-30.9** logit units |
| target_rank at pos 0 | 2 to **167,275** |

When M_ablate=-2 and M_amplify=20 are applied to hundreds of features
simultaneously, the combined effect can shift logits by 20-30 units at position 0,
pushing tokens to ranks > 100K.

Intervention count vs disruption (USA):

| total_count quartile | N | Hit% | vs_max | ctrl_stability |
|---------------------|---|------|--------|----------------|
| Q1 (94-147) | 614 | 23.6% | 2.45 | 13.3 |
| Q2 (148-164) | 642 | **27.3%** | **3.27** | 13.4 |
| Q3 (165-203) | 586 | 27.0% | 3.38 | 13.7 |
| Q4 (204-369) | 608 | 21.1% | 2.33 | **15.2** |

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
   0. This is orders of magnitude more disruption than needed to flip the target
   above the source.

3. **Recovery at later positions.** By position 2-3, target rank typically returns
   to 1-15 and the model generates coherent tokens including the target answer.
   The information is there -- the first token just gets destroyed.

4. **Confidence-hit paradox.** Higher steered_first_prob at position 0 correlates
   with FEWER hits (r=-0.211 in USA). The intervention does not just shift the
   logit distribution -- it concentrates probability mass on a single wrong token,
   making the model very confident in garbage.

**Sweep design recommendations**:

*Sweep parameters*:

| Parameter | Current | Recommended sweep values | Rationale |
|-----------|---------|-------------------------|-----------|
| M_amplify | 20 | **2, 5, 10, 15, 20** | Primary suspect; 20x stored activation is likely excessive |
| M_ablate | -2 | **0, -0.5, -1, -2** | Reversal (-2) may be too aggressive; 0 = full ablation |
| temperature | 0.3 | **0.3, 0.5, 0.7, 1.0** | Higher T may help escape distorted distribution |

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
- [x] The "garbage token" classification is based on visual inspection and heuristic
  rules, not a formal classifier. Some tokens classified as garbage may be
  legitimate (e.g., `' St'` for "St. Louis" could be correct in some contexts).
- [x] The confidence-hit paradox (r=-0.211) is a population-level correlation.
  Individual pairs may behave differently. A proper causal test requires the
  sweep itself.
- [x] The trajectory analysis shows 5 hand-picked high-vs_max cases. The
  recovery pattern may not hold for lower-vs_max cases where the direction is
  only marginally correct.
- [x] Lower M_amplify might not just reduce overshoot -- it might also reduce
  the label-specific signal, making labeled interventions more similar to random
  ones. The sweep must compare labeled vs random at each M value.
- [x] Temperature interacts with M: lower M + higher T might produce different
  results than lower M alone. A 2D sweep would be ideal but more expensive.
- [x] The current metric suite may not capture all the effects. Consider adding
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
previous entries `[2026-03-24] logit-shift taxonomy`, `[2026-03-25] best field-add
variant vs random in regime taxonomy`

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

| Dataset | sn_in_word features | % of active | Top noisy supernodes |
|---------|--------------------:|------------:|----------------------|
| USA | 442 / 4,579 | 9.0% | "is" (293), "port" (75), "in" (31) |
| Books | 994 / 2,260 | 34.7% | "Karen" (194), "uckleberry" (130), "hab" (111) |
| Products | 60 / 797 | 7.5% | "Tes" (38), "Press" (8), "Dy" (8) |
| Paintings | 1,049 / 1,880 | 48.8% | "ica" (192), "atte" (169), "ighth" (131), "ring" (125) |
| Sounds | 138 / 561 | 24.6% | "iss" (60), "ble" (36), "is" (27) |

Per-entity extremes:

| Entity | Noisy% | Active | Noisy | Direct | vs_max | Dataset mean |
|--------|--------|--------|-------|--------|--------|-------------|
| mississippi_Gulfport | **77.5%** | 160 | 124 | 36 | 3.20 | 2.86 |
| nighthawks | **78.1%** | 192 | 150 | 42 | 1.68 | 1.55 |
| grande_jatte | **77.2%** | 246 | 190 | 56 | 1.65 | 1.55 |
| anna_karenina | **68.2%** | 209 | 143 | 66 | 6.51 | 5.98 |
| hiss | **65.5%** | 145 | 95 | 50 | 3.29 | 3.28 |

All five highest-noisy entities perform **at or above** their dataset mean on
vs_max.

Correlations with mean_vs_max:

| Dataset | r(noisy_pct, vsMax) | r(noisy_feats, vsMax) | r(active_total, vsMax) | r(direct_feats, vsMax) | N |
|---------|--------------------:|----------------------:|-----------------------:|-----------------------:|--:|
| USA | 0.121 | 0.083 | **-0.298** | **-0.402** | 50 |
| Books | -0.207 | -0.215 | 0.211 | **-0.281** | 16 |
| Products | -0.442 | -0.439 | -0.265 | -0.084 | 12 |
| Paintings | -0.036 | -0.057 | -0.334 | -0.205 | 10 |
| Sounds | -0.545 | -0.384 | -0.289 | 0.355 | 6 |

Within-entity field-add comparison (USA, Mississippi_Gulfport vs low-noisy
entities as source):

| Condition | vs_max (Mississippi) | vs_max (low-noisy, N=5) | Delta |
|-----------|---------------------|------------------------|-------|
| state only | 2.51 | 2.68 | -0.17 |
| state+capital | **4.03** | **4.20** | -0.17 |
| all 3 fields (adds city) | 3.09 | 3.02 | **+0.07** |
| Drop (s+c -> all) | -0.94 | **-1.18** | -- |

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
- [x] USA is the only dataset with N=50 for entity-level correlations. Books (16),
  products (12), paintings (10), sounds (6) have small N where any correlation
  is unreliable. The USA null finding (r=0.121) is the most trustworthy.
- [x] Entity-level correlations conflate many factors. An entity with high noisy%
  may also differ in graph quality, prompt structure, answer specificity, etc.
  The within-entity field-add comparison is cleaner but only tests one entity
  (Mississippi) with extreme noisy burden.
- [x] "Noisy features don't hurt" could mean "the metrics don't capture the harm."
  If noisy features cause more control_stability disruption or push logits toward
  wrong answers in ways vs_max doesn't capture, the harm could be hidden.
- [x] The field-add comparison uses different pairs for Mississippi (N=49) vs
  low-noisy (N=392), so population differences could mask effects.
- [x] Paintings and sounds have known dataset-level issues (tiny answer space,
  field collapse) that may dominate any substring effect.
- [x] Mechanism (b) above -- partial semantic relevance of "noisy" matches --
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

**References**: Previous entries `[2026-03-24] reverse substring matching confound
scan`, `[2026-03-25] do "(concept) related" Relationship features hurt swap
performance?`, `[2026-03-25] best field-add variant vs random in regime taxonomy`;
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

| Dataset | Rel % of total | Rel % of active | Rel features matched |
|---------|---------------|----------------|---------------------|
| USA | 11.3% | 0.0% | 1/2962 |
| Books | 35.1% | 0.7% | 13/1757 |
| Products | 35.7% | 2.0% | 16/797 |
| Paintings | 13.0% | 0.7% | 11/1665 |
| Sounds | 20.6% | 2.0% | 6/295 |

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

| Dataset | r(low_layer_pct, vsMax) | r(rel_pct, vsMax) | r(active_total, vsMax) | N |
|---------|------------------------|-------------------|----------------------|---|
| USA | 0.018 | -0.044 | **-0.298** | 50 |
| Books | **0.473** | 0.475 | 0.211 | 16 |
| Products | -0.070 | 0.146 | -0.265 | 12 |
| Paintings | 0.051 | 0.455 | -0.334 | 10 |
| Sounds | -0.101 | 0.412 | -0.289 | 6 |

Notable per-entity examples (books):

| Entity | Active | Rel | Low% | mLayer | vsMax |
|--------|--------|-----|------|--------|-------|
| holden_caulfield | 127 | 2 | 70.9% | 3.9 | 6.85 |
| hermione_granger | 78 | 1 | 23.1% | 12.1 | 5.53 |
| captain_ahab | 183 | 0 | 64.5% | 5.3 | 6.07 |
| katniss_everdeen | 120 | 0 | 39.2% | 9.1 | 5.19 |

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
- [x] Per-entity correlations have small N for non-USA datasets (6-16). Individual
  correlations are unreliable; only USA's N=50 has reasonable statistical power.
- [x] Correlations between Relationship % and vs_max are confounded by entity
  name properties. Entities with distinctive first names (Oliver, Pablo, Jack)
  get both Relationship matches and potentially different baseline confusion.
- [x] The analysis counts features matched by the tracer's concept matcher, not
  the actual pipeline's matcher. If they differ, the counts could be wrong.
  However, the tracer uses the same `_concept_matches_supernode` logic.
- [x] "Active" features counted here are per-entity. In a swap, source features
  are ablated and target features are amplified -- the actual intervention set
  depends on both entities, not just one.
- [x] The books positive correlation (more low-layer features = higher vs_max)
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

**References**: Previous entries `[2026-03-25] cumulative influence of Semantic
(unknown) nodes`, `[2026-03-25] best field-add variant vs random in regime
taxonomy`; `scripts/02_node_grouping.py`; `scripts/utils/pipeline_tracer.py`

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

| Dataset | Entities affected | Unknown feat % | Unknown influence % |
|---------|-------------------|----------------|---------------------|
| USA states | 0/50 (0%) | 0.0% | 0.0% |
| Books | 16/16 (100%) | 2.3% (109/4693) | 1.7% |
| Products | 12/12 (100%) | 2.5% (70/2791) | 1.7% |
| Paintings | 10/10 (100%) | 2.3% (86/3785) | 1.7% |
| Sounds | 6/6 (100%) | 3.4% (71/2111) | 2.8% |

Root cause -- blacklist configuration difference:

- **USA** config (`usa_states_full.yml`): `blacklist_tokens: ["<bos>"]` only.
  Features with peak_token=`entity`/`attribute` get named normally and form
  supernodes like "entity" (1 feature), "attribute" (4 features).
- **Non-USA** configs (books, products, paintings, sounds):
  `blacklist_tokens: ["<bos>", "entity", "attribute"]`. Features whose best
  semantic peak token is `entity` or `attribute` have no valid fallback and
  become "Semantic (unknown)".

Peak tokens on unknown rows (all non-USA datasets pooled):

| Token | Rows | % of unknown |
|-------|------|-------------|
| `entity` | 967 | 57.5% |
| `attribute` | 334 | 19.9% |
| `relationship` | 332 | 19.8% |
| other (`:`, ` The`, ` Don`, etc.) | 47 | 2.8% |

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

| Dataset | Active % | Unknown % | Labeled-inert % |
|---------|----------|-----------|----------------|
| USA | 39.2% | 0.0% | 60.8% |
| Books | 48.2% | 2.3% | 49.5% |
| Products | 44.0% | 2.5% | 53.5% |
| Paintings | 49.7% | 2.3% | 48.1% |
| Sounds | 26.6% | 3.4% | 70.1% |

Correlation with swap performance:

| Dataset | Pearson r (unknown_influence_pct, mean_vs_max) | N |
|---------|------------------------------------------------|---|
| USA | 0.000 (no variance) | 50 |
| Books | 0.006 | 16 |
| Products | 0.320 | 12 |
| Paintings | 0.181 | 10 |
| Sounds | -0.297 | 6 |

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
- [x] The per-entity correlation has very small N (6-16) for non-USA datasets.
  Individual correlations are unreliable; the conclusion rests on the mechanism
  (matcher never matches) rather than correlation.
- [x] The influence join uses `(layer, id)` from the static metrics CSV.
  A small fraction of features may fail to match if the node_id format changed
  between pipeline versions.
- [x] This analysis considers only first-order effects (direct intervention).
  Unknown features could theoretically interact with intervened features through
  shared circuits. This second-order effect is not measured here and would
  require activation-level analysis.
- [x] The "inert feature" computation counts features per entity separately.
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
- [x] The baseline rank is computed at a single position (position 0). The
  model's internal representation may differ at later trajectory positions.
- [x] "First token sharing" does not automatically mean the model confuses
  the entities -- it means the first generated token is ambiguous, which
  may resolve by position 2+. But gap_closure=0.0 for the J. cluster
  suggests it does not resolve.
- [x] The near-duplicate thresholds (0.7 similarity, rank <= 3) are
  somewhat arbitrary. Changing them shifts counts but not the qualitative
  conclusions.
- [x] The field-ambiguity flaw (character==book) affects the field-add
  analysis specifically, not the full-triple labeled run.
- [x] This scan covers entity/answer properties only. It does not cover
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

**References**: Previous entry `[2026-03-24] curiosity-sampled method flaws
across datasets` (which first identified books Finch/Lee and sounds brown
collisions); `output/FULLSCALE_CONTROL_REPORT.md`; `scripts/utils/swap_query.py`

---

## [2026-03-25] Topic: gap closure is regime-dependent and mostly misleading

**Question**: Is `gap_closure` a useful signal for label evidence across
regimes, or is it only relevant in specific circumstances?

**Method**: Re-examined gap closure values from the regime taxonomy data already
collected in the `[2026-03-24] logit-shift taxonomy` and `[2026-03-25] best
field-add variant` entries. Compared gap closure across regimes A, C, D for
labeled, best variant, and random conditions, and checked whether it
discriminates labeled from random within each regime. Also checked the
cross-domain anomaly (USA vs books) where gap closure and `vs_max` disagree.

**Raw findings**:

Gap closure by regime (USA, full labeled vs random):

| Regime | Labeled gc | Random gc | Labeled vs_max | Random vs_max |
|--------|-----------|----------|---------------|--------------|
| A (tgt UP, src DOWN) | 0.88 | 0.76 | 4.28 | -0.19 |
| C (both DOWN, flip) | 2.73 | 1.59 | 2.33 | -0.10 |
| D (both DOWN, no flip) | **13.62** | **6.46** | 4.11 | -0.07 |

Gap closure by regime (USA, best variant vs random):

| Regime | Best gc | Random gc | Best vs_max | Random vs_max |
|--------|---------|----------|------------|--------------|
| A | 1.44 | 0.76 | 4.01 | -0.19 |
| C | 3.14 | 1.59 | 3.81 | -0.10 |
| D | **16.25** | **6.46** | 5.08 | -0.07 |

Cross-domain comparison (full labeled):

| Domain | gap_closure | vs_max | Interpretation conflict? |
|--------|-----------|--------|------------------------|
| USA | 4.67 | 2.86 | -- |
| Books | 0.01 | 5.98 | Yes: gc says weak, vs_max says strongest |
| Products | 0.19 | 3.46 | -- |
| Paintings | 0.80 | 1.55 | -- |
| Sounds | 1.46 | 3.28 | Mild: gc > paintings but vs_max > paintings |

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

| Dataset | best variant | full labeled | random |
|---------|-------------|-------------|--------|
| USA | 34.9%, hit 46%, vsMax 4.01 | 8.9%, hit 31%, vsMax 4.28 | 19.4%, hit 0%, vsMax -0.19 |
| Books | 62.1%, hit 54%, vsMax 9.08 | 38.8%, hit 4%, vsMax 7.64 | 40.8%, hit 0%, vsMax -1.49 |
| Products | 62.1%, hit 32%, vsMax 3.75 | 56.8%, hit 25%, vsMax 4.48 | 51.5%, hit 0%, vsMax 0.44 |
| Paintings | 47.8%, hit 0%, vsMax 2.25 | 17.8%, hit 6%, vsMax 3.76 | 23.3%, hit 0%, vsMax -0.54 |

Regime C (both DOWN, flip -- differential disruption):

| Dataset | best variant | full labeled | random |
|---------|-------------|-------------|--------|
| USA | 55.1%, hit 35%, recov 93%, winPct 0.804 | 71.1%, hit 23%, recov 92%, winPct 0.673 | 35.0%, hit 1%, recov 29%, winPct 0.319 |
| Books | 33.8%, hit 7%, recov 96%, winPct 0.378 | 56.2%, hit 2%, recov 92%, winPct 0.364 | 23.3%, hit 2%, recov 89%, winPct 0.192 |
| Products | 32.6%, hit 12%, recov 86%, winPct 0.315 | 39.4%, hit 2%, recov 98%, winPct 0.199 | 22.7%, hit 0%, recov 83%, winPct 0.282 |
| Paintings | 48.9%, hit 2%, recov 89%, winPct 0.273 | 75.6%, hit 4%, recov 93%, winPct 0.203 | 33.3%, hit 0%, recov 77%, winPct 0.188 |

Regime D (both DOWN, no flip -- generic disruption):

| Dataset | best variant | full labeled | random |
|---------|-------------|-------------|--------|
| USA | 9.1% | 19.4% | 45.3% |
| Books | 3.3% | 3.3% | 34.6% |
| Products | 2.3% | 2.3% | 22.0% |
| Paintings | 2.2% | 6.7% | 42.2% |

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
