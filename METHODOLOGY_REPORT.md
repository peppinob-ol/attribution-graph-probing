# Methodology Report: Automated Circuit Interpretation via Probe Prompting

**Date**: 2026-03-25
**Scope**: Full pipeline analysis -- from probe generation through feature swapping, specificity controls, and field-level decomposition
**Scale**: 33,387 steering runs across 5 domains, 3 experimental conditions

**Epistemic framing**: Claims, evidence, and reasoning are separated throughout. Three levels of interpretive claim are distinguished: (i) operationally useful labels, (ii) downstream causal effects, and (iii) full mechanistic explanation.

---

## 1. Problem Statement and Research Context

### 1.1 The Interpretation Bottleneck

Attribution graphs (Ameisen et al., 2025) represent causal pathways from input embeddings through cross-layer transcoder (CLT) features to output logits. These graphs typically contain hundreds to thousands of feature nodes. Manual interpretation -- inspecting activation patterns across corpus examples to assign semantic labels -- is reported to require approximately 2 hours per prompt by an experienced analyst.

**Claim**: Probe prompting can automate first-pass analysis, reducing interpretation time to 10--20 minutes of semi-automated processing per circuit.

**Evidence**: The pipeline generates interpretable supernode groupings across 5+ prompt families (geographic capitals, book/author, product/founder, painting/painter, sound/color). Processing time is 2--5 minutes for graphs with 50--200 features.

### 1.2 Three Levels of Interpretive Claim

Following Geiger et al. (2025), this report distinguishes three levels:

1. **Operationally useful labels**: Behaviorally grounded supernode names useful for navigating circuits. Weakest claim, most defensible.
2. **Downstream causal effects**: Labeled supernodes, when manipulated, produce entity-specific changes in model output. Stronger claim, now tested via specificity controls.
3. **Full mechanistic explanation**: Labels correctly describe the computational role of features. Strongest claim, NOT made by this work.

### 1.3 What This System Does (and Does Not Do)

The system operates *downstream* of circuit tracing. It does not propose a new attribution method, model attention (QK) circuits, handle multi-token concepts natively, or claim ground-truth mechanistic descriptions.

It does:

- Measure feature behavior under controlled semantic variation
- Classify features into functional roles using transparent rules
- Group features into operationally labeled supernodes
- Test supernode causal relevance via feature swapping with entity-specific outcome tracking
- Decompose steering effects by semantic field role (input, intermediate, answer)
- Establish specificity via structurally matched random-feature controls

---

## 2. Pipeline Specification

### 2.1 Attribution Graph Generation

**Input**: A seed prompt and target logit (e.g., "The capital of the state containing Dallas is" -> " Austin").

**Process**: Neuronpedia API generates an attribution graph using a local replacement model over CLT features (Gemma-2-2B, `clt-hp` source set). The replacement model freezes attention patterns and layer norms, linearizing the residual stream through CLT features.

**Default Parameters**:


| Parameter         | Default | Role                                 |
| ----------------- | ------- | ------------------------------------ |
| `nodeThreshold`   | 0.8     | Minimum node influence for inclusion |
| `edgeThreshold`   | 0.85    | Minimum edge weight for inclusion    |
| `maxFeatureNodes` | 5000    | Upper bound on graph size            |


**Output**: Graph JSON with nodes (features, embeddings, logits), edges (attribution weights), and metadata.

**Static metrics per node**: `node_influence` (marginal influence), `cumulative_influence` (pruning coverage), `frac_external_raw` (1 - self-loop weight / total incoming weight).

**Feature selection**: A cumulative influence threshold (tau, typically 0.95 for batch experiments) selects the feature universe for probing.

**Assumption**: The replacement model (which freezes attention during graph computation) faithfully represents the computations of interest. The downstream swap interventions use `freeze_attention: false`, so the model's attention adapts freely. Positive results under these conditions are stronger evidence than under frozen attention, where direct feature-feature effects are partly forced by construction (Ameisen et al., 2025, "Nuances of Steering with Cross-Layer Features").

### 2.2 Probe Prompt Generation and Activation Measurement

**Goal**: Produce a cross-prompt activation signature (CPAS) for each feature.

**Probe generation**: An instructed LLM (Claude-3.5-Sonnet, temperature 0.7) generates probe prompts designed to elicit activations that disambiguate each feature's circuit role. Probes reuse tokens and syntactic structure of the seed prompt. In batch mode, probes are loaded from shared template files with systematic concept coverage (entity, attribute, relationship categories) and are manually reviewed.

**Activation measurement**: For each (feature, probe) pair, activations are measured via Neuronpedia API or local GPU inference. The subset of aggregated metrics driving classification:


| Metric                  | Definition                                                               | Used in rule                   |
| ----------------------- | ------------------------------------------------------------------------ | ------------------------------ |
| `peak_consistency_main` | Fraction of probes where the most frequent peak token is the actual peak | Dictionary (>= 0.80)           |
| `n_distinct_peaks`      | Count of distinct tokens serving as peak across probes                   | Dictionary (<= 1)              |
| `conf_F` / `share_F`    | Fraction of active probes where peak is on a functional token            | Say-X (>= 0.90)                |
| `func_vs_sem_pct`       | 100 * (max_functional_act - max_semantic_act) / max_overall              | Say-X (>= 50), Semantic (< 50) |
| `sparsity_median`       | Median sparsity ratio across active probes                               | Relationship (< 0.45)          |
| `conf_S`                | 1 - share_F (semantic confidence)                                        | Semantic Concept (>= 0.50)     |
| `layer`                 | Feature's layer in the CLT                                               | Say-X (>= 7), Semantic (<=3)   |


### 2.3 Feature Classification and Supernode Construction

**Token preprocessing**: Each token is labeled as *functional* (syntactic: "is", "the", "of", etc.) or *semantic* (content-bearing). When a feature peaks on a functional token, a directional search within a 7-token window identifies the nearest semantic target token.

**Decision tree**:

```
1. IF peak_consistency >= 0.80 AND n_distinct_peaks <= 1
   -> Semantic (Dictionary): stable token detector

2. ELIF func_vs_sem_pct >= 50 AND conf_F >= 0.90 AND layer >= 7
   -> Say "X": output-promotion feature

3. ELIF sparsity_median < 0.45
   -> Relationship: sentence-spanning diffuse activations

4. ELIF layer <= 3 OR conf_S >= 0.50 OR func_vs_sem_pct < 50
   -> Semantic (Concept): category detector

5. ELSE
   -> Review (flagged for manual inspection)
```

**Conflict resolution**: Strict priority ordering -- the first matching rule wins. Simple and auditable, but the ordering encodes implicit priorities.

**Supernode formation**: Features sharing the same classification and name are grouped into supernodes. Each feature belongs to exactly one supernode.

### 2.4 Causal Testing via Feature Swapping

**Goal**: Test whether labeled supernodes have entity-specific causal influence on model output.

**Intervention mechanism**: Additive delta injection via CLT decoder vectors. For each intervened feature, `new_value = M * original_activation` is computed, the feature's CLT decoder vectors are scaled by `new_value` and added to the residual stream at all downstream layers. Attention patterns are **not frozen** (`freeze_attention: false`), so the model can route around interventions.

**Multipliers**: M_ablate = -2 (suppress source features), M_amplify = 20 (boost target features). These follow Anthropic's empirically calibrated practice, reflecting three structural reasons for overcompensation: incomplete CLT dictionaries, inexhaustive supernode membership, and incomplete cross-layer effect capture (Ameisen et al., 2025, "Unexplained Variance and Choice of Steering Factors").

**Protocol**: For a swap from entity A to entity B:

1. Identify supernodes associated with entity A's concepts
2. Identify supernodes associated with entity B's concepts
3. Multiply each A-feature activation by M_ablate (-2)
4. Multiply each B-feature activation by M_amplify (20)
5. Run the model with these additive delta interventions and record output

**Generation**: Temperature 0.3, n_tokens 10, frequency_penalty 2.0, seed 42.

---

## 3. Experimental Design

### 3.1 Datasets


| Dataset                 | Seed Prompt Template                                         | Concept Fields       | N Seeds | N Swap Pairs |
| ----------------------- | ------------------------------------------------------------ | -------------------- | ------- | ------------ |
| USA States              | "The capital of the state containing {city} is"              | state, capital       | 50      | 2,450        |
| Book Characters/Authors | "The book featuring {character} was written by"              | book, author         | 16      | 240          |
| Products/Founders       | "The company that makes {product} was founded by"            | company, founder     | 12      | 132          |
| Paintings/Painters      | "The first name of the painter of {painting} is"             | painting, first_name | 10      | 90           |
| Sounds/Colors           | "The most common color of the animal that goes '{sound}' is" | animal, color        | 6       | 30           |


**Model**: Gemma-2-2B-it with `clt-hp` (cross-layer transcoder, high-performance) containing ~2.5M features across 26 layers.

### 3.2 Experimental Conditions

Each swap pair is tested under three conditions:

**Labeled baseline**: All concept fields used for intervention. Ablate source supernodes (live activations, M=-2), amplify target supernodes (stored activations from target graph, M=20).

**Random feature-matched control**: Same feature count and layer distribution as labeled, but features sampled randomly from the graph after excluding all concept-matching supernodes. 3 deterministic replicates per pair (seeded from `sha256(run_seed:pair_id:replicate:mode)`).

**Field-based additivity**: Intervention restricted to subsets of concept fields. With 3 fields per domain, 7 variants: 3 single-field, 3 two-field combinations, 1 full triple. Each selected field drives both ablation and amplification.

**Answer field decoupling**: Trajectory tracking and exact-match evaluation use an explicit `answer_field` override, decoupling "what we intervene on" from "what we measure."

**Contrast groups**: Each swap pair's contrast group consists of all other dataset answer tokens (e.g., 48 other capitals for USA). Multi-word answers resolve to their first subword token.

### 3.3 Primary Metrics

Based on extensive metric validation (see Appendix C for why gap_closure was de-emphasized), three metrics emerge as the best signal discriminators between labeled and random interventions:


| Metric                   | Definition                                                                      | Why it matters                                                                                                                                                                                                      |
| ------------------------ | ------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Hit%**                 | Target answer appears in steered output                                         | Direct success measure. Zero for random controls in strong domains.                                                                                                                                                 |
| **vsMax**                | best(target_logit - max(other_dataset_answers)) over trajectory                 | Positive = target beats all same-domain alternatives. The cleanest cross-domain specificity discriminator. See Appendix G for position-0 variants, which provide sharper labeled/random separation in most domains. |
| **Target recovery rate** | Does target logit exceed its own unsteered baseline at any trajectory position? | Separates "the model's circuits responded to the target concept" from "everything got disrupted." 92% labeled vs 29% random in regime C (USA).                                                                      |


**Supporting metrics** (used for deeper analysis):


| Metric        | Definition                                                                           |
| ------------- | ------------------------------------------------------------------------------------ |
| Sup%          | Source answer absent from steered output                                             |
| TgtRk / MedRk | Mean and median best target rank during generation                                   |
| vsTopK        | best(target_logit - mean(top-3 other answers))                                       |
| RkGrp         | Best rank within full answer group (1 = top). See Appendix G for position-0 variant. |
| Flip%         | Fraction achieving target > source rank crossover                                    |
| CtrlS         | Mean absolute logit shift of control tokens (the, is, a, of)                         |


---

## 4. Results

### 4.1 Labeled vs Random: Specificity Established

Across 33,387 steering runs, labeled supernodes outperform structurally matched random controls on targeting metrics in 4 of 5 domains, while random controls often achieve equal or higher suppression through generic disruption.

**Headline comparison** (full labeled, all concept fields):


| Domain         | Cond        | N         | Hit%      | Sup%      | vsMax     | RkGrp    | MedRk  |
| -------------- | ----------- | --------- | --------- | --------- | --------- | -------- | ------ |
| **USA States** | **labeled** | **2,450** | **24.7%** | **92.8%** | **+2.86** | **1.72** | **5**  |
|                | random      | 7,350     | 0.1%      | 83.4%     | -2.31     | 9.00     | 566    |
| **Books**      | **labeled** | **240**   | **3.8%**  | **69.2%** | **+5.98** | **1.03** | **17** |
|                | random      | 720       | 0.3%      | 75.0%     | -0.15     | 2.43     | 283    |
| **Products**   | **labeled** | **132**   | **15.2%** | **65.2%** | **+3.46** | **1.20** | **26** |
|                | random      | 396       | 0.3%      | 87.1%     | +0.23     | 2.25     | 354    |
| **Paintings**  | **labeled** | **90**    | **4.4%**  | **34.4%** | **+1.55** | **1.31** | **66** |
|                | random      | 270       | 0.0%      | 74.1%     | -0.03     | 1.96     | 196    |
| **Sounds**     | **labeled** | **30**    | **0.0%**  | **100%**  | **+3.28** | **1.00** | **20** |
|                | random      | 90        | 12.2%     | 80.0%     | +3.14     | 1.08     | 24     |


**Key finding: suppression is generic, targeting is specific.** Random controls achieve higher suppression than labeled in 3 of 5 domains (books 75% vs 69%, products 87% vs 65%, paintings 74% vs 34%). Ablating random features is broadly disruptive. But only labeled supernodes steer toward the correct target -- random hit rates are near-zero in all strong domains, and vsMax is negative or near-zero (target fails to beat same-domain alternatives).

### 4.2 Field Additivity: The "Less is More" Effect

Each domain's concept fields map to semantic roles: **input** (mentioned in prompt), **intermediate** (bridging concept), **answer** (what the model produces). The field-additivity experiment reveals that including input-field supernodes degrades steering performance, often dramatically.

In 4 of 5 domains, a 2-field or 1-field subset outperforms the full 3-field labeled intervention:


| Domain     | Best subset               | Hit%      | Full 3-field Hit% | Delta   |
| ---------- | ------------------------- | --------- | ----------------- | ------- |
| USA States | state+capital (mid+ans)   | **38.8%** | 24.7%             | +14.1pp |
| Books      | book+author (mid+ans)     | **37.1%** | 3.8%              | +33.3pp |
| Products   | company+founder (mid+ans) | **24.2%** | 15.2%             | +9.0pp  |
| Sounds     | sound+animal (in+mid)     | **20.0%** | 0.0%              | +20.0pp |
| Paintings  | first_name alone (ans)    | **6.7%**  | 3.3%              | +3.4pp  |


The optimal subset is consistently **intermediate+answer** for the three strongest domains. Single-field averages across all domains confirm the pattern:


| Role         | Hit%  | Sup%  | MedRk | vsMax | RkGrp |
| ------------ | ----- | ----- | ----- | ----- | ----- |
| Input        | 6.1%  | 63.2% | 106   | +1.90 | 2.55  |
| Intermediate | 14.6% | 79.1% | 43    | +3.37 | 1.56  |
| Answer       | 8.8%  | 89.5% | 36    | +2.39 | 1.75  |


**Interpretation**: Input-field supernodes encode the concept the model *reads* in the prompt, not the concept it needs to *produce*. Including them in the intervention activates competing circuits that dilute or interfere with the answer signal. The model's internal representation of the prompt input is better left undisturbed during steering.

### 4.3 Best Field-Add Variant vs Random (Primary Result)

The cleanest test of label correctness compares the best field-add variant (intermediate+answer) against structurally matched random controls. This removes the noise from input-field features while preserving the full specificity comparison.


| Domain        | Condition                  | N         | Hit%      | vsMax     | MedRk  | RkGrp    |
| ------------- | -------------------------- | --------- | --------- | --------- | ------ | -------- |
| **USA**       | **best (state+capital)**   | **2,450** | **38.8%** | **+4.00** | **3**  | **1.47** |
|               | full labeled               | 2,450     | 24.7%     | +2.86     | 5      | 1.72     |
|               | random                     | 7,350     | 0.1%      | -2.31     | 566    | 9.00     |
| **Books**     | **best (book+author)**     | **240**   | **37.1%** | **+7.76** | **2**  | **1.02** |
|               | full labeled               | 240       | 3.8%      | +5.98     | 17     | 1.03     |
|               | random                     | 720       | 0.3%      | -0.15     | 283    | 2.43     |
| **Products**  | **best (company+founder)** | **132**   | **24.2%** | **+3.06** | **18** | **1.27** |
|               | full labeled               | 132       | 15.2%     | +3.47     | 26     | 1.20     |
|               | random                     | 396       | 0.3%      | +0.23     | 354    | 2.25     |
| **Paintings** | **best (first_name)**      | **90**    | **6.7%**  | **+1.46** | **90** | **1.41** |
|               | full labeled               | 90        | 3.3%      | +1.55     | 66     | 1.32     |
|               | random                     | 270       | 0.0%      | -0.03     | 196    | 1.96     |
| **Sounds**    | **best (sound+animal)**    | **30**    | **20.0%** | **+4.69** | **5**  | **1.07** |
|               | full labeled               | 30        | 0.0%      | +3.40     | 20     | 1.00     |
|               | random                     | 90        | 12.2%     | +3.14     | 24     | 1.08     |


**The best variant vs random gap** on the three primary metrics:


| Domain    | Hit%: best / random | vsMax: best / random | Recovery: best / random |
| --------- | ------------------- | -------------------- | ----------------------- |
| USA       | 38.8% / 0.1%        | +4.00 / -2.31        | 93% / 29%               |
| Books     | 37.1% / 0.3%        | +7.76 / -0.15        | 96% / 89%               |
| Products  | 24.2% / 0.3%        | +3.06 / +0.23        | 86% / 83%               |
| Paintings | 6.7% / 0.0%         | +1.46 / -0.03        | 89% / 77%               |
| Sounds    | 20.0% / 12.2%       | +4.69 / +3.14        | n/a                     |


Target recovery rates are from regime C (both tokens disrupted, target overtakes source), which is the dominant labeled behavior. The separation is sharpest for USA (93% vs 29%) and weakens across the domain gradient.

### 4.4 Logit-Shift Regime Taxonomy

Binary hit/miss evaluation obscures a rich structure in the logit trajectories. Classifying every swap by what happens to target and source logits at position 0 reveals four regimes:


| Regime | Target logit | Source logit | Flip? | Intuition                                                  |
| ------ | ------------ | ------------ | ----- | ---------------------------------------------------------- |
| **A**  | UP           | DOWN         | yes   | Clean redirection: target gains, source loses              |
| **C**  | DOWN         | DOWN         | yes   | Both disrupted, target less so (differential disruption)   |
| **D**  | DOWN         | DOWN         | no    | Both disrupted, source still dominant (generic disruption) |
| **E**  | FLAT         | DOWN         | yes   | Pure suppression, no target lift                           |


**The best field-add variant shifts cases from weak regimes to strong ones.** Regime A (cleanest label evidence) prevalence for best variant vs full labeled vs random:


| Dataset   | Best variant | Full labeled | Random |
| --------- | ------------ | ------------ | ------ |
| USA       | **34.9%**    | 8.9%         | 19.4%  |
| Books     | **62.1%**    | 38.8%        | 40.8%  |
| Products  | **62.1%**    | 56.8%        | 51.5%  |
| Paintings | **47.8%**    | 17.8%        | 23.3%  |


Simultaneously, regime D (generic disruption, weakest evidence) nearly vanishes for the best variant:


| Dataset   | Best variant | Full labeled | Random |
| --------- | ------------ | ------------ | ------ |
| USA       | **9.1%**     | 19.4%        | 45.3%  |
| Books     | **3.3%**     | 3.3%         | 34.6%  |
| Products  | **2.3%**     | 2.3%         | 22.0%  |
| Paintings | **2.2%**     | 6.7%         | 42.2%  |


Random controls concentrate in regime D (42--45%), while the best variant concentrates in regime A. Removing input-field features eliminates generic disruption and produces more surgical interventions.

**Within regime C** (both disrupted, target overtakes), labeled and random diverge sharply on three signals:


| Signal                            | Labeled (USA) | Random (USA) |
| --------------------------------- | ------------- | ------------ |
| Target recovery rate              | 92.2%         | 29.3%        |
| Sustained dominance (tgt_win_pct) | 0.673         | 0.319        |
| vsMax                             | +2.33         | -0.10        |
| Hit%                              | 22.5%         | 0.6%         |


These three sub-regime signals (target recovery, sustained dominance, vsMax) are the most discriminating evidence that labeled features capture genuine circuit structure rather than producing generic disruption.

### 4.5 Domain Gradient

The specificity gap between labeled and random follows a consistent domain gradient:


| Domain     | vsMax gap (labeled - random) | Interpretation |
| ---------- | ---------------------------- | -------------- |
| Books      | +6.13                        | Strong         |
| USA States | +5.17                        | Strong         |
| Products   | +3.23                        | Moderate       |
| Paintings  | +1.58                        | Weak           |
| Sounds     | +0.14                        | Negligible     |


The gradient does not track graph size (weaker domains have *more* features and supernodes) but correlates with:

- **CLT error node density**: USA ~10% error influence vs paintings/products ~15%
- **Answer-field specificity**: "capital" and "author" are highly specific; "first_name" and "color" are coarse
- **Circuit complexity**: Geographic capitals are single-hop factual lookups; painting attribution probably requires multi-step reasoning
- **Review-flagged burden**: Products 6.3 avg review-flagged features vs paintings 55.0

The honest characterization: *the method demonstrates entity-specific causal leverage primarily in single-hop factual domains with low CLT reconstruction error, with degradation tracking both associative complexity and answer-field coarseness*.

### 4.6 Cross-Prompt Robustness

**Evidence** (Dallas vs Oakland, detailed supernode comparison):

- 7/7 universal concept supernodes transfer (copula, prepositions, relational operators)
- 8/8 entity-specific supernodes show appropriate non-transfer
- 25 shared features (12.8% of total) with 94% activation stability
- Layer 0--1 feature overlap: 80--92%; Layer 16--22 overlap: 0--50%

Clean disentanglement of task structure from factual content supports robust concept discovery. The low overall feature overlap (12.8%) reflects entity-specificity, not failure.

---

## 5. Methodological Strengths

1. **Transparency**: All classification rules are explicit thresholds, not learned parameters. Every assignment is traceable to specific threshold crossings.
2. **Deterministic pipeline**: No random sampling or initialization (aside from LLM probe generation, which is manually reviewed). Fixed random seeds throughout.
3. **Multi-condition evaluation**: Labeled vs random-matched controls, field-level decomposition, regime taxonomy -- each addresses a distinct aspect of specificity.
4. **Scale**: 33,387 steering runs across 5 domains, with contrast groups tracking all same-domain alternatives per pair.
5. **Non-frozen attention**: Interventions run with `freeze_attention: false`. The model can route around perturbations, making positive results stronger evidence than constrained patching where some effects are architecturally guaranteed.
6. **Reproducibility**: Checkpoint/resume system, documented configurations, deterministic RNG for random controls, public codebase.

---

## 6. Limitations and Open Questions

### 6.1 Attention Circuit Blindspot

Attribution graphs freeze attention during computation, but interventions run with free attention. Features selected from the frozen-attention graph may fail to produce effects when attention compensates. This asymmetry likely contributes to the gap between logit-level success (high flip rates) and output-level success (lower hit rates), and may be the primary limiting factor in complex domains.

### 6.2 Token Overlap Confound

Six USA states share tokens between prompt city and state name (Colorado/Colorado Springs, New York/New York City, etc.). Preliminary evidence suggests overlap makes swaps *harder* (attention binds overlapping tokens strongly to source output). The `has_token_overlap` flag exists but stratified results have not been computed.

### 6.3 Substring Matching Confound

The concept-to-supernode matcher allows reverse containment (e.g., supernode "is" matching concept "mississippi"). This affects 28--45% of entity-field combinations across domains and can add semantically questionable supernodes. Impact on downstream swap performance is unmeasured.

### 6.4 Multi-Token Limitations

Multi-word answers (e.g., "J.K. Rowling", "New York City") resolve to their first subword token for trajectory tracking. Multi-token concept names are matched by splitting on spaces and matching words of length >= 3. Both heuristics can miss or create false matches.

### 6.5 Sounds Dataset Structural Issues

The sounds domain has only 6 entities, 12/30 non-identity pairs share the same answer ("brown"), and some concept fields match zero supernodes. It should not be weighted equally in cross-domain conclusions.

### 6.6 Statistical Methodology

All comparisons are descriptive (means, rates, percentages). Given sample sizes (2,450+ for USA, 240 for books), formal inference (bootstrap confidence intervals, permutation tests) would be informative.

### 6.7 Remaining Proposed Experiments


| Experiment                                        | Priority | Status                                  |
| ------------------------------------------------- | -------- | --------------------------------------- |
| Token overlap stratification                      | HIGH     | Infrastructure exists, not run          |
| Intervention multiplier sweep                     | MEDIUM   | Not run                                 |
| Ablation-only vs amplification-only decomposition | MEDIUM   | Partially addressed by field additivity |
| Threshold sensitivity analysis                    | MEDIUM   | Not run                                 |
| Cross-domain supernode transfer                   | MEDIUM   | Not run                                 |
| Probe prompt sensitivity                          | LOW      | Not run                                 |
| Attention-aware validation                        | LOW      | Requires infrastructure changes         |


---

## 7. Summary of Epistemic Status

### Level 1 -- Operationally Useful Labels: WELL-SUPPORTED

The pipeline produces behaviorally grounded, interpretable supernode groupings across 5 domains. Feature categories (Semantic Dictionary, Semantic Concept, Say-X, Relationship) are behaviorally distinct and produce labeled supernodes useful for navigating circuits. Cross-prompt robustness is demonstrated for geographic circuits.

### Level 2 -- Downstream Causal Effects: ESTABLISHED VIA SPECIFICITY CONTROLS

This is the report's main advance. Three lines of evidence support entity-specific causal leverage of labeled supernodes:

1. **Labeled vs random specificity**: Labeled supernodes outperform structurally matched random controls on vsMax in 4/5 domains (gap: +6.13 books, +5.17 USA, +3.23 products, +1.58 paintings). Random controls achieve equal or higher suppression through generic disruption but near-zero targeting.
2. **Field-level decomposition**: The best field-add variant (intermediate+answer) dramatically outperforms both the full 3-field labeled and random controls, confirming that the steering signal resides in semantically appropriate features, not in the total perturbation magnitude. Hit rates: 38.8% (USA), 37.1% (books), 24.2% (products) for best variant vs 0.1%, 0.3%, 0.3% for random.
3. **Target recovery within disruption regimes**: When both target and source tokens are disrupted (regime C, the dominant outcome), labeled interventions produce target recovery above the unsteered baseline 92% of the time (USA) vs 29% for random. This separates "the model's circuits responded to the target concept" from "everything got disrupted."

### Level 2 -- Remaining Gaps

- **Sounds specificity is negligible** (vsMax gap +0.14), limiting the method to 4 of 5 tested domains.
- **Paintings specificity is weak** (vsMax gap +1.58, 6.7% hit for best variant), suggesting the method is unreliable for abstract/multi-step reasoning domains.
- **Hit% remains modest** even for the best variant (38.8% USA, 37.1% books), indicating that feature-level steering is a partial, not complete, mechanism for controlling model output.

### Level 3 -- Full Mechanistic Explanation: NOT CLAIMED

The labels are behavioral abstractions, not ontological identifications of latent variables. The classification thresholds have not undergone sensitivity analysis. Whether the feature categories correspond to natural computational types or to arbitrary partitions of a continuous behavioral space remains an open question.

### Overall Assessment

This work establishes that labeled supernodes have entity-specific causal leverage beyond generic perturbation, primarily via three signals: hit rate, vsMax, and target recovery rate. The best field-add variant (intermediate+answer fields) provides the cleanest evidence, showing that the steering signal resides in the features the model uses for internal concept resolution and output production, while prompt-input features contribute noise. The method's operating envelope is single-hop factual domains with low CLT reconstruction error; it degrades predictably with circuit complexity and error node density.

---

## 8. Notation and Definitions Reference


| Symbol          | Definition                                                                      |
| --------------- | ------------------------------------------------------------------------------- |
| CLT             | Cross-Layer Transcoder (reads residual stream, writes to downstream MLP layers) |
| CPAS            | Cross-Prompt Activation Signature                                               |
| tau             | Cumulative influence threshold for feature selection                            |
| M_ablate        | Multiplication factor for source features during intervention (default: -2)     |
| M_amplify       | Multiplication factor for target features during intervention (default: 20)     |
| vsMax           | best(target_logit - max(other_dataset_answers)) over trajectory                 |
| RkGrp           | Best rank of target within all dataset answer tokens (1 = top)                  |
| Target recovery | Target logit exceeds its own unsteered baseline at any trajectory position      |
| Regime A        | Target logit UP, source logit DOWN, flip at position 0                          |
| Regime C        | Both logits DOWN, flip at position 0 (differential disruption)                  |
| Regime D        | Both logits DOWN, no flip (generic disruption)                                  |
| Tier            | Domain-specific ordinal quality score for swap outcomes (0--5 for USA states)   |


---

## 9. References

- Ameisen et al. (2025). "Circuit Tracing: Revealing Computational Graphs in Language Models." Transformer Circuits, March 2025.
- Geiger et al. (2025). "Causality is Key for Interpretability Claims to Generalise." arXiv:2602.16698.
- Raukur et al. (2025). "Open Problems in Mechanistic Interpretability." arXiv:2501.16496.
- Heap et al. (2025). "Sparse Autoencoders Can Interpret Randomly Initialized Transformers." arXiv:2501.17727.
- Kharlapenko et al. (2024). "Improving Steering Vectors by Targeting Sparse Autoencoder Features." arXiv:2411.02193.
- Birardi (2025). "Automated Circuit Interpretation via Probe Prompting." arXiv:2511.07002.

---

## Appendix A: Full-Scale Labeled vs Random by Domain

Complete results table including all metrics:


| Domain     | Cond    | N     | Hit%  | Sup%  | GapCl | TgtRk | MedRk | vsMax | vsTopK | RkGrp | Flip% |
| ---------- | ------- | ----- | ----- | ----- | ----- | ----- | ----- | ----- | ------ | ----- | ----- |
| USA States | labeled | 2,450 | 24.7% | 92.8% | 4.67  | 74.6  | 5     | +2.86 | +3.76  | 1.72  | 98.2% |
|            | random  | 7,350 | 0.1%  | 83.4% | 2.43  | 1,836 | 566   | -2.31 | -1.65  | 9.00  | 69.2% |
| Books      | labeled | 240   | 3.8%  | 69.2% | 0.01  | 44.7  | 18    | +5.98 | +7.40  | 1.03  | 96.7% |
|            | random  | 720   | 0.3%  | 75.0% | 3.39  | 1,608 | 283   | -0.15 | +0.76  | 2.43  | 79.6% |
| Products   | labeled | 132   | 15.2% | 65.2% | 0.19  | 67.0  | 26    | +3.46 | +5.11  | 1.20  | 97.0% |
|            | random  | 396   | 0.3%  | 87.1% | 1.70  | 1,547 | 354   | +0.23 | +1.21  | 2.25  | 75.3% |
| Paintings  | labeled | 90    | 4.4%  | 34.4% | 0.80  | 587.7 | 70    | +1.55 | +3.01  | 1.31  | 97.8% |
|            | random  | 270   | 0.0%  | 74.1% | 3.49  | 1,187 | 196   | -0.03 | +1.26  | 1.96  | 88.9% |
| Sounds     | labeled | 30    | 0.0%  | 100%  | 1.46  | 42.5  | 21    | +3.28 | +3.53  | 1.00  | 60.0% |
|            | random  | 90    | 12.2% | 80.0% | 2.29  | 133   | 24    | +3.14 | +3.72  | 1.08  | 53.3% |


**Specificity discriminators summary**:


| Domain     | Labeled vsMax | Random vsMax | Gap  | Strength   |
| ---------- | ------------- | ------------ | ---- | ---------- |
| Books      | +5.98         | -0.15        | 6.13 | Strong     |
| USA States | +2.86         | -2.31        | 5.17 | Strong     |
| Products   | +3.46         | +0.23        | 3.23 | Moderate   |
| Paintings  | +1.55         | -0.03        | 1.58 | Weak       |
| Sounds     | +3.28         | +3.14        | 0.14 | Negligible |


---

## Appendix B: Field-Based Additivity Detail Tables

### B.1 USA States (2,450 non-identity pairs per variant)


| Fields            | Role         | Hit%      | Sup%      | GapCl    | MedRk | vsMax     | vsTopK    | RkGrp    |
| ----------------- | ------------ | --------- | --------- | -------- | ----- | --------- | --------- | -------- |
| city              | input        | 2.9%      | 68.4%     | 3.56     | 190   | -1.26     | -0.49     | 6.92     |
| state             | intermediate | 17.0%     | 83.3%     | 4.38     | 14    | +2.38     | +3.33     | 2.72     |
| capital           | answer       | 14.2%     | 95.6%     | 2.23     | 11    | +0.63     | +1.33     | 3.69     |
| **state+capital** | **mid+ans**  | **38.8%** | **98.0%** | **3.74** | **3** | **+4.00** | **+4.86** | **1.47** |
| state+city        | mid+in       | 11.1%     | 82.7%     | 4.88     | 28    | +1.71     | +2.56     | 2.31     |
| capital+city      | ans+in       | 10.2%     | 91.2%     | 3.35     | 30    | +0.58     | +1.40     | 4.16     |
| all 3 (labeled)   | all          | 24.7%     | 92.8%     | 4.67     | 5     | +2.86     | +3.76     | 1.72     |


### B.2 Books (240 non-identity pairs per variant)


| Fields           | Role         | Hit%      | Sup%      | GapCl    | MedRk | vsMax     | vsTopK    | RkGrp    |
| ---------------- | ------------ | --------- | --------- | -------- | ----- | --------- | --------- | -------- |
| character        | input        | 4.2%      | 67.9%     | 1.46     | 125   | +1.87     | +3.18     | 1.77     |
| book             | intermediate | 37.1%     | 83.3%     | 0.24     | 2     | +6.69     | +8.25     | 1.20     |
| author           | answer       | 14.6%     | 92.1%     | 0.20     | 12    | +4.71     | +6.61     | 1.33     |
| **book+author**  | **mid+ans**  | **37.1%** | **84.6%** | **0.04** | **2** | **+7.76** | **+9.58** | **1.02** |
| character+book   | in+mid       | 5.0%      | 77.5%     | 0.15     | 24    | +5.22     | +6.71     | 1.23     |
| character+author | in+ans       | 3.8%      | 75.0%     | 0.21     | 76    | +3.45     | +4.73     | 1.30     |
| all 3 (labeled)  | all          | 3.8%      | 69.6%     | 0.02     | 17    | +5.97     | +7.39     | 1.03     |


Adding character supernodes degrades from 37.1% to 3.8% hit -- a dramatic interference effect.

### B.3 Products (132 non-identity pairs per variant)


| Fields              | Role         | Hit%      | Sup%      | GapCl    | MedRk  | vsMax     | vsTopK    | RkGrp    |
| ------------------- | ------------ | --------- | --------- | -------- | ------ | --------- | --------- | -------- |
| product             | input        | 0.0%      | 62.1%     | 0.20     | 137    | +1.90     | +3.46     | 1.61     |
| company             | intermediate | 5.3%      | 71.2%     | 0.26     | 128    | +2.62     | +4.39     | 1.39     |
| founder             | answer       | 8.3%      | 84.1%     | 0.51     | 18     | +2.08     | +3.07     | 1.27     |
| **company+founder** | **mid+ans**  | **24.2%** | **68.9%** | **0.35** | **18** | **+3.06** | **+4.48** | **1.27** |
| product+company     | in+mid       | 1.5%      | 68.2%     | 0.15     | 93     | +2.78     | +4.92     | 1.31     |
| product+founder     | in+ans       | 2.3%      | 66.7%     | 0.05     | 48     | +2.54     | +4.01     | 1.23     |
| all 3 (labeled)     | all          | 15.2%     | 63.6%     | 0.19     | 26     | +3.47     | +5.10     | 1.20     |


### B.4 Paintings (90 non-identity pairs per variant)


| Fields             | Role         | Hit% | Sup%  | GapCl | MedRk | vsMax | vsTopK | RkGrp |
| ------------------ | ------------ | ---- | ----- | ----- | ----- | ----- | ------ | ----- |
| painting           | input        | 3.3% | 34.4% | 0.71  | 71    | +1.50 | +2.72  | 1.44  |
| painter            | intermediate | 1.1% | 70.0% | 0.45  | 66    | +1.68 | +2.76  | 1.30  |
| first_name         | answer       | 6.7% | 75.6% | 0.79  | 90    | +1.46 | +2.72  | 1.41  |
| painter+first_name | mid+ans      | 1.1% | 70.0% | 0.49  | 65    | +1.69 | +2.78  | 1.30  |
| all 3 (labeled)    | all          | 3.3% | 33.3% | 0.84  | 66    | +1.55 | +2.99  | 1.32  |


Painter name subsumes first name in supernode matching, making painter and painter+first_name effectively identical. Weak steering across all variants.

### B.5 Sounds (30 non-identity pairs per variant)


| Fields           | Role         | Hit%      | Sup%      | GapCl    | MedRk | vsMax     | vsTopK    | RkGrp    |
| ---------------- | ------------ | --------- | --------- | -------- | ----- | --------- | --------- | -------- |
| sound            | input        | 20.0%     | 83.3%     | 2.75     | 5     | +5.49     | +5.91     | 1.00     |
| animal           | intermediate | 12.5%     | 87.5%     | 1.61     | 6     | +3.49     | +4.07     | 1.21     |
| color            | answer       | 0.0%      | 100%      | 1.51     | 48    | +3.09     | +3.68     | 1.07     |
| **sound+animal** | **in+mid**   | **20.0%** | **70.0%** | **1.15** | **5** | **+4.69** | **+4.99** | **1.07** |
| all 3 (labeled)  | all          | 0.0%      | 96.7%     | 1.50     | 20    | +3.40     | +3.66     | 1.00     |


Sounds is the exception to the intermediate+answer pattern: the input field (sound name) carries the strongest signal.

---

## Appendix C: Why Gap Closure Was De-Emphasized

Gap closure (`max(gap_trajectory) - gap_trajectory[0]`) was initially used as a primary metric. Analysis across logit-shift regimes reveals it is regime-dependent and often misleading:


| Regime                 | Labeled GapCl (USA) | Random GapCl (USA) | Labeled vsMax | Random vsMax |
| ---------------------- | ------------------- | ------------------ | ------------- | ------------ |
| A (tgt UP, src DOWN)   | 0.88                | 0.76               | +4.28         | -0.19        |
| C (both DOWN, flip)    | 2.73                | 1.59               | +2.33         | -0.10        |
| D (both DOWN, no flip) | **13.62**           | **6.46**           | +4.11         | -0.07        |


**Regime A**: Gap closure is redundant. Target already flipped above source; closure just measures further separation. vsMax separation (delta 4.47) dwarfs gap closure separation (delta 0.12).

**Regime C**: Gap closure is weakly informative. Target recovery rate (92% vs 29%) and sustained dominance (0.67 vs 0.32) are cleaner signals.

**Regime D**: Gap closure is **actively misleading**. Regime D shows the *highest* gap closure (13.62) despite being the weakest evidence regime. Both tokens start far apart and both get disrupted, creating room for gap "closure" without the target ever winning. A naive reader would think regime D is the strongest outcome.

**Cross-domain**: Gap closure says books is nearly zero (0.01) while USA is strong (4.67). But vsMax says books is the *strongest* domain (+5.98 vs +2.86). The discrepancy arises because books pairs have small baseline gaps, limiting room for "closure" even when the target wins convincingly. Gap closure is confounded by baseline gap magnitude and is not comparable across domains.

---

## Appendix D: Known Data Quality Issues

From curiosity-sampled inspection of 15 swap pairs across all domains:

1. **Exact-match prompt leakage**: In 0.04% of USA swaps, the target answer appears in the prompt string, inflating hit metrics. Other domains: 0%.
2. **Answer-level identity pairs**: Books has 2/240 pairs sharing the same answer (atticus_finch / scout_finch, both "Harper Lee"). Sounds has 12/30 pairs sharing the answer "brown" (40% of the dataset).
3. **First-token false positives**: 2--10% of swaps across domains have `first_token_matches_target = True` while `steered_has_to_answer = False` (e.g., "Mark" matching because of "Mark Hurd" instead of "Mark Zuckerberg").
4. **Rank-hit misalignment**: 56--100% of swaps with rank_in_group = 1 have no exact-match hit. The first-token logit trajectory and the decoded text are measuring different things.
5. **Zero-coverage concept fields**: In sounds, `animal` has zero matching supernodes for 2/6 entities.
6. **USA directory overcounting**: `output/usa_states_batch/` contains 68 directories but only 50 canonical entities (extras are casing/formatting variants).

---

## Appendix E: Tier Classification System

### USA States (full geographic classifier)


| Tier | Name              | Criterion                                           |
| ---- | ----------------- | --------------------------------------------------- |
| 5    | PERFECT           | Target capital appears in output                    |
| 4    | TARGET_STATE_CITY | Other city in target state (not capital)            |
| 3    | TARGET_STATE_ONLY | Target state mentioned, no valid city               |
| 2    | SUPPRESSED_ONLY   | Source suppressed, garbled or non-geographic output |
| 1    | SOURCE_PERSISTS   | Source capital/city still in output                 |
| 0    | WRONG_STATE       | City from a third state                             |


### Non-USA Domains (simplified evaluation)

Tier 5 (PERFECT): target answer detected via full-answer match, first-token substring match, or any word (len >= 3) of the target answer appearing in output. Tier 2 (SUPPRESSED): source absent, no target signal. Tier 1 (SOURCE_PERSISTS): source answer remains. Tiers 3--4 exist only for USA states.

**Cross-domain comparability warning**: T5 rates for non-USA domains are more generous due to word-level matching. Strict exact match rates (target answer as a whole in output): USA 38.8%, Books 36.7%, Products 24.2%, Sounds 3.3%, Paintings 1.1%.

---

---

## Appendix F: Individual Case Studies -- Success/Failure Grid

This appendix presents individual steering cases drawn from the best field-add variant across all five domains. Cases are selected to cover the full space of metric combinations and edge conditions. For each case we report the key metrics and an interpretive judgment of success or failure.

**Metric key**: vsMax = best(target logit - max other answer); rkGrp = best rank within answer group; flip@0 = target overtakes source at position 0; gap_cl = gap closure over trajectory; ctrl_stab = control stability (mean absolute logit change of control tokens); err_src/tgt = error node influence % for source/target entity; tgt_base_rk = target's unsteered rank; ablate/amplify = feature counts.

**Condition**: All cases use the best field-add variant (intermediate + answer fields) unless noted otherwise. This is: state+capital (USA), book+author (Books), company+founder (Products), painter+first_name (Paintings), sound+animal (Sounds).

### F.1 Domain Distribution Summary

Before examining individual cases, the aggregate distributions for the best field-add variant:


| Domain    | N     | Hit%  | rkGrp=1 % | Regime A (flip+hit) | Regime B (flip+miss) | Regime C (no-flip+hit) | Regime D (no-flip+miss) |
| --------- | ----- | ----- | --------- | ------------------- | -------------------- | ---------------------- | ----------------------- |
| USA       | 2,450 | 38.8% | 91.8%     | 35.4%               | 55.2%                | 3.3%                   | 6.0%                    |
| Books     | 240   | 37.1% | 98.8%     | 36.3%               | 60.4%                | 0.8%                   | 2.5%                    |
| Products  | 132   | 24.2% | 76.5%     | 24.2%               | 72.7%                | 0.0%                   | 3.0%                    |
| Paintings | 90    | 1.1%  | 81.1%     | 1.1%                | 96.7%                | 0.0%                   | 2.2%                    |
| Sounds    | 30    | 20.0% | 93.3%     | 0.0%                | 50.0%                | 20.0%                  | 30.0%                   |


**Key observation**: rkGrp=1 rates (76--99%) far exceed Hit% rates (1--39%) across all domains. The target token dominates the logit trajectory in most cases but decoded text often does not reflect this -- the rank-hit misalignment described in Appendix D. This means many cases classified below as "failures" are logit-level successes but output-level failures.

### F.2 Success Cases

#### F.2.1 Spectacular Success -- Regime A, Strong Domain (USA)

**Colorado Springs -> Detroit** (state+capital)


| Metric         | Value   | Interpretation                                                            |
| -------------- | ------- | ------------------------------------------------------------------------- |
| vsMax          | +17.5   | Target (Lansing) beats every other capital by 17.5 logits                 |
| rkGrp          | 1       | Target is the top-ranked answer at best trajectory position               |
| flip@0         | True    | Immediate flip at position 0                                              |
| gap_cl         | 14.53   | Large sustained gap growth                                                |
| hit            | True    | "Lansing" appears in steered output                                       |
| ctrl_stab      | 12.11   | Moderate collateral disruption                                            |
| err_src        | 11.72%  | Lowest error node source in USA (best graph quality)                      |
| err_tgt        | 14.51%  | Higher error node target                                                  |
| tgt_base_rk    | 342     | Target was rank 342 before steering -- pushed from obscurity to dominance |
| ablate/amplify | 74 / 51 | Moderate feature counts                                                   |


**Output**: Default " Denver..." -> Steered "...is's population is Lansing. Lansing is located..."

**Interpretation** (SUCCESS): Textbook regime A case. Source (Denver, p=0.37) completely suppressed; target (Lansing) emerges from rank 342 to rank 1. The non-grammatical "is's population is" shows the intervention's disruption of syntax while successfully redirecting factual content. Colorado Springs has the lowest error node rate (11.72%) in the USA dataset, consistent with the finding that better graph quality enables stronger steering. The target entity (Michigan/Detroit) has higher error nodes (14.51%) but the amplification side still works -- target features carry enough signal despite reconstruction gaps.

#### F.2.2 Cross-Domain Spectacle -- Books

**Holden Caulfield -> Katniss Everdeen** (book+author)


| Metric         | Value   |
| -------------- | ------- |
| vsMax          | +21.79  |
| rkGrp          | 1       |
| flip@0         | True    |
| gap_cl         | 0.0     |
| hit            | True    |
| err_src        | 12.86%  |
| tgt_base_rk    | 267     |
| ablate/amplify | 11 / 63 |


**Output**: Default "Harper Lee..." -> Steered "...Suzanne Collins..."

**Interpretation** (SUCCESS): The highest vsMax in the entire dataset (21.79), achieved with only 11 ablated features -- the source (Caulfield/Catcher in the Rye) requires very few features to suppress. The 0.0 gap closure reflects an immediate domination pattern: the target already leads by a large margin at position 0, with no room for further closure. Books is the strongest domain by vsMax despite having only 240 pairs (vs 2,450 for USA), confirming that domain specificity strength is not a function of sample size.

#### F.2.3 Product Founder Redirection -- Products

**Nike Shoes -> Model S** (company+founder)


| Metric              | Value            |
| ------------------- | ---------------- |
| vsMax               | +12.25           |
| rkGrp               | 1                |
| flip@0              | True             |
| gap_cl              | 6.84             |
| hit                 | True             |
| err_src             | 14.33%           |
| tgt_base_rk         | 5,933            |
| ablate/amplify      | 91 / 62          |
| steered first token | " Elon" (p=0.82) |


**Output**: Default "Bill Bowerman and Phil Knight..." -> Steered "Elon Musk. That's right. The company..."

**Interpretation** (SUCCESS): Dramatic redirection from Phil Knight to Elon Musk, with the target pushed from rank 5,933 to rank 1. The steered first token probability (0.82) is remarkably high -- the model is very confident about "Elon" after intervention. This is the cleanest product-domain hit: the model's knowledge of Tesla/Musk is strong enough that the amplified features lock onto it decisively.

#### F.2.4 Rare Paintings Success

**Grande Jatte -> Water Lilies** (painter+first_name)


| Metric         | Value   |
| -------------- | ------- |
| vsMax          | +9.375  |
| rkGrp          | 1       |
| flip@0         | True    |
| gap_cl         | 3.125   |
| hit            | True    |
| err_src        | 13.66%  |
| err_tgt        | 13.50%  |
| tgt_base_rk    | 3       |
| ablate/amplify | 92 / 70 |


**Output**: Default "Georges Seurat..." -> Steered "**Claude Monet** (1840-..."

**Interpretation** (SUCCESS): The only hit in the painter+first_name variant (1/90 = 1.1%). Two factors explain why this pair succeeds where 89 others fail: (1) the target (Claude) already ranks 3rd at baseline -- the model nearly produces it unsteered; (2) both entities have below-median error node rates. The steered output includes HTML formatting artifacts ( tags), a quirk of the model's generation under perturbation. This case illustrates the paintings domain's core problem: success requires the target to be almost already correct, leaving little room for the intervention to demonstrate causal leverage.

#### F.2.5 Sounds Shared-Answer Success

**Bark -> Hoot** (sound+animal)


| Metric         | Value   |
| -------------- | ------- |
| vsMax          | +13.0   |
| rkGrp          | 1       |
| flip@0         | False   |
| gap_cl         | 0.0     |
| hit            | True    |
| err_src        | 12.16%  |
| tgt_base_rk    | 1       |
| ablate/amplify | 33 / 57 |


**Output**: Default "brown..." -> Steered "...is brown..."

**Interpretation** (MECHANICAL SUCCESS -- not genuine evidence): Both bark (dog) and hoot (owl) share the answer "brown." The target baseline rank is already 1 -- it is the top answer without any intervention. The gap trajectory is flat zeros because source and target track the same token. This is a structural artifact of the sounds dataset (12/30 pairs share answers). The high vsMax (+13.0) is misleading: it measures target vs other answers (green, black, etc.), not target vs source. This case should not be counted as evidence of label quality.

#### F.2.6 Labeled (All Fields) Success -- USA

**Minnesota/Minneapolis -> Florida/Miami** (all 3 fields)


| Metric         | Value   |
| -------------- | ------- |
| vsMax          | +16.06  |
| rkGrp          | 1       |
| flip@0         | False   |
| gap_cl         | 16.56   |
| hit            | True    |
| err_src        | 13.0%   |
| ctrl_stab      | 16.89   |
| ablate/amplify | 82 / 66 |


**Output**: Default "St. Paul..." -> Steered "Beach, Florida is Tallahassee..."

**Interpretation** (SUCCESS with caveats): Strong hit with Tallahassee appearing in output, but note: (1) flip@0 is False -- the target does not lead at position 0, taking until position 3 to overtake; (2) control stability is high (16.89), indicating substantial collateral disruption; (3) the steered output produces "Beach, Florida is Tallahassee" -- suggesting the city-field features (Miami -> "Beach") are contributing noise that delays the clean answer. Contrast with the state+capital variant where city features are excluded: there, USA achieves 38.8% hit vs 24.7% with all fields.

### F.3 Failure Cases

#### F.3.1 Total Failure -- Garbled Output (USA)

**Kansas/Wichita -> New Hampshire/Manchester** (state+capital)


| Metric         | Value   |
| -------------- | ------- |
| vsMax          | -6.875  |
| rkGrp          | 29      |
| flip@0         | True    |
| gap_cl         | 0.0     |
| hit            | False   |
| suppressed     | True    |
| err_src        | 12.87%  |
| tgt_base_rk    | 5,816   |
| ablate/amplify | 63 / 27 |


**Output**: Default "Topeka..." -> Steered "(Arabic characters), Oklahoma City, Tulsa and Norman..."

**Interpretation** (FAILURE -- target too obscure): Target (Concord, NH) starts at rank 5,816 -- deeply buried in the vocabulary. Despite flip@0=True (differential disruption), the intervention cannot lift the target above 28 other capitals (rkGrp=29). The steered output degenerates into garbled text and Oklahoma geography, suggesting the amplified features for New Hampshire are too weak (only 27 amplified features) to overcome the model's near-zero prior for "Concord." The worst vsMax (-6.875) in the USA dataset. New Hampshire appears as the target in 4/5 of the worst USA failures, indicating a systematic entity-level weakness -- likely low supernode coverage or weak feature activations for this entity.

#### F.3.2 Near-Miss -- Logit Success, Output Failure (USA)

**Utah/Provo -> Iowa/Cedar Rapids** (state+capital)


| Metric      | Value  |
| ----------- | ------ |
| vsMax       | +14.0  |
| rkGrp       | 1      |
| flip@0      | True   |
| gap_cl      | 0.0    |
| hit         | False  |
| suppressed  | True   |
| err_src     | 13.74% |
| tgt_base_rk | 18     |
| ctrl_stab   | 14.06  |


**Output**: Default "Salt Lake City..." -> Steered "WithMany things to do in Utah..."

**Interpretation** (FAILURE -- rank-hit misalignment): The logit trajectory says this is a clear success: vsMax=+14.0, rkGrp=1, the target token (Des Moines) dominates. But the decoded output is garbled ("WithMany things to do in Utah"). This is the rank-hit misalignment problem: the first-token logit trajectory tracks "Des" (the first subword of Des Moines) which achieves rank 1, but at decoding time the model produces a different token. High control stability (14.06) suggests broad disruption beyond the target circuit. 56% of rkGrp=1 cases in USA have no hit, confirming this is systematic, not anomalous.

#### F.3.3 Regime D -- Generic Disruption (USA)

**Ohio/Cleveland -> Oklahoma/Tulsa** (state+capital)


| Metric      | Value  |
| ----------- | ------ |
| vsMax       | +13.31 |
| rkGrp       | 1      |
| flip@0      | False  |
| gap_cl      | 25.95  |
| hit         | False  |
| ctrl_stab   | 15.30  |
| tgt_base_rk | 34     |


**Interpretation** (FAILURE -- no flip despite strong logits): flip@0=False means the target never overtakes the source at position 0 -- this is regime D (both disrupted, source still dominant initially). Yet gap_cl=25.95 is extremely high and vsMax=+13.31 shows eventual target dominance. The high control stability (15.30) indicates the intervention is broadly disruptive. The target eventually wins in the logit trajectory but the output generation, which conditions autoregressively, never recovers from the initial position-0 failure. This illustrates why flip@0 is mechanically important even if it is not a clean specificity signal: the model's autoregressive decoding amplifies early-position errors.

#### F.3.4 Books Failure -- Source Suppression Without Redirection

**Scout Finch -> Huckleberry Finn** (book+author)


| Metric         | Value    |
| -------------- | -------- |
| vsMax          | +9.19    |
| rkGrp          | 1        |
| flip@0         | True     |
| gap_cl         | 0.0      |
| hit            | False    |
| suppressed     | True     |
| tgt_base_rk    | 101      |
| ablate/amplify | 65 / 176 |


**Output**: Default "Harper Lee..." -> Steered "'s first novel. It was published in 1..."

**Interpretation** (FAILURE -- high amplify count, garbled output): Despite 176 amplified features (highest in Books) and excellent logit metrics (vsMax=+9.19, rkGrp=1), the output is garbled. The excessive amplification count suggests a noisy supernode match for Huckleberry Finn, possibly inflated by substring confounds ("finn" matching functional supernodes). Harper Lee is successfully suppressed but Mark Twain never emerges. This is a case where more features hurt rather than help -- consistent with the "less is more" finding.

#### F.3.5 Products Failure -- Wrong Entity Capture

**Windows -> Oculus** (company+founder)


| Metric         | Value   |
| -------------- | ------- |
| vsMax          | -2.875  |
| rkGrp          | 2       |
| flip@0         | True    |
| gap_cl         | 0.0     |
| hit            | False   |
| suppressed     | True    |
| tgt_base_rk    | 1,523   |
| ablate/amplify | 56 / 82 |


**Output**: Default "Bill Gates and Paul Allen..." -> Steered "Rift, a virtual reality headset that is very similar to..."

**Interpretation** (FAILURE -- product leakage): Source (Bill Gates) is suppressed, but instead of producing "Palmer Luckey," the output produces "Rift" -- the product name of the target entity, not the founder. The amplified features for Oculus carry strong "Oculus Rift" associations that dominate over "Palmer Luckey" associations. Luckey is far less famous than the product (baseline rank 1,523), and the company/founder supernode matching likely captures more product-identity features than founder-specific ones. This reveals a feature labeling limitation: "company" supernodes encode the company's products as strongly as (or more than) the founder.

#### F.3.6 Paintings Failure -- Source Persists

**Girl with a Pearl Earring -> Guernica** (painter+first_name)


| Metric         | Value    |
| -------------- | -------- |
| vsMax          | -2.0     |
| rkGrp          | 2        |
| flip@0         | False    |
| gap_cl         | 6.94     |
| hit            | False    |
| suppressed     | False    |
| err_src        | 15.37%   |
| tgt_base_rk    | 1,382    |
| ablate/amplify | 88 / 195 |


**Output**: Default "Johannes Vermeer..." -> Steered "(archaic character), Johannes Vermeer, was born in Delft,..."

**Interpretation** (FAILURE -- source persists despite massive intervention): 195 amplified features (among the highest in any domain) and 88 ablated features fail to dislodge Vermeer. The source answer persists in the steered output. The target (Pablo Picasso's first name "Pablo") starts at rank 1,382 -- too far to reach. The high error node rate for the source (15.37%) means much of the source circuit is invisible to the pipeline, so ablation misses critical features. Combined with the paintings domain's structural weakness (multi-step reasoning, coarse answer field), this pair has essentially zero chance of success.

#### F.3.7 Sounds Failure -- Narrow Margin

**Hiss -> Hoot** (sound+animal)


| Metric         | Value   |
| -------------- | ------- |
| vsMax          | -0.5    |
| rkGrp          | 2       |
| flip@0         | True    |
| gap_cl         | 1.33    |
| hit            | False   |
| suppressed     | True    |
| tgt_base_rk    | 5       |
| ablate/amplify | 83 / 57 |


**Output**: Default "a snake..." -> Steered "is black..."

**Interpretation** (FAILURE -- competing answer wins): Target is "brown" (owl's color) but the steered output produces "black." With the sounds dataset, the answer space is tiny (5-6 colors), so even small logit shifts change the outcome. The target (brown) is baseline rank 5, close enough to compete, but the intervention nudges it to rank 2 while "black" takes rank 1. The source (green/snake) is suppressed but generic disruption pushes toward "black" rather than "brown." This mirrors the finding that sounds has negligible labeled-vs-random specificity (vsMax gap +0.14).

### F.4 Case Grid: Metric Combinations

The following grid maps the outcome space along the two best specificity discriminators (vsMax and rkGrp) crossed with regime (flip@0) and output result (hit). Each cell contains a representative case from the studies above.

#### F.4.1 vsMax x Hit% x Regime


| vsMax Range   | flip@0=True + Hit                            | flip@0=True + No Hit         | flip@0=False + Hit          | flip@0=False + No Hit            |
| ------------- | -------------------------------------------- | ---------------------------- | --------------------------- | -------------------------------- |
| **> +10**     | CO->MI (USA, +17.5)                          | UT->IA (USA, +14.0)          | Bark->Hoot (Sounds, +13.0)  | OH->OK (USA, +13.3)              |
|               | Holden->Katniss (Books, +21.8)               | Scout->Huck (Books, +9.2)    |                             |                                  |
|               | Nike->Tesla (Products, +12.3)                |                              |                             |                                  |
| **+2 to +10** | Grande Jatte->Water Lilies (Paintings, +9.4) | Many USA pairs               | Neigh->Bark (Sounds, +12.9) |                                  |
|               | MN->FL (USA, +16.1, labeled)                 |                              |                             |                                  |
| **0 to +2**   |                                              | Gobble->Meow (Sounds, +0.0)  |                             | Hoot->Gobble (Sounds, +0.8)      |
| **< 0**       |                                              | KS->NH (USA, -6.9)           |                             | Girl->Guernica (Paintings, -2.0) |
|               |                                              | WIN->Oculus (Products, -2.9) |                             |                                  |
|               |                                              | Hiss->Hoot (Sounds, -0.5)    |                             |                                  |


**Pattern**: The upper-left quadrant (high vsMax + flip + hit) contains the genuine successes. The upper-right (high vsMax + flip + no hit) contains the rank-hit misalignment zone -- logit-level success that fails to convert to output. Regime D (no flip, no hit) concentrates in the lower-right but can appear at surprisingly high vsMax values when the trajectory recovers late.

**Note on pos0 vs best**: All vsMax values in this grid are best-over-trajectory. Position-0 vsMax values are often lower and provide sharper labeled/random discrimination (see Appendix G). For example, the Colorado->Michigan case has pos0 vsMax = +1.44 (initial_target_minus_max) vs best = +17.5. The best-over-trajectory metric captures trajectory-sustained dominance; position-0 captures the direct causal effect.

#### F.4.2 Domain x Error Node % x Outcome


| Domain        | Low Error Node (< 13%)             | High Error Node (>= 13%)             |
| ------------- | ---------------------------------- | ------------------------------------ |
| **USA**       | Hit 291, Miss 493 (hit rate 37.1%) | Hit 659, Miss 1,007 (hit rate 39.5%) |
| **Books**     | Hit 67, Miss 113 (37.2%)           | Hit 22, Miss 38 (36.7%)              |
| **Products**  | Hit 1, Miss 10 (9.1%)              | Hit 31, Miss 90 (25.6%)              |
| **Paintings** | Hit 0, Miss 9 (0.0%)               | Hit 1, Miss 80 (1.2%)                |
| **Sounds**    | Hit 4, Miss 16 (20.0%)             | Hit 2, Miss 8 (20.0%)                |


**Pattern**: Error node % does not strongly predict success within a domain. USA and Books show near-identical hit rates regardless of error node level. Products shows a surprising *reverse* pattern (higher error nodes correlate with higher hit rate), likely because the few low-error-node entities happen to be harder targets. The cross-domain gradient (USA/Books >> Products >> Paintings) dominates over within-domain error node variation.

#### F.4.3 Target Baseline Rank x Outcome


| Domain    | Hit: Median Target Baseline Rank | Miss: Median Target Baseline Rank |
| --------- | -------------------------------- | --------------------------------- |
| USA       | 106                              | 179                               |
| Books     | 379                              | 175                               |
| Products  | 178                              | 268                               |
| Paintings | 3                                | 187                               |
| Sounds    | 1                                | 2                                 |


**Pattern**: For USA, Products, and Paintings, lower baseline rank (target closer to top) predicts success. The paintings success case (rank 3) illustrates the extreme: the only hit occurs when the target is already nearly correct. Books shows the reverse -- successful hits have *higher* baseline rank (median 379 vs 175), meaning the intervention is genuinely lifting obscure targets. This is consistent with Books having the strongest vsMax gap (+6.13) and suggests the book/author circuit features carry particularly reliable causal signal.

#### F.4.4 Feature Count x Outcome


| Domain   | Hit: Median Ablate | Miss: Median Ablate | Hit: Median Amplify | Miss: Median Amplify |
| -------- | ------------------ | ------------------- | ------------------- | -------------------- |
| USA      | 48                 | 49                  | 48                  | 49                   |
| Books    | 68                 | 65                  | 63                  | 96                   |
| Products | 81                 | 76                  | 56                  | 82                   |


**Pattern**: Feature count is not predictive for USA (identical medians). For Books and Products, *fewer* amplified features correlate with success (63 vs 96 for Books, 56 vs 82 for Products), consistent with the "less is more" finding. Excessive amplification introduces noise from marginally relevant or mismatched features.

#### F.4.5 Suppression-Only Zone (Source Suppressed, No Target Hit)


| Domain    | Count | % of Total | Interpretation                                        |
| --------- | ----- | ---------- | ----------------------------------------------------- |
| USA       | 1,450 | 59.2%      | Majority outcome: source gone, target doesn't surface |
| Books     | 116   | 48.3%      | Nearly half of all pairs                              |
| Products  | 61    | 46.2%      | Similar to Books                                      |
| Paintings | 62    | 68.9%      | Dominant outcome in weakest domain                    |
| Sounds    | 20    | 66.7%      | Most cases disrupt without redirecting                |


This is the single largest outcome category in every domain. The intervention successfully suppresses the source answer but fails to install the target. This is consistent with the finding that suppression is generic (random features achieve ~80%+ suppression in most domains) while targeting requires specific features.

### F.5 Edge Cases and Anomalies

#### F.5.1 Sounds: All Successes Are No-Flip (Regime C)

All 6 hits in the sounds dataset have flip@0=False. This is unique -- in every other domain, the majority of hits have flip@0=True. The sounds domain's success cases work via late-trajectory recovery, not immediate redirection. With only 6 entities and highly shared answer tokens, the "success" pattern in sounds appears mechanistically different from other domains and should not be interpreted as evidence of the same label-quality signal.

#### F.5.2 New Hampshire: Systematic Target-Side Failure

New Hampshire appears as the target in 4 of the 5 worst-vsMax USA pairs (-6.875, -6.813, -6.125, -6.0, -5.75). Target "Concord" has baseline rank 2,480--5,816 depending on the source prompt, and only 27 features are amplified. This suggests an entity-level supernode coverage problem: either the New Hampshire graph has few concept-matching features, or the features it does have carry weak activation signals. This is a pipeline-level limitation, not a fundamental problem with the method.

#### F.5.3 Paintings: 89/90 Pairs Fail

Only 1/90 pairs achieves a hit (Grande Jatte -> Water Lilies), and that success requires baseline rank=3 (target nearly correct without steering). The paintings domain's "first_name" answer field is fundamentally coarse: "Claude," "Pablo," "Leonardo" are common tokens with many non-painting associations. The painter supernode tends to subsume the first_name supernode (since "Monet" contains information about "Claude"), making the two fields effectively identical for matching purposes. With 17% error node rates (highest of any domain), much of the circuit is invisible.

#### F.5.4 Books: Inverse Amplify-Count Effect

In Books, successful hits have median 63 amplified features vs 96 for misses. The failing pair Scout Finch -> Huckleberry Finn amplifies 176 features -- the most in the Books dataset -- yet produces garbled output. This is the clearest per-case evidence of the "less is more" effect: large supernode matches introduce noisy features that interfere with the target signal.

### F.6 Threats to Validity for Case Studies

1. **Selection bias**: Cases were selected for extremity (best/worst vsMax, edge conditions), not randomly. They illustrate the outcome space but do not represent typical performance.
2. **Tier unavailability**: The best field-add variant does not compute tier classifications (all tiers = None), so the tier dimension is not covered in this grid. Tier data is available only for the legacy fullscale_labeled run.
3. **Sounds structural issues**: 12/30 sounds pairs share the answer "brown." Any analysis involving sounds hit rates is confounded by this. The bark->hoot "success" case (F.2.5) is a mechanical artifact, not evidence of label quality.
4. **Single-example interpretations**: Each cell in the grid contains 1--3 examples. Claims about patterns (e.g., "low amplify count predicts success") are supported by aggregate distributions (F.4.4) but individual cases should not be over-interpreted.
5. **Post-hoc narrative risk**: Explanations for why specific pairs succeed or fail (e.g., "New Hampshire has too few features") are generated after observing the outcome. Without running additional experiments (e.g., testing New Hampshire with more features), these are hypotheses, not conclusions.

---

## Appendix G: Position-0 vs Best-Over-Trajectory Metrics

### G.1 Motivation

The primary targeting metrics vsMax and RkGrp are defined as the **best** value over the entire generation trajectory (typically 11 positions: the initial intervention point plus 10 generated tokens). This means a momentary spike at any position -- including late positions where the model may be in an unstable state -- counts as "success."

An alternative is to evaluate these metrics at **position 0 only**: the first token position after the intervention, before autoregressive feedback loops can compound or correct the initial effect. Position-0 metrics capture the **direct causal effect** of the feature intervention.

The swap JSON already stores both variants:

- `initial_target_minus_max` / `initial_rank_within` (position 0)
- `best_target_minus_max` / `best_rank_within` (best over trajectory)

### G.2 Position-0 Metrics Crush Random Baselines More Effectively

The labeled/random gap for vsMax > 0 and rkGrp = 1, comparing position-0 vs best-over-trajectory:

**vsMax > 0 rate:**


| Domain                | Labeled pos0 | Labeled best | Random pos0 | Random best | Gap pos0   | Gap best |
| --------------------- | ------------ | ------------ | ----------- | ----------- | ---------- | -------- |
| USA (best var.)       | 52.9%        | 91.0%        | 2.8%        | 13.1%       | **50.2pp** | 77.9pp   |
| Books (best var.)     | 92.5%        | 98.8%        | 4.6%        | 45.8%       | **87.9pp** | 52.9pp   |
| Products (best var.)  | 70.5%        | 75.0%        | 15.2%       | 51.5%       | **55.3pp** | 23.5pp   |
| Paintings (best var.) | 61.1%        | 81.1%        | 14.4%       | 47.8%       | **46.7pp** | 33.3pp   |
| Sounds (best var.)    | 50.0%        | 90.0%        | 63.3%       | 93.3%       | -13.3pp    | -3.3pp   |


**rkGrp = 1 rate:**


| Domain                | Labeled pos0 | Labeled best | Random pos0 | Random best | Gap pos0   | Gap best |
| --------------------- | ------------ | ------------ | ----------- | ----------- | ---------- | -------- |
| USA (best var.)       | 53.8%        | 91.8%        | 3.1%        | 14.3%       | **50.7pp** | 77.5pp   |
| Books (best var.)     | 92.5%        | 98.8%        | 5.8%        | 48.8%       | **86.7pp** | 50.0pp   |
| Products (best var.)  | 71.2%        | 76.5%        | 15.2%       | 52.3%       | **56.1pp** | 24.2pp   |
| Paintings (best var.) | 61.1%        | 81.1%        | 14.4%       | 47.8%       | **46.7pp** | 33.3pp   |
| Sounds (best var.)    | 50.0%        | 93.3%        | 66.7%       | 96.7%       | -16.7pp    | -3.3pp   |


**Key finding**: In Books, Products, and Paintings, position-0 metrics provide **dramatically sharper** labeled/random separation. Random controls achieve vsMax > 0 at only 5--15% at position 0, compared to 46--52% at best-over-trajectory. The trajectory-best metric inflates random success by capturing momentary spikes at late positions where the model's logit landscape is already disrupted.

**USA exception**: The best-over-trajectory gap (78pp) is larger than the pos0 gap (50pp) for USA. This reflects the fact that many labeled USA pairs need 1--3 generation steps for the target to dominate -- only 53% achieve target dominance at position 0, but 91% do so at some trajectory point. USA steering works partly through trajectory recovery, not just immediate pos0 effects.

**Sounds**: Position-0 metrics reveal that sounds has **no signal at all** -- random actually exceeds labeled at pos0 (63% vs 50%). Best-over-trajectory masks this because both conditions inflate to 90%+ over the trajectory.

### G.3 Mean vsMax: Position-0 vs Best-Over-Trajectory


| Domain        | Condition | Mean vsMax (pos0) | Mean vsMax (best) | Median vsMax (pos0) | Median vsMax (best) |
| ------------- | --------- | ----------------- | ----------------- | ------------------- | ------------------- |
| **USA**       | best var. | -0.80             | +4.00             | +0.31               | +4.05               |
|               | labeled   | -4.16             | +2.86             | -3.88               | +2.50               |
|               | random    | **-5.83**         | -2.31             | -5.25               | -2.38               |
| **Books**     | best var. | +7.29             | +7.76             | +8.09               | +8.19               |
|               | labeled   | +5.56             | +5.98             | +5.88               | +6.00               |
|               | random    | **-5.80**         | -0.25             | -4.00               | -0.12               |
| **Products**  | best var. | +2.48             | +3.06             | +2.50               | +2.62               |
|               | labeled   | +2.95             | +3.46             | +2.56               | +2.75               |
|               | random    | **-3.84**         | +0.31             | -4.00               | +0.12               |
| **Paintings** | best var. | +0.69             | +1.69             | +0.62               | +1.62               |
|               | labeled   | -0.72             | +1.55             | +0.25               | +1.16               |
|               | random    | **-6.15**         | +0.06             | -5.12               | -0.19               |
| **Sounds**    | best var. | +0.23             | +4.69             | +0.19               | +4.03               |
|               | labeled   | +0.68             | +3.28             | +0.41               | +2.86               |
|               | random    | +0.30             | +2.85             | +0.69               | +2.75               |


**Critical observation**: Random mean vsMax at position 0 is strongly negative in all non-sounds domains (-3.84 to -6.15), while random best-over-trajectory mean is near zero or slightly positive in Products (+0.31) and Paintings (+0.06). The trajectory search rescues random controls by finding momentary spikes. At position 0, random controls clearly fail to elevate the target above competitors.

**Books** is most striking: labeled pos0 mean (+7.29) vs random pos0 mean (-5.80) = gap of **13.09 logits** at position 0. The best-over-trajectory gap is only 8.01 (7.76 vs -0.25). Position-0 nearly doubles the effect size.

### G.4 Hit Rate Conditioned on Position-0 vsMax


| Domain                | Hit% when pos0 vsMax > 0 | Hit% when pos0 vsMax <= 0 | N (pos0 <= 0) |
| --------------------- | ------------------------ | ------------------------- | ------------- |
| USA (best var.)       | **47.7%**                | 28.7%                     | 1,153         |
| Books (best var.)     | **40.1%**                | 0.0%                      | 18            |
| Products (best var.)  | **34.4%**                | 0.0%                      | 39            |
| Paintings (best var.) | 1.8%                     | 0.0%                      | 35            |
| Sounds (best var.)    | 13.3%                    | 26.7%                     | 15            |


**Necessary condition**: In Books and Products, **zero hits occur when position-0 vsMax is non-positive**. If the target doesn't beat all competitors at position 0, it never recovers enough to appear in decoded output. This makes pos0 vsMax > 0 a strict necessary condition for output-level success in these domains.

**USA allows recovery**: 28.7% of USA hits occur despite pos0 vsMax <= 0. The geographic domain's steering mechanism tolerates initial failure and recovers over the trajectory, likely because geographic tokens (state names, capital names) are strongly interconnected in the model's representations.

**Sounds is inverted**: Higher hit rate at pos0 <= 0, reflecting the structural confounds (shared answers, tiny answer space) that make all sounds metrics unreliable.

### G.5 The Labeled (All Fields) vs Best Variant Split at Position 0


| Domain   | Labeled pos0 vsMax > 0 | Best variant pos0 vsMax > 0 | Labeled median pos0 vsMax | Best variant median pos0 vsMax |
| -------- | ---------------------- | --------------------------- | ------------------------- | ------------------------------ |
| USA      | 27.2%                  | **52.9%**                   | -3.88                     | **+0.31**                      |
| Books    | 90.8%                  | **92.5%**                   | +5.88                     | **+8.09**                      |
| Products | 75.0%                  | 70.5%                       | +2.56                     | +2.50                          |


For USA, the labeled (all-fields) condition has **dramatically worse** position-0 metrics: median pos0 vsMax of -3.88 vs +0.31 for the best variant. Only 27% achieve pos0 vsMax > 0 (vs 53%). This provides position-0 evidence for the "less is more" effect: input-field features cause initial disruption at position 0, and the target only recovers later in the trajectory. The best variant (mid+answer fields only) produces cleaner initial redirections.

### G.6 Implications for Metric Choice

1. **Position-0 vsMax is the stricter discriminator.** It separates labeled from random more cleanly in Books (+87.9pp gap), Products (+55.3pp), and Paintings (+46.7pp) by eliminating the trajectory-search inflation that benefits random controls.
2. **Best-over-trajectory vsMax is more inclusive for USA.** The geographic domain benefits from trajectory recovery, and the best-over-trajectory metric captures this. Using only pos0 would miss ~half of USA's genuine successes.
3. **Reporting recommendation**: Both variants should be reported. Position-0 vsMax is the more conservative and harder-to-game metric. Best-over-trajectory vsMax is more sensitive to real effects that manifest over multiple generation steps. The two together provide a more complete picture than either alone.
4. **Sounds should be excluded from cross-domain claims.** Position-0 analysis confirms that sounds has no labeled/random separation at the direct-effect level; its apparently positive best-over-trajectory metrics are artifacts of trajectory search over a tiny, confounded answer space.

---

*Report based on analysis of the full attribution-graph-probing codebase, all output data (33,387 steering runs), and research log entries through 2026-03-27.*