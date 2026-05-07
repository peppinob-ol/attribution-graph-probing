# Investigation Log

Append-only log of investigations. Newest entries at the top.
Entry format per `AGENTIC_RESEARCH_GUIDE.md` §9.2:
Question / Method / Raw findings / Interpretation / Threats to validity / Follow-up.
Do not edit past entries; if a finding is wrong, add a new entry that references and corrects it.

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
