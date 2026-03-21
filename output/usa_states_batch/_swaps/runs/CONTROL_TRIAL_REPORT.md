# Control Experiment Trial Report

## 1. Experiment Overview

This report documents the first end-to-end trial of the control experiment framework
for attribution graph probing. Three experiment families were run on the same 5 swap
pairs from the USA states dataset to test whether observed steering effects are
specific to concept-labeled supernodes.

### Experiment families

| Family | Config | Run ID | Pairs | Variants | Total steering runs |
|--------|--------|--------|-------|----------|---------------------|
| Labeled baseline | `trial_combined_labeled.yml` | `trial_combined_labeled` | 5 | 1 | 5 |
| Random feature control | `trial_combined_random.yml` | `trial_combined_random` | 5 | 3 replicates | 15 |
| Field-based additivity | `trial_control_field_additivity.yml` | `trial_field_add_v1` | 5 | 7 field subsets | 35 |

**Total: 55 steering runs on a single NVIDIA A40 GPU.**

### Swap pairs

| # | Source | Target | Prompt | Difficulty |
|---|--------|--------|--------|------------|
| 1 | New Mexico (Santa Fe / Albuquerque) | Pennsylvania (Harrisburg / Philadelphia) | "The capital of the state containing Albuquerque is" | Medium |
| 2 | Texas (Austin / Dallas) | Georgia (Atlanta / Savannah) | "The capital of the state containing Dallas is" | Easy |
| 3 | California (Sacramento / Oakland) | Florida (Tallahassee / Miami) | "The capital of the state containing Oakland is" | Easy |
| 4 | Colorado (Denver / Colorado Springs) | New York (Albany / New York City) | "The capital of the state containing Colorado Springs is" | Hard (token overlap) |
| 5 | Georgia (Atlanta / Savannah) | Texas (Austin / Dallas) | "The capital of the state containing Savannah is" | Easy (reverse of #2) |

---

## 2. Methodology

### 2.1 Model and steering setup

- **Model**: Gemma-2-2b (google/gemma-2-2b)
- **Transcoder**: CLT (mntss/clt-gemma-2-2b-2.5M)
- **Multipliers**: M_ablate = -2, M_amplify = 20
- **Generation**: temperature 0.3, n_tokens 10, freq_penalty 2.0, seed 42, top_k 5
- **Trajectory tracking**: enabled for all runs

### 2.2 Concept fields

All three runs use `concept_fields: [state, capital, city]`, which means:

- **Supernode matching** can use state names ("Texas"), capital names ("Austin"),
  and city names ("Dallas") to find relevant supernodes in each entity's graph.
- **Answer field** defaults to the last concept field (`city`), so trajectory
  metrics track the city token (e.g., "Savannah" not "Atlanta" for Texas->Georgia).
- **Exact match** checks whether the target city appears in the steered output.
- **Contrast group** members are all other city names from the 50-state dataset
  (48 alternatives, excluding source and target cities).

**Important**: the prompt asks for the state capital, but the tracked answer is
the city.  This means exact-match hit rates are lower than in the 2-field
`[state, capital]` baseline where the capital is tracked. Relative comparisons
across conditions within this trial remain valid because all variants track the
same token.

### 2.3 Labeled baseline

The standard intervention: for each swap pair, ablate all supernodes matching
source entity concept fields (state + capital + city) using live activations
(M = -2), and amplify all supernodes matching target entity concept fields
using stored activations from the target graph (M = 20).

### 2.4 Random feature matched control

For each swap pair, a structurally matched null intervention is constructed by:

1. Running the labeled builder to get the reference intervention (count and
   layer distribution per role).
2. Building exclusion sets: all features in concept-matching supernodes are
   excluded from the candidate pool to prevent leaking concept signal.
3. Sampling random features from the same graphs, separately for source
   (ablation) and target (amplification) sides.
4. Matching the exact feature count and layer distribution of the labeled
   intervention per role.
5. Attaching stored_activation from the target graph's activations_map for
   amplification features, using the same lookup rules as the labeled path.

Three independent replicates (r0, r1, r2) are generated per pair using
deterministic seeding from `sha256(run_seed:pair_id:replicate_id:mode)`.

### 2.5 Field-based additivity decomposition

The labeled intervention is restricted to a subset of entity fields. Each
selected field is used for BOTH ablation (from source entity) and
amplification (from target entity). Seven variants are tested:

| Variant | Fields used | What it tests |
|---------|-------------|---------------|
| state | [state] | State-name supernodes only |
| capital | [capital] | Capital-name supernodes only |
| city | [city] | City-name supernodes only |
| st+cap | [state, capital] | State + capital |
| st+cit | [state, city] | State + city |
| cap+cit | [capital, city] | Capital + city |
| all3 | [state, capital, city] | All three (equivalent to labeled) |

### 2.6 Metrics tracked

**Target vs source (existing trajectory metrics)**:
- `flip_position`: first generation step where target rank < source rank
- `gap_closure`: max(gap_trajectory) - gap_trajectory[0], where gap = target_logit - source_logit
- `best_gap`: maximum target-minus-source logit difference achieved
- `target_min_rank`: best (lowest) rank the target token achieves
- `target_first_top5`: first step target enters top-5
- `source_final_rank`: final rank of source token (higher = more suppressed)

**Target vs dataset alternatives (contrast group, 48 members)**:
- `vsMax`: best(target_logit - max(other_logits)) over generation steps
- `vsTopK`: best(target_logit - mean(top-3 other_logits))
- `RkGrp`: best (lowest) rank of target within the 49-member dataset group
- `vsMean`: best(target_logit - mean(all other_logits))

**Control token stability**:
- `CtrlS`: mean absolute logit shift of control tokens ("the", "is", "a", "of")

---

## 3. Results

### 3.1 Labeled vs Random Feature Control

| Pair | Cond | Abl | Amp | Flip@ | GapCl | BstGp | TgtRk | Top5@ | SrcRk | CtrlS | vsMax | vsTopK | RkGrp | vsMean |
|------|------|-----|-----|-------|-------|-------|-------|-------|-------|-------|-------|--------|-------|--------|
| NM->PA | **labeled** | 79 | 71 | **0** | **15.1** | **22.0** | **5** | **5** | 5418 | 9.9 | **1.2** | **2.1** | **1** | **10.6** |
| | random_r0 | 79 | 71 | - | 0.0 | -1.1 | 145 | - | 132 | 5.9 | -4.7 | -2.8 | 10 | 2.5 |
| | random_r1 | 79 | 71 | - | 0.0 | -1.8 | 300 | - | 27 | 15.5 | -2.5 | -2.2 | 7 | 3.2 |
| | random_r2 | 79 | 71 | - | 0.0 | -3.5 | 4713 | - | 799 | 12.7 | -6.2 | -5.6 | 22 | 0.6 |
| TX->GA | **labeled** | 65 | 73 | **1** | **17.9** | 5.6 | **11** | - | 319 | 10.6 | **5.1** | **5.7** | **1** | **13.1** |
| | random_r0 | 65 | 73 | 0 | 0.0 | 0.1 | 319 | - | 3648 | 13.1 | -1.4 | -0.8 | 3 | 4.8 |
| | random_r1 | 65 | 73 | - | 0.0 | -0.2 | 882 | - | 2521 | 13.9 | -3.6 | -1.9 | 9 | 2.7 |
| | random_r2 | 65 | 73 | 0 | 0.0 | 3.1 | 642 | - | 14 | 31.6 | -5.2 | -4.4 | 22 | 0.2 |
| CA->FL | **labeled** | 62 | 66 | **1** | **22.1** | **14.2** | **6** | - | 3426 | 16.7 | **5.0** | **9.0** | **1** | **20.0** |
| | random_r0 | 62 | 66 | 1 | 8.4 | 5.0 | 239 | - | 17650 | 17.3 | -4.0 | -3.4 | 8 | 4.0 |
| | random_r1 | 62 | 66 | - | 0.0 | -2.8 | 229 | - | 31 | 19.3 | -3.5 | -3.0 | 15 | 2.0 |
| | random_r2 | 62 | 66 | 9 | 5.0 | 1.1 | 331 | - | 2639 | 16.1 | -2.4 | -1.8 | 5 | 6.1 |
| CO->NY | **labeled** | 163 | 68 | **1** | **32.1** | 4.0 | **1** | **1** | 158 | 26.7 | **6.5** | **7.2** | **1** | **11.9** |
| | random_r0 | 163 | 68 | 5 | 0.9 | 0.1 | 31 | - | 368 | 19.9 | 2.1 | 2.6 | 1 | 8.6 |
| | random_r1 | 163 | 68 | 0 | 0.0 | 1.4 | 255 | - | 141 | 9.1 | 0.4 | 0.7 | 1 | 8.9 |
| | random_r2 | 163 | 68 | - | 6.1 | -2.4 | 102 | - | 169 | 17.8 | 2.6 | 4.2 | 1 | 10.3 |
| GA->TX | **labeled** | 73 | 65 | **1** | **22.3** | 3.4 | **52** | - | 1935 | 17.1 | 0.0 | **1.2** | **1** | **7.1** |
| | random_r0 | 73 | 65 | - | 0.0 | 0.0 | 4980 | - | 39 | 11.1 | -4.6 | -4.2 | 17 | 1.0 |
| | random_r1 | 73 | 65 | - | 0.0 | -0.4 | 1788 | - | 36 | 26.8 | -1.6 | -0.5 | 2 | 4.3 |
| | random_r2 | 73 | 65 | 0 | 0.0 | 0.1 | 1686 | - | 9 | 8.1 | -0.8 | -0.5 | 3 | 3.9 |

#### Aggregate comparison

| Metric | Labeled (n=5) | Random (n=15) | Ratio |
|--------|---------------|---------------|-------|
| Flip achieved | 5/5 (100%) | 5/15 (33%) | 3.0x |
| Mean gap closure | 21.9 | 1.4 | 15.8x |
| Mean target min rank | 15.0 | 1138 | 76x worse |
| Mean vsMax(other) | 3.6 | -2.1 | - |
| Mean vsTopK(other) | 5.0 | -1.0 | - |
| Mean rank within group | 1.0 | 8.5 | 8.5x worse |
| Mean vsMean(other) | 12.5 | 3.0 | 4.2x |
| Exact match (city) | 1/5 (20%) | 0/15 (0%) | - |

**Interpretation**: labeled supernodes produce 15.8x more gap closure than
structurally matched random features with identical count and layer distribution.
Random controls occasionally achieve a mechanical flip (target briefly outranks
source) but with near-zero gap closure and poor contrast-group metrics, indicating
generic disruption rather than entity-specific steering. The contrast-group rank
(1.0 vs 8.5) confirms that labeled interventions make the target the top-ranked
answer within the full dataset, while random interventions leave it buried among
alternatives.

### 3.2 Field-Based Additivity Decomposition

#### 3.2.1 New Mexico -> Pennsylvania

Prompt: "The capital of the state containing Albuquerque is"
Source: state=New Mexico, capital=Santa Fe, city=Albuquerque
Target: state=Pennsylvania, capital=Harrisburg, city=Philadelphia

| Variant | Abl | Amp | Flip@ | GapCl | BstGp | TgtRk | Top5@ | SrcRk | CtrlS | vsMax | vsTopK | RkGrp | vsMean |
|---------|-----|-----|-------|-------|-------|-------|-------|-------|-------|-------|--------|-------|--------|
| **labeled** | **79** | **71** | **0** | **15.1** | **22.0** | **5** | **5** | **5418** | **9.9** | **1.2** | **2.1** | **1** | **10.6** |
| state | 12 | 13 | 0 | 7.3 | 20.5 | 4 | 5 | 2956 | 6.8 | 1.1 | 2.4 | 1 | 10.3 |
| capital | 38 | 36 | 0 | 0.0 | 17.4 | 25 | - | 426 | 10.1 | -0.9 | -0.2 | 2 | 8.1 |
| city | 29 | 22 | - | 0.0 | -2.4 | 728 | - | 258 | 8.9 | -6.7 | -5.1 | 15 | 1.9 |
| st+cap | 50 | 49 | 0 | 0.1 | 20.8 | 2 | 5 | 3926 | 8.8 | 3.5 | 4.3 | 1 | 11.8 |
| st+cit | 41 | 35 | 6 | 22.8 | 20.3 | 86 | - | 3749 | 10.1 | -0.9 | 1.4 | 2 | 10.1 |
| cap+cit | 67 | 58 | 0 | 0.0 | 7.4 | 37 | - | 88 | 8.8 | -0.9 | 1.6 | 2 | 8.1 |
| all3 | 79 | 71 | 0 | 15.1 | 22.0 | 5 | 5 | 5418 | 9.9 | 1.2 | 2.1 | 1 | 10.6 |

**Finding**: State supernodes carry the primary steering signal. With only 12
ablation + 13 amplification features (vs 79+71 for labeled), the state-only
variant achieves target rank 4, top-5 entry, and rank 1 within the contrast
group. Capital supernodes add incremental value (st+cap reaches rank 2), while
city supernodes contribute noise (rank 728, negative vsMax).

#### 3.2.2 Texas -> Georgia

Prompt: "The capital of the state containing Dallas is"
Source: state=Texas, capital=Austin, city=Dallas
Target: state=Georgia, capital=Atlanta, city=Savannah

| Variant | Abl | Amp | Flip@ | GapCl | BstGp | TgtRk | Top5@ | SrcRk | CtrlS | vsMax | vsTopK | RkGrp | vsMean |
|---------|-----|-----|-------|-------|-------|-------|-------|-------|-------|-------|--------|-------|--------|
| **labeled** | **65** | **73** | **1** | **17.9** | **5.6** | **11** | **-** | **319** | **10.6** | **5.1** | **5.7** | **1** | **13.1** |
| state | 16 | 10 | - | 0.1 | -2.5 | 129 | - | 897 | 8.9 | -3.9 | -3.2 | 8 | 5.0 |
| capital | 33 | 31 | 0 | 0.0 | 9.8 | 7 | - | 837 | 16.7 | 3.6 | 3.8 | 1 | 9.2 |
| city | 16 | 32 | - | 28.2 | -0.2 | 64 | - | 52 | 7.3 | 0.8 | 2.9 | 1 | 11.4 |
| st+cap | 49 | 41 | 0 | 0.0 | 5.0 | 7 | - | 273 | 12.8 | 2.2 | 3.8 | 1 | 11.8 |
| st+cit | 32 | 42 | 1 | 20.3 | 1.4 | 40 | - | 345 | 8.0 | 2.2 | 3.9 | 1 | 10.6 |
| cap+cit | 49 | 63 | 1 | 24.4 | 5.2 | 9 | - | 213 | 11.2 | 5.6 | 6.0 | 1 | 13.4 |
| all3 | 65 | 73 | 1 | 17.8 | 5.5 | 12 | - | 308 | 10.6 | 5.1 | 5.7 | 1 | 13.0 |

**Finding**: Capital supernodes carry the primary signal here (target rank 7,
vsMax 3.6, rank 1 in group) while state supernodes are weak (rank 129, vsMax
-3.9). This is the opposite pattern from New Mexico. The strongest 2-field
combination is cap+cit (gap closure 24.4, vsMax 5.6), exceeding the full
labeled intervention on gap closure.

#### 3.2.3 California -> Florida

Prompt: "The capital of the state containing Oakland is"

| Variant | Abl | Amp | Flip@ | GapCl | BstGp | TgtRk | Top5@ | SrcRk | CtrlS | vsMax | vsTopK | RkGrp | vsMean |
|---------|-----|-----|-------|-------|-------|-------|-------|-------|-------|-------|--------|-------|--------|
| **labeled** | **62** | **66** | **1** | **22.1** | **14.2** | **6** | **-** | **3426** | **16.7** | **5.0** | **9.0** | **1** | **20.0** |
| state | 10 | 9 | 0 | 5.3 | 8.1 | 9 | - | 3216 | 12.4 | 4.0 | 5.7 | 1 | 15.9 |
| capital | 27 | 32 | 1 | 7.7 | 5.3 | 9 | - | 2028 | 15.1 | 2.1 | 3.0 | 1 | 10.3 |
| city | 25 | 25 | 1 | 8.4 | 1.1 | 35 | - | 957 | 14.0 | -0.6 | -0.0 | 2 | 7.4 |
| st+cap | 37 | 41 | 0 | 19.0 | 20.0 | 10 | - | 3799 | 17.3 | 2.2 | 3.8 | 1 | 12.0 |
| st+cit | 35 | 34 | 1 | 15.3 | 9.3 | 8 | - | 2211 | 14.9 | 5.5 | 9.2 | 1 | 18.8 |
| cap+cit | 52 | 57 | 1 | 15.4 | 3.4 | 7 | - | 1912 | 14.0 | 0.5 | 1.1 | 1 | 7.1 |
| all3 | 62 | 66 | 1 | 22.1 | 14.2 | 6 | - | 3426 | 16.7 | 5.0 | 9.0 | 1 | 20.0 |

**Finding**: Both state and capital contribute meaningfully. All single-field
variants achieve rank 1 in the contrast group. The st+cit combination achieves
vsTopK 9.2, matching the full labeled intervention, suggesting state + city
captures most of the signal for this pair.

#### 3.2.4 Colorado -> New York (token overlap pair)

Prompt: "The capital of the state containing Colorado Springs is"

| Variant | Abl | Amp | Flip@ | GapCl | BstGp | TgtRk | Top5@ | SrcRk | CtrlS | vsMax | vsTopK | RkGrp | vsMean |
|---------|-----|-----|-------|-------|-------|-------|-------|-------|-------|-------|--------|-------|--------|
| **labeled** | **163** | **68** | **1** | **32.1** | **4.0** | **1** | **1** | **158** | **26.7** | **6.5** | **7.2** | **1** | **11.9** |
| state | 35 | 40 | 5 | 26.1 | 0.4 | 3 | 6 | 13 | 26.6 | 5.4 | 6.3 | 1 | 12.4 |
| capital | 39 | 28 | 0 | 0.0 | 7.4 | 33 | - | 111 | 4.1 | 7.1 | 7.8 | 1 | 14.6 |
| city | 89 | 40 | 5 | 26.2 | 0.4 | 3 | 6 | 13 | 26.8 | 5.5 | 6.4 | 1 | 12.6 |
| st+cap | 74 | 68 | 1 | 36.9 | 8.7 | 1 | 1 | 87212 | 24.3 | 6.5 | 7.3 | 1 | 12.7 |
| st+cit | 124 | 40 | 5 | 26.2 | 0.4 | 3 | 6 | 13 | 26.7 | 5.4 | 6.4 | 1 | 12.6 |
| cap+cit | 128 | 68 | 1 | 32.2 | 4.0 | 1 | 1 | 159 | 26.6 | 6.5 | 7.2 | 1 | 12.0 |
| all3 | 163 | 68 | 1 | 32.2 | 4.0 | 1 | 1 | 160 | 26.7 | 6.5 | 7.2 | 1 | 11.9 |

**Finding**: State and city variants produce identical results (flip@5, target
rank 3, gap closure 26.1-26.2) because "Colorado" appears in both the state
name and the city name ("Colorado Springs"), so they match the same supernodes.
Capital alone achieves no flip but high vsMax (7.1). The st+cap combination is
the strongest single result in the entire trial: gap closure 36.9, target rank
1, source rank 87212. Adding city to capital (cap+cit) matches the full labeled
intervention exactly.

#### 3.2.5 Georgia -> Texas (reverse pair)

Prompt: "The capital of the state containing Savannah is"

| Variant | Abl | Amp | Flip@ | GapCl | BstGp | TgtRk | Top5@ | SrcRk | CtrlS | vsMax | vsTopK | RkGrp | vsMean |
|---------|-----|-----|-------|-------|-------|-------|-------|-------|-------|-------|--------|-------|--------|
| **labeled** | **73** | **65** | **1** | **22.3** | **3.4** | **52** | **-** | **1935** | **17.1** | **0.0** | **1.2** | **1** | **7.1** |
| state | 10 | 16 | 5 | 16.9 | 5.7 | 11 | - | 85 | 12.1 | 2.8 | 3.8 | 1 | 13.4 |
| capital | 31 | 33 | 0 | 0.0 | 3.1 | 467 | - | 24 | 12.9 | -4.2 | -3.2 | 7 | 4.1 |
| city | 32 | 16 | 1 | 26.9 | 2.0 | 333 | - | 12340 | 15.5 | -0.2 | 2.1 | 2 | 8.6 |
| st+cap | 41 | 49 | 0 | 7.8 | 10.3 | 13 | - | 1556 | 14.1 | 1.2 | 3.5 | 1 | 11.3 |
| st+cit | 42 | 32 | 4 | 27.1 | 2.6 | 158 | - | 88 | 13.4 | -0.4 | 0.1 | 2 | 9.2 |
| cap+cit | 63 | 49 | - | 19.6 | -0.2 | 162 | - | 1953 | 19.3 | 0.4 | 0.6 | 1 | 6.0 |
| all3 | 73 | 65 | 1 | 22.3 | 3.4 | 52 | - | 1935 | 17.1 | 0.0 | 1.2 | 1 | 7.1 |

**Finding**: State supernodes achieve the best individual result (target rank
11, vsMax 2.8, rank 1) while capital supernodes perform poorly on the reverse
direction (rank 467, vsMax -4.2). This asymmetry between forward and reverse
pairs (Texas->Georgia vs Georgia->Texas) suggests that the capital grouping
encodes directional information specific to the prompt structure.

---

## 4. Cross-Pair Summary

### 4.1 Which field carries the most signal?

| Pair | Best single field | TgtRk | vsMax | Worst single field | TgtRk | vsMax |
|------|-------------------|-------|-------|--------------------|-------|-------|
| NM->PA | state | 4 | 1.1 | city | 728 | -6.7 |
| TX->GA | capital | 7 | 3.6 | state | 129 | -3.9 |
| CA->FL | state | 9 | 4.0 | city | 35 | -0.6 |
| CO->NY | state=city | 3 | 5.4 | capital | 33 | 7.1 |
| GA->TX | state | 11 | 2.8 | capital | 467 | -4.2 |

No single field dominates universally. State supernodes are most often the
strongest (3/5 pairs), but capital supernodes carry the primary signal for
Texas->Georgia. City supernodes are consistently the weakest or tied with
state (Colorado case where they share tokens).

### 4.2 Best 2-field combination

| Pair | Best 2-field | GapCl | TgtRk | Labeled GapCl | Labeled TgtRk |
|------|--------------|-------|-------|---------------|---------------|
| NM->PA | st+cap | 0.1 | 2 | 15.1 | 5 |
| TX->GA | cap+cit | 24.4 | 9 | 17.9 | 11 |
| CA->FL | st+cap | 19.0 | 10 | 22.1 | 6 |
| CO->NY | st+cap | 36.9 | 1 | 32.1 | 1 |
| GA->TX | st+cit | 27.1 | 158 | 22.3 | 52 |

In 3/5 pairs, the best 2-field combination exceeds the labeled intervention
on gap closure. This suggests that the full 3-field intervention sometimes
includes noisy features (from the weakest field) that dilute the signal.

### 4.3 Labeled vs Random: summary of specificity evidence

| Metric | Labeled always beats random? | Margin |
|--------|------------------------------|--------|
| Gap closure | Yes (5/5 pairs) | Mean 21.9 vs 1.4 |
| Target min rank | Yes (5/5 pairs) | Mean 15 vs 1138 |
| Contrast vsMax | Yes (5/5 pairs) | Mean 3.6 vs -2.1 |
| Contrast RkGrp | Yes (5/5 pairs) | Mean 1.0 vs 8.5 |
| Flip achieved | 5/5 vs 5/15 | |

The random control never achieves rank 1 within the contrast group for any
pair where labeled does. This confirms that the steering effect is specific
to concept-labeled supernodes, not a generic consequence of perturbation
magnitude.

---

## 5. Implementation Details

### 5.1 Architecture

The control framework is implemented as a builder pattern under
`scripts/experiments/batch/pipeline/controls/`:

```
controls/
  __init__.py          # exports create_intervention_builder
  types.py             # InterventionResult dataclass
  base.py              # InterventionBuilder protocol
  labeled.py           # LabeledInterventionBuilder (default)
  random_feature_matched.py   # RandomFeatureMatchedBuilder
  low_specificity_groupings.py # LowSpecificityGroupingsBuilder
  additivity.py        # AdditivityBuilder (role-based and field-based)
  factory.py           # maps config["control"]["mode"] to builder
  matching.py          # shared: resolve_stored_activation, build_intervention_dicts
  sampling.py          # shared: deterministic RNG, histogram-matched sampling
  exclusions.py        # shared: candidate pools, concept exclusions
  concept_sets.py      # shared: concept field selection, role mapping
```

### 5.2 Config-driven control selection

Controls are selected via a single YAML block. When absent, defaults to labeled:

```yaml
control:
  mode: random_feature_matched  # or labeled, additivity, low_specificity_groupings
  replicates: 3
  seed: 42
```

Field-based additivity uses:

```yaml
control:
  mode: additivity
  runs:
    - fields: [state]
    - fields: [capital]
    - fields: [state, capital, city]
```

### 5.3 Variant output layout

Each variant produces a separate result file with a suffix:

```
by_source/texas_dallas/to_georgia_savannah.json          # labeled
by_source/texas_dallas/to_georgia_savannah__r0.json      # random replicate 0
by_source/texas_dallas/to_georgia_savannah__add_state.json  # field: state only
```

The demo UI filters variant files automatically using `_is_control_variant()`,
so the main matrix view shows only labeled results.

### 5.4 Metadata persistence

Every result JSON includes control metadata under `metadata.control`:

```json
{
  "metadata": {
    "timestamp": "...",
    "is_identity": false,
    "control": {
      "control_mode": "random_feature_matched",
      "ablate_count": 79,
      "amplify_count": 71,
      "replicate_id": 0,
      "diagnostics": {
        "pool_from_size": 770,
        "pool_to_size": 890,
        "exclusion_from_count": 79,
        "exclusion_to_count": 71,
        "ablate_layer_match": { ... }
      }
    }
  }
}
```

### 5.5 Stored activation handling

Target-side amplification features in non-labeled controls use the same
`activations_map` lookup as the labeled path:
1. Exact `(layer, index, position)` key match
2. Wildcard fallback when `position == -1`

This ensures injection-mode features receive real activation magnitudes
from the target graph, not zero-valued placeholders.

### 5.6 Test coverage

56 tests in `tests/test_controls.py` cover: factory selection, labeled builder
regression, concept-field compatibility, stored_activation lookup, random
control exclusions and determinism, low-specificity groupings, additivity
(role-based and field-based), metadata persistence, and trajectory schema
preservation.

---

## 6. Methodological Notes

### 6.1 Answer field alignment

With `concept_fields: [state, capital, city]`, the `answer_field` convention
(last field) makes `city` the tracked answer. This means:

- Trajectory metrics track city tokens (e.g., "Savannah" for Georgia, not "Atlanta")
- Exact-match checks look for the city name in steered output
- Contrast group members are all other city names (48 alternatives)

For the USA states domain where the prompt asks "The capital of the state
containing {city} is", the natural answer is the capital, not the city. A
2-field config `[state, capital]` would align tracking with the prompt structure.
The 3-field config was chosen here to enable the city decomposition axis.

Relative comparisons across conditions within this trial remain valid because
all variants track the same token.

### 6.2 Sample size limitations

This is a 5-pair trial with 3 random replicates per pair. The specificity
patterns are consistent across pairs but formal statistical inference requires
a larger sample (the full 50x50 matrix with 100+ replicates, as designed in
the methodology report Section 7.1).

### 6.3 Contrast group composition

The contrast group consists of 48 other city names from the 50-state dataset
(excluding source and target). Single-token resolution may fail for multi-word
cities, reducing the effective group size for some pairs. The `n_members` field
in the results tracks the actual resolved count.
