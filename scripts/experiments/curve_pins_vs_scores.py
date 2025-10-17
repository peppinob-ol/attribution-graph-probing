#!/usr/bin/env python3
"""
Curva #supernodi pinnati → Replacement/Completeness scores
Trova il punto di "ginocchio" ottimale
"""
import json, sys, csv
sys.path.insert(0,'scripts')
from causal_utils import load_attribution_graph, _get_tokenizer

FINAL = "output/final_anthropological_optimized.json"
PERSON = "output/feature_personalities_corrected.json"
GRAPH = "output/example_graph.pt"
OUT   = "output/pins_vs_scores.csv"

TARGET_LOGIT = "Austin"
PIN_EMB_TOKENS = ["Dallas","capital","state"]

def try_import_scores():
    try:
        from circuit_tracer.metrics import compute_graph_scores
        return compute_graph_scores
    except Exception:
        return None

def norm(s):
    return (s or "").replace("Ġ"," ").strip().lower()

def main():
    print("📈 Curva #supernodi → Replacement/Completeness scores")
    print("=" * 60)
    
    scorer = try_import_scores()
    if scorer is None:
        print("⚠️ compute_graph_scores non disponibile (pip install circuit-tracer)")
        print("   Installa circuit-tracer per calcolare i punteggi")
        return

    results = json.load(open(FINAL,'r',encoding='utf-8'))
    pers = json.load(open(PERSON,'r',encoding='utf-8'))
    
    print("📥 Caricamento Attribution Graph...")
    g = load_attribution_graph(GRAPH)
    tok = _get_tokenizer(g['cfg'])

    def sn_score(sn):
        """Score basato su somma |node_influence| dei membri"""
        return sum(abs(pers.get(m,{}).get('node_influence',0)) for m in sn.get('members',[]) if m in pers)

    semantics = list(results['semantic_supernodes'].items())
    semantics.sort(key=lambda kv: sn_score(kv[1]), reverse=True)
    
    print(f"📊 Ordinati {len(semantics)} supernodi semantici per node_influence")

    # logit idx
    logit_idx = None
    for i,t in enumerate(g['logit_tokens']):
        try:
            dec = tok.decode([t]) if tok else str(t)
            if norm(dec) == norm(TARGET_LOGIT):
                logit_idx=i
                break
        except Exception:
            continue
    if logit_idx is None:
        logit_idx = 0

    # embeddings pos
    want = {norm(x) for x in PIN_EMB_TOKENS}
    pin_emb=[]
    for pos,t in enumerate(g['input_tokens']):
        try:
            dec = tok.decode([t]) if tok else str(t)
            if norm(dec) in want:
                pin_emb.append(pos)
        except Exception:
            continue
    
    print(f"✅ Logit index: {logit_idx}, Embeddings positions: {pin_emb}")
    print("\n🔄 Calcolo scores per K crescente...")

    rows=[["K","graph_repl","graph_comp","subgraph_repl","subgraph_comp"]]
    
    for K in range(2, min(30,len(semantics))+1):
        pinned=set()
        for sid,sn in semantics[:K]:
            pinned.update(sn.get('members',[]))
        
        try:
            scores = scorer(g, 
                          pinned_features=list(pinned), 
                          pinned_logits=[logit_idx], 
                          pinned_embeddings=pin_emb)
            
            rows.append([
                K,
                f"{scores['graph']['replacement']:.4f}",
                f"{scores['graph']['completeness']:.4f}",
                f"{scores['subgraph']['replacement']:.4f}",
                f"{scores['subgraph']['completeness']:.4f}"
            ])
            
            if K % 5 == 0:
                print(f"   K={K}: Sub R={scores['subgraph']['replacement']:.4f}, C={scores['subgraph']['completeness']:.4f}")
        
        except Exception as e:
            print(f"   ⚠️ Errore per K={K}: {e}")
            continue

    with open(OUT,'w',newline='',encoding='utf-8') as f:
        csv.writer(f).writerows(rows)
    
    print(f"\n✅ Salvato: {OUT}")
    print("📊 Importa il CSV in Excel/Python per visualizzare la curva")

if __name__=="__main__":
    main()
