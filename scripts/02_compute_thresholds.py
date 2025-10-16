#!/usr/bin/env python3
"""
Calcolo soglie robuste per filtering influence-first
τ_inf: copertura 80% influence cumulata o p90
τ_aff: 0.60 (configurabile)
"""

import json
import pandas as pd
import numpy as np

def compute_robust_thresholds():
    """Calcola soglie robuste per influence e affinity"""
    
    print("=" * 60)
    print("CALCOLO SOGLIE ROBUSTE (INFLUENCE-FIRST)")
    print("=" * 60)
    
    # 1. Carica logit influence
    print("\n📊 Step 1: Caricamento logit influence...")
    metrics_df = pd.read_csv("output/graph_feature_static_metrics (1).csv")
    metrics_df['feature_key'] = metrics_df['layer'].astype(str) + '_' + metrics_df['feature'].astype(str)
    
    total_influence = metrics_df['logit_influence'].sum()
    print(f"   Total influence: {total_influence:.2f}")
    
    # 2. Calcola τ_inf basato su copertura 80%
    sorted_df = metrics_df.sort_values('logit_influence', ascending=False)
    sorted_df['cumulative_influence'] = sorted_df['logit_influence'].cumsum()
    sorted_df['cumulative_pct'] = sorted_df['cumulative_influence'] / total_influence
    
    # Trova cutoff per 80% coverage
    idx_80 = (sorted_df['cumulative_pct'] >= 0.80).idxmax()
    tau_inf_80 = sorted_df.loc[idx_80, 'logit_influence']
    n_features_80 = (sorted_df['cumulative_pct'] >= 0.80).sum()
    
    # Calcola p90 come safety minimum
    tau_inf_p90 = np.percentile(metrics_df['logit_influence'], 90)
    
    # Scegli il più permissivo
    tau_inf = min(tau_inf_80, tau_inf_p90)
    
    print(f"\n🎯 τ_inf (logit influence threshold):")
    print(f"   80% coverage cutoff: {tau_inf_80:.6f} ({n_features_80} features)")
    print(f"   P90 safety minimum: {tau_inf_p90:.6f}")
    print(f"   → CHOSEN (most permissive): {tau_inf:.6f}")
    
    # 3. Carica personalities per max_affinity
    print(f"\n📊 Step 2: Caricamento max_affinity...")
    with open("output/feature_personalities_corrected.json", 'r', encoding='utf-8') as f:
        personalities = json.load(f)
    
    max_affinities = [p['max_affinity'] for p in personalities.values()]
    
    # τ_aff: 0.60 (safe default)
    tau_aff = 0.60
    n_features_aff = sum(1 for a in max_affinities if a >= tau_aff)
    
    print(f"\n🎯 τ_aff (max affinity threshold):")
    print(f"   Safe default: {tau_aff:.2f}")
    print(f"   Features passing: {n_features_aff}")
    
    # τ_cons: 0.60 (solo per labeling scaffold)
    tau_cons = 0.60
    mean_consistencies = [p['mean_consistency'] for p in personalities.values()]
    n_features_cons = sum(1 for c in mean_consistencies if c >= tau_cons)
    
    print(f"\n🎯 τ_cons (mean consistency, labeling only):")
    print(f"   Safe default: {tau_cons:.2f}")
    print(f"   Features passing: {n_features_cons}")
    
    # 4. Calcola tau_node_inf da node_influence (AG)
    print(f"\n🔗 Step 3a: Calcolo tau_node_inf da Attribution Graph...")
    node_influences = [p.get('node_influence', 0) for p in personalities.values() 
                      if 'node_influence' in p]
    
    if node_influences:
        tau_node_inf = np.percentile(node_influences, 90)
        tau_node_very_high = np.percentile(node_influences, 95)
        print(f"   τ_node_inf (node influence p90): {tau_node_inf:.6f}")
        print(f"   τ_node_very_high (for <BOS> p95): {tau_node_very_high:.6f}")
    else:
        print(f"   ⚠️ Node influence non disponibile, uso solo logit_influence")
        tau_node_inf = 0
        tau_node_very_high = 0
    
    # 5. Calcola feature passanti con criterio esteso + BOS filter
    print(f"\n📈 Step 3b: Applicazione criterio esteso + BOS filter...")
    
    # Soglia "influence altissima" per <BOS>: p95
    tau_inf_very_high = np.percentile(metrics_df['logit_influence'], 95)
    print(f"   τ_inf_very_high (logit influence for <BOS>): {tau_inf_very_high:.6f} (p95)")
    
    # Merge dati
    features_pass_influence = set()
    features_pass_affinity = set()
    features_pass_consistency = set()
    
    for _, row in metrics_df.iterrows():
        fkey = row['feature_key']
        
        # Check BOS: se è <BOS>, richiedi influence altissima
        is_bos = fkey in personalities and personalities[fkey]['most_common_peak'] == '<BOS>'
        
        # Check influence (con filtro BOS + node_influence)
        if is_bos:
            # <BOS> ammesso solo se influence altissima (logit OR node)
            node_inf = personalities.get(fkey, {}).get('node_influence', 0)
            if row['logit_influence'] >= tau_inf_very_high or node_inf >= tau_node_very_high:
                features_pass_influence.add(fkey)
        else:
            # Non-BOS: criterio esteso (logit_influence OR node_influence)
            node_inf = personalities.get(fkey, {}).get('node_influence', 0)
            if row['logit_influence'] >= tau_inf or node_inf >= tau_node_inf:
                features_pass_influence.add(fkey)
        
        # Check affinity (se esiste in personalities)
        if fkey in personalities:
            p = personalities[fkey]
            # <BOS> escluso anche da affinity/consistency salvo influence altissima
            if is_bos and row['logit_influence'] < tau_inf_very_high:
                continue  # Skip <BOS> con bassa influence
            
            if p['max_affinity'] >= tau_aff:
                features_pass_affinity.add(fkey)
            if p['mean_consistency'] >= tau_cons:
                features_pass_consistency.add(fkey)
    
    # Situational core: solo influence
    situational_core = features_pass_influence
    
    # Generalizable scaffold: affinity OR consistency
    generalizable_scaffold = features_pass_affinity.union(features_pass_consistency)
    
    # Totale ammesso
    features_admitted = situational_core.union(generalizable_scaffold)
    
    print(f"\n🔍 Breakdown per vista:")
    print(f"   Situational core (influence): {len(situational_core)} features")
    print(f"   Generalizable scaffold (affinity|consistency): {len(generalizable_scaffold)} features")
    print(f"   Overlap (core ∩ scaffold): {len(situational_core.intersection(generalizable_scaffold))} features")
    print(f"   TOTAL ADMITTED: {len(features_admitted)} features")
    
    # 5. Calcola influence coverage
    admitted_df = metrics_df[metrics_df['feature_key'].isin(features_admitted)]
    admitted_influence = admitted_df['logit_influence'].sum()
    coverage_pct = (admitted_influence / total_influence) * 100
    
    print(f"\n🎯 Influence Coverage:")
    print(f"   Admitted influence: {admitted_influence:.2f} / {total_influence:.2f}")
    print(f"   Coverage: {coverage_pct:.1f}%")
    
    # 6. Breakdown influence per vista
    core_df = metrics_df[metrics_df['feature_key'].isin(situational_core)]
    scaffold_df = metrics_df[metrics_df['feature_key'].isin(generalizable_scaffold)]
    
    core_influence = core_df['logit_influence'].sum()
    scaffold_influence = scaffold_df['logit_influence'].sum()
    
    print(f"\n📊 Influence breakdown:")
    print(f"   Situational core: {core_influence:.2f} ({core_influence/total_influence*100:.1f}%)")
    print(f"   Generalizable scaffold: {scaffold_influence:.2f} ({scaffold_influence/total_influence*100:.1f}%)")
    
    # 7. Controllo qualità: leakage BOS
    bos_features = [fkey for fkey in features_admitted 
                   if fkey in personalities and personalities[fkey]['most_common_peak'] == '<BOS>']
    bos_df = metrics_df[metrics_df['feature_key'].isin(bos_features)]
    bos_influence = bos_df['logit_influence'].sum()
    bos_pct = (bos_influence / admitted_influence) * 100 if admitted_influence > 0 else 0
    
    print(f"\n⚠️ Controllo qualità:")
    print(f"   <BOS> features admitted: {len(bos_features)} ({len(bos_features)/len(features_admitted)*100:.1f}%)")
    print(f"   <BOS> influence: {bos_influence:.2f} ({bos_pct:.1f}% of admitted)")
    
    if bos_pct > 30:
        print(f"   ⚠️ WARNING: BOS leakage >30%, consider excluding <BOS> or raising τ_aff")
    else:
        print(f"   ✅ BOS leakage acceptable (<30%)")
    
    # 8. Salva risultati
    results = {
        'thresholds': {
            'tau_inf': float(tau_inf),
            'tau_inf_80_cutoff': float(tau_inf_80),
            'tau_inf_p90': float(tau_inf_p90),
            'tau_inf_very_high': float(tau_inf_very_high),
            'tau_node_inf': float(tau_node_inf) if node_influences else 0.0,
            'tau_node_very_high': float(tau_node_very_high) if node_influences else 0.0,
            'tau_aff': float(tau_aff),
            'tau_cons': float(tau_cons)
        },
        'admitted_features': {
            'situational_core': list(situational_core),
            'generalizable_scaffold': list(generalizable_scaffold),
            'total': list(features_admitted)
        },
        'coverage': {
            'total_influence': float(total_influence),
            'admitted_influence': float(admitted_influence),
            'coverage_percent': float(coverage_pct),
            'core_influence_percent': float(core_influence/total_influence*100),
            'scaffold_influence_percent': float(scaffold_influence/total_influence*100)
        },
        'counts': {
            'situational_core': len(situational_core),
            'generalizable_scaffold': len(generalizable_scaffold),
            'overlap': len(situational_core.intersection(generalizable_scaffold)),
            'total_admitted': len(features_admitted)
        },
        'quality_checks': {
            'bos_features_count': len(bos_features),
            'bos_influence_percent': float(bos_pct),
            'bos_leakage_ok': bool(bos_pct <= 30)
        }
    }
    
    with open("output/robust_thresholds.json", 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2)
    
    print(f"\n💾 Risultati salvati: output/robust_thresholds.json")
    
    return results

if __name__ == "__main__":
    results = compute_robust_thresholds()
    
    print("\n" + "=" * 60)
    print("✅ THRESHOLDS COMPUTED")
    print("=" * 60)
    print(f"\nPrevious method (consistency gate): ~28% influence coverage")
    print(f"New method (influence-first): {results['coverage']['coverage_percent']:.1f}% influence coverage")
    print(f"\n🎯 Ready to rerun pipeline with new thresholds!")

