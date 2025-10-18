#!/usr/bin/env python3
"""
Genera un attribution graph su Neuronpedia, lo analizza e crea un subgraph con nodi pinnati strategicamente.

Flusso completo:
1. Genera un nuovo attribution graph tramite API
2. Recupera il JSON completo del grafo generato
3. Analizza la struttura per identificare nodi importanti
4. Seleziona strategicamente nodi da pinnare (embeddings, features intermedie, logit)
5. Crea supernodi raggruppando nodi correlati
6. Salva il subgraph con i nodi pinnati

Uso:
    python scripts/experiments/generate_and_analyze_graph.py
"""
import json
import os
import sys
import time
from typing import Dict, List, Tuple, Optional

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
                        # Rimuovi quotes se presenti
                        key = line.split('=', 1)[1].strip()
                        key = key.strip('"').strip("'")
                        if key:
                            return key
        except Exception as e:
            print(f"[ATTENZIONE] Errore leggendo .env: {e}")
    
    # Fallback: chiedi all'utente
    print("[ATTENZIONE] API key non trovata in .env o variabili d'ambiente.")
    print("   File .env cercato in: {}".format(os.path.abspath(env_path)))
    print("   Aggiungi una riga: NEURONPEDIA_API_KEY='your-key'")
    api_key = input("Oppure inserisci la tua API key ora (CTRL+C per uscire): ").strip()
    if not api_key:
        print("[ERRORE] API key necessaria per continuare.")
        sys.exit(1)
    return api_key

API_KEY = load_api_key()
print(f"[OK] API key caricata (lunghezza: {len(API_KEY)} caratteri)")
print()

# Configurazione generazione grafo
GRAPH_CONFIG = {
    "prompt": "The quick brown fox jumps over the lazy",  # Rimosso "dog" per predirlo
    "modelId": "gemma-2-2b",
    "sourceSetName": "gemmascope-transcoder-16k",
    "slug": "test-graph-fox",  # Verrà aggiunto timestamp per unicità
    "maxNLogits": 10,
    "desiredLogitProb": 0.95,
    "nodeThreshold": 0.8,
    "edgeThreshold": 0.85,
    "maxFeatureNodes": 5000
}

# Configurazione subgraph
SUBGRAPH_CONFIG = {
    "displayName": "Subgraph with Strategic Nodes",
    "pruningThreshold": 0.8,
    "densityThreshold": 0.99,
    "pin_all_embeddings": True,  # Pinna tutti gli embeddings (ma non in supernodi)
    "num_feature_nodes": 5,      # Numero di feature intermedie da selezionare
    "num_supernodes": 2,         # Numero di supernodi per le features (divideremo le 5 features in 2 gruppi)
    "pin_output_logit": True,    # Pinna l'output logit
}

# Directory output
OUTPUT_DIR = "output"
GRAPH_DATA_DIR = os.path.join(OUTPUT_DIR, "graph_data")

# API endpoints
API_BASE = "https://www.neuronpedia.org/api"
API_GENERATE = f"{API_BASE}/graph/generate"
API_GRAPH_META = f"{API_BASE}/graph"
API_SUBGRAPH_SAVE = f"{API_BASE}/graph/subgraph/save"

# ===== FUNZIONI UTILITY =====

def api_request(method: str, url: str, **kwargs) -> requests.Response:
    """Wrapper per richieste API con gestione errori"""
    headers = kwargs.pop('headers', {})
    headers.setdefault('x-api-key', API_KEY)
    
    try:
        response = requests.request(method, url, headers=headers, timeout=30, **kwargs)
        return response
    except requests.exceptions.RequestException as e:
        print(f"[ERRORE] Richiesta fallita: {e}")
        sys.exit(1)

def ensure_dirs():
    """Crea directory output se non esistono"""
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    os.makedirs(GRAPH_DATA_DIR, exist_ok=True)

def generate_unique_slug(base_slug: str) -> str:
    """Genera slug unico aggiungendo timestamp"""
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    return f"{base_slug}-{timestamp}"

# ===== STEP 1: GENERA ATTRIBUTION GRAPH =====

def generate_graph(config: Dict) -> Tuple[str, str, str]:
    """
    Genera un nuovo attribution graph su Neuronpedia.
    
    Returns:
        (s3_url, model_id, slug)
    """
    print("\n" + "=" * 70)
    print("STEP 1: GENERAZIONE ATTRIBUTION GRAPH")
    print("=" * 70)
    
    # Aggiungi timestamp allo slug per unicità
    config = config.copy()
    config['slug'] = generate_unique_slug(config['slug'])
    
    print(f"\nParametri generazione:")
    print(f"  Prompt: {config['prompt']}")
    print(f"  Model: {config['modelId']}")
    print(f"  Source Set: {config['sourceSetName']}")
    print(f"  Slug: {config['slug']}")
    print(f"  Max Feature Nodes: {config['maxFeatureNodes']}")
    print(f"  Node Threshold: {config['nodeThreshold']}")
    print(f"  Edge Threshold: {config['edgeThreshold']}")
    
    print("\nInvio richiesta generazione grafo...")
    
    response = api_request(
        'POST',
        API_GENERATE,
        headers={'Content-Type': 'application/json'},
        json=config
    )
    
    if response.status_code != 200:
        print(f"[ERRORE] Generazione fallita ({response.status_code})")
        print(f"Risposta: {response.text}")
        sys.exit(1)
    
    result = response.json()
    s3_url = result.get('s3url')
    
    if not s3_url:
        print(f"[ERRORE] URL S3 non trovato nella risposta: {result}")
        sys.exit(1)
    
    print(f"\n[OK] Grafo generato con successo!")
    print(f"     URL S3: {s3_url}")
    
    return s3_url, config['modelId'], config['slug']

# ===== STEP 2: RECUPERA JSON DEL GRAFO =====

def fetch_graph_data(s3_url: str, model_id: str, slug: str) -> Dict:
    """
    Recupera il JSON completo del grafo dall'URL S3.
    
    Returns:
        graph_data: dizionario con nodes, links, metadata
    """
    print("\n" + "=" * 70)
    print("STEP 2: RECUPERO DATI GRAFO")
    print("=" * 70)
    
    # Opzionale: recupera metadata dal server
    print(f"\nRecupero metadata grafo...")
    meta_url = f"{API_GRAPH_META}/{model_id}/{slug}"
    meta_response = api_request('GET', meta_url)
    
    if meta_response.status_code == 200:
        print(f"[OK] Metadata recuperati")
        meta = meta_response.json()
        print(f"     Display Name: {meta.get('displayName', 'N/A')}")
        print(f"     Created: {meta.get('createdAt', 'N/A')}")
    else:
        print(f"[ATTENZIONE] Impossibile recuperare metadata ({meta_response.status_code})")
    
    # Scarica JSON completo dal S3
    print(f"\nDownload JSON completo da S3...")
    graph_response = requests.get(s3_url, timeout=60)
    
    if graph_response.status_code != 200:
        print(f"[ERRORE] Download fallito ({graph_response.status_code})")
        sys.exit(1)
    
    graph_data = graph_response.json()
    
    # Salva localmente
    output_path = os.path.join(GRAPH_DATA_DIR, f"{slug}.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)
    
    file_size = os.path.getsize(output_path) / 1024 / 1024
    print(f"\n[OK] Grafo salvato: {output_path}")
    print(f"     Dimensione: {file_size:.2f} MB")
    print(f"     Nodi: {len(graph_data.get('nodes', []))}")
    print(f"     Links: {len(graph_data.get('links', []))}")
    
    return graph_data

# ===== STEP 3: ANALISI STRUTTURA GRAFO =====

def analyze_graph_structure(graph_data: Dict) -> Dict:
    """
    Analizza la struttura del grafo per identificare i tipi di nodi.
    
    Returns:
        analysis: dizionario con nodi categorizzati e metriche
    """
    print("\n" + "=" * 70)
    print("STEP 3: ANALISI STRUTTURA GRAFO")
    print("=" * 70)
    
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
        
        # Identifica tipo nodo
        layer = node.get('layer')
        
        # Embeddings (layer == 'E' o node_id inizia con 'E_')
        if layer == 'E' or (isinstance(node_id, str) and node_id.startswith('E_')):
            embedding_nodes.append(node)
        
        # Logit nodes (target output)
        elif node.get('is_target_logit') or node.get('isTargetLogit'):
            logit_nodes.append(node)
        
        # Feature nodes (layer numerico)
        else:
            feature_nodes.append(node)
            if layer is not None:
                layer_key = str(layer)
                if layer_key not in nodes_by_layer:
                    nodes_by_layer[layer_key] = []
                nodes_by_layer[layer_key].append(node)
    
    # Calcola metriche per nodi feature
    for node in feature_nodes:
        influence = node.get('influence') or 0.0
        activation = node.get('activation') or 0.0
        node['combined_score'] = abs(influence) * abs(activation)
    
    # Ordina per score
    feature_nodes.sort(key=lambda x: x.get('combined_score', 0), reverse=True)
    
    # Stampa analisi
    print(f"\nTipi di nodi identificati:")
    print(f"  Embedding nodes: {len(embedding_nodes)}")
    print(f"  Feature nodes: {len(feature_nodes)}")
    print(f"  Logit nodes: {len(logit_nodes)}")
    
    print(f"\nDistribuzione per layer:")
    for layer in sorted(nodes_by_layer.keys(), key=lambda x: int(x) if x.isdigit() else -1):
        count = len(nodes_by_layer[layer])
        print(f"  Layer {layer}: {count} nodi")
    
    if embedding_nodes:
        print(f"\nEmbedding nodes (primi 5):")
        for node in embedding_nodes[:5]:
            node_id = node.get('node_id') or node.get('nodeId')
            ctx_idx = node.get('ctx_idx', 'N/A')
            print(f"  {node_id} (pos={ctx_idx})")
    
    if logit_nodes:
        print(f"\nLogit nodes:")
        for node in logit_nodes:
            node_id = node.get('node_id') or node.get('nodeId')
            label = node.get('label', 'N/A')
            print(f"  {node_id} (label={label})")
    
    print(f"\nTop 10 feature nodes più influenti:")
    for i, node in enumerate(feature_nodes[:10], 1):
        node_id = node.get('node_id') or node.get('nodeId')
        layer = node.get('layer', 'N/A')
        influence = node.get('influence') or 0.0
        activation = node.get('activation') or 0.0
        score = node.get('combined_score', 0)
        print(f"  {i}. {node_id} (L{layer}): influence={influence:.3f}, "
              f"activation={activation:.3f}, score={score:.4f}")
    
    return {
        'embedding_nodes': embedding_nodes,
        'logit_nodes': logit_nodes,
        'feature_nodes': feature_nodes,
        'nodes_by_layer': nodes_by_layer,
        'total_links': len(links)
    }

# ===== STEP 4: SELEZIONE NODI DA PINNARE =====

def select_nodes_to_pin(analysis: Dict, config: Dict) -> Tuple[List[str], List[str], List]:
    """
    Seleziona strategicamente i nodi da pinnare.
    
    Returns:
        (pinned_node_ids, pinned_node_descriptions, feature_nodes_for_supernodes)
    """
    print("\n" + "=" * 70)
    print("STEP 4: SELEZIONE NODI DA PINNARE")
    print("=" * 70)
    
    pinned_nodes = []
    descriptions = []
    
    pin_all_emb = config.get('pin_all_embeddings', True)
    num_features = config.get('num_feature_nodes', 5)
    pin_logit = config.get('pin_output_logit', True)
    
    # 1. Pinna TUTTI gli embedding nodes (ma non in supernodi)
    emb_nodes = analysis['embedding_nodes']
    
    if pin_all_emb:
        print(f"\n1. Embedding nodes (tutti pinnati, NON in supernodi):")
        for node in emb_nodes:
            node_id = node.get('node_id') or node.get('nodeId')
            ctx_idx = node.get('ctx_idx', 'N/A')
            pinned_nodes.append(node_id)
            descriptions.append(f"Embedding pos={ctx_idx}")
            print(f"   ✓ {node_id} (pos={ctx_idx})")
    
    # 2. Seleziona N feature nodes intermedi più influenti
    feat_nodes = analysis['feature_nodes']
    # Evita nodi troppo vicini all'input o output
    mid_layer_features = []
    for n in feat_nodes:
        layer = n.get('layer')
        if layer is not None:
            try:
                layer_num = int(str(layer).replace('L', ''))
                if 2 <= layer_num <= 20:  # Layer intermedi (ampliato il range)
                    mid_layer_features.append(n)
            except (ValueError, TypeError):
                # Se il layer non è convertibile, usa comunque il nodo
                mid_layer_features.append(n)
    
    # Prendi i top N più influenti
    selected_features = mid_layer_features[:num_features]
    
    print(f"\n2. Feature nodes intermedi ({len(selected_features)} per supernodi):")
    for i, node in enumerate(selected_features, 1):
        node_id = node.get('node_id') or node.get('nodeId')
        layer = node.get('layer', 'N/A')
        score = node.get('combined_score', 0)
        pinned_nodes.append(node_id)
        descriptions.append(f"Feature L{layer} (score={score:.4f})")
        print(f"   {i}. {node_id} (L{layer}, score={score:.4f})")
    
    # 3. Pinna l'output logit
    logit_nodes = analysis['logit_nodes']
    
    if pin_logit and logit_nodes:
        print(f"\n3. Output logit (pinnato):")
        for node in logit_nodes:
            node_id = node.get('node_id') or node.get('nodeId')
            label = node.get('label', 'N/A')
            pinned_nodes.append(node_id)
            descriptions.append(f"Logit '{label}'")
            print(f"   ✓ {node_id} (label={label})")
    
    if not pinned_nodes:
        print("\n[ATTENZIONE] Nessun nodo selezionato per il pinning!")
        print("   Il grafo potrebbe non avere nodi con metriche sufficienti.")
        # Usa almeno un nodo se disponibile
        all_nodes = analysis['embedding_nodes'] + analysis['feature_nodes'] + analysis['logit_nodes']
        if all_nodes:
            fallback_node = all_nodes[0]
            node_id = fallback_node.get('node_id') or fallback_node.get('nodeId')
            pinned_nodes = [node_id]
            descriptions = ["Fallback node"]
            selected_features = []
            print(f"   Usando fallback: {node_id}")
    
    print(f"\n📌 Totale nodi pinnati: {len(pinned_nodes)}")
    print(f"   - Embeddings: {len(emb_nodes)} (NON in supernodi)")
    print(f"   - Features: {len(selected_features)} (da raggruppare in supernodi)")
    print(f"   - Logit: {len(logit_nodes)}")
    
    return pinned_nodes, descriptions, selected_features

# ===== STEP 5: CREAZIONE SUPERNODI =====

def create_supernodes(feature_nodes: List, config: Dict) -> List[List]:
    """
    Crea supernodi raggruppando le feature nodes.
    NON include embeddings o logit nei supernodi.
    
    Returns:
        supernodes: lista di [nome_supernodo, node_id1, node_id2, ...]
    """
    print("\n" + "=" * 70)
    print("STEP 5: CREAZIONE SUPERNODI")
    print("=" * 70)
    
    if not feature_nodes:
        print("  [INFO] Nessuna feature node disponibile per creare supernodi")
        return []
    
    num_supernodes = config.get('num_supernodes', 2)
    
    # Dividi le feature nodes in N gruppi
    supernodes = []
    nodes_per_supernode = len(feature_nodes) // num_supernodes
    remainder = len(feature_nodes) % num_supernodes
    
    start_idx = 0
    for i in range(num_supernodes):
        # Distribuisci il resto nei primi supernodi
        size = nodes_per_supernode + (1 if i < remainder else 0)
        end_idx = start_idx + size
        
        group = feature_nodes[start_idx:end_idx]
        
        if len(group) < 1:
            break
        
        # Determina il nome del supernodo basato sui layer
        layers = []
        for node in group:
            layer = node.get('layer')
            if layer is not None:
                try:
                    layers.append(int(str(layer).replace('L', '')))
                except:
                    pass
        
        if layers:
            min_layer = min(layers)
            max_layer = max(layers)
            if min_layer == max_layer:
                name = f"Features_L{min_layer}"
            else:
                name = f"Features_L{min_layer}-{max_layer}"
        else:
            name = f"Feature_Group_{i+1}"
        
        # Crea il supernodo
        node_ids = [node.get('node_id') or node.get('nodeId') for node in group]
        supernode = [name] + node_ids
        supernodes.append(supernode)
        
        print(f"\n  Supernodo {i+1}: '{name}'")
        print(f"    Nodi: {len(node_ids)}")
        for j, (node, nid) in enumerate(zip(group, node_ids), 1):
            layer = node.get('layer', 'N/A')
            score = node.get('combined_score', 0)
            print(f"      {j}. {nid} (L{layer}, score={score:.4f})")
        
        start_idx = end_idx
    
    print(f"\n  ✓ Creati {len(supernodes)} supernodi dalle {len(feature_nodes)} features")
    print(f"  ⚠️  Embeddings e logit NON sono in supernodi (solo pinnati individualmente)")
    
    return supernodes

# ===== STEP 6: SALVATAGGIO SUBGRAPH =====

def check_graph_status(model_id: str, slug: str) -> Dict:
    """
    Verifica lo stato del grafo su Neuronpedia.
    
    Returns:
        status: dizionario con informazioni sullo stato
    """
    meta_url = f"{API_GRAPH_META}/{model_id}/{slug}"
    response = api_request('GET', meta_url)
    
    if response.status_code == 200:
        return {
            'available': True,
            'data': response.json()
        }
    else:
        return {
            'available': False,
            'status_code': response.status_code,
            'message': response.text
        }

def save_subgraph(model_id: str, slug: str, pinned_nodes: List[str], 
                 supernodes: List[List], config: Dict) -> Dict:
    """
    Salva il subgraph su Neuronpedia.
    
    Returns:
        result: risposta API con subgraphId
    """
    print("\n" + "=" * 70)
    print("STEP 6: SALVATAGGIO SUBGRAPH")
    print("=" * 70)
    
    payload = {
        "modelId": model_id,
        "slug": slug,
        "displayName": config.get('displayName', 'Strategic Subgraph'),
        "pinnedIds": pinned_nodes,
        "supernodes": supernodes,
        "pruningThreshold": config.get('pruningThreshold', 0.8),
        "densityThreshold": config.get('densityThreshold', 0.99),
        "clerps": []
    }
    
    print(f"\nParametri subgraph:")
    print(f"  Model: {model_id}")
    print(f"  Slug: {slug}")
    print(f"  Display Name: {payload['displayName']}")
    print(f"  Nodi pinnati: {len(pinned_nodes)}")
    print(f"  Supernodi: {len(supernodes)}")
    print(f"  Pruning Threshold: {payload['pruningThreshold']}")
    print(f"  Density Threshold: {payload['densityThreshold']}")
    
    print(f"\nInvio richiesta salvataggio subgraph...")
    
    response = api_request(
        'POST',
        API_SUBGRAPH_SAVE,
        headers={'Content-Type': 'application/json'},
        json=payload
    )
    
    if response.status_code != 200:
        print(f"[ERRORE] Salvataggio fallito ({response.status_code})")
        print(f"Risposta: {response.text}")
        sys.exit(1)
    
    result = response.json()
    subgraph_id = result.get('subgraphId')
    
    print(f"\n[OK] Subgraph salvato con successo!")
    print(f"     Subgraph ID: {subgraph_id}")
    
    # Salva anche localmente
    output_path = os.path.join(GRAPH_DATA_DIR, f"{slug}_subgraph.json")
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    
    print(f"     Salvato localmente: {output_path}")
    
    return result

# ===== MAIN =====

def main():
    """Esegue il flusso completo di generazione e analisi"""
    ensure_dirs()
    
    print("\n" + "=" * 70)
    print("GENERAZIONE E ANALISI ATTRIBUTION GRAPH")
    print("=" * 70)
    print(f"\nPrompt: '{GRAPH_CONFIG['prompt']}'")
    print(f"Model: {GRAPH_CONFIG['modelId']}")
    print(f"Source Set: {GRAPH_CONFIG['sourceSetName']}")
    
    try:
        # Step 1: Genera grafo
        s3_url, model_id, slug = generate_graph(GRAPH_CONFIG)
        
        # Step 2: Recupera dati
        graph_data = fetch_graph_data(s3_url, model_id, slug)
        
        # Step 3: Analizza struttura
        analysis = analyze_graph_structure(graph_data)
        
        # Step 4: Seleziona nodi da pinnare
        pinned_nodes, descriptions, feature_nodes = select_nodes_to_pin(analysis, SUBGRAPH_CONFIG)
        
        # Step 5: Crea supernodi (solo dalle features, NO embeddings/logit)
        supernodes = create_supernodes(feature_nodes, SUBGRAPH_CONFIG)
        
        # Step 6: Salva subgraph
        result = save_subgraph(model_id, slug, pinned_nodes, supernodes, SUBGRAPH_CONFIG)
        
        # Step 7: Verifica stato
        print("\n" + "=" * 70)
        print("VERIFICA STATO GRAFO")
        print("=" * 70)
        
        print("\nControllo disponibilità del grafo...")
        time.sleep(2)  # Breve pausa per permettere al server di processare
        
        status = check_graph_status(model_id, slug)
        if status['available']:
            print("[OK] Grafo disponibile su Neuronpedia!")
            graph_data = status.get('data', {})
            if graph_data.get('isPublic'):
                print("     Visibilità: Pubblico")
            else:
                print("     Visibilità: Privato (solo tu con API key)")
        else:
            print(f"[INFO] Grafo non ancora disponibile (status: {status.get('status_code')})")
            print("      Potrebbe servire qualche minuto per il processing...")
        
        # Riepilogo finale
        print("\n" + "=" * 70)
        print("COMPLETATO CON SUCCESSO!")
        print("=" * 70)
        print(f"\nGrafo generato:")
        print(f"  Model: {model_id}")
        print(f"  Slug: {slug}")
        print(f"  Nodi totali: {len(graph_data.get('nodes', []))}")
        print(f"  Links totali: {len(graph_data.get('links', []))}")
        
        print(f"\nSubgraph creato:")
        print(f"  Subgraph ID: {result.get('subgraphId')}")
        print(f"  Nodi pinnati: {len(pinned_nodes)}")
        print(f"  Supernodi: {len(supernodes)}")
        
        print(f"\nTipi di nodi inclusi:")
        n_emb = sum(1 for d in descriptions if 'Embedding' in d)
        n_feat = sum(1 for d in descriptions if 'Feature' in d)
        n_logit = sum(1 for d in descriptions if 'Logit' in d)
        print(f"  Embeddings pinnati: {n_emb} (NON in supernodi)")
        print(f"  Features intermedie: {n_feat} (raggruppate in {len(supernodes)} supernodi)")
        print(f"  Output logits: {n_logit} (pinnati)")
        
        print(f"\nSupernodi creati:")
        for i, sn in enumerate(supernodes, 1):
            print(f"  {i}. '{sn[0]}' con {len(sn)-1} nodi")
        
        print(f"\nVisualizza su Neuronpedia:")
        print(f"  URL Grafo: https://www.neuronpedia.org/graph/{model_id}/{slug}")
        print(f"  URL Subgraph: https://www.neuronpedia.org/graph/{model_id}/{slug}?subgraph={result.get('subgraphId')}")
        
        print(f"\n⚠️  NOTA IMPORTANTE:")
        print(f"  - Il grafo potrebbe richiedere alcuni minuti per essere disponibile")
        print(f"  - Se vedi 'Couldn't find that page', attendi qualche minuto e riprova")
        print(f"  - Il grafo potrebbe essere privato (visibile solo con la tua API key)")
        
        print(f"\nFile salvati localmente:")
        print(f"  - Grafo: output/graph_data/{slug}.json")
        print(f"  - Subgraph: output/graph_data/{slug}_subgraph.json")
        print("=" * 70)
        
    except KeyboardInterrupt:
        print("\n\n[INFO] Operazione interrotta dall'utente.")
        sys.exit(0)
    except Exception as e:
        print(f"\n[ERRORE] Errore inaspettato: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    main()

