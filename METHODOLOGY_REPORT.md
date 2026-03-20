# Methodology Report: Automated Circuit Interpretation via Probe Prompting

**Date**: 2026-03-20 (revised -- data reconciliation: all metrics now computed live from per-swap JSONs, replacing stale aggregate files)
**Scope**: Full pipeline analysis -- from probe generation through feature swapping and trajectory analysis
**Epistemic framing**: Claims, evidence, and reasoning are separated throughout. Three levels of interpretive claim are distinguished: (i) operationally useful labels, (ii) downstream causal effects, and (iii) full mechanistic explanation. Recommendations for control experiments are in Section 7.

---

## 1. Problem Statement and Research Context

### 1.1 The Interpretation Bottleneck

Attribution graphs (Ameisen et al., 2025) represent causal pathways from input embeddings through cross-layer transcoder (CLT) features to output logits. These graphs typically contain hundreds to thousands of feature nodes. Manual interpretation -- inspecting activation patterns across corpus examples to assign semantic labels -- is reported to require approximately 2 hours per prompt by an experienced analyst.

**Claim**: Probe prompting can automate this first-pass analysis, reducing the time to 10--20 minutes of semi-automated processing per circuit.

**Evidence**: The pipeline generates interpretable supernode groupings across 5+ prompt families (geographic capitals, book/author, product/founder, painting/painter, sound/color domains). Processing time is documented at 2--5 minutes for graphs with 50--200 features.

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

**Default Parameters**:
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

**Assumption**: The replacement model (which freezes attention during graph computation) faithfully represents the computations of interest. This is standard in the field but may underestimate indirect effects mediated by attention pattern changes. The downstream swap interventions (Stage 3)  use `freeze_attention: false` in all configs; Anthropic's own perturbation experiments similarly do not always freeze attention, and they note that with frozen attention, direct feature-feature effects along graph edges are "nearly forced to be confirmed" (Ameisen et al., 2025, section "Nuances of Steering with Cross-Layer Features"). By not freezing attention, the intervention allows the model's attention to adapt freely, meaning observed effects are not architecturally guaranteed by the graph structure.

### 2.2 Stage 1: Probe Prompt Generation and Activation Measurement

**Goal**: Produce a cross-prompt activation signature (CPAS) for each feature, characterizing its behavioral response to controlled semantic variation.

**Probe generation**: An instructed LLM (e.g. Claude-3.5-Sonnet, temperature 0.7) generates probe prompts that describe single concepts likely involved in the seed prompt's internal circuit. Probes are designed to reuse tokens and syntactic structure of the seed when possible (e.g., seed "The capital of the state containing Dallas is" might produce probes like "A state in USA is Texas",  "A city in Texas is Dallas"). The goal is to elicit feature activations that disambiguate each feature's role in the circuit. In batch mode, probes are loaded from shared template files with systematic concept coverage (entity, attribute, relationship categories). Probes are manually reviewed for quality.

**Activation measurement**: For each (feature, probe) pair, activations are measured via Neuronpedia API (or local GPU inference in batch mode). Many per-pair metrics are recorded (peak token, cosine similarity, z-scores, density, sparsity ratio, label span statistics). The subset that drives the classification decision tree (Stage 2) is:

**Aggregated metrics used for classification** (per feature, across probes):
| Metric | Definition | Used in rule |
|--------|------------|-------------|
| `peak_consistency_main` | Fraction of probes where the most frequent peak token is the actual peak | Dictionary (>= 0.80) |
| `n_distinct_peaks` | Count of distinct tokens serving as peak across probes | Dictionary (<= 1) |
| `conf_F` / `share_F` | Fraction of active probes where peak is on a functional token | Say-X (>= 0.90) |
| `func_vs_sem_pct` | 100 * (max_functional_act - max_semantic_act) / max_overall | Say-X (>= 50), Semantic (< 50) |
| `sparsity_median` | Median sparsity ratio across active probes | Relationship (< 0.45) |
| `conf_S` | 1 - share_F (semantic confidence) | Semantic Concept (>= 0.50) |
| `layer` | Feature's layer in the CLT | Say-X (>= 7), Semantic (<=3) |



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

**Conflict resolution**: The decision tree uses strict priority ordering -- the first matching rule wins. There is no weighted scoring: if a feature matches Rule 1 (Dictionary), it is assigned there regardless of how well it might match Rule 2 (Say-X). This design is simple and auditable but means the rule ordering itself encodes implicit priorities.

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

### 2.5 Tier Classification

**USA States (full tier system)**: A rule-based classifier assigns each swap result to a tier (0--5) using curated geographic data (US cities, capitals, counties, regions, landmarks, islands, ambiguous cities, foreign places):

| Tier | Name | Criterion |
|------|------|-----------|
| 5 | PERFECT | Target capital appears in output |
| 4 | TARGET_STATE_CITY | Other city in target state (not capital) |
| 3 | TARGET_STATE_ONLY | Target state mentioned, no valid city |
| 2 | SUPPRESSED_ONLY | Source suppressed, garbled or non-geographic output |
| 1 | SOURCE_PERSISTS | Source capital/city still in output |
| 0 | WRONG_STATE | City from a third state |

**Non-USA domains (simplified evaluation)**: For books, paintings, products, sounds, and other domains, full geographic tier classification is not applicable. Evaluation uses the domain-agnostic `_get_tier_from_swap()` logic: tier 5 (PERFECT) is assigned when the target answer is detected via full-answer match, first-token substring match, or any word (len >= 3) of the target answer appearing in the steered output; tier 2 (SUPPRESSED) when the source is absent but no target signal is found; tier 1 (SOURCE_PERSISTS) when the source answer remains. Tiers 3 and 4 are not produced by this path -- they exist only for USA states where the geographic classifier distinguishes "target state mentioned" (T3) from "other city in target state" (T4).

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

| Dataset | Seed Prompt Template | Concept Fields | N Seeds | N Swap Pairs |
|---------|---------------------|----------------|---------|--------------|
| USA States | "The capital of the state containing {city} is" | state, capital | 50 | 2407 swap + 50 identity |
| Book Characters/Authors | "The book featuring {character} was written by" | book, author | 16 | 240 swap + 16 identity |
| Products/Founders | "The company that makes {product} was founded by" | company, founder | 12 | 132 swap + 12 identity |
| Paintings/Painters | "The first name of the painter of {painting} is" | painting, first_name | 10 | 90 swap + 10 identity |
| Sounds/Colors | "Fact: The most common color of the animal that goes '{sound}' is" | animal, color | 6 | 30 swap + 6 identity |

### 3.2 Model

All experiments use **Gemma-2-2B-it** with the `clt-hp` (cross-layer transcoder, high-performance) feature set containing ~2.5M features across 26 layers.

---

## 4. Results: Claims, Evidence, Reasoning

### 4.1 Claim C1: Feature swapping demonstrates entity-specific causal leverage of labeled supernodes

**Epistemic note**: The original framing ("validates supernode labels") conflates causal leverage with label correctness. We reframe: swap experiments test whether supernodes have entity-specific downstream causal effects (level 2), not whether their labels are mechanistically complete descriptions (level 3).

**Evidence** (across 5 domains, from latest runs with per-swap logit trajectory tracking):

| Dataset | Swap Pairs | Perfect (T5) | Suppression (T2+) | Flip @0 | Flip Any | Gap Closure (mean) |
|---------|------------|-------------|-------------------|---------|----------|-------------------|
| USA States | 2407 | 38.8% | 91.2% | 90.2% | 99.5% | 3.79 |
| Books/Authors | 240 | 46.7% | 85.4% | 96.7% | 96.7% | 0.04 |
| Products/Founders | 132 | 34.1% | 72.7% | 96.2% | 97.7% | 0.35 |
| Paintings/Painters | 90 | 1.1% | 70.0% | 97.8% | 100% | 0.45 |
| Sounds/Colors | 30 | 20.0% | 100% | 33.3% | 56.7% | 1.84 |

**Metric definitions**: "Perfect (T5)" = tier 5 classification, which uses full-answer match, first-token substring match, or word-level match (len >= 3) for non-USA domains, and the geographic classifier for USA states. "Suppression (T2+)" = tier >= 2 (source answer absent). "Flip @0" = first generated position where target token rank < source token rank (rank-based, see Section 4.5 for important caveats). "Gap Closure" = max(target_logit - source_logit over trajectory) minus initial gap.

**Cross-domain comparability note**: The T5 definition differs between USA states (geographic classifier: target capital string match) and non-USA domains (fuzzy: word-level match of len >= 3). This makes T5 rates more generous for non-USA domains. For apples-to-apples comparison, strict exact match rates (target answer as a whole in steered output) are: USA 38.8%, Books 36.7%, Products 24.2%, Sounds 3.3%, Paintings 1.1%. The strict metric preserves the expected complexity gradient.

**Data sources**: All metrics are computed live from per-swap JSON files in `output/<domain>_batch/_swaps/runs/<run_id>/by_source/`. Run IDs: USA States = `full_50states_v1` (2457 files); Books = `20260318_042511_*`; Products = `20260318_042902_*`; Paintings = `20260318_042730_*`; Sounds = `20260318_082355_*`. The interactive demo computes the same metrics at runtime from these files.

**USA States tier distribution** (full 50-state run, 2407 non-identity swaps):
- Perfect (T5): 38.8% (935 swaps)
- State-correct (T3+): 64.5% (1553 swaps)
- Suppression (T2+): 91.2% (2194 swaps)

**Note on flip metrics vs. gap closure**: The rank-based flip@0 metric is nearly universal across all domains (90--98% for USA, books, products, paintings) but dramatically overstates meaningful steering success in non-geographic domains. The critical distinction emerges from gap closure: USA states show a mean gap closure of 3.79 logit units, while non-geographic domains show 0.04--0.45. This indicates that the ablate+amplify intervention reliably makes the target token outrank the source token at position 0 (a mechanical consequence of suppressing one and boosting the other), but only in favorable domains does this translate into sustained logit improvement and successful output generation. Sounds/colors is the exception: despite having the highest suppression (100%) and moderate gap closure (1.84), flip rates are the lowest (33.3%), suggesting a different failure mode where the source and target tokens are in very different rank regions. See Section 4.5 for detailed trajectory analysis.

**The specificity argument**: The strongest evidence for level-2 causal claims is not mere logit movement but *entity-specific outcome resolution*. When ablating Texas features and amplifying Georgia features, the model produces "Atlanta" (Georgia's capital) or another Georgia city -- not a random high-probability token. Across 2,407 USA state swaps, 64.5% land in the correct target state. This directional specificity is hard to explain under a "brute-force perturbation" hypothesis: generic perturbation would not consistently resolve to the geographically correct entity. However, this argument is structural, not proven -- the random-feature control (Section 7.1) would provide the missing quantitative baseline.

**The domain gradient**: The performance disparity between domains is substantial but informative. Graph sizes (supernodes, pinned nodes) are comparable or larger for non-geographic domains, so poor performance is NOT explained by smaller graphs. However, a critical quality factor is **error node density**. Error nodes represent CLT reconstruction error -- the "dark matter" of model computation that the transcoder fails to explain (Ameisen et al., 2025). Error nodes receive no input edges, are not interpretable, and can dominate the graph, obscuring the real mechanism. In extreme cases, Anthropic notes that "almost all the nodes [...] are error nodes, making it impossible to trace back the origin of the [...] features."

| Dataset | Supernodes (range) | Error nodes per entity (range) |
|---------|-------------------|-------------------------------|
| USA States | 200--265 | 328--472 |
| Products/Founders | 194--285 | 326--431 |
| Books/Authors | -- | 343--536 |
| Paintings/Painters | 297--449 | 459--677 |
| Sounds/Colors | 315--396 | 558--673 |

(Source: counts of `"feature_type": "mlp reconstruction error"` in per-entity `graph.json` files.)

Non-geographic domains have systematically higher error node counts (sounds: 558--673 vs USA: 328--472). Higher error density means a larger fraction of the model's computation is invisible to the pipeline, making feature-level interventions less effective regardless of label quality. This is currently the strongest structural explanation for the domain performance gradient, though the pipeline does not yet track or filter by error node density.

Additional contributing factors:
1. **Circuit complexity**: Geographic capitals are single-hop factual lookups; book authorship requires character->book->author traversal; painting attribution and sound-color association are even more abstract
2. **Training data frequency**: State capitals are well-represented in training; painting-painter associations less so
3. **Token localization**: Geographic concepts map to single tokens ("Texas", "Austin"); multi-word creative entities ("The Persistence of Memory", "Salvador Dali") are harder to steer via single-token features
4. **Attention-mediated circuits**: Complex associations may rely more heavily on attention routing (invisible to this pipeline) than on residual-stream features

The honest characterization: *the method demonstrates entity-specific causal leverage primarily in single-hop factual domains with lower CLT reconstruction error, with systematic degradation in output success tracking both associative complexity and error node density, even as rank-based logit flips succeed near-universally*.

**Limitations**:
- Non-USA domains use simplified tier evaluation (exact match / suppression only)
- Without a random-feature baseline, we cannot quantify how much of the effect is specific to labeled features vs. any perturbation of similar magnitude
- Error node density is measured but not yet used as a per-entity quality filter
- Identity swaps are excluded from the counts above

### 4.5 Claim C5: Trajectory analysis provides continuous evidence of causal influence beyond exact match

**Evidence** (computed live from per-swap JSON files, same data source as Section 4.1):

| Dataset | Swaps w/ trajectory | Flip @0 | Flip Any | Gap Closure (mean) |
|---------|--------------------|---------|---------|--------------------|
| USA States | 2237 | 90.2% | 99.5% | 3.79 |
| Books/Authors | 240 | 96.7% | 96.7% | 0.04 |
| Products/Founders | 132 | 96.2% | 97.7% | 0.35 |
| Paintings/Painters | 90 | 97.8% | 100% | 0.45 |
| Sounds/Colors | 30 | 33.3% | 56.7% | 1.84 |

**Data source**: `evaluation.logit_trajectory.summary` in each swap JSON under `output/<domain>_batch/_swaps/runs/<run_id>/by_source/`. Note: earlier aggregate files (`trajectory_summary.json`) in some run directories are stale -- they were generated before the swap JSONs were re-processed with updated trajectory data and should not be used.

**What trajectory metrics measure**: `flip_position` is defined as the first generation step where `target_rank < source_rank` (rank-based comparison). `gap_closure` is `max(gap_trajectory) - gap_trajectory[0]` where `gap_trajectory[t] = target_logit[t] - source_logit[t]` (logit-based). These measure fundamentally different things: rank-based flips can occur even when both tokens are far from top-1, while gap closure measures sustained logit improvement.

**Key finding -- the flip/gap divergence**: Rank-based flip@0 is near-universal (90--98%) across all domains except sounds (33.3%). This is largely a mechanical consequence of the intervention: ablating source features pushes source rank down, while amplifying target features pushes target rank up, almost always achieving a rank crossover at position 0. However, gap closure -- the actual improvement in logit difference -- diverges dramatically: 3.79 for USA states vs 0.04--0.45 for non-geographic domains. This means the intervention reliably reorders the two tracked tokens but does not produce sustained logit dominance for the target in harder domains.

**Reasoning**: For USA states, the 51-percentage-point gap between flip@0 (90.2%) and Perfect T5 (38.8%) indicates substantial partial success invisible to binary evaluation, supported by meaningful gap closure (3.79). For non-geographic domains, the near-universal flip@0 combined with near-zero gap closure reveals that the rank crossover is shallow -- the target token marginally outranks the source but neither dominates the model's output distribution. The flip@0 metric as currently defined is too permissive to meaningfully distinguish successful from unsuccessful interventions in these domains; gap closure is the better discriminator.

Trajectory metrics cannot by themselves distinguish between: (a) the labels are correct and the model's decoding process introduces noise, or (b) the labels capture a correlated proxy that shifts logits in approximately the right direction without precisely targeting the correct mechanism. Distinguishing these requires the specificity controls in Section 7.

**Note on control stability metric**: The current control token stability metric (mean absolute logit change for "the", "is", "a", "of") uses an arbitrary ceiling threshold and a methodology that may not meaningfully measure intervention specificity. The metric shows near-0% "high specificity rate" across all datasets, but this likely reflects the metric design rather than a genuine finding. A more meaningful specificity measure would compare target-token logit movement against the distribution of logit movements across all vocabulary tokens, or use control tokens that are semantically related but not the intended target. This metric should be redesigned before drawing conclusions about intervention specificity.

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

4. **Scale**: ~2,900 swap experiments across 5 domains provide reasonable coverage of the method's operating characteristics. The 50x50 USA matrix in particular provides enough data for per-entity analysis.

5. **Reproducibility**: Checkpoint/resume system, documented configurations, public codebase, interactive demo.

6. **Non-frozen attention**: The choice to run interventions with `freeze_attention: false` means the model's attention is free to compensate for the perturbation. Positive results under these conditions are stronger evidence of causal leverage than they would be under constrained patching, where some feature-feature effects are architecturally guaranteed (Ameisen et al., 2025).


---

## 6. Methodological Concerns and Gaps

### 6.1 Confound: Token Overlap

The USA states dataset includes systematic token overlap for 6 entities where the prompt city shares tokens with the state name: `colorado_colorado_springs`, `new_york_new_york_city`, `virginia_virginia_beach`, `idaho_idaho_falls`, `missouri_kansas_city`, `indiana_fort_wayne`.

Contrary to the naive assumption that overlap makes swaps easier (by providing a "shortcut"), the empirical evidence suggests **token overlap makes swaps harder**, particularly when steering *away from* an overlap entity. Attention circuits (not modeled by this pipeline) likely bind the overlapping token strongly to the source output, making ablation of residual-stream features insufficient to overcome the attention-driven signal. Preliminary per-entity data supports this: Colorado (overlap) has among the lowest average tiers as a source entity (avg tier 2.33 vs population mean ~3.5), and New York (overlap) shows similar degradation.

**Status**: The `has_token_overlap` flag exists in the demo data loader and is displayed in the UI, but `analyze_swaps.py` does not stratify results by this flag. The affected entities represent 6/50 states (~12%), so the majority of swap pairs are overlap-free. Stratified results excluding overlap entities would provide cleaner aggregate metrics. [TODO: compute and report overlap-stratified metrics.]

### 6.2 Confound: Attention Circuits

Attribution graphs are computed using replacement models that freeze attention patterns, making QK-circuit effects invisible. However, the swap interventions themselves run with `freeze_attention: false` -- attention patterns are *not* frozen during steering. This creates an asymmetry: the features were selected based on a frozen-attention graph, but tested under full model dynamics where attention can adapt.

This asymmetry has two consequences:
- **Positive**: Results are not artifactually inflated by frozen-attention "guaranteed effects" (Ameisen et al., 2025). The model can route around interventions via attention, making positive results more meaningful.
- **Negative**: Features whose causal role depends on attention routing may be correctly identified in the graph but fail to produce effects when attention is free to compensate. This could contribute to the gap between flip@0 (90.2%) and exact match (38.8%) for USA states, and the near-total disconnect between flip@0 (~97%) and exact match (1--47%) for non-geographic domains.

**Status**: Known limitation, documented in the paper. The author's hypothesis that "attention circuits are probably having a main role" in failure cases is plausible but untested.

### 6.3 Missing Baseline: Random Feature Intervention

There is no reported experiment where randomly selected features (rather than labeled supernodes) are ablated/amplified. This control would establish whether the observed effects are specific to the labeled features or arise from any sufficiently large perturbation to the feature space.

### 6.4 Missing Baseline: Shuffled Labels

There is no experiment where supernode labels are randomly shuffled (e.g., swapping the "Texas" label with the "California" label) before running interventions. This would test whether the label-concept alignment matters or whether the intervention effect is purely structural.

### 6.5 Intervention Multiplier Sensitivity

The default multipliers (M_ablate = -2, M_amplify = 20) follow Anthropic's empirically calibrated practice (Ameisen et al., 2025, "Unexplained Variance and Choice of Steering Factors"), which documents three structural reasons for large factors: incomplete CLT dictionaries, inexhaustive supernode membership, and incomplete cross-layer effect capture. The asymmetry reflects different operational requirements: ablation reverses an already-active feature, while amplification must inject a feature that had near-zero activation on the original prompt, requiring much larger magnitude to overcome the model's prior.

Despite this justification, no systematic sweep of these parameters is reported across domains. The same values are used for all datasets despite potentially different feature activation scales. An ablation-only vs. amplification-only decomposition would clarify whether both operations contribute independently (Section 7.5), and a multiplier sweep (Section 7.4) would characterize the sensitivity curve.

### 6.6 Domain Performance Variance

The dramatic domain gradient in output success -- using strict exact match for comparability: USA (38.8%) > books (36.7%) > products (24.2%) > sounds (3.3%) > paintings (1.1%) -- is partially explained by CLT error node density (see Section 4.1 domain gradient analysis). Notably, rank-based flip@0 is near-universal across all domains (90--98%) except sounds (33.3%), so the domain gradient manifests in output quality and gap closure, not in initial rank reordering. Additional unexplained factors likely include circuit complexity, training data frequency, and the degree to which the relevant computation is mediated by attention circuits (invisible to this pipeline). Tracking error node density as an explicit per-entity quality metric would allow filtering low-quality graphs before swap experiments.

### 6.7 Statistical Methodology

No formal statistical tests are applied anywhere in the pipeline. All comparisons are descriptive (means, rates, percentages). Given the sample sizes (2,407 swaps for USA, 240 for books), standard statistical inference (e.g., bootstrap confidence intervals, permutation tests) would be straightforward and informative.

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

4. **Interventions on labeled supernodes produce entity-specific logit shifts**: USA states show 90.2% flip@0, 64.5% state-correct outcomes, 3.79 mean gap closure. Books/authors show strong effects (85% suppression, 96.7% flip@0, 46.7% T5). However, rank-based flip@0 is near-universal (~90--98%) across all domains, indicating this metric reflects the mechanical effect of ablation+amplification rather than meaningful steering success. Gap closure (3.79 for USA vs 0.04--0.45 for others) is the better discriminator. The entity-specificity of outcomes (correct target state, not random states) is structural evidence of level-2 causal alignment, but quantitative specificity (vs. random features) is not yet established.

5. **Suppression via ablation works broadly**: 70--100% suppression across all domains, indicating that features identified as source-relevant are genuinely causally involved in producing the source output.

6. **Trajectory analysis provides continuous evidence beyond exact match**: For USA states, the 51-point gap between flip@0 (90.2%) and T5 (38.8%) shows substantial partial success invisible to binary evaluation, backed by meaningful gap closure (3.79). For non-geographic domains, the near-universal flip@0 (~96--98%) with near-zero gap closure (0.04--0.45) reveals that the rank-based flip metric is too permissive to distinguish meaningful from mechanical rank reordering. Gap closure is the better discriminator of genuine causal leverage.

### Level 2 to Level 3 gap -- CRITICAL OPEN QUESTIONS

7. **Label specificity**: Without random-feature and label-permutation controls, we cannot quantify how much of the observed causal leverage is specific to the labeled features vs. arising from any sufficiently large perturbation. The entity-specificity of outcomes is suggestive but not quantitatively proven.

8. **Domain generalization**: Output success degrades with circuit complexity. Using strict exact match for cross-domain comparability: USA (38.8%) > books (36.7%) > products (24.2%) > sounds (3.3%) > paintings (1.1%). The gradient correlates with CLT error node density (USA ~365 avg vs sounds ~611 avg), suggesting that reconstruction quality is a major limiting factor. Rank-based flip@0 is near-universal (~90--98%) and does not track this gradient -- only gap closure (3.79 for USA vs 0.04--0.45 for non-geographic) faithfully reflects the domain performance disparity. The method's operating envelope for producing correct outputs is narrower than the multi-domain framing suggests. Note: T5 rates (which use domain-specific fuzzy matching) do not preserve this ordering -- books T5 (46.7%) exceeds USA T5 (38.8%) due to the more generous word-level matching in non-geographic domains (see Section 4.1 comparability note).

9. **Frozen-attention graph / unfrozen-attention intervention asymmetry**: Features were selected from graphs computed with frozen attention, but tested with unfrozen attention. This means the attribution graph and the intervention operate under different model dynamics, creating an uncharacterized source of discrepancy.

### Level 3 -- Full Mechanistic Explanation: NOT CLAIMED, NOT ESTABLISHED

10. **The classification thresholds carve natural computational joints**: No sensitivity analysis. Informally validated on a limited set.

11. **The backbone-and-specialization hierarchy is general**: Supported by one circuit pair (geographic). Not tested for non-factual tasks.

12. **The method captures the model's internal algorithm**: Not claimed by this work, and rightly so. The labels are behavioral abstractions, not ontological identifications of latent variables.

### Overall Assessment

This work makes a credible case for semi-automated, operationally meaningful circuit interpretation via supernode-level behavioral abstractions and entity-specific causal interventions, especially in favorable factual domains. Its main remaining limitation is not lack of promise but lack of specificity controls: the current evidence supports downstream causal leverage more strongly than fully correct mechanistic labeling. The three priority experiments (random-feature control, label permutation, token-overlap stratification) represent the critical path from a strong case of causal leverage to a strong case of label specificity.

The work is positioned correctly within the field's trajectory: less emphasis on the metaphysics of features, more emphasis on the class of interventions a description supports and the type of generalization it permits. The honest scope is: *a pipeline that generates operationally useful behavioral hypotheses about circuit features, with demonstrated entity-specific causal leverage in single-hop factual domains with low CLT reconstruction error. Interventions mechanically achieve rank-based logit flips across all domains, but meaningful output redirection (measured by gap closure and T5 rate) degrades with circuit complexity and error node density*.

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

*Report generated from analysis of the full attribution-graph-probing codebase, including all scripts, configurations, output data, paper sections, and validation summaries. Revised to incorporate adversarial review feedback, recent literature context, and data reconciliation (2026-03-20) aligning all reported metrics with live per-swap JSON data.*
