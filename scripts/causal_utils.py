#!/usr/bin/env python3
"""
Utilities per analisi causale dell'Attribution Graph
Funzioni per caricare grafo, calcolare node_influence, vicinato causale, compatibilità
"""

import torch
import numpy as np
from pathlib import Path
from typing import Dict, List, Tuple, Optional
from collections import defaultdict
from functools import lru_cache


def _norm_token_str(s: str) -> str:
    """Normalizza token string: rimuove Ġ (GPT-2 byte-level), spazi, lowercase"""
    return s.replace("Ġ", "").replace(" ", "").strip().lower()


@lru_cache(maxsize=4)
def _load_tokenizer_by_name(model_name: str):
    """Carica tokenizer dal nome del modello (cached)"""
    try:
        from transformers import AutoTokenizer
        return AutoTokenizer.from_pretrained(model_name, use_fast=True)
    except Exception:
        return None


def _get_tokenizer(cfg):
    """Estrae tokenizer dal config (non cached per evitare unhashable)"""
    model_name = getattr(cfg, "tokenizer_name", None) or getattr(cfg, "model_name", None) or "gpt2"
    return _load_tokenizer_by_name(model_name)


def _decode_token_id(token_id, tokenizer):
    """Decodifica un token ID in stringa"""
    try:
        tid = int(token_id.item() if hasattr(token_id, "item") else token_id)
        if tokenizer is not None:
            return tokenizer.decode([tid], clean_up_tokenization_spaces=False)
        return str(tid)
    except Exception:
        return str(token_id)


def load_attribution_graph(graph_path: str = "output/example_graph.pt", verbose: bool = False) -> Optional[Dict]:
    """
    Carica Attribution Graph da file .pt
    
    Args:
        graph_path: percorso del file .pt
        verbose: se True, stampa informazioni dettagliate sul caricamento
    
    Returns:
        Dict con: adjacency_matrix, active_features, input_tokens, logit_tokens, cfg
        None se file non trovato
    """
    if not Path(graph_path).exists():
        print(f"WARN: Grafo non trovato: {graph_path}")
        return None
    

    
    try:
        # Fix per PyTorch 2.6: weights_only=False per caricare oggetti custom
        # Il file è generato dal nostro codice, quindi è sicuro
        graph_data = torch.load(graph_path, map_location='cpu', weights_only=False)
        
        # Verifica componenti essenziali
        required_keys = ['adjacency_matrix', 'active_features', 'input_tokens', 'logit_tokens', 'cfg']
        for key in required_keys:
            if key not in graph_data:
                print(f"WARN: Chiave mancante nel grafo: {key}")
                return None
        

        return graph_data
    
    except Exception as e:
        print(f"ERROR: Errore caricamento grafo: {e}")
        import traceback
        traceback.print_exc()
        return None


def compute_node_influence(
    adjacency_matrix: torch.Tensor,
    n_features: int,
    n_logits: int,
    normalize: bool = True
) -> torch.Tensor:
    """
    Calcola node_influence per ogni feature propagando backward dai logits
    
    Algoritmo: influence[i] = sum_j (adjacency[logit_j, i] * weight_propagation)
    
    Args:
        adjacency_matrix: (n_nodes, n_nodes) - righe=target, colonne=source
        n_features: numero di feature attive
        n_logits: numero di logit nodes
        normalize: se True, normalizza per righe prima di propagare
        
    Returns:
        Tensor (n_features,) con node_influence per ogni feature
    """
    n_nodes = adjacency_matrix.shape[0]
    
    # Normalizza adjacency matrix per righe (optional, per stabilità)
    if normalize:
        row_sums = adjacency_matrix.sum(dim=1, keepdim=True)
        row_sums[row_sums == 0] = 1  # Evita divisione per zero
        adj_normalized = adjacency_matrix / row_sums
    else:
        adj_normalized = adjacency_matrix
    
    # Logit nodes sono gli ultimi n_logits nodi
    logit_start = n_nodes - n_logits
    
    # Influence iniziale: 1.0 per ogni logit
    influence = torch.zeros(n_nodes)
    influence[logit_start:] = 1.0
    
    # Propaga backward attraverso il grafo (max 10 iterazioni)
    for _ in range(10):
        # influence[i] = sum_j (adj[j, i] * influence[j])
        # Ovvero: quanto influence arriva a i dai suoi figli j
        new_influence = adj_normalized.T @ influence
        
        # Mantieni fisso l'influence dei logits
        new_influence[logit_start:] = 1.0
        
        # Check convergenza
        if torch.allclose(influence, new_influence, atol=1e-6):
            break
        
        influence = new_influence
    
    # Ritorna solo influence delle feature (primi n_features nodi)
    return influence[:n_features]


def compute_causal_metrics(
    graph_data: Dict,
    tau_edge: float = 0.01,
    top_k: int = 5,
    verbose: bool = False
) -> Dict[str, Dict]:
    """
    Calcola metriche causali per ogni feature nel grafo
    
    Args:
        graph_data: dict con adjacency_matrix, active_features, etc.
        tau_edge: soglia per considerare edge "forte"
        top_k: numero di top parents/children da estrarre
        verbose: se True, stampa informazioni dettagliate
        
    Returns:
        Dict[feature_key, metrics] con:
            - node_influence: float
            - causal_in_degree: int
            - causal_out_degree: int
            - top_parents: List[(feature_key, weight)]
            - top_children: List[(feature_key, weight)]
            - position_at_final: bool
            - layer: int
            - position: int
    """
    if verbose:
        print("\nCalcolo metriche causali...")
    
    adjacency_matrix = graph_data['adjacency_matrix']
    active_features = graph_data['active_features']
    n_features = len(active_features)
    n_logits = len(graph_data['logit_tokens'])
    n_pos = len(graph_data['input_tokens'])
    n_layers = graph_data['cfg'].n_layers
    
    # Calcola node influence
    node_influences = compute_node_influence(adjacency_matrix, n_features, n_logits)
    
    # Crea mapping feature_key -> indice
    feature_to_idx = {}
    idx_to_feature = {}
    for i, (layer, pos, feat_idx) in enumerate(active_features):
        feature_key = f"{layer.item()}_{feat_idx.item()}"
        feature_to_idx[feature_key] = i
        idx_to_feature[i] = (feature_key, layer.item(), pos.item())
    
    # Estrai submatrix solo per feature (ignora error/embed/logit nodes)
    feature_adj = adjacency_matrix[:n_features, :n_features]
    
    causal_metrics = {}
    
    for i, (layer, pos, feat_idx) in enumerate(active_features):
        feature_key = f"{layer.item()}_{feat_idx.item()}"
        
        # In-degree: quante edge entranti forti (chi causa questa feature)
        incoming_edges = feature_adj[i, :]  # Riga i = target
        strong_incoming = (incoming_edges > tau_edge).sum().item()
        
        # Out-degree: quante edge uscenti forti (chi è causato da questa feature)
        outgoing_edges = feature_adj[:, i]  # Colonna i = source
        strong_outgoing = (outgoing_edges > tau_edge).sum().item()
        
        # Top parents (features che causano questa)
        parent_weights = incoming_edges.clone()
        parent_weights[i] = 0  # Escludi self-loop
        top_parent_indices = torch.topk(parent_weights, min(top_k, n_features), largest=True)
        
        top_parents = []
        for idx, weight in zip(top_parent_indices.indices, top_parent_indices.values):
            if weight > tau_edge and idx.item() in idx_to_feature:
                parent_key, _, _ = idx_to_feature[idx.item()]
                top_parents.append((parent_key, float(weight)))
        
        # Top children (features causate da questa)
        child_weights = outgoing_edges.clone()
        child_weights[i] = 0  # Escludi self-loop
        top_child_indices = torch.topk(child_weights, min(top_k, n_features), largest=True)
        
        top_children = []
        for idx, weight in zip(top_child_indices.indices, top_child_indices.values):
            if weight > tau_edge and idx.item() in idx_to_feature:
                child_key, _, _ = idx_to_feature[idx.item()]
                top_children.append((child_key, float(weight)))
        
        # Position preference
        position_at_final = (pos.item() == n_pos - 1)
        
        causal_metrics[feature_key] = {
            'node_influence': float(node_influences[i]),
            'causal_in_degree': int(strong_incoming),
            'causal_out_degree': int(strong_outgoing),
            'top_parents': top_parents,
            'top_children': top_children,
            'position_at_final': position_at_final,
            'layer': int(layer.item()),
            'position': int(pos.item())
        }
    
    print(f"OK: Metriche causali calcolate per {len(causal_metrics)} feature")
    
    # Stats
    avg_influence = np.mean([m['node_influence'] for m in causal_metrics.values()])
    max_influence = max([m['node_influence'] for m in causal_metrics.values()])
    print(f"   Node influence: avg={avg_influence:.4f}, max={max_influence:.4f}")
    
    return causal_metrics


def find_say_austin_seed(
    graph_data: Dict,
    causal_metrics: Dict[str, Dict],
    target_logit_token: str = "Austin",
    tau_edge: float = 0.01
) -> Optional[Dict]:
    """
    Trova il seed "Say Austin": feature alla posizione finale con edge più forte su logit target
    
    Args:
        graph_data: dict con adjacency_matrix, active_features, logit_tokens
        causal_metrics: dict con metriche causali pre-calcolate
        target_logit_token: token logit target (default "Austin")
        tau_edge: soglia minima per edge
        
    Returns:
        Dict con seed info, o None se non trovato
    """
    print(f"\nRicerca seed 'Say {target_logit_token}'...")
    
    adjacency_matrix = graph_data['adjacency_matrix']
    active_features = graph_data['active_features']
    logit_tokens = graph_data['logit_tokens']
    n_features = len(active_features)
    n_pos = len(graph_data['input_tokens'])
    
    # Carica tokenizer e decodifica logit tokens
    tokenizer = _get_tokenizer(graph_data['cfg'])
    decoded_tokens = []
    for tok in logit_tokens:
        decoded_tokens.append(_decode_token_id(tok, tokenizer))
    
    # Normalizza per matching
    decoded_norm = [_norm_token_str(s) for s in decoded_tokens]
    target_norm = _norm_token_str(target_logit_token)
    
    # Trova indice del logit target
    logit_idx = None
    for i, (token_str, token_norm) in enumerate(zip(decoded_tokens, decoded_norm)):
        if token_norm == target_norm:
            logit_idx = i
            print(f"   OK: Logit '{target_logit_token}' trovato all'indice {i} (decodificato: '{token_str}')")
            break
    
    if logit_idx is None:
        print(f"   WARN: Logit '{target_logit_token}' non trovato nei top-{len(logit_tokens)} logit del grafo")
        if decoded_tokens:
            print(f"   ℹ️  Logit disponibili: {decoded_tokens[:10]}{' ...' if len(decoded_tokens)>10 else ''}")
        return None
    
    # Logit nodes sono alla fine della adjacency matrix
    n_nodes = adjacency_matrix.shape[0]
    n_logits = len(logit_tokens)
    logit_node_idx = n_nodes - n_logits + logit_idx
    
    # Trova feature con edge più forte verso questo logit
    # Edge da feature i a logit: adjacency[logit_node_idx, i] (colonna i = source)
    edges_to_logit = adjacency_matrix[logit_node_idx, :n_features]
    
    # Filtra solo feature alla posizione finale
    final_pos_mask = torch.zeros(n_features, dtype=torch.bool)
    for i, (layer, pos, feat_idx) in enumerate(active_features):
        if pos.item() == n_pos - 1:
            final_pos_mask[i] = True
    
    edges_to_logit_final = edges_to_logit.clone()
    edges_to_logit_final[~final_pos_mask] = 0  # Azzera non-finali
    
    # Top feature
    if edges_to_logit_final.sum() == 0:
        print(f"   WARN: Nessuna edge forte da posizione finale a logit '{target_logit_token}'")
        # Fallback: prendi la migliore in assoluto
        edges_to_logit_final = edges_to_logit
    
    best_idx = edges_to_logit_final.argmax().item()
    best_weight = edges_to_logit_final[best_idx].item()
    
    if best_weight < tau_edge:
        print(f"   WARN: Edge migliore troppo debole: {best_weight:.6f} < {tau_edge}")
        return None
    
    layer, pos, feat_idx = active_features[best_idx]
    feature_key = f"{layer.item()}_{feat_idx.item()}"
    
    seed_info = {
        'feature_key': feature_key,
        'layer': int(layer.item()),
        'position': int(pos.item()),
        'edge_weight_to_logit': float(best_weight),
        'logit_token': target_logit_token,
        'causal_metrics': causal_metrics.get(feature_key, {})
    }
    
    print(f"   Seed 'Say {target_logit_token}' trovato: {feature_key}")
    print(f"      Layer {seed_info['layer']}, Pos {seed_info['position']}, Edge weight: {best_weight:.4f}")
    
    return seed_info


def compute_causal_semantic_compatibility(
    seed_metrics: Dict,
    candidate_metrics: Dict,
    graph_data: Dict,
    feature_to_idx: Dict[str, int],
    tau_edge_strong: float = 0.05,
    weights: Dict[str, float] = None
) -> float:
    """
    Calcola compatibilità causale (60%) + semantica (40%) tra seed e candidato
    
    Args:
        seed_metrics: metriche causali del seed
        candidate_metrics: metriche causali del candidato
        graph_data: Attribution Graph
        feature_to_idx: mapping feature_key -> indice nella adjacency matrix
        tau_edge_strong: soglia per edge "forte"
        weights: pesi custom per componenti (default: None usa 60/40)
        
    Returns:
        Score compatibilità [0, 1]
    """
    if weights is None:
        weights = {
            'causal': 0.60,
            'semantic': 0.40,
            'direct_edge': 0.42,
            'neighborhood': 0.33,
            'position_prox': 0.25,
            'token_sim': 0.50,
            'layer_prox': 0.25,
            'consistency': 0.25
        }
    
    seed_key = f"{seed_metrics['layer']}_{seed_metrics.get('feature_id', '?')}"
    cand_key = f"{candidate_metrics['layer']}_{candidate_metrics.get('feature_id', '?')}"
    
    # ========== PARTE CAUSALE (60%) ==========
    
    # 1. Edge diretta tra seed e candidate
    direct_edge_score = 0.0
    if seed_key in feature_to_idx and cand_key in feature_to_idx:
        seed_idx = feature_to_idx[seed_key]
        cand_idx = feature_to_idx[cand_key]
        adjacency_matrix = graph_data['adjacency_matrix']
        
        # Edge da candidate a seed (backward growth)
        edge_weight = adjacency_matrix[seed_idx, cand_idx].item()
        direct_edge_score = min(1.0, edge_weight / tau_edge_strong)
    
    # 2. Vicinato causale simile (Jaccard)
    seed_neighbors = set()
    if 'top_parents' in seed_metrics:
        seed_neighbors.update([p[0] for p in seed_metrics['top_parents']])
    if 'top_children' in seed_metrics:
        seed_neighbors.update([c[0] for c in seed_metrics['top_children']])
    
    cand_neighbors = set()
    if 'top_parents' in candidate_metrics:
        cand_neighbors.update([p[0] for p in candidate_metrics['top_parents']])
    if 'top_children' in candidate_metrics:
        cand_neighbors.update([c[0] for c in candidate_metrics['top_children']])
    
    jaccard = 0.0
    if len(seed_neighbors | cand_neighbors) > 0:
        jaccard = len(seed_neighbors & cand_neighbors) / len(seed_neighbors | cand_neighbors)
    
    # 3. Position proximity
    seed_pos = seed_metrics.get('position', 0)
    cand_pos = candidate_metrics.get('position', 0)
    pos_distance = abs(seed_pos - cand_pos)
    position_compat = max(0, 1 - pos_distance / 5)
    
    causal_score = (
        direct_edge_score * weights['direct_edge'] +
        jaccard * weights['neighborhood'] +
        position_compat * weights['position_prox']
    )
    
    # ========== PARTE SEMANTICA (40%) ==========
    
    # 1. Token similarity
    seed_token = seed_metrics.get('most_common_peak', '')
    cand_token = candidate_metrics.get('most_common_peak', '')
    
    geographic_tokens = {'Dallas', 'Texas', 'Austin', 'state', 'State', 'city'}
    relation_tokens = {'of', 'in', 'is', 'the', ':', '.'}
    
    if seed_token in geographic_tokens and cand_token in geographic_tokens:
        token_compat = 0.8
    elif seed_token in relation_tokens and cand_token in relation_tokens:
        token_compat = 0.7
    elif seed_token == cand_token:
        token_compat = 1.0
    else:
        token_compat = 0.3
    
    # 2. Layer proximity
    seed_layer = seed_metrics.get('layer', 0)
    cand_layer = candidate_metrics.get('layer', 0)
    layer_distance = abs(seed_layer - cand_layer)
    layer_compat = max(0, 1 - layer_distance / 10)
    
    # 3. Consistency compatibility
    seed_cons = seed_metrics.get('conditional_consistency', 
                                seed_metrics.get('mean_consistency', 0))
    cand_cons = candidate_metrics.get('conditional_consistency',
                                     candidate_metrics.get('mean_consistency', 0))
    consistency_diff = abs(seed_cons - cand_cons)
    consistency_compat = max(0, 1 - consistency_diff)
    
    semantic_score = (
        token_compat * weights['token_sim'] +
        layer_compat * weights['layer_prox'] +
        consistency_compat * weights['consistency']
    )
    
    # ========== COMBINAZIONE FINALE ==========
    total_score = causal_score * weights['causal'] + semantic_score * weights['semantic']
    
    return total_score


def compute_edge_density(
    feature_keys: List[str],
    graph_data: Dict,
    feature_to_idx: Dict[str, int],
    tau_edge: float = 0.01
) -> float:
    """
    Calcola densità delle edge forti tra un gruppo di feature.
    Usa il valore assoluto dei pesi e NON conta la diagonale.
    
    Args:
        feature_keys: lista di feature_key
        graph_data: Attribution Graph
        feature_to_idx: mapping feature_key -> indice
        tau_edge: soglia per edge "forte" (applicata a |w|)
        
    Returns:
        Densità [0, 1]: (# edge forti) / (# edge possibili)
    """
    if len(feature_keys) <= 1:
        return 1.0
    
    # Trova indici delle feature
    indices = []
    for fkey in feature_keys:
        if fkey in feature_to_idx:
            indices.append(feature_to_idx[fkey])
    
    if len(indices) <= 1:
        return 1.0
    
    adjacency_matrix = graph_data['adjacency_matrix']
    
    # Estrai submatrix in valore assoluto
    submatrix = adjacency_matrix[indices, :][:, indices].abs()
    
    # Escludi diagonale (no self-loops)
    n = len(indices)
    try:
        submatrix.fill_diagonal_(0)
    except Exception:
        # Fallback: azzera con maschera
        import torch
        diag_mask = torch.eye(n, dtype=torch.bool, device=submatrix.device)
        submatrix = submatrix.masked_fill(diag_mask, 0.0)
    
    # Conta edge forti su |w| > tau_edge
    strong_edges = (submatrix > tau_edge).sum().item()
    max_edges = n * (n - 1)  # Grafo diretto, no self-loops
    
    density = strong_edges / max_edges if max_edges > 0 else 0.0
    
    return density


if __name__ == "__main__":
    # Test loading
    graph_data = load_attribution_graph("output/example_graph.pt", verbose=True)
    
    if graph_data is not None:
        causal_metrics = compute_causal_metrics(graph_data, tau_edge=0.01, top_k=5)
        
        # Test find_say_austin_seed
        say_austin = find_say_austin_seed(graph_data, causal_metrics, "Austin")
        
        if say_austin:
            print(f"\n✅ Test completato con successo!")
            print(f"   Say Austin seed: {say_austin['feature_key']}")
        else:
            print(f"\n⚠️ Test completato ma Say Austin non trovato")
    else:
        print(f"\n❌ Test fallito: grafo non caricato")

