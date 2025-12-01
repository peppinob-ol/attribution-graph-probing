"""
Exploratory analysis of swap performance factors.

Correlates swap success with:
- Supernode counts
- Feature counts
- Native logit probabilities
- Graph structure metrics
"""
from __future__ import annotations

import json
from pathlib import Path
from collections import defaultdict
import sys

def load_summary(summary_path: Path) -> dict:
    """Load the batch summary JSON."""
    with open(summary_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def load_swap_results(swaps_dir: Path) -> list:
    """Load all swap results."""
    results = []
    by_source = swaps_dir / "by_source"
    if not by_source.exists():
        return results
    
    for source_dir in by_source.iterdir():
        if not source_dir.is_dir():
            continue
        for f in source_dir.glob("to_*.json"):
            try:
                with open(f, 'r', encoding='utf-8') as fp:
                    results.append(json.load(fp))
            except:
                pass
    return results

def extract_state_metrics(batch_root: Path, summary: dict) -> dict:
    """Extract metrics per state from batch data."""
    state_data = {}
    
    for seed in summary.get('seeds', []):
        slug = seed['slug']
        np_data = seed.get('neuronpedia', {})
        
        # Extract state name from slug (e.g., "michigan_detroit" -> "Michigan")
        state_part = slug.split('_')[0]
        state = state_part.title()
        
        # Handle two-word states
        if state in ['New', 'North', 'South', 'West', 'Rhode']:
            parts = slug.split('_')
            if len(parts) >= 2:
                state = f"{parts[0]}_{parts[1]}".replace('_', ' ').title()
        
        state_data[slug] = {
            'state': state,
            'slug': slug,
            'supernodes': np_data.get('supernodes', 0),
            'pinned_nodes': np_data.get('pinned_nodes', 0),
        }
        
        # Try to load native logit from swap results
        state_dir = batch_root / slug
        if not state_dir.exists():
            # Try case variations
            for d in batch_root.iterdir():
                if d.is_dir() and d.name.lower() == slug.lower():
                    state_dir = d
                    break
        
        # Load graph.json to get native logit probability
        graph_file = state_dir / "00 Graph Generation" / "graph.json"
        if graph_file.exists():
            try:
                with open(graph_file, 'r', encoding='utf-8') as f:
                    graph = json.load(f)
                    # Find the target logit node
                    for node in graph.get('nodes', []):
                        if node.get('is_target_logit'):
                            state_data[slug]['native_prob'] = node.get('token_prob', 0)
                            # Find the token from node_id like "L_83496_8"
                            node_id = node.get('node_id', '')
                            state_data[slug]['target_logit_node'] = node_id
                            break
                    
                    # Also extract prompt for analysis
                    prompt = graph.get('metadata', {}).get('prompt', '')
                    state_data[slug]['prompt'] = prompt
            except Exception as e:
                pass
    
    return state_data

def main():
    batch_root = Path("output/usa_states_batch")
    swaps_dir = batch_root / "_swaps"
    tier_summary_path = swaps_dir / "_analysis_v3" / "tier_summary.json"
    
    # Find latest summary
    summaries = sorted(batch_root.glob("_summary_*.json"), reverse=True)
    if not summaries:
        print("No summary found")
        return
    
    summary_path = summaries[0]
    print(f"Loading summary: {summary_path.name}")
    
    summary = load_summary(summary_path)
    state_data = extract_state_metrics(batch_root, summary)
    
    # Load tier summary
    with open(tier_summary_path, 'r', encoding='utf-8') as f:
        tier_summary = json.load(f)
    
    by_target = tier_summary.get('by_target_state', {})
    by_source = tier_summary.get('by_source_state', {})
    
    # Build comparison table
    print("\n" + "=" * 100)
    print("STATE PERFORMANCE ANALYSIS")
    print("=" * 100)
    
    print("\n{:<15} {:>10} {:>12} {:>12} {:>12} {:>12}".format(
        "State", "Supernodes", "Pinned", "NativeProb",
        "Src Tier", "Tgt Tier"
    ))
    print("-" * 90)
    
    rows = []
    for slug, data in sorted(state_data.items()):
        state = data['state']
        
        # Get source and target performance
        src_tier = by_source.get(state, {}).get('avg_tier', None)
        tgt_tier = by_target.get(state, {}).get('avg_tier', None)
        tgt_perfect = by_target.get(state, {}).get('perfect_rate', None)
        
        rows.append({
            'state': state,
            'slug': slug,
            'supernodes': data.get('supernodes', 0),
            'pinned': data.get('pinned_nodes', 0),
            'native_prob': data.get('native_prob', 0),
            'src_tier': src_tier,
            'tgt_tier': tgt_tier,
            'tgt_perfect': tgt_perfect,
        })
        
        src_str = f"{src_tier:.2f}" if src_tier else "N/A"
        tgt_str = f"{tgt_tier:.2f}" if tgt_tier else "N/A"
        
        print("{:<15} {:>10} {:>12} {:>12.3f} {:>12} {:>12}".format(
            state[:15],
            data.get('supernodes', 0),
            data.get('pinned_nodes', 0),
            data.get('native_prob', 0),
            src_str,
            tgt_str
        ))
    
    # Summary insights
    print("\n" + "=" * 100)
    print("KEY PATTERNS")
    print("=" * 100)
    
    # States with swap data
    swap_states = [r for r in rows if r['src_tier'] is not None]
    
    if swap_states:
        # Best targets
        by_tgt = sorted(swap_states, key=lambda x: x['tgt_tier'] or 0, reverse=True)
        print("\nBEST TARGET STATES (easiest to steer TO):")
        for r in by_tgt[:5]:
            if r['tgt_tier']:
                print(f"  {r['state']}: avg_tier={r['tgt_tier']:.2f}, supernodes={r['supernodes']}, native_prob={r['native_prob']:.3f}")
        
        # Worst targets
        print("\nWORST TARGET STATES:")
        for r in by_tgt[-5:]:
            if r['tgt_tier']:
                print(f"  {r['state']}: avg_tier={r['tgt_tier']:.2f}, supernodes={r['supernodes']}, native_prob={r['native_prob']:.3f}")
        
        # Best sources
        by_src = sorted(swap_states, key=lambda x: x['src_tier'] or 0, reverse=True)
        print("\nBEST SOURCE STATES (easiest to steer FROM):")
        for r in by_src[:5]:
            if r['src_tier']:
                print(f"  {r['state']}: avg_tier={r['src_tier']:.2f}, supernodes={r['supernodes']}, native_prob={r['native_prob']:.3f}")
        
        # Worst sources
        print("\nWORST SOURCE STATES (hardest to steer FROM):")
        for r in by_src[-5:]:
            if r['src_tier']:
                print(f"  {r['state']}: avg_tier={r['src_tier']:.2f}, supernodes={r['supernodes']}, native_prob={r['native_prob']:.3f}")
        
        # Asymmetric states
        print("\nASYMMETRIC STATES (good target, bad source OR vice versa):")
        for r in swap_states:
            if r['src_tier'] and r['tgt_tier']:
                diff = r['tgt_tier'] - r['src_tier']
                if abs(diff) > 1.0:
                    direction = "better TARGET than source" if diff > 0 else "better SOURCE than target"
                    print(f"  {r['state']}: tgt={r['tgt_tier']:.2f}, src={r['src_tier']:.2f} ({direction})")
        
        # Correlation analysis
        print("\n" + "=" * 100)
        print("CORRELATION HINTS")
        print("=" * 100)
        
        # High supernode count states
        by_sn = sorted(swap_states, key=lambda x: x['supernodes'], reverse=True)
        print("\nHIGH SUPERNODE COUNT (>230):")
        for r in by_sn:
            if r['supernodes'] > 230:
                if r['src_tier'] and r['tgt_tier']:
                    print(f"  {r['state']}: {r['supernodes']} supernodes, native_prob={r['native_prob']:.3f}, src={r['src_tier']:.2f}, tgt={r['tgt_tier']:.2f}")
                else:
                    print(f"  {r['state']}: {r['supernodes']} supernodes, native_prob={r['native_prob']:.3f}")
        
        # Low native probability capitals
        by_prob = sorted(swap_states, key=lambda x: x['native_prob'])
        print("\nLOW NATIVE CAPITAL PROBABILITY (<0.30):")
        for r in by_prob:
            if r['native_prob'] < 0.30 and r['native_prob'] > 0:
                if r['src_tier']:
                    print(f"  {r['state']}: native_prob={r['native_prob']:.3f}, supernodes={r['supernodes']}, src={r['src_tier']:.2f}, tgt={r['tgt_tier']:.2f}")
                else:
                    print(f"  {r['state']}: native_prob={r['native_prob']:.3f}, supernodes={r['supernodes']}")
        
        # High native probability capitals
        by_prob_high = sorted(swap_states, key=lambda x: x['native_prob'], reverse=True)
        print("\nHIGH NATIVE CAPITAL PROBABILITY (>0.50):")
        for r in by_prob_high:
            if r['native_prob'] > 0.50:
                if r['src_tier']:
                    print(f"  {r['state']}: native_prob={r['native_prob']:.3f}, supernodes={r['supernodes']}, src={r['src_tier']:.2f}, tgt={r['tgt_tier']:.2f}")
                else:
                    print(f"  {r['state']}: native_prob={r['native_prob']:.3f}, supernodes={r['supernodes']}")

def compute_correlations(rows: list):
    """Compute Pearson correlations between metrics."""
    import statistics
    
    # Filter to states with swap data
    swap_rows = [r for r in rows if r.get('src_tier') is not None and r.get('native_prob', 0) > 0]
    
    if len(swap_rows) < 3:
        print("Not enough data for correlation analysis")
        return
    
    print("\n" + "=" * 100)
    print("CORRELATION ANALYSIS")
    print("=" * 100)
    
    # Extract arrays
    native_probs = [r['native_prob'] for r in swap_rows]
    supernodes = [r['supernodes'] for r in swap_rows]
    src_tiers = [r['src_tier'] for r in swap_rows]
    tgt_tiers = [r['tgt_tier'] for r in swap_rows if r.get('tgt_tier') is not None]
    
    def pearson(x, y):
        """Simple Pearson correlation."""
        n = min(len(x), len(y))
        if n < 2:
            return 0
        x, y = x[:n], y[:n]
        mean_x, mean_y = sum(x)/n, sum(y)/n
        std_x = (sum((xi - mean_x)**2 for xi in x) / n) ** 0.5
        std_y = (sum((yi - mean_y)**2 for yi in y) / n) ** 0.5
        if std_x == 0 or std_y == 0:
            return 0
        cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(n)) / n
        return cov / (std_x * std_y)
    
    print("\nCORRELATIONS (Pearson r):")
    print("-" * 60)
    
    # Native prob vs source tier
    r_prob_src = pearson(native_probs, src_tiers)
    print(f"  Native prob vs Source tier:  r = {r_prob_src:+.3f}")
    if r_prob_src < -0.3:
        print("    -> HIGH native prob = HARDER to steer FROM (strong inverse)")
    elif r_prob_src > 0.3:
        print("    -> HIGH native prob = EASIER to steer FROM")
    
    # Native prob vs target tier  
    tgt_probs = [r['native_prob'] for r in swap_rows if r.get('tgt_tier') is not None]
    r_prob_tgt = pearson(tgt_probs, tgt_tiers)
    print(f"  Native prob vs Target tier:  r = {r_prob_tgt:+.3f}")
    if r_prob_tgt > 0.3:
        print("    -> HIGH native prob = EASIER to steer TO (strong positive)")
    elif r_prob_tgt < -0.3:
        print("    -> HIGH native prob = HARDER to steer TO")
    
    # Supernodes vs source tier
    r_sn_src = pearson(supernodes, src_tiers)
    print(f"  Supernodes vs Source tier:   r = {r_sn_src:+.3f}")
    if r_sn_src < -0.3:
        print("    -> HIGH supernodes = HARDER to steer FROM")
    
    # Supernodes vs target tier
    tgt_sn = [r['supernodes'] for r in swap_rows if r.get('tgt_tier') is not None]
    r_sn_tgt = pearson(tgt_sn, tgt_tiers)
    print(f"  Supernodes vs Target tier:   r = {r_sn_tgt:+.3f}")
    
    # Native prob vs supernodes
    r_prob_sn = pearson(native_probs, supernodes)
    print(f"  Native prob vs Supernodes:   r = {r_prob_sn:+.3f}")
    
    # Summary
    print("\n" + "=" * 100)
    print("KEY INSIGHTS")
    print("=" * 100)
    
    print("""
HYPOTHESIS: Native Logit Probability as a Predictor

1. SOURCE PERFORMANCE (ability to steer AWAY from a state):
   - States with LOW native probability are easier to escape from
   - The model already has uncertainty about the capital -> easier to suppress
   
2. TARGET PERFORMANCE (ability to steer TO a state):  
   - States with HIGH native probability are easier to land on
   - The target capital has strong representation -> easier to amplify
   
3. ASYMMETRY EXPLANATION:
   - Georgia (native=0.139): Easy to leave (low native prob), hard to reach (weak target representation)
   - Michigan (native=0.527): Hard to leave (high native prob), easy to reach (strong target representation)
   - Colorado issue: HIGH supernodes (264) may create "defensive" structure despite high native prob
   
4. SUPERNODE EFFECT:
   - High supernode count may indicate complex feature interactions
   - More supernodes = more "defensive" mechanisms to suppress during steering
""")


def analyze_pair_patterns(results_path: Path):
    """Analyze specific pair patterns from detailed results."""
    import csv
    
    detailed = results_path / "_analysis_v3" / "detailed_results.csv"
    if not detailed.exists():
        return
    
    print("\n" + "=" * 100)
    print("PAIR PATTERN ANALYSIS")
    print("=" * 100)
    
    # Load detailed results
    with open(detailed, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        rows = list(reader)
    
    # Analyze Georgia as target - always fails
    georgia_targets = [r for r in rows if r['to_state'] == 'Georgia']
    print(f"\nGEORGIA AS TARGET ({len(georgia_targets)} swaps):")
    for r in georgia_targets:
        tier = int(r['tier'])
        print(f"  {r['from_state']:12} -> Georgia: tier={tier} ({r['tier_name']})")
        if 'notes' in r and r['notes']:
            print(f"               {r['notes'][:60]}...")
    
    # Analyze Oregon as target - always fails
    oregon_targets = [r for r in rows if r['to_state'] == 'Oregon']
    print(f"\nOREGON AS TARGET ({len(oregon_targets)} swaps):")
    for r in oregon_targets:
        tier = int(r['tier'])
        print(f"  {r['from_state']:12} -> Oregon:  tier={tier} ({r['tier_name']})")
    
    # Analyze Nevada as target - never perfect
    nevada_targets = [r for r in rows if r['to_state'] == 'Nevada']
    print(f"\nNEVADA AS TARGET ({len(nevada_targets)} swaps) - never PERFECT:")
    for r in nevada_targets:
        tier = int(r['tier'])
        print(f"  {r['from_state']:12} -> Nevada:  tier={tier} ({r['tier_name']})")
        # Nevada's capital is Carson City but model often outputs Las Vegas
        if 'Las Vegas' in r.get('steered_output', ''):
            print(f"               Output has 'Las Vegas' (wrong city, right state)")


if __name__ == '__main__':
    main()
    
    # Additional analyses
    batch_root = Path("output/usa_states_batch")
    swaps_dir = batch_root / "_swaps"
    tier_summary_path = swaps_dir / "_analysis_v3" / "tier_summary.json"
    
    # Load summary and build rows for correlation
    summaries = sorted(batch_root.glob("_summary_*.json"), reverse=True)
    if summaries:
        summary = load_summary(summaries[0])
        state_data = extract_state_metrics(batch_root, summary)
        
        with open(tier_summary_path, 'r', encoding='utf-8') as f:
            tier_summary = json.load(f)
        
        by_target = tier_summary.get('by_target_state', {})
        by_source = tier_summary.get('by_source_state', {})
        
        rows = []
        for slug, data in state_data.items():
            state = data['state']
            rows.append({
                'state': state,
                'supernodes': data.get('supernodes', 0),
                'native_prob': data.get('native_prob', 0),
                'src_tier': by_source.get(state, {}).get('avg_tier'),
                'tgt_tier': by_target.get(state, {}).get('avg_tier'),
            })
        
        compute_correlations(rows)
        analyze_pair_patterns(swaps_dir)

