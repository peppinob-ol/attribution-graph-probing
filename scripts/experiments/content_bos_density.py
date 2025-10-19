#!/usr/bin/env python3
"""
Analisi densità edge: content↔content vs BOS↔content
Capire se la connettività è sostenuta da spine causali o hub generici
"""
import json, sys
sys.path.insert(0,'scripts')
from causal_utils import load_attribution_graph, compute_edge_density

FINAL = "output/final_anthropological_optimized.json"
PERSON = "output/feature_personalities_corrected.json"
GRAPH = "output/example_graph.pt"

def main():
    print("🔗 Analisi Edge Density: content vs BOS")
    print("=" * 60)
    
    results = json.load(open(FINAL,'r',encoding='utf-8'))
    pers = json.load(open(PERSON,'r',encoding='utf-8'))
    
    g = load_attribution_graph(GRAPH)
    
    # feature_to_idx
    f2i={}
    for i,(layer,pos,feat) in enumerate(g['active_features']):
        f2i[f"{layer.item()}_{feat.item()}"] = i
    
    print("📊 Estrazione feature dai supernodi...")
    feats=set()
    for sn in results['semantic_supernodes'].values():
        feats.update(sn['members'])
    for sn in results['computational_supernodes'].values():
        feats.update(sn['members'])
    
    content=[f for f in feats if pers.get(f,{}).get('most_common_peak')!='<BOS>']
    bos=[f for f in feats if pers.get(f,{}).get('most_common_peak')=='<BOS>']
    
    print(f"✅ Feature content: {len(content)}")
    print(f"✅ Feature BOS: {len(bos)}")

    adj = g['adjacency_matrix'].abs()
    
    def density_between(A, B, tau=0.01):
        """Densità edge da A a B"""
        Ai=[f2i[a] for a in A if a in f2i]
        Bi=[f2i[b] for b in B if b in f2i]
        if not Ai or not Bi: return 0.0
        sub = adj[Bi,:][:,Ai]  # A->B (colonne A, righe B)
        strong=(sub>tau).sum().item()
        return strong/(len(Ai)*len(Bi))
    
    print("\n🔄 Calcolo densità...")
    
    cc = compute_edge_density(content,g,f2i,0.01) if content else 0.0
    bb = compute_edge_density(bos,g,f2i,0.01) if bos else 0.0
    cb = density_between(content,bos,0.01)
    bc = density_between(bos,content,0.01)
    
    print("\n📊 RISULTATI:")
    print("=" * 60)
    print(f"   content ↔ content: {cc:.3f}")
    print(f"   BOS ↔ BOS:         {bb:.3f}")
    print(f"   content → BOS:     {cb:.3f}")
    print(f"   BOS → content:     {bc:.3f}")
    
    # Interpretazione
    print("\n💡 INTERPRETAZIONE:")
    if cc > cb and cc > bc:
        print("   ✅ La densità è sostenuta da spine causali (content↔content)")
    elif cb > cc or bc > cc:
        print("   ⚠️ La densità è sostenuta da hub BOS (BOS↔content)")
    else:
        print("   📊 Densità bilanciata tra content e BOS")
    
    # Rapporto
    total_content_density = cc + cb + bc
    if total_content_density > 0:
        content_purity = cc / total_content_density * 100
        print(f"   📈 Purezza causale content: {content_purity:.1f}%")

if __name__=="__main__":
    main()


