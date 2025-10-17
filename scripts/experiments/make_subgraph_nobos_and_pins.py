#!/usr/bin/env python3
"""
Genera un subgraph JSON senza supernodi BOS e con pin per logit + embeddings
"""
import json, sys
sys.path.insert(0, 'scripts')
from causal_utils import load_attribution_graph, _get_tokenizer

INPUT_FINAL = "output/final_anthropological_optimized.json"
INPUT_PERSON = "output/feature_personalities_corrected.json"
GRAPH_PATH   = "output/example_graph.pt"
OUT_JSON     = "output/subgraph_no_bos_pinned.json"

TARGET_LOGIT = "Austin"
PIN_EMB_TOKENS = ["Dallas", "capital", "state"]

def norm(s): 
    return (s or "").replace("Ġ"," ").strip().lower()

def main():
    print("🔧 Generazione subgraph no-BOS con pin logit+embeddings")
    print("=" * 60)
    
    results = json.load(open(INPUT_FINAL,'r',encoding='utf-8'))
    personalities = json.load(open(INPUT_PERSON,'r',encoding='utf-8'))

    # 1) filtra cicciotti no-BOS (maggioranza BOS → scarta)
    def is_bos_supernode(sn):
        members = sn.get('members', [])
        bos = sum(1 for m in members if personalities.get(m,{}).get('most_common_peak') == '<BOS>')
        return bos > (len(members)//2)
    
    semantic_orig = results['semantic_supernodes']
    semantic = {k:v for k,v in semantic_orig.items() if not is_bos_supernode(v)}
    computational = results['computational_supernodes']
    
    print(f"✅ Supernodi semantici: {len(semantic_orig)} → {len(semantic)} (no-BOS)")
    print(f"✅ Supernodi computazionali: {len(computational)}")

    # 2) pinned feature set
    pinned_features = set()
    for sn in semantic.values(): 
        pinned_features.update(sn.get('members',[]))
    for sn in computational.values(): 
        pinned_features.update(sn.get('members',[]))
    
    print(f"✅ Feature pinnate: {len(pinned_features)}")

    # 3) pin logit+emb
    g = load_attribution_graph(GRAPH_PATH)
    tok = _get_tokenizer(g['cfg'])
    
    # logit idx
    logit_idx = None
    for i, t in enumerate(g['logit_tokens']):
        try:
            dec = tok.decode([t]) if tok else str(t)
            if norm(dec) == norm(TARGET_LOGIT):
                logit_idx = i
                print(f"✅ Logit '{TARGET_LOGIT}' trovato all'indice {i}")
                break
        except Exception:
            continue
    
    if logit_idx is None:
        logit_idx = 0
        print(f"⚠️ Logit '{TARGET_LOGIT}' non trovato, uso indice 0")
    
    # emb pos
    pin_emb = []
    want = {norm(w) for w in PIN_EMB_TOKENS}
    for pos, t in enumerate(g['input_tokens']):
        try:
            dec = tok.decode([t]) if tok else str(t)
            if norm(dec) in want:
                pin_emb.append(pos)
                print(f"✅ Embedding '{dec.strip()}' trovato alla posizione {pos}")
        except Exception:
            continue
    
    print(f"✅ Embeddings pinnati: {len(pin_emb)}")

    payload = {
        "semantic_supernodes": semantic,
        "computational_supernodes": computational,
        "pins": {
            "pinned_features": sorted(pinned_features),
            "pinned_logits": [logit_idx],
            "pinned_embeddings": pin_emb
        },
        "meta": {
            "sourceSetSlug": "gemmascope-transcoder-16k",
            "sourceSetName": "GEMMASCOPE - TRANSCODER -16K",
            "description": "Subgraph no-BOS with pinned logit and embeddings"
        }
    }
    
    with open(OUT_JSON,'w',encoding='utf-8') as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    
    print(f"\n✅ Salvato: {OUT_JSON}")

if __name__=="__main__":
    main()
