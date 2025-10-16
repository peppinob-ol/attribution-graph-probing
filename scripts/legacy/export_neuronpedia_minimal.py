#!/usr/bin/env python3
"""
Export MINIMO per Neuronpedia - Solo top 3-5 supernodi per evitare URL troppo lunghi
"""

import json
import urllib.parse

def export_minimal_neuronpedia():
    """
    Crea URL Neuronpedia MINIMO con solo i top supernodi
    per evitare problemi di lunghezza URL
    """
    
    print("=" * 70)
    print("EXPORT NEURONPEDIA MINIMALE (TOP SUPERNODI ONLY)")
    print("=" * 70)
    print("")
    
    # Carica supernodi finali
    with open("output/final_anthropological_optimized.json", 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Carica personalities per logit_influence
    with open("output/feature_personalities_corrected.json", 'r', encoding='utf-8') as f:
        personalities = json.load(f)
    
    # Prompt e posizione
    prompt = "Fact: the capital of the state containing Dallas is"
    
    # Prova diverse posizioni (Neuronpedia potrebbe usare posizione diversa)
    positions_to_try = [-1, 10, 9, 8, 7]  # -1 = ultima posizione
    
    print("Posizioni token da provare:")
    for pos in positions_to_try:
        if pos == -1:
            actual_pos = len(prompt.split()) - 1
            print(f"  pos={actual_pos} (ultima posizione del prompt)")
        else:
            print(f"  pos={pos}")
    print("")
    
    # Usa ultima posizione per default
    pos = len(prompt.split()) - 1
    
    # Seleziona SOLO i top 3 supernodi semantici per influence
    semantic_supernodes = data.get('semantic_supernodes', {})
    
    # Calcola influence totale per ogni supernode
    supernodes_with_influence = []
    for sn_id, sn_data in semantic_supernodes.items():
        total_inf = sum(
            personalities.get(member, {}).get('logit_influence', 0)
            for member in sn_data.get('members', [])
        )
        supernodes_with_influence.append((sn_id, sn_data, total_inf))
    
    # Ordina per influence decrescente
    supernodes_with_influence.sort(key=lambda x: x[2], reverse=True)
    
    # Prendi solo top 3
    top_supernodes = supernodes_with_influence[:3]
    
    print("Top 3 Supernodi Semantici (per logit influence):")
    for i, (sn_id, sn_data, total_inf) in enumerate(top_supernodes, 1):
        theme = sn_data.get('narrative_theme', sn_id)
        n_members = len(sn_data.get('members', []))
        print(f"  {i}. {theme}: {n_members} feature, influence={total_inf:.4f}")
    print("")
    
    # Costruisci supernodes data
    supernodes_data = []
    pinned_ids = []
    
    for sn_id, sn_data, total_inf in top_supernodes:
        theme = sn_data.get('narrative_theme', sn_id)
        members = sn_data.get('members', [])
        
        # Calcola layer range per nome distintivo
        layers = []
        for member in members:
            if member in personalities:
                layers.append(personalities[member]['layer'])
        
        if layers:
            min_layer = min(layers)
            max_layer = max(layers)
            if min_layer == max_layer:
                name = f"{theme}_L{min_layer}"
            else:
                name = f"{theme}_L{min_layer}-{max_layer}"
        else:
            name = theme
        
        # Converti membri (LIMITA a max 10 per supernode per ridurre URL)
        member_strs = []
        for member in members[:10]:  # MAX 10 feature per supernode
            layer, feature = member.split('_')
            member_str = f"{layer}_{feature}_{pos}"
            member_strs.append(member_str)
            pinned_ids.append(member_str)
        
        supernodes_data.append([name] + member_strs)
    
    # Costruisci URL
    base_url = f"https://www.neuronpedia.org/gemma-2-2b/graph"
    
    params = {
        'slug': 'circuit-tracer-minimal',
        'supernodes': json.dumps(supernodes_data),
        'pinnedIds': ','.join(pinned_ids),
        'pruningThreshold': '0.6',
        'densityThreshold': '0.99'
    }
    
    query_string = urllib.parse.urlencode(params, safe='[],"')
    full_url = f"{base_url}?{query_string}"
    
    print("=" * 70)
    print("URL GENERATO (MINIMALE)")
    print("=" * 70)
    print("")
    print(f"Lunghezza URL: {len(full_url)} caratteri")
    print(f"Supernodi inclusi: {len(supernodes_data)}")
    print(f"Feature totali: {sum(len(sn)-1 for sn in supernodes_data)}")
    print("")
    print(full_url)
    print("")
    
    # Salva
    with open("output/neuronpedia_url_minimal.txt", 'w', encoding='utf-8') as f:
        f.write(full_url)
    
    # Salva anche versioni con diverse posizioni
    print("=" * 70)
    print("ALTERNATIVE URLs CON DIVERSE POSIZIONI")
    print("=" * 70)
    print("")
    
    alternative_urls = {}
    for alt_pos in [7, 8, 9, 10]:
        # Rigenera con posizione diversa
        alt_pinned = []
        alt_supernodes = []
        
        for sn_name_members in supernodes_data:
            name = sn_name_members[0]
            orig_members = sn_name_members[1:]
            
            new_members = []
            for member_str in orig_members:
                # Cambia solo la posizione
                parts = member_str.split('_')
                new_member = f"{parts[0]}_{parts[1]}_{alt_pos}"
                new_members.append(new_member)
                alt_pinned.append(new_member)
            
            alt_supernodes.append([name] + new_members)
        
        alt_params = {
            'slug': f'circuit-tracer-pos{alt_pos}',
            'supernodes': json.dumps(alt_supernodes),
            'pinnedIds': ','.join(alt_pinned),
            'pruningThreshold': '0.6',
            'densityThreshold': '0.99'
        }
        
        alt_query = urllib.parse.urlencode(alt_params, safe='[],"')
        alt_url = f"{base_url}?{alt_query}"
        alternative_urls[alt_pos] = alt_url
        
        print(f"pos={alt_pos}: {len(alt_url)} caratteri")
        with open(f"output/neuronpedia_url_pos{alt_pos}.txt", 'w', encoding='utf-8') as f:
            f.write(alt_url)
    
    print("")
    print("Salvati file:")
    print("  output/neuronpedia_url_minimal.txt")
    for pos in [7, 8, 9, 10]:
        print(f"  output/neuronpedia_url_pos{pos}.txt")
    print("")
    
    print("=" * 70)
    print("ISTRUZIONI")
    print("=" * 70)
    print("")
    print("Prova OGNI URL in ordine finché non vedi i nodi:")
    print("")
    print("1. Apri output/neuronpedia_url_pos10.txt")
    print("2. Copia l'URL e incollalo nel browser")
    print("3. Se vedi solo pochi nodi, prova pos9.txt, poi pos8.txt, ecc.")
    print("")
    print("La posizione corretta dipende da come Circuit Tracer ha")
    print("generato il grafo originale.")
    print("")
    print("=" * 70)

if __name__ == "__main__":
    export_minimal_neuronpedia()

