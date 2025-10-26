"""
Cross-Prompt Robustness Analysis

Evaluates whether supernodes/features generalize across prompt variations:
- Entity swaps: Dallas->Oakland, Texas->California, Austin->Sacramento
- Same semantic structure, different entities

Measures:
1. Feature survival rate (>=70% activation overlap)
2. Concept shift accuracy (features activate on swapped entities)
3. Layer distribution similarity
4. Notable failure modes

Usage:
    python scripts/experiments/cross_prompt_robustness.py \
        --prompt1_csv <path> --prompt2_csv <path> \
        --prompt1_name "Dallas" --prompt2_name "Oakland" \
        --entity_mapping '{"Dallas":"Oakland","Texas":"California","Austin":"Sacramento"}' \
        --output_json <path>
"""

import argparse
import json
import warnings
from pathlib import Path
from typing import Dict, List, Tuple, Any, Set
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy.stats import entropy, ks_2samp


def load_and_prepare_data(csv_path: Path) -> pd.DataFrame:
    """Load CSV and prepare for analysis."""
    df = pd.read_csv(csv_path)
    
    # Ensure we have required columns
    required = ["feature_key", "layer", "prompt", "activation_max", "peak_token", "peak_token_idx"]
    missing = [col for col in required if col not in df.columns]
    
    if missing:
        raise ValueError(f"Missing required columns: {missing}")
    
    return df


def extract_entity_from_prompt(prompt: str) -> str:
    """Extract the main entity being tested in a probe prompt."""
    # Patterns: "entity: X is Y", "attribute: X is Y", "relationship: X"
    if ":" in prompt:
        after_colon = prompt.split(":", 1)[1].strip()
        # Get the last word (usually the entity/concept)
        words = after_colon.split()
        if words:
            return words[-1].strip(".,!?")
    return ""


def get_probe_concepts(df: pd.DataFrame) -> List[str]:
    """Extract unique probe concepts from prompts."""
    concepts = set()
    for prompt in df["prompt"].unique():
        entity = extract_entity_from_prompt(prompt)
        if entity:
            concepts.add(entity)
    return sorted(list(concepts))


def compute_activation_overlap(
    activations1: np.ndarray,
    activations2: np.ndarray,
    threshold_percentile: float = 50.0
) -> float:
    """
    Compute overlap of high-activation positions.
    
    Returns fraction of top activated positions that overlap.
    """
    if len(activations1) == 0 or len(activations2) == 0:
        return 0.0
    
    # Threshold at percentile
    thresh1 = np.percentile(activations1, threshold_percentile)
    thresh2 = np.percentile(activations2, threshold_percentile)
    
    active1 = set(np.where(activations1 >= thresh1)[0])
    active2 = set(np.where(activations2 >= thresh2)[0])
    
    if len(active1) == 0 or len(active2) == 0:
        return 0.0
    
    overlap = len(active1.intersection(active2))
    union = len(active1.union(active2))
    
    return overlap / union if union > 0 else 0.0


def compute_peak_token_consistency(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    feature_key: str,
    entity_mapping: Dict[str, str]
) -> Tuple[float, Dict[str, Any]]:
    """
    Check if peak tokens shift appropriately with entity swaps.
    
    Returns:
        - consistency score (0-1)
        - details dict with matched/mismatched tokens
    """
    feature1 = df1[df1["feature_key"] == feature_key]
    feature2 = df2[df2["feature_key"] == feature_key]
    
    if len(feature1) == 0 or len(feature2) == 0:
        return 0.0, {"error": "missing feature"}
    
    # Get peak tokens for each probe
    peaks1 = {}
    peaks2 = {}
    
    for _, row in feature1.iterrows():
        prompt = row["prompt"]
        peak = row["peak_token"]
        peaks1[prompt] = peak
    
    for _, row in feature2.iterrows():
        prompt = row["prompt"]
        peak = row["peak_token"]
        peaks2[prompt] = peak
    
    # Check if entities shifted correctly
    matches = 0
    total = 0
    details = {"matches": [], "mismatches": []}
    
    for old_entity, new_entity in entity_mapping.items():
        # Find prompts mentioning these entities
        for prompt1, peak1 in peaks1.items():
            if old_entity.lower() in prompt1.lower():
                # Find corresponding prompt in prompt2
                prompt2_candidate = prompt1.replace(old_entity, new_entity)
                
                if prompt2_candidate in peaks2:
                    peak2 = peaks2[prompt2_candidate]
                    
                    total += 1
                    
                    # Check if peak shifted appropriately
                    # Either: (1) same position (functional), or (2) entity name changed
                    if peak1.strip().lower() == old_entity.lower() and peak2.strip().lower() == new_entity.lower():
                        matches += 1
                        details["matches"].append({
                            "prompt1": prompt1,
                            "prompt2": prompt2_candidate,
                            "peak1": peak1,
                            "peak2": peak2,
                            "expected_shift": f"{old_entity}->{new_entity}"
                        })
                    elif peak1 == peak2:
                        # Functional token (didn't change)
                        matches += 1
                        details["matches"].append({
                            "prompt1": prompt1,
                            "prompt2": prompt2_candidate,
                            "peak1": peak1,
                            "peak2": peak2,
                            "note": "functional token (stable)"
                        })
                    else:
                        details["mismatches"].append({
                            "prompt1": prompt1,
                            "prompt2": prompt2_candidate,
                            "peak1": peak1,
                            "peak2": peak2,
                            "expected": f"{old_entity}->{new_entity}"
                        })
    
    consistency = matches / total if total > 0 else 0.0
    return consistency, details


def compute_layer_distribution_similarity(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    feature_key: str
) -> Tuple[float, Dict[str, Any]]:
    """
    Measure similarity of layer distributions using KS test.
    
    Returns p-value (higher = more similar).
    """
    feature1 = df1[df1["feature_key"] == feature_key]
    feature2 = df2[df2["feature_key"] == feature_key]
    
    if len(feature1) == 0 or len(feature2) == 0:
        return 0.0, {"error": "missing feature"}
    
    layers1 = feature1["layer"].values
    layers2 = feature2["layer"].values
    
    # KS test
    statistic, pvalue = ks_2samp(layers1, layers2)
    
    details = {
        "mean_layer1": float(np.mean(layers1)),
        "mean_layer2": float(np.mean(layers2)),
        "std_layer1": float(np.std(layers1)),
        "std_layer2": float(np.std(layers2)),
        "ks_statistic": float(statistic),
        "ks_pvalue": float(pvalue),
    }
    
    return pvalue, details


def analyze_feature_robustness(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    feature_key: str,
    entity_mapping: Dict[str, str],
    survival_threshold: float = 0.7
) -> Dict[str, Any]:
    """
    Comprehensive robustness analysis for a single feature.
    """
    result = {
        "feature_key": feature_key,
        "survives": False,
        "metrics": {}
    }
    
    # Get feature data
    feature1 = df1[df1["feature_key"] == feature_key]
    feature2 = df2[df2["feature_key"] == feature_key]
    
    if len(feature1) == 0 or len(feature2) == 0:
        result["error"] = "Feature not found in both datasets"
        return result
    
    # 1. Activation overlap
    activations1 = feature1["activation_max"].values
    activations2 = feature2["activation_max"].values
    
    # Pad to same length
    max_len = max(len(activations1), len(activations2))
    act1_padded = np.pad(activations1, (0, max_len - len(activations1)), constant_values=0)
    act2_padded = np.pad(activations2, (0, max_len - len(activations2)), constant_values=0)
    
    overlap = compute_activation_overlap(act1_padded, act2_padded)
    result["metrics"]["activation_overlap"] = float(overlap)
    
    # 2. Peak token consistency
    token_consistency, token_details = compute_peak_token_consistency(
        df1, df2, feature_key, entity_mapping
    )
    result["metrics"]["peak_token_consistency"] = float(token_consistency)
    result["peak_token_details"] = token_details
    
    # 3. Layer distribution similarity
    layer_similarity, layer_details = compute_layer_distribution_similarity(
        df1, df2, feature_key
    )
    result["metrics"]["layer_distribution_pvalue"] = float(layer_similarity)
    result["layer_details"] = layer_details
    
    # 4. Determine survival
    # Feature survives if activation overlap >= threshold
    result["survives"] = overlap >= survival_threshold
    
    return result


def analyze_cross_prompt_robustness(
    df1: pd.DataFrame,
    df2: pd.DataFrame,
    prompt1_name: str,
    prompt2_name: str,
    entity_mapping: Dict[str, str],
    survival_threshold: float = 0.7
) -> Dict[str, Any]:
    """
    Full cross-prompt robustness analysis.
    """
    # Find common features
    features1 = set(df1["feature_key"].unique())
    features2 = set(df2["feature_key"].unique())
    common_features = features1.intersection(features2)
    
    print(f"\n{prompt1_name}: {len(features1)} features")
    print(f"{prompt2_name}: {len(features2)} features")
    print(f"Common features: {len(common_features)}")
    
    # Analyze each common feature
    feature_results = []
    survival_count = 0
    
    for feature_key in sorted(common_features):
        result = analyze_feature_robustness(
            df1, df2, feature_key, entity_mapping, survival_threshold
        )
        feature_results.append(result)
        
        if result.get("survives", False):
            survival_count += 1
    
    survival_rate = survival_count / len(common_features) if len(common_features) > 0 else 0.0
    
    # Aggregate metrics
    activation_overlaps = [r["metrics"].get("activation_overlap", 0) for r in feature_results if "error" not in r]
    peak_consistencies = [r["metrics"].get("peak_token_consistency", 0) for r in feature_results if "error" not in r]
    layer_pvalues = [r["metrics"].get("layer_distribution_pvalue", 0) for r in feature_results if "error" not in r]
    
    aggregate_metrics = {
        "mean_activation_overlap": float(np.mean(activation_overlaps)) if activation_overlaps else 0.0,
        "std_activation_overlap": float(np.std(activation_overlaps)) if activation_overlaps else 0.0,
        "mean_peak_token_consistency": float(np.mean(peak_consistencies)) if peak_consistencies else 0.0,
        "std_peak_token_consistency": float(np.std(peak_consistencies)) if peak_consistencies else 0.0,
        "mean_layer_pvalue": float(np.mean(layer_pvalues)) if layer_pvalues else 0.0,
        "features_with_similar_layers": sum(1 for p in layer_pvalues if p > 0.05),
    }
    
    # Identify failure modes
    failure_modes = identify_failure_modes(feature_results, df1, df2)
    
    return {
        "prompt1": prompt1_name,
        "prompt2": prompt2_name,
        "entity_mapping": entity_mapping,
        "n_features_prompt1": len(features1),
        "n_features_prompt2": len(features2),
        "n_common_features": len(common_features),
        "survival_threshold": survival_threshold,
        "survival_count": survival_count,
        "survival_rate": survival_rate,
        "aggregate_metrics": aggregate_metrics,
        "feature_results": feature_results,
        "failure_modes": failure_modes,
    }


def identify_failure_modes(
    feature_results: List[Dict[str, Any]],
    df1: pd.DataFrame,
    df2: pd.DataFrame
) -> Dict[str, Any]:
    """
    Identify common failure patterns.
    """
    failures = [r for r in feature_results if not r.get("survives", False)]
    
    failure_modes = {
        "n_failures": len(failures),
        "categories": {}
    }
    
    # Categorize failures
    low_overlap = [f for f in failures if f["metrics"].get("activation_overlap", 1.0) < 0.3]
    inconsistent_peaks = [f for f in failures if f["metrics"].get("peak_token_consistency", 1.0) < 0.5]
    shifted_layers = [f for f in failures if f["metrics"].get("layer_distribution_pvalue", 1.0) < 0.01]
    
    failure_modes["categories"]["low_activation_overlap"] = {
        "count": len(low_overlap),
        "examples": [f["feature_key"] for f in low_overlap[:5]]
    }
    
    failure_modes["categories"]["inconsistent_peak_tokens"] = {
        "count": len(inconsistent_peaks),
        "examples": [f["feature_key"] for f in inconsistent_peaks[:5]]
    }
    
    failure_modes["categories"]["layer_distribution_shift"] = {
        "count": len(shifted_layers),
        "examples": [f["feature_key"] for f in shifted_layers[:5]]
    }
    
    return failure_modes


def print_summary(results: Dict[str, Any]):
    """Print human-readable summary."""
    print("\n" + "="*80)
    print("CROSS-PROMPT ROBUSTNESS ANALYSIS")
    print("="*80)
    
    print(f"\nPrompt 1: {results['prompt1']}")
    print(f"Prompt 2: {results['prompt2']}")
    print(f"\nEntity Mapping:")
    for old, new in results['entity_mapping'].items():
        print(f"  {old} -> {new}")
    
    print(f"\nFeature Coverage:")
    print(f"  {results['prompt1']}: {results['n_features_prompt1']} features")
    print(f"  {results['prompt2']}: {results['n_features_prompt2']} features")
    print(f"  Common: {results['n_common_features']} features")
    
    print(f"\nSurvival Analysis (threshold >={results['survival_threshold']:.0%} overlap):")
    print(f"  Survived: {results['survival_count']} / {results['n_common_features']}")
    print(f"  Survival Rate: {results['survival_rate']:.2%}")
    
    agg = results['aggregate_metrics']
    print(f"\nAggregate Metrics:")
    print(f"  Mean Activation Overlap: {agg['mean_activation_overlap']:.3f} +/- {agg['std_activation_overlap']:.3f}")
    print(f"  Mean Peak Token Consistency: {agg['mean_peak_token_consistency']:.3f} +/- {agg['std_peak_token_consistency']:.3f}")
    print(f"  Mean Layer P-value: {agg['mean_layer_pvalue']:.3f}")
    print(f"  Features with Similar Layers (p>0.05): {agg['features_with_similar_layers']} / {results['n_common_features']}")
    
    fm = results['failure_modes']
    print(f"\nFailure Modes ({fm['n_failures']} total failures):")
    for category, data in fm['categories'].items():
        print(f"  {category.replace('_', ' ').title()}: {data['count']}")
        if data['examples']:
            print(f"    Examples: {', '.join(data['examples'][:3])}")


def main():
    parser = argparse.ArgumentParser(description="Cross-prompt robustness analysis")
    parser.add_argument("--prompt1_csv", type=str, required=True, help="CSV for prompt 1")
    parser.add_argument("--prompt2_csv", type=str, required=True, help="CSV for prompt 2")
    parser.add_argument("--prompt1_name", type=str, required=True, help="Name for prompt 1")
    parser.add_argument("--prompt2_name", type=str, required=True, help="Name for prompt 2")
    parser.add_argument("--entity_mapping", type=str, required=True, 
                       help='JSON entity mapping, e.g. \'{"Dallas":"Oakland","Texas":"California"}\'')
    parser.add_argument("--survival_threshold", type=float, default=0.7,
                       help="Activation overlap threshold for survival (default: 0.7)")
    parser.add_argument("--output_json", type=str, default=None, help="Output JSON path")
    
    args = parser.parse_args()
    
    # Parse entity mapping
    entity_mapping = json.loads(args.entity_mapping)
    
    # Load data
    print(f"Loading {args.prompt1_name} from {args.prompt1_csv}...")
    df1 = load_and_prepare_data(Path(args.prompt1_csv))
    
    print(f"Loading {args.prompt2_name} from {args.prompt2_csv}...")
    df2 = load_and_prepare_data(Path(args.prompt2_csv))
    
    # Analyze
    results = analyze_cross_prompt_robustness(
        df1, df2,
        args.prompt1_name, args.prompt2_name,
        entity_mapping,
        args.survival_threshold
    )
    
    # Print summary
    print_summary(results)
    
    # Save results
    if args.output_json:
        output_path = Path(args.output_json)
    else:
        output_path = Path(args.prompt1_csv).parent / "cross_prompt_robustness.json"
    
    print(f"\nSaving results to {output_path}...")
    with open(output_path, "w") as f:
        json.dump(results, f, indent=2)
    
    print("\nDone!")


if __name__ == "__main__":
    main()

