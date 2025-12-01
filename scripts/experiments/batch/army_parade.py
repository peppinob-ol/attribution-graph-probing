"""Show all 50 states ready for the full swap experiment."""
import json
from pathlib import Path

# Load summary
summary_path = Path('output/usa_states_batch/_summary_20251201_055938.json')
with open(summary_path, 'r', encoding='utf-8') as f:
    summary = json.load(f)

seeds = summary['seeds']
print("=" * 80)
print(f"USA STATES ARMY PARADE - {len(seeds)} STATES READY FOR 50x50 SWAP")
print("=" * 80)
print()

# Extract state info and native probabilities
states_info = []
batch_root = Path('output/usa_states_batch')

for seed in seeds:
    slug = seed['slug']
    np_data = seed.get('neuronpedia', {})
    
    # Get native probability from graph
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
    
    # Extract state name
    state_part = slug.split('_')[0]
    state = state_part.title()
    if state in ['New', 'North', 'South', 'West', 'Rhode']:
        parts = slug.split('_')
        if len(parts) >= 2:
            state = f"{parts[0]} {parts[1]}".title()
    
    states_info.append({
        'slug': slug,
        'state': state,
        'supernodes': np_data.get('supernodes', 0),
        'pinned': np_data.get('pinned_nodes', 0),
        'native_prob': native_prob,
        'url': np_data.get('url', ''),
    })

# Sort by state name
states_info.sort(key=lambda x: x['state'])

# Print table
print(f"{'#':>2}  {'State':<20} {'Slug':<30} {'SN':>4} {'Pin':>4} {'NatProb':>8}")
print("-" * 80)

low_prob = []
high_prob = []
high_sn = []

for i, s in enumerate(states_info, 1):
    prob_str = f"{s['native_prob']:.3f}" if s['native_prob'] > 0 else "N/A"
    flag = ""
    
    if s['native_prob'] < 0.20 and s['native_prob'] > 0:
        flag = " [LOW PROB]"
        low_prob.append(s)
    elif s['native_prob'] > 0.50:
        flag = " [HIGH PROB]"
        high_prob.append(s)
    
    if s['supernodes'] > 280:
        flag += " [HIGH SN]"
        high_sn.append(s)
    
    print(f"{i:2d}. {s['state']:<20} {s['slug']:<30} {s['supernodes']:>4} {s['pinned']:>4} {prob_str:>8}{flag}")

print()
print("=" * 80)
print("SUMMARY STATISTICS")
print("=" * 80)

probs = [s['native_prob'] for s in states_info if s['native_prob'] > 0]
sns = [s['supernodes'] for s in states_info]

print(f"Native probability: min={min(probs):.3f}, max={max(probs):.3f}, avg={sum(probs)/len(probs):.3f}")
print(f"Supernode count:    min={min(sns)}, max={max(sns)}, avg={sum(sns)/len(sns):.1f}")
print()

print("POTENTIAL ISSUES FOR 50x50:")
print("-" * 40)
print(f"Low native prob (<0.20): {len(low_prob)} states")
for s in low_prob:
    print(f"  - {s['state']}: {s['native_prob']:.3f}")

print(f"\nHigh native prob (>0.50): {len(high_prob)} states")
for s in high_prob:
    print(f"  - {s['state']}: {s['native_prob']:.3f}")

print(f"\nHigh supernode count (>280): {len(high_sn)} states")
for s in high_sn:
    print(f"  - {s['state']}: {s['supernodes']}")

# Check for token overlap issues
print()
print("PROMPT TOKEN OVERLAP (city contains state name):")
print("-" * 40)
overlap_states = [
    ('colorado_colorado_springs', 'Colorado', 'Colorado Springs'),
    ('new_york_new_york_city', 'New York', 'New York City'),
    ('virginia_virginia_beach', 'Virginia', 'Virginia Beach'),
    ('idaho_idaho_falls', 'Idaho', 'Idaho Falls'),
    ('missouri_kansas_city', 'Missouri', 'Kansas City'),  # Kansas overlap
    ('indiana_fort_wayne', 'Indiana', 'Fort Wayne'),  # Wayne/Indiana?
]

for slug, state, city in overlap_states:
    if any(s['slug'] == slug for s in states_info):
        print(f"  - {state}: prompt city '{city}' may have token overlap")

print()
print("=" * 80)
print(f"READY FOR 50x50 = {len(seeds) * len(seeds)} total swap pairs")
print(f"(minus {len(seeds)} identity pairs = {len(seeds) * (len(seeds)-1)} actual swaps)")
print("=" * 80)

