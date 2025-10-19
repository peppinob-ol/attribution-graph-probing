#!/usr/bin/env python3
"""
Script per generare attribution graphs su Neuronpedia.

Fornisce funzioni parametrizzate per:
- Generare un nuovo attribution graph tramite API
- Recuperare il JSON completo del grafo generato
- Salvare localmente i dati

Uso come script:
    python scripts/00_neuronpedia_graph_generation.py

Uso come modulo:
    from scripts.neuronpedia_graph_generation import generate_attribution_graph
    
    result = generate_attribution_graph(
        prompt="<bos> The capital of state containing Dallas is",
        model_id="gemma-2-2b",
        api_key="your-key"
    )
"""
import json
import os
import sys
import time
from typing import Dict, Optional, Tuple
from pathlib import Path

try:
    import requests
except ImportError:
    print("[ERRORE] Modulo 'requests' non trovato. Installa con: pip install requests")
    sys.exit(1)

# ===== CONFIGURAZIONE DEFAULT =====

DEFAULT_CONFIG = {
    "modelId": "gemma-2-2b",
    "sourceSetName": "gemmascope-transcoder-16k",
    "maxNLogits": 10,
    "desiredLogitProb": 0.95,
    "nodeThreshold": 0.8,
    "edgeThreshold": 0.85,
    "maxFeatureNodes": 5000
}

# Directory output
OUTPUT_DIR = "output"
GRAPH_DATA_DIR = os.path.join(OUTPUT_DIR, "graph_data")

# API endpoints
API_BASE = "https://www.neuronpedia.org/api"
API_GENERATE = f"{API_BASE}/graph/generate"
API_GRAPH_META = f"{API_BASE}/graph"

# ===== FUNZIONI UTILITY =====

def load_api_key(env_path: Optional[str] = None) -> Optional[str]:
    """
    Carica API key da .env o variabile d'ambiente.
    
    Args:
        env_path: Path al file .env (opzionale, default: root/.env)
        
    Returns:
        API key se trovata, altrimenti None
    """
    # Prima prova con variabile d'ambiente
    api_key = os.environ.get('NEURONPEDIA_API_KEY')
    if api_key:
        return api_key
    
    # Poi cerca nel file .env
    if env_path is None:
        env_path = os.path.join(os.path.dirname(__file__), '..', '.env')
    
    if os.path.exists(env_path):
        try:
            with open(env_path, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if line.startswith('NEURONPEDIA_API_KEY='):
                        # Rimuovi quotes se presenti
                        key = line.split('=', 1)[1].strip()
                        key = key.strip('"').strip("'")
                        if key:
                            return key
        except Exception as e:
            print(f"[ATTENZIONE] Errore leggendo .env: {e}")
    
    return None


def ensure_output_dirs():
    """Crea directory output se non esistono"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(GRAPH_DATA_DIR, exist_ok=True)


def generate_unique_slug(base_slug: str) -> str:
    """Genera slug unico aggiungendo timestamp"""
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return f"{base_slug}-{timestamp}"


def api_request(method: str, url: str, api_key: str, **kwargs) -> requests.Response:
    """
    Wrapper per richieste API con gestione errori.
    
    Args:
        method: Metodo HTTP (GET, POST, etc.)
        url: URL della richiesta
        api_key: Chiave API Neuronpedia
        **kwargs: Parametri aggiuntivi per requests
        
    Returns:
        Response object
        
    Raises:
        requests.exceptions.RequestException: Se la richiesta fallisce
    """
    headers = kwargs.pop('headers', {})
    headers.setdefault('x-api-key', api_key)
    
    response = requests.request(method, url, headers=headers, timeout=60, **kwargs)
    return response


# ===== FUNZIONI PRINCIPALI =====

def generate_attribution_graph(
    prompt: str,
    api_key: str,
    model_id: str = "gemma-2-2b",
    source_set_name: str = "gemmascope-transcoder-16k",
    slug: Optional[str] = None,
    max_n_logits: int = 10,
    desired_logit_prob: float = 0.95,
    node_threshold: float = 0.8,
    edge_threshold: float = 0.85,
    max_feature_nodes: int = 5000,
    save_locally: bool = True,
    output_dir: Optional[str] = None,
    verbose: bool = True
) -> Dict:
    """
    Genera un attribution graph su Neuronpedia e recupera il JSON.
    
    Args:
        prompt: Testo del prompt da analizzare
        api_key: Chiave API Neuronpedia
        model_id: ID del modello (default: gemma-2-2b)
        source_set_name: Nome del source set (default: gemmascope-transcoder-16k)
        slug: Slug personalizzato (se None, usa 'graph' + timestamp)
        max_n_logits: Numero massimo di logit da considerare
        desired_logit_prob: Probabilità desiderata per i logit
        node_threshold: Soglia per inclusione nodi
        edge_threshold: Soglia per inclusione edges
        max_feature_nodes: Numero massimo di feature nodes
        save_locally: Se True, salva il JSON localmente
        output_dir: Directory dove salvare (default: output/graph_data/)
        verbose: Se True, stampa informazioni di progresso
        
    Returns:
        Dict con keys:
            - 'success': bool
            - 'graph_data': Dict con nodes, links, metadata
            - 's3_url': URL S3 del grafo
            - 'model_id': ID del modello
            - 'slug': Slug del grafo
            - 'local_path': Path locale (se save_locally=True)
            - 'error': messaggio di errore (se success=False)
    """
    ensure_output_dirs()
    
    # Genera slug unico
    if slug is None:
        # Usa i primi 3 token del prompt come base slug
        tokens = prompt.strip().split()[:3]
        base_slug = "-".join(token.lower().strip('<>') for token in tokens)
        slug = generate_unique_slug(base_slug)
    else:
        slug = generate_unique_slug(slug)
    
    if output_dir is None:
        output_dir = GRAPH_DATA_DIR
    
    # Prepara payload
    config = {
        "prompt": prompt,
        "modelId": model_id,
        "sourceSetName": source_set_name,
        "slug": slug,
        "maxNLogits": max_n_logits,
        "desiredLogitProb": desired_logit_prob,
        "nodeThreshold": node_threshold,
        "edgeThreshold": edge_threshold,
        "maxFeatureNodes": max_feature_nodes
    }
    
    if verbose:
        print(f"\n{'='*70}")
        print("GENERAZIONE ATTRIBUTION GRAPH")
        print(f"{'='*70}")
        print(f"Prompt: {prompt}")
        print(f"Model: {model_id}")
        print(f"Source Set: {source_set_name}")
        print(f"Slug: {slug}")
        print(f"Max Feature Nodes: {max_feature_nodes}")
        print(f"Node Threshold: {node_threshold}")
        print(f"Edge Threshold: {edge_threshold}")
    
    try:
        # Step 1: Richiesta generazione
        if verbose:
            print("\nInvio richiesta generazione...")
        
        response = api_request(
            'POST',
            API_GENERATE,
            api_key,
            headers={'Content-Type': 'application/json'},
            json=config
        )
        
        if response.status_code != 200:
            error_msg = f"Generazione fallita (status {response.status_code}): {response.text}"
            if verbose:
                print(f"[ERRORE] {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                'status_code': response.status_code
            }
        
        result = response.json()
        s3_url = result.get('s3url')
        
        if not s3_url:
            error_msg = f"URL S3 non trovato nella risposta: {result}"
            if verbose:
                print(f"[ERRORE] {error_msg}")
            return {
                'success': False,
                'error': error_msg
            }
        
        if verbose:
            print(f"[OK] Grafo generato!")
            print(f"     URL S3: {s3_url}")
        
        # Step 2: Download JSON da S3
        if verbose:
            print("\nDownload JSON da S3...")
        
        graph_response = requests.get(s3_url, timeout=120)
        
        if graph_response.status_code != 200:
            error_msg = f"Download fallito (status {graph_response.status_code})"
            if verbose:
                print(f"[ERRORE] {error_msg}")
            return {
                'success': False,
                'error': error_msg,
                's3_url': s3_url,
                'model_id': model_id,
                'slug': slug
            }
        
        graph_data = graph_response.json()
        
        if verbose:
            print(f"[OK] JSON recuperato!")
            print(f"     Nodi: {len(graph_data.get('nodes', []))}")
            print(f"     Links: {len(graph_data.get('links', []))}")
        
        # Step 3: Salvataggio locale (opzionale)
        local_path = None
        if save_locally:
            local_path = os.path.join(output_dir, f"{slug}.json")
            with open(local_path, 'w', encoding='utf-8') as f:
                json.dump(graph_data, f, ensure_ascii=False, indent=2)
            
            file_size = os.path.getsize(local_path) / 1024 / 1024
            if verbose:
                print(f"\n[OK] Salvato localmente: {local_path}")
                print(f"     Dimensione: {file_size:.2f} MB")
        
        # Recupera metadata (opzionale)
        metadata = None
        try:
            meta_url = f"{API_GRAPH_META}/{model_id}/{slug}"
            meta_response = api_request('GET', meta_url, api_key)
            if meta_response.status_code == 200:
                metadata = meta_response.json()
                if verbose:
                    print(f"\n[OK] Metadata recuperati")
        except Exception as e:
            if verbose:
                print(f"\n[INFO] Metadata non disponibili: {e}")
        
        if verbose:
            print(f"\n{'='*70}")
            print("COMPLETATO CON SUCCESSO!")
            print(f"{'='*70}")
            print(f"\nURL Neuronpedia:")
            print(f"  https://www.neuronpedia.org/graph/{model_id}/{slug}")
        
        return {
            'success': True,
            'graph_data': graph_data,
            's3_url': s3_url,
            'model_id': model_id,
            'slug': slug,
            'local_path': local_path,
            'metadata': metadata,
            'num_nodes': len(graph_data.get('nodes', [])),
            'num_links': len(graph_data.get('links', []))
        }
        
    except requests.exceptions.RequestException as e:
        error_msg = f"Errore di rete: {str(e)}"
        if verbose:
            print(f"\n[ERRORE] {error_msg}")
        return {
            'success': False,
            'error': error_msg
        }
    except Exception as e:
        error_msg = f"Errore inaspettato: {str(e)}"
        if verbose:
            print(f"\n[ERRORE] {error_msg}")
            import traceback
            traceback.print_exc()
        return {
            'success': False,
            'error': error_msg
        }


def extract_static_metrics_from_json(
    graph_data: Dict,
    output_path: Optional[str] = None,
    verbose: bool = True
) -> Optional[Dict]:
    """
    Estrae metriche statiche (logit_influence, frac_external_raw) dal JSON del grafo.
    
    Args:
        graph_data: Dict con nodes e links dal JSON Neuronpedia
        output_path: Path dove salvare CSV (se None, non salva)
        verbose: Se True, stampa informazioni
        
    Returns:
        DataFrame con colonne: layer, feature, frac_external_raw, logit_influence
    """
    try:
        import pandas as pd
    except ImportError:
        print("[ERRORE] pandas richiesto. Installa con: pip install pandas")
        return None
    
    nodes = graph_data.get('nodes', [])
    links = graph_data.get('links', [])
    
    if verbose:
        print(f"\n{'='*70}")
        print("ESTRAZIONE METRICHE STATICHE DA JSON")
        print(f"{'='*70}")
        print(f"Nodi totali: {len(nodes)}")
        print(f"Links totali: {len(links)}")
    
    # Step 1: Filtra solo feature nodes (escludi embeddings e logit nodes)
    feature_nodes = []
    for node in nodes:
        layer = node.get('layer')
        is_logit = node.get('is_target_logit') or node.get('isTargetLogit')
        
        # Escludi embeddings (layer='E') e logit nodes
        if layer != 'E' and not is_logit:
            feature_nodes.append(node)
    
    if verbose:
        print(f"Feature nodes: {len(feature_nodes)}")
    
    # Step 2: Estrai logit_influence (già presente come 'influence' nel JSON)
    metrics_list = []
    node_id_to_data = {}
    
    for node in feature_nodes:
        node_id = node.get('node_id') or node.get('nodeId')
        layer = node.get('layer')
        feature = node.get('feature')
        influence = node.get('influence', 0.0)
        
        # Converti layer a int se possibile
        try:
            layer_int = int(layer)
        except (ValueError, TypeError):
            continue
        
        data = {
            'node_id': node_id,
            'layer': layer_int,
            'feature': feature,
            'logit_influence': influence
        }
        
        metrics_list.append(data)
        node_id_to_data[node_id] = data
    
    # Step 3: Calcola frac_external_raw dai links
    # frac_external = 1 - (self_loop_weight / total_incoming_weight)
    
    # Calcola total incoming weight per ogni nodo
    incoming_weights = {}
    self_loop_weights = {}
    
    for link in links:
        source = link.get('source')
        target = link.get('target')
        weight = abs(link.get('weight', 0.0))
        
        if target not in incoming_weights:
            incoming_weights[target] = 0.0
            self_loop_weights[target] = 0.0
        
        incoming_weights[target] += weight
        
        # Se source == target, è un self-loop
        if source == target:
            self_loop_weights[target] = weight
    
    # Calcola frac_external per ogni feature node
    for data in metrics_list:
        node_id = data['node_id']
        
        total_in = incoming_weights.get(node_id, 0.0)
        self_loop = self_loop_weights.get(node_id, 0.0)
        
        if total_in > 0:
            # Normalizza self-loop
            self_normalized = self_loop / total_in
            frac_external = 1.0 - self_normalized
        else:
            # Nessun input → assume tutto esterno
            frac_external = 1.0
        
        data['frac_external_raw'] = frac_external
    
    # Step 4: Crea DataFrame
    df = pd.DataFrame(metrics_list)
    df = df[['layer', 'feature', 'frac_external_raw', 'logit_influence']]
    df = df.sort_values(['layer', 'feature']).reset_index(drop=True)
    
    if verbose:
        print(f"\nStatistiche metriche:")
        print(f"   Feature processate: {len(df)}")
        print(f"   frac_external_raw: min={df['frac_external_raw'].min():.3f}, "
              f"max={df['frac_external_raw'].max():.3f}, "
              f"mean={df['frac_external_raw'].mean():.3f}")
        print(f"   logit_influence: min={df['logit_influence'].min():.4f}, "
              f"max={df['logit_influence'].max():.4f}, "
              f"sum={df['logit_influence'].sum():.4f}")
    
    # Step 5: Salva CSV (opzionale)
    if output_path:
        df.to_csv(output_path, index=False)
        if verbose:
            file_size = os.path.getsize(output_path) / 1024
            print(f"\n[OK] CSV salvato: {output_path}")
            print(f"     Dimensione: {file_size:.1f} KB")
    
    return df


def generate_static_metrics_csv(
    json_path: str,
    output_csv_path: Optional[str] = None,
    verbose: bool = True
) -> Optional[Dict]:
    """
    Genera CSV con metriche statiche a partire da un file JSON del grafo.
    
    Args:
        json_path: Path al file JSON del grafo
        output_csv_path: Path dove salvare il CSV (default: stesso nome con .csv)
        verbose: Se True, stampa informazioni
        
    Returns:
        DataFrame con le metriche, o None se errore
    """
    try:
        # Carica JSON
        if verbose:
            print(f"Caricamento JSON: {json_path}")
        
        with open(json_path, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)
        
        # Genera path CSV se non specificato
        if output_csv_path is None:
            json_pathobj = Path(json_path)
            output_csv_path = str(json_pathobj.parent.parent / 'graph_feature_static_metrics.csv')
        
        # Estrai metriche
        df = extract_static_metrics_from_json(graph_data, output_csv_path, verbose)
        
        return df
        
    except FileNotFoundError:
        print(f"[ERRORE] File non trovato: {json_path}")
        return None
    except json.JSONDecodeError:
        print(f"[ERRORE] File JSON non valido: {json_path}")
        return None
    except Exception as e:
        print(f"[ERRORE] Errore inaspettato: {e}")
        if verbose:
            import traceback
            traceback.print_exc()
        return None


def get_graph_stats(graph_data: Dict) -> Dict:
    """
    Calcola statistiche di base sul grafo.
    
    Args:
        graph_data: Dizionario con nodes, links
        
    Returns:
        Dict con statistiche
    """
    nodes = graph_data.get('nodes', [])
    links = graph_data.get('links', [])
    
    # Categorizza nodi
    embedding_nodes = []
    logit_nodes = []
    feature_nodes = []
    nodes_by_layer = {}
    
    for node in nodes:
        node_id = node.get('node_id') or node.get('nodeId')
        if not node_id:
            continue
        
        layer = node.get('layer')
        
        # Embeddings
        if layer == 'E' or (isinstance(node_id, str) and node_id.startswith('E_')):
            embedding_nodes.append(node)
        # Logit nodes
        elif node.get('is_target_logit') or node.get('isTargetLogit'):
            logit_nodes.append(node)
        # Feature nodes
        else:
            feature_nodes.append(node)
            if layer is not None:
                layer_key = str(layer)
                if layer_key not in nodes_by_layer:
                    nodes_by_layer[layer_key] = []
                nodes_by_layer[layer_key].append(node)
    
    return {
        'total_nodes': len(nodes),
        'total_links': len(links),
        'embedding_nodes': len(embedding_nodes),
        'feature_nodes': len(feature_nodes),
        'logit_nodes': len(logit_nodes),
        'layers': sorted(nodes_by_layer.keys(), key=lambda x: int(x) if x.isdigit() else -1),
        'nodes_by_layer': {k: len(v) for k, v in nodes_by_layer.items()}
    }


# ===== MAIN PER USO STANDALONE =====

def main():
    """Esegue generazione grafo con parametri di default"""
    
    # Carica API key
    api_key = load_api_key()
    
    if not api_key:
        print("[ERRORE] API key non trovata!")
        print("  Imposta NEURONPEDIA_API_KEY come variabile d'ambiente")
        print("  oppure aggiungila al file .env nella root del progetto:")
        print("  NEURONPEDIA_API_KEY='your-key-here'")
        sys.exit(1)
    
    print(f"[OK] API key caricata (lunghezza: {len(api_key)} caratteri)\n")
    
    # Parametri di default
    default_prompt = "The capital of state containing Dallas is"
    
    print("Parametri di default:")
    print(f"  Prompt: {default_prompt}")
    print(f"  Model: {DEFAULT_CONFIG['modelId']}")
    print(f"  Source Set: {DEFAULT_CONFIG['sourceSetName']}")
    print()
    
    use_default = input("Usare parametri di default? (y/n, default=y): ").strip().lower()
    
    if use_default in ['', 'y', 'yes']:
        prompt = default_prompt
    else:
        prompt = input("Inserisci prompt personalizzato: ").strip()
        if not prompt:
            print("[ERRORE] Prompt richiesto!")
            sys.exit(1)
    
    # Genera grafo
    result = generate_attribution_graph(
        prompt=prompt,
        api_key=api_key,
        verbose=True
    )
    
    if not result['success']:
        print(f"\n[ERRORE] Generazione fallita: {result.get('error')}")
        sys.exit(1)
    
    # Calcola statistiche
    stats = get_graph_stats(result['graph_data'])
    
    print("\nStatistiche grafo:")
    print(f"  Nodi totali: {stats['total_nodes']}")
    print(f"  Links totali: {stats['total_links']}")
    print(f"  Embedding nodes: {stats['embedding_nodes']}")
    print(f"  Feature nodes: {stats['feature_nodes']}")
    print(f"  Logit nodes: {stats['logit_nodes']}")
    print(f"\nDistribuzione per layer:")
    for layer in stats['layers']:
        print(f"  Layer {layer}: {stats['nodes_by_layer'][layer]} nodi")
    
    print(f"\n✓ Grafo salvato in: {result['local_path']}")
    print(f"\n🌐 Visualizza su Neuronpedia:")
    print(f"   https://www.neuronpedia.org/graph/{result['model_id']}/{result['slug']}")


if __name__ == "__main__":
    main()

