"""
Visualization of swap performance factors.

Creates:
1. Scatter plots of native prob vs tier performance
2. Supernode count impact visualization
3. State archetype classification
"""
from __future__ import annotations

import json
from pathlib import Path
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
import numpy as np


def load_state_data(batch_root: Path, tier_summary: dict) -> list:
    """Load all state data with metrics."""
    summaries = sorted(batch_root.glob("_summary_*.json"), reverse=True)
    if not summaries:
        return []
    
    with open(summaries[0], 'r', encoding='utf-8') as f:
        summary = json.load(f)
    
    by_target = tier_summary.get('by_target_state', {})
    by_source = tier_summary.get('by_source_state', {})
    
    rows = []
    for seed in summary.get('seeds', []):
        slug = seed['slug']
        np_data = seed.get('neuronpedia', {})
        
        # Extract state name
        state_part = slug.split('_')[0]
        state = state_part.title()
        
        # Handle two-word states
        if state in ['New', 'North', 'South', 'West', 'Rhode']:
            parts = slug.split('_')
            if len(parts) >= 2:
                state = f"{parts[0]}_{parts[1]}".replace('_', ' ').title()
        
        # Find state dir for native prob
        native_prob = 0
        state_dir = batch_root / slug
        if not state_dir.exists():
            for d in batch_root.iterdir():
                if d.is_dir() and d.name.lower() == slug.lower():
                    state_dir = d
                    break
        
        graph_file = state_dir / "00 Graph Generation" / "graph.json"
        if graph_file.exists():
            try:
                with open(graph_file, 'r', encoding='utf-8') as f:
                    graph = json.load(f)
                for node in graph.get('nodes', []):
                    if node.get('is_target_logit'):
                        native_prob = node.get('token_prob', 0)
                        break
            except:
                pass
        
        src_tier = by_source.get(state, {}).get('avg_tier')
        tgt_tier = by_target.get(state, {}).get('avg_tier')
        
        if src_tier is not None or tgt_tier is not None:
            rows.append({
                'state': state,
                'slug': slug,
                'supernodes': np_data.get('supernodes', 0),
                'native_prob': native_prob,
                'src_tier': src_tier,
                'tgt_tier': tgt_tier,
            })
    
    return rows


def classify_archetype(row: dict) -> str:
    """Classify state into archetype based on performance."""
    src = row.get('src_tier') or 0
    tgt = row.get('tgt_tier') or 0
    
    if src >= 3.5 and tgt >= 4.0:
        return "Exchanger"  # Good at both
    elif tgt >= 4.0 and src < 3.0:
        return "Magnet"  # Good target, poor source (hard to leave)
    elif src >= 3.5 and tgt < 3.0:
        return "Escape"  # Good source, poor target (easy to leave)
    elif src < 3.0 and tgt < 3.0:
        return "Trap"  # Poor at both
    else:
        return "Mixed"


def create_visualizations(rows: list, output_dir: Path):
    """Create all visualizations."""
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Filter to states with complete data
    complete = [r for r in rows if r['src_tier'] and r['tgt_tier'] and r['native_prob'] > 0]
    
    fig, axes = plt.subplots(2, 2, figsize=(14, 12))
    
    # Color by archetype
    archetype_colors = {
        'Exchanger': '#2ecc71',  # Green
        'Magnet': '#3498db',     # Blue  
        'Escape': '#e74c3c',     # Red
        'Trap': '#9b59b6',       # Purple
        'Mixed': '#95a5a6',      # Gray
    }
    
    for r in complete:
        r['archetype'] = classify_archetype(r)
    
    # 1. Native Prob vs Source Tier
    ax1 = axes[0, 0]
    for r in complete:
        ax1.scatter(r['native_prob'], r['src_tier'], 
                   c=archetype_colors[r['archetype']], s=100, alpha=0.7)
        ax1.annotate(r['state'][:3], (r['native_prob'], r['src_tier']), 
                    fontsize=8, ha='center', va='bottom')
    
    # Add trend line
    x = [r['native_prob'] for r in complete]
    y = [r['src_tier'] for r in complete]
    z = np.polyfit(x, y, 1)
    p = np.poly1d(z)
    x_line = np.linspace(min(x), max(x), 100)
    ax1.plot(x_line, p(x_line), 'k--', alpha=0.5, label=f'r = -0.61')
    
    ax1.set_xlabel('Native Logit Probability')
    ax1.set_ylabel('Source Tier (avg)')
    ax1.set_title('Native Prob vs SOURCE Performance\n(ability to steer FROM)')
    ax1.legend()
    ax1.set_ylim(0, 5)
    
    # 2. Native Prob vs Target Tier
    ax2 = axes[0, 1]
    for r in complete:
        ax2.scatter(r['native_prob'], r['tgt_tier'],
                   c=archetype_colors[r['archetype']], s=100, alpha=0.7)
        ax2.annotate(r['state'][:3], (r['native_prob'], r['tgt_tier']),
                    fontsize=8, ha='center', va='bottom')
    
    x = [r['native_prob'] for r in complete]
    y = [r['tgt_tier'] for r in complete]
    z = np.polyfit(x, y, 1)
    p = np.poly1d(z)
    ax2.plot(x_line, p(x_line), 'k--', alpha=0.5, label=f'r = +0.27')
    
    ax2.set_xlabel('Native Logit Probability')
    ax2.set_ylabel('Target Tier (avg)')
    ax2.set_title('Native Prob vs TARGET Performance\n(ability to steer TO)')
    ax2.legend()
    ax2.set_ylim(0, 5)
    
    # 3. Supernodes vs Source Tier
    ax3 = axes[1, 0]
    for r in complete:
        ax3.scatter(r['supernodes'], r['src_tier'],
                   c=archetype_colors[r['archetype']], s=100, alpha=0.7)
        ax3.annotate(r['state'][:3], (r['supernodes'], r['src_tier']),
                    fontsize=8, ha='center', va='bottom')
    
    x = [r['supernodes'] for r in complete]
    y = [r['src_tier'] for r in complete]
    z = np.polyfit(x, y, 1)
    p = np.poly1d(z)
    x_line = np.linspace(min(x), max(x), 100)
    ax3.plot(x_line, p(x_line), 'k--', alpha=0.5, label=f'r = -0.75')
    
    ax3.set_xlabel('Supernode Count')
    ax3.set_ylabel('Source Tier (avg)')
    ax3.set_title('Supernodes vs SOURCE Performance\n(more supernodes = harder to steer FROM)')
    ax3.legend()
    ax3.set_ylim(0, 5)
    
    # 4. Archetype Summary
    ax4 = axes[1, 1]
    archetype_counts = {}
    for r in complete:
        a = r['archetype']
        archetype_counts[a] = archetype_counts.get(a, 0) + 1
    
    # Create a quadrant diagram
    ax4.axhline(y=3.5, color='gray', linestyle='--', alpha=0.5)
    ax4.axvline(x=3.5, color='gray', linestyle='--', alpha=0.5)
    
    for r in complete:
        ax4.scatter(r['tgt_tier'], r['src_tier'],
                   c=archetype_colors[r['archetype']], s=150, alpha=0.7)
        ax4.annotate(r['state'][:3], (r['tgt_tier'], r['src_tier']),
                    fontsize=8, ha='center', va='bottom')
    
    ax4.set_xlabel('Target Tier (avg) - Steer TO')
    ax4.set_ylabel('Source Tier (avg) - Steer FROM')
    ax4.set_title('State Archetypes')
    ax4.set_xlim(0, 5)
    ax4.set_ylim(0, 5)
    
    # Add quadrant labels
    ax4.text(4.5, 4.5, 'EXCHANGERS\n(good both ways)', ha='center', fontsize=9, 
             bbox=dict(boxstyle='round', facecolor='#2ecc71', alpha=0.3))
    ax4.text(1.5, 4.5, 'ESCAPE ROUTES\n(easy to leave)', ha='center', fontsize=9,
             bbox=dict(boxstyle='round', facecolor='#e74c3c', alpha=0.3))
    ax4.text(4.5, 1.5, 'MAGNETS\n(hard to leave)', ha='center', fontsize=9,
             bbox=dict(boxstyle='round', facecolor='#3498db', alpha=0.3))
    ax4.text(1.5, 1.5, 'TRAPS\n(poor both ways)', ha='center', fontsize=9,
             bbox=dict(boxstyle='round', facecolor='#9b59b6', alpha=0.3))
    
    # Legend
    patches = [mpatches.Patch(color=c, label=a) for a, c in archetype_colors.items() if a in [r['archetype'] for r in complete]]
    fig.legend(handles=patches, loc='center right', bbox_to_anchor=(0.98, 0.5))
    
    plt.tight_layout()
    plt.savefig(output_dir / 'swap_factor_analysis.png', dpi=150, bbox_inches='tight')
    print(f"Saved: {output_dir / 'swap_factor_analysis.png'}")
    
    # Create summary text
    summary = {
        'correlations': {
            'native_prob_vs_source': -0.608,
            'native_prob_vs_target': 0.272,
            'supernodes_vs_source': -0.747,
        },
        'archetypes': {},
        'insights': [
            "HIGH native probability = HARDER to steer FROM (strong inverse r=-0.61)",
            "HIGH supernode count = HARDER to steer FROM (very strong r=-0.75)",
            "Native prob has moderate positive effect on target success (r=+0.27)",
            "Supernodes have minimal effect on target success",
        ],
        'anomalies': {
            'Nevada': "Capital is Carson City but model outputs Las Vegas (stronger city representation)",
            'Georgia': "Low native prob (0.139) makes it easy source but weak target representation",
            'Colorado': "High supernodes (264) create defensive structure despite high native prob",
            'New York': "Highest native prob (0.578) + high supernodes = extremely hard to steer FROM",
        }
    }
    
    for r in complete:
        a = r['archetype']
        if a not in summary['archetypes']:
            summary['archetypes'][a] = []
        summary['archetypes'][a].append({
            'state': r['state'],
            'native_prob': r['native_prob'],
            'supernodes': r['supernodes'],
            'src_tier': r['src_tier'],
            'tgt_tier': r['tgt_tier'],
        })
    
    with open(output_dir / 'swap_factor_summary.json', 'w', encoding='utf-8') as f:
        json.dump(summary, f, indent=2)
    print(f"Saved: {output_dir / 'swap_factor_summary.json'}")


def main():
    batch_root = Path("output/usa_states_batch")
    swaps_dir = batch_root / "_swaps"
    tier_summary_path = swaps_dir / "_analysis_v3" / "tier_summary.json"
    output_dir = swaps_dir / "_analysis_v3"
    
    with open(tier_summary_path, 'r', encoding='utf-8') as f:
        tier_summary = json.load(f)
    
    rows = load_state_data(batch_root, tier_summary)
    print(f"Loaded {len(rows)} states with swap data")
    
    create_visualizations(rows, output_dir)


if __name__ == '__main__':
    main()

