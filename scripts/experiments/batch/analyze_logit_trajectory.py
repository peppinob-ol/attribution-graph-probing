"""
Analyze swap experiment results using logit trajectory metrics.

Provides continuous metrics instead of discrete tiers, enabling:
- Effect size analysis (how much did target logit improve?)
- Specificity verification (did control tokens remain stable?)
- Partial success quantification (did we get close to flip even without top-1?)
- Trajectory visualization (when does target become prominent?)

Usage:
    python scripts/experiments/batch/analyze_logit_trajectory.py --help
    
    # Analyze a completed swap run
    python scripts/experiments/batch/analyze_logit_trajectory.py \\
        --swaps-dir output/usa_states_batch/_swaps/runs/full_50states_v1

    # Generate visualizations
    python scripts/experiments/batch/analyze_logit_trajectory.py \\
        --swaps-dir output/usa_states_batch/_swaps/runs/full_50states_v1 \\
        --visualize
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd


def load_results_with_trajectory(swaps_dir: Path) -> List[Dict[str, Any]]:
    """
    Load swap results that have trajectory data.
    
    Args:
        swaps_dir: Path to _swaps directory or specific run directory
    
    Returns:
        List of result dicts with trajectory data
    """
    # Find by_source directory
    if (swaps_dir / "by_source").exists():
        by_source_dir = swaps_dir / "by_source"
    elif swaps_dir.name == "by_source":
        by_source_dir = swaps_dir
    else:
        raise FileNotFoundError(f"by_source directory not found in: {swaps_dir}")
    
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


def has_trajectory(result: Dict[str, Any]) -> bool:
    """Check if a result has trajectory data."""
    return 'logit_trajectory' in result.get('evaluation', {})


def extract_trajectory_metrics(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """
    Extract key trajectory metrics from a result.
    
    Returns None if no trajectory data is present.
    """
    eval_data = result.get('evaluation', {})
    trajectory = eval_data.get('logit_trajectory')
    baseline = eval_data.get('baseline_logits')
    pos0_comp = eval_data.get('position_0_comparison')
    
    if not trajectory:
        return None
    
    summary = trajectory.get('summary', {})
    target_traj = trajectory.get('trajectories', {}).get('target')
    source_traj = trajectory.get('trajectories', {}).get('source')
    
    evaluation = result.get('evaluation', {})
    answer_field = evaluation.get('answer_field', 'capital')
    from_answer = evaluation.get('from_answer', result.get('source', {}).get('capital', ''))
    to_answer = evaluation.get('to_answer', result.get('target', {}).get('capital', ''))

    metrics = {
        # Identification
        'swap_id': result.get('swap_id'),
        'from_slug': result.get('source', {}).get('slug'),
        'to_slug': result.get('target', {}).get('slug'),
        'from_answer': from_answer,
        'to_answer': to_answer,
        'answer_field': answer_field,
        # Backward-compatible aliases
        'from_capital': from_answer,
        'to_capital': to_answer,
        
        # Trajectory summary
        'n_positions': trajectory.get('n_positions', 0),
        'target_appears_at': summary.get('target_appears_at'),
        'source_appears_at': summary.get('source_appears_at'),
        'flip_position': summary.get('flip_position'),
        
        # Gap metrics
        'initial_gap': summary.get('initial_gap'),
        'best_gap': summary.get('best_gap'),
        'final_gap': summary.get('final_gap'),
        'gap_closure': summary.get('gap_closure'),
        
        # Control stability
        'control_stability_mean': summary.get('control_stability_mean'),
        'control_stability_max': summary.get('control_stability_max'),
    }
    
    # Target trajectory summary
    if target_traj:
        target_summary = target_traj.get('summary', {})
        metrics.update({
            'target_first_top1': target_summary.get('first_top1_position'),
            'target_first_top5': target_summary.get('first_top5_position'),
            'target_first_top10': target_summary.get('first_top10_position'),
            'target_max_prob': target_summary.get('max_prob'),
            'target_min_rank': target_summary.get('min_rank'),
            'target_final_rank': target_summary.get('final_rank'),
            'target_rank_improvement': target_summary.get('rank_improvement'),
        })
    
    # Source trajectory summary
    if source_traj:
        source_summary = source_traj.get('summary', {})
        metrics.update({
            'source_final_rank': source_summary.get('final_rank'),
            'source_max_prob': source_summary.get('max_prob'),
        })
    
    # Position 0 comparison (baseline vs steered)
    if pos0_comp:
        metrics.update({
            'target_logit_delta_0': pos0_comp.get('target_logit_delta'),
            'source_logit_delta_0': pos0_comp.get('source_logit_delta'),
            'baseline_gap': pos0_comp.get('baseline_gap'),
            'steered_gap_0': pos0_comp.get('steered_gap_0'),
            'gap_closure_0': pos0_comp.get('gap_closure_0'),
            'target_rank_improvement_0': pos0_comp.get('target_rank_improvement'),
            'flip_at_0': pos0_comp.get('flip_at_0', False),
        })
    
    # Baseline info
    if baseline:
        baseline_target = baseline.get('target', {})
        baseline_source = baseline.get('source', {})
        metrics.update({
            'baseline_target_rank': baseline_target.get('rank') if baseline_target else None,
            'baseline_source_rank': baseline_source.get('rank') if baseline_source else None,
            'baseline_target_prob': baseline_target.get('prob') if baseline_target else None,
            'baseline_source_prob': baseline_source.get('prob') if baseline_source else None,
        })

    # Contrast-group specificity (same-dataset alternative answers)
    cg = trajectory.get('contrast_groups', {}).get('same_dataset')
    if cg:
        agg = cg.get('aggregate', {})
        metrics.update({
            'contrast_n_members': cg.get('n_members'),
            'contrast_topk_k': cg.get('topk_k'),
            'contrast_initial_target_minus_max': agg.get('initial_target_minus_max'),
            'contrast_best_target_minus_max': agg.get('best_target_minus_max'),
            'contrast_initial_target_minus_topk': agg.get('initial_target_minus_topk'),
            'contrast_best_target_minus_topk': agg.get('best_target_minus_topk'),
            'contrast_initial_rank_within': agg.get('initial_rank_within'),
            'contrast_best_rank_within': agg.get('best_rank_within'),
            'contrast_initial_target_minus_mean': agg.get('initial_target_minus_mean'),
            'contrast_best_target_minus_mean': agg.get('best_target_minus_mean'),
        })
    
    return metrics


def compute_trajectory_summary(results: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Compute aggregate summary statistics from trajectory metrics.
    """
    # Extract metrics from all results with trajectory data
    metrics_list = []
    for r in results:
        m = extract_trajectory_metrics(r)
        if m:
            metrics_list.append(m)
    
    if not metrics_list:
        return {'error': 'No trajectory data found in results'}
    
    total = len(metrics_list)
    
    # Helper for safe statistics
    def safe_stats(values: List[Optional[float]]) -> Dict[str, Optional[float]]:
        valid = [v for v in values if v is not None]
        if not valid:
            return {'mean': None, 'std': None, 'median': None, 'min': None, 'max': None}
        return {
            'mean': float(np.mean(valid)),
            'std': float(np.std(valid)),
            'median': float(np.median(valid)),
            'min': float(np.min(valid)),
            'max': float(np.max(valid)),
        }
    
    # Gap closure statistics
    gap_closures = [m.get('gap_closure') for m in metrics_list]
    gap_closures_0 = [m.get('gap_closure_0') for m in metrics_list]
    
    # Flip statistics
    flips = [m.get('flip_position') for m in metrics_list]
    flips_at_0 = [m.get('flip_at_0', False) for m in metrics_list]
    
    # Target reaching top-N
    target_top1 = [m.get('target_first_top1') for m in metrics_list]
    target_top5 = [m.get('target_first_top5') for m in metrics_list]
    target_top10 = [m.get('target_first_top10') for m in metrics_list]
    
    # Control stability
    stability_mean = [m.get('control_stability_mean') for m in metrics_list]
    stability_max = [m.get('control_stability_max') for m in metrics_list]
    
    # Target rank improvement
    rank_improvement = [m.get('target_rank_improvement') for m in metrics_list]
    rank_improvement_0 = [m.get('target_rank_improvement_0') for m in metrics_list]
    
    # Target logit delta
    target_logit_delta = [m.get('target_logit_delta_0') for m in metrics_list]
    
    summary = {
        'total_with_trajectory': total,
        
        'gap_closure': {
            'over_trajectory': safe_stats(gap_closures),
            'at_position_0': safe_stats(gap_closures_0),
            'positive_rate': sum(1 for g in gap_closures if g and g > 0) / total,
        },
        
        'flip_achieved': {
            'any_position_rate': sum(1 for f in flips if f is not None) / total,
            'position_0_rate': sum(1 for f in flips_at_0 if f) / total,
            'mean_flip_position': float(np.mean([f for f in flips if f is not None])) if any(f is not None for f in flips) else None,
        },
        
        'target_reaches_top_n': {
            'top1_rate': sum(1 for t in target_top1 if t is not None) / total,
            'top5_rate': sum(1 for t in target_top5 if t is not None) / total,
            'top10_rate': sum(1 for t in target_top10 if t is not None) / total,
            'mean_first_top5_position': float(np.mean([t for t in target_top5 if t is not None])) if any(t is not None for t in target_top5) else None,
        },
        
        'target_rank_improvement': {
            'over_trajectory': safe_stats(rank_improvement),
            'at_position_0': safe_stats(rank_improvement_0),
        },
        
        'target_logit_delta': safe_stats(target_logit_delta),
        
        'control_stability': {
            'mean': safe_stats(stability_mean),
            'max': safe_stats(stability_max),
            'high_specificity_rate': sum(1 for s in stability_mean if s and s < 1.0) / total,
        },
    }

    # Contrast-group specificity (present only for runs with contrast_tokens)
    has_contrast = [m for m in metrics_list if m.get('contrast_n_members') is not None]
    if has_contrast:
        n_cg = len(has_contrast)
        rank_within_vals = [m['contrast_best_rank_within'] for m in has_contrast
                           if m.get('contrast_best_rank_within') is not None]
        summary['contrast_specificity'] = {
            'n_results_with_contrast': n_cg,
            'n_members_range': {
                'min': min(m['contrast_n_members'] for m in has_contrast),
                'max': max(m['contrast_n_members'] for m in has_contrast),
            },
            'topk_k': has_contrast[0].get('contrast_topk_k'),
            'target_vs_max_other': {
                'initial': safe_stats([m.get('contrast_initial_target_minus_max') for m in has_contrast]),
                'best': safe_stats([m.get('contrast_best_target_minus_max') for m in has_contrast]),
                'positive_rate': (
                    sum(1 for m in has_contrast
                        if (m.get('contrast_best_target_minus_max') or 0) > 0) / n_cg
                ),
            },
            'target_vs_topk_other': {
                'initial': safe_stats([m.get('contrast_initial_target_minus_topk') for m in has_contrast]),
                'best': safe_stats([m.get('contrast_best_target_minus_topk') for m in has_contrast]),
                'positive_rate': (
                    sum(1 for m in has_contrast
                        if (m.get('contrast_best_target_minus_topk') or 0) > 0) / n_cg
                ),
            },
            'rank_within_group': {
                'initial': safe_stats([m.get('contrast_initial_rank_within') for m in has_contrast]),
                'best': safe_stats(rank_within_vals),
                'top1_rate': (
                    sum(1 for v in rank_within_vals if v == 1) / len(rank_within_vals)
                    if rank_within_vals else 0
                ),
            },
            'target_vs_mean_other': {
                'initial': safe_stats([m.get('contrast_initial_target_minus_mean') for m in has_contrast]),
                'best': safe_stats([m.get('contrast_best_target_minus_mean') for m in has_contrast]),
            },
        }

    return summary


def create_trajectory_dataframe(results: List[Dict[str, Any]]) -> pd.DataFrame:
    """
    Create a DataFrame with trajectory metrics for each swap.
    """
    rows = []
    for r in results:
        m = extract_trajectory_metrics(r)
        if m:
            rows.append(m)
    
    if not rows:
        return pd.DataFrame()
    
    return pd.DataFrame(rows)


def analyze_by_target_entity(df: pd.DataFrame) -> pd.DataFrame:
    """
    Group trajectory metrics by target entity (slug).

    For USA states the slug encodes state_city, so grouping by slug
    effectively groups by entity.  For other domains the slug is the
    full entity identifier (e.g. 'hermione_granger').
    """
    if df.empty or 'to_slug' not in df.columns:
        return pd.DataFrame()

    df = df.copy()
    df['target_entity'] = df['to_slug']
    
    agg_funcs = {
        'gap_closure': ['mean', 'std', 'count'],
        'target_rank_improvement': 'mean',
        'target_first_top5': lambda x: (x.notna().sum() / len(x)) if len(x) > 0 else 0,
        'flip_position': lambda x: (x.notna().sum() / len(x)) if len(x) > 0 else 0,
    }
    
    # Only aggregate columns that exist
    valid_agg = {k: v for k, v in agg_funcs.items() if k in df.columns}
    
    if not valid_agg:
        return pd.DataFrame()
    
    return df.groupby('target_entity').agg(valid_agg)


# Backward-compatible alias
analyze_by_target_state = analyze_by_target_entity


def visualize_gap_trajectories(
    results: List[Dict[str, Any]],
    output_dir: Path,
    top_k: int = 10,
) -> None:
    """
    Create visualizations of gap trajectories.
    
    Args:
        results: List of results with trajectory data
        output_dir: Directory to save visualizations
        top_k: Number of top results to visualize individually
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("  Warning: matplotlib not available, skipping visualization")
        return
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Collect all gap trajectories
    trajectories = []
    for r in results:
        eval_data = r.get('evaluation', {})
        traj = eval_data.get('logit_trajectory', {})
        summary = traj.get('summary', {})
        gap_traj = summary.get('gap_trajectory', [])
        
        if gap_traj:
            trajectories.append({
                'swap_id': r.get('swap_id'),
                'gap_trajectory': gap_traj,
                'gap_closure': summary.get('gap_closure'),
                'flip_position': summary.get('flip_position'),
            })
    
    if not trajectories:
        print("  No gap trajectories found")
        return
    
    # Sort by gap closure (best to worst)
    trajectories.sort(key=lambda x: x.get('gap_closure') or float('-inf'), reverse=True)
    
    # 1. Plot top-k individual trajectories
    fig, ax = plt.subplots(figsize=(12, 6))
    
    for i, t in enumerate(trajectories[:top_k]):
        gap_traj = t['gap_trajectory']
        label = f"{t['swap_id'][:30]}... (closure: {t['gap_closure']:.1f})" if t['gap_closure'] else t['swap_id'][:40]
        ax.plot(range(len(gap_traj)), gap_traj, label=label, alpha=0.7)
        
        # Mark flip position if exists
        if t['flip_position'] is not None:
            ax.axvline(x=t['flip_position'], color='gray', linestyle='--', alpha=0.3)
    
    ax.axhline(y=0, color='black', linestyle='-', alpha=0.5, label='Flip threshold')
    ax.set_xlabel('Generation Position')
    ax.set_ylabel('Target - Source Logit Gap')
    ax.set_title(f'Top {min(top_k, len(trajectories))} Gap Trajectories (by closure)')
    ax.legend(bbox_to_anchor=(1.05, 1), loc='upper left', fontsize=8)
    plt.tight_layout()
    
    fig.savefig(output_dir / 'top_gap_trajectories.png', dpi=150, bbox_inches='tight')
    plt.close(fig)
    print(f"  Saved: {output_dir / 'top_gap_trajectories.png'}")
    
    # 2. Aggregate trajectory plot (mean + std)
    max_len = max(len(t['gap_trajectory']) for t in trajectories)
    padded = []
    for t in trajectories:
        gt = t['gap_trajectory']
        # Pad with last value
        padded.append(gt + [gt[-1]] * (max_len - len(gt)) if gt else [0] * max_len)
    
    arr = np.array(padded)
    mean_traj = np.mean(arr, axis=0)
    std_traj = np.std(arr, axis=0)
    
    fig, ax = plt.subplots(figsize=(10, 5))
    positions = range(len(mean_traj))
    
    ax.plot(positions, mean_traj, 'b-', label='Mean gap', linewidth=2)
    ax.fill_between(positions, mean_traj - std_traj, mean_traj + std_traj, 
                    alpha=0.3, label='+/- 1 std')
    ax.axhline(y=0, color='red', linestyle='--', alpha=0.7, label='Flip threshold')
    
    ax.set_xlabel('Generation Position')
    ax.set_ylabel('Target - Source Logit Gap')
    ax.set_title(f'Aggregate Gap Trajectory (n={len(trajectories)})')
    ax.legend()
    plt.tight_layout()
    
    fig.savefig(output_dir / 'aggregate_gap_trajectory.png', dpi=150)
    plt.close(fig)
    print(f"  Saved: {output_dir / 'aggregate_gap_trajectory.png'}")
    
    # 3. Gap closure distribution
    closures = [t['gap_closure'] for t in trajectories if t['gap_closure'] is not None]
    
    if closures:
        fig, ax = plt.subplots(figsize=(8, 5))
        ax.hist(closures, bins=30, edgecolor='black', alpha=0.7)
        ax.axvline(x=0, color='red', linestyle='--', label='No improvement')
        ax.axvline(x=np.mean(closures), color='green', linestyle='--', 
                   label=f'Mean: {np.mean(closures):.2f}')
        
        ax.set_xlabel('Gap Closure (logits)')
        ax.set_ylabel('Count')
        ax.set_title('Distribution of Gap Closure')
        ax.legend()
        plt.tight_layout()
        
        fig.savefig(output_dir / 'gap_closure_distribution.png', dpi=150)
        plt.close(fig)
        print(f"  Saved: {output_dir / 'gap_closure_distribution.png'}")


def main():
    parser = argparse.ArgumentParser(
        description='Analyze swap results using logit trajectory metrics'
    )
    parser.add_argument(
        '--swaps-dir',
        type=str,
        required=True,
        help='Path to _swaps directory or specific run directory'
    )
    parser.add_argument(
        '--output-dir',
        type=str,
        default=None,
        help='Output directory for analysis (default: {swaps-dir}/_trajectory_analysis)'
    )
    parser.add_argument(
        '--visualize',
        action='store_true',
        help='Generate visualizations (requires matplotlib)'
    )
    parser.add_argument(
        '--export-csv',
        action='store_true',
        help='Export detailed metrics to CSV'
    )
    parser.add_argument(
        '--primary-specificity',
        type=str,
        choices=['legacy', 'max', 'topk', 'rank'],
        default='legacy',
        help=(
            'Which specificity metric to highlight in output. '
            '"legacy" = stopword control stability (default), '
            '"max" = target vs max(other dataset answers), '
            '"topk" = target vs top-k mean(other), '
            '"rank" = rank within dataset group'
        ),
    )
    
    args = parser.parse_args()
    
    # Resolve paths
    swaps_dir = Path(args.swaps_dir)
    if not swaps_dir.exists():
        print(f"Error: Directory not found: {swaps_dir}")
        return 1
    
    output_dir = Path(args.output_dir) if args.output_dir else swaps_dir / "_trajectory_analysis"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Analyzing trajectory data in: {swaps_dir}")
    print(f"Output directory: {output_dir}")
    
    # Load results
    print("\n[1/4] Loading swap results...")
    results = load_results_with_trajectory(swaps_dir)
    print(f"  Loaded {len(results)} total results")
    
    # Count results with trajectory
    with_trajectory = [r for r in results if has_trajectory(r)]
    print(f"  Results with trajectory data: {len(with_trajectory)}")
    
    if not with_trajectory:
        print("\nNo trajectory data found. Make sure track_trajectory is enabled in config.")
        return 1
    
    # Compute summary
    print("\n[2/4] Computing trajectory summary...")
    summary = compute_trajectory_summary(with_trajectory)
    
    summary_path = output_dir / "trajectory_summary.json"
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    print(f"  Saved summary to: {summary_path}")
    
    # Create DataFrame
    print("\n[3/4] Creating metrics dataframe...")
    df = create_trajectory_dataframe(with_trajectory)
    print(f"  DataFrame shape: {df.shape}")
    
    if args.export_csv and not df.empty:
        csv_path = output_dir / "trajectory_metrics.csv"
        df.to_csv(csv_path, index=False)
        print(f"  Exported to: {csv_path}")
        
        by_entity = analyze_by_target_entity(df)
        if not by_entity.empty:
            entity_path = output_dir / "by_target_entity.csv"
            by_entity.to_csv(entity_path)
            print(f"  By-entity analysis: {entity_path}")
    
    # Visualizations
    if args.visualize:
        print("\n[4/4] Generating visualizations...")
        visualize_gap_trajectories(with_trajectory, output_dir)
    
    # Print summary
    spec_mode = args.primary_specificity
    print("\n" + "="*60)
    print("TRAJECTORY ANALYSIS SUMMARY")
    if spec_mode != 'legacy':
        spec_labels = {'max': 'target vs max(other)', 'topk': 'target vs top-k mean(other)', 'rank': 'rank within group'}
        print(f"  Primary specificity: {spec_labels.get(spec_mode, spec_mode)}")
    print("="*60)
    
    gc = summary.get('gap_closure', {})
    gc_traj = gc.get('over_trajectory', {})
    gc_0 = gc.get('at_position_0', {})
    
    def _fmt(val, fmt=".2f"):
        return f"{val:{fmt}}" if val is not None else "N/A"

    print(f"\nGap Closure:")
    print(f"  Over trajectory - Mean: {_fmt(gc_traj.get('mean'))}, Std: {_fmt(gc_traj.get('std'))}")
    print(f"  At position 0   - Mean: {_fmt(gc_0.get('mean'))}, Std: {_fmt(gc_0.get('std'))}")
    print(f"  Positive closure rate: {_fmt(gc.get('positive_rate', 0), '.1%')}")
    
    flip = summary.get('flip_achieved', {})
    print(f"\nFlip Achieved:")
    print(f"  Any position: {_fmt(flip.get('any_position_rate', 0), '.1%')}")
    print(f"  At position 0: {_fmt(flip.get('position_0_rate', 0), '.1%')}")
    mfp = flip.get('mean_flip_position')
    if mfp is not None:
        print(f"  Mean flip position: {mfp:.1f}")
    
    top_n = summary.get('target_reaches_top_n', {})
    print(f"\nTarget Reaches Top-N:")
    print(f"  Top-1: {_fmt(top_n.get('top1_rate', 0), '.1%')}")
    print(f"  Top-5: {_fmt(top_n.get('top5_rate', 0), '.1%')}")
    print(f"  Top-10: {_fmt(top_n.get('top10_rate', 0), '.1%')}")
    
    ctrl = summary.get('control_stability', {})
    print(f"\nControl Stability (stopword-based, legacy):")
    print(f"  Mean stability: {_fmt(ctrl.get('mean', {}).get('mean'))}")
    print(f"  High specificity rate: {_fmt(ctrl.get('high_specificity_rate', 0), '.1%')}")

    cs = summary.get('contrast_specificity')
    if cs:
        n_cg = cs.get('n_results_with_contrast', 0)
        mr = cs.get('n_members_range', {})
        topk_k = cs.get('topk_k', '?')
        print(f"\nContrast Specificity ({n_cg} results, "
              f"{mr.get('min','?')}-{mr.get('max','?')} dataset alternatives, "
              f"topk_k={topk_k}):")

        vm = cs.get('target_vs_max_other', {})
        print(f"  Target vs max(other):")
        print(f"    Initial: mean={_fmt(vm.get('initial', {}).get('mean'))}")
        print(f"    Best:    mean={_fmt(vm.get('best', {}).get('mean'))}, "
              f"positive_rate={_fmt(vm.get('positive_rate', 0), '.1%')}")

        vt = cs.get('target_vs_topk_other', {})
        print(f"  Target vs top-{topk_k} mean(other):")
        print(f"    Initial: mean={_fmt(vt.get('initial', {}).get('mean'))}")
        print(f"    Best:    mean={_fmt(vt.get('best', {}).get('mean'))}, "
              f"positive_rate={_fmt(vt.get('positive_rate', 0), '.1%')}")

        rw = cs.get('rank_within_group', {})
        print(f"  Rank within dataset group:")
        print(f"    Initial: mean={_fmt(rw.get('initial', {}).get('mean'))}")
        print(f"    Best:    mean={_fmt(rw.get('best', {}).get('mean'))}, "
              f"top1_rate={_fmt(rw.get('top1_rate', 0), '.1%')}")

    if spec_mode != 'legacy' and cs:
        print(f"\n--- Primary Specificity Metric ---")
        if spec_mode == 'max':
            block = cs.get('target_vs_max_other', {})
            print(f"  target vs max(other dataset answers)")
            print(f"  Best mean: {_fmt(block.get('best', {}).get('mean'))}")
            print(f"  Positive rate: {_fmt(block.get('positive_rate', 0), '.1%')}")
        elif spec_mode == 'topk':
            block = cs.get('target_vs_topk_other', {})
            print(f"  target vs top-{cs.get('topk_k', '?')} mean(other)")
            print(f"  Best mean: {_fmt(block.get('best', {}).get('mean'))}")
            print(f"  Positive rate: {_fmt(block.get('positive_rate', 0), '.1%')}")
        elif spec_mode == 'rank':
            block = cs.get('rank_within_group', {})
            print(f"  rank within dataset group")
            print(f"  Best mean rank: {_fmt(block.get('best', {}).get('mean'))}")
            print(f"  Top-1 rate: {_fmt(block.get('top1_rate', 0), '.1%')}")

    print(f"\nOutputs saved to: {output_dir}")
    print("="*60)
    
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())





