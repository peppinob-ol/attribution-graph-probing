# Strategies for Universal Swap Success

Based on the analysis showing **r = -0.918** correlation between state supernode feature count and source tier difficulty, the core problem is:

> **Too many features in the state supernode creates a "defensive wall" that resists steering.**

## Current Mechanism

```
extract_ct_supernode():
    supernode_name.contains("Michigan")  # Case-insensitive substring match
    -> Returns ALL features matching
    -> ALL features get ablated/amplified
```

## Problem States

| State | State Features | Source Tier | Issue |
|-------|---------------|-------------|-------|
| New York | 180 | 1.00 | Impossible to escape |
| Colorado | 175 | 2.33 | Very defensive |
| Oregon | 45 | 4.00 | Easy (but poor target) |

---

## STRATEGY 1: Grouping Refinements

### 1A. Finer-grained supernodes
Instead of one "Michigan" supernode, create:
- `Michigan-state-identity` (general state features)
- `Michigan-capital` (capital-related features)
- `Michigan-cities` (city features)
- `Michigan-geography` (geographic features)

**Implementation**: Modify clustering threshold or add sub-grouping pass.

### 1B. Concept-specific extraction
Only extract features where concept is the PRIMARY label, not just contained:

```python
# Current: substring match
names.str.contains("michigan")  # Matches too broadly

# Better: exact match OR weighted by activation
matches = grouping_df[supernode_col == concept]  # Exact primary match
```

### 1C. Size-capped supernodes
During grouping, cap maximum features per supernode:
```python
MAX_SUPERNODE_SIZE = 50
if len(features) > MAX_SUPERNODE_SIZE:
    # Keep only top-K by influence/activation
    features = sorted(features, key=lambda f: f.influence)[:MAX_SUPERNODE_SIZE]
```

---

## STRATEGY 2: Target Capital, Not State

The key insight: We want to swap CAPITALS, not STATES.

### 2A. Capital-focused ablation
Instead of ablating "Michigan" supernode, ablate "Lansing" supernode:

```python
# Current
pair.from_concept = "Michigan"  # 60 features

# Better
pair.from_concept = "Lansing"  # ~15-20 features
```

**Results from analysis:**
- Michigan: 195 capital features (Lansing-related)
- Georgia: 155 capital features (Atlanta-related)

### 2B. Dual-target strategy
For SOURCE state: ablate CAPITAL supernode only
For TARGET state: amplify CAPITAL supernode only

```yaml
# Config change
swap:
  ablate_concept: capital  # "Lansing" instead of "Michigan"
  amplify_concept: capital  # "Sacramento" instead of "California"
```

---

## STRATEGY 3: Influence-Based Feature Selection

### 3A. Filter by influence on target logit
Only include features that actually affect the target logit prediction:

```python
def extract_ct_supernode_filtered(
    grouping_df, metrics_df, concept, slug,
    min_influence: float = 0.1,  # Only features with >10% influence
    max_features: int = 30,
):
    matches = extract_all_matches(concept)
    
    # Filter by influence
    matches = matches[matches['influence'] > min_influence]
    
    # Cap by count, sorted by influence
    matches = matches.nlargest(max_features, 'influence')
    
    return matches
```

### 3B. Layer-based filtering
Later layers are closer to output, may be more effective:

```python
# Only use features from layers 8+ (closer to logit)
matches = matches[matches['layer'] >= 8]
```

---

## STRATEGY 4: Adaptive Steering Strength

### 4A. State-dependent M_ablate
Scale ablation strength based on state "defensiveness":

```python
state_features = count_state_features(from_state)

if state_features > 150:
    M_ablate = -4.0  # Very defensive, need stronger ablation
elif state_features > 100:
    M_ablate = -3.0
else:
    M_ablate = -2.0  # Standard
```

### 4B. Feature-count-aware amplification
For targets with weak representation, amplify more:

```python
capital_features = count_capital_features(to_state)

if capital_features < 100:
    M_amplify = 30  # Weak target, need stronger boost
else:
    M_amplify = 20  # Standard
```

---

## STRATEGY 5: Causal Path Analysis

### 5A. Graph-based feature selection
Only manipulate features that lie on the causal path to the target logit:

```python
def get_causal_features(graph, target_logit_node):
    """Find features that directly influence the target logit."""
    causal_features = []
    for edge in graph['edges']:
        if edge['target'] == target_logit_node:
            source_node = get_node(edge['source'])
            if source_node['feature_type'] == 'transcoder':
                causal_features.append(source_node)
    return causal_features
```

### 5B. Prune redundant features
If multiple features encode the same concept, keep only the most influential:

```python
# Group by semantic similarity or activation pattern
# Keep top feature per group
```

---

## STRATEGY 6: Iterative Steering

### 6A. Two-pass steering
1. First pass: Light ablation, measure effect
2. Second pass: Adjust strength based on first pass

```python
# Pass 1: Light ablation
result1 = steer(M_ablate=-1.0)
if source_still_present(result1):
    # Pass 2: Stronger
    result2 = steer(M_ablate=-3.0)
```

### 6B. Feedback-driven steering
Monitor steered output and adjust in real-time:

```python
while source_in_output and attempts < 5:
    M_ablate *= 1.5  # Increase strength
    result = steer(M_ablate)
    attempts += 1
```

---

## RECOMMENDED IMPLEMENTATION ORDER

### Phase 1: Quick Wins (config changes only)
1. **Strategy 2A**: Switch to capital-focused extraction
2. **Strategy 4A**: State-dependent M_ablate

### Phase 2: Feature Selection (code changes)
3. **Strategy 3A**: Influence-based filtering
4. **Strategy 3B**: Layer-based filtering
5. **Strategy 1C**: Size-capped supernodes

### Phase 3: Advanced (requires graph analysis)
6. **Strategy 5A**: Causal path analysis
7. **Strategy 1A**: Finer-grained supernodes
8. **Strategy 6**: Iterative steering

---

## Quick Test: Capital-Only Swap

To test if capital-focused extraction helps, modify the swap config:

```yaml
# usa_states_swap.yml
swap:
  concept_type: capital  # NEW: use capital name instead of state
  pairs:
    - [texas_dallas, california_oakland, Austin, Sacramento]  # Explicit capitals
```

Then measure:
- Does ablating "Lansing" (15 features) work better than "Michigan" (60 features)?
- Does New York improve if we ablate "Albany" (140 features) instead of "York" (180 features)?

---

## Metrics to Track

For each strategy:
1. **Feature count** - How many features are manipulated?
2. **Source suppression rate** - Is source info removed?
3. **Target hit rate** - Does target appear?
4. **Tier distribution** - Full tier breakdown

The goal is to find the minimal set of features that achieves reliable steering.

