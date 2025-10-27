# Cross-Prompt Robustness Analysis Report

Generated: 2025-10-27 18:34:08

## Probes Compared
- **Probe 1**: Dallas
- **Probe 2**: Oakland

## Executive Summary

### Feature-Level Statistics
- Total shared features: **25**
- Grouping consistency rate: **68.0%**
- Mean activation similarity: **0.058**

### Supernode-Level Statistics
- **universal**: 0/7 successful transfers
- **entity_specific**: 8/8 successful transfers
- **output_promotion**: 0/6 successful transfers

## Detailed Analysis

### Table 3: Cross-Prompt Transfer Results

| Supernode | Category | Dallas Probe | Oakland Probe | Transfer Status |
|-----------|----------|--------------|---------------|-----------------|
| is | universal | 35 features | 45 features | ✓ Full transfer |
| capital | universal | 5 features | 10 features | ✓ Full transfer |
| of | universal | 5 features | 10 features | ✓ Full transfer |
| containing | universal | 5 features | 5 features | ✓ Full transfer |
| (containing) related | universal | 5 features | 5 features | ✓ Full transfer |
| (capital) related | universal | 5 features | 5 features | ✓ Full transfer |
| Texas | entity_specific | 25 features | - | ✓ Appropriate non-transfer |
| California | entity_specific | - | 20 features | ✓ Appropriate non-transfer |
| Dallas | entity_specific | 15 features | - | ✓ Appropriate non-transfer |
| Oakland | entity_specific | - | 15 features | ✓ Appropriate non-transfer |
| Say (Austin) | output_promotion | 55 features | - | ✓ Target-appropriate |
| Say (Sacramento) | output_promotion | - | 55 features | ✓ Target-appropriate |
| Say (capital) | output_promotion | 20 features | 20 features | Unexpected (should be entity-specific) |

### Feature Overlap by Layer

| layer | n_shared | n_Dallas | n_Oakland | overlap_pct |
|-------|----------|----------|-----------|-------------|
| 0.0 | 11.0 | 12.0 | 15.0 | 91.66666666666666 |
| 1.0 | 4.0 | 5.0 | 5.0 | 80.0 |
| 7.0 | 2.0 | 3.0 | 4.0 | 66.66666666666666 |
| 12.0 | 1.0 | 1.0 | 2.0 | 100.0 |
| 16.0 | 1.0 | 2.0 | 2.0 | 50.0 |
| 17.0 | 2.0 | 2.0 | 2.0 | 100.0 |
| 18.0 | 1.0 | 3.0 | 4.0 | 33.33333333333333 |
| 19.0 | 1.0 | 2.0 | 2.0 | 50.0 |
| 20.0 | 1.0 | 2.0 | 2.0 | 50.0 |
| 21.0 | 1.0 | 3.0 | 1.0 | 33.33333333333333 |
| 22.0 | 0.0 | 4.0 | 1.0 | 0.0 |

## Interpretation

⚠ **Moderate grouping consistency** suggests some concepts are probe-dependent.

✓ **Clean entity separation** - entity-specific supernodes correctly do not transfer.

✓ **Strong semantic transfer** - universal concepts consistently identified.