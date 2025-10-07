#!/usr/bin/env python3
"""
Analisi dettagliata delle feature escluse con alta logit influence
"""

import json
import pandas as pd

def analyze_high_influence_excluded():
    print("=" * 60)
    print("ANALISI FEATURE ESCLUSE CON ALTA LOGIT INFLUENCE")
    print("=" * 60)
    
    # Carica dati
    metrics_df = pd.read_csv("output/graph_feature_static_metrics (1).csv")
    metrics_df['feature_key'] = metrics_df['layer'].astype(str) + '_' + metrics_df['feature'].astype(str)
    
    with open("output/final_anthropological_optimized.json", 'r', encoding='utf-8') as f:
        results = json.load(f)
    
    with open("output/feature_personalities_corrected.json", 'r', encoding='utf-8') as f:
        personalities = json.load(f)
    
    # Estrai feature nei supernodi
    supernode_features = set()
    for supernode in results['semantic_supernodes'].values():
        supernode_features.update(supernode['members'])
    for supernode in results['computational_supernodes'].values():
        supernode_features.update(supernode['members'])
    
    # Feature escluse
    excluded_features = set(metrics_df['feature_key']) - supernode_features
    excluded_df = metrics_df[metrics_df['feature_key'].isin(excluded_features)]
    
    # Top 20 feature escluse per logit influence
    print("\nTOP 20 FEATURE ESCLUSE (per logit influence):")
    print("-" * 60)
    top_excluded = excluded_df.nlargest(20, 'logit_influence')
    
    for idx, row in top_excluded.iterrows():
        fkey = f"{int(row['layer'])}_{int(row['feature'])}"
        personality = personalities.get(fkey, {})
        
        layer = personality.get('layer', '?')
        token = personality.get('most_common_peak', '?')
        consistency = personality.get('consistency_score', 0)
        archetype = personality.get('archetype', '?')
        
        print(f"\n{fkey}:")
        print(f"  Logit Influence: {row['logit_influence']:.4f}")
        print(f"  Layer: {layer}, Token: '{token}', Consistency: {consistency:.3f}")
        print(f"  Archetype: {archetype}")
        print(f"  Frac External: {row['frac_external_raw']:.3f}")
    
    # Analisi per layer delle feature escluse con alta influence
    print("\n" + "=" * 60)
    print("DISTRIBUZIONE PER LAYER (feature escluse con influence > 5):")
    print("-" * 60)
    
    high_influence = excluded_df[excluded_df['logit_influence'] > 5.0]
    layer_distribution = {}
    
    for idx, row in high_influence.iterrows():
        fkey = f"{int(row['layer'])}_{int(row['feature'])}"
        if fkey in personalities:
            layer = personalities[fkey]['layer']
            if layer not in layer_distribution:
                layer_distribution[layer] = {'count': 0, 'total_influence': 0}
            layer_distribution[layer]['count'] += 1
            layer_distribution[layer]['total_influence'] += row['logit_influence']
    
    for layer in sorted(layer_distribution.keys()):
        info = layer_distribution[layer]
        print(f"  Layer {layer}: {info['count']} features, influence totale: {info['total_influence']:.2f}")
    
    # Analisi per token type
    print("\n" + "=" * 60)
    print("DISTRIBUZIONE PER TOKEN TYPE (feature escluse con influence > 5):")
    print("-" * 60)
    
    token_distribution = {}
    for idx, row in high_influence.iterrows():
        fkey = f"{int(row['layer'])}_{int(row['feature'])}"
        if fkey in personalities:
            token = personalities[fkey]['most_common_peak']
            if token not in token_distribution:
                token_distribution[token] = {'count': 0, 'total_influence': 0}
            token_distribution[token]['count'] += 1
            token_distribution[token]['total_influence'] += row['logit_influence']
    
    for token in sorted(token_distribution.items(), key=lambda x: x[1]['total_influence'], reverse=True)[:15]:
        token_name, info = token
        print(f"  '{token_name}': {info['count']} features, influence totale: {info['total_influence']:.2f}")
    
    # Analisi consistency vs influence
    print("\n" + "=" * 60)
    print("CONSISTENCY vs LOGIT INFLUENCE (feature escluse):")
    print("-" * 60)
    
    consistency_bins = {
        '0.0 (excluded as non-informative)': [],
        '0.0-0.2': [],
        '0.2-0.5': [],
        '0.5-0.8': [],
        '0.8-1.0': []
    }
    
    for idx, row in excluded_df.iterrows():
        fkey = f"{int(row['layer'])}_{int(row['feature'])}"
        if fkey in personalities:
            cons = personalities[fkey]['consistency_score']
            influence = row['logit_influence']
            
            if cons == 0:
                consistency_bins['0.0 (excluded as non-informative)'].append(influence)
            elif cons < 0.2:
                consistency_bins['0.0-0.2'].append(influence)
            elif cons < 0.5:
                consistency_bins['0.2-0.5'].append(influence)
            elif cons < 0.8:
                consistency_bins['0.5-0.8'].append(influence)
            else:
                consistency_bins['0.8-1.0'].append(influence)
    
    for bin_name, influences in consistency_bins.items():
        if influences:
            total = sum(influences)
            avg = total / len(influences)
            print(f"  {bin_name}: {len(influences)} features, avg influence: {avg:.4f}, total: {total:.2f}")
    
    print("\n" + "=" * 60)

if __name__ == "__main__":
    analyze_high_influence_excluded()

