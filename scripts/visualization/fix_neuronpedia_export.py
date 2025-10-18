#!/usr/bin/env python3
"""
Fix per export Neuronpedia: gestisce Cantor pairing e formati alternativi
"""

import json
import os
import uuid


def cantor_unpair(z):
    """Inverte il Cantor pairing: z -> (layer, feature)"""
    w = int(((-1 + (1 + 8*z)**0.5) / 2))
    t = (w * w + w) / 2
    y = int(z - t)
    x = int(w - y)
    return x, y


def cantor_pair(x, y):
    """Cantor pairing: (layer, feature) -> z"""
    return int((x + y) * (x + y + 1) / 2 + y)


def fix_export(
    input_json='output/graph_data/anthropological-circuit.json',
    supernodes_file='output/final_anthropological_optimized.json',
    output_json='output/neuronpedia_graph_with_subgraph.json'
):
    """
    Prepara export Neuronpedia con supernodi dalla pipeline antropologica.
    
    Input:
        - Graph JSON base (da circuit-tracer create_graph_files)
        - Supernodi dalla pipeline (01→02→03→04)
    
    Output:
        - neuronpedia_graph_with_subgraph.json con qParams.supernodes
    """
    print("=" * 70)
    print("NEURONPEDIA EXPORT - Pipeline Antropologica")
    print("=" * 70)
    
    # Verifica che il grafo base esista
    if not os.path.exists(input_json):
        print(f"\n⚠️  ERRORE: Graph JSON base non trovato: {input_json}")
        print(f"\n📝 SOLUZIONE:")
        print(f"   1. Genera il Graph JSON base usando circuit-tracer:")
        print(f"      from circuit_tracer.utils.create_graph_files import create_graph_files")
        print(f"      create_graph_files(")
        print(f"          graph_or_path='output/example_graph.pt',")
        print(f"          slug='anthropological-circuit',")
        print(f"          output_path='output/graph_data',")
        print(f"          scan='gemma-2-2b',")
        print(f"          node_threshold=0.8,")
        print(f"          edge_threshold=0.98")
        print(f"      )")
        print(f"\n   2. Oppure genera su Colab e copia il file qui")
        return None
    
    # Carica il grafo
    print(f"\n[1/3] Caricamento grafo da {input_json}...")
    with open(input_json, 'r', encoding='utf-8') as f:
        graph = json.load(f)
    
    nodes = graph.get('nodes', [])
    metadata = graph.get('metadata', {})
    qparams = graph.get('qParams', {}) or {}
    
    # Aggiungi UUID allo slug per renderlo unico
    unique_id = str(uuid.uuid4())[:8]  # Primi 8 caratteri del UUID
    original_slug = metadata.get('slug', 'graph')
    new_slug = f"{original_slug}-{unique_id}"
    metadata['slug'] = new_slug
    
    # Aggiungi/verifica info.source_urls (formato compatibile con API Neuronpedia)
    if 'info' not in metadata:
        metadata['info'] = {}
    
    info = metadata['info']
    if 'source_urls' not in info or not info['source_urls']:
        info['source_urls'] = [
            "https://neuronpedia.org/gemma-2-2b/gemmascope-transcoder-16k",
            "https://huggingface.co/google/gemma-scope-2b-pt-transcoders"
        ]
        print(f"[+] Aggiunti source_urls in metadata.info")
    
    if 'transcoder_set' not in info:
        info['transcoder_set'] = 'gemma'
        print(f"[+] Aggiunto transcoder_set in metadata.info")
    
    # Aggiungi anche sourceSetSlug/Name per compatibilità (alcuni validator li usano)
    if 'sourceSetSlug' not in metadata:
        metadata['sourceSetSlug'] = 'gemmascope-transcoder-16k'
    if 'sourceSetName' not in metadata:
        metadata['sourceSetName'] = 'GEMMASCOPE - TRANSCODER -16K'
    
    print(f"[OK] Nodi: {len(nodes)}, Links: {len(graph.get('links', []))}")
    print(f"[i] Slug unico generato: {new_slug}")
    print(f"[i] Source Set: {metadata.get('sourceSetName', 'N/A')}")
    print(f"[i] Source URLs: {len(info.get('source_urls', []))} URL")
    
    # Carica supernodi
    print(f"\n[2/3] Caricamento supernodi da {supernodes_file}...")
    with open(supernodes_file, 'r', encoding='utf-8') as f:
        supernodes_data = json.load(f)
    
    # Analizza formato dei nodi
    sample_node = nodes[0] if nodes else {}
    feature_val = sample_node.get('feature')
    layer_val = sample_node.get('layer')
    
    print(f"\n[DEBUG] Sample node:")
    print(f"  node_id: {sample_node.get('node_id')}")
    print(f"  feature: {feature_val} (type: {type(feature_val).__name__})")
    print(f"  layer: {layer_val} (type: {type(layer_val).__name__})")
    
    # Determina se usa Cantor pairing
    uses_cantor = False
    if feature_val and layer_val:
        try:
            l = int(layer_val)
            f_raw = int(feature_val)
            # Se feature è molto più grande di quanto ci si aspetta per un layer basso, è Cantor
            expected_cantor = cantor_pair(l, 41)  # esempio dal sample
            if abs(f_raw - expected_cantor) < 10:  # tolleranza
                uses_cantor = True
                print(f"\n[i] Rilevato Cantor pairing: feature={f_raw} ≈ cantor({l}, 41)={expected_cantor}")
        except:
            pass
    
    # Crea indice
    print(f"\n[3/3] Creazione indice nodi...")
    if uses_cantor:
        print("[i] Modalità: Cantor pairing - node feature è cantor(layer, feat_idx)")
        # Decodifica Cantor per creare l'indice
        lf_index = {}
        for node in nodes:
            try:
                layer = int(node.get('layer', -1))
                cantor_feat = int(node.get('feature', -1))
                if layer >= 0 and cantor_feat >= 0:
                    # Unpair per ottenere il vero feature index
                    l_decoded, f_decoded = cantor_unpair(cantor_feat)
                    # Se il layer decodificato corrisponde, usa feature decodificata
                    if l_decoded == layer:
                        node_id = node.get('node_id') or node.get('nodeId') or node.get('jsNodeId')
                        ctx_idx = int(node.get('ctx_idx', -1))
                        if node_id and ctx_idx >= 0:
                            lf_index.setdefault((layer, f_decoded), []).append((node_id, ctx_idx))
            except Exception as e:
                continue
        print(f"[OK] Indicizzati {len(lf_index)} (layer, feature) pairs con Cantor unpair")
    else:
        print("[i] Modalità: Standard - feature è l'indice diretto")
        lf_index = {}
        for node in nodes:
            try:
                layer = int(node.get('layer', -1))
                feature = int(node.get('feature', -1))
                if layer >= 0 and feature >= 0:
                    node_id = node.get('node_id') or node.get('nodeId') or node.get('jsNodeId')
                    ctx_idx = int(node.get('ctx_idx', -1))
                    if node_id and ctx_idx >= 0:
                        lf_index.setdefault((layer, feature), []).append((node_id, ctx_idx))
            except:
                continue
        print(f"[OK] Indicizzati {len(lf_index)} (layer, feature) pairs standard")
    
    # Calcola ctx_idx preferito
    prefer_ctx = None
    try:
        prompt_tokens = metadata.get('prompt_tokens', [])
        if prompt_tokens:
            prefer_ctx = len(prompt_tokens) - 1
            print(f"[i] Preferenza ctx_idx: {prefer_ctx} (ultima posizione prompt)")
    except:
        pass
    
    # Costruisci supernodes
    supernodes_out = []
    pinned_ids = []
    
    # ===== PINNA TUTTI GLI EMBEDDINGS (NON in supernodi) =====
    print(f"\n[EMBEDDINGS] Identificazione e pinning embeddings...")
    embedding_nodes = []
    for node in nodes:
        layer = node.get('layer')
        # Gli embeddings hanno layer='E' oppure node_id che inizia con 'E_'
        node_id = node.get('node_id') or node.get('nodeId') or node.get('jsNodeId')
        if layer == 'E' or (isinstance(node_id, str) and node_id.startswith('E_')):
            if node_id:
                embedding_nodes.append(node_id)
                pinned_ids.append(node_id)
    
    print(f"[OK] Pinnati {len(embedding_nodes)} embeddings (NON in supernodi)")
    
    # ===== PINNA OUTPUT LOGIT =====
    print(f"\n[OUTPUT] Identificazione e pinning output logit...")
    logit_nodes = []
    for node in nodes:
        # I logit hanno is_target_logit=True o isTargetLogit=True
        if node.get('is_target_logit') or node.get('isTargetLogit'):
            node_id = node.get('node_id') or node.get('nodeId') or node.get('jsNodeId')
            if node_id:
                logit_nodes.append(node_id)
                pinned_ids.append(node_id)
    
    print(f"[OK] Pinnati {len(logit_nodes)} nodi logit")
    
    # ===== SUPERNODI DA FEATURES =====
    print(f"\n[SUPERNODI] Costruzione supernodi da features...")
    
    # Semantici
    semantic = supernodes_data.get('semantic_supernodes', {})
    for sid, sn in semantic.items():
        theme = sn.get('narrative_theme', sid)
        members = sn.get('members', [])
        
        layers = []
        for m in members:
            try:
                l, f = m.split('_')
                layers.append(int(l))
            except:
                pass
        
        if layers:
            min_l, max_l = min(layers), max(layers)
            name = f"{theme}_L{min_l}" if min_l == max_l else f"{theme}_L{min_l}-{max_l}"
        else:
            name = theme
        
        node_ids = []
        for m in members:
            try:
                l, f = m.split('_')
                l_int, f_int = int(l), int(f)
                cands = lf_index.get((l_int, f_int), [])
                
                if cands:
                    nid = None
                    if prefer_ctx is not None:
                        for n, c in cands:
                            if c == prefer_ctx:
                                nid = n
                                break
                    if not nid:
                        nid = cands[0][0]
                    node_ids.append(nid)
                    pinned_ids.append(nid)
                else:
                    # Debug: prova a trovare con varianti
                    print(f"[!] Non trovato mapping per {m} (layer={l_int}, feat={f_int})")
            except Exception as e:
                print(f"[!] Errore parsing membro {m}: {e}")
                continue
        
        if node_ids:
            supernodes_out.append([name] + node_ids)
            print(f"  + {name}: {len(node_ids)} feature")
    
    # Computazionali
    computational = supernodes_data.get('computational_supernodes', {})
    for sid, sn in computational.items():
        token = sn.get('dominant_token', 'comp')
        avg_layer = sn.get('avg_layer', 0)
        n_members = sn.get('n_members', 0)
        name = f"{token}_L{int(avg_layer)}_n{n_members}"
        
        node_ids = []
        for m in sn.get('members', []):
            try:
                l, f = m.split('_')
                l_int, f_int = int(l), int(f)
                cands = lf_index.get((l_int, f_int), [])
                
                if cands:
                    nid = None
                    if prefer_ctx is not None:
                        for n, c in cands:
                            if c == prefer_ctx:
                                nid = n
                                break
                    if not nid:
                        nid = cands[0][0]
                    node_ids.append(nid)
                    pinned_ids.append(nid)
            except:
                continue
        
        if node_ids:
            supernodes_out.append([name] + node_ids)
            print(f"  + {name}: {len(node_ids)} feature")
    
    # De-duplica
    pinned_ids = list(dict.fromkeys(pinned_ids))
    
    # Aggiorna qParams
    qparams = {
        **qparams,
        'pinnedIds': pinned_ids,
        'supernodes': supernodes_out,
        'linkType': qparams.get('linkType', 'both'),
        'clickedId': pinned_ids[0] if pinned_ids else qparams.get('clickedId', ''),
        'sg_pos': qparams.get('sg_pos', ''),
    }
    
    # Aggiungi clerp
    nodeid_to_label = {}
    for sn in supernodes_out:
        if len(sn) < 2:
            continue
        label = sn[0]
        for nid in sn[1:]:
            nodeid_to_label.setdefault(nid, label)
    
    for node in nodes:
        nid = node.get('node_id') or node.get('nodeId') or node.get('jsNodeId')
        if nid and nid in nodeid_to_label and not node.get('clerp'):
            node['clerp'] = nodeid_to_label[nid]
    
    # Scrivi output
    out = {
        'metadata': metadata,
        'qParams': qparams,
        'nodes': nodes,
        'links': graph.get('links', []),
    }
    
    with open(output_json, 'w', encoding='utf-8') as f:
        json.dump(out, f, ensure_ascii=False)
    
    print(f"\n{'=' * 70}")
    print("RISULTATO")
    print("=" * 70)
    print(f"  File: {output_json}")
    print(f"  Dimensione: {os.path.getsize(output_json) / 1024 / 1024:.1f} MB")
    print(f"\n  Nodi pinnati totali: {len(pinned_ids)}")
    print(f"    - Embeddings: {len(embedding_nodes)} (NON in supernodi)")
    print(f"    - Features in supernodi: {len([n for n in pinned_ids if n not in embedding_nodes and n not in logit_nodes])}")
    print(f"    - Output logit: {len(logit_nodes)}")
    print(f"\n  Supernodi creati: {len(supernodes_out)}")
    print(f"  Source Set: {metadata.get('sourceSetName', 'N/A')}")
    
    if not supernodes_out:
        print(f"\n[!] ATTENZIONE: Nessun supernodo aggiunto!")
        print(f"[i] Verifica che i membri in {supernodes_file} corrispondano ai nodi nel grafo")
    
    print(f"\n{'=' * 70}\n")
    
    return output_json


if __name__ == "__main__":
    print("\n📌 PREREQUISITI:")
    print("   1. Esegui la pipeline antropologica:")
    print("      python scripts/01_anthropological_basic.py")
    print("      python scripts/02_compute_thresholds.py")
    print("      python scripts/03_cicciotti_supernodes.py")
    print("      python scripts/04_final_optimized_clustering.py")
    print("   2. Genera il Graph JSON base (vedi README)")
    print("\n" + "="*70 + "\n")
    
    result = fix_export()
    if result:
        print(f"\n[✅ OK] Export completato: {result}")
        
        # Suggerimenti per upload
        print("\n" + "="*70)
        print("PROSSIMO PASSO: UPLOAD SU NEURONPEDIA")
        print("="*70)
        print("\nIl file è troppo grande per il validator UI.")
        print("\n✅ USA L'API PYTHON:")
        print("\n   python scripts/visualization/upload_to_neuronpedia.py")
        print("\nOppure manualmente:")
        print("\n   from neuronpedia.np_graph_metadata import NPGraphMetadata")
        print(f"   graph = NPGraphMetadata.upload_file('{result}')")
        print("   print(graph.url)")
    else:
        print(f"\n[❌ ERRORE] Export fallito - vedi messaggi sopra")

