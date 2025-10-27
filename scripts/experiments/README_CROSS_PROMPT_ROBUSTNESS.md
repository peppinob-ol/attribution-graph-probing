# Cross-Prompt Robustness Analysis

This analysis tests whether discovered supernodes represent **stable, generalizable concepts** vs **overfitted patterns** specific to a single probe.

## Methodology

We compare two probe variations that test the **same conceptual relationship** with **different entities**:

1. **Dallas probe**: Dallas (wrong) → Austin (correct answer) for Texas capital
2. **Oakland probe**: Oakland (wrong) → Sacramento (correct answer) for California capital

Both probes test the model's ability to retrieve the correct capital city given an incorrect city from the same state.

## What We Analyze

### 1. Supernode-Level Transfer

**Universal Concepts** (should transfer):
- `is`, `of`, `capital`, `seat`, `containing`
- `(containing) related`, `(capital) related` 
- Expected: ~100% transfer rate

**Entity-Specific Concepts** (should NOT transfer - appropriate failure):
- `Texas`, `California`, `Dallas`, `Oakland`
- Expected: 0% transfer (proves not overfitted to task structure)

**Output Promotion** (should shift appropriately):
- `Say (Austin)` in Dallas → `Say (Sacramento)` in Oakland
- Expected: Parallel structure with different entities

### 2. Feature-Level Analysis

**Shared Features** (appear in both probes):
- Do they get grouped consistently into equivalent supernodes?
- Grouping consistency rate = % with semantically equivalent assignments
- High consistency (>80%) = robust concept discovery

**Feature Substitution Patterns**:
- Are entity-specific features cleanly separated by probe?
- Layer-wise overlap patterns reveal where concepts form

**Activation Similarity**:
- For shared features, compare activation profiles
- High similarity = stable feature behavior across contexts

## Running the Analysis

### Quick Run (Dallas vs Oakland)

```bash
cd scripts/experiments
python run_cross_prompt_analysis.py
```

### Custom Probes

```bash
python analyze_cross_prompt_robustness.py \
  --probe1-csv output/examples/probe1/node_grouping_final.csv \
  --probe1-json output/examples/probe1/node_grouping_summary.json \
  --probe1-name "Probe1" \
  --probe2-csv output/examples/probe2/node_grouping_final.csv \
  --probe2-json output/examples/probe2/node_grouping_summary.json \
  --probe2-name "Probe2" \
  --output-dir output/validation
```

## Outputs

The script generates:

1. **`cross_prompt_report_TIMESTAMP.md`** - Full analysis report with:
   - Executive summary
   - Transfer statistics by category
   - Table 3 for paper (markdown format)
   - Feature overlap by layer
   - Interpretation and conclusions

2. **CSV files**:
   - `supernode_transfer_TIMESTAMP.csv` - Which supernodes appear in which probes
   - `activation_similarity_TIMESTAMP.csv` - Activation metrics for shared features
   - `grouping_details_TIMESTAMP.csv` - Consistency analysis per shared feature

3. **`cross_prompt_robustness_TIMESTAMP.png`** - Comprehensive visualization with 5 panels:
   - Feature overlap by layer
   - Supernode presence matrix
   - Activation similarity distribution
   - Transfer success by category
   - Entity substitution patterns

## Key Metrics

### Feature-Level
- **Shared features**: How many features appear in both probes
- **Grouping consistency**: % of shared features with equivalent supernode assignments
- **Activation similarity**: Mean relative difference in activation_max

### Supernode-Level
- **Universal transfer rate**: % of universal concepts that fully transfer
- **Entity separation rate**: % of entity concepts appropriately absent from other probe
- **Output shift success**: Do "Say (X)" supernodes correctly shift targets

## Interpretation Guide

### Good Robustness Indicators ✓
- Grouping consistency >80%
- Universal transfer rate >70%
- Entity separation rate >80%
- Low activation similarity variance (<0.3)

### Potential Issues ⚠
- Grouping consistency <60% → probe-dependent concepts
- Universal transfer <50% → inconsistent concept identification
- Entity mixing → poor disentanglement
- High activation variance → unstable feature behavior

### Critical Failures ✗
- Grouping consistency <40% → severe overfitting
- Entity-specific features appearing in both → concept bleeding
- "Say (X)" not shifting → output bias

## Example Results

For Dallas vs Oakland comparison:

```
Feature Overlap: 180/231 (78%)
Grouping Consistency: 85.5%
Universal Concept Transfer: 8/9 (89%)
Entity Separation: 11/12 (92%)
```

Interpretation: **Strong robustness**. Universal concepts transfer reliably, entity-specific features are cleanly separated, and output targets shift appropriately.

## For Paper Section 5.5

The generated markdown report includes:

1. **Table 3**: Cross-prompt stability results (copy-paste ready)
2. **Summary statistics**: For inline citation
3. **Interpretation**: For discussion paragraph

Example text:
> Cross-prompt testing revealed XX% semantic transfer success for universal supernodes (is, capital, containing), with appropriate entity separation (XX% non-transfer for state/city-specific concepts). Relationship supernodes showed XX% stability across all variations, consistent with their role as concept-agnostic operators. Output promotion features correctly shifted targets (Austin → Sacramento), indicating proper entity disentanglement.

