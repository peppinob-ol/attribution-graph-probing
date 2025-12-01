import pandas as pd

# Load California grouping
ca = pd.read_csv('C:/Github/circuit_tracer-prompt_rover/output/usa_states_batch/california_Oakland/02 Node Grouping/node_grouping.csv')

# Pilot's California amplify features (from the working pilot)
pilot_ca_feats = [
    (0, 32742, 2.42),   # present in pilot
    (0, 76137, 2.27),   # present in pilot  
    (5, 21198, 3.16),   # MISSING from batch
    (6, 67459, 1.54),   # present in pilot
    (8, 37691, 17.0),   # MISSING from batch (highest activation!)
    (9, 59799, 0.59),   # present in pilot
    (10, 75793, 12.88), # MISSING from batch
    (12, 1425, 6.72),   # MISSING from batch
    (12, 87969, 2.11),  # present in pilot
    (13, 16947, 1.33),  # MISSING from batch
    (16, 29578, 0.81),  # present in pilot
]

print('=== CHECKING PILOT CALIFORNIA FEATURES IN CURRENT GROUPING ===\n')
for layer, feat, pilot_act in pilot_ca_feats:
    match = ca[(ca['layer']==layer) & (ca['feature']==feat)]
    if len(match) > 0:
        sn = match['supernode_name'].iloc[0]
        act = match['activation_max'].iloc[0]
        in_ca = 'YES' if sn == 'California' else 'NO'
        print(f'{layer:2d}_{feat:5d}: supernode="{sn:20s}" California={in_ca}, act={act:.2f} (pilot: {pilot_act})')
    else:
        print(f'{layer:2d}_{feat:5d}: *** NOT IN node_grouping.csv *** (pilot had act={pilot_act})')

# Check what supernodes have California in the name
print('\n=== ALL SUPERNODES CONTAINING "CALIFORNIA" OR "SACRA" ===')
ca_related = ca[ca['supernode_name'].str.contains('California|Sacramento|Sacra', case=False, na=False)]
print(f"Matching rows: {len(ca_related)}")
print(ca_related[['supernode_name']].drop_duplicates())

# Show all unique supernodes
print('\n=== TOP 10 SUPERNODES BY FEATURE COUNT ===')
sn_counts = ca.groupby('feature_key')['supernode_name'].first().value_counts()
print(sn_counts.head(10))

# Check if missing features are in original graph
import json
print('\n=== CHECKING MISSING FEATURES IN ORIGINAL GRAPH ===')
with open('C:/Github/circuit_tracer-prompt_rover/output/usa_states_batch/california_Oakland/00 Graph Generation/graph.json') as f:
    graph = json.load(f)

# Build lookup from graph nodes
graph_nodes = {}
for n in graph['nodes']:
    if n.get('feature_type') == 'cross layer transcoder':
        node_id = n.get('node_id') or n.get('nodeId')
        if node_id and '_' in str(node_id):
            parts = str(node_id).split('_')
            if parts[0].isdigit():
                layer = int(parts[0])
                feat = int(parts[1])
                graph_nodes[(layer, feat)] = n.get('influence', 'N/A')

missing = [(5,21198), (8,37691), (12,1425), (13,16947)]
for layer, feat in missing:
    if (layer, feat) in graph_nodes:
        print(f'{layer}_{feat}: IN GRAPH, influence={graph_nodes[(layer, feat)]:.4f}')
    else:
        print(f'{layer}_{feat}: NOT IN GRAPH')

# Check the CSV metrics file for these features
print('\n=== CHECKING METRICS CSV FOR MISSING FEATURES ===')
try:
    metrics = pd.read_csv('C:/Github/circuit_tracer-prompt_rover/output/usa_states_batch/california_Oakland/00 Graph Generation/graph_feature_static_metrics.csv')
    for layer, feat in missing:
        match = metrics[(metrics['layer']==layer) & (metrics['feature']==feat)]
        if len(match) > 0:
            ci = match['cumulative_influence'].iloc[0]
            print(f'{layer}_{feat}: cumulative_influence={ci:.4f} (threshold is 0.70)')
        else:
            print(f'{layer}_{feat}: NOT IN METRICS CSV')
except Exception as e:
    print(f'Error reading metrics: {e}')

