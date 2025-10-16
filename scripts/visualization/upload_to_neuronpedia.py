#!/usr/bin/env python3
"""
Upload grafo con supernodi su Neuronpedia via API
"""

import sys

try:
    from neuronpedia.np_graph_metadata import NPGraphMetadata
except ImportError:
    print("[!] Installa neuronpedia prima:")
    print("    pip install neuronpedia")
    sys.exit(1)


def upload_graph(json_path='output/neuronpedia_graph_with_subgraph.json'):
    """Upload del grafo su Neuronpedia"""
    print("=" * 70)
    print("UPLOAD NEURONPEDIA")
    print("=" * 70)
    print(f"\n[1/2] Upload del file {json_path}...")
    print("[i] Questo può richiedere alcuni minuti per file grandi...")
    
    try:
        graph = NPGraphMetadata.upload_file(json_path)
        
        print(f"\n[OK] Upload completato!")
        print(f"\n{'=' * 70}")
        print("RISULTATO")
        print("=" * 70)
        print(f"\nURL del grafo:")
        print(f"  {graph.url}")
        print(f"\n[i] Apri l'URL nel browser per visualizzare il grafo con i supernodi")
        print("=" * 70)
        
        return graph.url
        
    except Exception as e:
        print(f"\n[ERRORE] Upload fallito: {e}")
        print(f"\n[SOLUZIONI]")
        print("1. Verifica di essere autenticato su Neuronpedia")
        print("2. Controlla che il JSON sia valido")
        print("3. Prova a ridurre la dimensione del grafo (threshold più alti)")
        return None


if __name__ == "__main__":
    url = upload_graph()
    if not url:
        sys.exit(1)

