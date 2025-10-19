#!/usr/bin/env python3
"""Verifica coverage dettagliata dei cicciotti"""
import json
import pandas as pd

# Carica dati
cicc = json.load(open('output/cicciotti_supernodes.json','r'))
metrics = pd.read_csv('output/graph_feature_static_metrics (1).csv')
metrics['fkey'] = metrics['layer'].astype(str) + '_' + metrics['feature'].astype(str)
pers = json.load(open('output/feature_personalities_corrected.json','r'))

total_influence = metrics['logit_influence'].sum()

# Feature nei cicciotti
cicc_features = set()
for c in cicc.values():
    cicc_features.update(c['members'])

print(f"Feature nei cicciotti: {len(cicc_features)}")

# Calcola influence
cicc_df = metrics[metrics['fkey'].isin(cicc_features)]
cicc_influence = cicc_df['logit_influence'].sum()
coverage = (cicc_influence / total_influence) * 100

print(f"\n=== COVERAGE CICCIOTTI ===")
print(f"Logit influence totale: {total_influence:.2f}")
print(f"Logit influence cicciotti: {cicc_influence:.2f}")
print(f"Coverage: {coverage:.1f}%")

# Analizza top-20 feature per nuova_max
print(f"\n=== TOP-20 FEATURE PER NUOVA_MAX ===")
items = [(k, v.get('nuova_max_label_span', 0)) for k, v in pers.items()]
items.sort(key=lambda x: x[1], reverse=True)

top20_features = [k for k, v in items[:20]]
top20_df = metrics[metrics['fkey'].isin(top20_features)]
top20_influence = top20_df['logit_influence'].sum()
top20_coverage = (top20_influence / total_influence) * 100

print(f"Top-20 feature per probe:")
for i, (k, nuova) in enumerate(items[:20], 1):
    m = metrics[metrics['fkey'] == k]
    logit = m['logit_influence'].iloc[0] if len(m) > 0 else 0
    in_cicc = k in cicc_features
    print(f"{i:2d}. {k:12s}: nuova={nuova:6.1f}, logit={logit:.4f} {'<- IN CICC' if in_cicc else ''}")

print(f"\nTop-20 influence totale: {top20_influence:.2f} ({top20_coverage:.1f}%)")
print(f"Top-20 dentro cicciotti: {sum(1 for k in top20_features if k in cicc_features)}/20")

# Verifica se problem è in crescita
print(f"\n=== ANALISI MEMBRI CICCIOTTI ===")
for cid, c in list(cicc.items())[:5]:
    members = c['members']
    seed = c['seed']
    
    # Influence dei membri
    members_df = metrics[metrics['fkey'].isin(members)]
    members_influence = members_df['logit_influence'].sum()
    
    seed_m = metrics[metrics['fkey'] == seed]
    seed_inf = seed_m['logit_influence'].iloc[0] if len(seed_m) > 0 else 0
    seed_nuova = pers.get(seed, {}).get('nuova_max_label_span', 0)
    
    print(f"\n{cid}: {len(members)} membri")
    print(f"  Seed {seed}: nuova={seed_nuova:.1f}, logit={seed_inf:.4f}")
    print(f"  Influence totale: {members_influence:.4f}")
    print(f"  Influence media/membro: {members_influence/len(members):.4f}")






