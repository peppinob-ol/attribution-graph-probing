## 🔬 Causal Validation Guide

### Research Question

**"Do features causally important for the output 'Austin' activate distinctively on semantically related prompts?"**

This page validates whether cross-prompt activation patterns can help identify causally important features.

---

## 📊 Page Structure

### 1. **Causal Importance Calculation**

**Purpose**: Define which features are "causally important" as ground truth.

**Configuration**:
- **Primary metric**:
  - `node_influence`: Backward propagation from logits (default)
  - `output_impact`: Direct logit influence  
  - `combined`: Weighted combination (configurable weight)
  
- **Top percentile**: Features above this percentile are considered "important" (default: 90th)

**Output**:
- Total features, important features, threshold value
- Distribution histogram with percentile line

---

### 2. **Cross-Prompt Activation Analysis**

**Purpose**: Analyze how features activate on different prompts.

**Metrics from `acts_compared.csv`**:
- `nuova_max_label_span`: Peak activation in label span (default)
- `normalized_sum_label`: Average activation in label span
- `nuova_somma_label_span`: Total activation in label span
- `twera_total_in`: Token-weighted edge relevance
- `cosine_similarity`: Pattern similarity with original prompt

**Statistical Test**:
- **Mann-Whitney U Test**: Tests if important features have significantly higher activation
- H1: Important features activate more than unimportant ones
- p < 0.05 = significant difference

---

## 📈 Analysis Tabs

### Tab 1: **Main Chart**

**Stacked Bar Chart**: Features ordered by causal importance (left = most important)

**Elements**:
- **X-axis**: Features (ordered by importance score DESC)
- **Y-axis (left)**: Activation metric value
- **Y-axis (right)**: Importance score (red line)
- **Bars**: Stacked by prompt (different colors)

**Interpretation**:
- Important features (left side) should have **tall bars** on relevant prompts
- If bars are **gray** (only original prompt), activation doesn't generalize
- If bars are **colorful** (multiple prompts), feature activates cross-prompt

**Expected Pattern**:
```
High Importance (left)     →  Tall colored bars (activates on related prompts)
Low Importance (right)     →  Short gray bars (doesn't activate much)
```

**Export**: Download chart data as CSV

---

### Tab 2: **ROC Analysis**

**ROC Curve**: Using activation metric to predict causal importance

**Metrics**:
- **AUC (Area Under Curve)**:
  - 1.0 = Perfect predictor
  - 0.9-1.0 = Excellent
  - 0.8-0.9 = Good
  - 0.7-0.8 = Fair
  - 0.5-0.7 = Poor
  - 0.5 = Random (no predictive power)

**Precision-Recall Curve**:
- Shows trade-off between precision and recall
- Baseline = random classifier (% of important features)
- Higher curve = better predictor

**Optimal Threshold**:
- Threshold that maximizes F1 score
- Use this to filter features by activation

**Interpretation**:
- **AUC > 0.8**: Cross-prompt activation is a **good proxy** for causal importance
  - ✅ Can use activation for feature selection
- **AUC 0.6-0.8**: **Moderate** predictive power
  - ⚠️ Use in combination with other metrics
- **AUC < 0.6**: **Poor** predictor
  - ❌ Activation doesn't correlate with causal importance

---

### Tab 3: **Feature Ranking**

**Two Rankings Side-by-Side**:

1. **Top 20 by Causal Importance**:
   - Features with highest `importance_score`
   - Shows their `max_activation` across prompts
   - Expected: High activation if hypothesis holds

2. **Top 20 by Activation**:
   - Features with highest activation on selected prompts
   - Shows their `importance_score`
   - Expected: High importance if hypothesis holds

**Overlap Analysis**:
- **Both top 20**: Features that are both important AND highly activated ✅
- **Only important**: Causally important but low activation ⚠️
  - Potential **false negatives** (missed by activation filter)
- **Only activated**: Highly activated but not important ⚠️
  - Potential **false positives** (noise, semantic markers)

**Ideal Scenario**: High overlap (>50%) = good alignment

---

### Tab 4: **Prompt Comparison**

**Heatmap**: Feature × Prompt activation matrix

**Structure**:
- Rows: Top N features (ordered by importance)
- Columns: Selected prompts
- Color: Activation intensity

**Patterns to Look For**:
1. **Horizontal bands** (same feature, multiple prompts):
   - Dark = feature activates on many prompts (generalist)
   - Light = feature activates rarely (specialist)

2. **Vertical bands** (same prompt, multiple features):
   - Dark column = prompt activates many important features
   - Light column = prompt doesn't activate important features

3. **Clusters**:
   - Dark blocks = groups of features that co-activate on specific prompts
   - Indicates semantic/causal subnetworks

**Violin Plots**:
- Distribution of activation by prompt
- Separate violins for important vs unimportant features
- **Good separation** = important features have higher distribution

---

### Tab 5: **Token Analysis**

**Peak on Label Analysis**:
- **`picco_su_label`**: Boolean indicating if peak activation falls within label span
- **Contingency table**: % of features with peak on label, by importance
- **Chi-Square Test**: Tests association between importance and peak on label

**Expected**:
- Important features should have **higher % of peak on label**
- p < 0.05 = significant association

**Peak Token Distribution**:
- Most frequent `peak_token` for important vs unimportant features
- **Important features** should peak on semantically relevant tokens:
  - "Austin", "Texas", "capital", "city"
- **Unimportant features** might peak on structural tokens:
  - `<BOS>`, punctuation, stopwords

---

## 🎯 Interpretation Guidelines

### Scenario 1: **Strong Validation** ✅

**Indicators**:
- AUC > 0.85
- Mann-Whitney p < 0.001
- Top 20 overlap > 60%
- Important features peak on label > 70%

**Conclusion**: Cross-prompt activation is a **reliable proxy** for causal importance.

**Action**: Use activation filtering for feature selection in downstream tasks.

---

### Scenario 2: **Moderate Validation** ⚠️

**Indicators**:
- AUC 0.65-0.85
- Mann-Whitney p < 0.05
- Top 20 overlap 30-60%
- Some separation in distributions

**Conclusion**: Activation has **some predictive power** but not sufficient alone.

**Action**: Combine activation with other metrics (e.g., `node_influence`, `output_impact`).

---

### Scenario 3: **Weak/No Validation** ❌

**Indicators**:
- AUC < 0.65
- Mann-Whitney p > 0.05
- Top 20 overlap < 30%
- No clear separation

**Conclusion**: Cross-prompt activation **does not predict** causal importance.

**Possible Reasons**:
1. **Prompts not relevant**: Selected prompts don't activate the causal pathway
2. **Computational features dominate**: Important features are computational (low semantic activation)
3. **Measurement noise**: `acts_compared.csv` has quality issues
4. **Wrong activation metric**: Try different metrics (TWERA, cosine_similarity)

**Action**: 
- Try different prompts (more semantically related)
- Focus on semantic features only (exclude computational helpers)
- Check data quality in `acts_compared.csv`

---

## 🔍 Advanced Analysis

### Archetype-Specific Patterns

**Hypothesis**: Different archetypes have different activation patterns.

**Test**:
1. Filter features by archetype (from Phase 1)
2. Run ROC analysis separately for each archetype
3. Compare AUC across archetypes

**Expected**:
- **Semantic Anchors**: High AUC (activation predicts importance well)
- **Computational Helpers**: Low AUC (important but don't activate semantically)
- **Contextual Specialists**: Moderate AUC (activate on specific prompts only)

---

### Layer-Wise Analysis

**Hypothesis**: Activation-importance correlation varies by layer.

**Test**:
1. Group features by layer (e.g., 0-8, 9-17, 18-25)
2. Compute AUC for each group
3. Plot AUC vs layer group

**Expected**:
- **Low layers** (0-8): Lower AUC (structural, less semantic)
- **Mid layers** (9-17): Moderate AUC
- **High layers** (18-25): Higher AUC (semantic, task-specific)

---

### Prompt Engineering

**Hypothesis**: Some prompts are more informative than others.

**Test**:
1. For each prompt, compute AUC using only that prompt's activations
2. Rank prompts by AUC
3. Identify best discriminative prompts

**Categories**:
- **Positive related**: "Capital of Texas", "Texas cities" (should activate important features)
- **Negative related**: "Capital of France" (same domain, different target)
- **Unrelated**: Random prompts (should NOT activate important features)

**Optimal Set**: Prompts with highest AUC difference between important/unimportant features.

---

## 📥 Exports

### 1. **Analysis Summary JSON**
```json
{
  "configuration": {
    "importance_metric": "node_influence",
    "importance_percentile": 90,
    "activation_metric": "nuova_max_label_span",
    "activation_threshold": 0.5,
    "selected_prompts": [...]
  },
  "results": {
    "n_important": 50,
    "n_total": 500,
    "importance_threshold": 0.0234,
    "auc": 0.87,
    "mann_whitney_pvalue": 0.0001,
    "top20_overlap": 14
  }
}
```

### 2. **Feature Importance + Activation CSV**
Columns:
- `feature_key`
- `importance_score`
- `is_important`
- `max_activation` (across selected prompts)
- `layer`, `most_common_peak`, `node_influence`, `output_impact`

**Use**: Further analysis in notebooks, correlation studies, feature selection pipelines.

---

## 🛠️ Troubleshooting

### Issue: "AUC is 0.5 (random)"

**Diagnosis**:
- No correlation between activation and importance
- Activation metric doesn't capture causal relevance

**Solutions**:
1. Try different activation metric (e.g., `twera_total_in` instead of `nuova_max_label_span`)
2. Change prompts to more semantically related ones
3. Adjust importance metric (try `output_impact` instead of `node_influence`)
4. Check if important features are computational (low semantic activation expected)

---

### Issue: "Mann-Whitney test not significant"

**Diagnosis**:
- Distributions of activation overlap too much
- Not enough separation between important/unimportant

**Solutions**:
1. Increase `importance_percentile` (e.g., 95th instead of 90th) for stricter definition
2. Increase `activation_threshold` to focus on strong activations
3. Filter by archetype (analyze Semantic Anchors only)

---

### Issue: "Top 20 overlap is very low"

**Diagnosis**:
- Features ranked by importance ≠ features ranked by activation
- Activation captures different signal than causal importance

**Solutions**:
1. Investigate "only important" features: Why don't they activate?
   - Are they computational?
   - Are they position-specific (not captured by label span)?
2. Investigate "only activated" features: Why aren't they important?
   - Are they semantic markers without causal role?
   - Are they redundant (covered by other features in pruned graph)?

---

### Issue: "Not enough data for ROC"

**Diagnosis**:
- Too few features in `acts_compared.csv`
- Many features have NaN activation

**Solutions**:
1. Check `acts_compared.csv` quality: Are there missing values?
2. Ensure prompts are actually activating features
3. Lower `activation_threshold` to include more features

---

## 💡 Pro Tips

1. **Start with default settings**: Run analysis with defaults first, then iterate

2. **Compare multiple metrics**: Try all activation metrics to find best predictor

3. **Visualize outliers**: Features with high importance but low activation (or vice versa) are interesting edge cases

4. **Cross-validate**: If AUC is high, validate on held-out prompts

5. **Combine with Phase 2**: Check if features in high-coherence supernodes have better activation-importance alignment

6. **Document findings**: Export summary JSON for reproducibility

---

## 📚 Related Documentation

- **Metrics definitions**: `eda/METRICS_GLOSSARY.md`
- **Interpretation examples**: `eda/INTERPRETATION_GUIDE.md`
- **acts_compared.csv columns**: See main README or legacy notebooks
- **Causal metrics**: `docs/supernode_labelling/CAUSAL_METRICS.md`

---

**Last Updated**: 2025-10-18  
**Version**: 1.0.0


