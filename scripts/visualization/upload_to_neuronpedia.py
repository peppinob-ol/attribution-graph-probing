#!/usr/bin/env python3
"""
Upload grafo con supernodi su Neuronpedia via API

Uso:
    python scripts/visualization/upload_to_neuronpedia.py
    python scripts/visualization/upload_to_neuronpedia.py output/subgraph_no_bos_pinned.json
"""

import sys
import os
import argparse
import json
from datetime import datetime
from pathlib import Path

# Carica variabili d'ambiente dal file .env
try:
    from dotenv import load_dotenv
    # Cerca il file .env nella root del progetto
    env_path = Path(__file__).parent.parent.parent / '.env'
    print(f"[DEBUG] Cerco .env in: {env_path.absolute()}")
    print(f"[DEBUG] File esiste: {env_path.exists()}")
    load_dotenv(dotenv_path=env_path)
    print(f"[DEBUG] .env caricato. NEURONPEDIA_API_KEY presente: {os.getenv('NEURONPEDIA_API_KEY') is not None}")
except ImportError:
    print("[!] Installa python-dotenv:")
    print("    pip install python-dotenv")
    sys.exit(1)

try:
    from neuronpedia.np_graph_metadata import NPGraphMetadata
except ImportError:
    print("[!] Installa neuronpedia prima:")
    print("    pip install neuronpedia")
    sys.exit(1)


def upload_graph(json_path='output/neuronpedia_graph_with_subgraph.json'):
    """Upload del grafo su Neuronpedia"""
    # Genera timestamp per identificazione
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    
    print("=" * 70)
    print("UPLOAD NEURONPEDIA - Pipeline Antropologica")
    print("=" * 70)
    print(f"\n[i] Timestamp upload: {timestamp}")
    
    # Verifica che il file esista
    if not os.path.exists(json_path):
        print(f"\n[❌ ERRORE] File non trovato: {json_path}")
        print(f"\n📝 SOLUZIONE:")
        print(f"   Esegui prima:")
        print(f"   python scripts/visualization/fix_neuronpedia_export.py")
        return None
    
    # Verifica che la chiave API sia disponibile
    api_key = os.getenv('NEURONPEDIA_API_KEY')
    if not api_key:
        print("\n[ERRORE] NEURONPEDIA_API_KEY non trovata!")
        print("\nAssicurati di avere un file .env nella root del progetto con:")
        print("NEURONPEDIA_API_KEY=tua_chiave_api")
        return None
    
    print(f"\n[✓] Chiave API caricata")
    print(f"\n[1/2] Upload del file {json_path}...")
    print("[i] Questo può richiedere alcuni minuti per file grandi...")
    
    try:
        graph = NPGraphMetadata.upload_file(json_path)
        
        print(f"\n[OK] Upload completato!")
        print(f"\n{'=' * 70}")
        print("RISULTATO")
        print("=" * 70)
        print(f"\nTimestamp: {timestamp}")
        print(f"URL del grafo:")
        print(f"  {graph.url}")
        print(f"\n[i] L'URL contiene un UUID generato automaticamente da Neuronpedia")
        print(f"[i] Usa il timestamp sopra per identificare questo upload")
        print(f"[i] Apri l'URL nel browser per visualizzare il grafo con i supernodi")
        
        # Salva log con timestamp e URL
        log_file = Path('output/neuronpedia_uploads.log')
        log_entry = {
            'timestamp': timestamp,
            'datetime': datetime.now().isoformat(),
            'url': graph.url,
            'file': json_path
        }
        
        # Leggi log esistente o crea nuovo
        logs = []
        if log_file.exists():
            try:
                with open(log_file, 'r', encoding='utf-8') as f:
                    logs = json.load(f)
            except:
                logs = []
        
        logs.append(log_entry)
        
        # Salva log aggiornato
        with open(log_file, 'w', encoding='utf-8') as f:
            json.dump(logs, f, indent=2, ensure_ascii=False)
        
        print(f"\n[i] Log salvato in: {log_file}")
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
    parser = argparse.ArgumentParser(
        description='Upload grafo con supernodi su Neuronpedia',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  # Upload del grafo di default
  python scripts/visualization/upload_to_neuronpedia.py
  
  # Upload del subgraph no-BOS
  python scripts/visualization/upload_to_neuronpedia.py output/subgraph_no_bos_pinned.json
  
  # Upload di un altro file
  python scripts/visualization/upload_to_neuronpedia.py output/mio_grafo.json
        """
    )
    parser.add_argument(
        'json_path',
        nargs='?',
        default='output/neuronpedia_graph_with_subgraph.json',
        help='Path al file JSON da uploadare (default: output/neuronpedia_graph_with_subgraph.json)'
    )
    
    args = parser.parse_args()
    
    url = upload_graph(args.json_path)
    if not url:
        sys.exit(1)

