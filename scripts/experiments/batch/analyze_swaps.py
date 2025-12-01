"""
Analyze swap experiment results with tiered success classification.

Loads all swap results, classifies each with tiered metrics,
and generates analysis outputs including heatmaps.

Usage:
    python scripts/experiments/batch/analyze_swaps.py
    python scripts/experiments/batch/analyze_swaps.py --swaps-dir output/usa_states_batch/_swaps
    python scripts/experiments/batch/analyze_swaps.py --help
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent))

from pipeline.swap_classifier import (
    SwapTier,
    ClassificationResult,
    classify_swap_result,
)


def load_all_swap_results(swaps_dir: Path) -> List[Dict[str, Any]]:
    """
    Load all swap result JSON files from the by_source directory.
    
    Args:
        swaps_dir: Path to _swaps directory
    
    Returns:
        List of swap result dicts
    """
    by_source_dir = swaps_dir / "by_source"
    if not by_source_dir.exists():
        raise FileNotFoundError(f"by_source directory not found: {by_source_dir}")
    
    results = []
    
    for source_dir in sorted(by_source_dir.iterdir()):
        if not source_dir.is_dir():
            continue
        
        for result_file in sorted(source_dir.glob("to_*.json")):
            try:
                with open(result_file, 'r', encoding='utf-8') as f:
                    result = json.load(f)
                    result['_file'] = str(result_file)
                    results.append(result)
            except (json.JSONDecodeError, IOError) as e:
                print(f"  Warning: Failed to load {result_file}: {e}")
    
    return results


def classify_all_results(
    results: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Classify all results and add tier information.
    
    Args:
        results: List of swap result dicts
    
    Returns:
        List of results with added 'classification' key
    """
    classified = []
    
    for result in results:
        classification = classify_swap_result(result)
        result['classification'] = classification.to_dict()
        classified.append(result)
    
    return classified


def build_tier_matrix(
    results: List[Dict[str, Any]],
) -> pd.DataFrame:
    """
    Build NxN matrix of tier values.
    
    Args:
        results: Classified results
    
    Returns:
        DataFrame with sources as rows, targets as columns, tier values as cells
    """
    # Collect all unique slugs
    slugs = set()
    for result in results:
        slugs.add(result['source']['slug'])
        slugs.add(result['target']['slug'])
    
    slugs = sorted(slugs)
    
    # Initialize matrix with NaN
    matrix = pd.DataFrame(
        index=slugs,
        columns=slugs,
        dtype=float,
    )
    matrix.index.name = 'from_slug'
    matrix.columns.name = 'to_slug'
    
    # Fill in tier values
    for result in results:
        from_slug = result['source']['slug']
        to_slug = result['target']['slug']
        tier = result['classification']['tier']
        matrix.loc[from_slug, to_slug] = tier
    
    return matrix


def compute_summary_stats(
    results: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """
    Compute summary statistics from classified results.
    
    Args:
        results: Classified results
    
    Returns:
        Summary dict with tier counts, rates, and breakdowns
    """
    total = len(results)
    if total == 0:
        return {'error': 'No results to analyze'}
    
    # Count by tier
    tier_counts = defaultdict(int)
    for result in results:
        tier = result['classification']['tier']
        tier_counts[tier] += 1
    
    # Group by target state
    by_target_state = defaultdict(list)
    for result in results:
        target_state = result['target']['state']
        tier = result['classification']['tier']
        by_target_state[target_state].append(tier)
    
    # Compute average tier per target
    target_stats = {}
    for state, tiers in sorted(by_target_state.items()):
        target_stats[state] = {
            'count': len(tiers),
            'avg_tier': sum(tiers) / len(tiers),
            'perfect_count': sum(1 for t in tiers if t == SwapTier.PERFECT),
            'perfect_rate': sum(1 for t in tiers if t == SwapTier.PERFECT) / len(tiers),
        }
    
    # Group by source state
    by_source_state = defaultdict(list)
    for result in results:
        source_state = result['source']['state']
        tier = result['classification']['tier']
        by_source_state[source_state].append(tier)
    
    source_stats = {}
    for state, tiers in sorted(by_source_state.items()):
        source_stats[state] = {
            'count': len(tiers),
            'avg_tier': sum(tiers) / len(tiers),
        }
    
    return {
        'timestamp': datetime.now().isoformat(),
        'total_swaps': total,
        'tier_counts': {
            SwapTier(t).name: c for t, c in sorted(tier_counts.items())
        },
        'tier_rates': {
            SwapTier(t).name: c / total for t, c in sorted(tier_counts.items())
        },
        'aggregate': {
            'perfect_rate': tier_counts.get(SwapTier.PERFECT, 0) / total,
            'state_correct_rate': (
                tier_counts.get(SwapTier.PERFECT, 0) + 
                tier_counts.get(SwapTier.TARGET_STATE_CITY, 0)
            ) / total,
            'suppression_rate': (
                total - tier_counts.get(SwapTier.SOURCE_PERSISTS, 0)
            ) / total,
            'avg_tier': sum(
                t * c for t, c in tier_counts.items()
            ) / total,
        },
        'by_target_state': target_stats,
        'by_source_state': source_stats,
    }


def export_detailed_results(
    results: List[Dict[str, Any]],
    output_path: Path,
) -> None:
    """
    Export detailed classification results to CSV.
    
    Args:
        results: Classified results
        output_path: Path to output CSV
    """
    rows = []
    for result in results:
        rows.append({
            'swap_id': result.get('swap_id', ''),
            'from_slug': result['source']['slug'],
            'from_state': result['source']['state'],
            'from_capital': result['source']['capital'],
            'to_slug': result['target']['slug'],
            'to_state': result['target']['state'],
            'to_capital': result['target']['capital'],
            'tier': result['classification']['tier'],
            'tier_name': result['classification']['tier_name'],
            'cities_found': ', '.join(result['classification']['cities_found']),
            'notes': result['classification']['notes'],
            'steered_output': result.get('evaluation', {}).get('raw', {}).get('steered_output', '')[:200],
        })
    
    df = pd.DataFrame(rows)
    df.to_csv(output_path, index=False)
    print(f"  Exported detailed results to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Analyze swap experiment results with tiered classification'
    )
    parser.add_argument(
        '--swaps-dir',
        type=str,
        default='output/usa_states_batch/_swaps',
        help='Path to _swaps directory (default: output/usa_states_batch/_swaps)'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Output directory for analysis (default: {swaps-dir}/_analysis)'
    )
    parser.add_argument(
        '--no-heatmap',
        action='store_true',
        help='Skip heatmap generation'
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    swaps_dir = Path(args.swaps_dir)
    if not swaps_dir.is_absolute():
        # Try relative to script location first, then cwd
        script_dir = Path(__file__).parent
        repo_root = script_dir.parents[2]
        
        candidate = repo_root / args.swaps_dir
        if candidate.exists():
            swaps_dir = candidate
        else:
            swaps_dir = Path(args.swaps_dir)
    
    if not swaps_dir.exists():
        print(f"Error: Swaps directory not found: {swaps_dir}")
        return 1
    
    output_dir = Path(args.output_dir) if args.output_dir else swaps_dir / "_analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Analyzing swaps in: {swaps_dir}")
    print(f"Output directory: {output_dir}")
    
    # Load all results
    print("\n[1/4] Loading swap results...")
    results = load_all_swap_results(swaps_dir)
    print(f"  Loaded {len(results)} swap results")
    
    if not results:
        print("Error: No results found")
        return 1
    
    # Classify all results
    print("\n[2/4] Classifying results...")
    classified = classify_all_results(results)
    
    # Print tier distribution
    tier_dist = defaultdict(int)
    for r in classified:
        tier_dist[r['classification']['tier_name']] += 1
    
    print("  Tier distribution:")
    for tier_name in ['PERFECT', 'TARGET_STATE_CITY', 'TARGET_STATE_ONLY', 
                      'SUPPRESSED_ONLY', 'SOURCE_PERSISTS', 'WRONG_STATE']:
        count = tier_dist.get(tier_name, 0)
        pct = count / len(classified) * 100
        print(f"    {tier_name}: {count} ({pct:.1f}%)")
    
    # Build tier matrix
    print("\n[3/4] Building tier matrix...")
    tier_matrix = build_tier_matrix(classified)
    
    # Export tier matrix
    matrix_path = output_dir / "tier_matrix.csv"
    tier_matrix.to_csv(matrix_path)
    print(f"  Exported tier matrix to: {matrix_path}")
    
    # Compute and export summary
    print("\n[4/4] Computing summary statistics...")
    summary = compute_summary_stats(classified)
    
    summary_path = output_dir / "tier_summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    print(f"  Exported summary to: {summary_path}")
    
    # Export detailed results
    detailed_path = output_dir / "detailed_results.csv"
    export_detailed_results(classified, detailed_path)
    
    # Generate heatmap
    if not args.no_heatmap:
        print("\n[5/4] Generating heatmap...")
        try:
            # Import here to avoid matplotlib dependency if not needed
            from scripts.visualization.swap_heatmap import create_swap_heatmap
            
            heatmap_path = output_dir / "tier_heatmap.png"
            create_swap_heatmap(
                tier_matrix,
                output_path=heatmap_path,
                title="Swap Success Tiers (0=Fail, 5=Perfect)",
            )
            print(f"  Exported heatmap to: {heatmap_path}")
        except ImportError as e:
            print(f"  Warning: Could not generate heatmap: {e}")
            print("  Run: python scripts/visualization/swap_heatmap.py --help")
    
    # Print summary
    print("\n" + "="*60)
    print("ANALYSIS SUMMARY")
    print("="*60)
    print(f"Total swaps analyzed: {summary['total_swaps']}")
    print(f"\nAggregate metrics:")
    print(f"  Perfect match rate:      {summary['aggregate']['perfect_rate']:.1%}")
    print(f"  State-correct rate:      {summary['aggregate']['state_correct_rate']:.1%}")
    print(f"  Source suppression rate: {summary['aggregate']['suppression_rate']:.1%}")
    print(f"  Average tier:            {summary['aggregate']['avg_tier']:.2f}/5.0")
    
    print(f"\nTop target states (by perfect rate):")
    sorted_targets = sorted(
        summary['by_target_state'].items(),
        key=lambda x: x[1]['perfect_rate'],
        reverse=True
    )[:5]
    for state, stats in sorted_targets:
        print(f"  {state}: {stats['perfect_rate']:.1%} perfect ({stats['count']} swaps)")
    
    print(f"\nOutputs saved to: {output_dir}")
    print("="*60)
    
    return 0


if __name__ == '__main__':
    sys.exit(main())

