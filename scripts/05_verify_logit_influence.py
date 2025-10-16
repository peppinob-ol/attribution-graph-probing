#!/usr/bin/env python3
"""
Verifica Logit Influence Coverage dei Supernodi Antropologici
Risponde: i nostri supernodi spiegano abbastanza il comportamento del modello?
"""

import json
import pandas as pd
from collections import defaultdict

def verify_logit_influence_coverage():
    """
    Calcola quanta logit influence è coperta dai supernodi antropologici
    vs. feature escluse come "non-informative"
    """
    
    print("🔬 VERIFICA LOGIT INFLUENCE COVERAGE")
    print("=" * 60)
    
    # 1. Carica logit influence per tutte le feature
    print("\n📊 Step 1: Caricamento metriche logit influence...")
    metrics_df = pd.read_csv("output/graph_feature_static_metrics (1).csv")
    
    # Crea feature_key come "layer_feature"
    metrics_df['feature_key'] = metrics_df['layer'].astype(str) + '_' + metrics_df['feature'].astype(str)
    
    total_logit_influence = metrics_df['logit_influence'].sum()
    print(f"   ✅ Logit influence totale del grafo: {total_logit_influence:.4f}")
    print(f"   📈 Feature totali nel grafo: {len(metrics_df)}")
    
    # 2. Carica supernodi antropologici
    print("\n🧠 Step 2: Caricamento supernodi antropologici...")
    with open("output/final_anthropological_optimized.json", 'r') as f:
        results = json.load(f)
    
    # Estrai tutte le feature nei supernodi
    supernode_features = set()
    
    for supernode in results['semantic_supernodes'].values():
        supernode_features.update(supernode['members'])
    
    for supernode in results['computational_supernodes'].values():
        supernode_features.update(supernode['members'])
    
    print(f"   ✅ Feature nei supernodi: {len(supernode_features)}")
    
    # 3. Calcola logit influence dei supernodi
    print("\n🎯 Step 3: Calcolo logit influence coverage...")
    
    supernode_df = metrics_df[metrics_df['feature_key'].isin(supernode_features)]
    supernode_logit_influence = supernode_df['logit_influence'].sum()
    supernode_coverage = (supernode_logit_influence / total_logit_influence) * 100
    
    print(f"   📊 Logit influence coperta dai supernodi: {supernode_logit_influence:.4f}")
    print(f"   🎯 Coverage percentuale: {supernode_coverage:.2f}%")
    
    # 4. Analisi feature "non-informative" escluse
    print("\n🗑️ Step 4: Analisi feature escluse come 'non-informative'...")
    
    excluded_features = set(metrics_df['feature_key']) - supernode_features
    excluded_df = metrics_df[metrics_df['feature_key'].isin(excluded_features)]
    excluded_logit_influence = excluded_df['logit_influence'].sum()
    excluded_coverage = (excluded_logit_influence / total_logit_influence) * 100
    
    print(f"   📊 Logit influence delle feature escluse: {excluded_logit_influence:.4f}")
    print(f"   💥 Coverage percentuale persa: {excluded_coverage:.2f}%")
    
    # 5. Analisi per categoria di esclusione
    print("\n🔍 Step 5: Breakdown feature escluse...")
    
    with open("output/feature_personalities_corrected.json", 'r') as f:
        personalities = json.load(f)
    
    # Categorie di esclusione
    layer0_features = [k for k in excluded_features if k in personalities and personalities[k]['layer'] == 0]
    low_consistency = [k for k in excluded_features if k in personalities and personalities[k].get('mean_consistency', personalities[k].get('consistency_score_legacy', 0)) == 0]
    bos_features = [k for k in excluded_features if k in personalities and personalities[k]['most_common_peak'] == '<BOS>']
    
    # Calcola logit influence per categoria
    def get_category_influence(feature_list):
        cat_df = metrics_df[metrics_df['feature_key'].isin(feature_list)]
        return cat_df['logit_influence'].sum()
    
    layer0_influence = get_category_influence(layer0_features)
    low_cons_influence = get_category_influence(low_consistency)
    bos_influence = get_category_influence(bos_features)
    
    print(f"   📉 Layer-0 features: {len(layer0_features)} → {layer0_influence:.4f} influence ({layer0_influence/total_logit_influence*100:.2f}%)")
    print(f"   📉 Zero consistency: {len(low_consistency)} → {low_cons_influence:.4f} influence ({low_cons_influence/total_logit_influence*100:.2f}%)")
    print(f"   📉 <BOS> features: {len(bos_features)} → {bos_influence:.4f} influence ({bos_influence/total_logit_influence*100:.2f}%)")
    
    # 6. Top feature escluse per logit influence
    print("\n⚠️ Step 6: Top 10 feature ESCLUSE con alta logit influence:")
    top_excluded = excluded_df.nlargest(10, 'logit_influence')[['layer', 'feature', 'logit_influence']]
    
    for idx, row in top_excluded.iterrows():
        fkey = f"{int(row['layer'])}_{int(row['feature'])}"
        personality = personalities.get(fkey, {})
        layer = personality.get('layer', '?')
        token = personality.get('most_common_peak', '?')
        consistency = personality.get('mean_consistency', personality.get('consistency_score_legacy', 0))
        
        print(f"   ⚠️ {fkey}: influence={row['logit_influence']:.4f}, token='{token}', mean_consistency={consistency:.3f}")
    
    # 7. Analisi per Feature Type
    print("\n" + "=" * 60)
    print("STEP 7: LOGIT INFLUENCE PER FEATURE TYPE")
    print("=" * 60)
    
    try:
        with open("output/feature_typology.json", 'r', encoding='utf-8') as f:
            typology = json.load(f)
        
        type_influence = defaultdict(lambda: {'count': 0, 'total_influence': 0})
        
        for fkey in supernode_features:
            if fkey in typology:
                ftype = typology[fkey]['type']
                influence = typology[fkey]['logit_influence']
                type_influence[ftype]['count'] += 1
                type_influence[ftype]['total_influence'] += influence
        
        print(f"\n   Distribuzione per tipo di feature:")
        for ftype in sorted(type_influence.keys()):
            data = type_influence[ftype]
            pct = (data['total_influence'] / total_logit_influence * 100) if total_logit_influence > 0 else 0
            avg = data['total_influence'] / data['count'] if data['count'] > 0 else 0
            print(f"      {ftype.capitalize()}: {data['count']} features, "
                  f"total influence: {data['total_influence']:.2f} ({pct:.1f}%), "
                  f"avg: {avg:.4f}")
        
        # Aggiungi ai risultati
        type_breakdown = {
            ftype: {
                'count': data['count'],
                'total_influence': float(data['total_influence']),
                'influence_percent': float(data['total_influence'] / total_logit_influence * 100) if total_logit_influence > 0 else 0,
                'avg_influence': float(data['total_influence'] / data['count']) if data['count'] > 0 else 0
            }
            for ftype, data in type_influence.items()
        }
    except FileNotFoundError:
        print("   ⚠️ File feature_typology.json non trovato - analisi per tipo saltata")
        type_breakdown = {}
    
    # 8. Attribution Graph Quality Metrics
    print("\n" + "=" * 60)
    print("🔬 STEP 8: ATTRIBUTION GRAPH QUALITY METRICS")
    print("=" * 60)
    
    try:
        import sys
        sys.path.insert(0, 'scripts')
        from causal_utils import load_attribution_graph, compute_edge_density
        
        graph_data = load_attribution_graph("output/example_graph.pt")
        
        if graph_data is not None:
            # Crea feature_to_idx mapping
            feature_to_idx = {}
            for i, (layer, pos, feat_idx) in enumerate(graph_data['active_features']):
                fkey = f"{layer.item()}_{feat_idx.item()}"
                feature_to_idx[fkey] = i
            
            # 8a. Media node_influence per supernodo
            node_influences = [personalities.get(fkey, {}).get('node_influence', 0) 
                              for fkey in supernode_features 
                              if fkey in personalities and 'node_influence' in personalities[fkey]]
            
            if node_influences:
                avg_node_influence = sum(node_influences) / len(node_influences)
                max_node_influence = max(node_influences)
                print(f"\n   📊 Node Influence (supernodi):")
                print(f"      Media: {avg_node_influence:.4f}")
                print(f"      Massima: {max_node_influence:.4f}")
                
                # 8b. Node influence coverage
                all_node_influences = [p.get('node_influence', 0) for p in personalities.values() 
                                      if 'node_influence' in p]
                if all_node_influences:
                    total_node_inf = sum(all_node_influences)
                    supernode_node_inf = sum(node_influences)
                    node_inf_coverage = (supernode_node_inf / total_node_inf * 100) if total_node_inf > 0 else 0
                    print(f"      Coverage: {node_inf_coverage:.1f}% del node_influence totale")
            else:
                print(f"\n   ⚠️ Node influence non disponibile")
                avg_node_influence = 0
                node_inf_coverage = 0
            
            # 8c. Edge density interna ai supernodi
            print(f"\n   🔗 Causal Edge Density:")
            edge_density = compute_edge_density(
                list(supernode_features),
                graph_data,
                feature_to_idx,
                tau_edge=0.01
            )
            print(f"      Internal edge density: {edge_density:.3f}")
            print(f"      Interpretazione: {'ALTA' if edge_density > 0.3 else 'MEDIA' if edge_density > 0.1 else 'BASSA'} "
                  f"connettività causale")
            
            # 8d. Top-20 coverage per node_influence
            if all_node_influences:
                sorted_features = sorted(
                    [(fkey, personalities[fkey].get('node_influence', 0)) 
                     for fkey in personalities if 'node_influence' in personalities[fkey]],
                    key=lambda x: x[1],
                    reverse=True
                )
                top20_features = set([f[0] for f in sorted_features[:20]])
                top20_in_supernodes = len(top20_features & supernode_features)
                top20_coverage = (top20_in_supernodes / 20 * 100) if len(top20_features) > 0 else 0
                
                print(f"\n   🎯 Top-20 Node Influence Coverage:")
                print(f"      {top20_in_supernodes}/20 feature top causali catturate ({top20_coverage:.0f}%)")
            
            # Salva metriche AG
            ag_metrics = {
                'avg_node_influence': float(avg_node_influence) if node_influences else 0.0,
                'node_influence_coverage_percent': float(node_inf_coverage) if node_influences else 0.0,
                'internal_edge_density': float(edge_density),
                'top20_coverage_percent': float(top20_coverage) if all_node_influences else 0.0
            }
        else:
            print(f"\n   ⚠️ Attribution Graph non disponibile")
            ag_metrics = {}
    
    except Exception as e:
        print(f"\n   ⚠️ Errore calcolo metriche AG: {e}")
        import traceback
        traceback.print_exc()
        ag_metrics = {}
    
    # 9. Risultato finale
    print("\n" + "=" * 60)
    print("🏆 RISULTATO VALIDAZIONE:")
    print("=" * 60)
    
    if supernode_coverage >= 80:
        print(f"✅ FORTE: I supernodi spiegano {supernode_coverage:.1f}% del comportamento del modello")
        print(f"   → La strategia antropologica cattura le feature più importanti!")
    elif supernode_coverage >= 60:
        print(f"⚠️ MODERATO: I supernodi spiegano {supernode_coverage:.1f}% del comportamento")
        print(f"   → Copertura accettabile ma migliorabile")
    else:
        print(f"❌ DEBOLE: I supernodi spiegano solo {supernode_coverage:.1f}% del comportamento")
        print(f"   → La tassonomia 'non-informative' potrebbe escludere feature importanti!")
    
    print(f"\n📊 Metrica corretta per MATS Application:")
    print(f"   '{supernode_coverage:.1f}% of model output influence captured'")
    print(f"   (891 features explaining {supernode_coverage:.1f}% of logit influence)")
    
    # Salva risultati
    validation_results = {
        'total_logit_influence': float(total_logit_influence),
        'supernode_logit_influence': float(supernode_logit_influence),
        'supernode_influence_coverage_percent': float(supernode_coverage),
        'excluded_logit_influence': float(excluded_logit_influence),
        'excluded_influence_percent': float(excluded_coverage),
        'breakdown': {
            'layer0_influence_percent': float(layer0_influence/total_logit_influence*100),
            'low_consistency_influence_percent': float(low_cons_influence/total_logit_influence*100),
            'bos_influence_percent': float(bos_influence/total_logit_influence*100)
        },
        'type_breakdown': type_breakdown,
        'ag_metrics': ag_metrics,
        'interpretation': 'STRONG' if supernode_coverage >= 80 else ('MODERATE' if supernode_coverage >= 60 else 'WEAK')
    }
    
    with open("output/logit_influence_validation.json", 'w', encoding='utf-8') as f:
        json.dump(validation_results, f, indent=2)
    
    print(f"\n💾 Risultati salvati: output/logit_influence_validation.json")
    
    return validation_results

if __name__ == "__main__":
    results = verify_logit_influence_coverage()
