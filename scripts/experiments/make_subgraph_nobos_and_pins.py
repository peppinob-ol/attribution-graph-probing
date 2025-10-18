#!/usr/bin/env python3
"""
Genera un subgraph JSON senza supernodi BOS e con pin per logit + embeddings
"""
import json, sys, os, uuid
sys.path.insert(0, 'scripts')
from causal_utils import load_attribution_graph, _get_tokenizer

INPUT_FINAL = "output/final_anthropological_optimized.json"
INPUT_PERSON = "output/feature_personalities_corrected.json"
GRAPH_PATH   = "output/example_graph.pt"
GRAPH_JSON   = "output/graph_data/anthropological-circuit.json"
OUT_JSON     = "output/subgraph_no_bos_pinned.json"

TARGET_LOGIT = "Austin"
PIN_EMB_TOKENS = ["Dallas", "capital", "state"]

def norm(s): 
    return (s or "").replace("Ġ"," ").strip().lower()

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

def main():
    print("Generazione subgraph no-BOS con pin logit+embeddings")
    print("=" * 60)
    
    # 1) Carica dati antropologici
    results = json.load(open(INPUT_FINAL,'r',encoding='utf-8'))
    personalities = json.load(open(INPUT_PERSON,'r',encoding='utf-8'))

    # Filtra cicciotti no-BOS (maggioranza BOS → scarta)
    def is_bos_supernode(sn):
        members = sn.get('members', [])
        bos = sum(1 for m in members if personalities.get(m,{}).get('most_common_peak') == '<BOS>')
        return bos > (len(members)//2)
    
    semantic_orig = results['semantic_supernodes']
    semantic = {k:v for k,v in semantic_orig.items() if not is_bos_supernode(v)}
    
    # Filtra anche i supernodi computazionali con dominant_token = <BOS>
    computational_orig = results['computational_supernodes']
    computational = {k:v for k,v in computational_orig.items() 
                     if v.get('dominant_token', '') != '<BOS>'}
    
    print(f"[OK] Supernodi semantici: {len(semantic_orig)} -> {len(semantic)} (no-BOS)")
    print(f"[OK] Supernodi computazionali: {len(computational_orig)} -> {len(computational)} (no-BOS)")

    # 2) Carica graph JSON base (formato Neuronpedia)
    if not os.path.exists(GRAPH_JSON):
        print(f"\n[ERRORE] Graph JSON base non trovato: {GRAPH_JSON}")
        print("   Esegui prima fix_neuronpedia_export.py per generare il graph JSON base")
        sys.exit(1)
    
    with open(GRAPH_JSON, 'r', encoding='utf-8') as f:
        base_graph = json.load(f)
    
    nodes = base_graph.get('nodes', [])
    links = base_graph.get('links', [])
    metadata = base_graph.get('metadata', {})
    qparams = base_graph.get('qParams', {}) or {}
    
    print(f"[OK] Graph base caricato: {len(nodes)} nodi, {len(links)} archi")
    
    # 3) Determina se usa Cantor pairing
    sample_node = nodes[0] if nodes else {}
    feature_val = sample_node.get('feature')
    layer_val = sample_node.get('layer')
    
    uses_cantor = False
    if feature_val and layer_val:
        try:
            l = int(layer_val)
            f_raw = int(feature_val)
            # Se feature è molto più grande di quanto ci si aspetta per un layer basso, è Cantor
            expected_cantor = cantor_pair(l, 41)  # esempio dal sample
            if abs(f_raw - expected_cantor) < 10:  # tolleranza
                uses_cantor = True
                print(f"[i] Rilevato Cantor pairing: feature={f_raw} ≈ cantor({l}, 41)={expected_cantor}")
        except:
            pass
    
    # Crea indice (layer, feature) -> node_ids
    lf_index = {}
    if uses_cantor:
        print("[i] Modalità: Cantor pairing - decodifica feature per creare indice")
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
    else:
        print("[i] Modalità: Standard - feature è l'indice diretto")
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
    
    print(f"[OK] Indicizzati {len(lf_index)} (layer, feature) pairs")

    # 4) Costruisci supernodes nel formato Neuronpedia: [name, node_id1, node_id2, ...]
    supernodes_out = []
    pinned_ids = []
    
    # Preferenza ctx_idx (ultima posizione del prompt)
    prefer_ctx = None
    try:
        prompt_tokens = metadata.get('prompt_tokens', [])
        if prompt_tokens:
            prefer_ctx = len(prompt_tokens) - 1
    except:
        pass
    
    # Semantici (no-BOS già filtrati)
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
            except:
                continue
        
        if node_ids:
            supernodes_out.append([name] + node_ids)
    
    # Computazionali
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
    
    # De-duplica
    pinned_ids = list(dict.fromkeys(pinned_ids))
    
    print(f"[OK] Supernodi convertiti: {len(supernodes_out)}")
    print(f"[OK] Feature pinnate nei supernodi: {len(pinned_ids)}")
    
    # 5) Trova nodi embedding e logit da pinnare
    g = load_attribution_graph(GRAPH_PATH)
    tok = _get_tokenizer(g['cfg'])
    
    # Determina quali posizioni embedding pinnare
    pin_emb_pos = []
    want = {norm(w) for w in PIN_EMB_TOKENS}
    for pos, t in enumerate(g['input_tokens']):
        try:
            dec = tok.decode([t]) if tok else str(t)
            if norm(dec) in want:
                pin_emb_pos.append(pos)
                print(f"[OK] Embedding '{dec.strip()}' alla posizione {pos}")
        except Exception:
            continue
    
    # Trova i node_id corrispondenti agli embeddings
    emb_node_ids = []
    for node in nodes:
        if node.get('layer') == 'E' and node.get('ctx_idx') in pin_emb_pos:
            node_id = node.get('node_id') or node.get('nodeId') or node.get('jsNodeId')
            if node_id:
                emb_node_ids.append(node_id)
                pinned_ids.append(node_id)
    
    print(f"[OK] Nodi embedding pinnati: {len(emb_node_ids)}")
    
    # Trova nodi logit da pinnare (tutti i logit per sicurezza)
    logit_node_ids = []
    for node in nodes:
        if node.get('is_target_logit') == True:
            node_id = node.get('node_id') or node.get('nodeId') or node.get('jsNodeId')
            if node_id:
                logit_node_ids.append(node_id)
                pinned_ids.append(node_id)
    
    print(f"[OK] Nodi logit pinnati: {len(logit_node_ids)}")
    
    # 6) Genera slug unico
    unique_id = str(uuid.uuid4())[:8]
    original_slug = metadata.get('slug', 'graph')
    new_slug = f"{original_slug}-nobos-{unique_id}"
    metadata['slug'] = new_slug
    metadata['description'] = "Subgraph no-BOS with pinned logit and embeddings"
    
    print(f"[OK] Slug unico generato: {new_slug}")
    
    # 7) Aggiorna qParams
    qparams = {
        **qparams,
        'pinnedIds': pinned_ids,
        'supernodes': supernodes_out,
        'linkType': qparams.get('linkType', 'both'),
        'clickedId': pinned_ids[0] if pinned_ids else qparams.get('clickedId', ''),
        'sg_pos': qparams.get('sg_pos', ''),
    }
    
    # 8) Aggiungi clerp ai nodi
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
    
    # 9) Output finale nel formato Neuronpedia
    payload = {
        'metadata': metadata,
        'qParams': qparams,
        'nodes': nodes,
        'links': links
    }
    
    with open(OUT_JSON, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False)
    
    print(f"\n{'=' * 60}")
    print("RISULTATO")
    print("=" * 60)
    print(f"  File: {OUT_JSON}")
    print(f"  Dimensione: {os.path.getsize(OUT_JSON) / 1024 / 1024:.1f} MB")
    print(f"  Supernodi: {len(supernodes_out)} (no-BOS)")
    print(f"  Nodi pinnati totali: {len(pinned_ids)}")
    print(f"    - Feature supernodi: {len(pinned_ids) - len(emb_node_ids) - len(logit_node_ids)}")
    print(f"    - Nodi logit: {len(logit_node_ids)}")
    print(f"    - Nodi embedding: {len(emb_node_ids)} (posizioni: {pin_emb_pos})")
    print(f"\n[OK] Pronto per upload su Neuronpedia!")
    print(f"   python scripts/visualization/upload_to_neuronpedia.py {OUT_JSON}")
    print("=" * 60)

if __name__=="__main__":
    main()
