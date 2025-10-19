# Metrics Glossary

Complete reference for all metrics used in the EDA app.

## Feature-Level Metrics (Phase 1)

### Semantic Metrics

#### `mean_consistency`
- **Definition**: Average cosine similarity between feature activation vector and label embedding across all prompts
- **Formula**: `mean(cosine_similarity(feature_activation, label_embedding))` for all prompts
- **Range**: [0, 1]
- **Interpretation**: 
  - High (>0.7): Feature consistently aligns with target concept
  - Medium (0.4-0.7): Moderate semantic alignment
  - Low (<0.4): Weak or inconsistent alignment
- **Use case**: Identify semantically stable features

#### `max_affinity`
- **Definition**: Peak (maximum) cosine similarity observed between feature and label
- **Formula**: `max(cosine_similarity(feature_activation, label_embedding))` across all prompts
- **Range**: [0, 1]
- **Interpretation**: 
  - High (>0.8): Feature has strong semantic alignment in at least one context
  - Medium (0.6-0.8): Moderate peak alignment
  - Low (<0.6): Never strongly aligns with target
- **Use case**: Admission threshold for quality residuals (tau_aff)

#### `conditional_consistency`
- **Definition**: Consistency computed only when feature is active (above adaptive threshold)
- **Formula**: `mean(cosine_similarity)` for activations > `activation_threshold`
- **Range**: [0, 1]
- **Interpretation**: More robust than `mean_consistency` for sparse features
- **Use case**: Better measure for features that activate rarely but meaningfully

#### `consistency_std`
- **Definition**: Standard deviation of consistency scores across prompts
- **Range**: [0, 1]
- **Interpretation**:
  - Low (<0.2): Stable, consistent behavior
  - High (>0.4): Variable, context-dependent behavior
- **Use case**: Identify features with unstable semantics

#### `label_affinity`
- **Definition**: Weighted average of cosine similarities, prioritizing higher values
- **Range**: [0, 1]
- **Use case**: Alternative to mean_consistency, emphasizes peak alignments

### Causal Metrics

#### `node_influence`
- **Definition**: Causal influence on target logits via backward propagation through attribution graph
- **Formula**: Recursive backward propagation from logits:
  ```
  influence[node] = sum(edge_weight[parent→node] × influence[parent]) for all parents
  influence[logit_nodes] = 1.0 (base case)
  ```
- **Range**: Typically [-0.5, 0.5], can be negative
- **Interpretation**:
  - Positive: Feature increases target logit probability
  - Negative: Feature suppresses target logit
  - High absolute value: Strong causal impact
- **Use case**: Seed selection, tier classification (HIGH/MED/LOW)

#### `output_impact` (logit_influence)
- **Definition**: Direct influence on output logits (sum of edge weights to final logits)
- **Formula**: `sum(edge_weight[feature→logit])` for all target logits
- **Range**: Typically [0, 0.1], rarely higher
- **Interpretation**: Direct causal path strength to output
- **Use case**: Admission threshold (tau_inf), "Say Austin" seed identification

#### `causal_in_degree`
- **Definition**: Number of incoming causal edges (parents) with weight > tau_edge
- **Range**: [0, N] where N = number of features in earlier layers
- **Interpretation**: How many features causally influence this one
- **Use case**: Identify computational hubs (high in-degree)

#### `causal_out_degree`
- **Definition**: Number of outgoing causal edges (children) with weight > tau_edge
- **Range**: [0, N] where N = number of features in later layers
- **Interpretation**: How many features this one causally influences
- **Use case**: Identify propagation sources (high out-degree)

#### `top_parents`
- **Definition**: List of top 5 parent features by edge weight
- **Format**: `[(parent_key, edge_weight), ...]`
- **Use case**: Causal neighborhood analysis, bootstrap growth candidates

#### `top_children`
- **Definition**: List of top 5 child features by edge weight
- **Format**: `[(child_key, edge_weight), ...]`
- **Use case**: Causal neighborhood analysis, forward propagation

### Contextual Metrics

#### `layer`
- **Definition**: Transformer layer where feature is located
- **Range**: [0, 25] for Gemma-2B-it
- **Interpretation**:
  - Low layers (0-8): Syntax, structure, basic patterns
  - Mid layers (9-17): Intermediate concepts, composition
  - High layers (18-25): Abstract semantics, task-specific concepts

#### `position`
- **Definition**: Token position in sequence where feature activates
- **Range**: [0, seq_length]
- **Interpretation**: Context-dependent, varies by prompt

#### `most_common_peak`
- **Definition**: Token where feature activates most frequently across prompts
- **Use case**: Token-based clustering, semantic interpretation

#### `activation_threshold`
- **Definition**: Adaptive threshold for considering feature "active"
- **Formula**: `min(percentile_75(activations), otsu_threshold(activations))`
- **Use case**: Filtering activations for `conditional_consistency`

---

## Supernode-Level Metrics (Phase 2)

### `final_coherence`
- **Definition**: Internal consistency of supernode after growth
- **Formula**: 
  ```
  coherence = 0.30 × consistency_homogeneity +
              0.20 × token_diversity_score +
              0.20 × layer_span_score +
              0.30 × causal_edge_density
  ```
- **Components**:
  - `consistency_homogeneity`: `1 - std(conditional_consistency)` across members
  - `token_diversity_score`: `1 - |diversity - 0.5|` where diversity = unique_tokens/total_tokens
  - `layer_span_score`: `1 - (max_layer - min_layer) / 15`
  - `causal_edge_density`: ratio of actual edges to possible edges (weight > tau_edge)
- **Range**: [0, 1]
- **Interpretation**:
  - High (>0.6): Tight, coherent supernode
  - Medium (0.4-0.6): Acceptable coherence
  - Low (<0.4): Loose, potentially over-grown
- **Use case**: Growth stopping criterion (min_coherence threshold)

### `growth_iterations`
- **Definition**: Number of members added during growth (excluding seed)
- **Range**: [0, max_iterations]
- **Interpretation**: 
  - High: Supernode found many compatible candidates
  - Low: Selective growth or early stopping
- **Use case**: Identify supernodes that grew extensively

### `seed_logit_influence`
- **Definition**: `output_impact` of the seed feature
- **Use case**: Prioritize supernodes with high-influence seeds

### `total_influence_score`
- **Definition**: Sum of `node_influence` across all members
- **Interpretation**: Aggregate causal impact of supernode
- **Use case**: Rank supernodes by causal importance

### `edge_density`
- **Definition**: Density of causal edges within supernode
- **Formula**: `actual_edges / possible_edges` where edges have weight > tau_edge
- **Range**: [0, 1]
- **Interpretation**:
  - High (>0.3): Tightly causally connected
  - Low (<0.1): Sparse causal structure
- **Use case**: Validate causal coherence

### `narrative_theme`
- **Definition**: Semantic theme inferred from dominant tokens
- **Examples**: "Geographic Context", "Relational Structure", "Semantic Core"
- **Use case**: Human-interpretable supernode labels

---

## Compatibility Metrics (Phase 2 Growth)

### `causal_compatibility`
- **Definition**: Causal alignment between seed and candidate
- **Formula**:
  ```
  causal_compat = 0.42 × direct_edge_score +
                  0.33 × jaccard_neighborhood +
                  0.25 × position_proximity
  ```
- **Components**:
  - `direct_edge_score`: `min(1, edge_weight / tau_edge_strong)` with 1.5x boost if edge_weight > 0.1
  - `jaccard_neighborhood`: Jaccard similarity of top_parents/children sets
  - `position_proximity`: `1 - |pos_seed - pos_candidate| / 5`
- **Range**: [0, 1]

### `semantic_compatibility`
- **Definition**: Semantic alignment between seed and candidate
- **Formula**:
  ```
  semantic_compat = 0.50 × token_compatibility +
                    0.25 × layer_proximity +
                    0.25 × consistency_compatibility
  ```
- **Components**:
  - `token_compatibility`: 
    - 1.0 if same token
    - 0.8 if both geographic tokens
    - 0.7 if both relational tokens
    - 0.3 otherwise
  - `layer_proximity`: `1 - |layer_seed - layer_candidate| / 10`
  - `consistency_compatibility`: `1 - |consistency_seed - consistency_candidate|`
- **Range**: [0, 1]

### `total_compatibility`
- **Definition**: Weighted combination of causal and semantic
- **Formula**: `causal_weight × causal_compat + (1 - causal_weight) × semantic_compat`
- **Range**: [0, 1]
- **Use case**: Acceptance criterion for growth (compare to threshold_bootstrap or threshold_normal)

---

## Thresholds (Phase 3)

### `tau_inf`
- **Definition**: Minimum `output_impact` for admission as quality residual
- **Default**: 0.000194 (robust threshold from data distribution)
- **Interpretation**: Features below this have negligible direct impact on logits
- **Use case**: Filter out low-influence features

### `tau_aff`
- **Definition**: Minimum `max_affinity` for admission
- **Default**: 0.65
- **Interpretation**: Features below this never strongly align with target semantically
- **Use case**: Ensure semantic quality of residuals

### `tau_inf_very_high`
- **Definition**: Special threshold for `<BOS>` token features
- **Default**: 0.025
- **Interpretation**: `<BOS>` features need higher influence to be admitted
- **Use case**: Prevent structural tokens from cluttering residuals

### `tau_edge_strong`
- **Definition**: Threshold for "strong" causal edge
- **Default**: 0.05
- **Use case**: Boost compatibility score for strong edges

### `tau_edge_bootstrap`
- **Definition**: Minimum edge weight for bootstrap phase
- **Default**: 0.03
- **Use case**: Bootstrap phase uses only edges above this

---

## Cluster Metrics (Phase 3)

### `cluster_signature`
- **Definition**: Multi-dimensional identifier for cluster
- **Format**: `"{layer_group}_{token_class}_{causal_tier}"`
- **Example**: `"L6-8_Dallas_HIGH"`
- **Components**:
  - `layer_group`: e.g., "L6-8" (span=3)
  - `token_class`: structural token, semantic token, or "RARE"
  - `causal_tier`: "HIGH", "MED", or "LOW" based on node_influence
- **Use case**: Identify cluster type

### `causal_connectivity`
- **Definition**: Average edge density within cluster
- **Formula**: `mean(edge_density)` for all pairs in cluster
- **Range**: [0, 1]
- **Use case**: Validate computational clusters have some causal structure

### `jaccard_similarity`
- **Definition**: Set similarity between two clusters
- **Formula**: `|A ∩ B| / |A ∪ B|`
- **Range**: [0, 1]
- **Use case**: Merge criterion (merge if Jaccard > jaccard_threshold)

---

## Coverage Metrics (Global)

### `coverage_percentage`
- **Definition**: Percentage of all features covered by supernodes
- **Formula**: `(total_features_covered / original_features) × 100`
- **Range**: [0, 100]
- **Target**: >75%

### `quality_coverage_percentage`
- **Definition**: Coverage of quality features only
- **Formula**: `(features_in_supernodes / (features_in_supernodes + processable_features)) × 100`
- **Range**: [0, 100]
- **Interpretation**: Excludes garbage features from denominator
- **Target**: >80%

### `garbage_features_identified`
- **Definition**: Features below both tau_inf AND tau_aff
- **Interpretation**: Not processable, low quality
- **Use case**: Understand data quality

### `processable_features`
- **Definition**: Quality residuals not yet in supernodes
- **Interpretation**: Candidates for further clustering
- **Use case**: Monitor remaining work

---

## Cross-Prompt Validation Metrics

### `n_active_members`
- **Definition**: Number of supernode members active on a specific prompt
- **Range**: [0, n_members]
- **Interpretation**: Higher = supernode more active on that prompt

### `avg_consistency`
- **Definition**: Average consistency of active members on a prompt
- **Range**: [0, 1]
- **Interpretation**: Semantic alignment quality on that prompt

### `consistency_std`
- **Definition**: Standard deviation of consistency across active members
- **Range**: [0, 1]
- **Interpretation**: Higher = more variable behavior on that prompt

### Robustness Metrics

#### `avg_active_members`
- **Definition**: Mean of `n_active_members` across all prompts
- **Interpretation**: Average activation level

#### `std_active_members`
- **Definition**: Standard deviation of `n_active_members` across prompts
- **Interpretation**: 
  - Low: Stable, robust supernode
  - High: Variable, prompt-dependent supernode
- **Use case**: Identify most/least robust supernodes

---

## Interpretation Guidelines

### Feature Quality Tiers

| Tier | Criteria | Interpretation |
|------|----------|----------------|
| **High Quality** | `output_impact > 0.001` OR `max_affinity > 0.75` | Strong semantic or causal signal |
| **Medium Quality** | `output_impact > tau_inf` OR `max_affinity > tau_aff` | Processable, admitted as residual |
| **Low Quality** | Below both thresholds | Garbage, excluded |

### Supernode Quality

| Quality | `final_coherence` | `edge_density` | Interpretation |
|---------|-------------------|----------------|----------------|
| **Excellent** | >0.6 | >0.3 | Tight, well-connected |
| **Good** | 0.5-0.6 | 0.2-0.3 | Acceptable |
| **Fair** | 0.4-0.5 | 0.1-0.2 | Loose but valid |
| **Poor** | <0.4 | <0.1 | Over-grown or weak |

### Causal Influence Tiers

| Tier | `node_influence` | Interpretation |
|------|------------------|----------------|
| **HIGH** | >0.10 | Strong causal impact |
| **MED** | 0.01-0.10 | Moderate impact |
| **LOW** | <0.01 | Weak impact |

---

## Common Formulas

### Cosine Similarity
```
cosine_sim(A, B) = (A · B) / (||A|| × ||B||)
```
Range: [-1, 1], typically [0, 1] for feature activations

### Jaccard Similarity
```
Jaccard(A, B) = |A ∩ B| / |A ∪ B|
```
Range: [0, 1]

### Backward Propagation (Node Influence)
```
influence[node] = Σ(edge_weight[parent→node] × influence[parent])
```
Base case: `influence[logit] = 1.0`

### Edge Density
```
density = actual_edges / possible_edges
where possible_edges = n × (n-1) for directed graph
```

---

## References

- **Anthropological Analysis**: `scripts/02_anthropological_basic.py`
- **Causal Metrics**: `scripts/causal_utils.py`
- **Supernode Growth**: `scripts/04_cicciotti_supernodes.py`
- **Residual Clustering**: `scripts/05_final_optimized_clustering.py`
- **Full Documentation**: `docs/supernode_labelling/`

---

**Last Updated**: 2025-10-18  
**Version**: 1.0.0


