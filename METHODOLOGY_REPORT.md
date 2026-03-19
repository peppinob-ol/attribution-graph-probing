# Methodology Report: Automated Circuit Interpretation via Probe Prompting

**Date**: 2026-03-19 (revised)
**Scope**: Full pipeline analysis -- from probe generation through feature swapping and trajectory analysis
**Epistemic framing**: Claims, evidence, and reasoning are separated throughout. Three levels of interpretive claim are distinguished: (i) operationally useful labels, (ii) downstream causal effects, and (iii) full mechanistic explanation. Recommendations for control experiments are in Section 7.

---

## 1. Problem Statement and Research Context

### 1.1 The Interpretation Bottleneck

Attribution graphs (Ameisen et al., 2025) represent causal pathways from input embeddings through cross-layer transcoder (CLT) features to output logits. These graphs typically contain hundreds to thousands of feature nodes. Manual interpretation -- inspecting activation patterns across corpus examples to assign semantic labels -- is reported to require approximately 2 hours per prompt by an experienced analyst.

**Claim**: Probe prompting can automate this first-pass analysis, reducing the time to 10--20 minutes of semi-automated processing per circuit.

**Evidence**: The pipeline generates interpretable supernode groupings across 5+ prompt families (geographic capitals, sports entities, semantic opposition, anatomy, book/author, product/founder, painting/painter, sound/color domains). Processing time is documented at 2--5 minutes for graphs with 50--200 features.

**Reasoning**: The speedup is achieved by replacing open-ended corpus inspection with a structured protocol: LLM-generated probe prompts that systematically vary semantic content while preserving syntactic structure. This trades open-ended exploration for targeted behavioral measurement, which may miss unexpected feature roles not captured by the probe set.

### 1.2 Three Levels of Interpretive Claim

Recent work (Geiger et al., 2025, "Causality is Key for Interpretability Claims to Generalise") argues that interpretability claims must be formulated in the language of intervention, estimand, and causal generalization -- not as direct ontological identification of latent variables. This report adopts that framing by distinguishing three levels:

1. **Operationally useful labels**: The pipeline produces supernode names and categories that are behaviorally grounded and useful for navigating circuits. This is the weakest claim and the most defensible.
2. **Downstream causal effects**: The labeled supernodes, when manipulated, produce entity-specific changes in model output. This is a stronger claim requiring specificity controls.
3. **Full mechanistic explanation**: The labels correctly describe the computational role of features in the model's internal algorithm. This is the strongest claim and is NOT made by this work.

The work's defensible position is primarily at level (1) with substantial evidence for level (2), pending specificity controls. Level (3) remains an open problem for the field.

### 1.3 What This System Does (and Does Not Do)

The system operates *downstream* of circuit tracing. It does not:
- Propose a new attribution method
- Model attention (QK) circuits
- Resolve polysemantic features
- Handle multi-token concepts natively
- Claim to identify ground-truth computational mechanisms

It does:
- Measure feature behavior under controlled semantic variation
- Classify features into functional roles using transparent rules
- Group features into operationally labeled supernodes
- Test supernode causal relevance via feature swapping with entity-specific outcome tracking
- Track continuous logit trajectories as a secondary evaluation metric

---

## 2. Pipeline Specification

### 2.1 Stage 0: Attribution Graph Generation

**Input**: A seed prompt and target logit (e.g., "The capital of Texas is" -> " Austin").

**Process**: Neuronpedia API generates an attribution graph using a local replacement model over CLT features (Gemma-2-2B, `clt-hp` source set). The replacement model freezes attention patterns and layer norms, linearizing the residual stream through CLT features.

**Parameters**:
| Parameter | Default | Role |
|-----------|---------|------|
| `nodeThreshold` | 0.8 | Minimum node influence for inclusion |
| `edgeThreshold` | 0.85 | Minimum edge weight for inclusion |
| `maxFeatureNodes` | 5000 | Upper bound on graph size |

**Output**: Graph JSON with nodes (features, embeddings, logits), edges (attribution weights), and metadata.

**Static metrics extracted per node**:
- `node_influence`: marginal influence (difference between consecutive cumulative influences, sorted)
- `cumulative_influence`: pruning coverage
- `frac_external_raw`: 1 - (self-loop weight / total incoming weight)

**Feature selection**: A cumulative influence threshold (tau = 0.60--0.95, typically 0.95 for batch experiments) selects the universe of features for probing. This determines the features that enter Stage 1.

**Assumption**: The replacement model (which freezes attention during graph computation) faithfully represents the computations of interest. This is standard in the field but may underestimate indirect effects mediated by attention pattern changes. Notably, while graph generation uses frozen attention, the downstream feature swap interventions (Stage 3) do NOT freeze attention (`freeze_attention: false` in all configs), creating an asymmetry between the model used for feature identification and the model used for feature testing.

### 2.2 Stage 1: Probe Prompt Generation and Activation Measurement

**Goal**: Produce a cross-prompt activation signature (CPAS) for each feature, characterizing its behavioral response to controlled semantic variation.

**Probe generation**: An instructed LLM (Claude-3.5-Sonnet, temperature 0.7) generates 5--10 concept-targeted probe prompts per concept. Prompts are designed to preserve the syntactic frame of the seed while varying entity content (e.g., "The capital of Texas is" -> "The capital of California is"). Probes are manually reviewed for quality (rejecting duplicates and malformed prompts) or loaded from shared template files in batch mode.

**Activation measurement**: For each (feature, probe) pair, activations are measured via Neuronpedia API (or local GPU inference in batch mode). The following per-pair metrics are recorded:

| Metric | Definition | Purpose |
|--------|------------|---------|
| `peak_token` | Token with highest activation | Identifies what the feature "detects" |
| `peak_position` | Index of peak activation | Localization |
| `cosine_similarity` | Cosine between probe and seed activation patterns | Cross-prompt stability |
| `z_score_robust` | IQR-based anomaly score: `0.741 * (max - median) / max(IQR, 1e-3)` | Activation significance |
| `density_attivazione` | Fraction of tokens above 90th percentile | Diffuseness |
| `sparsity_ratio` | `(peak - mean) / peak` | Concentration |
| `picco_su_label` | Boolean: peak inside label span | Label relevance |
| `normalized_sum_label` | Label span sum / label length | Normalized activation intensity |
| `percentile_in_sequence` | Percentile rank of label max in full sequence | Relative prominence |

**Aggregation across probes** (per feature):
| Metric | Definition |
|--------|------------|
| `peak_consistency_main` | Fraction of probes where the most frequent peak token is the actual peak |
| `n_distinct_peaks` | Count of distinct tokens serving as peak across probes |
| `share_F` / `conf_F` | Fraction of active probes where peak is on a functional token |
| `conf_S` | 1 - share_F (semantic confidence) |
| `func_vs_sem_pct` | 100 * (max_functional_act - max_semantic_act) / max_overall |
| `sparsity_median` | Median sparsity ratio across active probes |
| `K_sem_distinct` | Number of distinct semantic tokens serving as peak |

**Cross-prompt stability**: Features must satisfy classification conditions on >= 60% of probes to be grouped; those failing are marked "ungrouped" (typically 5--10%).

### 2.3 Stage 2: Feature Classification and Supernode Construction

**Token preprocessing**: Each token in each probe is labeled as *functional* (syntactic bridging: "is", "the", "of", etc.) or *semantic* (content-bearing: entity names, concepts). A configurable vocabulary of ~30 English functional tokens is provided. When a feature peaks on a functional token, a directional search within a 7-token window identifies the nearest semantic *target token* (e.g., "is" -> look forward; "of" -> look backward).

**Decision tree (V4)**:
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

**Conflict resolution**: When a feature satisfies multiple conditions, a weighted alignment score determines assignment: peak consistency (40%), category-specific confidence (30%), layer prior (20%), sparsity consistency (10%).

**Naming**:
- Semantic nodes: strongest semantic peak token (e.g., "Texas")
- Say-X nodes: target token from functional peak mapping (e.g., "Say (Austin)")
- Relationship nodes: aggregated activation pattern (e.g., "(capital) related")

**Supernode formation**: Features sharing the same classification and name are grouped into supernodes. Duplicate prevention ensures each feature belongs to exactly one supernode.

### 2.4 Stage 3: Causal Testing via Feature Swapping

**Goal**: Test whether the labeled supernodes have entity-specific causal influence on model output by ablating source features and amplifying target features between entity-matched prompts.

**Intervention mechanism**: Additive delta injection via CLT decoder vectors. For each intervened feature, the code computes `new_value = M * original_activation`, then scales the feature's CLT decoder vectors by `new_value` and adds these scaled vectors to the residual stream at all downstream layers in a single forward pass. This is **not** constrained patching (MLP output clamping) and does **not** use frozen attention patterns (`freeze_attention: false` in all configs). The model's attention patterns are free to adapt to the intervention, meaning effects are not "guaranteed" by the linear structure of the replacement model -- the model can in principle route around the perturbation via attention changes. This makes positive results *more* evidentially valuable than they would be under frozen attention, where direct feature-feature effects are partly forced by construction (Ameisen et al., 2025, Appendix: "Nuances of Steering with Cross-Layer Features").

**Intervention multipliers**: The default values (M_ablate = -2, M_amplify = 20) follow Anthropic's empirically calibrated practice. Ameisen et al. (2025, "Unexplained Variance and Choice of Steering Factors") document three structural reasons why overcompensation is required: (i) unexplained variance in finite CLT dictionaries, (ii) inexhaustive feature selection within supernodes, and (iii) incomplete capture of cross-layer effects. The asymmetry reflects different operational requirements: ablation reverses and doubles (strong enough to suppress but not so extreme as to create artifacts), while amplification must overcome the model's prior probability distribution for the target entity, which was not originally activated. Despite this justification, an ablation-only vs. amplification-only decomposition and a multiplier sweep remain valuable controls (see Section 7.4, 7.5).

**Protocol**: For a swap from entity A to entity B on the same seed prompt template:
1. Identify supernodes associated with entity A's concepts (e.g., state: "Texas", capital: "Austin")
2. Identify supernodes associated with entity B's concepts (e.g., state: "Georgia", capital: "Atlanta")
3. For each feature in A's supernodes: multiply activation by M_ablate (default: -2)
4. For each feature in B's supernodes: multiply activation by M_amplify (default: 20)
5. Run the model with these additive delta interventions and record the generated output

**Concept matching**: The swap_loader resolves concept fields (e.g., `[state, capital]`) from the YAML config and maps them to supernodes via string matching. Multi-token concepts are handled by splitting on spaces and matching words of length >= 3.

**Evaluation metrics** (per swap):
- `exact_match`: target answer appears in steered output
- `suppression`: source answer absent from steered output
- `first_token_matches_target`: first generated token is a substring of target
- `fuzzy_match`: normalized exact match (punctuation-insensitive)
- `topk_presence`: target/source presence in top-k probabilities

### 2.5 Tier Classification (Domain-Specific: USA States)

A rule-based classifier assigns each swap result to a tier (0--5):

| Tier | Name | Criterion |
|------|------|-----------|
| 5 | PERFECT | Target capital appears in output |
| 4 | TARGET_STATE_CITY | Other city in target state (not capital) |
| 3 | TARGET_STATE_ONLY | Target state mentioned, no valid city |
| 2 | SUPPRESSED_ONLY | Source suppressed, garbled or non-geographic output |
| 1 | SOURCE_PERSISTS | Source capital/city still in output |
| 0 | WRONG_STATE | City from a third state |

This classifier uses curated geographic data (US cities, capitals, counties, regions, landmarks, islands, ambiguous cities, foreign places) and handles confidence scoring for ambiguous cases. An optional LLM fallback is available for low-confidence classifications.

**Important note**: This tier system is domain-specific (designed for USA state capitals) and cannot be directly applied to other domains (books, paintings, etc.) without analogous domain knowledge bases.

### 2.6 Trajectory Analysis

**Motivation**: Exact-match evaluation (does the target token appear in the output?) is binary and cannot distinguish near-misses from complete failures. Trajectory analysis provides a continuous metric.

**Method** (`extract_logit_trajectory`):

At each generation step `t` after the prompt, record:
- `target_logit[t]`, `target_prob[t]`, `target_rank[t]` -- for the desired output token
- `source_logit[t]`, `source_prob[t]`, `source_rank[t]` -- for the original output token
- `control_logit[t]` for control tokens ("the", "is", "a", "of") -- for specificity

**Derived metrics**:
| Metric | Definition |
|--------|------------|
| `gap_trajectory[t]` | `target_logit[t] - source_logit[t]` |
| `flip_position` | First step `t` where `target_rank[t] < source_rank[t]` |
| `initial_gap` | `gap_trajectory[0]` |
| `best_gap` | `max(gap_trajectory)` |
| `gap_closure` | `best_gap - initial_gap` |
| `control_stability` | Mean absolute logit change of control tokens from position 0 |

**Rationale**: A flip at position 0 or 1 indicates that the intervention successfully redirected the model's first-token prediction toward the target. Even without achieving top-1, upward trajectory in target rank indicates partial causal influence.

---

## 3. Datasets and Experimental Scope

### 3.1 Datasets Tested

| Dataset | Template | Concept Fields | N Seeds | N Swap Pairs |
|---------|----------|----------------|---------|--------------|
| USA States | "The capital of the state containing {city} is" | state, capital | 50 | 2280 (50x50 minus identity minus failures) |
| Book Characters/Authors | "The book featuring {character} was written by" | book, author | 16 | 256 (16x16) |
| Products/Founders | (templated) | product, founder | 12 | 144 (12x12) |
| Paintings/Painters | (templated) | painting, painter | 10 | 100 (10x10) |
| Sounds/Colors | (templated) | sound, color | 6 | 36 (6x6) |

### 3.2 Model

All experiments use **Gemma-2-2B-it** with the `clt-hp` (cross-layer transcoder, high-performance) feature set containing ~2.5M features across 26 layers.

---

## 4. Results: Claims, Evidence, Reasoning

### 4.1 Claim C1: Behavioral coherence exceeds geometric clustering

**Evidence** (from Michael Jordan circuit, n=1 circuit, 39 features):
- Peak-token consistency: 0.425 (concept-aligned) vs 0.183 (cosine), 2.3x
- Activation-pattern similarity: 0.762 vs 0.130, 5.8x
- Silhouette index: 0.124 vs 0.707 (layer-adjacency wins on geometric compactness)
- Sparsity consistency: 0.255 vs 0.335--0.399 (lower = more concentrated, favorable)

**Reasoning**: Concept-aligned grouping trades geometric compactness for functional coherence -- features in a behavioral supernode respond to the same tokens across contexts, while cosine-clustered features may be geometrically close but functionally diverse. The lower Silhouette is expected because functional roles span multiple layers.

**Limitations**: Single circuit (Michael Jordan). Baselines received "comparable attention" but no formal hyperparameter optimization is documented. No significance tests. The same activation matrix is used for concept-aligned and cosine baselines, isolating the grouping rule as the only variable.

### 4.2 Claim C2: Interpretability-oriented compression

**Evidence** (5 circuits):
- Completeness: mean 0.83 (subgraph) vs 0.90 (full graph), Delta = -0.07
- Replacement: mean 0.54 vs 0.70, Delta = -0.16
- Completeness range: 0.79--0.86 across all 5 prompts

**Reasoning**: The Replacement drop reflects deliberate exclusion of low-influence nodes. Completeness remaining high indicates that concept-aligned subgraphs capture most incoming edge influence. The trade-off is intentional: 30--50 labeled supernodes vs 600+ unlabeled features.

**Limitations**: Replacement and Completeness are near-invariant across grouping methods (all pin the same nodes), so they do not discriminate grouping quality. They only measure subgraph coverage, not interpretability itself.

### 4.3 Claim C3: Early-vs-late computational hierarchy

**Evidence** (Dallas -> Oakland transfer, 39 features):
- Transfer rate: 64% (25/39 features)
- Transferred features: mean layer 6.3 (SD 5.2)
- Non-transferred features: mean layer 16.4 (SD 5.8)
- Layer difference: Delta = 10.1 (~40% of 26-layer model)
- Entity-appropriate activation: 96% of transferred features peak on correct capital
- Activation overlap for transferred features: 1.000 (SD 0.000)

**Reasoning**: Early layers encode transferable relational structure ("X is the capital of Y"), while late layers specialize for output promotion ("Say Austin" vs "Say Sacramento"). This is consistent with a backbone-and-specialization model of transformer computation.

**Limitations**: Single circuit pair (Texas -> California). The 64% transfer rate and 10.1-layer gap are descriptive, not inferential. No significance test, no confidence interval. Replication across additional entity pairs is needed.

### 4.4 Claim C4: Feature swapping demonstrates entity-specific causal leverage of labeled supernodes

**Epistemic note**: The original framing ("validates supernode labels") conflates causal leverage with label correctness. We reframe: swap experiments test whether supernodes have entity-specific downstream causal effects (level 2), not whether their labels are mechanistically complete descriptions (level 3).

**Evidence** (across 5 domains):

| Dataset | Swap Pairs | Exact Match | Suppression | Flip @0 | Flip Any | Gap Closure (mean) |
|---------|------------|-------------|-------------|---------|----------|-------------------|
| USA States | 2284 | 38.8% | 96.7% | 88.4% | 97.4% | 3.71 |
| Books/Authors | 256 | 37.9% | 82.0% | 18.0% | 21.9% | 0.78 |
| Products/Founders | 144 | 25.7% | 67.4% | 15.3% | 17.4% | 0.68 |
| Paintings/Painters | 100 | 4.0% | 70.0% | N/A | N/A | N/A |
| Sounds/Colors | 36 | 2.8% | 100% | N/A | N/A | N/A |

**USA States tier distribution** (from `_analysis_v3`):
- Tier 5 (PERFECT): 35.5%
- Tier 4 (TARGET_STATE_CITY): 25.8%
- Tier 3 (TARGET_STATE_ONLY): 9.7%
- Tier 2 (SUPPRESSED_ONLY): 10.8%
- Tier 1 (SOURCE_PERSISTS): 18.3%
- State-correct rate (tier 4+5): 61.3%
- Suppression rate: 81.7% (source absent from output)
- Average tier: 3.49

**The specificity argument**: The strongest evidence for level-2 causal claims is not mere logit movement but *entity-specific outcome resolution*. When ablating Texas features and amplifying Georgia features, the model produces "Atlanta" (Georgia's capital) or another Georgia city -- not a random high-probability token. Across 2,284 USA state swaps, 61.3% land in the correct target state. This directional specificity is hard to explain under a "brute-force perturbation" hypothesis: generic perturbation would not consistently resolve to the geographically correct entity. However, this argument is structural, not proven -- the random-feature control (Section 7.1) would provide the missing quantitative baseline.

**The domain gradient**: The performance disparity between domains is substantial but informative. Crucially, graph sizes and supernode counts are *comparable* across domains:

| Dataset | Supernodes (range) | Graph size (pinned nodes) |
|---------|-------------------|--------------------------|
| USA States | 200--265 | comparable |
| Products/Founders | 194--285 | comparable |
| Paintings/Painters | 297--449 | 361--540 |
| Sounds/Colors | 315--396 | 415--500 |

Poor performance in paintings and sounds is NOT explained by smaller or lower-quality graphs. The most parsimonious explanations are:
1. **Circuit complexity**: Geographic capitals are single-hop factual lookups; book authorship requires character->book->author traversal; painting attribution and sound-color association are even more abstract
2. **Training data frequency**: State capitals are well-represented in training; painting-painter associations less so
3. **Token localization**: Geographic concepts map to single tokens ("Texas", "Austin"); multi-word creative entities ("The Persistence of Memory", "Salvador Dali") are harder to steer via single-token features
4. **Attention-mediated circuits**: Complex associations may rely more heavily on attention routing (invisible to this pipeline) than on residual-stream features

The honest characterization: *the method demonstrates entity-specific causal leverage primarily in single-hop factual domains, with a systematic degradation tracking associative complexity*. This is a meaningful empirical finding about both the method's operating envelope and the underlying circuit structure.

**Limitations**:
- The tier classifier is domain-specific (USA geography); cross-domain tier comparisons are not meaningful
- Without a random-feature baseline, we cannot quantify how much of the effect is specific to labeled features vs. any perturbation of similar magnitude
- Trajectory data is missing for paintings and sounds/colors, preventing continuous evaluation
- Identity swaps (A -> A) are included in some runs, slightly inflating aggregate metrics
- The `freeze_attention: false` setting means interventions are tested under full model dynamics (attention can adapt), which strengthens positive results but also means the model may partially compensate for interventions, potentially understating feature importance

### 4.5 Claim C5: Trajectory analysis provides continuous evidence of causal influence beyond exact match

**Evidence**: In the USA states dataset:
- 97.4% of swaps achieve a flip at some position (target outranks source)
- 88.4% flip at position 0 (first generated token)
- Mean gap closure: 3.71 logits over trajectory, 14.45 at position 0
- 52.8% have positive gap closure (gap improves over generation)
- Target reaches top-5 in 71.6% of swaps, top-10 in 80.3%

For books/authors:
- Only 21.9% achieve any flip, 18.0% at position 0
- Mean gap closure: 0.78 (much smaller effect)
- Target reaches top-5 in only 0.78% of cases

For products/founders:
- 17.4% achieve any flip, 15.3% at position 0
- Mean gap closure: 0.68
- Target reaches top-5 in 4.9% of cases

**What trajectory metrics measure**: A flip at position 0 means that at the very first generation step -- before any autoregressive dynamics -- the model's probability distribution has shifted so the target token outranks the source token. This is a direct consequence of the residual-stream intervention. Gap closure measures how much the target-source logit difference improves. Both are metrics of *steering success* (causal leverage) rather than *interpretive correctness* (label accuracy). The distinction matters.

**Reasoning**: The trajectory data shows that interventions produce real, entity-specific logit movement toward targets even when the target token is not ultimately sampled as output. For USA states, the 50-percentage-point gap between flip@0 (88.4%) and exact match (38.8%) indicates substantial partial success invisible to binary evaluation. This supports the claim that exact match alone understates intervention effectiveness.

However, trajectory metrics cannot by themselves distinguish between two hypotheses: (a) the labels are correct and the model's decoding process introduces noise that prevents the top-logit token from being sampled, or (b) the labels capture a correlated proxy that shifts logits in approximately the right direction without precisely targeting the correct mechanism. Distinguishing these requires the specificity controls in Section 7.

**Caveat on control stability**: The control token stability metric (mean absolute logit change for "the", "is", "a", "of") shows high specificity rate near 0% across all datasets, meaning control tokens are substantially perturbed by the intervention. This indicates the intervention has broad effects on the logit distribution, not only on source and target tokens. This is expected given the large multipliers but should be noted when interpreting gap closure as evidence of targeted steering.

### 4.6 Cross-Prompt Robustness (from validation analysis)

**Evidence** (Dallas vs Oakland, detailed supernode comparison):
- 7/7 universal concept supernodes transfer perfectly (copula, prepositions, relational operators)
- 8/8 entity-specific supernodes show appropriate non-transfer
- 25 shared features (12.8% of total) with 94% activation stability
- Peak token consistency among shared features: 88% (same token), 96% (same token type)
- Layer 0--1 feature overlap: 80--92%; Layer 16--22 overlap: 0--50%

**Reasoning**: Clean disentanglement of task structure from factual content supports robust concept discovery rather than probe-specific overfitting. The low overall feature overlap (12.8%) reflects entity-specificity, not failure.

**Limitations**: Single probe pair. Corrected grouping consistency (96%) requires manual review to distinguish appropriate entity-dependent variation from genuine error.

---

## 5. Methodological Strengths

1. **Transparency**: All classification rules are explicit thresholds, not learned parameters. Every assignment is traceable to specific threshold crossings. This is a genuine advantage over opaque clustering methods, even acknowledging that transparent thresholds can still be wrong.

2. **Deterministic pipeline**: No random sampling or initialization (aside from LLM probe generation, which is manually reviewed). Fixed random seeds throughout.

3. **Multi-level evaluation**: Exact match (binary), tier classification (ordinal, domain-specific), trajectory analysis (continuous). These measure different aspects of intervention success and complement each other.

4. **Scale**: 2,800+ swap experiments across 5 domains provide reasonable coverage of the method's operating characteristics. The 50x50 USA matrix in particular provides enough data for per-entity analysis.

5. **Honest internal framing**: The paper and codebase consistently flag limitations, use "descriptive rather than inferential" framing, and distinguish exploratory from pre-specified analyses. The codebase documentation preemptively identifies most of its own weaknesses.

6. **Reproducibility**: Checkpoint/resume system, documented configurations, public codebase, interactive demo.

7. **Non-frozen attention**: The choice to run interventions with `freeze_attention: false` means the model's attention is free to compensate for the perturbation. Positive results under these conditions are stronger evidence of causal leverage than they would be under constrained patching, where some feature-feature effects are architecturally guaranteed (Ameisen et al., 2025).

8. **Methodological alignment with field trajectory**: The approach of using behavioral probes + causal intervention for feature evaluation is consistent with recent work on SAE-targeted steering (Kharlapenko et al., 2024) and the causal interpretability framework (Geiger et al., 2025). The pipeline occupies a methodologically coherent position between pure behavioral observation and full mechanistic explanation.

---

## 6. Methodological Concerns and Gaps

### 6.1 Confound: Token Overlap

The USA states dataset (the strongest-performing domain) includes systematic token overlap for several entities (e.g., "Colorado" in prompt city "Colorado Springs" and state name "Colorado"). The codebase identifies 6 specific entities with overlap: `colorado_colorado_springs`, `new_york_new_york_city`, `virginia_virginia_beach`, `idaho_idaho_falls`, `missouri_kansas_city`, `indiana_fort_wayne`. Token overlap provides a potential shortcut for the model: attention to shared tokens may drive output without semantic feature-level processing.

**Status**: The `has_token_overlap` flag exists in the demo data loader and is displayed in the UI, but `analyze_swaps.py` does not stratify results by this flag. The affected entities represent 6/50 states (~12%), so the majority of swap pairs are overlap-free. However, without stratified reporting, the confound's contribution to aggregate metrics is unknown. This is the most straightforward control to implement (Section 7.3).

### 6.2 Confound: Attention Circuits

Attribution graphs are computed using replacement models that freeze attention patterns, making QK-circuit effects invisible. However, the swap interventions themselves run with `freeze_attention: false` -- attention patterns are *not* frozen during steering. This creates an asymmetry: the features were selected based on a frozen-attention graph, but tested under full model dynamics where attention can adapt.

This asymmetry has two consequences:
- **Positive**: Results are not artifactually inflated by frozen-attention "guaranteed effects" (Ameisen et al., 2025). The model can route around interventions via attention, making positive results more meaningful.
- **Negative**: Features whose causal role depends on attention routing may be correctly identified in the graph but fail to produce effects when attention is free to compensate. This could contribute to the gap between flip@0 (88.4%) and exact match (38.8%) for USA states.

**Status**: Known limitation, documented in the paper. The author's hypothesis that "attention circuits are probably having a main role" in failure cases is plausible but untested.

### 6.3 Missing Baseline: Random Feature Intervention

There is no reported experiment where randomly selected features (rather than labeled supernodes) are ablated/amplified. This control would establish whether the observed effects are specific to the labeled features or arise from any sufficiently large perturbation to the feature space.

### 6.4 Missing Baseline: Shuffled Labels

There is no experiment where supernode labels are randomly shuffled (e.g., swapping the "Texas" label with the "California" label) before running interventions. This would test whether the label-concept alignment matters or whether the intervention effect is purely structural.

### 6.5 Intervention Multiplier Sensitivity

The default multipliers (M_ablate = -2, M_amplify = 20) follow Anthropic's empirically calibrated practice (Ameisen et al., 2025, "Unexplained Variance and Choice of Steering Factors"), which documents three structural reasons for large factors: incomplete CLT dictionaries, inexhaustive supernode membership, and incomplete cross-layer effect capture. The asymmetry reflects different operational requirements: ablation reverses an already-active feature, while amplification must inject a feature that had near-zero activation on the original prompt, requiring much larger magnitude to overcome the model's prior.

Despite this justification, no systematic sweep of these parameters is reported across domains. The same values are used for all datasets despite potentially different feature activation scales. An ablation-only vs. amplification-only decomposition would clarify whether both operations contribute independently (Section 7.5), and a multiplier sweep (Section 7.4) would characterize the sensitivity curve.

### 6.6 Domain Performance Variance

The dramatic performance drop from USA states (38.8% exact match, 88.4% flip@0) to paintings (4% exact match, no trajectory) to sounds/colors (2.8% exact match) is not adequately explained. Possible explanations include:
- Factual retrieval (geography) vs. associative recall (creative works) uses different circuit structures
- Training data frequency differences (state capitals appear more often than painting attributions)
- Prompt template quality varies across domains
- Graph quality (number and relevance of extracted features) varies
- Some domains may simply lack the factual circuits this method is designed to probe

### 6.7 Statistical Methodology

No formal statistical tests are applied anywhere in the pipeline. All comparisons are descriptive (means, rates, percentages). Given the sample sizes (2,284 swaps for USA, 256 for books), standard statistical inference (e.g., bootstrap confidence intervals, permutation tests) would be straightforward and informative.

### 6.8 Threshold Sensitivity

The classification thresholds (peak_consistency >= 0.80, layer >= 7 for Say-X, sparsity_median < 0.45 for Relationship) were developed through iterative manual inspection of activation patterns across multiple circuits. This constitutes informal validation on a limited set but not formal sensitivity analysis. Without systematic perturbation (+/- 10%, 20%, 50%) and measurement of downstream effects on classification distributions and swap performance, we cannot distinguish between thresholds that carve natural joints in the model's computation and thresholds that happen to work on the cases inspected. The interactive UI exposes adjustable sliders, and the swap results provide a natural validation signal (degraded swap performance under perturbed thresholds would indicate the thresholds capture real structure), but this feedback loop has not been formally exercised.

**Note on category ontology**: If the boundaries between Semantic Dictionary, Say-X, and Relationship shift substantially with small threshold changes, the categories may not correspond to natural computational types in the model but rather to regions in a continuous behavioral space that the threshold-based decision tree artificially discretizes. This is an important open question for the interpretability of the interpretability tool itself.

### 6.9 Behavioral Coherence vs. Meaningful Structure

Recent work (Heap et al., 2025) demonstrates that SAE latents in randomly initialized transformers can appear "interpretable" and score well on quantitative auto-interpretability metrics. This undermines the assumption that behavioral coherence or descriptive quality alone constitutes evidence of meaningful internal structure. The implication for this pipeline: the behavioral coherence metrics (C1) and the readability of supernode labels (level 1 claims) are necessary but not sufficient for meaningful interpretation. Only the intervention results (level 2 claims) provide evidence that the identified structure has causal relevance beyond descriptive convenience. This reinforces the priority of specificity controls over further behavioral measurement.

### 6.10 Multi-Token Limitations

Multi-token concepts (e.g., "New York", "J.K. Rowling") are handled by splitting on spaces and matching words of length >= 3. This heuristic can miss partial matches or create false positives. The naming system uses single-token peaks, requiring manual post-correction for multi-token names.

---

## 7. Proposed Control Experiments

The following experiments are ordered by expected informativeness and feasibility.

### 7.1 Random Feature Ablation Control (HIGH PRIORITY)

**Design**: For each swap pair, instead of ablating/amplifying labeled supernodes, select the same number of random features from the graph and apply the same multipliers.

**Expected outcome**: If labeled supernodes are meaningfully identified, random features should produce significantly lower exact match rates, flip rates, and gap closure compared to the labeled features.

**Falsifies**: The hypothesis that any large perturbation to the feature space produces similar effects.

**Implementation**: Minimal -- modify `run_batch_swaps.py` to sample random feature sets of matching size per swap, reuse existing evaluation pipeline.

### 7.2 Label Permutation Control (HIGH PRIORITY)

**Design**: For each entity A, instead of ablating A's supernodes and amplifying B's supernodes, ablate B's supernodes and amplify A's (reversed direction) or ablate A's and amplify C's (mismatched target).

**Expected outcome**: Reversed swaps should produce worse results. Mismatched amplification targets should produce different (likely worse) outcomes than correctly matched targets.

**Falsifies**: The hypothesis that only ablation matters (and amplification is irrelevant), or that any amplification is equally effective.

**Implementation**: Add a `--reverse` flag to swap pipeline and a `--random-target` mode.

### 7.3 Token Overlap Stratification (HIGH PRIORITY)

**Design**: Split the USA states 50x50 matrix into two groups: swaps with token overlap between prompt city and any concept field, and swaps without. Report all metrics separately.

**Expected outcome**: If token overlap drives results, the overlap group should show substantially higher success rates.

**Falsifies**: (or supports) The confound that geographic results are inflated by token overlap.

**Implementation**: The `has_token_overlap` flag already exists in the demo data loader. Extend `analyze_swaps.py` to stratify by this flag.

### 7.4 Intervention Multiplier Sweep (MEDIUM PRIORITY)

**Design**: Sweep M_ablate in {0, -1, -2, -5} and M_amplify in {1, 2, 5, 10, 20, 50} for a subset of swap pairs (e.g., 10 well-characterized pairs from USA states). Plot exact_match, flip@0, and gap_closure as functions of both multipliers.

**Expected outcome**: Performance should plateau at some amplification level and degrade at extreme values. The optimal ratio may differ across domains.

**Falsifies**: The assumption that M_ablate=-2, M_amplify=20 is near-optimal. Alternatively, if performance increases monotonically with amplification, this suggests the intervention is more like brute-force logit manipulation than targeted circuit steering.

### 7.5 Ablation-Only vs. Amplification-Only (MEDIUM PRIORITY)

**Design**: Run swaps with ablation only (M_amplify=1, no change) and amplification only (M_ablate=1, no change).

**Expected outcome**: Clarifies whether the observed effects are driven primarily by suppressing source features, boosting target features, or both. Suppression rate should be high for ablation-only; exact match should be higher for amplification-only if the target features are correctly identified.

**Falsifies**: If ablation alone achieves high suppression but near-zero exact match, and amplification alone achieves exact match, this supports the claim that both operations are meaningfully targeted.

### 7.6 Cross-Domain Transfer (MEDIUM PRIORITY)

**Design**: Apply supernodes learned from USA states (e.g., the "Say (X)" features for state capitals) to a completely different geographic prompt template, or to a non-geographic domain. Test whether universal supernodes (copula, preposition) transfer.

**Expected outcome**: Universal supernodes should transfer (they encode syntax); entity-specific supernodes should not. If they do, the features may be less specific than claimed.

### 7.7 Threshold Sensitivity Analysis (MEDIUM PRIORITY)

**Design**: Perturb each classification threshold by +/- 10%, 20%, 50% and record the number of features in each category, the number that change category, and the downstream swap performance.

**Expected outcome**: Small perturbations should produce small changes (stability). Large perturbations should degrade performance but not catastrophically (robustness). If the system is brittle (small threshold changes cause large classification shifts), this undermines the claim of expert-tuned thresholds.

### 7.8 Attention-Aware Validation (LOW PRIORITY, HIGH EFFORT)

**Design**: Use a non-frozen attention intervention method (e.g., activation patching without freezing attention) to test whether results change significantly.

**Expected outcome**: If attention circuits are important for the domains where this pipeline fails (books, paintings), unfreezing attention should improve those domains. If results are similar, the frozen-attention assumption is vindicated.

**Note**: This requires modifying the circuit tracer infrastructure, not just this pipeline.

### 7.9 Per-Entity Feature Quality Analysis (MEDIUM PRIORITY)

**Design**: For each entity in each domain, compute a "feature quality score" from the probe stage (e.g., mean peak consistency, mean z-score, number of supernodes) and correlate it with swap performance (as-source tier, as-target tier).

**Expected outcome**: Entities with higher feature quality should produce better swap outcomes. The existing `explore_swap_factors.py` partially addresses this (correlating native_prob and supernodes with tier), but a more systematic per-entity feature audit would strengthen the analysis.

**Evidence already available**: Factor analysis reports r = -0.92 between state supernode count and source tier (more supernodes = better suppression), r = -0.61 for native logit probability, and r = -0.75 for total supernodes. These are suggestive but based on Pearson correlation without controlling for confounds.

### 7.10 Probe Prompt Sensitivity (LOW PRIORITY)

**Design**: Generate multiple independent sets of probe prompts for the same seed (using different LLM seeds or different models) and compare the resulting CPAS and classifications.

**Expected outcome**: If the pipeline is robust, different probe sets should produce similar classifications and downstream swap performance.

**Falsifies**: The concern that results are artifacts of the specific probe prompts chosen.

---

## 8. Summary of Epistemic Status

The following assessment uses the three-level framework from Section 1.2.

### Level 1 -- Operationally Useful Labels: WELL-SUPPORTED

1. **The pipeline produces behaviorally grounded, interpretable groupings**: Evidence across 5+ circuits and 8 domains. Feature categories (Semantic Dictionary, Semantic Concept, Say-X, Relationship) are behaviorally distinct and produce labeled supernodes that are useful for navigating and understanding circuits. This is the strongest and most defensible claim.

2. **Cross-prompt robustness for geographic circuits**: Strong evidence from Dallas/Oakland transfer analysis (100% universal supernode transfer, 100% appropriate entity non-transfer, 94% activation stability for shared features). The labels function as stable behavioral abstractions.

3. **Interpretability-oriented compression**: Subgraphs reduce hundreds of features to 30--50 labeled supernodes while preserving 83% Completeness. This is a useful engineering contribution regardless of whether the labels are mechanistically "true."

### Level 2 -- Downstream Causal Effects: SUBSTANTIALLY SUPPORTED, PENDING SPECIFICITY CONTROLS

4. **Interventions on labeled supernodes produce entity-specific logit shifts**: USA states show 88.4% flip@0, 61.3% state-correct outcomes, 3.71 mean gap closure. Books/authors show moderate effects (82% suppression, 18% flip@0). The entity-specificity of outcomes (correct target state, not random states) is structural evidence of level-2 causal alignment, but quantitative specificity (vs. random features) is not yet established.

5. **Suppression via ablation works broadly**: 67--100% suppression across all domains, indicating that features identified as source-relevant are genuinely causally involved in producing the source output.

6. **Trajectory analysis provides continuous evidence beyond exact match**: The 50-point gap between flip@0 (88.4%) and exact match (38.8%) for USA states shows substantial partial success invisible to binary evaluation. However, trajectory metrics measure steering success, not interpretive correctness -- the distinction is material.

### Level 2 to Level 3 gap -- CRITICAL OPEN QUESTIONS

7. **Label specificity**: Without random-feature and label-permutation controls, we cannot quantify how much of the observed causal leverage is specific to the labeled features vs. arising from any sufficiently large perturbation. The entity-specificity of outcomes is suggestive but not quantitatively proven.

8. **Domain generalization**: Performance degrades systematically with circuit complexity (geography > books > products > paintings > sounds), and this gradient is NOT explained by graph size differences (graphs are comparable across domains). The method's operating envelope is narrower than the multi-domain framing suggests.

9. **Frozen-attention graph / unfrozen-attention intervention asymmetry**: Features were selected from graphs computed with frozen attention, but tested with unfrozen attention. This means the attribution graph and the intervention operate under different model dynamics, creating an uncharacterized source of discrepancy.

### Level 3 -- Full Mechanistic Explanation: NOT CLAIMED, NOT ESTABLISHED

10. **The classification thresholds carve natural computational joints**: No sensitivity analysis. Informally validated on a limited set.

11. **The backbone-and-specialization hierarchy is general**: Supported by one circuit pair (geographic). Not tested for non-factual tasks.

12. **The method captures the model's internal algorithm**: Not claimed by this work, and rightly so. The labels are behavioral abstractions, not ontological identifications of latent variables.

### Overall Assessment

This work makes a credible case for semi-automated, operationally meaningful circuit interpretation via supernode-level behavioral abstractions and entity-specific causal interventions, especially in favorable factual domains. Its main remaining limitation is not lack of promise but lack of specificity controls: the current evidence supports downstream causal leverage more strongly than fully correct mechanistic labeling. The three priority experiments (random-feature control, label permutation, token-overlap stratification) represent the critical path from a strong case of causal leverage to a strong case of label specificity.

The work is positioned correctly within the field's trajectory: less emphasis on the metaphysics of features, more emphasis on the class of interventions a description supports and the type of generalization it permits. The honest scope is: *a pipeline that generates operationally useful behavioral hypotheses about circuit features, with demonstrated entity-specific causal leverage in single-hop factual domains and a well-characterized degradation gradient across domain complexity*.

---

## 9. Notation and Definitions Reference

| Symbol | Definition |
|--------|------------|
| CLT | Cross-Layer Transcoder (reads residual stream, writes to downstream MLP layers) |
| CPAS | Cross-Prompt Activation Signature |
| tau | Cumulative influence threshold for feature selection |
| M_ablate | Multiplication factor applied to source features during intervention (default: -2) |
| M_amplify | Multiplication factor applied to target features during intervention (default: 20) |
| flip_position | First generation step where target rank < source rank |
| gap_closure | max(gap_trajectory) - gap_trajectory[0]; measures improvement from initial state |
| gap_trajectory[t] | target_logit[t] - source_logit[t] at generation step t |
| Replacement | Fraction of end-to-end influence routing through pinned features |
| Completeness | Fraction of incoming edge influence explained by upstream features/embeddings |
| Tier | Domain-specific ordinal quality score for swap outcomes (0--5 for USA states) |

---

## 10. References and Context

- Ameisen et al. (2025). "Circuit Tracing: Revealing Computational Graphs in Language Models." Transformer Circuits, March 2025. Primary methodological foundation.
- Geiger et al. (2025). "Causality is Key for Interpretability Claims to Generalise." arXiv:2602.16698. Framework for distinguishing levels of interpretive claim.
- Raukur et al. (2025). "Open Problems in Mechanistic Interpretability." arXiv:2501.16496. Contextualizes internal description validation as open problem.
- Heap et al. (2025). "Sparse Autoencoders Can Interpret Randomly Initialized Transformers." arXiv:2501.17727. Caution against over-relying on behavioral coherence or autointerp metrics as evidence of meaningful structure.
- Kharlapenko et al. (2024). "Improving Steering Vectors by Targeting Sparse Autoencoder Features." arXiv:2411.02193. Related work on SAE-targeted steering for evaluation.
- Birardi (2025). "Automated Circuit Interpretation via Probe Prompting." arXiv:2511.07002. The paper accompanying this codebase.

---

*Report generated from analysis of the full attribution-graph-probing codebase, including all scripts, configurations, output data, paper sections, and validation summaries. Revised to incorporate adversarial review feedback and recent literature context.*
