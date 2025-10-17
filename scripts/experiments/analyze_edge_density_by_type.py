#!/usr/bin/env python3
"""
Analizza edge density interna separata per:
- content ↔ content
- content ↔ BOS
- BOS ↔ BOS
Per capire se la densità è sostenuta da hub generici o spine causali specifiche.
"""
import json
import sys
sys.path.insert(0, 'scripts')
from causal_utils import load_attribution_graph, compute_edge_density

FINAL = "output/final_anthropological_optimized.json"
PERSON = "output/feature_personalities_corrected.json"
GRAPH = "output/example_graph.pt"

def main():
    print("ANALISI EDGE DENSITY PER TIPO DI NODO")
    print("=" * 60)
    
    # Carica dati
    with open(FINAL, 'r', encoding='utf-8') as f:
        results = json.load(f)
    with open(PERSON, 'r', encoding='utf-8') as f:
        personalities = json.load(f)
    
    graph_data = load_attribution_graph(GRAPH)
    
    # Crea feature_to_idx mapping
    feature_to_idx = {}
    for i, (layer, pos, feat_idx) in enumerate(graph_data['active_features']):
        fkey = f"{layer.item()}_{feat_idx.item()}"
        feature_to_idx[fkey] = i
    
    # Raccogli tutte le feature nei supernodi
    all_features = set()
    for sn in results['semantic_supernodes'].values():
        all_features.update(sn.get('members', []))
    for sn in results['computational_supernodes'].values():
        all_features.update(sn.get('members', []))
    
    print(f"\nFeature totali nei supernodi: {len(all_features)}")
    
    # Separa in content vs BOS
    content_features = []
    bos_features = []
    
    for fkey in all_features:
        if fkey in personalities:
            peak_token = personalities[fkey].get('most_common_peak', '')
            if peak_token == '<BOS>':
                bos_features.append(fkey)
            else:
                content_features.append(fkey)
    
    print(f"   Content features (non-BOS): {len(content_features)}")
    print(f"   BOS features: {len(bos_features)}")
    
    # Calcola densità separatamente
    print("\nCalcolo edge density per tipo...")
    
    results_density = {}
    
    if len(content_features) >= 2:
        density_content = compute_edge_density(
            content_features, graph_data, feature_to_idx, tau_edge=0.01
        )
        results_density['content_to_content'] = float(density_content)
        print(f"   Content ↔ Content: {density_content:.3f}")
    else:
        results_density['content_to_content'] = 0.0
        print(f"   Content ↔ Content: n/a (troppo poche feature)")
    
    if len(bos_features) >= 2:
        density_bos = compute_edge_density(
            bos_features, graph_data, feature_to_idx, tau_edge=0.01
        )
        results_density['bos_to_bos'] = float(density_bos)
        print(f"   BOS ↔ BOS: {density_bos:.3f}")
    else:
        results_density['bos_to_bos'] = 0.0
        print(f"   BOS ↔ BOS: n/a (troppo poche feature)")
    
    if len(content_features) >= 1 and len(bos_features) >= 1:
        # Mix: content + bos insieme
        mixed_features = content_features + bos_features
        density_mixed = compute_edge_density(
            mixed_features, graph_data, feature_to_idx, tau_edge=0.01
        )
        results_density['mixed'] = float(density_mixed)
        print(f"   Mixed (Content + BOS): {density_mixed:.3f}")
    else:
        results_density['mixed'] = 0.0
    
    # Interpretazione
    print("\nINTERPRETAZIONE:")
    print("=" * 60)
    
    content_dense = results_density.get('content_to_content', 0)
    bos_dense = results_density.get('bos_to_bos', 0)
    mixed_dense = results_density.get('mixed', 0)
    
    if content_dense > bos_dense:
        print("OK: Densita causale maggiore tra feature di CONTENUTO")
        print("   Le spine causali specifiche dominano i circuiti")
    else:
        print("WARN: Densita causale maggiore tra feature BOS")
        print("   Gli hub generici (<BOS>) sostengono la connettivita")
    
    if mixed_dense > max(content_dense, bos_dense):
        print("\nLa densita mista e superiore alle densita interne")
        print("   Forte interconnessione tra content e BOS")
    
    # Analisi per supernodo
    print("\nDENSITA PER SUPERNODO:")
    sn_densities = []
    
    for sn_id, sn in list(results['semantic_supernodes'].items())[:10]:  # primi 10
        members = sn.get('members', [])
        if len(members) < 2:
            continue
        
        # Conta content vs BOS
        n_content = sum(
            1 for m in members 
            if personalities.get(m, {}).get('most_common_peak', '') != '<BOS>'
        )
        n_bos = len(members) - n_content
        
        density = compute_edge_density(members, graph_data, feature_to_idx, tau_edge=0.01)
        
        sn_densities.append({
            'supernode_id': sn_id,
            'n_members': len(members),
            'n_content': n_content,
            'n_bos': n_bos,
            'density': float(density)
        })
        
        print(f"   {sn_id}: density={density:.3f}, "
              f"content={n_content}, bos={n_bos}")
    
    # Salva risultati
    output = {
        "summary": {
            "total_features": len(all_features),
            "content_features": len(content_features),
            "bos_features": len(bos_features)
        },
        "density_by_type": results_density,
        "supernode_densities": sn_densities
    }
    
    with open("output/edge_density_by_type.json", 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2)
    
    print(f"\nSalvato: output/edge_density_by_type.json")

if __name__ == "__main__":
    main()

