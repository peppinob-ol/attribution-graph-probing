"""
Create visualizations for cross-prompt robustness analysis.

Usage:
    python scripts/experiments/visualize_robustness.py --input_json <path> --output_dir <path>
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any

import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


def create_survival_summary_chart(results: Dict[str, Any], output_path: Path):
    """Create a summary chart showing survival rate and key metrics."""
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    # 1. Survival rate gauge
    survival_rate = results['survival_rate']
    survival_count = results['survival_count']
    n_common = results['n_common_features']
    
    ax = axes[0]
    colors = ['#2ecc71' if survival_rate >= 0.7 else '#e74c3c']
    ax.bar(['Survival\nRate'], [survival_rate], color=colors, alpha=0.8, edgecolor='black', linewidth=2)
    ax.axhline(y=0.7, color='red', linestyle='--', linewidth=2, label='Threshold (70%)')
    ax.set_ylim(0, 1.0)
    ax.set_ylabel('Rate', fontsize=12, fontweight='bold')
    ax.set_title(f'Feature Survival Rate\n({survival_count}/{n_common} features)', 
                fontsize=12, fontweight='bold')
    ax.text(0, survival_rate + 0.05, f'{survival_rate:.1%}', 
           ha='center', fontsize=16, fontweight='bold')
    ax.legend(fontsize=9)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    # 2. Aggregate metrics
    ax = axes[1]
    agg = results['aggregate_metrics']
    
    metrics_names = ['Activation\nOverlap', 'Peak Token\nConsistency', 'Layer\nSimilarity']
    metrics_values = [
        agg['mean_activation_overlap'],
        agg['mean_peak_token_consistency'],
        1.0 if agg['mean_layer_pvalue'] > 0.05 else 0.5  # Binary for visualization
    ]
    
    colors_bars = ['#3498db', '#9b59b6', '#e67e22']
    bars = ax.bar(metrics_names, metrics_values, color=colors_bars, alpha=0.8, 
                  edgecolor='black', linewidth=1.5)
    ax.set_ylim(0, 1.1)
    ax.set_ylabel('Score', fontsize=12, fontweight='bold')
    ax.set_title('Robustness Metrics', fontsize=12, fontweight='bold')
    ax.axhline(y=0.7, color='red', linestyle='--', linewidth=1, alpha=0.5)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    for i, (bar, val) in enumerate(zip(bars, metrics_values)):
        ax.text(bar.get_x() + bar.get_width()/2, val + 0.03, 
               f'{val:.2f}', ha='center', fontsize=11, fontweight='bold')
    
    # 3. Feature coverage
    ax = axes[2]
    
    n_prompt1 = results['n_features_prompt1']
    n_prompt2 = results['n_features_prompt2']
    n_common = results['n_common_features']
    
    prompt1_only = n_prompt1 - n_common
    prompt2_only = n_prompt2 - n_common
    
    categories = [results['prompt1'], results['prompt2'], 'Common']
    values = [n_prompt1, n_prompt2, n_common]
    colors_cov = ['#3498db', '#e74c3c', '#2ecc71']
    
    bars = ax.bar(categories, values, color=colors_cov, alpha=0.8, 
                  edgecolor='black', linewidth=1.5)
    ax.set_ylabel('Feature Count', fontsize=12, fontweight='bold')
    ax.set_title('Feature Coverage', fontsize=12, fontweight='bold')
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    
    for bar, val in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width()/2, val + 1, 
               str(val), ha='center', fontsize=11, fontweight='bold')
    
    plt.suptitle(f'Cross-Prompt Robustness: {results["prompt1"]} vs {results["prompt2"]}',
                fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved survival summary to {output_path}")
    plt.close()


def create_feature_level_analysis(results: Dict[str, Any], output_path: Path):
    """Create per-feature analysis chart."""
    feature_results = results['feature_results']
    
    # Extract metrics
    feature_keys = [f['feature_key'] for f in feature_results]
    activation_overlaps = [f['metrics'].get('activation_overlap', 0) for f in feature_results]
    peak_consistencies = [f['metrics'].get('peak_token_consistency', 0) for f in feature_results]
    survives = [f.get('survives', False) for f in feature_results]
    
    # Sort by survival then overlap
    sorted_indices = sorted(range(len(feature_results)), 
                           key=lambda i: (survives[i], activation_overlaps[i]), 
                           reverse=True)
    
    feature_keys_sorted = [feature_keys[i] for i in sorted_indices]
    activation_overlaps_sorted = [activation_overlaps[i] for i in sorted_indices]
    peak_consistencies_sorted = [peak_consistencies[i] for i in sorted_indices]
    survives_sorted = [survives[i] for i in sorted_indices]
    
    # Limit to top 25 for visibility
    n_show = min(25, len(feature_results))
    feature_keys_show = feature_keys_sorted[:n_show]
    activation_overlaps_show = activation_overlaps_sorted[:n_show]
    peak_consistencies_show = peak_consistencies_sorted[:n_show]
    survives_show = survives_sorted[:n_show]
    
    fig, ax = plt.subplots(figsize=(12, 8))
    
    x = np.arange(n_show)
    width = 0.35
    
    colors_act = ['#2ecc71' if s else '#e74c3c' for s in survives_show]
    colors_peak = ['#3498db' if s else '#e74c3c' for s in survives_show]
    
    bars1 = ax.bar(x - width/2, activation_overlaps_show, width, label='Activation Overlap',
                  color=colors_act, alpha=0.8, edgecolor='black', linewidth=1)
    bars2 = ax.bar(x + width/2, peak_consistencies_show, width, label='Peak Token Consistency',
                  color=colors_peak, alpha=0.8, edgecolor='black', linewidth=1)
    
    ax.axhline(y=0.7, color='red', linestyle='--', linewidth=2, label='Survival Threshold')
    ax.set_ylabel('Score', fontsize=12, fontweight='bold')
    ax.set_xlabel('Features', fontsize=12, fontweight='bold')
    ax.set_title(f'Per-Feature Robustness Metrics (Top {n_show})', 
                fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(feature_keys_show, rotation=45, ha='right', fontsize=8)
    ax.legend(fontsize=10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.set_ylim(0, 1.1)
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved feature-level analysis to {output_path}")
    plt.close()


def create_entity_mapping_diagram(results: Dict[str, Any], output_path: Path):
    """Create a diagram showing entity mappings."""
    entity_mapping = results['entity_mapping']
    
    fig, ax = plt.subplots(figsize=(10, 6))
    ax.axis('off')
    
    n_entities = len(entity_mapping)
    y_positions = np.linspace(0.8, 0.2, n_entities)
    
    prompt1_name = results['prompt1']
    prompt2_name = results['prompt2']
    
    # Draw headers
    ax.text(0.2, 0.95, prompt1_name, fontsize=16, fontweight='bold', 
           ha='center', va='center',
           bbox=dict(boxstyle='round,pad=0.5', facecolor='#3498db', alpha=0.8, edgecolor='black', linewidth=2))
    ax.text(0.8, 0.95, prompt2_name, fontsize=16, fontweight='bold', 
           ha='center', va='center',
           bbox=dict(boxstyle='round,pad=0.5', facecolor='#e74c3c', alpha=0.8, edgecolor='black', linewidth=2))
    
    # Draw entity mappings
    for i, (old_entity, new_entity) in enumerate(entity_mapping.items()):
        y = y_positions[i]
        
        # Old entity box
        ax.text(0.2, y, old_entity, fontsize=14, ha='center', va='center',
               bbox=dict(boxstyle='round,pad=0.4', facecolor='lightblue', 
                        alpha=0.7, edgecolor='black', linewidth=1.5))
        
        # New entity box
        ax.text(0.8, y, new_entity, fontsize=14, ha='center', va='center',
               bbox=dict(boxstyle='round,pad=0.4', facecolor='lightcoral', 
                        alpha=0.7, edgecolor='black', linewidth=1.5))
        
        # Arrow
        ax.annotate('', xy=(0.75, y), xytext=(0.25, y),
                   arrowprops=dict(arrowstyle='->', lw=3, color='black', alpha=0.6))
    
    # Add survival rate
    survival_rate = results['survival_rate']
    ax.text(0.5, 0.05, f'Survival Rate: {survival_rate:.0%}', 
           fontsize=18, ha='center', fontweight='bold',
           bbox=dict(boxstyle='round,pad=0.5', 
                    facecolor='#2ecc71' if survival_rate >= 0.7 else '#e74c3c',
                    alpha=0.8, edgecolor='black', linewidth=2))
    
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    
    plt.title('Entity Swap Test', fontsize=18, fontweight='bold', pad=20)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved entity mapping diagram to {output_path}")
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_json", type=str, required=True, help="Robustness results JSON")
    parser.add_argument("--output_dir", type=str, default=None, help="Output directory")
    
    args = parser.parse_args()
    
    input_path = Path(args.input_json)
    
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = input_path.parent
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(input_path, "r") as f:
        results = json.load(f)
    
    print("Creating visualizations...")
    
    create_survival_summary_chart(
        results,
        output_dir / "robustness_summary.png"
    )
    
    create_feature_level_analysis(
        results,
        output_dir / "robustness_feature_analysis.png"
    )
    
    create_entity_mapping_diagram(
        results,
        output_dir / "entity_mapping_diagram.png"
    )
    
    print(f"\nAll visualizations saved to {output_dir}")


if __name__ == "__main__":
    main()


