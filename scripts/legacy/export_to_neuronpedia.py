#!/usr/bin/env python3
"""
Export supernodi antropologici verso formato URL Neuronpedia
"""

import json
import urllib.parse

def export_to_neuronpedia_url(
    supernodes_file='output/final_anthropological_optimized.json',
    prompt="Fact: the capital of the state containing Dallas is",
    model_name='gemma-2-2b',
    slug='circuit-tracer-anthropological',
    pos=None,  # Posizione di default nel prompt (None = ultima posizione)
    max_supernodes=10,
    include_computational=True
):
    """
    Crea URL Neuronpedia dai supernodi antropologici
    
    Args:
        supernodes_file: Path al file JSON con supernodi
        prompt: Prompt usato per generare i supernodi
        model_name: Nome modello su Neuronpedia
        slug: Identificatore univoco per il grafo
        pos: Posizione token nel prompt (None = usa len tokens - 1)
        max_supernodes: Numero massimo supernodi semantici da includere
        include_computational: Se includere supernodi computazionali
    """
    
    # Carica supernodi
    with open(supernodes_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Calcola posizione di default (ultima posizione del prompt)
    if pos is None:
        # Stima approssimativa: conta parole (tokenizzazione vera richiede il tokenizer)
        pos = len(prompt.split()) - 1
    
    supernodes_data = []
    pinned_ids = []
    
    # 1. Aggiungi supernodi semantici (cicciotti)
    semantic_supernodes = data.get('semantic_supernodes', {})
    semantic_count = 0
    
    print(f"\nProcessando supernodi semantici...")
    for supernode_id, sn_data in semantic_supernodes.items():
        if semantic_count >= max_supernodes:
            break
        
        # Nome del supernode (usa narrative_theme)
        theme = sn_data.get('narrative_theme', supernode_id)
        
        # Converti membri da "layer_feature" a "layer_feature_pos"
        members = []
        for member in sn_data.get('members', []):
            layer, feature = member.split('_')
            # Formato Neuronpedia: layer_feature_pos
            member_str = f"{layer}_{feature}_{pos}"
            members.append(member_str)
            pinned_ids.append(member_str)  # Aggiungi anche a pinnedIds
        
        # Aggiungi supernode: [nome, member1, member2, ...]
        supernodes_data.append([theme] + members)
        print(f"  + {theme}: {len(members)} feature")
        semantic_count += 1
    
    # 2. Aggiungi supernodi computazionali (opzionale)
    if include_computational:
        print(f"\nProcessando supernodi computazionali...")
        computational_supernodes = data.get('computational_supernodes', {})
        comp_count = 0
        max_computational = 5  # Limita per non sovraccaricare
        
        for supernode_id, sn_data in computational_supernodes.items():
            if comp_count >= max_computational:
                break
            
            # Nome: usa dominant_token o layer info
            token = sn_data.get('dominant_token', 'comp')
            avg_layer = sn_data.get('avg_layer', 0)
            name = f"{token}_L{int(avg_layer)}"
            
            # Converti membri
            members = []
            for member in sn_data.get('members', []):
                layer, feature = member.split('_')
                member_str = f"{layer}_{feature}_{pos}"
                members.append(member_str)
                pinned_ids.append(member_str)
            
            supernodes_data.append([name] + members)
            print(f"  + {name}: {len(members)} feature")
            comp_count += 1
    
    # 3. Costruisci URL
    base_url = f"https://www.neuronpedia.org/{model_name}/graph"
    
    # Parametri query
    params = {
        'slug': slug,
        'supernodes': json.dumps(supernodes_data),
        'pinnedIds': ','.join(pinned_ids),
        'pruningThreshold': '0.6',  # Default threshold
        'densityThreshold': '0.99'
    }
    
    # Costruisci URL completo
    query_string = urllib.parse.urlencode(params, safe='[],"')
    full_url = f"{base_url}?{query_string}"
    
    return full_url, supernodes_data


def main():
    """Genera URL e stampa risultati"""
    
    print("=" * 70)
    print("EXPORT SUPERNODI ANTROPOLOGICI -> NEURONPEDIA")
    print("=" * 70)
    
    # Genera URL
    url, supernodes_data = export_to_neuronpedia_url(
        max_supernodes=10,
        include_computational=True
    )
    
    print(f"\n{'=' * 70}")
    print("RISULTATI EXPORT")
    print("=" * 70)
    
    print(f"\nGenerato URL Neuronpedia con:")
    print(f"  Supernodi totali: {len(supernodes_data)}")
    print(f"  Feature totali: {sum(len(sn)-1 for sn in supernodes_data)}")
    
    print(f"\nSupernodi inclusi:")
    for i, sn in enumerate(supernodes_data[:15], 1):
        print(f"  {i:2d}. {sn[0]}: {len(sn)-1} feature")
    
    if len(supernodes_data) > 15:
        print(f"  ... e altri {len(supernodes_data)-15}")
    
    print(f"\n{'=' * 70}")
    print("URL NEURONPEDIA")
    print("=" * 70)
    print(f"\n{url}\n")
    
    # Salva anche su file per comodità
    with open("output/neuronpedia_url.txt", 'w', encoding='utf-8') as f:
        f.write(url)
    
    with open("output/neuronpedia_supernodes.json", 'w', encoding='utf-8') as f:
        json.dump(supernodes_data, f, indent=2)
    
    print(f"Salvato anche su:")
    print(f"  output/neuronpedia_url.txt")
    print(f"  output/neuronpedia_supernodes.json")
    
    print(f"\n{'=' * 70}")
    print("ISTRUZIONI")
    print("=" * 70)
    print(f"\n1. Copia l'URL sopra")
    print(f"2. Incollalo nella barra degli indirizzi del browser")
    print(f"3. Neuronpedia caricherà il grafo con i tuoi supernodi")
    print(f"4. Puoi interagire, modificare labels, fare interventions")
    print(f"\nNOTA: L'URL è molto lungo, ma Neuronpedia lo gestisce correttamente")
    
    print(f"\n{'=' * 70}\n")


if __name__ == "__main__":
    main()



