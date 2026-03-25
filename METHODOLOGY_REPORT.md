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
| Parameter | Default | Role |
|-----------|---------|------|
| `nodeThreshold` | 0.8 | Minimum node influence for inclusion |
| `edgeThreshold` | 0.85 | Minimum edge weight for inclusion |
| `maxFeatureNodes` | 5000 | Upper bound on graph size |

**Output**: Graph JSON with nodes (features, embeddings, logits), edges (attribution weights), and metadata.

**Static metrics per node**: `node_influence` (marginal influence), `cumulative_influence` (pruning coverage), `frac_external_raw` (1 - self-loop weight / total incoming weight).

**Feature selection**: A cumulative influence threshold (tau, typically 0.95 for batch experiments) selects the feature universe for probing.

**Assumption**: The replacement model (which freezes attention during graph computation) faithfully represents the computations of interest. The downstream swap interventions use `freeze_attention: false`, so the model's attention adapts freely. Positive results under these conditions are stronger evidence than under frozen attention, where direct feature-feature effects are partly forced by construction (Ameisen et al., 2025, "Nuances of Steering with Cross-Layer Features").

### 2.2 Probe Prompt Generation and Activation Measurement

**Goal**: Produce a cross-prompt activation signature (CPAS) for each feature.

**Probe generation**: An instructed LLM (Claude-3.5-Sonnet, temperature 0.7) generates probe prompts designed to elicit activations that disambiguate each feature's circuit role. Probes reuse tokens and syntactic structure of the seed prompt. In batch mode, probes are loaded from shared template files with systematic concept coverage (entity, attribute, relationship categories) and are manually reviewed.

**Activation measurement**: For each (feature, probe) pair, activations are measured via Neuronpedia API or local GPU inference. The subset of aggregated metrics driving classification:

| Metric | Definition | Used in rule |
|--------|------------|-------------|
| `peak_consistency_main` | Fraction of probes where the most frequent peak token is the actual peak | Dictionary (>= 0.80) |
| `n_distinct_peaks` | Count of distinct tokens serving as peak across probes | Dictionary (<= 1) |
| `conf_F` / `share_F` | Fraction of active probes where peak is on a functional token | Say-X (>= 0.90) |
| `func_vs_sem_pct` | 100 * (max_functional_act - max_semantic_act) / max_overall | Say-X (>= 50), Semantic (< 50) |
| `sparsity_median` | Median sparsity ratio across active probes | Relationship (< 0.45) |
| `conf_S` | 1 - share_F (semantic confidence) | Semantic Concept (>= 0.50) |
| `layer` | Feature's layer in the CLT | Say-X (>= 7), Semantic (<=3) |

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

| Dataset | Seed Prompt Template | Concept Fields | N Seeds | N Swap Pairs |
|---------|---------------------|----------------|---------|--------------|
| USA States | "The capital of the state containing {city} is" | state, capital | 50 | 2,450 |
| Book Characters/Authors | "The book featuring {character} was written by" | book, author | 16 | 240 |
| Products/Founders | "The company that makes {product} was founded by" | company, founder | 12 | 132 |
| Paintings/Painters | "The first name of the painter of {painting} is" | painting, first_name | 10 | 90 |
| Sounds/Colors | "The most common color of the animal that goes '{sound}' is" | animal, color | 6 | 30 |

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

| Metric | Definition | Why it matters |
|--------|------------|---------------|
| **Hit%** | Target answer appears in steered output | Direct success measure. Zero for random controls in strong domains. |
| **vsMax** | best(target_logit - max(other_dataset_answers)) over trajectory | Positive = target beats all same-domain alternatives. The cleanest cross-domain specificity discriminator. |
| **Target recovery rate** | Does target logit exceed its own unsteered baseline at any trajectory position? | Separates "the model's circuits responded to the target concept" from "everything got disrupted." 92% labeled vs 29% random in regime C (USA). |

**Supporting metrics** (used for deeper analysis):

| Metric | Definition |
|--------|------------|
| Sup% | Source answer absent from steered output |
| TgtRk / MedRk | Mean and median best target rank during generation |
| vsTopK | best(target_logit - mean(top-3 other answers)) |
| RkGrp | Best rank within full answer group (1 = top) |
| Flip% | Fraction achieving target > source rank crossover |
| CtrlS | Mean absolute logit shift of control tokens (the, is, a, of) |

---

## 4. Results

### 4.1 Labeled vs Random: Specificity Established

Across 33,387 steering runs, labeled supernodes outperform structurally matched random controls on targeting metrics in 4 of 5 domains, while random controls often achieve equal or higher suppression through generic disruption.

**Headline comparison** (full labeled, all concept fields):

| Domain | Cond | N | Hit% | Sup% | vsMax | RkGrp | MedRk |
|--------|------|---|------|------|-------|-------|-------|
| **USA States** | **labeled** | **2,450** | **24.7%** | **92.8%** | **+2.86** | **1.72** | **5** |
| | random | 7,350 | 0.1% | 83.4% | -2.31 | 9.00 | 566 |
| **Books** | **labeled** | **240** | **3.8%** | **69.2%** | **+5.98** | **1.03** | **17** |
| | random | 720 | 0.3% | 75.0% | -0.15 | 2.43 | 283 |
| **Products** | **labeled** | **132** | **15.2%** | **65.2%** | **+3.46** | **1.20** | **26** |
| | random | 396 | 0.3% | 87.1% | +0.23 | 2.25 | 354 |
| **Paintings** | **labeled** | **90** | **4.4%** | **34.4%** | **+1.55** | **1.31** | **66** |
| | random | 270 | 0.0% | 74.1% | -0.03 | 1.96 | 196 |
| **Sounds** | **labeled** | **30** | **0.0%** | **100%** | **+3.28** | **1.00** | **20** |
| | random | 90 | 12.2% | 80.0% | +3.14 | 1.08 | 24 |

**Key finding: suppression is generic, targeting is specific.** Random controls achieve higher suppression than labeled in 3 of 5 domains (books 75% vs 69%, products 87% vs 65%, paintings 74% vs 34%). Ablating random features is broadly disruptive. But only labeled supernodes steer toward the correct target -- random hit rates are near-zero in all strong domains, and vsMax is negative or near-zero (target fails to beat same-domain alternatives).

### 4.2 Field Additivity: The "Less is More" Effect

Each domain's concept fields map to semantic roles: **input** (mentioned in prompt), **intermediate** (bridging concept), **answer** (what the model produces). The field-additivity experiment reveals that including input-field supernodes degrades steering performance, often dramatically.

In 4 of 5 domains, a 2-field or 1-field subset outperforms the full 3-field labeled intervention:

| Domain | Best subset | Hit% | Full 3-field Hit% | Delta |
|--------|-------------|------|--------------------|-------|
| USA States | state+capital (mid+ans) | **38.8%** | 24.7% | +14.1pp |
| Books | book+author (mid+ans) | **37.1%** | 3.8% | +33.3pp |
| Products | company+founder (mid+ans) | **24.2%** | 15.2% | +9.0pp |
| Sounds | sound+animal (in+mid) | **20.0%** | 0.0% | +20.0pp |
| Paintings | first_name alone (ans) | **6.7%** | 3.3% | +3.4pp |

The optimal subset is consistently **intermediate+answer** for the three strongest domains. Single-field averages across all domains confirm the pattern:

| Role | Hit% | Sup% | MedRk | vsMax | RkGrp |
|------|------|------|-------|-------|-------|
| Input | 6.1% | 63.2% | 106 | +1.90 | 2.55 |
| Intermediate | 14.6% | 79.1% | 43 | +3.37 | 1.56 |
| Answer | 8.8% | 89.5% | 36 | +2.39 | 1.75 |

**Interpretation**: Input-field supernodes encode the concept the model *reads* in the prompt, not the concept it needs to *produce*. Including them in the intervention activates competing circuits that dilute or interfere with the answer signal. The model's internal representation of the prompt input is better left undisturbed during steering.

### 4.3 Best Field-Add Variant vs Random (Primary Result)

The cleanest test of label correctness compares the best field-add variant (intermediate+answer) against structurally matched random controls. This removes the noise from input-field features while preserving the full specificity comparison.

| Domain | Condition | N | Hit% | vsMax | MedRk | RkGrp |
|--------|-----------|---|------|-------|-------|-------|
| **USA** | **best (state+capital)** | **2,450** | **38.8%** | **+4.00** | **3** | **1.47** |
| | full labeled | 2,450 | 24.7% | +2.86 | 5 | 1.72 |
| | random | 7,350 | 0.1% | -2.31 | 566 | 9.00 |
| **Books** | **best (book+author)** | **240** | **37.1%** | **+7.76** | **2** | **1.02** |
| | full labeled | 240 | 3.8% | +5.98 | 17 | 1.03 |
| | random | 720 | 0.3% | -0.15 | 283 | 2.43 |
| **Products** | **best (company+founder)** | **132** | **24.2%** | **+3.06** | **18** | **1.27** |
| | full labeled | 132 | 15.2% | +3.47 | 26 | 1.20 |
| | random | 396 | 0.3% | +0.23 | 354 | 2.25 |
| **Paintings** | **best (first_name)** | **90** | **6.7%** | **+1.46** | **90** | **1.41** |
| | full labeled | 90 | 3.3% | +1.55 | 66 | 1.32 |
| | random | 270 | 0.0% | -0.03 | 196 | 1.96 |
| **Sounds** | **best (sound+animal)** | **30** | **20.0%** | **+4.69** | **5** | **1.07** |
| | full labeled | 30 | 0.0% | +3.40 | 20 | 1.00 |
| | random | 90 | 12.2% | +3.14 | 24 | 1.08 |

**The best variant vs random gap** on the three primary metrics:

| Domain | Hit%: best / random | vsMax: best / random | Recovery: best / random |
|--------|---------------------|----------------------|-------------------------|
| USA | 38.8% / 0.1% | +4.00 / -2.31 | 93% / 29% |
| Books | 37.1% / 0.3% | +7.76 / -0.15 | 96% / 89% |
| Products | 24.2% / 0.3% | +3.06 / +0.23 | 86% / 83% |
| Paintings | 6.7% / 0.0% | +1.46 / -0.03 | 89% / 77% |
| Sounds | 20.0% / 12.2% | +4.69 / +3.14 | n/a |

Target recovery rates are from regime C (both tokens disrupted, target overtakes source), which is the dominant labeled behavior. The separation is sharpest for USA (93% vs 29%) and weakens across the domain gradient.

### 4.4 Logit-Shift Regime Taxonomy

Binary hit/miss evaluation obscures a rich structure in the logit trajectories. Classifying every swap by what happens to target and source logits at position 0 reveals four regimes:

| Regime | Target logit | Source logit | Flip? | Intuition |
|--------|-------------|-------------|-------|-----------|
| **A** | UP | DOWN | yes | Clean redirection: target gains, source loses |
| **C** | DOWN | DOWN | yes | Both disrupted, target less so (differential disruption) |
| **D** | DOWN | DOWN | no | Both disrupted, source still dominant (generic disruption) |
| **E** | FLAT | DOWN | yes | Pure suppression, no target lift |

**The best field-add variant shifts cases from weak regimes to strong ones.** Regime A (cleanest label evidence) prevalence for best variant vs full labeled vs random:

| Dataset | Best variant | Full labeled | Random |
|---------|-------------|-------------|--------|
| USA | **34.9%** | 8.9% | 19.4% |
| Books | **62.1%** | 38.8% | 40.8% |
| Products | **62.1%** | 56.8% | 51.5% |
| Paintings | **47.8%** | 17.8% | 23.3% |

Simultaneously, regime D (generic disruption, weakest evidence) nearly vanishes for the best variant:

| Dataset | Best variant | Full labeled | Random |
|---------|-------------|-------------|--------|
| USA | **9.1%** | 19.4% | 45.3% |
| Books | **3.3%** | 3.3% | 34.6% |
| Products | **2.3%** | 2.3% | 22.0% |
| Paintings | **2.2%** | 6.7% | 42.2% |

Random controls concentrate in regime D (42--45%), while the best variant concentrates in regime A. Removing input-field features eliminates generic disruption and produces more surgical interventions.

**Within regime C** (both disrupted, target overtakes), labeled and random diverge sharply on three signals:

| Signal | Labeled (USA) | Random (USA) |
|--------|---------------|--------------|
| Target recovery rate | 92.2% | 29.3% |
| Sustained dominance (tgt_win_pct) | 0.673 | 0.319 |
| vsMax | +2.33 | -0.10 |
| Hit% | 22.5% | 0.6% |

These three sub-regime signals (target recovery, sustained dominance, vsMax) are the most discriminating evidence that labeled features capture genuine circuit structure rather than producing generic disruption.

### 4.5 Domain Gradient

The specificity gap between labeled and random follows a consistent domain gradient:

| Domain | vsMax gap (labeled - random) | Interpretation |
|--------|------------------------------|----------------|
| Books | +6.13 | Strong |
| USA States | +5.17 | Strong |
| Products | +3.23 | Moderate |
| Paintings | +1.58 | Weak |
| Sounds | +0.14 | Negligible |

The gradient does not track graph size (weaker domains have *more* features and supernodes) but correlates with:
- **CLT error node density**: USA ~10% error influence vs paintings/products ~15%
- **Answer-field specificity**: "capital" and "author" are highly specific; "first_name" and "color" are coarse
- **Circuit complexity**: Geographic capitals are single-hop factual lookups; painting attribution requires multi-step reasoning
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

| Experiment | Priority | Status |
|-----------|----------|--------|
| Token overlap stratification | HIGH | Infrastructure exists, not run |
| Intervention multiplier sweep | MEDIUM | Not run |
| Ablation-only vs amplification-only decomposition | MEDIUM | Partially addressed by field additivity |
| Threshold sensitivity analysis | MEDIUM | Not run |
| Cross-domain supernode transfer | MEDIUM | Not run |
| Probe prompt sensitivity | LOW | Not run |
| Attention-aware validation | LOW | Requires infrastructure changes |

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

| Symbol | Definition |
|--------|------------|
| CLT | Cross-Layer Transcoder (reads residual stream, writes to downstream MLP layers) |
| CPAS | Cross-Prompt Activation Signature |
| tau | Cumulative influence threshold for feature selection |
| M_ablate | Multiplication factor for source features during intervention (default: -2) |
| M_amplify | Multiplication factor for target features during intervention (default: 20) |
| vsMax | best(target_logit - max(other_dataset_answers)) over trajectory |
| RkGrp | Best rank of target within all dataset answer tokens (1 = top) |
| Target recovery | Target logit exceeds its own unsteered baseline at any trajectory position |
| Regime A | Target logit UP, source logit DOWN, flip at position 0 |
| Regime C | Both logits DOWN, flip at position 0 (differential disruption) |
| Regime D | Both logits DOWN, no flip (generic disruption) |
| Tier | Domain-specific ordinal quality score for swap outcomes (0--5 for USA states) |

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

| Domain | Cond | N | Hit% | Sup% | GapCl | TgtRk | MedRk | vsMax | vsTopK | RkGrp | Flip% |
|--------|------|---|------|------|-------|-------|-------|-------|--------|-------|-------|
| USA States | labeled | 2,450 | 24.7% | 92.8% | 4.67 | 74.6 | 5 | +2.86 | +3.76 | 1.72 | 98.2% |
| | random | 7,350 | 0.1% | 83.4% | 2.43 | 1,836 | 566 | -2.31 | -1.65 | 9.00 | 69.2% |
| Books | labeled | 240 | 3.8% | 69.2% | 0.01 | 44.7 | 18 | +5.98 | +7.40 | 1.03 | 96.7% |
| | random | 720 | 0.3% | 75.0% | 3.39 | 1,608 | 283 | -0.15 | +0.76 | 2.43 | 79.6% |
| Products | labeled | 132 | 15.2% | 65.2% | 0.19 | 67.0 | 26 | +3.46 | +5.11 | 1.20 | 97.0% |
| | random | 396 | 0.3% | 87.1% | 1.70 | 1,547 | 354 | +0.23 | +1.21 | 2.25 | 75.3% |
| Paintings | labeled | 90 | 4.4% | 34.4% | 0.80 | 587.7 | 70 | +1.55 | +3.01 | 1.31 | 97.8% |
| | random | 270 | 0.0% | 74.1% | 3.49 | 1,187 | 196 | -0.03 | +1.26 | 1.96 | 88.9% |
| Sounds | labeled | 30 | 0.0% | 100% | 1.46 | 42.5 | 21 | +3.28 | +3.53 | 1.00 | 60.0% |
| | random | 90 | 12.2% | 80.0% | 2.29 | 133 | 24 | +3.14 | +3.72 | 1.08 | 53.3% |

**Specificity discriminators summary**:

| Domain | Labeled vsMax | Random vsMax | Gap | Strength |
|--------|---------------|--------------|-----|----------|
| Books | +5.98 | -0.15 | 6.13 | Strong |
| USA States | +2.86 | -2.31 | 5.17 | Strong |
| Products | +3.46 | +0.23 | 3.23 | Moderate |
| Paintings | +1.55 | -0.03 | 1.58 | Weak |
| Sounds | +3.28 | +3.14 | 0.14 | Negligible |

---

## Appendix B: Field-Based Additivity Detail Tables

### B.1 USA States (2,450 non-identity pairs per variant)

| Fields | Role | Hit% | Sup% | GapCl | MedRk | vsMax | vsTopK | RkGrp |
|--------|------|------|------|-------|-------|-------|--------|-------|
| city | input | 2.9% | 68.4% | 3.56 | 190 | -1.26 | -0.49 | 6.92 |
| state | intermediate | 17.0% | 83.3% | 4.38 | 14 | +2.38 | +3.33 | 2.72 |
| capital | answer | 14.2% | 95.6% | 2.23 | 11 | +0.63 | +1.33 | 3.69 |
| **state+capital** | **mid+ans** | **38.8%** | **98.0%** | **3.74** | **3** | **+4.00** | **+4.86** | **1.47** |
| state+city | mid+in | 11.1% | 82.7% | 4.88 | 28 | +1.71 | +2.56 | 2.31 |
| capital+city | ans+in | 10.2% | 91.2% | 3.35 | 30 | +0.58 | +1.40 | 4.16 |
| all 3 (labeled) | all | 24.7% | 92.8% | 4.67 | 5 | +2.86 | +3.76 | 1.72 |

### B.2 Books (240 non-identity pairs per variant)

| Fields | Role | Hit% | Sup% | GapCl | MedRk | vsMax | vsTopK | RkGrp |
|--------|------|------|------|-------|-------|-------|--------|-------|
| character | input | 4.2% | 67.9% | 1.46 | 125 | +1.87 | +3.18 | 1.77 |
| book | intermediate | 37.1% | 83.3% | 0.24 | 2 | +6.69 | +8.25 | 1.20 |
| author | answer | 14.6% | 92.1% | 0.20 | 12 | +4.71 | +6.61 | 1.33 |
| **book+author** | **mid+ans** | **37.1%** | **84.6%** | **0.04** | **2** | **+7.76** | **+9.58** | **1.02** |
| character+book | in+mid | 5.0% | 77.5% | 0.15 | 24 | +5.22 | +6.71 | 1.23 |
| character+author | in+ans | 3.8% | 75.0% | 0.21 | 76 | +3.45 | +4.73 | 1.30 |
| all 3 (labeled) | all | 3.8% | 69.6% | 0.02 | 17 | +5.97 | +7.39 | 1.03 |

Adding character supernodes degrades from 37.1% to 3.8% hit -- a dramatic interference effect.

### B.3 Products (132 non-identity pairs per variant)

| Fields | Role | Hit% | Sup% | GapCl | MedRk | vsMax | vsTopK | RkGrp |
|--------|------|------|------|-------|-------|-------|--------|-------|
| product | input | 0.0% | 62.1% | 0.20 | 137 | +1.90 | +3.46 | 1.61 |
| company | intermediate | 5.3% | 71.2% | 0.26 | 128 | +2.62 | +4.39 | 1.39 |
| founder | answer | 8.3% | 84.1% | 0.51 | 18 | +2.08 | +3.07 | 1.27 |
| **company+founder** | **mid+ans** | **24.2%** | **68.9%** | **0.35** | **18** | **+3.06** | **+4.48** | **1.27** |
| product+company | in+mid | 1.5% | 68.2% | 0.15 | 93 | +2.78 | +4.92 | 1.31 |
| product+founder | in+ans | 2.3% | 66.7% | 0.05 | 48 | +2.54 | +4.01 | 1.23 |
| all 3 (labeled) | all | 15.2% | 63.6% | 0.19 | 26 | +3.47 | +5.10 | 1.20 |

### B.4 Paintings (90 non-identity pairs per variant)

| Fields | Role | Hit% | Sup% | GapCl | MedRk | vsMax | vsTopK | RkGrp |
|--------|------|------|------|-------|-------|-------|--------|-------|
| painting | input | 3.3% | 34.4% | 0.71 | 71 | +1.50 | +2.72 | 1.44 |
| painter | intermediate | 1.1% | 70.0% | 0.45 | 66 | +1.68 | +2.76 | 1.30 |
| first_name | answer | 6.7% | 75.6% | 0.79 | 90 | +1.46 | +2.72 | 1.41 |
| painter+first_name | mid+ans | 1.1% | 70.0% | 0.49 | 65 | +1.69 | +2.78 | 1.30 |
| all 3 (labeled) | all | 3.3% | 33.3% | 0.84 | 66 | +1.55 | +2.99 | 1.32 |

Painter name subsumes first name in supernode matching, making painter and painter+first_name effectively identical. Weak steering across all variants.

### B.5 Sounds (30 non-identity pairs per variant)

| Fields | Role | Hit% | Sup% | GapCl | MedRk | vsMax | vsTopK | RkGrp |
|--------|------|------|------|-------|-------|-------|--------|-------|
| sound | input | 20.0% | 83.3% | 2.75 | 5 | +5.49 | +5.91 | 1.00 |
| animal | intermediate | 12.5% | 87.5% | 1.61 | 6 | +3.49 | +4.07 | 1.21 |
| color | answer | 0.0% | 100% | 1.51 | 48 | +3.09 | +3.68 | 1.07 |
| **sound+animal** | **in+mid** | **20.0%** | **70.0%** | **1.15** | **5** | **+4.69** | **+4.99** | **1.07** |
| all 3 (labeled) | all | 0.0% | 96.7% | 1.50 | 20 | +3.40 | +3.66 | 1.00 |

Sounds is the exception to the intermediate+answer pattern: the input field (sound name) carries the strongest signal.

---

## Appendix C: Why Gap Closure Was De-Emphasized

Gap closure (`max(gap_trajectory) - gap_trajectory[0]`) was initially used as a primary metric. Analysis across logit-shift regimes reveals it is regime-dependent and often misleading:

| Regime | Labeled GapCl (USA) | Random GapCl (USA) | Labeled vsMax | Random vsMax |
|--------|--------------------|--------------------|---------------|--------------|
| A (tgt UP, src DOWN) | 0.88 | 0.76 | +4.28 | -0.19 |
| C (both DOWN, flip) | 2.73 | 1.59 | +2.33 | -0.10 |
| D (both DOWN, no flip) | **13.62** | **6.46** | +4.11 | -0.07 |

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

| Tier | Name | Criterion |
|------|------|-----------|
| 5 | PERFECT | Target capital appears in output |
| 4 | TARGET_STATE_CITY | Other city in target state (not capital) |
| 3 | TARGET_STATE_ONLY | Target state mentioned, no valid city |
| 2 | SUPPRESSED_ONLY | Source suppressed, garbled or non-geographic output |
| 1 | SOURCE_PERSISTS | Source capital/city still in output |
| 0 | WRONG_STATE | City from a third state |

### Non-USA Domains (simplified evaluation)

Tier 5 (PERFECT): target answer detected via full-answer match, first-token substring match, or any word (len >= 3) of the target answer appearing in output. Tier 2 (SUPPRESSED): source absent, no target signal. Tier 1 (SOURCE_PERSISTS): source answer remains. Tiers 3--4 exist only for USA states.

**Cross-domain comparability warning**: T5 rates for non-USA domains are more generous due to word-level matching. Strict exact match rates (target answer as a whole in output): USA 38.8%, Books 36.7%, Products 24.2%, Sounds 3.3%, Paintings 1.1%.

---

*Report based on analysis of the full attribution-graph-probing codebase, all output data (33,387 steering runs), and research log entries through 2026-03-25.*
