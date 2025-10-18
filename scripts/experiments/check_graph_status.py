#!/usr/bin/env python3
"""
Verifica lo stato di un grafo su Neuronpedia e attende che sia disponibile.

Uso:
    python scripts/experiments/check_graph_status.py gemma-2-2b test-graph-fox-20251018-225552
    
    Oppure con attesa automatica:
    python scripts/experiments/check_graph_status.py gemma-2-2b test-graph-fox-20251018-225552 --wait
"""
import sys
import os
import time
import argparse

try:
    import requests
except ImportError:
    print("[ERRORE] Modulo 'requests' non trovato. Installa con: pip install requests")
    sys.exit(1)

# ===== CONFIGURAZIONE =====

def load_api_key() -> str:
    """Carica API key da .env o variabile d'ambiente"""
    # Prima prova con variabile d'ambiente
    api_key = os.environ.get('NEURONPEDIA_API_KEY')
    if api_key:
        return api_key
    
    # Poi cerca nel file .env
    env_path = os.path.join(os.path.dirname(__file__), '..', '..', '.env')
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('NEURONPEDIA_API_KEY='):
                        key = line.split('=', 1)[1].strip()
                        key = key.strip('"').strip("'")
                        if key:
                            return key
        except Exception as e:
            print(f"[ATTENZIONE] Errore leggendo .env: {e}")
    
    print("[ERRORE] API key non trovata in .env o variabili d'ambiente.")
    sys.exit(1)

API_KEY = load_api_key()
API_BASE = "https://www.neuronpedia.org/api"

# ===== FUNZIONI =====

def check_graph_status(model_id: str, slug: str) -> dict:
    """Verifica lo stato del grafo"""
    url = f"{API_BASE}/graph/{model_id}/{slug}"
    
    try:
        response = requests.get(
            url,
            headers={"x-api-key": API_KEY},
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                'available': True,
                'data': data,
                'status_code': 200
            }
        else:
            return {
                'available': False,
                'status_code': response.status_code,
                'message': response.text[:200]
            }
    except requests.exceptions.RequestException as e:
        return {
            'available': False,
            'error': str(e)
        }

def wait_for_graph(model_id: str, slug: str, max_wait: int = 300, 
                  check_interval: int = 10) -> bool:
    """Attende che il grafo sia disponibile"""
    print(f"Attendo che il grafo sia disponibile...")
    print(f"  Max attesa: {max_wait}s, check ogni: {check_interval}s")
    print()
    
    start = time.time()
    attempt = 0
    
    while time.time() - start < max_wait:
        attempt += 1
        elapsed = int(time.time() - start)
        
        print(f"[Tentativo {attempt}] Controllo stato... ({elapsed}s)", end='')
        
        status = check_graph_status(model_id, slug)
        
        if status['available']:
            print(" ✓ DISPONIBILE!")
            return True
        
        print(f" ✗ Non disponibile (status: {status.get('status_code', 'N/A')})")
        
        if elapsed + check_interval < max_wait:
            time.sleep(check_interval)
        else:
            break
    
    print(f"\n[TIMEOUT] Grafo non disponibile dopo {max_wait}s")
    return False

def print_graph_info(data: dict):
    """Stampa informazioni sul grafo"""
    print("\n" + "=" * 70)
    print("INFORMAZIONI GRAFO")
    print("=" * 70)
    
    print(f"\nID: {data.get('id', 'N/A')}")
    print(f"Slug: {data.get('slug', 'N/A')}")
    print(f"Model: {data.get('modelId', 'N/A')}")
    print(f"Source Set: {data.get('sourceSetName', 'N/A')}")
    
    print(f"\nVisibilità: {'Pubblico' if data.get('isPublic') else 'Privato'}")
    print(f"Creato: {data.get('createdAt', 'N/A')}")
    print(f"Aggiornato: {data.get('updatedAt', 'N/A')}")
    
    if 'prompt' in data:
        prompt = data['prompt']
        if len(prompt) > 50:
            prompt = prompt[:50] + "..."
        print(f"\nPrompt: {prompt}")
    
    if 'stats' in data:
        stats = data['stats']
        print(f"\nStatistiche:")
        print(f"  Nodi: {stats.get('nodeCount', 'N/A')}")
        print(f"  Links: {stats.get('linkCount', 'N/A')}")
    
    # URL
    model_id = data.get('modelId')
    slug = data.get('slug')
    if model_id and slug:
        print(f"\nURL: https://www.neuronpedia.org/graph/{model_id}/{slug}")
    
    print("=" * 70)

# ===== MAIN =====

def main():
    parser = argparse.ArgumentParser(
        description="Verifica lo stato di un grafo su Neuronpedia",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Esempi:
  # Controllo singolo
  python %(prog)s gemma-2-2b my-graph-slug
  
  # Attende fino a disponibilità (max 5 minuti)
  python %(prog)s gemma-2-2b my-graph-slug --wait
  
  # Attende con timeout personalizzato
  python %(prog)s gemma-2-2b my-graph-slug --wait --max-wait 600
        """
    )
    
    parser.add_argument('model_id', help='Model ID (es: gemma-2-2b)')
    parser.add_argument('slug', help='Slug del grafo')
    parser.add_argument('--wait', action='store_true', 
                       help='Attende che il grafo sia disponibile')
    parser.add_argument('--max-wait', type=int, default=300,
                       help='Tempo massimo di attesa in secondi (default: 300)')
    parser.add_argument('--check-interval', type=int, default=10,
                       help='Intervallo tra i controlli in secondi (default: 10)')
    
    args = parser.parse_args()
    
    print("=" * 70)
    print("VERIFICA STATO GRAFO NEURONPEDIA")
    print("=" * 70)
    print(f"\nModel: {args.model_id}")
    print(f"Slug: {args.slug}")
    print()
    
    if args.wait:
        # Attende disponibilità
        available = wait_for_graph(
            args.model_id, 
            args.slug, 
            args.max_wait, 
            args.check_interval
        )
        
        if not available:
            print("\n[ERRORE] Grafo non disponibile dopo il timeout")
            sys.exit(1)
        
        # Recupera e mostra info
        status = check_graph_status(args.model_id, args.slug)
        print_graph_info(status['data'])
        
    else:
        # Controllo singolo
        print("Controllo stato...")
        status = check_graph_status(args.model_id, args.slug)
        
        if status['available']:
            print("[OK] Grafo disponibile!")
            print_graph_info(status['data'])
        else:
            print(f"[ERRORE] Grafo non disponibile")
            print(f"  Status code: {status.get('status_code', 'N/A')}")
            if 'error' in status:
                print(f"  Errore: {status['error']}")
            if 'message' in status:
                print(f"  Messaggio: {status['message']}")
            sys.exit(1)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n[INFO] Operazione interrotta dall'utente.")
        sys.exit(0)

