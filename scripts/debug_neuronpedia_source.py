#!/usr/bin/env python3
"""
Script diagnostico per identificare il formato corretto del source per Neuronpedia API.

Uso:
    python scripts/debug_neuronpedia_source.py path/to/graph.json
    
Questo script:
1. Analizza il graph JSON
2. Identifica il formato source corretto dai nodi
3. Testa una chiamata API di esempio
4. Fornisce raccomandazioni
"""

import sys
import json
from pathlib import Path
import os

# Setup path
parent_dir = Path(__file__).parent.parent
sys.path.insert(0, str(parent_dir))

from dotenv import load_dotenv
load_dotenv()


def analyze_graph_source_format(graph_json: dict):
    """Analizza il graph JSON per determinare il formato source corretto"""
    
    print("\n" + "="*70)
    print("ANALISI GRAPH JSON - SOURCE FORMAT")
    print("="*70)
    
    # Metadata
    metadata = graph_json.get("metadata", {})
    model_id = metadata.get("scan")
    prompt = metadata.get("prompt", "")
    info = metadata.get("info", {})
    
    print(f"\n[METADATA]")
    print(f"  Model ID: {model_id}")
    print(f"  Prompt: '{prompt[:80]}...'")
    print(f"  Info keys: {list(info.keys())}")
    
    if info:
        print(f"\n[INFO CONTENUTO]")
        for key, value in info.items():
            print(f"  {key}: {value}")
    
    # Analizza nodi
    nodes = graph_json.get("nodes", [])
    feature_nodes = [n for n in nodes if n.get("feature_type") == "cross layer transcoder"]
    
    print(f"\n[NODI NEL GRAPH]")
    print(f"  Totale nodi: {len(nodes)}")
    print(f"  Feature nodes: {len(feature_nodes)}")
    
    if not feature_nodes:
        print("\n[WARNING] NESSUN FEATURE NODE TROVATO!")
        return None, None
    
    # Ispeziona primo feature node in dettaglio
    first_node = feature_nodes[0]
    print(f"\n[PRIMO FEATURE NODE - esempio]")
    for key, value in first_node.items():
        if isinstance(value, (int, float, str, bool)):
            print(f"  {key}: {value}")
    
    # Cerca indizi sul source format
    source_candidates = []
    
    # Opzione 1: Campo "modelId" nel nodo
    if "modelId" in first_node:
        source_candidates.append(("node.modelId", first_node["modelId"]))
    
    # Opzione 2: Campo "source" nel nodo
    if "source" in first_node:
        source_candidates.append(("node.source", first_node["source"]))
    
    # Opzione 3: Ricostruzione da metadata
    transcoder_set = info.get("transcoder_set", "gemmascope")
    layer = first_node.get("layer", 0)
    
    # Prova vari formati comuni
    formats = [
        f"{layer}-{transcoder_set}-res-16k",
        f"{layer}-{transcoder_set}-transcoder-16k",
        f"{transcoder_set}-res-16k",
        f"{transcoder_set}-transcoder-16k",
    ]
    
    for fmt in formats:
        source_candidates.append(("inferred", fmt))
    
    print(f"\n[SOURCE FORMAT CANDIDATI]")
    for i, (origin, candidate) in enumerate(source_candidates, 1):
        print(f"  {i}. [{origin}] {candidate}")
    
    # Estrai template (senza layer prefix)
    if source_candidates:
        best_candidate = source_candidates[0][1]
        
        # Se il candidato include il layer, rimuovilo per ottenere il template
        if best_candidate.startswith(f"{layer}-"):
            template = best_candidate[len(f"{layer}-"):]
        else:
            template = best_candidate
        
        print(f"\n[RACCOMANDAZIONE]")
        print(f"  Source template: {template}")
        print(f"  Esempio completo (layer {layer}): {layer}-{template}")
        
        return template, model_id
    
    return None, model_id


def test_api_call(model_id: str, source_template: str, test_layer: int = 6, test_feature: int = 0):
    """Testa una chiamata API con il source format"""
    
    print("\n" + "="*70)
    print("TEST API CALL")
    print("="*70)
    
    api_key = os.environ.get("NEURONPEDIA_API_KEY")
    
    if not api_key:
        print("\n[WARNING] API Key Neuronpedia non trovata in .env")
        print("   Skippo test API")
        return
    
    import requests
    
    source = f"{test_layer}-{source_template}"
    
    print(f"\n[TEST PARAMETERS]")
    print(f"  Model ID: {model_id}")
    print(f"  Source: {source}")
    print(f"  Feature: {test_feature}")
    print(f"  Custom text: 'Hello world'")
    
    endpoint = "https://www.neuronpedia.org/api/activation/new"
    payload = {
        "feature": {
            "modelId": model_id,
            "source": source,
            "index": str(test_feature)
        },
        "customText": "Hello world"
    }
    
    print(f"\n[REQUEST]")
    print(f"  POST {endpoint}")
    print(f"  Payload: {json.dumps(payload, indent=2)}")
    
    try:
        headers = {
            "Content-Type": "application/json",
            "x-api-key": api_key
        }
        
        response = requests.post(endpoint, json=payload, headers=headers, timeout=10)
        
        print(f"\n[RESPONSE]")
        print(f"  Status: {response.status_code}")
        
        if response.status_code == 200:
            data = response.json()
            print(f"  [SUCCESS] API call works!")
            print(f"  Tokens received: {len(data.get('tokens', []))}")
            print(f"  Activations received: {len(data.get('activations', {}).get('values', []))}")
        else:
            print(f"  [ERROR] {response.status_code}")
            print(f"  Response: {response.text[:200]}")
            
            if response.status_code == 500:
                print(f"\n[SUGGERIMENTI]")
                print(f"  - Il source format potrebbe essere errato")
                print(f"  - Prova varianti come:")
                print(f"    * {test_layer}-gemmascope-res-16k")
                print(f"    * {test_layer}-gemmascope-transcoder-16k")
                print(f"  - Verifica che la feature {test_feature} esista")
            
    except Exception as e:
        print(f"\n[EXCEPTION] {e}")


def main():
    if len(sys.argv) < 2:
        print("Uso: python scripts/debug_neuronpedia_source.py path/to/graph.json")
        sys.exit(1)
    
    graph_path = Path(sys.argv[1])
    
    if not graph_path.exists():
        print(f"[ERROR] File non trovato: {graph_path}")
        sys.exit(1)
    
    print(f"\n[LOADING] Caricamento graph: {graph_path}")
    
    with open(graph_path, 'r', encoding='utf-8') as f:
        graph_json = json.load(f)
    
    # Analizza
    source_template, model_id = analyze_graph_source_format(graph_json)
    
    if source_template and model_id:
        # Test API
        test_api_call(model_id, source_template)
    else:
        print("\n[WARNING] Non e' stato possibile determinare il source format")
    
    print("\n" + "="*70)
    print("FINE DIAGNOSTICA")
    print("="*70)


if __name__ == "__main__":
    main()

