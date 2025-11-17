# USA States Capital Prediction Validation Methodology

## Overview
This document outlines a systematic validation approach using feature interventions to test the causal relationships between geographic concepts and capital city predictions in the 50 USA states dataset.

## Theoretical Foundation
Based on Anthropic's circuit tracing methodology, we use:
- **Constrained patching** across layer ranges to avoid second-order effects
- **Supernode interventions** treating related features as semantic units
- **Multiplicative steering** with factors (-2, +2, +8) instead of ablation
- **Cross-validation matrix** testing all 50×50 state combinations

## Intervention Matrix Design

### 1. Baseline Assessment
For each state-city pair (e.g., "The capital of the state containing Colorado Springs is"):
- Record top-5 predicted tokens and their probabilities
- Identify the target capital (e.g., Denver) and its rank/logit value
- Document successful vs failed predictions

### 2. Supernode Mapping Strategy

#### Geographic Supernodes
Create semantic groupings based on:
- **State Identity Features**: Features responding to state names ("Texas", "California", etc.)
- **Capital City Features**: Features responding to capital names ("Austin", "Denver", etc.)
- **Geographic Relationship Features**: Features encoding state-capital relationships
- **City Type Features**: Features distinguishing capitals from other cities

#### Mapping Process
1. **Feature Identification**: Use Neuronpedia's feature visualization to identify relevant features
2. **Semantic Clustering**: Group features with similar activation patterns
3. **Supernode Creation**: Create 50 supernodes (one per state) containing state-related features
4. **Cross-validation**: Ensure supernodes are state-specific, not city-specific

### 3. Intervention Protocol

#### A. Targeted Ablation Tests
For each state S with capital C:
- **Prompt**: "The capital of the state containing [MajorCity] is"
- **Intervention**: Suppress (-2x) supernode for state S
- **Expected**: Significant decrease in probability of capital C
- **Metric**: Δlogit(C) should be negative and substantial

#### B. Cross-State Steering Tests
For each pair (SourceState, TargetState):
- **Prompt**: "The capital of the state containing [SourceCity] is"
- **Intervention**: Amplify (+2x or +8x) supernode for TargetState
- **Expected**: Increase in probability of TargetState's capital
- **Metric**: Δlogit(TargetCapital) should be positive

#### C. False Positive Controls
- **Intervention**: Amplify unrelated state supernodes
- **Expected**: Minimal effect on correct capital prediction
- **Purpose**: Validate specificity of geographic relationships

### 4. Validation Matrix Structure

#### Primary Matrix (50×50)
```
Rows: Source states (where prompt city is located)
Cols: Target states (whose supernode is intervened)
Cells: Δlogit(TargetCapital) when steering TargetState supernode

Example cell [Texas, Colorado]:
- Prompt: "The capital of the state containing Dallas is"
- Intervention: +2x Colorado supernode
- Measure: Change in logit(Denver)
```

#### Secondary Matrix (50×1)
```
Rows: Each state
Cols: Ablation effect on own capital
Cells: Δlogit(OwnCapital) when suppressing own state supernode
```

### 5. Implementation Pipeline

#### Phase 1: Supernode Identification
1. **Feature Extraction**: Extract all features from each state's graph
2. **Semantic Analysis**: Use Neuronpedia visualization to identify state-relevant features
3. **Clustering**: Group features by activation patterns and semantic similarity
4. **Validation**: Ensure supernodes are state-specific

#### Phase 2: Intervention Execution
1. **API Integration**: Use Neuronpedia steering API with parameters:
   - modelId: "gemma-2-2b"
   - steer_method: "SIMPLE_ADDITIVE"
   - strength_multiplier: [-2, 2, 8]
   - n_tokens: 1 (focus on next token prediction)

2. **Systematic Testing**:
   - Run all 50×50 steering combinations
   - Run all 50 ablation tests
   - Record pre/post intervention logits

#### Phase 3: Analysis Framework

##### Success Criteria
- **Causal Validity**: Ablation of state S should significantly reduce P(Capital_C)
- **Specificity**: Steering unrelated states should have minimal effect
- **Directionality**: Steering state T should increase P(Capital_T)
- **Magnitude**: Effects should be proportional to steering strength

##### Statistical Metrics
- **Effect Size**: Cohen's d for logit changes
- **False Discovery Rate**: Control for multiple comparisons
- **Consistency**: Effects should replicate across similar prompts
- **Gradual Scaling**: Effects should scale with steering magnitude

### 6. Expected Outcomes

#### Strong Validation
- Clear causal chains from state concepts to capital predictions
- High specificity in geographic relationships
- Replicable effects across the 50×50 matrix

#### Weak Validation
- Mixed or weak intervention effects
- Non-specific responses to steering
- Inconsistent patterns across states

#### Failure Modes
- Supernodes don't capture geographic concepts
- Interventions affect general language modeling
- Relationships are correlational, not causal

### 7. Technical Implementation

#### API Usage Pattern
```python
# Example intervention call
payload = {
    "prompt": "The capital of the state containing Dallas is",
    "modelId": "gemma-2-2b",
    "features": [
        {
            "modelId": "gemma-2-2b",
            "layer": "20-gemmascope-res-16k",
            "index": [texas_supernode_features],
            "strength": -2.0
        }
    ],
    "temperature": 0.0,
    "n_tokens": 1,
    "steer_method": "SIMPLE_ADDITIVE"
}
```

#### Data Collection
- Pre-intervention: Baseline logits for all 50 capitals
- Post-intervention: Logits after each steering/ablation
- Control: Random feature interventions for baseline noise

### 8. Validation Timeline

#### Week 1: Supernode Identification
- Complete feature analysis for all 50 states
- Create validated supernode mappings
- Test supernode coherence

#### Week 2: Intervention Testing
- Execute 50 ablation tests
- Execute 50×50 steering matrix
- Collect all logit data

#### Week 3: Analysis & Validation
- Statistical analysis of intervention effects
- Generate validation report
- Identify failure modes and improvements

### 9. Success Metrics

#### Primary Metrics
- **Causal Strength**: Average |Δlogit| > 1.0 for ablation tests
- **Specificity**: Cross-state steering effects < 0.2 |Δlogit|
- **Consistency**: >80% of interventions show expected direction

#### Secondary Metrics
- **Feature Purity**: Supernodes contain >70% state-relevant features
- **Reproducibility**: Effects replicate across prompt variations
- **Scalability**: Effects scale appropriately with steering magnitude

This methodology provides a rigorous framework for validating whether the model's geographic knowledge is causally structured and can be systematically manipulated through feature interventions.
