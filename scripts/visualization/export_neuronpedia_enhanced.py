#!/usr/bin/env python3
"""
Export Neuronpedia Migliorato
- Include embeddings come nodo dedicato
- Include "Say Austin" come supernodo output_driver
- Filtra <BOS> per node_influence (p95)
- Crea macro-gruppi per supernodi simili (Jaccard > 0.7)
"""

import json
import numpy as np
from pathlib import Path
from collections import defaultdict
import sys
sys.path.insert(0, 'scripts')


def compute_edge_signature_similarity(sn1_data, sn2_data, causal_metrics):
    """
    Calcola similarità Jaccard tra edge-signature di due supernodi
    """
    # Raccogli tutti i top_parents e top_children dei membri
    neighbors1 = set()
    for member in sn1_data.get('members', []):
        if member in causal_metrics:
            neighbors1.update([p[0] for p in causal_metrics[member].get('top_parents', [])])
            neighbors1.update([c[0] for c in causal_metrics[member].get('top_children', [])])
    
    neighbors2 = set()
    for member in sn2_data.get('members', []):
        if member in causal_metrics:
            neighbors2.update([p[0] for p in causal_metrics[member].get('top_parents', [])])
            neighbors2.update([c[0] for c in causal_metrics[member].get('top_children', [])])
    
    if len(neighbors1 | neighbors2) == 0:
        return 0.0
    
    jaccard = len(neighbors1 & neighbors2) / len(neighbors1 | neighbors2)
    return jaccard


def create_macro_groups(supernodes, causal_metrics, similarity_threshold=0.7):
    """
    Crea macro-gruppi per supernodi con edge-signature simile
    """
    print(f"\n🔗 Creazione macro-gruppi (Jaccard >= {similarity_threshold})")
    
    # Identifica supernodi simili (es. Capital_L*)
    macro_groups = []
    processed = set()
    
    sn_list = list(supernodes.items())
    
    for i, (sn_id1, sn1_data) in enumerate(sn_list):
        if sn_id1 in processed:
            continue
        
        # Inizia un nuovo gruppo
        group = {
            'name': f"MACRO_{len(macro_groups)+1}",
            'base_supernode': sn_id1,
            'members': [sn_id1],
            'similarity_scores': []
        }
        processed.add(sn_id1)
        
        # Trova supernodi simili
        for j, (sn_id2, sn2_data) in enumerate(sn_list[i+1:], start=i+1):
            if sn_id2 in processed:
                continue
            
            # Calcola similarità
            sim = compute_edge_signature_similarity(sn1_data, sn2_data, causal_metrics)
            
            if sim >= similarity_threshold:
                group['members'].append(sn_id2)
                group['similarity_scores'].append((sn_id2, sim))
                processed.add(sn_id2)
        
        # Aggiungi gruppo solo se ha almeno 2 membri
        if len(group['members']) >= 2:
            macro_groups.append(group)
            print(f"   {group['name']}: {len(group['members'])} supernodi (base: {sn_id1})")
    
    return macro_groups


def filter_bos_by_influence(personalities, node_influence_threshold_p95):
    """
    Filtra feature <BOS> mantenendo solo quelle con alta node_influence
    """
    bos_features = []
    bos_high_influence = []
    
    for fkey, personality in personalities.items():
        if personality.get('most_common_peak') == '<BOS>':
            bos_features.append(fkey)
            node_inf = personality.get('node_influence', 0)
            if node_inf >= node_influence_threshold_p95:
                bos_high_influence.append(fkey)
    
    print(f"\n🔍 Filtro <BOS>:")
    print(f"   Totale <BOS>: {len(bos_features)}")
    print(f"   Alta influence (p95): {len(bos_high_influence)}")
    print(f"   Escluse: {len(bos_features) - len(bos_high_influence)}")
    
    return bos_high_influence, set(bos_features) - set(bos_high_influence)


def export_neuronpedia_enhanced(
    supernodes_path: str = "output/cicciotti_supernodes.json",
    personalities_path: str = "output/feature_personalities_corrected.json",
    graph_path: str = "output/example_graph.pt",
    output_url_file: str = "output/neuronpedia_enhanced_url.txt",
    similarity_threshold: float = 0.7
):
    """
    Export migliorato a Neuronpedia con embeddings, Say Austin, filtro BOS e macro-gruppi
    """
    print(f"🚀 NEURONPEDIA EXPORT ENHANCED")
    print(f"=" * 60)
    
    # 1. Carica dati
    print(f"\n📥 Step 1: Caricamento dati...")
    
    with open(supernodes_path, 'r') as f:
        supernodes = json.load(f)
    print(f"   ✅ Supernodi: {len(supernodes)}")
    
    with open(personalities_path, 'r') as f:
        personalities = json.load(f)
    print(f"   ✅ Personalities: {len(personalities)}")
    
    from causal_utils import load_attribution_graph
    graph_data = load_attribution_graph(graph_path)
    if graph_data is None:
        print(f"   ⚠️ Grafo non caricato, procedo senza metriche causali")
        causal_metrics = {}
    else:
        # Estrai causal_metrics dalle personalities
        causal_metrics = {}
        for fkey, p in personalities.items():
            if 'node_influence' in p:
                causal_metrics[fkey] = {
                    'node_influence': p['node_influence'],
                    'top_parents': p.get('top_parents', []),
                    'top_children': p.get('top_children', [])
                }
        print(f"   ✅ Causal metrics: {len(causal_metrics)}")
    
    # 2. Calcola soglia p95 per node_influence
    print(f"\n📊 Step 2: Calcolo soglie...")
    node_influences = [m['node_influence'] for m in causal_metrics.values()]
    if node_influences:
        tau_node_p95 = np.percentile(node_influences, 95)
        print(f"   τ_node_p95: {tau_node_p95:.6f}")
    else:
        tau_node_p95 = 0
        print(f"   ⚠️ Node influence non disponibile")
    
    # 3. Filtro <BOS>
    bos_kept, bos_excluded = filter_bos_by_influence(personalities, tau_node_p95)
    
    # 4. Identifica Say Austin
    print(f"\n🎯 Step 3: Identificazione Say Austin...")
    say_austin_sn = None
    for sn_id, sn_data in supernodes.items():
        # Cerca supernode con is_say_austin=True o con seed alla posizione finale e alta influence su Austin
        seed = sn_data.get('seed', '')
        if seed in personalities:
            seed_p = personalities[seed]
            # Criterio: posizione finale + token con "Austin" o "capital"
            if (seed_p.get('position', -1) == max([personalities[m].get('position', 0) for m in sn_data.get('members', [])]) and
                any(tok in seed_p.get('most_common_peak', '').lower() for tok in ['austin', 'capital'])):
                say_austin_sn = (sn_id, sn_data)
                print(f"   ✅ Say Austin trovato: {sn_id} (seed: {seed})")
                break
    
    if say_austin_sn is None:
        print(f"   ⚠️ Say Austin non trovato automaticamente")
    
    # 5. Crea macro-gruppi
    print(f"\n🔗 Step 4: Creazione macro-gruppi...")
    macro_groups = create_macro_groups(supernodes, causal_metrics, similarity_threshold)
    
    # 6. Prepara nodi per Neuronpedia
    print(f"\n📦 Step 5: Preparazione nodi...")
    
    neuronpedia_nodes = []
    
    # 6a. Embedding node
    if graph_data:
        input_tokens = graph_data.get('input_tokens', [])
        token_strings = []
        for i, tok_id in enumerate(input_tokens):
            # Semplificato: usa indice
            token_strings.append(f"Token_{i}")
        
        neuronpedia_nodes.append({
            'id': 'EMBEDDINGS',
            'label': 'Input Embeddings',
            'type': 'embedding',
            'layer': -1,
            'features': token_strings[:10],  # Mostra prime 10
            'description': f'{len(token_strings)} input tokens'
        })
        print(f"   ✅ Embeddings node creato ({len(token_strings)} tokens)")
    
    # 6b. Say Austin (se trovato)
    if say_austin_sn:
        sn_id, sn_data = say_austin_sn
        neuronpedia_nodes.append({
            'id': f'SAY_AUSTIN_{sn_id}',
            'label': 'Say Austin',
            'type': 'output_driver',
            'layer': personalities[sn_data['seed']]['layer'],
            'features': sn_data['members'][:10],  # Top 10
            'n_features': len(sn_data['members']),
            'node_influence': sn_data.get('total_influence_score', 0),
            'description': f'Direct output driver for "Austin" logit'
        })
        print(f"   ✅ Say Austin node creato")
    
    # 6c. Macro-gruppi
    for macro in macro_groups:
        all_members = []
        for sn_id in macro['members']:
            all_members.extend(supernodes[sn_id].get('members', []))
        
        # Filtra <BOS> escluse
        all_members = [m for m in all_members if m not in bos_excluded]
        
        neuronpedia_nodes.append({
            'id': macro['name'],
            'label': f"{macro['name']} ({len(macro['members'])} supernodes)",
            'type': 'macro_group',
            'features': all_members[:20],  # Top 20
            'n_features': len(all_members),
            'supernodes': macro['members'],
            'description': f'Macro-group of {len(macro['members'])} causally-similar supernodes'
        })
    
    print(f"   ✅ {len(macro_groups)} macro-gruppi creati")
    
    # 6d. Supernodi rimanenti (non in macro-gruppi, non Say Austin, filtrati per <BOS>)
    macro_members = set()
    for macro in macro_groups:
        macro_members.update(macro['members'])
    
    say_austin_id = say_austin_sn[0] if say_austin_sn else None
    
    for sn_id, sn_data in supernodes.items():
        if sn_id in macro_members or sn_id == say_austin_id:
            continue
        
        # Filtra membri <BOS> esclusi
        members = [m for m in sn_data.get('members', []) if m not in bos_excluded]
        
        if len(members) == 0:
            continue
        
        neuronpedia_nodes.append({
            'id': sn_id,
            'label': sn_id,
            'type': 'supernode',
            'layer': personalities[sn_data['seed']]['layer'] if sn_data['seed'] in personalities else -1,
            'features': members[:15],  # Top 15
            'n_features': len(members),
            'coherence': sn_data.get('final_coherence', 0),
            'description': f'Supernode with {len(members)} features'
        })
    
    print(f"   ✅ Totale nodi per Neuronpedia: {len(neuronpedia_nodes)}")
    
    # 7. Salva e genera URL
    print(f"\n💾 Step 6: Salvataggio...")
    
    output_data = {
        'nodes': neuronpedia_nodes,
        'metadata': {
            'total_supernodes': len(supernodes),
            'macro_groups': len(macro_groups),
            'bos_filtered': len(bos_excluded),
            'has_say_austin': say_austin_sn is not None,
            'similarity_threshold': similarity_threshold
        }
    }
    
    output_json = output_url_file.replace('.txt', '.json')
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2)
    
    print(f"   ✅ JSON salvato: {output_json}")
    
    # Genera URL Neuronpedia (placeholder - richiede upload reale)
    neuronpedia_url = "https://neuronpedia.org/sae_graph?..." # URL placeholder
    
    with open(output_url_file, 'w', encoding='utf-8') as f:
        f.write(f"Neuronpedia Enhanced Export\n")
        f.write(f"=" * 60 + "\n\n")
        f.write(f"Totale nodi: {len(neuronpedia_nodes)}\n")
        f.write(f"Macro-gruppi: {len(macro_groups)}\n")
        f.write(f"Say Austin: {'Yes' if say_austin_sn else 'No'}\n")
        f.write(f"<BOS> filtrate: {len(bos_excluded)}\n\n")
        f.write(f"Per caricare su Neuronpedia:\n")
        f.write(f"1. Usa il file JSON: {output_json}\n")
        f.write(f"2. Carica su Neuronpedia SAE Graph Viewer\n")
        f.write(f"3. URL placeholder: {neuronpedia_url}\n")
    
    print(f"   ✅ URL info salvato: {output_url_file}")
    
    print(f"\n✅ Export Enhanced completato!")
    print(f"   Nodi totali: {len(neuronpedia_nodes)}")
    print(f"   - Embeddings: 1")
    print(f"   - Say Austin: {1 if say_austin_sn else 0}")
    print(f"   - Macro-gruppi: {len(macro_groups)}")
    print(f"   - Supernodi individuali: {len(neuronpedia_nodes) - len(macro_groups) - 1 - (1 if say_austin_sn else 0)}")
    
    return output_json, output_url_file


if __name__ == "__main__":
    export_neuronpedia_enhanced(
        supernodes_path="output/cicciotti_supernodes.json",
        personalities_path="output/feature_personalities_corrected.json",
        graph_path="output/example_graph.pt",
        output_url_file="output/neuronpedia_enhanced_url.txt",
        similarity_threshold=0.7
    )
    
    print(f"\n🎉 Script completato!")

