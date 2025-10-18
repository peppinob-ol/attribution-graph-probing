# Tooltips & Documentation Changelog

## Summary

Added comprehensive tooltips and help text throughout the EDA app to explain all metrics, parameters, and calculations in English.

## Changes Made

### 1. **Phase 2 - Supernodes** (`pages/03_Phase2_Supernodes.py`)

#### Parameters with Tooltips:
- **Enable dry-run**: Explains interactive parameter tuning
- **Causal weight** (0.4-0.8): 
  - Formula: `semantic_weight = 1 - causal_weight`
  - Effect: Higher = prioritize causal graph connections
  - Default: 0.60 (60% causal, 40% semantic)
- **tau_edge_strong** (0.02-0.10):
  - Threshold for "strong" edges
  - Edges > threshold get 1.5x boost
  - Default: 0.05
- **Bootstrap threshold** (0.1-0.5):
  - Minimum compatibility for bootstrap phase (2-hop causal)
  - Lower = more permissive
  - Default: 0.30
- **Normal threshold** (0.3-0.7):
  - Minimum compatibility for normal phase (causal+semantic)
  - Higher = smaller, more selective supernodes
  - Default: 0.45
- **Min coherence** (0.3-0.8):
  - Stop growth if coherence drops below
  - Formula: `0.30×consistency + 0.20×diversity + 0.20×layer_span + 0.30×edge_density`
  - Default: 0.50

#### Filters with Tooltips:
- **Theme filter**: Filter by narrative theme (inferred from tokens)
- **Min members**: Minimum features in supernode
- **Min coherence**: Minimum final_coherence score

#### Caption Added:
- Explanation of Cicciotti supernodes methodology

---

### 2. **Phase 3 - Residuals** (`pages/05_Phase3_Residuals.py`)

#### Admission Thresholds:
- **tau_inf** (logit influence):
  - Definition: Minimum output_impact for admission
  - Computation: Backward propagation from logits
  - Effect: Lower = more features admitted
  - Default: 0.000194 (robust threshold)
- **tau_aff** (max affinity):
  - Definition: Minimum peak cosine similarity
  - Computation: `max(cosine_sim(feature, label))`
  - Effect: Higher = only strong semantic alignment
  - Default: 0.65
- **tau_inf_very_high** (<BOS>):
  - Special filter for structural tokens
  - Prevents low-influence <BOS> from cluttering
  - Default: 0.025

#### Clustering Parameters:
- **Min cluster size** (2-10):
  - Minimum members for valid cluster
  - Higher = fewer, larger clusters
  - Default: 3
- **Layer group span** (2-5):
  - Consecutive layers grouped together
  - Example: span=3 → L0-2, L3-5, L6-8
  - Larger = coarser grouping
  - Default: 3
- **Node influence HIGH** (0.05-0.20):
  - Threshold for HIGH causal tier
  - Computation: Backward propagation score
  - Default: 0.10
- **Node influence MED** (0.005-0.05):
  - Threshold for MED tier (between HIGH and LOW)
  - Default: 0.01
- **Min frequency ratio** (0.01-0.05):
  - Minimum frequency for "semantic" token classification
  - Tokens below = "RARE"
  - Also enforces absolute min = 3
  - Default: 0.02 (2%)

#### Merge Parameters:
- **Jaccard threshold** (0.5-0.9):
  - Minimum similarity to merge clusters
  - Formula: `Jaccard(A,B) = |A ∩ B| / |A ∪ B|`
  - Higher = more distinct clusters
  - Lower = aggressive merging
  - Default: 0.70

#### Info Boxes Added:
- Explanation of quality residuals concept
- Admission criteria (tau_inf OR tau_aff)

#### Metrics with Tooltips:
- **Total admitted**: Features passing thresholds
- **Used in cicciotti**: Already in semantic supernodes
- **Quality residuals**: Candidates for clustering

---

### 3. **Phase 1 - Features** (`pages/02_Phase1_Features.py`)

#### Filters with Tooltips:
- **Layer range**: 
  - Explanation: Layers = depth in transformer
  - Lower layers = syntax/structure
  - Higher layers = semantics
- **Token filter**:
  - Definition: most_common_peak token
  - Use: Focus on specific concepts

#### Archetype Info Box:
- **Semantic Anchors**: High consistency, strong alignment
- **Stable Contributors**: Consistent, moderate influence
- **Contextual Specialists**: High max_affinity, variable consistency
- **Computational Helpers**: High causal, lower semantic
- **Outliers**: Low on most metrics

---

### 4. **Feature Panel** (`components/feature_panel.py`)

All metrics now have tooltips:

- **Layer**: Transformer layer (0-25 for Gemma-2B)
- **Position**: Token position in sequence
- **Mean Consistency**: 
  - Definition: Average cosine similarity with label
  - Range: [0,1]
  - Interpretation: Higher = more consistent alignment
- **Max Affinity**:
  - Definition: Peak cosine similarity
  - Range: [0,1]
  - Interpretation: Strongest alignment observed
- **Conditional Consistency**:
  - Definition: Consistency when feature is active
  - More robust for sparse features
- **Node Influence**:
  - Definition: Causal influence via backward propagation
  - Can be negative
  - Higher absolute = stronger impact
- **Output Impact**:
  - Definition: Direct influence on logits
  - From attribution graph edges to final logits
  - Range: typically [0, 0.1]
- **Peak Token**:
  - Definition: Token with most frequent activation

---

### 5. **Supernode Panel** (`components/supernode_panel.py`)

All metrics now have tooltips:

- **N membri**: Number of features in supernode
- **Seed layer**: Layer of initiating seed feature
- **Final coherence**:
  - Formula: `0.30×consistency + 0.20×diversity + 0.20×layer_span + 0.30×edge_density`
  - Range: [0,1]
- **Growth iterations**: Members added during growth
- **Narrative theme**: Inferred from dominant tokens
- **Seed logit influence**: output_impact of seed
- **Total influence**: Sum of node_influence across members
- **Edge density**:
  - Definition: Ratio of actual edges to possible edges
  - Range: [0,1]
  - Note: "N/A" if graph unavailable

---

### 6. **Overview** (`pages/01_Overview.py`)

All KPIs now have tooltips:

- **Total supernodes**: semantic + computational
- **Semantic**: Cicciotti supernodes (coherent + causal)
- **Computational**: Multi-dimensional residual clusters
- **Features covered**: Total in any supernode
- **Total coverage**: 
  - Formula: `(covered / original) × 100`
- **Quality coverage**:
  - Coverage of quality features only
  - Excludes garbage
- **Garbage identified**:
  - Features below both tau_inf AND tau_aff
  - Not processable
- **Processable**:
  - Quality features not in supernodes
  - Clustering candidates
- **Semantic avg coherence**:
  - Average final_coherence of semantic supernodes
  - Range: [0,1]
- **Computational diversity**:
  - Distinct cluster signatures
  - (layer_group × token × causal_tier)

---

### 7. **Cross-Prompt** (`pages/04_CrossPrompt.py`)

#### Metric Selector with Tooltip:
- **n_active_members**: Members active on each prompt
- **avg_consistency**: Average consistency of active members
- **consistency_std**: Variability (higher = more variable)

#### Caption Added:
- How to read heatmap
- Color interpretation
- Empty cells = not active

---

### 8. **Main App** (`app.py`)

#### Sidebar Updates:
- Changed to English
- Added references to:
  - Metrics glossary: `eda/METRICS_GLOSSARY.md`
  - Quick guide: `eda/GUIDA_RAPIDA.md`
  - Full docs: `docs/supernode_labelling/`
- Added caption: "💡 Hover over metrics and parameters for explanations"

---

## New Documentation Files

### 1. **METRICS_GLOSSARY.md**
Complete reference for all metrics with:
- Definitions
- Formulas
- Ranges
- Interpretations
- Use cases

Organized by:
- Feature-level metrics (semantic, causal, contextual)
- Supernode-level metrics
- Compatibility metrics
- Thresholds
- Cluster metrics
- Coverage metrics
- Cross-prompt validation metrics

Includes:
- Common formulas (cosine similarity, Jaccard, backward propagation)
- Interpretation guidelines
- Quality tiers tables

---

### 2. **INTERPRETATION_GUIDE.md**
Practical guide with:
- **Decision trees**: "Is this feature important?", "Is this supernode high quality?"
- **Scenario analysis**: 6 detailed examples with interpretations
- **Red flags**: Tables of warning signs and actions
- **Optimization strategies**: For coverage, quality, or balance
- **Advanced interpretation**: Compatibility score breakdown, coherence analysis
- **Troubleshooting**: Common issues with diagnosis steps and solutions

---

### 3. **TOOLTIPS_CHANGELOG.md** (this file)
Complete changelog of tooltip additions

---

## Implementation Details

### Tooltip Syntax
All tooltips use Streamlit's `help` parameter:

```python
st.metric("Metric name", value, help="Explanation text")
st.slider("Parameter", min, max, default, help="Explanation text")
st.selectbox("Option", choices, help="Explanation text")
```

### Help Text Structure
Each tooltip includes:
1. **Definition**: What the metric/parameter is
2. **Formula** (if applicable): How it's calculated
3. **Range**: Expected values
4. **Interpretation**: What values mean
5. **Default** (for parameters): Standard value
6. **Effect** (for parameters): What changing it does

### Language
All tooltips and help text are in **English** as requested.

---

## Testing Checklist

- [x] All Phase 2 parameters have tooltips
- [x] All Phase 3 parameters have tooltips
- [x] All Phase 1 filters have tooltips
- [x] All feature metrics have tooltips
- [x] All supernode metrics have tooltips
- [x] All Overview KPIs have tooltips
- [x] Cross-prompt metrics explained
- [x] Info boxes added where appropriate
- [x] Captions added to complex visualizations
- [x] Main app sidebar updated with documentation links
- [x] METRICS_GLOSSARY.md created
- [x] INTERPRETATION_GUIDE.md created
- [x] README.md updated with tooltip usage section
- [x] No linter errors

---

## User Experience

Users can now:
1. **Hover over any metric** to see definition, range, and interpretation
2. **Hover over any parameter** to see formula, effect, and default
3. **Read info boxes** for conceptual explanations
4. **Consult METRICS_GLOSSARY.md** for comprehensive reference
5. **Use INTERPRETATION_GUIDE.md** for practical examples and troubleshooting
6. **Follow decision trees** to make informed choices

---

## Future Enhancements

Potential additions:
- [ ] Interactive formula visualizations (e.g., show coherence breakdown on hover)
- [ ] Contextual help button that opens relevant section of METRICS_GLOSSARY.md
- [ ] Tooltip for each column in dataframes
- [ ] Video tutorials linked from tooltips
- [ ] Glossary search function in sidebar

---

**Completed**: 2025-10-18  
**Version**: 1.0.0  
**Language**: English (tooltips and new docs)


