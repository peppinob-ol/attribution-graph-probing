#!/usr/bin/env python3
"""
Analizza feature ancora escluse con alta logit influence
per identificare opportunità di ulteriore ottimizzazione
"""

import json
import pandas as pd

def analyze_remaining_excluded():
    """Analizza perché top-influence feature sono ancora escluse"""
    
    print("=" * 60)
    print("ANALISI FEATURE ESCLUSE CON ALTA INFLUENCE")
    print("=" * 60)
    
    # 1. Carica dati
    with open("output/robust_thresholds.json", 'r', encoding='utf-8') as f:
        thresholds_data = json.load(f)
    
    with open("output/feature_personalities_corrected.json", 'r', encoding='utf-8') as f:
        personalities = json.load(f)
    
    with open("output/final_anthropological_optimized.json", 'r', encoding='utf-8') as f:
        final_data = json.load(f)
    
    metrics_df = pd.read_csv("output/graph_feature_static_metrics (1).csv")
    metrics_df['feature_key'] = metrics_df['layer'].astype(str) + '_' + metrics_df['feature'].astype(str)
    
    # Feature nei supernodi
    supernode_features = set()
    # Semantic supernodes
    for sn_name, sn_data in final_data.get('semantic_supernodes', {}).items():
        supernode_features.update(sn_data['members'])
    # Computational supernodes
    for sn_name, sn_data in final_data.get('computational_supernodes', {}).items():
        supernode_features.update(sn_data['members'])
    
    # Feature ammesse dal criterio
    admitted_features = set(thresholds_data['admitted_features']['total'])
    
    # Feature escluse = tutte le altre
    all_features = set(metrics_df['feature_key'])
    excluded_features = all_features - admitted_features
    
    print(f"\n📊 Breakdown:")
    print(f"   Totale feature: {len(all_features)}")
    print(f"   Ammesse dal criterio: {len(admitted_features)}")
    print(f"   Nei supernodi: {len(supernode_features)}")
    print(f"   Escluse: {len(excluded_features)}")
    
    # 2. Analizza top-50 escluse per logit influence
    excluded_df = metrics_df[metrics_df['feature_key'].isin(excluded_features)]
    top_excluded = excluded_df.nlargest(50, 'logit_influence')
    
    print(f"\n🔍 Top 50 feature ESCLUSE per logit influence:")
    print(f"   Total influence: {top_excluded['logit_influence'].sum():.2f}")
    print(f"   % of total: {top_excluded['logit_influence'].sum() / metrics_df['logit_influence'].sum() * 100:.1f}%")
    
    # Categorizza per motivo di esclusione
    categories = {
        'layer_25_boundary': [],
        'bos_below_p95': [],
        'low_affinity_low_influence': [],
        'missing_personality': [],
        'other': []
    }
    
    tau_inf = thresholds_data['thresholds']['tau_inf']
    tau_inf_vh = thresholds_data['thresholds']['tau_inf_very_high']
    tau_aff = thresholds_data['thresholds']['tau_aff']
    
    for _, row in top_excluded.iterrows():
        fkey = row['feature_key']
        layer = row['layer']
        influence = row['logit_influence']
        
        if fkey not in personalities:
            categories['missing_personality'].append((fkey, influence, layer, 'N/A', 'N/A'))
            continue
        
        p = personalities[fkey]
        token = p['most_common_peak']
        max_aff = p['max_affinity']
        mean_cons = p['mean_consistency']
        
        # Categorizza
        if layer == 25:
            categories['layer_25_boundary'].append((fkey, influence, layer, token, max_aff))
        elif token == '<BOS>' and influence < tau_inf_vh:
            categories['bos_below_p95'].append((fkey, influence, layer, token, max_aff))
        elif influence < tau_inf and max_aff < tau_aff:
            categories['low_affinity_low_influence'].append((fkey, influence, layer, token, max_aff))
        else:
            categories['other'].append((fkey, influence, layer, token, max_aff))
    
    # Report per categoria
    print(f"\n📋 Categorizzazione feature escluse (top 50):")
    
    for cat_name, features in categories.items():
        if not features:
            continue
        
        total_inf = sum(f[1] for f in features)
        print(f"\n   {cat_name.upper()}: {len(features)} feature")
        print(f"      Total influence: {total_inf:.2f}")
        print(f"      Top 3:")
        for i, (fkey, inf, layer, token, aff) in enumerate(features[:3]):
            print(f"         {i+1}. {fkey}: influence={inf:.4f}, layer={layer}, "
                  f"token='{token}', max_aff={aff if aff != 'N/A' else 'N/A'}")
    
    # 3. Simulazione: se abbassassimo soglie
    print(f"\n🧪 SIMULAZIONI OTTIMIZZAZIONE:")
    
    # Sim 1: Abbassa tau_aff a 0.55
    new_tau_aff = 0.55
    sim1_recovered = []
    for fkey in excluded_features:
        if fkey not in personalities:
            continue
        p = personalities[fkey]
        row = metrics_df[metrics_df['feature_key'] == fkey]
        if len(row) == 0:
            continue
        influence = row.iloc[0]['logit_influence']
        max_aff = p['max_affinity']
        token = p['most_common_peak']
        
        # Sarebbe ammesso con tau_aff=0.55?
        if max_aff >= new_tau_aff and max_aff < tau_aff:
            # BOS check
            if token == '<BOS>' and influence < tau_inf_vh:
                continue
            sim1_recovered.append((fkey, influence, max_aff, token))
    
    sim1_inf = sum(f[1] for f in sim1_recovered)
    print(f"\n   SIM 1: tau_aff 0.60 → 0.55")
    print(f"      Feature recuperate: {len(sim1_recovered)}")
    print(f"      Influence recuperata: {sim1_inf:.2f} ({sim1_inf / metrics_df['logit_influence'].sum() * 100:.1f}%)")
    print(f"      New total coverage: {(thresholds_data['coverage']['admitted_influence'] + sim1_inf) / metrics_df['logit_influence'].sum() * 100:.1f}%")
    
    # Sim 2: Includi layer 25 con influence > tau_inf
    sim2_recovered = []
    for fkey in excluded_features:
        row = metrics_df[metrics_df['feature_key'] == fkey]
        if len(row) == 0:
            continue
        layer = row.iloc[0]['layer']
        influence = row.iloc[0]['logit_influence']
        
        if layer == 25 and influence >= tau_inf:
            if fkey not in personalities:
                token = '?'
            else:
                token = personalities[fkey]['most_common_peak']
                # BOS check
                if token == '<BOS>' and influence < tau_inf_vh:
                    continue
            sim2_recovered.append((fkey, influence, layer, token))
    
    sim2_inf = sum(f[1] for f in sim2_recovered)
    print(f"\n   SIM 2: Includi layer 25 con influence >= tau_inf")
    print(f"      Feature recuperate: {len(sim2_recovered)}")
    print(f"      Influence recuperata: {sim2_inf:.2f} ({sim2_inf / metrics_df['logit_influence'].sum() * 100:.1f}%)")
    
    # Sim 3: Abbassa tau_inf_very_high (BOS) a p90
    tau_inf_p90 = thresholds_data['thresholds']['tau_inf_p90']
    sim3_recovered = []
    for fkey in excluded_features:
        if fkey not in personalities:
            continue
        p = personalities[fkey]
        token = p['most_common_peak']
        row = metrics_df[metrics_df['feature_key'] == fkey]
        if len(row) == 0:
            continue
        influence = row.iloc[0]['logit_influence']
        
        # BOS con influence tra p90 e p95
        if token == '<BOS>' and influence >= tau_inf_p90 and influence < tau_inf_vh:
            sim3_recovered.append((fkey, influence, token))
    
    sim3_inf = sum(f[1] for f in sim3_recovered)
    print(f"\n   SIM 3: BOS threshold p95 → p90")
    print(f"      Feature BOS recuperate: {len(sim3_recovered)}")
    print(f"      Influence recuperata: {sim3_inf:.2f} ({sim3_inf / metrics_df['logit_influence'].sum() * 100:.1f}%)")
    print(f"      ⚠️ BOS leakage risk: potrebbe superare 30%")
    
    # Combined simulation
    combined_inf = sim1_inf + sim2_inf
    new_coverage = (thresholds_data['coverage']['admitted_influence'] + combined_inf) / metrics_df['logit_influence'].sum() * 100
    
    print(f"\n🎯 COMBINED (Sim1 + Sim2 senza Sim3):")
    print(f"   Influence totale recuperata: {combined_inf:.2f}")
    print(f"   New coverage: {thresholds_data['coverage']['coverage_percent']:.1f}% → {new_coverage:.1f}%")
    print(f"   Improvement: +{new_coverage - thresholds_data['coverage']['coverage_percent']:.1f} pts")
    
    print(f"\n✅ RACCOMANDAZIONE:")
    print(f"   - Applica Sim1 (tau_aff 0.55) se vuoi più feature semantiche")
    print(f"   - Applica Sim2 (layer 25) solo se verifichi che non siano artifacts")
    print(f"   - Evita Sim3 (BOS p90) per mantenere BOS leakage <30%")

if __name__ == "__main__":
    analyze_remaining_excluded()

