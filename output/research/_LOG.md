# Investigation Log

Append-only log of investigations. Newest entries at the top.
Entry format per `AGENTIC_RESEARCH_GUIDE.md` §9.2:
Question / Method / Raw findings / Interpretation / Threats to validity / Follow-up.
Do not edit past entries; if a finding is wrong, add a new entry that references and corrects it.

---

## 2026-05-08 -- Does target-token unembedding norm predict steer-success?

**Status**: Done (4 domains x labeled + fa_best; per-pair, per-target, OLS controlling for baseline)
**Confidence**: High in Products (the user's example domain); high in USA in the OPPOSITE direction; mixed in Books / Paintings.
**Claim tested**: User hypothesis (refined) -- "the achievable target logit margin under steering is structurally bounded by `||W_U[:, target_token]||`, so tokens with small unembedding norm (e.g. ` Jack`) are harder to steer than tokens with larger norm (e.g. ` Austin`)". Mechanism: `logit_t = RMSNorm(residual) . W_U[:, t]`, so for any fixed residual push the achievable logit increment is upper-bounded by `||residual_push|| * ||W_U[:, t]|| * cos`.

### Question

Headline T2 shows residual misses across all four domains. The first iteration of this entry tested two weaker proxies for "specific" (baseline target logit at source prompt; within-dataset first-token collision) and produced mixed results. The user clarified that the relevant quantity is the L2 norm of the unembedding row for the target token -- a purely geometric property of the model that bounds the dot-product between any residual direction and the target's logit channel, independent of the baseline. This re-runs the test with `||W_U[:, target_token]||` extracted from `google/gemma-2-2b` (weights tied; `embed_tokens.weight` row L2 norm).

### Question

Headline `T2_headline` shows steer hit-rates of 18.9 - 77.8 % across the four in-scope domains under FA+M-search. The user's intuition is that the residual misses are partly explained by the "magnitude" of the target logit -- specific tokens being easier to push to the top than generic ones. We need to know whether the data agrees, and under which definition of "specific".

### Method

- Four investigation scripts (kept self-contained on top of `SwapQuery` + raw JSON scans):
  - [`scripts/research/analyze_target_logit_specificity.py`](../../scripts/research/analyze_target_logit_specificity.py) -- per-pair `baseline_logits.target.logit/prob/rank` + per-target marginal baseline logit. (First-iteration weaker proxy.)
  - [`scripts/research/analyze_target_token_collision.py`](../../scripts/research/analyze_target_token_collision.py) -- per pair, unique- vs shared-token classification of the target's first token. (First-iteration weaker proxy.)
  - [`scripts/research/analyze_unembedding_norm.py`](../../scripts/research/analyze_unembedding_norm.py) -- loads `google/gemma-2-2b` (weights tied; `embed_tokens.weight` row L2 norm = `||W_U[:, t]||`), maps each per-pair `target.token_id` to its unembedding norm, reports PB and per-target Spearman against hit, plus quintile hit-rates and the per-target table sorted by norm.
  - [`scripts/research/analyze_unembed_vs_logit_margin.py`](../../scripts/research/analyze_unembed_vs_logit_margin.py) -- direct test of the geometric mechanism: per-pair Spearman/Pearson of `unembed_norm` against `vs_max`, `best_gap`, and `max_target_logit`; OLS `hit_rate ~ unembed_norm + marginal_baseline_logit` on per-target aggregates to check whether unembedding norm carries predictive power above and beyond the model's baseline propensity for the target token.
- Conditions analysed per domain: `fullscale_<dom>_labeled` (canonical labeled, single variant per pair) and per-pair best-of variant from `fullscale_<dom>_field_add` (best == any variant whose `steered_has_to_answer` is true; tie-break on `vs_max`). The fa_best slice mirrors the FA+M-search best-of construction in T2.
- Outputs:
  - [`output/research/target_logit_specificity/report.json`](target_logit_specificity/report.json), [`report.txt`](target_logit_specificity/report.txt), [`collision_report.json`](target_logit_specificity/collision_report.json) -- first-iteration findings.
  - [`output/research/target_logit_specificity/unembed_report.json`](target_logit_specificity/unembed_report.json) -- per-pair PB and per-target Spearman vs unembedding norm, plus per-domain top-50 / top-15 / top-14 / top-12 per-target rows sorted by norm.
  - [`output/research/target_logit_specificity/unembed_vs_logit_margin.json`](target_logit_specificity/unembed_vs_logit_margin.json) -- direct mechanism check (norm vs vs_max / best_gap / max_target_logit) and OLS controlling for baseline.

### Raw findings

#### (1) Unembedding norm `||W_U[:, target]||` vs hit  (REFINED USER HYPOTHESIS)

Vocab-wide reference: 256,000 tokens, d_model=2304, embedding-row L2 norm distribution: min 1.073, p25 1.624, median 1.759, p75 1.903, max 4.871; final-RMSNorm gamma mean-abs 2.45 (shared across tokens, monotone factor only).

Per-pair point-biserial PB(`unembed_norm`, `hit`) and per-target Spearman:

| Domain | Condition | N | PB(norm, hit) | Spearman_per_target |
|---|---|---:|---:|---:|
| usa                | labeled | 2,450 | -0.081 | -0.162 |
| usa                | fa_best | 2,450 | -0.165 | -0.191 |
| books              | labeled |   210 | +0.171 | +0.284 |
| books              | fa_best |   210 | -0.143 | -0.250 |
| **products**       | labeled |   174 | **+0.627** | **+0.640** |
| **products**       | fa_best |   174 | **+0.460** | **+0.442** |
| paintings          | labeled |   124 | -0.031 | -0.113 |
| paintings          | fa_best |   124 | -0.082 | +0.058 |

Products quintiles by `unembed_norm` (labeled / fa_best):

| Q | norm range | mean | hit% labeled | hit% fa_best |
|---:|---|---:|---:|---:|
| 1 | 1.487-1.521 | 1.507 |  0.0 | 28.2 |
| 2 | 1.521-1.573 | 1.546 |  0.0 |  0.0 |
| 3 | 1.573-1.613 | 1.597 |  0.0 |  0.0 |
| 4 | 1.613-1.690 | 1.687 | 38.5 | 57.7 |
| 5 | 1.690-1.764 | 1.731 | 50.0 | **76.9** |

Per-target table for Products (sorted low-norm first; columns: token, norm, marginal baseline logit, hit% under fa_best, N):

```
 ' Steve'    1.487   15.20   84.6%   13   <-- outlier: very strong founder feature
 ' Matt'     1.513   13.00    0.0%   13
 ' Larry'    1.521   13.54    0.0%   13
 ' Pierre'   1.531   12.20    0.0%   11
 ' Michael'  1.535   16.14    0.0%   13
 ' Henry'    1.573   10.78    0.0%   11
 ' Phil'     1.576   12.09    0.0%   11
 ' James'    1.587   15.55    0.0%   13
 ' Jack'     1.613   14.90    0.0%   11   <-- twitter
 ' Jack'     1.613   14.51    0.0%   13   <-- alibaba
 ' Bill'     1.684   14.96   61.5%   13
 ' Mark'     1.690   15.88   53.8%   13
 ' Palmer'   1.698    8.78   53.8%   13
 ' Elon'     1.764   13.06  100.0%   13
```

USA per-target table excerpt (all 50 capitals, sorted low-norm first; only first/last 6 shown for space):

```
 ' Boston'      1.472  18.12  71.4%   <-- low norm + warm token: hits
 ' Atlanta'     1.491  19.57  83.7%
 ' Oklahoma'    1.508  20.11  24.5%
 ' Denver'      1.528  20.50  89.8%
 ' Pierre'      1.531  17.73  42.9%
 ' Saint'       1.537  19.61  93.9%
 ...
 ' Topeka'      1.922  18.97  18.4%
 ' Bismarck'    1.947  15.68  46.9%
 ' Frankfort'   2.079  18.78  91.8%   <-- high norm but easy
 ' Juneau'      2.171  17.28  14.3%   <-- highest norm, hard
```

#### (2) Direct mechanism check: does unembed norm bound the achievable steered margin?

Per-pair Spearman of `unembed_norm` against the achieved best logit margin (`vs_max`) and the max target logit over the trajectory:

| Domain | Sp(norm, vs_max) | Pearson(norm, vs_max) | Sp(norm, max_target_logit) | Sp(baseline_logit, vs_max) [ref] |
|---|---:|---:|---:|---:|
| usa       | -0.277 | -0.236 | -0.200 | +0.200 |
| books     | -0.149 | -0.156 | -0.165 | +0.201 |
| **products**  | **+0.541** | **+0.640** | +0.184 | +0.134 |
| paintings | +0.119 | -0.043 | +0.125 | +0.148 |

Per-target OLS `hit_rate ~ b1 * unembed_norm + b2 * baseline_logit`:

| Domain | beta_unembed | beta_baseline | R^2 | N targets |
|---|---:|---:|---:|---:|
| usa       | +0.008 | +0.124 | 0.185 | 50 |
| books     | -0.370 | -0.020 | 0.018 | 15 |
| **products**  | **+1.661** | **-0.008** | **0.245** | 14 |
| paintings | +0.024 | +0.032 | 0.062 | 12 |

In Products the unembedding norm completely dominates the marginal baseline logit (beta_unembed = +1.66, beta_baseline ~ 0); in USA the situation reverses (baseline logit dominates, unembed norm has zero independent effect).

#### (Earlier proxies, kept for cross-reference)

PB(`baseline_logits.target.logit`, `hit`) per pair, Spearman per target -- positive in 7/8 cells with a clean USA gradient (Q1 fa_best 47%, Q5 79%); see [unembed_report.json](target_logit_specificity/unembed_report.json) for the side-by-side. First-token collision: ` Jack` is the only within-domain shared first token in any of the four datasets, and all 24 Jack-target pairs hit 0 / 24 in both labeled and fa_best (z_unique-shared = +3.19 in fa_best Products).

### Interpretation

The user's refined hypothesis -- "low `||W_U[:, target]||` => hard to steer because the geometric ceiling on the achievable target-logit increment is small" -- is **strongly supported in Products and rejected in USA**. The two domains tell complementary stories:

1. **Products: the geometric channel dominates** (confidence High). PB(unembed_norm, hit) = +0.46 / +0.63 (fa_best / labeled); Spearman_per_target +0.44 / +0.64. The OLS `hit_rate ~ unembed_norm + baseline_logit` puts essentially all the signal on `beta_unembed = +1.66` and zero on `beta_baseline ~ 0`. Per-pair Spearman(`unembed_norm`, `vs_max`) = **+0.54** (Pearson +0.64): the achieved logit margin is monotone in the unembedding norm, exactly as the geometric mechanism predicts. The Products quintiles are clean: every target with norm < 1.61 hits 0 % (Matt, Larry, Pierre, Michael, Henry, Phil, James, Jack-twitter, Jack-alibaba) while every target with norm > 1.68 hits 54-100 % (Bill, Mark, Palmer, Elon). The single low-norm outlier is ` Steve` (norm 1.487, hit 84.6 %), explainable by the unusually strong Apple/Steve-Jobs feature signal that lets a small W_U row support a still-large dot-product.

2. **USA: the feature channel dominates** (confidence High). PB(unembed_norm, hit) = -0.08 / -0.16; Spearman_per_target -0.16 / -0.19; per-pair Spearman(unembed_norm, vs_max) = **-0.28**. Direction is INVERTED from the user's hypothesis. The reason is visible in the per-target table: the lowest-norm capitals are also the most frequent everyday English words (` Boston` 1.472, ` Atlanta` 1.491, ` Denver` 1.528, ` Austin` 1.547, ` Sacramento` 1.549, ` Phoenix` 1.564) and the model has rich features for all of them, so the residual aligns strongly with W_U[t] even though ||W_U[t]|| is small. The high-norm capitals are rare-word small-state capitals (` Concord` 1.803, ` Frankfort` 2.079, ` Juneau` 2.171) where the model has weaker features regardless of geometry, so the larger ||W_U[t]|| cannot be exploited. This is not a refutation of the geometric mechanism: it is feature-channel variance overwhelming the geometric channel because the two are anti-correlated in this domain (high-frequency tokens have small embeddings AND rich features).

3. **Books / Paintings: small N, signal washes out** (confidence Medium). Books labeled has the user-predicted direction (+0.17 / +0.28) but flips negative under fa_best (-0.14 / -0.25); paintings is null in both. Per-target N (15 / 12) is too small to resolve.

The Products result is the cleanest possible test of the user's hypothesis because all 14 founder targets are first-name tokens of comparable feature richness (well-known tech founders), so the feature channel is approximately controlled. In that controlled setting, the unembedding-norm channel is dominant (R^2 = 0.245 with norm alone; baseline logit adds nothing).

The earlier within-dataset collision finding (` Jack` shared by twitter + alibaba, both 0 % hit) is now a sub-effect of (1): both Jack pairs sit at norm 1.613, on the wrong side of the Products inflection point at ~1.65. Whether the collision *adds* to the geometric penalty cannot be settled here -- they are confounded -- but the Jack failure no longer requires invoking collision as a separate cause.

T2 implications:
- L1 / L2: nothing in T2 changes. The geometric ceiling is a property of the model, not of the feature labels, so this finding does not weaken any of the T2 verdicts.
- It does explain *part* of the residual Products miss-rate (`fa_best Hit% = 41.7` from T2 under the lenient rule, ~26-31 % under the per-pair best-of slice we use here): roughly half of Products targets sit on the low-norm side and a labeled feature bag can hit them only when the residual aligns very precisely with `W_U[target]`.
- It does NOT offer a clean, model-only, universally predictive diagnostic. See the decomposition follow-up entry below.

#### Decomposition follow-up (corrects the over-claim)

`baseline_logit_t = ||W_U[t]|| * alignment_proxy`, where
`alignment_proxy = baseline_logit_t / ||W_U[t]|| ~ ||LN(residual_default)|| * cos(LN(r), W_U[t])`.

Per-target OLS `hit_rate ~ ceiling + alignment` (standardised betas, R^2):

| Domain | std_beta_ceiling | std_beta_alignment | dominant | R^2 | N_targets |
|---|---:|---:|---|---:|---:|
| usa       | +0.569 | **+0.812** | alignment | 0.174 | 50 |
| books     | -0.181 | -0.113 | (neither) | 0.014 | 15 |
| products  | **+0.481** | -0.026 | **ceiling** | 0.243 | 14 |
| paintings | +0.105 | +0.314 | alignment | 0.059 | 12 |

Univariate Spearman per target:

| Domain | Sp(ceiling, hit) | Sp(alignment, hit) | Sp(baseline_logit, hit) |
|---|---:|---:|---:|
| usa       | -0.103 | +0.276 | +0.414 |
| books     | -0.219 | -0.009 | -0.029 |
| products  | +0.454 | -0.141 | +0.059 |
| paintings | +0.042 | +0.116 | +0.200 |

Two cleanly separable conclusions:

1. **`||W_U[:, t]||` is a true geometric ceiling on `vs_max` for any token, in any domain** (Cauchy-Schwarz on `LN(r) . W_U[t]`). That is a model-only property and is correct as stated.
2. **The ceiling binds only when steering can produce high `cos(r, W_U[t])`, and `cos` is feature-driven.** Whether the ceiling actually predicts hits varies by domain: ceiling dominates Products (where founder-feature richness is roughly uniform across the 14 targets) and is shadowed by alignment in USA (where ` Boston`/` Atlanta`/etc have an order of magnitude richer features than ` Concord`/` Juneau`). Best-case explained variance (Products) is R^2 = 0.243 with both factors -- the rest lives in feature-bag quality, intervention size, error-node coverage.

Practical reading: there is no *model-only*, *prompt-free* number we can compute up front and use to predict steer success in an arbitrary domain. We have a model-only **upper bound** (ceiling) and a model-plus-source-prompt **alignment proxy** (baseline_logit / norm), and together they explain 5-25 % of per-target hit-rate variance. Useful to flag structurally-doomed targets (Products' low-norm cluster) and useful conceptually, but it is not a substitute for running the swap.

The cleanest single experiment that would close the question:
- For each pair, log `||LN(steered_residual)||` at the trajectory position where `vs_max` is reached, recompute `cos = vs_max / (||LN(r)|| * ||W_U[t]||)` and check whether `cos` saturates at 1 (ceiling binds) or stays small (feature alignment is the real bottleneck) per domain.

Outputs of this follow-up: [`output/research/target_logit_specificity/decomposition.json`](target_logit_specificity/decomposition.json); script: [`scripts/research/decompose_unembed_logit.py`](../../scripts/research/decompose_unembed_logit.py).

### Threats to validity

- "Unembedding norm" is a one-number summary of W_U geometry. The full mechanism is `||W_U[t]|| * ||residual_push|| * cos(W_U[t], residual_push)`. We never measured the cos term per pair; the residual_push direction is a function of the labeled feature bag, so the user's hypothesis only constrains an upper bound, not the actual achievable margin. The Products result therefore plausibly *under*-states the true geometric effect because cos is also varying.
- Per-target N (12-15) in Products / Books / Paintings is small. The Products beta_unembed = 1.66 has a wide implicit CI; we did not bootstrap.
- USA's anti-correlation between unembedding norm and feature richness is itself an empirical claim that we did not measure directly (would need a per-token feature-count proxy from the CLT graph).
- Gemma-2 applies final-RMSNorm with shared gamma and a logit soft-cap. Both are monotone transforms that do not affect rank correlations but do compress absolute logit magnitudes; the Pearson coefficients in section (2) are slight under-estimates as a result.
- The fa_best slice has positive selection bias on hit; the per-pair PB is dampened toward the easier (high-norm or high-feature) end of each domain. Labeled-condition stats agree on the direction in Products, so this does not flip the conclusion.
- We did not re-run a hard control: pairing two USA capitals that share a first token (` Salt` for Salt Lake City vs. some other Salt-prefixed entry would falsify the collision sub-claim cleanly) -- the dataset does not contain such a collision.

### Follow-up

- Per-pair cos(W_U[target], residual_push) measurement: cache the post-RMSNorm residual at position 0 for each steered run and dot it with W_U[target]. This isolates the geometric channel from the feature channel and resolves the Products vs USA divergence cleanly.
- Cross-domain feature-richness proxy: count target-supporting features in each entity's CLT graph (number of features whose top-activating context includes the target token). Test whether (norm * feature_count) is a better single predictor than either alone.
- Replicate Products finding on a synthetic "low-norm vs high-norm matched founder names" subset to remove the collision confound from the ` Jack` rows.
- Add a "structural ceiling" column to the per-pair appendix table (`appx:perpair`): `||W_U[target]|| * achievable_residual_norm` could be reported alongside `vs_max` to show which misses are diagnostic of label quality vs. structural model geometry.

### Artifacts

- Scripts: `scripts/research/analyze_target_logit_specificity.py`, `scripts/research/analyze_target_token_collision.py`, `scripts/research/analyze_unembedding_norm.py`, `scripts/research/analyze_unembed_vs_logit_margin.py`
- JSON outputs: `output/research/target_logit_specificity/{report,collision_report,unembed_report,unembed_vs_logit_margin}.json`
- Text summary: `output/research/target_logit_specificity/report.txt`

---

## 2026-05-08 -- Fair Dallas top-K saturation re-run (single bag, no field-additivity)

**Status**: Done (top-10 + top-21 + top-100 + top-200, all 49 source states)
**Confidence**: High; the previous unfair phase3v3 top-K result is now corrected.
**Claim tested**: After removing the field-additivity boost the previous Dallas top-K conditions inherited from `auto`'s supernode labels, can pure top-$K$-by-`node_influence` substitute for either the human curation or our auto pipeline on the all-49-USA-source Dallas swap?

### Question

The 2026-05-05 Phase B v3 entry below ran every Dallas top-K condition with `control.mode: additivity` and the 7-variant field-add sweep (`add_state`, `add_capital`, `add_state+capital`, ...). Top-$K$-by-influence has no labeling capability of its own, so per-variant subsetting was inherited *from the auto labels stamped on the top-K rows of `node_grouping.csv`*. The phase3v3 top-K markers (top-21 31/49, top-100 34/49, top-200 40/49) were therefore not a fair influence-only baseline — they were "auto's labels restricted to the top-K rows, plus 7-variant field-add, plus M-search". This entry re-runs the Dallas top-K family without that boost and asks whether the apparent top-K saturation near `ours` survives.

### Method

- New control builder [`scripts/experiments/batch/pipeline/controls/single_bag_grouping.py`](../../scripts/experiments/batch/pipeline/controls/single_bag_grouping.py) (registered in `pipeline/controls/factory.py` as `single_bag_grouping`): every `(layer, feature)` row in `data_from["grouping"]` is ablated, every row in `data_to["grouping"]` is amplified, no concept-field plumbing, no per-variant subsetting, no `supernode_name` filter. Diagnostics: `n_src`, `n_tgt`, `achieved_sum_src`, `achieved_sum_tgt`.
- **Asymmetric design**: top-$K$ filtering is applied to the *target side only* (Dallas). The source side keeps its canonical auto grouping (~1{,}253 features per state on average) so the source-side ablation is held constant across `ours / human / top-K / shuffled` and the only varying quantity is the target bag. This mirrors the phase3v3 protocol minus field-additivity, and isolates the target-side feature selection as the experimental variable. (We did not re-run `ours / human / shuffled` — those conditions were *designed* to use field-additivity and running them without it would penalize them on a setting they were built for.)
- Built [`output/usa_states_fact_batch/_swap_conditions/auto_top10_dallas/`](../usa_states_fact_batch/_swap_conditions/auto_top10_dallas/) (49 source symlinks + filtered Dallas grouping; 10 unique features over 50 grouping rows) via the extended [`tools/build_topk_dallas_conditions.py`](../../tools/build_topk_dallas_conditions.py) (new `--full` flag pulls the 49-source list from `full_swap_auto_top21_dallas.yml`). The existing `auto_top21_dallas`, `auto_top100_dallas`, `auto_top200_dallas` graph roots from phase3v3 are reused as-is — only the run output (work/) is regenerated by the new YAMLs.
- Four phase-4 configs: [`scripts/experiments/batch/configs/phase4_topk_{10,21,100,200}_dallas_singlebag.yml`](../../scripts/experiments/batch/configs/) — `control.mode: single_bag_grouping`, `m_search.enabled: true` with the same parameters as `fullscale_usa_labeled_msearch.yml` (coarse 6 probes $M \in \{0.1, 0.25, 0.6, 1.5, 4.0, 10.0, 20.0\}$, fine 6 steps).
- Launcher [`tools/launch_phase4_topk_singlebag.sh`](../../tools/launch_phase4_topk_singlebag.sh): 4 in-process workers, one K per GPU, shared `RUN_ID`. Logs at [`logs/phase4_topk_singlebag/`](../../logs/phase4_topk_singlebag/).
- Aggregator [`tools/phase4_topk_singlebag_aggregate.py`](../../tools/phase4_topk_singlebag_aggregate.py) emits `output/research/phase4_topk_singlebag_{cells,conditions}.csv` with the same column layout as `phase3v3_conditions.csv` so `scripts/research/figure_topk_saturation_full50.py` can stitch them.

### Raw findings (final)

Per-condition source coverage on Dallas, all 49 sources, single-bag target with adaptive M-search:

| condition | sources hit / 49 | cells run | cell hit-rate | mean amplified feat / call | mean cum target inf / call | $M_{\mathrm{tuned}}$ median |
|---|---:|---:|---:|---:|---:|---:|
| auto_top10  | 3 / 49 | 49 | 6.1% | 10  | 0.051 | (default M=20 hits all 3) |
| auto_top21  | 3 / 49 | 49 | 6.1% | 21  | 0.073 | 6.93 |
| auto_top100 | 6 / 49 | 49 | 12.2% | 100 | 0.146 | 2.40 |
| auto_top200 | 1 / 49 | 49 | 2.0% | 200 | 0.197 | 4.08 |

Reference markers (kept from phase3v3, *with* field-additivity, same 49 sources):

| condition | sources hit / 49 | cell hit-rate | mean amplified feat / call |
|---|---:|---:|---:|
| ours (auto)             | 40 / 49 (82%) | 30.1% | 96.5 |
| top-200 *phase3v3 unfair* | 40 / 49 (82%) | 26.9% | 30.7 |
| human                   | 38 / 49 (78%) | 26.2% | 4.0  |
| top-100 *phase3v3 unfair* | 34 / 49 (69%) | 22.5% | 19.7 |
| top-21 *phase3v3 unfair*  | 31 / 49 (63%) | 18.1% | 8.1  |
| shuffled-labels         | 0 / 49 (0%)   | 0.0%  | 3.4  |

Per-K loss from the field-add boost (phase3v3 → phase4):
- top-21: 31 → 3 (−28 sources, $-57$ pp source coverage)
- top-100: 34 → 6 (−28 sources, $-57$ pp)
- top-200: 40 → 1 (−39 sources, $-80$ pp)

The fair top-K family saturates at 6-12% source hit-rate across $K \in \{10, 21, 100, 200\}$, against `ours`'s 82% and `human`'s 78% on the same 49 source states. None of the four K values matches even half of `human`'s coverage despite consuming $0.76\times$ to $2.93\times$ `ours`'s per-call cumulative target-feature influence (`top-10` is the one $K$ below ours's per-call influence; `top-21/100/200` are above). The figure ([`paper/figures/fig_topk_saturation_full50.{pdf,png}`](../../paper/figures/fig_topk_saturation_full50.pdf)) shows this as a wide vertical gap between the green top-K curve (near the floor) and the red/blue labeled markers (near the ceiling).

The non-monotone top-100 vs top-200 result (12.2% → 2.0%) is consistent with high-$K$ disruption: with 200 amplified features in a single bag the target circuit is drowned out even at low $M$. Adaptive $M$-search rescues all top-21/100/200 hits at $M \in \{2.4, 4.1, 6.9\}$ (well below the default $M{=}20$); top-10 hits already exist at the default. *Every* phase4 hit is at $M \leq 6.93$.

### Interpretation

The phase3v3 top-K markers were not measuring "what does an influence-only ranking buy you", they were measuring "what do auto's labels buy you, restricted to the top-K rows, with 7-way field-additivity and M-search free to pick the best variant". The field-add boost was carrying $57$-$80$~pp of the apparent source coverage. The fair single-bag re-run isolates the influence ranking and shows it cannot substitute for either the human curation or our pipeline on the Dallas case study: every $K$ saturates near the floor.

This is consistent with the cross-domain influence-matched result from 2026-05-07 (`appx:topkim`): there, at the same per-pair influence budget, the labeled best-of beat the influence-matched top-$K$ on every pair-level comparison in every in-scope domain (Hit\% gap $+22$ to $+66$~pp, McNemar $p \leq 7\!\times\!10^{-5}$). The Dallas case study now lines up with that picture rather than against it.

The reason `top-100` outperforms `top-21` in the fair setting is plausibly that the labeled methods (human, ours) carry low-influence "scaffold" features whose individual graph influence is small but whose collective specificity for the target answer is high (cf.\ `appx:fieldadd`); raising $K$ from 21 to 100 picks up a few of those features, but ranking purely by `node_influence` still leaves most of them behind. Pushing $K$ to 200 adds more high-influence-but-low-specificity features that just disrupt the circuit (cf. the M-search top-$k$ rescue null at `appx:msearch`).

### Threats to validity

- Single target circuit (Dallas, USA). The cross-domain influence-matched analogue is in `appx:topkim` (4 domains).
- The Dallas top-K happens to be unusually concept-pure (~90% of top-21 features fall in the 8 auto-labeled supernodes), which gave the phase3v3 unfair runs an even larger boost than it would on a domain with messier labels. The fair phase4 numbers are *unaffected* by this concentration (no labels are read), but the "phase3v3 → phase4 loss" magnitude reported above may not generalize to other domains.
- Source side uses canonical auto's labels for every condition, so the auto pipeline is "running" on every row as ablation, even when the target side is human/top-K/shuffled. This is the standard convention since phase3v3 (the only Dallas-target curated graph is the human one), but means we cannot disentangle "labels matter for ablation" from "labels matter for amplification" in this specific experiment. The cross-domain `appx:topkim` experiment, which has both source-side and target-side influence-matched bags, addresses the same question without this confound.
- We kept `--source-stop-on-hit` *off* for phase4 (single bag has only one variant per pair, so stop-on-hit would be a no-op on cells but could mask diagnostics if extended later).
- Adaptive $M$-search is the only outer sweep; we did not re-run a high-$M$ rescue on top-200 to check whether the disruption can be undone by $M$-reduction below the Phase-1 grid floor of $M{=}0.1$.

### Follow-up

- Symmetric top-K: apply the influence filter to *both* sides (source ablation also restricted to top-K). This was rejected for the Dallas figure because the asymmetric design isolates target-side selection as the variable, but a follow-up experiment would quantify how much of the labeled methods' lead is target-side feature choice vs source-side ablation completeness.
- Stratified analysis: which 6 sources does top-100 hit (and why aren't they hit by top-200)? Likely overlap with the 40-pair `ours` set; if so, top-100 is a strict subset of `ours`'s coverage rather than a complementary regime.
- Top-K with field-additivity transferred from `auto`: the phase3v3 protocol, but now we know it adds $57$-$80$~pp of source coverage. A clean ablation that toggles only field-additivity (with everything else single-bag) would isolate that boost and quantify how much of the ours-vs-human gap is explained by feature *labeling* vs feature *selection*.

### Artifacts

- Per-cell CSV: `output/research/phase4_topk_singlebag_cells.csv`
- Per-condition CSV: `output/research/phase4_topk_singlebag_conditions.csv`
- Run dirs: `output/usa_states_fact_batch/_swap_conditions/auto_top{10,21,100,200}_dallas/_swaps/runs/phase4_topk_singlebag_20260508_0409/`
- Configs: `scripts/experiments/batch/configs/phase4_topk_{10,21,100,200}_dallas_singlebag.yml`
- Control: `scripts/experiments/batch/pipeline/controls/single_bag_grouping.py`
- Launcher + logs: `tools/launch_phase4_topk_singlebag.sh`, `logs/phase4_topk_singlebag/swap_top{10,21,100,200}.log`
- Aggregator: `tools/phase4_topk_singlebag_aggregate.py`
- Figure (regenerated): `paper/figures/fig_topk_saturation_full50.{pdf,png}` (`scripts/research/figure_topk_saturation_full50.py`)

---

## 2026-05-07 -- Per-pair influence-matched top-K baseline across 4 in-scope domains

**Status**: Done (paintings + products + books + USA)
**Confidence**: High (paired McNemar tests $p \le 7\!\times\!10^{-5}$ in every domain; $p < 10^{-30}$ in books and USA)
**Claim tested**: At the same per-pair, per-side cumulative graph-influence budget, does selecting the top-$K$ features by `node_influence` recover the labeled best-of Hit-rate?

### Question

The earlier Dallas-only top-$K$ saturation result (`fig_topk_saturation`) showed a single-circuit ceiling where top-$K$-by-influence couldn't clear what probe-prompting did, even at very large $k$. That experiment had three confounds for cross-domain generalization:

1. It only ran on Dallas (USA, single source entity).
2. The Dallas top-$K$ conditions inherited `auto`'s supernode labels, so the field-additivity matcher was free to subset the bag *per variant* — unfair to a top-$K$ that has no field semantics.
3. Total feature count, not per-side cumulative `node_influence`, was the matched quantity.

We built a fairer baseline that is: (a) per-pair, (b) per-side influence-budget-matched against the *exact* labeled best-of winner for that pair, (c) a single bag (no field-add variants), and (d) given the same outer adaptive-$M$ search.

### Method

For every pair $(e_A, e_B)$ in the four in-scope domains:

1. Identify the best variant in `fullscale_<domain>_field_add` by Hit, ties broken by `best_gap`; prefer `__m_tuned.json` if present. Read its `features.json`, split into source-ablate and target-amplify by sign of $M$.
2. Sum `node_influence` for those features against `<from>`'s and `<to>`'s `graph_feature_static_metrics.csv` (max over `ctx_idx` per `(layer, id)`). Output `output/research/topk_budgets_<domain>.csv` with `ref_sum_src`, `ref_sum_tgt`, `n_ablate_labeled`, `n_amplify_labeled`. Built by [tools/build_topk_budgets.py](../../tools/build_topk_budgets.py).
3. New control mode `topk_influence_matched` (registered in `pipeline/controls/factory.py`, implemented in `pipeline/controls/topk_influence_matched.py`): per pair, look up the budgets, take the smallest top-$K$ prefix of the entity's own `node_grouping.csv` universe ranked by max `node_influence` whose cumulative reaches the budget, return a single bag, no concept-field plumbing.
4. Four per-domain configs (`scripts/experiments/batch/configs/topk_<domain>_influence_matched.yml`), `m_search.enabled: true` with the same parameters as `fullscale_usa_labeled_msearch.yml`, no `control.runs` (no field-add variants).
5. Run via `tools/launch_topk_im.sh <domain>` -> 8 in-process workers, one per GPU, round-robin pair-sliced via `--source-slice $i/8`. *No `--source-stop-on-hit`* (this control has only one variant per pair; stop-on-hit would short-circuit target entities and corrupt the per-pair comparison).
6. Aggregator [tools/topk_influence_matched_aggregate.py](../../tools/topk_influence_matched_aggregate.py) joins each topk-IM swap result with the labeled best-of row from the budgets CSV and emits `output/research/topk_im_pairs_<domain>.csv` and `topk_im_summary.csv`. Paper figure: [tools/figure_topk_saturation_4domains.py](../../tools/figure_topk_saturation_4domains.py).

### Raw findings (final, all 4 domains)

| Domain    | $N$ | top-K Hit% (best of default + $M$-search) | Lab.\ Hit% (paired) | $\Delta$ pp | lbl-only / topk-only | McNemar $p$ |
|---        |---:|---:|---:|---:|---:|---:|
| Paintings | 100 | 6.0 | 28.0 | $+22.0$ | 25 / 3 | $7.2\times 10^{-5}$ |
| Products  | 144 | 4.2 | 36.8 | $+32.6$ | 47 / 0 | $1.9\times 10^{-11}$ |
| Books     | 225 | 4.4 | 65.8 | $+61.3$ | 139 / 1 | $5.3\times 10^{-31}$ |
| USA       | 2{,}500 | 2.3 | 67.8 | $+65.6$ | 1{,}642 / 3 | $< 10^{-30}$ (underflow) |

Per-pair budget-match is exact by construction: median achieved-vs-reference ratio is $1.013$--$1.034$ (smallest-prefix overshoot), and only 1 pair across all 4 domains is under-budget on a single side (books src). Mean amplification feature counts: top-K $K_{\mathrm{tgt}} = 12.4$ (USA), $22.8$ (Products), $29.7$ (Books), $44.5$ (Paintings) vs labeled $n_{\mathrm{amp}} = 51.9$, $86.0$, $77.3$, $119.7$ respectively, so the labeled bag uses $1.7$--$4.2\times$ more features at the same per-pair influence budget. Source suppression rate (`from_suppressed`) is $48\%$ (paintings), $74\%$ (products), $91\%$ (books), $88\%$ (USA): top-$K$ is reliably knocking out the source answer in every domain --- what it cannot do as cleanly as labeled is steer to the target.

Wall time per domain (8 in-process shards, 8 A40 GPUs): paintings 4.4 min, products 6.1 min, books 7.6 min, USA 109 min default + ~10 min $M$-search rescue (51 rescues; 5 default hits + 51 $M$-tuned hits = 56 / 2500 = 2.24\% Hit-rate, so adaptive $M$-search recovers a $10\times$ multiple of the default hits but the absolute top-$K$ ceiling stays at $2.3\%$).

### Interpretation (preliminary)

The labeled bag wins on every pair-level comparison in every completed domain. Two non-mutually-exclusive readings are consistent with the gap and with the `appx:msearch` top-$k$-rescue null on Products:

1. *Many low-influence "scaffold" features in the labeled bag still gate the answer circuit.* Field-additivity sweeps are dominated by the intermediate and answer fields (`appx:fieldadd`); those features carry low per-node influence individually but high collective specificity for the target answer. Ranking by `node_influence` and taking the smallest prefix that matches the same total budget systematically excludes them.
2. *The highest-influence features per the attribution graph are the loudest at position-0, but not the most informative for redirection.* This is the same mechanism observed at the $k$-rescue null on `products$\to$facebook` (only the full $k{=}67$ set produces hits; top-1 to top-10 produce 0 hits at any $M \in \{20, 50, 100, 200\}$).

We do not separate these two readings within this experiment.

### Threats to validity

- The labeled best-of is itself selected to maximize Hit, so the matched-budget definition is biased toward the labeled side. The fair comparison is the paired sign test (McNemar), not the marginal difference; we report both.
- The grouping universe used for top-$K$ is `node_grouping.csv`, which is the same set of steerable features the labeled pipeline classifies. We did *not* test top-$K$ over a wider universe (e.g., the full attribution graph minus error nodes); doing so would let top-$K$ reach features that the labeled pipeline has explicitly chosen to exclude, which is a different experiment.
- Domain coverage: 4 of 5 domains. Sounds is excluded ($N{=}30$, 6 entities, shared answer tokens); we expect it to behave like Paintings or worse but did not verify.
- The McNemar $p$-values are calibrated against the assumption of independent pairs. Within-source dependence (the 50 USA states each producing 49 swap rows) inflates effective $N$ less than nominal; the contingency-level claim ($b \gg c$) is robust to this.

### Follow-up

- Pure-unlabeled-bag variant: top-$K$ at a single global $K$ chosen to match the *cross-domain* mean labeled budget, to disentangle "selection by influence" from "per-pair budget matching".
- Stratified analysis: do labeled-only wins concentrate on pairs where the labeled features are far down the influence ranking? That would localize claim (1) above.
- Pure rank-by-influence baseline that does *not* exclude scaffold/error-node rows, to check that the universe restriction in `node_grouping.csv` is not what is doing the work.

### Artifacts

- Per-pair joined CSV: `output/research/topk_im_pairs_{paintings,products,books,usa}.csv`
- Per-domain summary: `output/research/topk_im_summary.csv`
- Per-pair budgets (labeled best-of reference): `output/research/topk_budgets_{paintings,products,books,usa}.csv`
- Paper figure: `paper/figures/fig_topk_im_4domains.{pdf,png}`
- Paper table: `paper/tables/T_topk_influence_matched.tex`
- Run dirs: `output/<dataset>/_swaps/runs/topk_<domain>_influence_matched/`
- Launcher + logs: `tools/launch_topk_im.sh`, `logs/topk_im/<domain>__shard_*.log`

---

## 2026-05-05 -- Phase B v3 pipeline: in-process model + early-stop + 8-GPU split (~25x faster than v2)

**Status**: Running (started 02:51 UTC May 5, ETA ~04:33 UTC)
**Confidence**: High for speedup, results pending
**Claim tested**: Can the full 6-condition × 49-source × 7-variant matrix (2058 cells)
finish in single-digit hours on the 8-GPU box?

### Question

The first attempt at Phase B was tracking ~35 h wall-clock (rate ~46 cells/h
across 6 GPUs), dominated by the per-call ReplacementModel reload inside
`_run_local_ct_steering` that spawns `batch_steering_ct.py` as a fresh
Python subprocess on every M-search probe. Each probe paid ~30 s of model
load for ~3 s of actual compute.

Two changes were stacked:

1. **In-process steering backend.** Added
   `run_steering_session_inprocess()` to `batch_steering_ct.py` and a
   `--in-process` CLI flag to `run_batch_swaps.py` that loads ONE
   `ReplacementModel` at process start and reuses it across every probe in
   that worker.
2. **Stop at first hit per source.** New `--source-stop-on-hit` flag.
   `run_single_swap` attaches `_hit_found` (default-M hit OR M-search hit);
   the variant loop breaks out for a source once any variant hits. Changes
   the unit of analysis from cell to source.

8-GPU layout: 6 conditions but 8 GPUs. Two of the conditions
(`human_dallas`, `auto_dallas`) are split with `--source-slice 0/2` and
`1/2` so all 8 GPUs run a full worker process.

### Method

Smoke validation (1 source x 7 variants on `human_dallas`,
`smoke_inprocess_0245`) before launching:

| metric              | old subprocess backend | new in-process |
|---------------------|------------------------|----------------|
| time per probe      | ~50 s                  | ~3.3 s         |
| time per cell       | ~5 min                 | ~25 s          |
| 7-cell smoke total  | ~35 min (extrapolated) | ~3 min         |

Then launched the full 8-worker run via `tools/launch_phase3_swaps.sh`
(updated to use `--in-process --source-stop-on-hit` and the source-slice
split for the two heaviest conditions).

### Raw findings (interim, 19 min into the run)

* 387 / 2058 cells complete (18.8 %)
* Aggregate rate **1200 cells/h** (vs ~46 cells/h on v2: ~26 x)
* All 8 GPUs at 100 % util, 24.6 GiB each
* Hits so far: human 27, auto 34, top21 9, top100 17, top200 21,
  shuffled 0
* Early-stop already kicked: 14 source-hits in `human_dallas` slice 0/2,
  23 in `auto_dallas` slice 0/2 (each saves ~5-6 variants)

### Interpretation (preliminary)

* The dominant cost on v2 was model load, not compute. Removing it gives
  a ~12-15 x speedup at the per-probe level; the rest of the gain over
  the v2 *aggregate* rate comes from also using all 8 GPUs.
* `shuffled_labels_dallas` still at 0 / 35 hits at this checkpoint --
  consistent with it being a clean negative control under M-search.

### Threats to validity

* Numbers above are interim; need to revisit after the run completes.
* The two split conditions (`human`, `auto`) experience the same
  per-process model load cost as unsplit ones, so they each cost ~30 s
  more startup than they would unsplit. Negligible at 2 h scale.

### Final results (run finished 05:23 UTC, 2 h 32 m wall-clock)

| condition       | sources hit / 49 | cells run | cell hit-rate | mean M_tuned (median) |
|-----------------|-----------------:|----------:|--------------:|----------------------:|
| probe-prompting |             40   |       133 |        30.1 % |                  4.08 |
| top-200         |             40   |       149 |        26.9 % |                  2.40 |
| human           |             38   |       145 |        26.2 % |                  2.00 |
| top-100         |             34   |       151 |        22.5 % |                  6.93 |
| top-21          |             31   |       171 |        18.1 % |                  2.40 |
| shuffled-labels |              0   |       343 |         0.0 % |                  --   |

### Follow-up

* Add the per-source heatmap and the M_tuned distribution as
  supplementary figures: they reveal that human is the *most natural*
  condition (M_median = 2.0, almost always default-M), while
  probe-prompting is the most *consistent* (M_IQR tight, no outliers).
* If 8-GPU still feels under-used, a cross-condition dispatcher would
  push wall-clock toward ~67 min.

---

## 2026-05-05 -- Source coverage rewrites the headline: probe-prompting ties top-200, human is most natural

**Status**: Concluded
**Confidence**: High (N = 49 sources x 7 field-additivity variants per
condition, M-search enabled, full 50-state graph batch)
**Claim tested**: Does the cell-level top-K saturation story (5-source
M-search smoke) survive at the 49-source scale?

### Question

The paper figure baseline (`fig_topk_saturation.pdf`, generated from
`smoke_msearch_main_table_v2.csv` with N = 5 sources x 7 variants = 35
cells per condition) showed:
* probe-prompting 14 / 35 hits, mean amplified influence = 0.067 per
  call -- strict winner;
* top-K family saturated near 9-10 / 35 regardless of K (K=21..200);
* human at the bottom (5 / 35) despite its tiny 4-feature footprint.

The 5-source slice was small enough that the *source-level* coverage
question was indistinguishable from the cell-level question. Phase B v3
ran the same six conditions on every one of the 49 non-Dallas USA
sources, with M-search and seven field-additivity variants per source.
That gives us, for the first time, two complementary pictures: per-cell
efficiency and per-source coverage.

### Method

1. Phase A regenerated the full 50-state graph batch with the
   `gemmascope-transcoder-16k` set (matches the human-annotated
   `texas_dallas` graph). Done already in earlier Phase A entry.
2. Phase B v3 (this entry's predecessor) ran 6 conditions x 49 sources
   x 7 variants = 2058 cell-attempts maximum, with
   `--source-stop-on-hit` early-stopping the variant loop on the first
   hit per source. M-search remained on (coarse 6 probes, fine 6 steps,
   M_min = 0.1, M_max = 20).
3. Aggregator: `scripts/research/phase3v3_aggregate.py` walks every
   `by_source/<source>/to_<target>__<variant>.json` plus its
   `__m_tuned.json` sibling and emits two CSVs in `output/research/`:
   `phase3v3_cells.csv` (one row per attempted cell) and
   `phase3v3_conditions.csv` (per-condition aggregate).

### Raw findings

Per-condition aggregate (full table also in `phase3v3_conditions.csv`):

| condition       | sources hit / 49 | cells run | cell hit-rate | mean amplified feat / call | M_median |
|-----------------|-----------------:|----------:|--------------:|---------------------------:|---------:|
| probe-prompting |             40   |       133 |        30.1 % |                       96.5 |     4.08 |
| top-200         |             40   |       149 |        26.9 % |                       30.7 |     2.40 |
| human           |             38   |       145 |        26.2 % |                        4.0 |     2.00 |
| top-100         |             34   |       151 |        22.5 % |                       19.7 |     6.93 |
| top-21          |             31   |       171 |        18.1 % |                        8.1 |     2.40 |
| shuffled-labels |              0   |       343 |         0.0 % |                        3.4 |     --   |

Shuffled-labels still zero hits across all 343 cells -- the negative
control survives the scale-up cleanly.

Three findings worth highlighting:

1. **Source coverage**: at the source level, probe-prompting and
   top-200 are tied (40 / 49 = 82 %) and human is one source behind
   (38 / 49 = 78 %). Top-21 (31 / 49) is genuinely worse. The
   per-source heatmap (`fig_per_source_heatmap.pdf`) shows there's a
   small "universally hard" set (idaho_idaho_falls, several smaller
   cities) that no method touches.

2. **Cell-level efficiency** still favours probe-prompting: 30.1 %
   cell hit-rate vs 26.9 % (top-200) vs 26.2 % (human) vs 18-22 %
   (top-21, top-100). Same general shape as the 5-source figure, but
   the gap is smaller and human is now slightly above the top-K
   saturation, not below it.

3. **Naturalness via M_tuned**: when human hits, it does so with a
   tiny perturbation (M_median = 2.0, IQR collapsed at default M).
   probe-prompting is the most *consistent* (M_median = 4.1, tight
   IQR, no outliers above ~7); top-100 has a bimodal distribution
   with several hits requiring M = 12+; top-200 mixes easy and hard
   transfers.

### Interpretation

The full 50-state evidence makes the story more nuanced than the
5-source paper figure suggested:

* **probe-prompting** is the *best general-purpose* method: highest
  cell hit-rate, ties the best on source coverage, and never demands
  >7x amplification.
* **human curation** is the *most natural*: when it works, it works at
  default M, with only 4 features per call. The cost is that it
  generalises slightly less broadly (38 vs 40 sources hit).
* **top-K-by-influence** with K=200 catches up at the source level by
  brute-forcing 30+ features per call, but pays a higher cell-level
  cost and a much higher M variance.
* **shuffled-labels** still 0 / 49: the labels-as-information story
  stands.

The right framing for the paper is probably "two pictures, two
metrics": cell efficiency = probe-prompting wins; source coverage =
probe-prompting ties top-200; M-naturalness = human wins. All three are
captured in the new figures.

### Method/source agreement (49 sources, 5 real methods)

Looking only at the 5 non-shuffled methods, the 49 sources break down as:

* **22 / 49 universally easy** -- hit by all 5 methods (alaska, arizona,
  california oakland, delaware, florida, georgia, hawaii, iowa, kentucky,
  louisiana, maine, massachusetts, minnesota, montana, nevada, new
  hampshire, new mexico, ohio, oregon, rhode island, tennessee, vermont).
* **1 / 49 universally hard** -- `idaho_idaho_falls` is missed by every
  method. Worth auditing the Phase A graph and node grouping for this
  source: the "Idaho" supernode may be poorly localised in the graph.
* **26 / 49 disagreement** -- methods are non-redundant. Three highlights:
  * `missouri_kansas_city` and `north_dakota_fargo` are hit *only* by
    **human**. No auto method (probe-prompting, top-21, top-100, top-200)
    succeeds on them. The human-curated 22-feature "Texas" subgraph
    captures something the auto pipeline doesn't on these two states.
  * `colorado_colorado_springs` is hit *only* by **probe-prompting**.
    None of human, top-21, top-100, top-200 succeed. The probe-prompting
    label-driven supernode composition captures something even top-200
    misses with its 30+ features.
  * `oklahoma_tulsa` is hit *only* by **top-200** -- a pure influence
    win where the volume of features carries the day.

This complementarity is the strongest argument against treating these
methods as "good vs better": at the source level, human curation,
probe-prompting, and top-K each pick up sources that the others miss.
The right framing for the paper is that these methods are partially
*orthogonal*, not strictly ordered.

### Threats to validity

* "Source coverage" depends on how generous one is with variants. With
  7 field-additivity variants per source and M-search, top-200 catches
  up. If the variant set were smaller, top-200 would underperform
  probe-prompting more visibly.
* `cells_run` differs across conditions because of `--source-stop-on-hit`.
  Cell hit-rate is therefore "hit rate among run cells", not "hit rate
  among 343 fixed cells". This is the right metric for ranking by
  efficiency, but it does mean the denominator is not constant.
* `idaho_idaho_falls` may have Phase A graph-quality issues we have not
  audited.

### Outputs

* `output/research/phase3v3_cells.csv` -- 1092 cell-attempt rows
* `output/research/phase3v3_conditions.csv` -- 6 condition rows
* `paper/figures/fig_topk_saturation_full50.{pdf,png}` -- two-panel
  full-50-state version of the paper figure (per-cell efficiency +
  source-level coverage)
* `paper/figures/fig_per_source_heatmap.{pdf,png}` -- 49 x 6 grid of
  hit / no-hit / M-at-hit per (source, condition)
* `paper/figures/fig_mtuned_distribution.{pdf,png}` -- log-scale
  per-condition M_tuned strip plot showing human-as-most-natural

### Follow-up

* Decide whether to keep both `fig_topk_saturation.pdf` (5-source) and
  the new `fig_topk_saturation_full50.pdf` in the paper or replace the
  former. Replacing is cleaner; the supplementary heatmap covers the
  evidence we'd lose.
* Audit the 6 "universally hard" sources to check for Phase A graph
  defects.

---

## 2026-05-04 -- Top-K-by-influence saturates at K=21..200 for Dallas-target swaps; auto wins on labels, not on influence budget

**Status**: Concluded
**Confidence**: Medium (N = 5 sources × 7 variants per condition = 35 cells; 6 conditions; results consistent across pre-registered top-K sweep)
**Claim tested**: If we expand the auto top-K-by-influence bag from K=21 toward auto's per-subprocess influence budget, do we close the auto-vs-top-21 hit gap (auto: 14, top-21: 10)? More generally: is the auto pipeline's edge over top-K-by-influence a *budget* effect or a *bag composition* effect?

### Question

In the Dallas-as-target M-search smoke (5 source states × 7 field-additivity variants = 35 cells per condition, all run with `m_search.enabled=true, m_min=0.1, n_coarse_probes=6, n_fine_steps=6`), four conditions had been compared:

- `human_dallas`     -- 21 human-curated features from the Anthropic Dallas-Austin graph
- `auto_dallas`      -- the full canonical Dallas auto grouping (pool = 1182 unique features)
- `auto_top21_dallas` -- top-21 of the auto pool by `node_influence`
- `shuffled_labels_dallas` -- same 21 features as human, with supernode labels shuffled

Per-subprocess (35-cell mean) view of those four:

| condition       | n_amplify_per_subprocess | cum_inf_per_subprocess | n_hits | mean_M |
|-----------------|--------------------------|------------------------|--------|--------|
| human           | 3.4                      | 0.0144                 | 5      | 12.96  |
| auto            | 120.6                    | 0.0671                 | 14     | 7.74   |
| auto top-21     | 8.0                      | 0.0306                 | 10     | 5.20   |
| shuffled-labels | 3.4                      | 0.0043                 | 0      | --     |

Top-21 reached ~46% of auto's per-subprocess influence (0.0306 / 0.0671) and got ~71% of auto's hits (10/14), while spending ~7% of the features (8/120.6). It looked dramatically more efficient. The natural question was whether scaling K toward auto's influence budget would close the gap.

### Method

- Two new conditions `auto_top100_dallas` and `auto_top200_dallas` built by `tools/build_topk_dallas_conditions.py`. Each takes the canonical Dallas auto grouping CSV (`output/usa_states_fact_batch/texas_dallas/02 Node Grouping/node_grouping.csv`), keeps only the top-K rows by max `node_influence` per `(layer, raw_id)` from the canonical Dallas circuit-tracer metrics, and preserves the auto supernode labels so the field-additivity matcher can subset the bag by concept field.
- Configs: `scripts/experiments/batch/configs/smoke_swap_auto_top{100,200}_dallas.yml` cloned from `smoke_swap_auto_top21_dallas.yml`, M-search left at the same parameters as the original four conditions.
- Both conditions run on the same 5 sources × 7 variants matrix in parallel on `CUDA_VISIBLE_DEVICES={0,1}`, ~3h wall-clock each.
- Outputs aggregated by `tools/smoke_msearch_analysis.py` into `output/research/smoke_msearch_results.csv`, `_summary.csv`, `_hits_clean.csv`. Headline table by `tools/smoke_msearch_main_table_v2.py` into `smoke_msearch_main_table_v2.csv`.

### Raw findings

**Per-subprocess view, all six conditions (means across the 35 cells of each condition):**

| type            | n_amplify_per_subprocess | cum_influence_amplified_per_subprocess | n_hits | n_failures | mean_M |
|-----------------|-------------------------:|---------------------------------------:|-------:|-----------:|-------:|
| human           |   3.4 | 0.0144 |  5 | 30 | 12.96 |
| auto            | 120.6 | 0.0671 | 14 | 21 |  7.74 |
| auto top-21     |   8.0 | 0.0306 | 10 | 25 |  5.20 |
| auto top-100    |  21.1 | 0.0432 |  9 | 26 |  6.11 |
| auto top-200    |  34.9 | 0.0502 | 10 | 25 |  3.64 |
| shuffled-labels |   3.4 | 0.0043 |  0 | 35 |  --   |

**Hit-count trajectory along the top-K sweep:** 10 → 9 → 10. Quasi-flat. **Cum-influence trajectory along the same sweep:** 0.031 → 0.043 → 0.050 (1.6× larger). **Amplify-count trajectory:** 8 → 21 → 35 (4.4× larger). Despite the budget growing substantially, the hit count does not grow at all between K=21 and K=200.

**Canonical-vs-rescued split for the new conditions:**

| condition    | canonical hits at M=20 | M-search rescues |
|--------------|------------------------|------------------|
| auto top-100 | 0/35                   | 9                |
| auto top-200 | 0/35                   | 10               |

Both top-100 and top-200 produce **zero canonical hits** at the default `M_amplify=20`; every Austin hit is M-search-rescued at lower M. Top-200 has the lowest mean_M of any condition in the study (3.64) and 0/10 hits with the `ⓧ` over-amplification artifact (vs 4/14 = 29% in auto canonical hits).

**Per-feature potency (cum_influence ÷ n_amplify_per_subprocess):**

| condition       | per-feature potency |
|-----------------|--------------------:|
| human           | 0.0042              |
| top-21          | 0.0038              |
| top-100         | 0.0020              |
| top-200         | 0.0014              |
| auto            | 0.0006              |
| shuffled        | 0.0013              |

Per-feature, the bag becomes ~3× more diluted between K=21 and K=200, and an order of magnitude more diluted in auto.

**Concept-pure share of the bag (fraction of unique features whose supernode label maps to a concept field used by some variant: `Texas`, `state`, `Dallas`, `containing`, `capital`, `Say (Austin)`, `Say (capital)`, `city`, `Say (city)`, ...):**

|   K | concept-pure | newly-included supernode labels (top-K vs top-21)              |
|----:|-------------:|----------------------------------------------------------------|
|  21 | ~90%         | --                                                             |
| 100 | ~84%         | adds `is`, `the`, `serving`, `attribute`, `seat`, `(entity) related`, `relationship` |
| 200 | ~84%         | adds `(entity) related` (more), `entity`, `United`, `Say (state)` |

The features past the top-21 are increasingly things like the verb `is`, punctuation, or `(entity) related` -- syntactically present in the prompt but not direct carriers of the Texas-as-state signal that an `add_state` variant needs to override "Florida"/"Illinois"/etc.

### Interpretation

**The matched-budget hypothesis is falsified.** Auto's 14-hit advantage over top-21's 10 hits is not a budget gap that can be closed by feeding top-K-by-influence more features. Going from K=21 → K=200 quadruples the amplified bag and ~doubles its cum-influence, and the hit count moves from 10 to 9 to 10. The plateau is real.

**The bag composition is the operative variable.** Auto wins because the supernode labels on its 1182 features map cleanly to the field-additivity matcher's concept fields. The matcher then assembles a different 100-200-feature subset for each of the 7 variants, and across 7 variants × 5 sources every Austin-relevant subset is well-populated. Top-K-by-influence has no such mechanism; once it admits features labelled `is`/`the`/`(entity) related`/etc., those features sit in the bag but are *never amplified* by any variant of the additivity sweep. They are influence on paper, dead weight in practice.

**Top-200 is the cleanest baseline of the six.** Lowest mean_M (3.64), zero `ⓧ` artifacts, zero canonical M=20 hits (so no over-amplification false positives) -- all 10 hits are M-search-rescued at M ∈ [2.4, 6.9]. As a no-label control it is a more honest summary of what auto's pool looks like at smaller scale than top-21 (which happened to be 90% concept-pure by coincidence of the top-21 ranking). It loses 4 hits to auto, but the loss is interpretable: those 4 cells need labelled features the influence-only ranking does not surface near the top.

**Restated headline.** "Auto wins on hits because the labels channel a much larger subset of the graph through the right concept-field variants. The labels are not decorative; they are the mechanism." Top-21's earlier-looking 1.5× influence-efficiency advantage over auto was an artifact of K=21 happening to land mostly inside auto's most concept-pure layer. It does not generalise.

### Threats to validity

- **N = 35 cells per condition**; differences in the 1- to 2-cell range (e.g., top-21 vs top-100, 10 vs 9) are noise. Direction of the saturation is robust (no monotonic increase across K=21/100/200), but the precise crossover point is not.
- **M-search is greedy.** It returns the *first* M (low-to-high) that produces an Austin token; it doesn't optimise for cleanliness or KL. A run could miss a cleaner hit at M=4 because it found a noisier one at M=2.4 first.
- **Top-K labels are inherited from auto.** That makes the comparison "top-K-by-influence with auto's labels" rather than "top-K-by-influence with no labels". A pure unlabelled top-K (single supernode named "Texas" for all features, say) would be a different control and might yield a different hit count -- but it would also be unfair to auto, which is structurally a multi-supernode condition.
- **Single target (Dallas).** All 6 conditions use Dallas as target. The top-K saturation might be Dallas-specific if Dallas's top-21 happens to be unusually concept-pure. This is plausible because Dallas was the first state we curated and the auto pipeline is tuned on similar prompts.
- **Five sources** were chosen for diversity (`california_oakland`, `florida_miami`, `illinois_chicago`, `new_york_new_york_city`, `washington_seattle`) but they all share the same Fact-prompt template and are all US-state geographies. Generalisation to other prompt templates or domains is untested.

### Follow-up

- **Replicate at full 50-state scale.** The smoke shows the trajectory; the full run will tell us whether 14 vs 10 is a stable gap or whether it shrinks/grows at scale.
- **Test pure-Texas-label top-K.** Build a parallel set of top-K conditions where every feature is relabelled into a single `"Texas"` supernode (analogous to the human's compact 5-supernode design). This isolates "selection by influence" from "labels inherited from auto".
- **Apply this finding to the paper's swap-matrix narrative.** The previous framing -- "auto needs a 5× larger pool to achieve a comparable result" -- is misleading; it should be "auto needs the labels to deploy that pool selectively per variant".
- **Audit the noise supernodes for the full 50-state run.** If we are going to keep auto's full 1182-feature pool in production, we should confirm the ~16% noise share (`is`/`of`/`the`/`(entity) related`/...) is consistent across states.

---

## 2026-05-04 -- Influence-match audit, cross-domain: USA / books / products / paintings / sounds

**Status**: Concluded
**Confidence**: High
**Claim tested**: Follow-up to the USA entry below. Does the existing random
control's approximate influence-matching generalise across domains, or is it
a USA-specific coincidence of pool size?

### Question

Repeat the audit of `sum(node_influence)` per intervention (ablate and
amplify roles) on the four non-USA domains, to see whether labeled and
random are matched on injected static saliency everywhere or only for
large pools.

### Method

- Same script / metric as the USA entry, generalised to all 5 domains:
  `tools/audit_intervention_influence.py`.
- Runs compared per domain:
  `fullscale_<domain>_labeled` vs `fullscale_<domain>_random` (r0/r1/r2).
- Identity swaps excluded. `__m_tuned` variants excluded.
- Per-swap output CSVs:
  `output/research/audit_intervention_influence_{books,products,paintings,sounds}.csv`.
- USA CSV from the previous entry remains at
  `output/research/audit_intervention_influence_usa.csv`.

### Raw findings

**Per-domain sum(`node_influence`) -- amplify role, median and per-pair ratio labeled/random:**

| Domain    | N pairs | Labeled median | Random median (r0) | Median ratio lab/rnd | % pairs labeled > random (amplify, avg r0-r2) |
|-----------|--------:|---------------:|-------------------:|---------------------:|----------------------------------------------:|
| usa       | 2,450   | 0.1154         | 0.1128             | ~1.00                | 49.3%                                         |
| books     | 210     | 0.1878         | 0.1784             | ~1.04                | 52.9%                                         |
| paintings | 124     | 0.2056         | 0.1803             | ~1.14                | 55.6%                                         |
| sounds    | 30      | 0.0775         | 0.0636             | ~1.22                | 85.5%                                         |
| products  | 174     | 0.1500         | 0.1734             | ~0.86                | 38.9%                                         |

**Per-domain mean ratio labeled/random (amplify, pooled across r0-r2):**

| Domain    | Mean ratio | Q25-Q75 at r0     | Min-Max at r0 |
|-----------|-----------:|-------------------|---------------|
| usa       | 0.995      | 0.86 -- 1.13      | 0.35 -- 1.77  |
| books     | 1.057      | 0.91 -- 1.16      | 0.72 -- 1.69  |
| paintings | 1.081      | 0.94 -- 1.26      | 0.78 -- 1.61  |
| sounds    | 1.290      | 1.07 -- 1.49      | 0.88 -- 1.84  |
| products  | 0.910      | 0.72 -- 1.10      | 0.51 -- 1.50  |

**Per-pair sign of labeled - random (amplify), pooled over replicates:**

| Domain    | N pairs | Pairs where labeled > random |
|-----------|--------:|-----------------------------:|
| usa       | 2,450   | 49.3%                        |
| books     | 210     | 52.9%                        |
| paintings | 124     | 55.6%                        |
| sounds    | 30      | 85.5%                        |
| products  | 174     | 38.9%                        |

Feature count remains perfectly matched per role within each domain by
construction (e.g., products mean=142, median=116; sounds mean=83,
median=77; paintings mean=214, median=192; books mean=179, median=166).

### Interpretation

**The "approximately influence-matched" result does NOT hold uniformly
across domains.** Three distinct regimes emerge:

1. **USA and books: clean (near-perfect) match.** Medians within 5%,
   per-pair sign split ~50/50, mean ratio ~1.0. The labeled-vs-random
   comparisons there are not confounded by total injected influence.

2. **Paintings and sounds: systematic pro-labeled tilt.** Labeled carries
   ~14% more total `node_influence` on paintings and ~22% more on sounds.
   In sounds specifically, 85.5% of pairs have labeled > random. The
   existing random control **under-estimates the influence budget** of
   the labeled condition in these two domains, so any observed
   `labeled > random` gap in outcome metrics there is partially (possibly
   fully) explained by influence bulk rather than label correctness.

3. **Products: inverted tilt.** Random carries ~14% more total influence
   than labeled (median ratio 0.86, only 38.9% of pairs have
   labeled > random). The existing random control **over-estimates** the
   labeled condition's budget. If labeled beats random on outcomes in
   products, that is actually *stronger* evidence for label specificity
   than previously thought -- labels are winning with a smaller influence
   budget.

**Mechanism hypothesis.** The `RandomFeatureMatchedBuilder` excludes
labeled + concept-matching supernodes from the candidate pool, then
samples matched on layer histogram. Whether this excluded set is
systematically high- or low-influence relative to the remaining pool
depends on the domain:

- USA/books: large candidate pool, exclusion removes a small fraction of
  mass, residual influence distribution looks like the labeled one.
- Paintings/sounds: small pool. Labeled features sit in dense,
  high-`node_influence` concept supernodes; what remains is thinner and
  lower-influence on average, so random ends up below labeled.
- Products: apparently the opposite -- the pool outside the labeled
  supernodes contains higher-influence features than the labeled
  themselves. Plausibly because product concept supernodes are short and
  include peripheral / reverse-substring matches (see
  `AGENTIC_RESEARCH_GUIDE.md` §4) which dilute the labeled bag with
  low-influence features.

**Consequence for the cross-domain findings in
`FULLSCALE_CONTROL_REPORT.md`.** The "domain gradient"
(USA > books > products > paintings > sounds on targeting metrics)
interacts with the direction of the influence-match deviation:

- USA (clean) and books (clean) are the top two domains. Their
  `labeled > random` signal is uncontaminated.
- Paintings and sounds (bottom) have labeled carrying extra influence.
  The gradient at the bottom is partially artefactual.
- Products (middle) has labeled carrying less influence. Any
  `labeled > random` there is more robust than the audit alone would
  suggest.

Confidence: High. N is sufficient in books / paintings / products; only
sounds (N=30 per replicate) has wide CIs on the per-pair proportion, but
the effect size (22% median inflation) is large enough to be meaningful.

### Threats to validity

- **Static metric only.** `node_influence` is a graph-derived saliency,
  not the actual logit-space delta of the intervention. The same caveat
  as the USA entry applies: matching on this metric is necessary but not
  sufficient for matching on real effect.
- **Small-sample noise for sounds.** N=30 pairs per replicate. The 83-93%
  "labeled > random" rates are consistent across r0/r1/r2, so the effect
  is stable under reseeding, but absolute magnitude estimates have wide
  CIs.
- **Dedup by max across `ctx_idx`.** Per-position sum could change the
  numbers; likely does not flip any direction since the per-domain
  imbalance is consistent across both roles (ablate and amplify move
  together).
- **Exclusions in `RandomFeatureMatchedBuilder`.** The random pool
  explicitly excludes labeled and concept-matching supernodes. The
  products inversion could be driven entirely by what those exclusions
  remove, which is dataset-specific. Worth verifying by reading the
  actual excluded-feature mass per domain.

### What this does and does not establish

- **Establishes**: the clean-match USA result is not a universal property
  of the pipeline. Two domains have notable pro-labeled tilt, one has a
  clear pro-random tilt.
- **Does not establish**: that any of the outcome-metric gaps
  (`vs_max`, `gap_closure`, `rank_in_group`) are actually driven by
  influence rather than structure. That requires regressing outcome on
  influence-gap within domain, which is the obvious next investigation.

### Follow-up

- [ ] **Outcome regression.** For each domain, regress the per-pair
      labeled-vs-random outcome gap on the per-pair influence gap. If
      slope is ~0 and R^2 is low, influence is not the driver of outcome
      differences in that domain. If slope is large and positive, the
      outcome gap is partly explained by influence.
- [ ] **Inspect products exclusions.** Why is the residual pool in
      products higher-influence than the labeled set? Read
      `RandomFeatureMatchedBuilder` + grouping CSVs for a sample of
      products pairs to identify the mechanism.
- [ ] **Re-examine sounds conclusions.** Sounds is already the weakest
      domain. Any residual `labeled > random` there should be discounted
      by the ~22% labeled influence advantage.
- [ ] **Consider adding an explicit influence-matched random control**
      for paintings and sounds in future runs. It is low priority for
      USA and books.

### Artifacts

- Script: `tools/audit_intervention_influence.py`
- CSVs:
  - `output/research/audit_intervention_influence_usa.csv`
  - `output/research/audit_intervention_influence_books.csv`
  - `output/research/audit_intervention_influence_products.csv`
  - `output/research/audit_intervention_influence_paintings.csv`
  - `output/research/audit_intervention_influence_sounds.csv`

---

## 2026-05-04 -- Is "labeled > random" confounded by total injected node_influence? (USA states)

**Status**: Concluded
**Confidence**: Medium-High
**Claim tested**: Adversarial null to `FULLSCALE_CONTROL_REPORT.md` -- "labeled
interventions outperform random matched interventions because the labels name
the right circuits". Alternative null: "labeled interventions happen to carry
higher total per-feature influence, and any intervention with comparable
influence at matching layers would work as well".

### Question

Does the existing random-matched control (`RandomFeatureMatchedBuilder`, which
matches count + layer histogram + excludes labeled features) accidentally also
match on total `node_influence`? If yes, the labeled-vs-random contrast is
not confounded by influence and the finding is clean. If no, the finding is
partially explained by influence bulk and needs a new influence-matched control.

### Method

- Dataset: `usa_states_batch`.
- Runs: `fullscale_usa_labeled` (canonical), `fullscale_usa_random` (r0,r1,r2).
- Non-identity swap pairs: 2,450 per condition, 9,800 total measurements.
- Per swap: read `work/<swap_id>/features.json`, split by role
  (M = -2 -> ablate from source graph; M = 20 -> amplify from target graph).
- For each (layer, feature_id) in the intervention, look up
  `node_influence` in the entity's
  `00 Graph Generation/graph_feature_static_metrics.csv`,
  deduplicated to one value per (layer, id) using the max across `ctx_idx`.
- Compute `sum(node_influence)` per role per swap.
- Script: `tools/audit_intervention_influence.py`.
- Data: `output/research/audit_intervention_influence_usa.csv` (9,800 rows).

### Raw findings

**Feature counts per role (identical by construction across conditions):**
N=2,450, mean 88.86, median 82, Q25-Q75 = [69, 94], range [40, 200].

**Sum of `node_influence` per role, per condition:**

| Condition  | Role    | Mean   | Median | Q25    | Q75    |
|------------|---------|--------|--------|--------|--------|
| labeled    | ablate  | 0.1161 | 0.1154 | 0.0968 | 0.1246 |
| labeled    | amplify | 0.1161 | 0.1154 | 0.0968 | 0.1246 |
| random_r0  | ablate  | 0.1185 | 0.1126 | 0.0948 | 0.1347 |
| random_r0  | amplify | 0.1184 | 0.1128 | 0.0947 | 0.1334 |
| random_r1  | ablate  | 0.1184 | 0.1131 | 0.0943 | 0.1338 |
| random_r1  | amplify | 0.1190 | 0.1143 | 0.0956 | 0.1339 |
| random_r2  | ablate  | 0.1185 | 0.1133 | 0.0945 | 0.1344 |
| random_r2  | amplify | 0.1183 | 0.1136 | 0.0948 | 0.1332 |

Random is slightly higher on mean (+0.002, ~2%) than labeled; medians are
within ~0.003 of each other.

**Per-pair ratio labeled/random (sum node_influence), pooled across replicates:**

| Replicate | Role    | Mean ratio | Median | Q25   | Q75   | Min   | Max   |
|-----------|---------|-----------:|-------:|------:|------:|------:|------:|
| r0        | ablate  | 0.998      | 1.004  | 0.851 | 1.136 | 0.361 | 1.888 |
| r0        | amplify | 0.998      | 0.998  | 0.856 | 1.130 | 0.354 | 1.769 |
| r1        | ablate  | 0.998      | 0.994  | 0.857 | 1.137 | 0.403 | 1.861 |
| r1        | amplify | 0.990      | 0.992  | 0.851 | 1.123 | 0.400 | 1.783 |
| r2        | ablate  | 0.998      | 0.999  | 0.861 | 1.129 | 0.384 | 1.790 |
| r2        | amplify | 0.996      | 1.000  | 0.860 | 1.120 | 0.418 | 1.745 |

Ratios are centred on 1.0 at the mean and median; 50% of pairs lie within
[0.85, 1.13].

**Sign of labeled - random per pair:**

| Replicate | Pairs labeled > random (ablate) | Pairs labeled > random (amplify) |
|-----------|---------------------------------|----------------------------------|
| r0        | 1253 / 2450 (51.1%)             | 1213 / 2450 (49.5%)              |
| r1        | 1191 / 2450 (48.6%)             | 1189 / 2450 (48.5%)              |
| r2        | 1222 / 2450 (49.9%)             | 1226 / 2450 (50.0%)              |

Essentially a coin flip. Mean per-pair difference is slightly negative
(-0.002 to -0.003), i.e., random is marginally higher on average.

### Interpretation

**The existing random-matched control is already approximately
influence-matched, with no systematic advantage for labeled interventions.**
The total `node_influence` distribution for labeled is indistinguishable
from random at the population level (means within 2%, medians within 3%),
and at the pair level labeled beats random on total influence in ~50% of
pairs -- noise, not signal.

Consequence for the `labeled > random` finding in
`FULLSCALE_CONTROL_REPORT.md`: that gap is NOT explained by labeled
interventions carrying more total per-feature influence. Whatever drives
the vsMax / gap-closure / RkGrp advantage of labeled over random has to
come from somewhere else -- presumably from which specific features sit at
those layers with that total influence, i.e., the structural content the
labels are tracking. **This makes the existing labeled-vs-random comparison
cleaner than initially suspected.**

Mechanism hypothesis (not verified here): the layer-histogram match in
`RandomFeatureMatchedBuilder` is doing most of the influence-matching work
implicitly. `node_influence` per feature is roughly stratified by layer,
so matching the layer distribution already drags the per-feature influence
distribution close to the labeled bag's.

Confidence: Medium-High. The numbers are unambiguous at N=2,450 per
replicate and 7,350 random samples total, but the analysis uses a static
saliency metric from the graph (`node_influence`) rather than the actual
logit-space effect of the intervention.

### Threats to validity

- **Metric scope**: uses `node_influence` from
  `graph_feature_static_metrics.csv`, which is a static graph-derived
  saliency. It does not reflect the actual per-feature contribution to the
  final logit delta under intervention. Matching on this metric is
  necessary but not sufficient for matching on "real" influence.
- **Per-position dedup**: the CSV has multiple rows per (layer, id) due to
  `ctx_idx`; I take the max. Using sum instead could shift distributions,
  but the labeled-vs-random contrast would be affected symmetrically.
- **Domain coverage**: only USA states tested. The candidate pool for the
  non-USA domains is smaller, which could break the approximate influence
  match there.
- **Exclusion asymmetry**: random excludes labeled features. If labeled
  features are concentrated in the extreme upper tail of influence, the
  remaining pool could be slightly lower on average. The symmetric means
  here (0.118 vs 0.116) suggest any such tail effect is negligible at
  population scale but could matter for individual pairs.
- **Matched count is a confound too**: this analysis treats count-matching
  as given. A separate question (not addressed here) is whether a much
  smaller random intervention can reach the same steering.

### What this does NOT establish

- That labels encode semantic structure beyond what high-node-influence
  features in matching layers would capture. The fixed-M influence sweep
  (Experiment B, still pending) would address this.
- That the finding generalises to books / products / paintings / sounds.
- That `node_influence`-sum parity corresponds to equal real-intervention
  effect magnitude.

### Follow-up

- [ ] Repeat the same audit on books, products, paintings, sounds -- check
      whether the approximate influence match survives when the candidate
      pool is smaller. Expected pool sizes (from grouping CSVs) are far
      smaller for non-USA domains.
- [ ] Run the fixed-M influence sweep (Experiment B): pick features by
      rank on `node_influence` (top-K, features [K+1, 2K], ..., bottom-K)
      at fixed M and plot hit / vsMax vs mean influence. This tests the
      *stronger* claim -- that the labels do more than exploit layer
      structure.
- [ ] Optional: replace the static `node_influence` proxy with the true
      ablate/amplify logit delta per feature and redo this audit. If the
      parity holds under that metric too, the case is closed.

### Artifacts

- Script: `tools/audit_intervention_influence.py`
- Data:   `output/research/audit_intervention_influence_usa.csv`
