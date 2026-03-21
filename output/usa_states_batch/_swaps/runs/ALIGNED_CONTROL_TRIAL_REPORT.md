# Capital-Aligned Control Trial Report

## Overview

This report corrects the answer-field misalignment in the previous trial.
All metrics now track the **capital** token (the actual prompt completion target)
while keeping `concept_fields: [state, capital, city]` for full three-field
supernode matching. The `swap.answer_field: capital` override decouples
evaluation/trajectory scoring from the intervention field list.

**Runs**: 55 total steering runs on 5 USA swap pairs.
- Labeled baseline: 5 runs
- Random feature control: 15 runs (3 replicates x 5 pairs)
- Field-based additivity: 35 runs (7 field subsets x 5 pairs)

**Alignment verification**: `evaluation.answer_field == "capital"` in all results.
Trajectory tracks capital tokens (e.g., " Atlanta" / " Austin" for TX->GA).
Contrast group consists of 48 other state capitals.

---

## Aggregate Results

| Condition | N | Hit% | Sup% | GapCl | TgtRk | vsMax | RkGrp |
|-----------|---|------|------|-------|-------|-------|-------|
| **labeled** | **5** | **80%** | **100%** | **8.7** | **10** | **5.9** | **1.0** |
| random | 15 | 0% | 80% | 1.5 | 1157 | -1.5 | 6.0 |
| f:state | 5 | 40% | 80% | 6.5 | 16 | 6.4 | 1.0 |
| f:capital | 5 | 40% | 100% | 3.9 | 39 | 4.3 | 1.2 |
| f:city | 5 | 0% | 60% | 1.5 | 794 | -1.8 | 7.6 |
| f:st+cap | 5 | 100% | 100% | 7.9 | 2 | 6.4 | 1.0 |
| f:all3 | 5 | 80% | 100% | 8.7 | 10 | 5.9 | 1.0 |

**Metric definitions**:
- Hit%: target capital appears in steered output
- Sup%: source capital absent from steered output
- GapCl: max(target_logit - source_logit) over generation minus initial gap
- TgtRk: best (lowest) rank achieved by target capital token
- vsMax: best(target_logit - max(other 48 capitals)) -- positive means target beats all
- RkGrp: best rank of target among 49 capitals (1 = top)

---

## Key Findings

### 1. Labeled vs Random: strong specificity confirmed

Labeled interventions produce 80% exact match on capitals; structurally matched
random features produce 0%. The gap is visible on every continuous metric:

- Gap closure: 8.7 vs 1.5 (5.8x)
- Target best rank: 10 vs 1157 (115x worse for random)
- vsMax: +5.9 vs -1.5 (labeled target beats all other capitals; random target is below max)
- Rank within group: 1.0 vs 6.0 (labeled always rank 1)

Random controls achieve high suppression (80%) because ablating any large feature
set disrupts the source output. But suppression without target specificity is
generic disruption, not concept-level steering.

### 2. State+capital is the strongest 2-field combination

| Combination | Hit% | Sup% | GapCl | TgtRk | vsMax | RkGrp |
|-------------|------|------|-------|-------|-------|-------|
| state+capital | **100%** | **100%** | **7.9** | **2** | **6.4** | **1.0** |
| labeled (all 3) | 80% | 100% | 8.7 | 10 | 5.9 | 1.0 |

State+capital achieves 100% hit rate -- *higher* than the full 3-field labeled
intervention (80%). This suggests that city supernodes add noise that
occasionally degrades the capital answer.

### 3. No single field dominates universally

| Field | Best pair | TgtRk | Worst pair | TgtRk |
|-------|-----------|-------|------------|-------|
| state | CA->FL | 1 | TX->GA | 18 |
| capital | TX->GA | 2 | NM->PA | 4 |
| city | TX->GA | 32 | GA->TX | 2741 |

State supernodes are strongest for 3/5 pairs (NM, CA, GA reverse).
Capital supernodes are strongest for TX->GA.
City supernodes never achieve competitive capital-token rank.

### 4. City groupings are noise for capital-answer steering

City supernodes perform at random-control level on capital-aligned metrics:
- Mean vsMax: -1.8 (below zero, like random)
- Mean rank within group: 7.6 (like random at 6.0)
- 0% exact match on capitals

This is expected: city supernodes encode the prompt input concept, not the
answer concept. They should not help steer toward the target capital.

### 5. Colorado confirms token overlap confound

State and city variants produce identical results for CO->NY because
"Colorado" appears in both "Colorado" (state) and "Colorado Springs" (city),
matching the same supernodes. The capital-only variant (targeting "Denver" /
"Albany") is the only independent signal for this pair.

---

## Methodological Caveats

### Feature count imbalance

Field subsets differ in total perturbation:

| Variant | Mean ablate | Mean amplify | Mean total |
|---------|-------------|--------------|------------|
| state | 17 | 18 | 35 |
| capital | 34 | 32 | 66 |
| city | 38 | 27 | 65 |
| st+cap | 50 | 50 | 100 |
| all3 | 88 | 69 | 157 |

State-only uses ~35 features while all3 uses ~157. Differences in steering
strength could partly reflect feature count rather than concept specificity.
The random control (matched on count) provides a partial normalization, but
field-to-field comparisons are not magnitude-controlled.

### Substring overlap

"Colorado" / "Colorado Springs" share supernode matches. "New York" / "New
York City" share first-token resolution (" New"). These cases conflate
field isolation with string-level overlap.

### Answer_field alignment

This trial uses `swap.answer_field: capital` to decouple trajectory scoring
from intervention matching. The previous trial tracked city tokens; results
are not directly comparable. The `answer_field` override is now implemented
as `resolve_answer_field()` in `swap_evaluator.py`, used by both the
evaluator and the runner.

### Sample size

5 pairs, 3 random replicates. Patterns are consistent but formal inference
requires the full 50x50 matrix (2450 non-identity pairs) with 100+
replicates per pair.

---

## Implementation

All configs use:
```yaml
swap:
  concept_fields: [state, capital, city]
  answer_field: capital
```

Run IDs: `trial_aligned_labeled`, `trial_aligned_random`, `trial_aligned_field_add`

No existing data was overwritten. The `answer_field` override is backward-compatible:
existing configs without it behave identically to before.
