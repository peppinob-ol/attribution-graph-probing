#!/usr/bin/env python3
"""
Verifica Logit Influence Coverage dei Supernodi Antropologici
Risponde: i nostri supernodi spiegano abbastanza il comportamento del modello?
"""

import json
import pandas as pd

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
    low_consistency = [k for k in excluded_features if k in personalities and personalities[k]['consistency_score'] == 0]
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
        consistency = personality.get('consistency_score', 0)
        
        print(f"   ⚠️ {fkey}: influence={row['logit_influence']:.4f}, token='{token}', consistency={consistency:.3f}")
    
    # 7. Risultato finale
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
        'interpretation': 'STRONG' if supernode_coverage >= 80 else ('MODERATE' if supernode_coverage >= 60 else 'WEAK')
    }
    
    with open("output/logit_influence_validation.json", 'w', encoding='utf-8') as f:
        json.dump(validation_results, f, indent=2)
    
    print(f"\n💾 Risultati salvati: output/logit_influence_validation.json")
    
    return validation_results

if __name__ == "__main__":
    results = verify_logit_influence_coverage()
