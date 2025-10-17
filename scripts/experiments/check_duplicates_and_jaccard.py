#!/usr/bin/env python3
"""
Verifica duplicati di supernodi sullo stesso layer/pos/token
e calcola Jaccard del vicinato causale
"""
import json, sys
sys.path.insert(0, 'scripts')
from causal_utils import load_attribution_graph, compute_causal_metrics

FINAL = "output/final_anthropological_optimized.json"
PERSON = "output/feature_personalities_corrected.json"
GRAPH  = "output/example_graph.pt"
OUT    = "output/duplicate_candidates.json"

def jaccard(a,b):
    a,b=set(a),set(b)
    u=len(a|b)
    return (len(a&b)/u) if u else 0.0

def main():
    print("🔍 Verifica duplicati supernodi e Jaccard vicinato causale")
    print("=" * 60)
    
    results = json.load(open(FINAL,'r',encoding='utf-8'))
    personalities = json.load(open(PERSON,'r',encoding='utf-8'))
    
    print("📥 Caricamento Attribution Graph...")
    g = load_attribution_graph(GRAPH)
    print("📊 Calcolo metriche causali...")
    cm = compute_causal_metrics(g, tau_edge=0.01, top_k=10)

    def sn_sig(sn):
        members = sn.get('members', [])
        layers = [personalities[m]['layer'] for m in members if m in personalities]
        pos = [personalities[m].get('position', personalities[m].get('pos')) for m in members if m in personalities]
        layer = max(set(layers), key=layers.count) if layers else -1
        p = max(set(pos), key=pos.count) if pos else -1
        peaks = [personalities[m].get('most_common_peak') for m in members if m in personalities]
        token = max(set(peaks), key=peaks.count) if peaks else None
        
        # vicinato causale aggregato
        neigh = set()
        for m in members:
            if m in cm:
                neigh.update([x[0] for x in cm[m].get('top_parents',[])])
                neigh.update([x[0] for x in cm[m].get('top_children',[])])
        
        return (layer,p,token,neigh)

    all_sn = {**results['semantic_supernodes'], **results['computational_supernodes']}
    
    print(f"📊 Analizzando {len(all_sn)} supernodi...")
    
    buckets = {}
    for sid, sn in all_sn.items():
        sig = sn_sig(sn)
        key = sig[:3]  # (layer, pos, token)
        if key not in buckets:
            buckets[key] = []
        buckets[key].append((sid, sig[3]))  # (supernode_id, neighborhood)

    report = []
    duplicates_found = 0
    
    print("\n🔎 Ricerca duplicati (stesso layer/pos/token)...")
    
    for k, arr in buckets.items():
        if len(arr) < 2:
            continue
        
        layer, pos, token = k
        print(f"\n📍 Bucket: layer={layer}, pos={pos}, token='{token}' → {len(arr)} supernodi")
        
        for i in range(len(arr)):
            for j in range(i+1,len(arr)):
                s1,n1=arr[i]
                s2,n2=arr[j]
                jacc = jaccard(n1,n2)
                
                print(f"   {s1} vs {s2} → Jaccard vicinato={jacc:.3f}")
                
                report.append({
                    "key": {"layer": int(layer), "pos": int(pos), "token": token},
                    "pair": [s1, s2],
                    "neighborhood_jaccard": float(jacc)
                })
                duplicates_found += 1

    print(f"\n✅ Trovate {duplicates_found} coppie potenzialmente duplicate")
    
    with open(OUT,'w',encoding='utf-8') as f:
        json.dump(report, f, indent=2)
    
    print(f"✅ Salvato: {OUT}")

if __name__=="__main__":
    main()
