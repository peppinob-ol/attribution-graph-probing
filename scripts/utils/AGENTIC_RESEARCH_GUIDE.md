# Agentic Research Guide: Attribution Graph Interpretation

Guidelines for LLM agents conducting field research on this codebase.
This document describes the data, tools, research context, and investigation
patterns needed for qualitative and quantitative analysis of attribution graph
feature swapping experiments.

---

## 1. Research Context

This project tests whether behavioral labels assigned to CLT (Cross-Layer
Transcoder) features via probe prompting have genuine causal relevance, or
whether the observed steering effects are artifacts of generic perturbation.

**The core question**: when we ablate "source" features and amplify "target"
features between entities, does the model produce entity-specific outputs
because the labels are correct, or because any sufficiently large perturbation
shifts logits in approximately the right direction?

### Key documents

| Document | Content |
|----------|---------|
| `METHODOLOGY_REPORT.md` | Full pipeline spec, claims at 3 epistemic levels, proposed controls |
| `output/FULLSCALE_CONTROL_REPORT.md` | 33k-run results: labeled vs random, field additivity |

### Established findings

1. **Labeled > random** on targeting metrics (vsMax, RkGrp) in 4/5 domains
2. **Suppression is generic** -- random features suppress equally well
3. **"Less is more"** -- intermediate+answer fields beat the full triple
4. **Domain gradient**: USA > books > products > paintings > sounds
5. **Error node density** correlates with domain difficulty
6. **Flip@0 is mechanically trivial** -- gap closure is the real discriminator

### Open questions for investigation

- Why do some entity pairs succeed spectacularly while similar ones fail?
- Does the reverse substring confound in concept matching bias results?
- How much of the "less is more" effect is explained by feature count dilution
  vs genuine interference between field circuits?
- Are there entity-level predictors of swap success beyond error_node_pct?
- Do review-flagged (ambiguous) features contribute positively or negatively?

---

## 2. Data Layout

All experiment data lives under `output/<dataset>_batch/`.

### Datasets

| Dataset | Dir name | Entities | Pairs | Concept fields |
|---------|----------|----------|-------|----------------|
| USA States | `usa_states_batch` | 50 | 2,450 | state, capital, city |
| Books | `book_characters_authors_batch` | 16 | 240 | character, book, author |
| Products | `products_founders_batch` | 12 | 132 | product, company, founder |
| Paintings | `paintings_painters_batch` | 10 | 90 | painting, painter, first_name |

### Per-entity data (upstream pipeline)

```
output/<dataset>/<Entity_Name>/
    manifest.json                          # metadata, neuronpedia URL
    00 Graph Generation/
        graph.json                         # full attribution graph (nodes + edges)
        graph_feature_static_metrics.csv   # per-feature: layer, feature, node_influence, cumulative_influence
        selected_features_with_nodes.json  # features selected for probing
    01 Prompt Probing/
        prompts.json                       # probe prompts used
        activations_dump.json              # per-feature per-probe activations
    02 Node Grouping/
        node_grouping.csv                  # per-(feature, probe) classification + supernode assignment
```

### Per-run swap data

```
output/<dataset>/_swaps/runs/<run_id>/
    run_manifest.json          # run metadata, git hash, config summary
    config_resolved.json       # full resolved YAML config
    by_source/<from_slug>/
        to_<to_slug>.json                   # canonical (labeled) swap
        to_<to_slug>__add_state.json        # field-additivity variant
        to_<to_slug>__add_capital.json      # ...
        to_<to_slug>__r0.json               # random replicate 0
        to_<to_slug>__r1.json               # random replicate 1
```

### Run naming conventions

| Pattern | Meaning |
|---------|---------|
| `fullscale_<domain>_labeled` | Full labeled intervention (all concept fields) |
| `fullscale_<domain>_random` | Random-feature-matched control (3 replicates) |
| `fullscale_<domain>_field_add` | Field additivity (7 variants per pair) |
| `full_50states_v1` | Legacy labeled run (USA states only) |

### Swap JSON schema (key fields)

Each swap JSON contains:

```
swap_id, source{slug, state, capital, city, ...}, target{...}
interventions{ablate_count, amplify_count, total_count}
evaluation:
    exact_match{steered_has_to_answer, from_suppressed, first_token_matches_target, ...}
    first_token{default, default_prob, steered, steered_prob}
    target_in_topk{to_answer_in_steered_topk, from_answer_in_default_topk, ...}
    raw{default_output, steered_output, default_topk, steered_topk}
    logit_trajectory:
        summary{flip_position, initial_gap, best_gap, gap_closure, control_stability_mean}
        contrast_groups.same_dataset.aggregate{best_target_minus_max, best_rank_within, ...}
    baseline_logits{target{logit, prob, rank}, source{logit, prob, rank}}
    position_0_comparison{gap_closure_0, flip_at_0, target_rank_improvement}
metadata.control{control_mode, concept_subsets_used, diagnostics{active_fields, ...}}
config{M_ablate, M_amplify, temperature, seed}
```

---

## 3. Research Toolkit

Three modules in `scripts/utils/`. Import with:

```python
import sys; sys.path.insert(0, '.')
from scripts.utils.swap_query import SwapQuery
from scripts.utils.swap_stats import SwapStats
from scripts.utils.pipeline_tracer import PipelineTracer
```

### SwapQuery -- individual sample access

```python
q = SwapQuery()

# Discovery
q.list_datasets()                              # -> ['usa_states_batch', ...]
q.list_runs('usa_states_batch')                # -> ['fullscale_usa_labeled', ...]
q.list_variants('usa_states_batch', 'fullscale_usa_field_add')  # -> ['add_state', ...]
q.entity_error_nodes('usa_states_batch')       # -> {'slug': pct, ...}

# Search (returns List[SwapSummary])
results = q.search(
    dataset='usa_states_batch',
    run='fullscale_usa_field_add',
    variant='add_state',           # None = all variants, '' = canonical only
    source='mississippi',          # substring filter on source slug
    target=None,                   # substring filter on target slug
    sort_by='vs_max',              # any numeric field on SwapSummary
    ascending=False,
    top_n=10,
    where=lambda s: s.steered_has_to_answer is True,  # custom filter
    skip_identity=True,
)
q.describe_search(results)

# Full detail (returns raw JSON dict + _query enrichment)
detail = q.get('usa_states_batch', 'fullscale_usa_field_add',
               'mississippi_gulfport', 'arizona_tucson', variant='add_state')
q.describe(detail)
```

#### SwapSummary sortable/filterable fields (37 total)

**Entity**: `source_error_node_pct`, `target_error_node_pct`
**Evaluation flags**: `steered_has_to_answer`, `from_suppressed`, `first_token_matches_target`, `flip_at_0`
**First token**: `default_first_prob`, `steered_first_prob`
**Trajectory**: `flip_position`, `initial_gap`, `best_gap`, `gap_closure`, `control_stability_mean`
**Contrast group**: `vs_max`, `vs_topk`, `rank_in_group`
**Baseline**: `target_baseline_rank`, `source_baseline_rank`
**Position 0**: `gap_closure_0`, `target_rank_improvement`
**Intervention**: `ablate_count`, `amplify_count`, `total_count`
**Classification**: `tier`
**Text**: `default_output_preview`, `steered_output_preview`

### SwapStats -- aggregation and comparison

```python
s = SwapStats(q)

# Aggregate stats for any filtered condition
agg = s.aggregate('usa_states_batch', 'fullscale_usa_field_add',
                   variant='add_state')
s.print_aggregate(agg)

# Compare two conditions with effect sizes + bootstrap CIs
comp = s.compare(
    a=dict(dataset='usa_states_batch', run='fullscale_usa_labeled', label='labeled'),
    b=dict(dataset='usa_states_batch', run='fullscale_usa_random', label='random'),
    metrics=['vs_max', 'gap_closure', 'rank_in_group'],
    bootstrap_n=2000,
)
s.print_comparison(comp)

# Per-entity breakdown
rows = s.per_entity('usa_states_batch', 'fullscale_usa_field_add',
                     variant='add_state', role='source')
s.print_entity_table(rows, sort_by='error_node_pct')

# Same pair across conditions
paired = s.cross_run(
    'usa_states_batch', 'mississippi_gulfport', 'arizona_tucson',
    runs={
        'labeled':      'fullscale_usa_labeled',
        'random (r0)':  ('fullscale_usa_random', 'r0'),
        'state only':   ('fullscale_usa_field_add', 'add_state'),
        'state+cap':    ('fullscale_usa_field_add', 'add_state_capital'),
        'all fields':   ('fullscale_usa_field_add', 'add_state_capital_city'),
    },
)
s.print_cross_run(paired)
```

### PipelineTracer -- upstream debugging

```python
t = PipelineTracer()

# Entity profile: graph nodes, error budget, supernode breakdown
gp, grp = t.entity_profile('usa_states_batch', 'mississippi_gulfport')
t.print_entity_profile(gp, grp)

# Concept-to-supernode matching trace
trace = t.trace_swap_matching(
    'usa_states_batch', 'mississippi_gulfport', 'arizona_tucson',
    concept_fields=['state'],
)
t.print_matching_trace(trace)
# Shows exactly which supernodes match each concept field,
# including confounds like "is" matching "mississippi"

# Quality table: all entities in a dataset
table = t.grouping_quality_table('usa_states_batch')
t.print_quality_table(table)
```

---

## 4. Known Confounds and Pipeline Quirks

When investigating individual samples, check for these known issues:

### Reverse substring matching

The concept-to-supernode matcher uses bidirectional substring matching:
`concept_word in supernode_name OR supernode_name in concept_word`.
This causes false positives:

- "mississippi" matches the "is" supernode (copula features get ablated)
- "indiana" matches "india"
- "colorado" in "colorado_springs" creates token overlap

Use `PipelineTracer.trace_swap_matching()` to verify what actually gets matched.

### Token overlap entities (USA)

6 entities have token overlap between prompt city and state name:
`colorado_colorado_springs`, `new_york_new_york_city`,
`virginia_virginia_beach`, `idaho_idaho_falls`,
`missouri_kansas_city`, `indiana_fort_wayne`.

These tend to have **worse** swap performance as source (attention circuits
bind the overlapping token strongly to source output). Check
`source_error_node_pct` is not the explanation before attributing to overlap.

### Grouping blacklist

The pipeline blacklists certain tokens from forming supernodes:
- Always: `<bos>`
- Per config: `entity` (non-USA), sometimes others

Check `config_resolved.json` for the run's `grouping.blacklist_tokens`.

### Review-flagged features

Features classified as "Ambiguous" in `node_grouping.csv` have
`review=True`. These got assigned to a supernode anyway but their
classification is uncertain. Count with `GroupingProfile.review_flagged`.

### Dictionary (fallback) subtype

Features classified as "Semantic Dictionary (fallback)" matched the
dictionary rule but with lower confidence. The `(fallback)` tag means
the peak consistency was above threshold but the feature's behavior was
not perfectly clean. Large supernodes dominated by fallback features
(e.g., "port" with 375 rows for Gulfport) may be noisy.

### Node grouping CSV row count vs unique features

`node_grouping.csv` has one row per (feature, probe) pair, not per unique
feature. A supernode with N=375 rows might contain far fewer unique features.
The actual intervention feature count is in the swap JSON
(`interventions.ablate_count` / `amplify_count`).

### Error node influence

Error nodes represent CLT reconstruction error -- the "dark matter" of model
computation. `error_node_influence_pct` measures what fraction of total
`node_influence` belongs to features with `feature == -1` (error features).
Higher values mean more of the circuit is invisible to the pipeline.

---

## 5. Investigation Patterns

### Pattern A: "Why did this swap succeed/fail?"

1. Pick a sample with `q.search()` (e.g., high gap_closure + hit=False)
2. Get full detail with `q.get()` and `q.describe()`
3. Check concept matching with `t.trace_swap_matching()`
4. Compare across conditions with `s.cross_run()`
5. Inspect entity graph quality with `t.entity_profile()`

### Pattern B: "Is metric X predictive of success?"

1. Get per-entity breakdown with `s.per_entity()`
2. Look at the table sorted by the metric of interest
3. Check if hit_rate / mean_vs_max correlate with the metric
4. Use `q.search(where=lambda s: ...)` to find edge cases

### Pattern C: "Does condition A outperform condition B?"

1. Run `s.compare(a=..., b=...)` with the two conditions
2. Check Cohen's d for effect size and bootstrap CI for significance
3. Look at rate differences (hit%, suppression%) and metric differences
4. Drill into specific pairs with `s.cross_run()` to understand why

### Pattern D: "What explains the domain gradient?"

1. Run `s.aggregate()` for each domain's labeled run
2. Compare error_node_pct distributions across domains
3. Check per-entity quality with `t.grouping_quality_table()`
4. Look for structural patterns: graph size, supernode count, feature count

### Pattern E: "Is there a pipeline bug/quirk affecting results?"

1. Use `t.trace_swap_matching()` on suspicious pairs
2. Check if unexpected supernodes match (reverse substring)
3. Count review-flagged features in the entity's grouping
4. Verify intervention counts match expected feature counts
5. Check `config_resolved.json` for unexpected config values

---

## 6. Metric Reference

### Primary targeting metrics (higher = better steering)

| Metric | Definition | Good value |
|--------|-----------|------------|
| **vsMax** | Target logit minus max other answer (best over trajectory) | > 0 means target beats strongest competitor |
| **RkGrp** | Best rank within answer contrast group | 1 = target is top answer |
| **Hit%** | Target answer appears in steered output | Binary success |
| **Gap closure** | max(target-source gap) minus initial gap | > 0 means improvement |

### Suppression metrics

| Metric | Definition | Note |
|--------|-----------|------|
| **Sup%** | Source answer absent from steered output | Generic -- random achieves ~80%+ |
| **from_suppressed** | Same, per-sample boolean | |

### Trajectory metrics

| Metric | Definition | Interpretation |
|--------|-----------|----------------|
| **flip_position** | First step where target rank < source rank | 0 = immediate flip (often mechanical) |
| **initial_gap** | target_logit - source_logit at position 0 | Negative = source leads initially |
| **best_gap** | Maximum gap over trajectory | How dominant target ever gets |
| **control_stability_mean** | Mean absolute logit change of control tokens | High = intervention is not specific |

### Entity-level metrics

| Metric | Source | Interpretation |
|--------|--------|----------------|
| **error_node_influence_pct** | `graph_feature_static_metrics.csv` | Higher = more invisible computation |
| **n_supernodes** | `node_grouping.csv` | More supernodes = more features identified |
| **review_flagged** | `node_grouping.csv` review=True | More = lower grouping confidence |

---

## 7. Tips for Effective Investigation

- **Start broad, then narrow**: use `s.aggregate()` to understand a condition,
  then `q.search()` to find interesting samples, then `q.describe()` + `t.trace_swap_matching()`
  for deep dives.

- **Always compare conditions**: a metric for one condition is meaningless
  without a baseline. Use `s.compare()` or `s.cross_run()`.

- **Check the raw output**: `steered_output` in `q.describe()` often reveals
  things metrics miss -- the model might produce a geographically coherent
  but wrong answer that no metric captures.

- **Watch for mechanical effects**: flip@0 near 100% does not mean success.
  Gap closure and vsMax are the real discriminators.

- **Error nodes matter**: before concluding a feature label is wrong, check
  if the entity has high error_node_influence_pct (> 14% is top quartile for
  USA states).

- **Cross-domain comparison needs care**: T5 (hit) definitions differ
  across domains. Use strict metrics (vsMax, RkGrp) for cross-domain claims.
  USA "hit" uses geographic classifier; non-USA uses word-level fuzzy match.

- **Scan times**: `q.search()` on a full run takes 2-3 seconds.
  `s.compare()` with random controls (7350 files) takes ~30 seconds.
  `t.entity_profile()` takes < 2 seconds.

---

## 8. Epistemic Guidelines

The purpose of this research is to probe, stress-test, and potentially
falsify claims made in `METHODOLOGY_REPORT.md` and
`output/FULLSCALE_CONTROL_REPORT.md`. The default posture is suspicion,
not confirmation.

### 8.1 Default to suspicion

Every result could be an artifact of:
- The pipeline (concept matching quirks, blacklist gaps, fallback classifications)
- The metric definition (fuzzy T5 matching, mechanical flip@0, arbitrary thresholds)
- The data (small N, entity-specific confounds, token overlap)
- Coincidence (cherry-picked examples, multiple comparisons)

Before reporting a finding, ask: "What is the simplest boring explanation
for this result?" If a boring explanation exists and has not been ruled
out, state it prominently.

### 8.2 Claim / Evidence / Reasoning separation

Never mix what the data shows with what it means. In every investigation
entry and report:

1. **State the numbers first** (rates, effect sizes, CIs, sample details).
2. **Interpret second**, explicitly labeling the interpretive step.
3. **State the confidence level**: Low / Medium / High.
4. **State the epistemic level** the finding addresses:
   - L1: Operationally useful labels
   - L2: Downstream causal effects
   - L3: Full mechanistic explanation (this project does not claim L3)

### 8.3 Actively seek disconfirmation

After finding something that appears to support a claim:
1. Search for counterexamples (entities/pairs where the pattern breaks).
2. Check if the same pattern holds under a different condition (labeled vs
   random, different domain, different field subset).
3. Test whether a simpler mechanism explains the result (e.g., does
   feature count alone predict outcome as well as the "correct label"
   hypothesis?).
4. Check the pipeline trace to verify the intervention is what you think
   it is.

### 8.4 Check the denominator

Any rate (hit%, suppression%, flip%) must be accompanied by:
- N (how many samples)
- The population it is drawn from (which run, which variant, which filter)
- Whether identity swaps are included or excluded

A 100% hit rate on N=3 is noise. A 25% hit rate on N=2450 is signal.

### 8.5 Trace before concluding

Before attributing a swap outcome to feature quality, label correctness,
or domain difficulty:

1. Run `t.trace_swap_matching()` to check what actually gets matched.
   Watch for reverse substring confounds ("is" in "mississippi").
2. Check `error_node_influence_pct` for the source and target entities.
3. Verify `ablate_count` / `amplify_count` are in the expected range
   for the variant.
4. Read the raw `steered_output` -- metrics can miss important context.

### 8.6 Distinguish mechanical from meaningful

| Metric | Type | Interpretation |
|--------|------|----------------|
| flip@0 | **Mechanical** | Near-universal (~90-98%), reflects ablation+amplification arithmetic, not steering success |
| suppression rate | **Mostly mechanical** | Random controls achieve ~80%+ suppression; it is generic disruption |
| gap closure | **Meaningful** | Sustained logit improvement; 3.79 for USA vs 0.04 for books |
| vsMax | **Best discriminator** | Target logit minus strongest competitor in answer group |
| RkGrp | **Meaningful** | Rank within answer contrast group; labeled median 5 vs random 566 |
| Hit% | **Meaningful but noisy** | Binary; misses near-misses entirely |

Do not cite flip@0 or suppression as evidence of label quality.
These metrics succeed even with random features.

### 8.7 Report negative and null results

Findings that something is NOT significant, that a confound DOES explain
a result, or that a hypothesis FAILS are at least as valuable as positive
results. Do not omit them or bury them.

If an investigation yields "no clear signal," that is a finding. Write it up.

### 8.8 Write for a skeptical reader

Every claim in a report should survive the question: "But couldn't this
just be because of X?" If you cannot answer that question, the claim is
not ready to report. Move it to "Remaining uncertainties" instead.

---

## 9. Report Writing

### 9.1 Where reports live

All investigation output goes in `output/research/`.

| File | Purpose |
|------|---------|
| `_LOG.md` | Running investigation log (append-only, newest first) |
| `_TEMPLATE.md` | Template for summary reports (copy, don't edit) |
| `<topic>_report.md` | Periodic summary reports on specific claims |

### 9.2 Investigation log entries

Every investigation session should produce at least one entry in
`_LOG.md`. Copy the template block in that file and fill it in.

Required sections per entry:
- **Question**: what are we testing?
- **Method**: what queries were run?
- **Raw findings**: numbers only, no interpretation
- **Interpretation**: what it means, with confidence level
- **Threats to validity**: what could make this wrong (checklist)
- **Follow-up**: what to check next

Do not edit past entries. If a previous finding was wrong, add a new
entry that references and corrects it.

### 9.3 Summary reports

When an investigation topic has accumulated enough log entries to support
a conclusion (typically 3-5 entries exploring a claim from different
angles), write a summary report:

1. Copy `_TEMPLATE.md` to `<topic>_report.md`.
2. Fill in all sections, pulling evidence from log entries.
3. The "Alternative Explanations" table (Section 4) is mandatory -- if you
   cannot fill it, the investigation is not complete.
4. Write the Summary section last, after all evidence is assembled.

### 9.4 Naming conventions

- Log entries: use date + short topic in the heading
- Summary reports: `<topic>_report.md` where topic is snake_case
  (e.g., `field_additivity_less_is_more_report.md`,
  `error_node_predictiveness_report.md`,
  `reverse_substring_confound_report.md`)

### 9.5 What not to do

- Do not write a report that only confirms the methodology report's claims.
  The purpose is adversarial probing.
- Do not report aggregate statistics without checking individual samples.
  Aggregates hide important structure.
- Do not conclude based on a single entity, pair, or domain.
- Do not skip the "Threats to validity" section. If you have no threats,
  you have not thought hard enough.
