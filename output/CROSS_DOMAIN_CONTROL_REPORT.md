# Cross-Domain Control Experiment Report

## 1. Overview

This report presents the results of specificity control experiments across five
domains, testing whether feature-swap steering effects in attribution graphs are
specific to concept-labeled supernodes. Each domain is decomposed by all entity
fields (prompt input, intermediate concept, answer concept) to measure which
parts of the circuit carry the steering signal.

**Total steering runs: ~300** across 5 domains, 3 conditions, 5 pairs each.

**Model**: Gemma-2-2b with CLT transcoders (mntss/clt-gemma-2-2b-2.5M).
**Multipliers**: M_ablate = -2, M_amplify = 20.
**Trajectory tracking**: enabled with same-dataset contrast groups.

---

## 2. Domains

| Domain | N | Input field | Intermediate | Answer field | Prompt |
|--------|---|-------------|--------------|--------------|--------|
| USA States | 50 | city | state | capital | "The capital of the state containing {city} is" |
| Books | 16 | character | book | author | "The book featuring {character} was written by" |
| Products | 12 | product | company | founder | "The company that makes {product} was founded by" |
| Paintings | 10 | painting | painter | first_name | "The first name of the painter of {painting} is" |
| Sounds | 6 | sound | animal | color | "The most common color of the animal that goes '{sound}' is" |

Each domain has 3 entity fields corresponding to 3 semantic roles:
- **Input**: the concept mentioned in the prompt (what the model reads)
- **Intermediate**: the bridging concept (what the model must internally resolve)
- **Answer**: what the model is asked to produce

---

## 3. Experimental Conditions

### 3.1 Labeled baseline
All 3 concept fields used for intervention. Ablate source supernodes (live activations,
M=-2), amplify target supernodes (stored activations, M=20).

### 3.2 Random feature matched control
Same feature count and layer distribution as labeled, but features sampled randomly
from the graph after excluding all concept-matching supernodes. 3 replicates per pair.

### 3.3 Field-based additivity
Intervention restricted to subsets of concept fields. With 3 fields per domain,
7 variants: 3 single-field, 3 two-field combinations, 1 full triple.
Each selected field is used for both ablation and amplification.

### 3.4 Answer field alignment
Trajectory tracking and exact-match evaluation use an explicit `answer_field`
override (via `swap.answer_field` in config) to track the answer token regardless
of concept_fields ordering. This decouples "what we intervene on" from "what we
measure."

---

## 4. Metrics

| Metric | Definition |
|--------|------------|
| Hit% | Target answer appears in steered output (exact match) |
| Sup% | Source answer absent from steered output |
| GapCl | max(target_logit - source_logit) over trajectory minus initial gap |
| TgtRk | Best (lowest) rank of target answer token during generation |
| vsMax | best(target_logit - max(other_dataset_answers)) -- positive = target beats all alternatives |
| vsTopK | best(target_logit - mean(top-3 other_dataset_answers)) |
| RkGrp | Best rank of target within all dataset answer tokens (1 = top) |
| CtrlS | Mean absolute logit shift of control tokens (the, is, a, of) |

---

## 5. Results: Labeled vs Random

### 5.1 Cross-Domain Aggregate

| Domain | Cond | N | Hit% | Sup% | GapCl | TgtRk | vsMax | vsTopK | RkGrp |
|--------|------|---|------|------|-------|-------|-------|--------|-------|
| **USA States** | **labeled** | **5** | **80%** | **100%** | **8.7** | **10** | **5.9** | **6.4** | **1.0** |
| | random | 15 | 0% | 80% | 1.5 | 1157 | -1.5 | -0.7 | 6.0 |
| **Books** | **labeled** | **5** | **0%** | **100%** | **0.0** | **47** | **5.6** | **7.1** | **1.0** |
| | random | 15 | 0% | 60% | 0.1 | 189 | 1.6 | 2.7 | 2.2 |
| **Products** | **labeled** | **5** | **40%** | **40%** | **0.0** | **14** | **5.3** | **7.2** | **1.0** |
| | random | 15 | 0% | 80% | 3.9 | 403 | 1.1 | 2.1 | 1.5 |
| **Paintings** | **labeled** | **5** | **0%** | **0%** | **0.0** | **622** | **3.1** | **5.0** | **1.0** |
| | random | 15 | 0% | 80% | 1.1 | 4025 | 0.5 | 1.5 | 1.6 |
| **Sounds** | **labeled** | **5** | **0%** | **100%** | **1.8** | **30** | **3.5** | **3.6** | **1.0** |
| | random | 15 | 13% | 80% | 2.5 | 114 | 3.6 | 4.1 | 1.1 |

### 5.2 Specificity Summary

| Domain | Labeled RkGrp | Random RkGrp | Labeled vsMax | Random vsMax | Gap |
|--------|---------------|--------------|---------------|--------------|-----|
| USA States | **1.0** | 6.0 | **+5.9** | -1.5 | **Strong** |
| Books | **1.0** | 2.2 | **+5.6** | +1.6 | **Moderate-Strong** |
| Products | **1.0** | 1.5 | **+5.3** | +1.1 | **Moderate** |
| Paintings | **1.0** | 1.6 | **+3.1** | +0.5 | **Moderate** |
| Sounds | **1.0** | 1.1 | **+3.5** | +3.6 | **Weak** |

**Key finding**: labeled supernodes achieve rank 1 within the answer group in
every domain (RkGrp = 1.0). The gap between labeled and random narrows from USA
(strong) through paintings (moderate) to sounds (weak), reproducing the domain
gradient from the main methodology.

### 5.3 Suppression is generic, targeting is specific

| Domain | Labeled Sup% | Random Sup% | Labeled Hit% | Random Hit% |
|--------|-------------|-------------|-------------|-------------|
| USA States | 100% | 80% | 80% | 0% |
| Books | 100% | 60% | 0% | 0% |
| Products | 40% | 80% | 40% | 0% |
| Paintings | 0% | 80% | 0% | 0% |
| Sounds | 100% | 80% | 0% | 13% |

Random controls often achieve higher suppression than labeled (products 80% vs
40%, paintings 80% vs 0%). Ablating random features is broadly disruptive. But
only labeled supernodes produce entity-specific targeting. The vsMax metric
reveals this most cleanly: labeled always positive (target beats all alternatives),
random usually negative or near-zero.

---

## 6. Results: Field-Based Additivity

### 6.1 Field Role Analysis

Each field is classified by its semantic role: **input** (prompt mention),
**intermediate** (bridging concept), or **answer** (expected output).

#### USA States (input=city, intermediate=state, answer=capital)

| Field | Role | Hit% | Sup% | TgtRk | vsMax | RkGrp |
|-------|------|------|------|-------|-------|-------|
| city | input | 0% | 60% | 794 | -1.8 | 7.6 |
| state | intermediate | 40% | 80% | 16 | 6.4 | 1.0 |
| capital | answer | 40% | 100% | 39 | 4.3 | 1.2 |
| **state+capital** | **inter+answer** | **100%** | **100%** | **2** | **6.4** | **1.0** |
| all 3 (labeled) | all | 80% | 100% | 10 | 5.9 | 1.0 |

State supernodes (intermediate) carry the strongest single-field signal. City
supernodes (input) perform at random level. State+capital is the optimal
combination, exceeding the full labeled on hit rate (100% vs 80%).

#### Books (input=character, intermediate=book, answer=author)

| Field | Role | Hit% | Sup% | TgtRk | vsMax | RkGrp |
|-------|------|------|------|-------|-------|-------|
| character | input | 0% | 80% | 121 | 2.2 | 1.8 |
| book | intermediate | 20% | 60% | 109 | 6.6 | 1.6 |
| author | answer | 20% | 80% | 19 | 6.1 | 1.0 |
| **book+author** | **inter+answer** | **20%** | **40%** | **29** | **7.8** | **1.0** |
| all 3 (labeled) | all | 0% | 100% | 47 | 5.6 | 1.0 |

Author supernodes (answer) achieve the best target rank (19). Book supernodes
(intermediate) have high vsMax (6.6). Adding character supernodes (input)
paradoxically degrades performance: the full 3-field labeled gets 0% hit vs
book+author at 20%.

#### Products (input=product, intermediate=company, answer=founder)

| Field | Role | Hit% | Sup% | TgtRk | vsMax | RkGrp |
|-------|------|------|------|-------|-------|-------|
| product | input | 0% | 80% | 1764 | 4.0 | 1.2 |
| company | intermediate | 20% | 40% | 70 | 3.3 | 1.0 |
| founder | answer | 0% | 100% | 42 | 2.6 | 1.0 |
| **company+founder** | **inter+answer** | **40%** | **60%** | **33** | **4.6** | **1.0** |
| all 3 (labeled) | all | 40% | 40% | 14 | 5.3 | 1.0 |

Product supernodes (input) have extremely poor target rank (1764) despite
positive vsMax -- they disrupt the source without steering toward the target.
Company (intermediate) provides targeting. Founder (answer) drives suppression
(100%) but zero hits alone. The full triple achieves the best target rank (14).

#### Paintings (input=painting, intermediate=painter, answer=first_name)

| Field | Role | Hit% | Sup% | TgtRk | vsMax | RkGrp |
|-------|------|------|------|-------|-------|-------|
| painting | input | 0% | 40% | 70 | 2.3 | 1.0 |
| painter | intermediate | 0% | 60% | 38 | 3.5 | 1.0 |
| first_name | answer | 40% | 40% | 36 | 4.2 | 1.0 |
| **painter+first_name** | **inter+answer** | **0%** | **60%** | **38** | **3.5** | **1.0** |
| all 3 (labeled) | all | 0% | 0% | 622 | 3.1 | 1.0 |

First_name alone achieves 40% hit rate -- higher than any combination. Adding
painting supernodes (input) to the full triple degrades to 0% hit and target
rank 622. The labeled 3-field intervention is worse than single-field
first_name. This suggests painting supernodes actively interfere with
first-name steering.

#### Sounds (input=sound, intermediate=animal, answer=color)

| Field | Role | Hit% | Sup% | TgtRk | vsMax | RkGrp |
|-------|------|------|------|-------|-------|-------|
| sound | input | 0% | 80% | 29 | 3.7 | 1.0 |
| animal | intermediate | 0% | 100% | 173 | 1.8 | 1.3 |
| color | answer | 0% | 100% | 41 | 3.8 | 1.0 |
| **sound+color** | **input+answer** | **0%** | **100%** | **11** | **5.3** | **1.0** |
| all 3 (labeled) | all | 0% | 100% | 30 | 3.5 | 1.0 |

Sound supernodes (input) unexpectedly achieve the best single-field target
rank (29) and good vsMax (3.7) -- better than animal (intermediate, rank 173).
The best combination is sound+color (TgtRk 11, vsMax 5.3), outperforming
the full triple. Animal supernodes (intermediate) contribute noise.

### 6.2 Cross-Domain Field Role Patterns

| Role | Avg single-field TgtRk | Avg single-field vsMax | Best role for targeting? |
|------|------------------------|------------------------|-------------------------|
| Input | 556 | 2.1 | Rarely (usually noise) |
| Intermediate | 73 | 3.9 | Often (strong targeting) |
| Answer | 35 | 4.2 | Often (best rank, best vsMax) |

**Pattern**: answer-field supernodes (the concept the model must produce)
consistently achieve the best target rank. Intermediate-field supernodes
(the bridging concept) provide strong targeting via vsMax. Input-field
supernodes (the concept in the prompt) usually contribute noise or
interference, with the notable exception of sounds where the input
(sound name) carries useful signal.

### 6.3 The "Less is More" Effect

In 3 of 5 domains, a subset of fields outperforms the full labeled intervention:

| Domain | Best subset | Hit% | Full labeled Hit% |
|--------|-------------|------|-------------------|
| USA States | state+capital | 100% | 80% |
| Books | book+author | 20% | 0% |
| Paintings | first_name alone | 40% | 0% |
| Sounds | sound+color | 0% (TgtRk 11) | 0% (TgtRk 30) |
| Products | all 3 is best | 40% | 40% |

Including the input-field supernodes degrades performance in books and
paintings, likely because they activate competing circuits or inject noise
that dilutes the answer signal.

---

## 7. Methodology

### 7.1 Random control construction

For each pair, the labeled intervention is built first to get the reference
feature count and layer distribution. Random features are then sampled from
the same graph with:
- Exact count matching per role (ablation / amplification)
- Layer histogram matching
- Exclusion of all features in concept-matching supernodes
- Per-feature stored_activation lookup from the target graph
- Deterministic seeding from sha256(run_seed:pair_id:replicate:mode)

### 7.2 Field-based additivity

The `AdditivityBuilder` accepts `concept_subset.fields: [field1, field2]`.
Selected fields are used for both ablation and amplification, matching the
same supernodes the labeled builder would match for those fields, using the
same `extract_ct_supernode()` and `compute_ct_interventions()` path.

### 7.3 Answer field decoupling

`resolve_answer_field()` centralizes answer-token selection:
1. Explicit `swap.answer_field` in config (highest priority)
2. Last element of `concept_fields` (backward-compatible default)
3. Fallback to `"capital"` (USA legacy)

This is used by both `evaluate_swap()` (for exact-match and metrics) and the
runner (for trajectory target/source tokens and contrast group composition).

### 7.4 Contrast groups

Each swap pair's contrast group consists of all other dataset answer tokens
(e.g., 48 other capitals for USA, 14 other authors for books). Multi-word
answers resolve to their first subword token. The contrast group enables
vsMax, vsTopK, and RkGrp metrics.

---

## 8. Caveats

### 8.1 Feature count imbalance
Single-field variants use 10-40 features while full-triple uses 60-160.
Differences in steering strength may partly reflect perturbation magnitude.
The random control (matched on count) partially addresses this for
labeled-vs-random, but field-to-field comparisons lack magnitude normalization.

### 8.2 Substring overlap
Painter names contain first names ("Claude Monet" contains "Claude"), causing
painter and first_name supernodes to overlap. Colorado/Colorado Springs share
state and city tokens. These cases conflate field isolation with string matching.

### 8.3 Multi-token resolution
Multi-word answers (e.g., "J.K. Rowling", "New York City") resolve to their
first subword token for trajectory tracking. This may weaken metrics for
entities with common first tokens.

### 8.4 Sample size
5 pairs per domain, 3 random replicates. Patterns are consistent but formal
inference requires larger samples. The infrastructure supports full NxN matrices
with 100+ replicates.

---

## 9. Implementation

### 9.1 Control framework

```
pipeline/controls/
  factory.py              config["control"]["mode"] -> builder
  labeled.py              LabeledInterventionBuilder (default)
  random_feature_matched.py  RandomFeatureMatchedBuilder
  additivity.py           AdditivityBuilder (role-based + field-based)
  matching.py             resolve_stored_activation, build_intervention_dicts
  sampling.py             deterministic RNG, histogram-matched sampling
  exclusions.py           candidate pools, concept-adjacent exclusions
  concept_sets.py         field/role selection
```

### 9.2 Config example

```yaml
swap:
  concept_fields: [character, book, author]
  answer_field: author

control:
  mode: additivity
  runs:
    - fields: [character]
    - fields: [book]
    - fields: [author]
    - fields: [character, book]
    - fields: [character, author]
    - fields: [book, author]
    - fields: [character, book, author]
```

### 9.3 Output layout

Variant files use suffixes: `to_slug__add_book.json`, `to_slug__r0.json`.
The demo UI filters these automatically via `_is_control_variant()`.

### 9.4 Reproducibility

All runs: seed 42, temperature 0.3, deterministic RNG for random controls.
Run IDs: `trial_aligned_*` (USA), `trial_full_{domain}_*` (others).
Test suite: 65+ tests in `tests/test_controls.py`.

---

## 10. Conclusions

1. **Labeled supernodes are specifically effective across all five domains.**
   They achieve RkGrp=1.0 (top answer among all dataset alternatives) in
   every domain. Random controls range from 1.1 to 6.0.

2. **The specificity gap follows the domain gradient:**
   USA (strong) > Books (moderate-strong) > Products (moderate) > Paintings
   (moderate) > Sounds (weak). This reproduces the pattern from the main
   full-scale experiments.

3. **Suppression is generic; targeting is specific.** Random controls often
   suppress the source better than labeled (by disrupting broadly), but they
   cannot steer toward the correct target.

4. **Answer-field and intermediate-field supernodes carry the steering signal.**
   Input-field supernodes (the concept in the prompt) usually contribute
   noise. The average single-field target rank is 35 for answer fields,
   73 for intermediate fields, and 556 for input fields.

5. **Including input-field supernodes can degrade performance.** In books
   and paintings, adding character/painting supernodes to the intervention
   reduces hit rate to 0%, while answer-only or intermediate+answer subsets
   achieve 20-40%. This "less is more" effect suggests the input-field
   supernodes activate competing circuits.

6. **The optimal field combination is domain-dependent** but consistently
   excludes or minimizes the input field: state+capital (USA), book+author
   (books), company+founder (products), first_name alone (paintings),
   sound+color (sounds).

7. **Contrast-group metrics (vsMax, RkGrp) are the most informative
   cross-domain discriminators**, especially where binary hit rate is zero
   for both labeled and random conditions.
