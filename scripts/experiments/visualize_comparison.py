"""
Create publication-ready visualizations comparing grouping methods.

Usage:
    python scripts/experiments/visualize_comparison.py --input_json <comparison.json> --output_dir <dir>
"""

import argparse
import json
from pathlib import Path
from typing import Dict, Any

import matplotlib.pyplot as plt
import numpy as np


def create_coherence_comparison_chart(comparison: Dict[str, Any], output_path: Path):
    """Create a bar chart comparing coherence metrics."""
    coherence = comparison.get("coherence", {})
    
    # Metrics to plot (higher is better)
    metrics_higher = ["peak_token_consistency", "activation_similarity"]
    metrics_lower = ["sparsity_consistency_avg"]
    
    fig, axes = plt.subplots(1, 3, figsize=(15, 5))
    
    # Plot higher-is-better metrics
    for idx, metric in enumerate(metrics_higher):
        data = coherence.get(metric, {})
        
        methods = ["Concept\nAligned", "Cosine\nSimilarity", "Layer\nAdjacency"]
        values = [
            data.get("concept_aligned", 0),
            data.get("cosine_similarity", 0),
            data.get("layer_adjacency", 0)
        ]
        
        colors = ["#2ecc71" if data.get("best") == "concept_aligned" else "#3498db" 
                 if data.get("best") == "cosine_similarity" else "#e74c3c" 
                 for _ in values]
        
        best_idx = ["concept_aligned", "cosine_similarity", "layer_adjacency"].index(data.get("best", "concept_aligned"))
        colors = ["#95a5a6"] * 3
        colors[best_idx] = "#2ecc71"
        
        axes[idx].bar(methods, values, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
        axes[idx].set_title(metric.replace("_", " ").title(), fontsize=12, fontweight='bold')
        axes[idx].set_ylabel("Score", fontsize=10)
        axes[idx].grid(axis='y', alpha=0.3, linestyle='--')
        axes[idx].set_ylim(0, max(values) * 1.2)
        
        # Add value labels on bars
        for i, v in enumerate(values):
            axes[idx].text(i, v + max(values) * 0.02, f"{v:.3f}", 
                          ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    # Plot lower-is-better metric (inverted display)
    metric = "sparsity_consistency_avg"
    data = coherence.get(metric, {})
    
    methods = ["Concept\nAligned", "Cosine\nSimilarity", "Layer\nAdjacency"]
    values = [
        data.get("concept_aligned", 0),
        data.get("cosine_similarity", 0),
        data.get("layer_adjacency", 0)
    ]
    
    best_idx = ["concept_aligned", "cosine_similarity", "layer_adjacency"].index(data.get("best", "concept_aligned"))
    colors = ["#95a5a6"] * 3
    colors[best_idx] = "#2ecc71"
    
    axes[2].bar(methods, values, color=colors, alpha=0.8, edgecolor='black', linewidth=1.5)
    axes[2].set_title("Sparsity Consistency\n(Lower is Better)", fontsize=12, fontweight='bold')
    axes[2].set_ylabel("Score", fontsize=10)
    axes[2].grid(axis='y', alpha=0.3, linestyle='--')
    axes[2].set_ylim(0, max(values) * 1.2)
    
    for i, v in enumerate(values):
        axes[2].text(i, v + max(values) * 0.02, f"{v:.3f}", 
                    ha='center', va='bottom', fontsize=9, fontweight='bold')
    
    plt.suptitle("Coherence Metrics Comparison", fontsize=16, fontweight='bold', y=1.02)
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved coherence comparison to {output_path}")
    plt.close()


def create_improvement_chart(comparison: Dict[str, Any], output_path: Path):
    """Create a chart showing percentage improvements."""
    coherence = comparison.get("coherence", {})
    
    metrics = ["peak_token_consistency", "activation_similarity", "sparsity_consistency_avg"]
    metric_labels = ["Peak Token\nConsistency", "Activation\nSimilarity", "Sparsity\nConsistency"]
    
    improvements_cosine = []
    improvements_adjacency = []
    
    for metric in metrics:
        data = coherence.get(metric, {})
        improvements_cosine.append(data.get("improvement_vs_cosine", 0))
        improvements_adjacency.append(data.get("improvement_vs_adjacency", 0))
    
    x = np.arange(len(metric_labels))
    width = 0.35
    
    fig, ax = plt.subplots(figsize=(10, 6))
    
    bars1 = ax.bar(x - width/2, improvements_cosine, width, label='vs Cosine Similarity', 
                   color='#3498db', alpha=0.8, edgecolor='black', linewidth=1.5)
    bars2 = ax.bar(x + width/2, improvements_adjacency, width, label='vs Layer Adjacency', 
                   color='#e74c3c', alpha=0.8, edgecolor='black', linewidth=1.5)
    
    ax.set_ylabel('Improvement (%)', fontsize=12, fontweight='bold')
    ax.set_title('Concept-Aligned Grouping Improvements Over Baselines', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(metric_labels, fontsize=10)
    ax.legend(fontsize=10)
    ax.grid(axis='y', alpha=0.3, linestyle='--')
    ax.axhline(y=0, color='black', linestyle='-', linewidth=0.8)
    
    # Add value labels
    for bars in [bars1, bars2]:
        for bar in bars:
            height = bar.get_height()
            ax.text(bar.get_x() + bar.get_width()/2., height,
                   f'{height:.1f}%',
                   ha='center', va='bottom' if height >= 0 else 'top',
                   fontsize=9, fontweight='bold')
    
    plt.tight_layout()
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved improvement chart to {output_path}")
    plt.close()


def create_summary_table(comparison: Dict[str, Any], output_path: Path):
    """Create a summary table as an image."""
    coherence = comparison.get("coherence", {})
    
    # Prepare data
    data = []
    headers = ["Metric", "Concept-Aligned", "Cosine Sim", "Layer Adj", "Winner"]
    
    for metric, values in coherence.items():
        metric_name = metric.replace("_", " ").title()
        row = [
            metric_name,
            f"{values.get('concept_aligned', 0):.4f}",
            f"{values.get('cosine_similarity', 0):.4f}",
            f"{values.get('layer_adjacency', 0):.4f}",
            values.get('best', '').replace('_', ' ').title()
        ]
        data.append(row)
    
    fig, ax = plt.subplots(figsize=(12, 4))
    ax.axis('tight')
    ax.axis('off')
    
    table = ax.table(cellText=data, colLabels=headers, cellLoc='center', loc='center',
                    colWidths=[0.3, 0.15, 0.15, 0.15, 0.15])
    
    table.auto_set_font_size(False)
    table.set_fontsize(10)
    table.scale(1, 2)
    
    # Color header
    for i in range(len(headers)):
        table[(0, i)].set_facecolor('#34495e')
        table[(0, i)].set_text_props(weight='bold', color='white')
    
    # Color winner cells
    for i, row_data in enumerate(data):
        winner = row_data[4]
        if "Concept" in winner:
            table[(i+1, 1)].set_facecolor('#d5f4e6')
        elif "Cosine" in winner:
            table[(i+1, 2)].set_facecolor('#d5f4e6')
        elif "Layer" in winner or "Adjacency" in winner:
            table[(i+1, 3)].set_facecolor('#d5f4e6')
    
    plt.title("Coherence Metrics Summary", fontsize=14, fontweight='bold', pad=20)
    plt.savefig(output_path, dpi=300, bbox_inches='tight')
    print(f"Saved summary table to {output_path}")
    plt.close()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--input_json", type=str, required=True, help="Comparison results JSON")
    parser.add_argument("--output_dir", type=str, default=None, help="Output directory for visualizations")
    
    args = parser.parse_args()
    
    input_path = Path(args.input_json)
    
    if args.output_dir:
        output_dir = Path(args.output_dir)
    else:
        output_dir = input_path.parent
    
    output_dir.mkdir(parents=True, exist_ok=True)
    
    with open(input_path, "r") as f:
        results = json.load(f)
    
    comparison = results.get("comparison", {})
    
    print("Creating visualizations...")
    
    create_coherence_comparison_chart(
        comparison,
        output_dir / "coherence_comparison.png"
    )
    
    create_improvement_chart(
        comparison,
        output_dir / "improvement_chart.png"
    )
    
    create_summary_table(
        comparison,
        output_dir / "summary_table.png"
    )
    
    print(f"\nAll visualizations saved to {output_dir}")


if __name__ == "__main__":
    main()


