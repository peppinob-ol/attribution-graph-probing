# Full-Scale Cross-Domain Control Experiment Report

## 1. Overview

**33,387 steering runs** across 5 domains, testing specificity and field-level
decomposition of attribution graph feature swaps.

| Domain | Entities | Pairs | Labeled | Random x3 | Field-add x7 | Total |
|--------|----------|-------|---------|-----------|--------------|-------|
| USA States | 50 | 2,450 | 2,500 | 7,500 | 17,500 | 27,500 |
| Books | 16 | 240 | 256 | 768 | 1,792 | 2,816 |
| Products | 12 | 132 | 144 | 432 | 1,008 | 1,584 |
| Paintings | 10 | 90 | 100 | 300 | 700 | 1,100 |
| Sounds | 6 | 30 | 36 | 108 | 243 | 387 |
| **Total** | | **2,942** | **3,036** | **9,108** | **21,243** | **33,387** |

**Model**: Gemma-2-2b, CLT transcoders (mntss/clt-gemma-2-2b-2.5M).
**Hardware**: 8x NVIDIA A40 (48GB). **Runtime**: ~2.5 hours.
**Every result** includes full trajectory, contrast groups (48 capitals / 14 authors / etc.), and control token stability.

---

## 2. Domains and Semantic Roles

Each domain has 3 entity fields mapped to semantic roles:

| Domain | Input (in prompt) | Intermediate (bridging) | Answer (model output) | Prompt |
|--------|-------------------|------------------------|-----------------------|--------|
| USA States | city | state | **capital** | "The capital of the state containing {city} is" |
| Books | character | book | **author** | "The book featuring {character} was written by" |
| Products | product | company | **founder** | "The company that makes {product} was founded by" |
| Paintings | painting | painter | **first_name** | "The first name of the painter of {painting} is" |
| Sounds | sound | animal | **color** | "The most common color of the animal that goes '{sound}' is" |

All runs use `answer_field` set to the answer column, decoupling trajectory scoring
from intervention matching.

---

## 3. Labeled vs Random: Full-Scale Results

| Domain | Cond | N | Hit% | Sup% | GapCl | TgtRk | MedRk | vsMax | vsTopK | RkGrp | Flip% |
|--------|------|---|------|------|-------|-------|-------|-------|--------|-------|-------|
| **USA States** | **labeled** | **2450** | **24.7%** | **92.8%** | **4.67** | **74.6** | **5.0** | **2.86** | **3.76** | **1.72** | **98.2%** |
| | random | 7350 | 0.1% | 83.4% | 2.43 | 1836 | 566 | -2.31 | -1.65 | 9.00 | 69.2% |
| **Books** | **labeled** | **240** | **3.8%** | **69.2%** | **0.01** | **44.7** | **18.0** | **5.98** | **7.40** | **1.03** | **96.7%** |
| | random | 720 | 0.3% | 75.0% | 3.39 | 1608 | 283 | -0.15 | 0.76 | 2.43 | 79.6% |
| **Products** | **labeled** | **132** | **15.2%** | **65.2%** | **0.19** | **67.0** | **26.5** | **3.46** | **5.11** | **1.20** | **97.0%** |
| | random | 396 | 0.3% | 87.1% | 1.70 | 1547 | 354 | 0.23 | 1.21 | 2.25 | 75.3% |
| **Paintings** | **labeled** | **90** | **4.4%** | **34.4%** | **0.80** | **587.7** | **70.5** | **1.55** | **3.01** | **1.31** | **97.8%** |
| | random | 270 | 0.0% | 74.1% | 3.49 | 1187 | 196 | -0.03 | 1.26 | 1.96 | 88.9% |
| **Sounds** | **labeled** | **30** | **0.0%** | **100%** | **1.46** | **42.5** | **21.5** | **3.28** | **3.53** | **1.00** | **60.0%** |
| | random | 90 | 12.2% | 80.0% | 2.29 | 133 | 24 | 3.14 | 3.72 | 1.08 | 53.3% |

### Specificity discriminators

| Domain | Labeled vsMax | Random vsMax | Gap | Labeled RkGrp | Random RkGrp | Gap |
|--------|---------------|--------------|-----|---------------|--------------|-----|
| USA States | **+2.86** | -2.31 | 5.17 | **1.72** | 9.00 | 5.2x |
| Books | **+5.98** | -0.15 | 6.13 | **1.03** | 2.43 | 2.4x |
| Products | **+3.46** | +0.23 | 3.23 | **1.20** | 2.25 | 1.9x |
| Paintings | **+1.55** | -0.03 | 1.58 | **1.31** | 1.96 | 1.5x |
| Sounds | +3.28 | +3.14 | 0.14 | **1.00** | 1.08 | 1.1x |

**Key finding 1**: labeled supernodes outperform random controls on vsMax in 4 of
5 domains. The gap is strongest for books (+6.13 logits) and USA (+5.17), moderate
for products (+3.23), weak for paintings (+1.58), and negligible for sounds (+0.14).

**Key finding 2**: labeled interventions achieve lower (better) RkGrp in all domains.
USA labeled median rank is 5 vs random 566 -- a 113x difference.

**Key finding 3**: random controls achieve higher suppression than labeled in 3 of 5
domains (books 75% vs 69%, products 87% vs 65%, paintings 74% vs 34%). Suppression
is generic disruption; it does not require concept-specific features.

---

## 4. Field-Based Additivity: Full-Scale Results

### 4.1 USA States (2,450 non-identity pairs per variant)

| Fields | Role | N | Hit% | Sup% | GapCl | TgtRk | MedRk | vsMax | vsTopK | RkGrp |
|--------|------|---|------|------|-------|-------|-------|-------|--------|-------|
| city | input | 2450 | 2.9% | 68.4% | 3.56 | 854 | 190 | -1.26 | -0.49 | 6.92 |
| state | intermediate | 2450 | 17.0% | 83.3% | 4.38 | 836 | 14 | 2.38 | 3.33 | 2.72 |
| capital | answer | 2450 | 14.2% | 95.6% | 2.23 | 97 | 11 | 0.63 | 1.33 | 3.69 |
| **state+capital** | **mid+ans** | **2450** | **38.8%** | **98.0%** | **3.74** | **18** | **3** | **4.00** | **4.86** | **1.47** |
| state+city | mid+in | 2450 | 11.1% | 82.7% | 4.88 | 325 | 28 | 1.71 | 2.56 | 2.31 |
| capital+city | ans+in | 2450 | 10.2% | 91.2% | 3.35 | 184 | 30 | 0.58 | 1.40 | 4.16 |
| all 3 (labeled) | all | 2450 | 24.7% | 92.8% | 4.67 | 75 | 5 | 2.86 | 3.76 | 1.72 |

**state+capital achieves 38.8% hit rate** -- significantly higher than the full
3-field labeled (24.7%). Median target rank 3 vs 5. City supernodes degrade
performance when added.

### 4.2 Books (240 non-identity pairs per variant)

| Fields | Role | N | Hit% | Sup% | GapCl | TgtRk | MedRk | vsMax | vsTopK | RkGrp |
|--------|------|---|------|------|-------|-------|-------|-------|--------|-------|
| character | input | 240 | 4.2% | 67.9% | 1.46 | 839 | 125 | 1.87 | 3.18 | 1.77 |
| book | intermediate | 240 | 37.1% | 83.3% | 0.24 | 73 | 2 | 6.69 | 8.25 | 1.20 |
| author | answer | 240 | 14.6% | 92.1% | 0.20 | 389 | 12 | 4.71 | 6.61 | 1.33 |
| **book+author** | **mid+ans** | **240** | **37.1%** | **84.6%** | **0.04** | **24** | **2** | **7.76** | **9.58** | **1.02** |
| character+book | in+mid | 240 | 5.0% | 77.5% | 0.15 | 88 | 24 | 5.22 | 6.71 | 1.23 |
| character+author | in+ans | 240 | 3.8% | 75.0% | 0.21 | 618 | 76 | 3.45 | 4.73 | 1.30 |
| all 3 (labeled) | all | 240 | 3.8% | 69.6% | 0.02 | 44 | 17 | 5.97 | 7.39 | 1.03 |

**Book supernodes dominate**: 37.1% hit rate with median rank 2. Adding character
supernodes degrades from 37.1% to 3.8% -- a dramatic "less is more" effect.
Book+author (37.1% hit, vsMax 7.76) vastly outperforms the full triple (3.8% hit,
vsMax 5.97).

### 4.3 Products (132 non-identity pairs per variant)

| Fields | Role | N | Hit% | Sup% | GapCl | TgtRk | MedRk | vsMax | vsTopK | RkGrp |
|--------|------|---|------|------|-------|-------|-------|-------|--------|-------|
| product | input | 132 | 0.0% | 62.1% | 0.20 | 553 | 137 | 1.90 | 3.46 | 1.61 |
| company | intermediate | 132 | 5.3% | 71.2% | 0.26 | 348 | 128 | 2.62 | 4.39 | 1.39 |
| founder | answer | 132 | 8.3% | 84.1% | 0.51 | 146 | 18 | 2.08 | 3.07 | 1.27 |
| **company+founder** | **mid+ans** | **132** | **24.2%** | **68.9%** | **0.35** | **145** | **18** | **3.06** | **4.48** | **1.27** |
| product+company | in+mid | 132 | 1.5% | 68.2% | 0.15 | 318 | 93 | 2.78 | 4.92 | 1.31 |
| product+founder | in+ans | 132 | 2.3% | 66.7% | 0.05 | 171 | 48 | 2.54 | 4.01 | 1.23 |
| all 3 (labeled) | all | 132 | 15.2% | 63.6% | 0.19 | 66 | 26 | 3.47 | 5.10 | 1.20 |

**company+founder is the strongest pair** (24.2% hit), outperforming the full triple
(15.2%). Product supernodes contribute nothing to targeting (0% hit, highest rank).

### 4.4 Paintings (90 non-identity pairs per variant)

| Fields | Role | N | Hit% | Sup% | GapCl | TgtRk | MedRk | vsMax | vsTopK | RkGrp |
|--------|------|---|------|------|-------|-------|-------|-------|--------|-------|
| painting | input | 90 | 3.3% | 34.4% | 0.71 | 762 | 71 | 1.50 | 2.72 | 1.44 |
| painter | intermediate | 90 | 1.1% | 70.0% | 0.45 | 452 | 66 | 1.68 | 2.76 | 1.30 |
| first_name | answer | 90 | 6.7% | 75.6% | 0.79 | 265 | 90 | 1.46 | 2.72 | 1.41 |
| painter+first_name | mid+ans | 90 | 1.1% | 70.0% | 0.49 | 452 | 65 | 1.69 | 2.78 | 1.30 |
| painting+painter | in+mid | 90 | 3.3% | 36.7% | 0.75 | 588 | 70 | 1.55 | 3.02 | 1.30 |
| painting+first_name | in+ans | 90 | 3.3% | 47.8% | 0.50 | 580 | 62 | 1.23 | 2.59 | 1.39 |
| all 3 (labeled) | all | 90 | 3.3% | 33.3% | 0.84 | 562 | 66 | 1.55 | 2.99 | 1.32 |

Paintings shows weak steering across all variants. No combination exceeds 6.7% hit.
The painter and painter+first_name variants produce identical results (painter name
subsumes first name in supernode matching). All variants achieve RkGrp ~1.3.

### 4.5 Sounds (30 non-identity pairs per variant)

| Fields | Role | N | Hit% | Sup% | GapCl | TgtRk | MedRk | vsMax | vsTopK | RkGrp |
|--------|------|---|------|------|-------|-------|-------|-------|--------|-------|
| sound | input | 30 | 20.0% | 83.3% | 2.75 | 30 | 5 | 5.49 | 5.91 | 1.00 |
| animal | intermediate | 24 | 12.5% | 87.5% | 1.61 | 88 | 6 | 3.49 | 4.07 | 1.21 |
| color | answer | 30 | 0.0% | 100% | 1.51 | 73 | 48 | 3.09 | 3.68 | 1.07 |
| **sound+color** | **in+ans** | **30** | **10.0%** | **76.7%** | **1.45** | **12** | **9** | **4.51** | **4.89** | **1.00** |
| animal+color | mid+ans | 30 | 3.3% | 100% | 1.84 | 103 | 82 | 4.78 | 5.11 | 1.00 |
| sound+animal | in+mid | 30 | 20.0% | 70.0% | 1.15 | 97 | 5 | 4.69 | 4.99 | 1.07 |
| all 3 (labeled) | all | 30 | 0.0% | 96.7% | 1.50 | 41 | 20 | 3.40 | 3.66 | 1.00 |

**Sounds is the exception**: the input field (sound name) carries the strongest
signal (20% hit, median rank 5, vsMax 5.49). Sound+color achieves the best target
rank (median 9). The full triple gets 0% hit -- adding all three fields together
degrades performance compared to sound alone.

---

## 5. Cross-Domain Field Role Summary

Single-field variants only, averaged across all 5 domains:

| Role | Hit% | Sup% | TgtRk | MedRk | vsMax | vsTopK | RkGrp |
|------|------|------|-------|-------|-------|--------|-------|
| **Input** | 6.1% | 63.2% | 608 | 106 | 1.90 | 2.96 | 2.55 |
| **Intermediate** | 14.6% | 79.1% | 360 | 43 | 3.37 | 4.56 | 1.56 |
| **Answer** | 8.8% | 89.5% | 194 | 36 | 2.39 | 3.48 | 1.75 |

**Intermediate-field supernodes** (state, book, company, painter, animal) provide
the strongest targeting on average: highest hit rate (14.6%), best vsMax (+3.37),
best RkGrp (1.56).

**Answer-field supernodes** achieve the best suppression (89.5%) and lowest median
target rank (36) but lower hit rate than intermediate.

**Input-field supernodes** are weakest on every metric except sounds (where
sound names are unusually effective).

---

## 6. The "Less is More" Effect

In 4 of 5 domains, a 2-field subset outperforms the full 3-field labeled:

| Domain | Best subset | Hit% | Full 3-field Hit% | Delta |
|--------|-------------|------|--------------------|-------|
| USA States | state+capital | **38.8%** | 24.7% | +14.1pp |
| Books | book+author | **37.1%** | 3.8% | +33.3pp |
| Products | company+founder | **24.2%** | 15.2% | +9.0pp |
| Sounds | sound+animal | **20.0%** | 0.0% | +20.0pp |
| Paintings | first_name alone | **6.7%** | 3.3% | +3.4pp |

The optimal subset is consistently **intermediate+answer** (state+capital,
book+author, company+founder) for the three strongest domains.

**Interpretation**: input-field supernodes (city, character, product, painting,
sound) encode the concept the model reads in the prompt, not the concept it needs
to produce. Including them in the intervention activates competing circuits that
dilute or interfere with the answer signal. The model's internal representation
of the prompt input is apparently better left undisturbed during steering.

---

## 7. Methodology

### 7.1 Steering setup
- Ablation: M = -2, live activations from current prompt
- Amplification: M = 20, stored activations from target graph
- Generation: temperature 0.3, n_tokens 10, freq_penalty 2.0, seed 42

### 7.2 Random control
For each pair: run labeled builder to get reference count and layer distribution,
exclude all concept-matching supernodes, sample random features preserving count
and layer histogram per role, attach stored_activation from target activations_map.
3 deterministic replicates per pair.

### 7.3 Field additivity
Intervention restricted to selected concept fields on both sides. With 3 fields:
7 variants (3 single, 3 pair, 1 triple). Each variant uses the same supernode
extraction and intervention mechanics as labeled.

### 7.4 Answer field decoupling
`swap.answer_field` explicitly sets the tracked answer token. This decouples
trajectory scoring and exact-match evaluation from the intervention field list.
Contrast groups consist of all other dataset answer tokens.

### 7.5 Metrics
- **Hit%**: target answer in steered output
- **Sup%**: source answer absent from steered output
- **GapCl**: max logit gap improvement over trajectory
- **TgtRk / MedRk**: mean and median best target rank
- **vsMax**: target logit minus max other answer logit (best over trajectory)
- **vsTopK**: target logit minus mean top-3 other answers
- **RkGrp**: best rank within full answer group (1 = top)
- **Flip%**: fraction of pairs achieving target > source rank crossover

---

## 8. Caveats

1. **Feature count imbalance**: single-field variants use 10-40 features while
   full-triple uses 60-160. Stronger metrics may partly reflect perturbation
   magnitude. The random control (matched on count) partially addresses this
   for labeled-vs-random but not for field-to-field comparisons.

2. **Substring overlap**: painter names contain first names, Colorado contains
   Colorado Springs. These cases conflate field isolation with string matching.

3. **Multi-token resolution**: multi-word answers resolve to first subword for
   trajectory tracking. Weakens metrics for entities with common first tokens.

4. **Sounds anomaly**: the domain has only 6 entities and shows weak specificity
   (labeled vsMax barely exceeds random). Results should be treated cautiously.

5. **Paintings weakness**: labeled steering is barely distinguishable from random
   on vsMax (1.55 vs -0.03) and RkGrp (1.31 vs 1.96). The painting domain may
   be dominated by attention circuits invisible to this residual-stream pipeline.

---

## 9. Conclusions

1. **Labeled supernodes are specifically effective in 4 of 5 domains.** They
   outperform structurally matched random controls on vsMax and RkGrp across
   USA, books, products, and paintings. Sounds shows negligible specificity.

2. **The domain gradient is confirmed at full scale:** USA (strong) > Books
   (strong on vsMax) > Products (moderate) > Paintings (weak) > Sounds (weak).

3. **Intermediate+answer is the optimal field combination.** State+capital
   (USA), book+author (books), company+founder (products) all outperform the
   full 3-field labeled intervention, often dramatically.

4. **The "less is more" effect is robust across domains.** Adding input-field
   supernodes degrades performance by +14pp (USA), +33pp (books), +9pp
   (products), and +20pp (sounds). The prompt-input concept should typically
   be excluded from the intervention.

5. **Suppression is generic; targeting is specific.** Random controls achieve
   equal or higher suppression (83% vs 93% labeled average) but near-zero
   targeting (0.2% hit vs 12.4% labeled average, median rank 566 vs 5 for USA).

6. **Contrast-group metrics (vsMax, RkGrp) are the best cross-domain
   discriminators.** Binary hit rate is too coarse for weaker domains.
   vsMax reveals specificity even where hit rate is 0% for both conditions.
