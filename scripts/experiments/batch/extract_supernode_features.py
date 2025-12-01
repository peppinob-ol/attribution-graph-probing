"""Extract feature counts from state supernodes."""
import csv
from pathlib import Path
from collections import Counter

states_config = {
    'michigan_Detroit': {'state': 'Michigan', 'capital': 'Lansing', 'city': 'Detroit'},
    'georgia_Savannah': {'state': 'Georgia', 'capital': 'Atlanta', 'city': 'Savannah'}, 
    'arizona_Tucson': {'state': 'Arizona', 'capital': 'Phoenix', 'city': 'Tucson'},
    'nevada_las_vegas': {'state': 'Nevada', 'capital': 'Carson', 'city': 'Vegas'},
    'california_Oakland': {'state': 'California', 'capital': 'Sacramento', 'city': 'Oakland'},
    'colorado_colorado_springs': {'state': 'Colorado', 'capital': 'Denver', 'city': 'Springs'},
    'ohio_Cleveland': {'state': 'Ohio', 'capital': 'Columbus', 'city': 'Cleveland'},
    'florida_Miami': {'state': 'Florida', 'capital': 'Tallahassee', 'city': 'Miami'},
    'oregon_Portland': {'state': 'Oregon', 'capital': 'Salem', 'city': 'Portland'},
    'texas_Dallas': {'state': 'Texas', 'capital': 'Austin', 'city': 'Dallas'},
    'new_york_new_york_city': {'state': 'York', 'capital': 'Albany', 'city': 'York'},
}

batch_root = Path('output/usa_states_batch')

print(f"{'State':<12} {'StateSN':<8} {'CapitalSN':<10} {'CitySN':<8} {'Total':<8} {'State%':<8} {'Capital%':<8}")
print("-" * 75)

results = []
for folder, cfg in states_config.items():
    csv_path = batch_root / folder / '02 Node Grouping' / 'node_grouping.csv'
    if not csv_path.exists():
        continue
    
    counts = Counter()
    total = 0
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            sn = row.get('supernode_name', '')
            counts[sn] += 1
            total += 1
    
    # Sum features containing the key terms
    state_sn = sum(c for n, c in counts.items() if cfg['state'] in n)
    capital_sn = sum(c for n, c in counts.items() if cfg['capital'] in n)
    city_sn = sum(c for n, c in counts.items() if cfg['city'] in n and cfg['capital'] not in n)
    
    state_pct = state_sn / total * 100 if total > 0 else 0
    capital_pct = capital_sn / total * 100 if total > 0 else 0
    
    display_state = cfg['state'] if cfg['state'] != 'York' else 'New York'
    results.append({
        'state': display_state,
        'state_sn': state_sn,
        'capital_sn': capital_sn,
        'city_sn': city_sn,
        'total': total,
        'state_pct': state_pct,
        'capital_pct': capital_pct,
    })
    
    print(f"{display_state:<12} {state_sn:<8} {capital_sn:<10} {city_sn:<8} {total:<8} {state_pct:<.1f}%     {capital_pct:<.1f}%")

print()
print("Key:")
print("  StateSN = features in state supernode(s)")
print("  CapitalSN = features in capital supernode(s)")  
print("  CitySN = features in prompt city supernode(s)")
print("  State% = StateSN / Total")
print("  Capital% = CapitalSN / Total")

# Now correlate with swap performance
import json
tier_summary_path = Path('output/usa_states_batch/_swaps/_analysis_v3/tier_summary.json')
with open(tier_summary_path, 'r', encoding='utf-8') as f:
    tier_summary = json.load(f)

by_target = tier_summary.get('by_target_state', {})
by_source = tier_summary.get('by_source_state', {})

print()
print("=" * 90)
print("CORRELATION WITH SWAP PERFORMANCE")
print("=" * 90)
print()
print(f"{'State':<12} {'StateSN':<8} {'CapSN':<8} {'CitySN':<8} {'SrcTier':<10} {'TgtTier':<10}")
print("-" * 65)

for r in results:
    state = r['state']
    src_tier = by_source.get(state, {}).get('avg_tier', None)
    tgt_tier = by_target.get(state, {}).get('avg_tier', None)
    
    src_str = f"{src_tier:.2f}" if src_tier else "N/A"
    tgt_str = f"{tgt_tier:.2f}" if tgt_tier else "N/A"
    
    print(f"{state:<12} {r['state_sn']:<8} {r['capital_sn']:<8} {r['city_sn']:<8} {src_str:<10} {tgt_str:<10}")

# Compute correlations
def pearson(x, y):
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

# Filter to states with swap data
swap_results = [r for r in results if by_source.get(r['state'])]
for r in swap_results:
    r['src_tier'] = by_source.get(r['state'], {}).get('avg_tier', 0)
    r['tgt_tier'] = by_target.get(r['state'], {}).get('avg_tier', 0)

if swap_results:
    state_sn = [r['state_sn'] for r in swap_results]
    capital_sn = [r['capital_sn'] for r in swap_results]
    city_sn = [r['city_sn'] for r in swap_results]
    total = [r['total'] for r in swap_results]
    src_tiers = [r['src_tier'] for r in swap_results]
    tgt_tiers = [r['tgt_tier'] for r in swap_results]
    
    print()
    print("CORRELATIONS (Pearson r):")
    print("-" * 50)
    print(f"  State features vs Source tier:   r = {pearson(state_sn, src_tiers):+.3f}")
    print(f"  State features vs Target tier:   r = {pearson(state_sn, tgt_tiers):+.3f}")
    print(f"  Capital features vs Source tier: r = {pearson(capital_sn, src_tiers):+.3f}")
    print(f"  Capital features vs Target tier: r = {pearson(capital_sn, tgt_tiers):+.3f}")
    print(f"  City features vs Source tier:    r = {pearson(city_sn, src_tiers):+.3f}")
    print(f"  Total features vs Source tier:   r = {pearson(total, src_tiers):+.3f}")
    
    print()
    print("INSIGHTS:")
    print("-" * 50)
    
    r_state_src = pearson(state_sn, src_tiers)
    r_cap_tgt = pearson(capital_sn, tgt_tiers)
    
    if r_state_src < -0.3:
        print("  - More STATE features -> HARDER to steer FROM")
    if r_cap_tgt > 0.3:
        print("  - More CAPITAL features -> EASIER to steer TO")
    
    # Special cases
    print()
    print("NOTABLE STATES:")
    for r in sorted(swap_results, key=lambda x: x['state_sn'], reverse=True)[:3]:
        print(f"  {r['state']}: {r['state_sn']} state features, src_tier={r['src_tier']:.2f}")

