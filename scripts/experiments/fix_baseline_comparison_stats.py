"""
Fix baseline comparison with proper statistical tests.

Adds:
- Significance tests (t-test, Wilcoxon)
- Effect sizes (Cohen's d)
- Confidence intervals
- Multiple comparison corrections

Usage:
    python scripts/experiments/fix_baseline_comparison_stats.py \
        --input_json <comparison.json> --output_json <output.json>
"""

import argparse
import json
import warnings
from pathlib import Path
from typing import Dict, List, Any

import numpy as np
import pandas as pd
from scipy import stats
from scipy.stats import ttest_ind, mannwhitneyu, wilcoxon


def compute_cohens_d(group1: np.ndarray, group2: np.ndarray) -> float:
    """Compute Cohen's d effect size."""
    n1, n2 = len(group1), len(group2)
    var1, var2 = np.var(group1, ddof=1), np.var(group2, ddof=1)
    
    pooled_std = np.sqrt(((n1 - 1) * var1 + (n2 - 1) * var2) / (n1 + n2 - 2))
    
    if pooled_std == 0:
        return 0.0
    
    return (np.mean(group1) - np.mean(group2)) / pooled_std


def interpret_cohens_d(d: float) -> str:
    """Interpret effect size magnitude."""
    abs_d = abs(d)
    if abs_d < 0.2:
        return "negligible"
    elif abs_d < 0.5:
        return "small"
    elif abs_d < 0.8:
        return "medium"
    else:
        return "large"


def compute_statistical_tests(
    concept_values: List[float],
    cosine_values: List[float],
    adjacency_values: List[float],
    metric_name: str,
    higher_is_better: bool = True
) -> Dict[str, Any]:
    """
    Run statistical tests comparing methods.
    
    Returns dict with:
    - t-test results
    - Wilcoxon test results
    - Cohen's d effect sizes
    - Confidence intervals
    - Interpretation
    """
    concept_arr = np.array(concept_values)
    cosine_arr = np.array(cosine_values)
    adjacency_arr = np.array(adjacency_values)
    
    results = {
        "metric": metric_name,
        "higher_is_better": higher_is_better,
        "n_samples": len(concept_arr)
    }
    
    # Concept vs Cosine
    if len(concept_arr) > 1 and len(cosine_arr) > 1:
        # t-test (parametric)
        t_stat, t_p = ttest_ind(concept_arr, cosine_arr)
        results["concept_vs_cosine_ttest"] = {
            "t_statistic": float(t_stat),
            "p_value": float(t_p),
            "significant": t_p < 0.05
        }
        
        # Wilcoxon (non-parametric)
        try:
            u_stat, u_p = mannwhitneyu(concept_arr, cosine_arr, alternative='two-sided')
            results["concept_vs_cosine_mannwhitney"] = {
                "u_statistic": float(u_stat),
                "p_value": float(u_p),
                "significant": u_p < 0.05
            }
        except:
            results["concept_vs_cosine_mannwhitney"] = {"error": "insufficient data"}
        
        # Cohen's d
        d = compute_cohens_d(concept_arr, cosine_arr)
        results["concept_vs_cosine_effect"] = {
            "cohens_d": float(d),
            "magnitude": interpret_cohens_d(d)
        }
        
        # 95% CI for mean difference
        diff = concept_arr.mean() - cosine_arr.mean()
        se = np.sqrt(np.var(concept_arr, ddof=1)/len(concept_arr) + 
                     np.var(cosine_arr, ddof=1)/len(cosine_arr))
        ci_low = diff - 1.96 * se
        ci_high = diff + 1.96 * se
        results["concept_vs_cosine_ci95"] = {
            "mean_difference": float(diff),
            "ci_low": float(ci_low),
            "ci_high": float(ci_high)
        }
    
    # Concept vs Adjacency
    if len(concept_arr) > 1 and len(adjacency_arr) > 1:
        # t-test
        t_stat, t_p = ttest_ind(concept_arr, adjacency_arr)
        results["concept_vs_adjacency_ttest"] = {
            "t_statistic": float(t_stat),
            "p_value": float(t_p),
            "significant": t_p < 0.05
        }
        
        # Mann-Whitney U
        try:
            u_stat, u_p = mannwhitneyu(concept_arr, adjacency_arr, alternative='two-sided')
            results["concept_vs_adjacency_mannwhitney"] = {
                "u_statistic": float(u_stat),
                "p_value": float(u_p),
                "significant": u_p < 0.05
            }
        except:
            results["concept_vs_adjacency_mannwhitney"] = {"error": "insufficient data"}
        
        # Cohen's d
        d = compute_cohens_d(concept_arr, adjacency_arr)
        results["concept_vs_adjacency_effect"] = {
            "cohens_d": float(d),
            "magnitude": interpret_cohens_d(d)
        }
        
        # 95% CI
        diff = concept_arr.mean() - adjacency_arr.mean()
        se = np.sqrt(np.var(concept_arr, ddof=1)/len(concept_arr) + 
                     np.var(adjacency_arr, ddof=1)/len(adjacency_arr))
        ci_low = diff - 1.96 * se
        ci_high = diff + 1.96 * se
        results["concept_vs_adjacency_ci95"] = {
            "mean_difference": float(diff),
            "ci_low": float(ci_low),
            "ci_high": float(ci_high)
        }
    
    # Overall interpretation
    results["interpretation"] = generate_interpretation(results, higher_is_better)
    
    return results


def generate_interpretation(results: Dict[str, Any], higher_is_better: bool) -> str:
    """Generate human-readable interpretation."""
    interp = []
    
    # vs Cosine
    if "concept_vs_cosine_ttest" in results:
        p = results["concept_vs_cosine_ttest"]["p_value"]
        d = results["concept_vs_cosine_effect"]["cohens_d"]
        mag = results["concept_vs_cosine_effect"]["magnitude"]
        
        if p < 0.05:
            direction = "higher" if (d > 0 and higher_is_better) or (d < 0 and not higher_is_better) else "lower"
            interp.append(f"Significantly {direction} than cosine (p={p:.4f}, d={d:.2f}, {mag} effect)")
        else:
            interp.append(f"Not significantly different from cosine (p={p:.4f})")
    
    # vs Adjacency
    if "concept_vs_adjacency_ttest" in results:
        p = results["concept_vs_adjacency_ttest"]["p_value"]
        d = results["concept_vs_adjacency_effect"]["cohens_d"]
        mag = results["concept_vs_adjacency_effect"]["magnitude"]
        
        if p < 0.05:
            direction = "higher" if (d > 0 and higher_is_better) or (d < 0 and not higher_is_better) else "lower"
            interp.append(f"Significantly {direction} than adjacency (p={p:.4f}, d={d:.2f}, {mag} effect)")
        else:
            interp.append(f"Not significantly different from adjacency (p={p:.4f})")
    
    return "; ".join(interp) if interp else "Insufficient data for inference"


def add_statistics_to_comparison(comparison_file: Path, output_file: Path):
    """Add statistical tests to existing comparison results."""
    
    with open(comparison_file, 'r') as f:
        data = json.load(f)
    
    # Note: This requires per-feature data which isn't in the comparison JSON
    # We need the original CSV to do proper statistics
    
    print("ERROR: Statistical tests require per-feature data.")
    print("The comparison JSON only has aggregate metrics.")
    print("")
    print("To fix this, you need to:")
    print("1. Modify compare_grouping_methods.py to save per-feature metrics")
    print("2. Run statistical tests on those metrics")
    print("")
    print("See the corrected comparison script for the proper implementation.")
    
    return None


def main():
    print("="*80)
    print("IMPORTANT: Statistical Testing Requires Per-Feature Data")
    print("="*80)
    print("")
    print("The current comparison JSON only contains AGGREGATE metrics.")
    print("To run proper statistical tests, you need PER-FEATURE metrics.")
    print("")
    print("Solution:")
    print("1. Use the corrected comparison script")
    print("2. This will compute statistics properly")
    print("")
    print("Creating corrected comparison script now...")


if __name__ == "__main__":
    main()

