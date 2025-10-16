#!/usr/bin/env python3
"""
Export Neuronpedia con range esteso di posizioni (10-15)
"""

import json
import urllib.parse

def export_extended_positions():
    """
    Genera URL per posizioni 10-15 per trovare quella corretta
    """
    
    print("=" * 70)
    print("EXPORT NEURONPEDIA - POSIZIONI ESTESE (10-15)")
    print("=" * 70)
    print("")
    
    # Carica supernodi finali
    with open("output/final_anthropological_optimized.json", 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    # Carica personalities
    with open("output/feature_personalities_corrected.json", 'r', encoding='utf-8') as f:
        personalities = json.load(f)
    
    # Top 3 supernodi semantici
    semantic_supernodes = data.get('semantic_supernodes', {})
    
    # Calcola influence e prendi top 3
    supernodes_with_influence = []
    for sn_id, sn_data in semantic_supernodes.items():
        total_inf = sum(
            personalities.get(member, {}).get('logit_influence', 0)
            for member in sn_data.get('members', [])
        )
        supernodes_with_influence.append((sn_id, sn_data, total_inf))
    
    supernodes_with_influence.sort(key=lambda x: x[2], reverse=True)
    top_supernodes = supernodes_with_influence[:3]
    
    # Template supernodes (senza posizione)
    supernodes_template = []
    for sn_id, sn_data, total_inf in top_supernodes:
        theme = sn_data.get('narrative_theme', sn_id)
        members = sn_data.get('members', [])
        
        # Calcola layer range
        layers = [personalities[m]['layer'] for m in members if m in personalities]
        if layers:
            min_layer, max_layer = min(layers), max(layers)
            name = f"{theme}_L{min_layer}-{max_layer}" if min_layer != max_layer else f"{theme}_L{min_layer}"
        else:
            name = theme
        
        # Membri come layer_feature (senza pos)
        supernodes_template.append({
            'name': name,
            'members': [m for m in members[:10]]  # Max 10
        })
    
    # Genera URL per posizioni 10-15
    base_url = "https://www.neuronpedia.org/gemma-2-2b/graph"
    
    print("Generando URL per posizioni 10-15...")
    print("")
    
    results = {}
    
    for pos in range(10, 16):
        # Costruisci supernodes con questa posizione
        supernodes_data = []
        pinned_ids = []
        
        for sn in supernodes_template:
            member_strs = []
            for member in sn['members']:
                layer, feature = member.split('_')
                member_str = f"{layer}_{feature}_{pos}"
                member_strs.append(member_str)
                pinned_ids.append(member_str)
            
            supernodes_data.append([sn['name']] + member_strs)
        
        # Costruisci URL
        params = {
            'slug': f'circuit-tracer-pos{pos}',
            'supernodes': json.dumps(supernodes_data),
            'pinnedIds': ','.join(pinned_ids),
            'pruningThreshold': '0.6',
            'densityThreshold': '0.99'
        }
        
        query_string = urllib.parse.urlencode(params, safe='[],"')
        full_url = f"{base_url}?{query_string}"
        
        results[pos] = full_url
        
        # Salva
        filename = f"output/neuronpedia_url_pos{pos}.txt"
        with open(filename, 'w', encoding='utf-8') as f:
            f.write(full_url)
        
        print(f"✓ pos={pos}: {len(full_url)} caratteri → {filename}")
    
    print("")
    print("=" * 70)
    print("TEST PROGRESSIVO")
    print("=" * 70)
    print("")
    print("Basandoci sui tuoi test precedenti:")
    print("")
    print("  pos 7  → 0 supernodi")
    print("  pos 8  → 1 supernodo")
    print("  pos 9  → 1 supernodo")
    print("  pos 10 → 2 supernodi ✓ (quasi completo!)")
    print("")
    print("PROVA QUESTI IN ORDINE:")
    print("")
    print("  1. output/neuronpedia_url_pos11.txt  ← PIÙ PROBABILE")
    print("  2. output/neuronpedia_url_pos12.txt")
    print("  3. output/neuronpedia_url_pos13.txt")
    print("")
    print("Uno di questi dovrebbe mostrare TUTTI e 3 i supernodi.")
    print("")
    print("=" * 70)
    print("")
    
    # Crea anche un file di riferimento
    with open("output/neuronpedia_position_test_log.txt", 'w', encoding='utf-8') as f:
        f.write("NEURONPEDIA POSITION TEST LOG\n")
        f.write("=" * 70 + "\n\n")
        f.write("Test Results:\n\n")
        f.write("pos 7  → 0 supernodi\n")
        f.write("pos 8  → 1 supernodo  (Capital_L0-15 con 1 feature)\n")
        f.write("pos 9  → 1 supernodo  (Capital_L15-18 con 2 feature)\n")
        f.write("pos 10 → 2 supernodi (Capital_L15-18 + Capital_L13-16)\n")
        f.write("\nExpected: 3 supernodi totali\n")
        f.write("  - Capital_L0-15 (10 feature)\n")
        f.write("  - Capital_L13-16 (7 feature)\n")
        f.write("  - Capital_L15-18 (10 feature)\n\n")
        f.write("TO TEST:\n")
        for pos in range(11, 16):
            f.write(f"  [ ] pos {pos}: output/neuronpedia_url_pos{pos}.txt\n")
        f.write("\n")
        f.write("Fill in results and mark which position shows all 3 supernodes.\n")
    
    print("Salvato anche: output/neuronpedia_position_test_log.txt")
    print("(per tracciare i risultati dei test)")
    print("")

if __name__ == "__main__":
    export_extended_positions()

