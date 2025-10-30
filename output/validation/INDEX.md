# Validation Directory Index

**Last Updated**: 2025-10-27

---

## 🎯 Quick Start

### For Paper Writing → Start Here:
📄 **`CROSS_PROMPT_ROBUSTNESS_MASTER.md`** ⭐

This master file explains both robustness methods and provides ready-to-use text for your paper.

---

## 📂 Main Analyses

### ⭐ Cross-Prompt Robustness (Dual-Level Validation)

**Overview**: `CROSS_PROMPT_ROBUSTNESS_MASTER.md`

Two complementary methods testing robustness at different levels:

#### 1. **feature_level_robustness/** - Computational Stability
**Question**: Do individual features maintain stable activation patterns?

**Method**: Activation overlap analysis

**Key Results**:
- 100% feature survival (25/25)
- Perfect activation overlap (1.000)
- 96% peak token consistency

**Start here**: `feature_level_robustness/CROSS_PROMPT_EVIDENCE.md`

---

#### 2. **supernode_level_robustness/** - Semantic Disentanglement  
**Question**: Do conceptual groupings transfer appropriately?

**Method**: Supernode transfer analysis

**Key Results**:
- 100% universal concept transfer (7/7)
- 100% entity separation (8/8)
- 94% activation stability
- 96% grouping consistency

**Start here**: `supernode_level_robustness/PAPER_READY_SUMMARY_CORRECTED.md` ⭐

---

### 📊 **baseline comparison/** - Method Validation
**Purpose**: Compares concept-aligned grouping vs geometric baselines

**Key Results**:
- +132% peak token consistency vs cosine similarity
- +486% activation similarity vs cosine similarity

**Start here**: `baseline comparison/CLAIM_EVIDENCE.md`

---

## 📄 Root-Level Documents

### Primary References
- **`CROSS_PROMPT_ROBUSTNESS_MASTER.md`** ⭐ - Overview of both methods
- `PUBLICATION_READY_CLAIMS.md` - All claims for paper
- `CORRECTED_CLAIMS_HONEST_ASSESSMENT.md` - Honest assessment

### Technical Documentation  
- `README_CORRECTED.md` - Corrected README after reviews
- `STATISTICAL_REVIEW_RESPONSE.md` - Response to statistical concerns

---

## 🎯 Navigation by Task

### Writing Abstract
→ See "Combined Results for Paper" in `CROSS_PROMPT_ROBUSTNESS_MASTER.md`

### Writing Results Section 5.5
→ Use paragraphs 1-3 from `CROSS_PROMPT_ROBUSTNESS_MASTER.md`  
→ Plus Table 3 from `supernode_level_robustness/PAPER_READY_SUMMARY_CORRECTED.md`

### Writing Discussion
→ Use "Interpretation" from `CROSS_PROMPT_ROBUSTNESS_MASTER.md`

### Creating Figures
→ `supernode_level_robustness/cross_prompt_robustness_*.png` (comprehensive)  
→ Or combine: `feature_level_robustness/robustness_summary.png` + supernode figure

### Verifying Claims
→ `supernode_level_robustness/VERIFIED_CLAIMS.md` (all numbers verified)  
→ `feature_level_robustness/cross_prompt_robustness_dallas_oakland.json` (raw data)

---

## 📊 Summary Statistics (Quick Reference)

### Feature-Level Robustness
| Metric | Value |
|--------|-------|
| Survival Rate | 100% (25/25) |
| Activation Overlap | 1.000 (perfect) |
| Peak Token Consistency | 96% |
| Layer Distribution | p=1.000 (stable) |

### Supernode-Level Robustness
| Metric | Value |
|--------|-------|
| Universal Transfer | 100% (7/7) |
| Entity Separation | 100% (8/8) |
| Activation Stability | 94% |
| Grouping Consistency | 96% (corrected) |

---

## 🔬 Analysis Scripts

Located in `scripts/experiments/`:

### Cross-Prompt Robustness
- `cross_prompt_robustness.py` - Feature-level analysis
- `analyze_cross_prompt_robustness.py` - Supernode-level analysis
- `run_cross_prompt_analysis.py` - Quick runner
- `verify_claims.py` - Claim verification

### Baseline Comparison
- `compare_grouping_methods.py` - Method comparison
- `visualize_comparison.py` - Visualization

### Documentation
- `README_CROSS_PROMPT_ROBUSTNESS.md` - Full methodology

---

## 🔄 Reproduction

### Feature-Level Analysis
```bash
python scripts/experiments/cross_prompt_robustness.py \
    --prompt1_csv "output/examples/Dallas/node_grouping_final_*.csv" \
    --prompt2_csv "output/examples/capital oakland/node_grouping_final_*.csv" \
    --prompt1_name "Dallas" --prompt2_name "Oakland"
```

### Supernode-Level Analysis
```bash
cd scripts/experiments
python run_cross_prompt_analysis.py
```

### Verify All Claims
```bash
cd scripts/experiments
python verify_claims.py
```

---

## 📂 Complete Directory Structure

```
output/validation/
├── INDEX.md (this file)
├── CROSS_PROMPT_ROBUSTNESS_MASTER.md ⭐ START HERE
│
├── feature_level_robustness/
│   ├── README.md
│   ├── CROSS_PROMPT_EVIDENCE.md
│   ├── CROSS_PROMPT_ROBUSTNESS_REPORT.md
│   ├── MASTER_VALIDATION_SUMMARY.md
│   ├── cross_prompt_robustness_dallas_oakland.json
│   ├── robustness_summary.png
│   ├── robustness_feature_analysis.png
│   └── entity_mapping_diagram.png
│
├── supernode_level_robustness/
│   ├── README.md
│   ├── PAPER_READY_SUMMARY_CORRECTED.md ⭐
│   ├── VERIFIED_CLAIMS.md
│   ├── DOUBLE_CHECK_RESULTS.md
│   ├── supernode_transfer_*.csv
│   ├── activation_similarity_*.csv
│   ├── cross_prompt_report_*.md
│   ├── cross_prompt_robustness_*.png
│   └── figure_supernode_transfer_matrix.png
│
├── baseline comparison/
│   ├── CLAIM_EVIDENCE.md
│   ├── coherence_comparison.png
│   ├── improvement_chart.png
│   └── summary_table.png
│
├── PUBLICATION_READY_CLAIMS.md
├── CORRECTED_CLAIMS_HONEST_ASSESSMENT.md
├── README_CORRECTED.md
└── STATISTICAL_REVIEW_RESPONSE.md
```

---

## ⚠️ Important Notes

### Which Method for Which Claim?

**Feature-Level** (activation overlap):
- ✅ "Features are computationally stable"
- ✅ "Activation patterns consistent across probes"
- ✅ "100% survival rate"

**Supernode-Level** (concept transfer):
- ✅ "Concepts are semantically disentangled"
- ✅ "Universal vs entity discrimination"
- ✅ "96% grouping consistency"

**Both Together**:
- ✅ "Robust, generalizable concept discovery"
- ✅ "Evidence against overfitting"
- ✅ "Dual-level validation"

### Don't Mix Methods!
When citing statistics, be clear which method you're referencing:
- "Feature-level survival rate: 100%"
- "Supernode-level transfer rate: 100%"

These are different metrics from different analyses!

---

## 🎯 Bottom Line

**You have TWO complementary validations**:
1. Features are computationally robust → Feature-level analysis
2. Concepts are semantically organized → Supernode-level analysis

**Use both** in your paper for strongest evidence.

**Start with**: `CROSS_PROMPT_ROBUSTNESS_MASTER.md` which combines both.

---

## 📞 Need Help?

- **Methodology questions** → See respective README.md files
- **Claims verification** → See `supernode_level_robustness/VERIFIED_CLAIMS.md`
- **Paper text** → See `CROSS_PROMPT_ROBUSTNESS_MASTER.md`
- **Raw data** → CSV files in respective directories
- **Scripts** → See `scripts/experiments/`

---

**Status**: ✅ All analyses complete, verified, publication-ready




