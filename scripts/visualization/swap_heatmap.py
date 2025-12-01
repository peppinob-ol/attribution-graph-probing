"""
Heatmap visualization for swap experiment results.

Creates annotated heatmaps showing swap success tiers across
source/target state combinations.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import matplotlib.colors as mcolors
import numpy as np
import pandas as pd


def create_swap_heatmap(
    tier_matrix: pd.DataFrame,
    output_path: Optional[Path] = None,
    title: str = "Swap Success Tiers",
    figsize: tuple = (14, 12),
    annotate: bool = True,
    show_marginals: bool = True,
) -> plt.Figure:
    """
    Create a heatmap visualization of swap tier results.
    
    Args:
        tier_matrix: DataFrame with source as index, target as columns, tier values (0-5)
        output_path: Path to save figure (optional)
        title: Plot title
        figsize: Figure size (width, height)
        annotate: Whether to show tier values in cells
        show_marginals: Whether to show row/column averages
    
    Returns:
        matplotlib Figure object
    """
    # Extract state names from slugs for cleaner labels
    def slug_to_state(slug: str) -> str:
        # "california_oakland" -> "CA"
        state_abbrevs = {
            'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
            'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
            'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
            'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
            'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
            'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
            'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
            'new_hampshire': 'NH', 'new_jersey': 'NJ', 'new_mexico': 'NM', 'new_york': 'NY',
            'north_carolina': 'NC', 'north_dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
            'oregon': 'OR', 'pennsylvania': 'PA', 'rhode_island': 'RI', 'south_carolina': 'SC',
            'south_dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
            'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west_virginia': 'WV',
            'wisconsin': 'WI', 'wyoming': 'WY',
        }
        state_part = slug.split('_')[0]
        # Handle two-word states like "new_york"
        if state_part == 'new' or state_part == 'north' or state_part == 'south' or state_part == 'west' or state_part == 'rhode':
            state_part = '_'.join(slug.split('_')[:2])
        return state_abbrevs.get(state_part, state_part[:2].upper())
    
    # Create figure
    fig, ax = plt.subplots(figsize=figsize)
    
    # Get data as numpy array
    data = tier_matrix.values.astype(float)
    
    # Create custom colormap: red (0) -> yellow (2.5) -> green (5)
    colors = ['#d73027', '#fc8d59', '#fee08b', '#d9ef8b', '#91cf60', '#1a9850']
    n_bins = 6  # 0, 1, 2, 3, 4, 5
    cmap = mcolors.LinearSegmentedColormap.from_list('tier_cmap', colors, N=n_bins)
    
    # Handle NaN values - show as gray
    cmap.set_bad(color='#f0f0f0')
    
    # Create masked array for NaN handling
    masked_data = np.ma.masked_invalid(data)
    
    # Plot heatmap
    im = ax.imshow(masked_data, cmap=cmap, vmin=0, vmax=5, aspect='auto')
    
    # Get labels
    row_labels = [slug_to_state(s) for s in tier_matrix.index]
    col_labels = [slug_to_state(s) for s in tier_matrix.columns]
    
    # Set ticks
    ax.set_xticks(np.arange(len(col_labels)))
    ax.set_yticks(np.arange(len(row_labels)))
    ax.set_xticklabels(col_labels, fontsize=8)
    ax.set_yticklabels(row_labels, fontsize=8)
    
    # Rotate x labels
    plt.setp(ax.get_xticklabels(), rotation=45, ha='right', rotation_mode='anchor')
    
    # Add annotations
    if annotate:
        for i in range(len(row_labels)):
            for j in range(len(col_labels)):
                val = data[i, j]
                if not np.isnan(val):
                    # Choose text color based on background
                    text_color = 'white' if val <= 1.5 or val >= 4 else 'black'
                    ax.text(j, i, f'{int(val)}', ha='center', va='center',
                           color=text_color, fontsize=7, fontweight='bold')
    
    # Add marginal averages
    if show_marginals:
        # Row averages (source performance)
        row_means = np.nanmean(data, axis=1)
        for i, mean in enumerate(row_means):
            if not np.isnan(mean):
                ax.text(len(col_labels) + 0.5, i, f'{mean:.1f}', 
                       ha='left', va='center', fontsize=7, color='gray')
        
        # Column averages (target performance)
        col_means = np.nanmean(data, axis=0)
        for j, mean in enumerate(col_means):
            if not np.isnan(mean):
                ax.text(j, len(row_labels) + 0.5, f'{mean:.1f}',
                       ha='center', va='top', fontsize=7, color='gray', rotation=45)
    
    # Labels
    ax.set_xlabel('Target State', fontsize=10, fontweight='bold')
    ax.set_ylabel('Source State', fontsize=10, fontweight='bold')
    ax.set_title(title, fontsize=12, fontweight='bold', pad=20)
    
    # Colorbar
    cbar = plt.colorbar(im, ax=ax, shrink=0.8, pad=0.1)
    cbar.set_label('Success Tier', rotation=270, labelpad=20)
    cbar.set_ticks([0, 1, 2, 3, 4, 5])
    cbar.set_ticklabels(['0: Wrong', '1: Source', '2: Suppress', '3: State', '4: City', '5: Perfect'])
    
    # Adjust layout
    plt.tight_layout()
    
    # Save if path provided
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        print(f"Saved heatmap to: {output_path}")
    
    return fig


def create_target_performance_chart(
    tier_matrix: pd.DataFrame,
    output_path: Optional[Path] = None,
    title: str = "Swap Success by Target State",
) -> plt.Figure:
    """
    Create a bar chart showing average success tier by target state.
    
    Args:
        tier_matrix: DataFrame with source as index, target as columns
        output_path: Path to save figure (optional)
        title: Plot title
    
    Returns:
        matplotlib Figure object
    """
    # Compute column means (target performance)
    col_means = tier_matrix.mean(axis=0).sort_values(ascending=False)
    
    # Extract state abbreviations
    def slug_to_state(slug: str) -> str:
        state_abbrevs = {
            'alabama': 'AL', 'alaska': 'AK', 'arizona': 'AZ', 'arkansas': 'AR',
            'california': 'CA', 'colorado': 'CO', 'connecticut': 'CT', 'delaware': 'DE',
            'florida': 'FL', 'georgia': 'GA', 'hawaii': 'HI', 'idaho': 'ID',
            'illinois': 'IL', 'indiana': 'IN', 'iowa': 'IA', 'kansas': 'KS',
            'kentucky': 'KY', 'louisiana': 'LA', 'maine': 'ME', 'maryland': 'MD',
            'massachusetts': 'MA', 'michigan': 'MI', 'minnesota': 'MN', 'mississippi': 'MS',
            'missouri': 'MO', 'montana': 'MT', 'nebraska': 'NE', 'nevada': 'NV',
            'new_hampshire': 'NH', 'new_jersey': 'NJ', 'new_mexico': 'NM', 'new_york': 'NY',
            'north_carolina': 'NC', 'north_dakota': 'ND', 'ohio': 'OH', 'oklahoma': 'OK',
            'oregon': 'OR', 'pennsylvania': 'PA', 'rhode_island': 'RI', 'south_carolina': 'SC',
            'south_dakota': 'SD', 'tennessee': 'TN', 'texas': 'TX', 'utah': 'UT',
            'vermont': 'VT', 'virginia': 'VA', 'washington': 'WA', 'west_virginia': 'WV',
            'wisconsin': 'WI', 'wyoming': 'WY',
        }
        state_part = slug.split('_')[0]
        if state_part in ['new', 'north', 'south', 'west', 'rhode']:
            state_part = '_'.join(slug.split('_')[:2])
        return state_abbrevs.get(state_part, state_part[:2].upper())
    
    labels = [slug_to_state(s) for s in col_means.index]
    values = col_means.values
    
    # Create figure
    fig, ax = plt.subplots(figsize=(12, 6))
    
    # Color bars by value
    colors = ['#1a9850' if v >= 4 else '#91cf60' if v >= 3 else '#fee08b' if v >= 2 else '#fc8d59' if v >= 1 else '#d73027' for v in values]
    
    bars = ax.bar(range(len(labels)), values, color=colors, edgecolor='white', linewidth=0.5)
    
    # Add value labels on bars
    for i, (bar, val) in enumerate(zip(bars, values)):
        if not np.isnan(val):
            ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.1,
                   f'{val:.1f}', ha='center', va='bottom', fontsize=8)
    
    # Set labels
    ax.set_xticks(range(len(labels)))
    ax.set_xticklabels(labels, rotation=45, ha='right', fontsize=9)
    ax.set_ylabel('Average Success Tier', fontsize=10)
    ax.set_xlabel('Target State', fontsize=10)
    ax.set_title(title, fontsize=12, fontweight='bold')
    ax.set_ylim(0, 5.5)
    
    # Add tier reference lines
    for tier in [1, 2, 3, 4, 5]:
        ax.axhline(y=tier, color='gray', linestyle='--', alpha=0.3, linewidth=0.5)
    
    plt.tight_layout()
    
    if output_path:
        fig.savefig(output_path, dpi=150, bbox_inches='tight', facecolor='white')
        print(f"Saved chart to: {output_path}")
    
    return fig


def main():
    parser = argparse.ArgumentParser(
        description='Generate heatmap visualizations for swap results'
    )
    parser.add_argument(
        'tier_matrix_csv',
        type=str,
        help='Path to tier_matrix.csv file'
    )
    parser.add_argument(
        '-o', '--output-dir',
        type=str,
        default=None,
        help='Output directory for figures (default: same as input)'
    )
    parser.add_argument(
        '--no-annotations',
        action='store_true',
        help='Skip cell value annotations'
    )
    parser.add_argument(
        '--no-marginals',
        action='store_true',
        help='Skip marginal averages'
    )
    
    args = parser.parse_args()
    
    # Load tier matrix
    input_path = Path(args.tier_matrix_csv)
    if not input_path.exists():
        print(f"Error: File not found: {input_path}")
        return 1
    
    print(f"Loading tier matrix from: {input_path}")
    tier_matrix = pd.read_csv(input_path, index_col=0)
    print(f"  Matrix shape: {tier_matrix.shape}")
    
    # Determine output directory
    output_dir = Path(args.output_dir) if args.output_dir else input_path.parent
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Generate heatmap
    print("\nGenerating tier heatmap...")
    create_swap_heatmap(
        tier_matrix,
        output_path=output_dir / "tier_heatmap.png",
        title="Swap Success Tiers (0=Fail, 5=Perfect)",
        annotate=not args.no_annotations,
        show_marginals=not args.no_marginals,
    )
    
    # Generate target performance chart
    print("\nGenerating target performance chart...")
    create_target_performance_chart(
        tier_matrix,
        output_path=output_dir / "target_performance.png",
        title="Average Success Tier by Target State",
    )
    
    print(f"\nFigures saved to: {output_dir}")
    return 0


if __name__ == '__main__':
    import sys
    sys.exit(main())

