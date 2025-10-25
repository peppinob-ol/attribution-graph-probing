"""Funzioni di ricalcolo per dry-run e analisi parametriche"""
from typing import Dict, List, Tuple, Set, Optional
from collections import Counter, defaultdict
import numpy as np


def compute_compatibility(
    seed_personality: Dict,
    candidate_personality: Dict,
    causal_weight: float = 0.60,
    adjacency_matrix = None,
    feature_to_idx: Dict = None,
    tau_edge_strong: float = 0.05
) -> Tuple[float, Dict]:
    """
    Calcola compatibilità causale+semantica
    
    Returns:
        (total_score, breakdown_dict)
    """
    seed_key = f"{seed_personality['layer']}_{seed_personality['feature_id']}"
    cand_key = f"{candidate_personality['layer']}_{candidate_personality['feature_id']}"
    
    # PARTE CAUSALE (60% default)
    causal_score = 0.0
    breakdown = {'causal': {}, 'semantic': {}}
    
    if adjacency_matrix is not None and feature_to_idx is not None:
        if seed_key in feature_to_idx and cand_key in feature_to_idx:
            seed_idx = feature_to_idx[seed_key]
            cand_idx = feature_to_idx[cand_key]
            
            # Edge diretta
            edge_weight = adjacency_matrix[seed_idx, cand_idx].item()
            direct_edge_score = min(1.0, edge_weight / tau_edge_strong)
            if edge_weight > 0.1:
                direct_edge_score = min(1.0, direct_edge_score * 1.5)
            breakdown['causal']['direct_edge'] = direct_edge_score
            
            # Vicinato (Jaccard) - semplificato
            jaccard = 0.0  # TODO: implementare con top_parents/children
            breakdown['causal']['jaccard'] = jaccard
            
            # Position proximity
            seed_pos = seed_personality.get('position', 0)
            cand_pos = candidate_personality.get('position', 0)
            pos_distance = abs(seed_pos - cand_pos)
            position_compat = max(0, 1 - pos_distance / 5)
            breakdown['causal']['position'] = position_compat
            
            causal_score = (
                direct_edge_score * 0.42 +
                jaccard * 0.33 +
                position_compat * 0.25
            )
    else:
        # Fallback: solo position
        seed_pos = seed_personality.get('position', 0)
        cand_pos = candidate_personality.get('position', 0)
        pos_distance = abs(seed_pos - cand_pos)
        causal_score = max(0, 1 - pos_distance / 5)
        breakdown['causal']['position_only'] = causal_score
    
    # PARTE SEMANTICA (40% default)
    seed_token = seed_personality['most_common_peak']
    cand_token = candidate_personality['most_common_peak']
    
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
    breakdown['semantic']['token'] = token_compat
    
    layer_distance = abs(seed_personality['layer'] - candidate_personality['layer'])
    layer_compat = max(0, 1 - layer_distance / 10)
    breakdown['semantic']['layer'] = layer_compat
    
    seed_cons = seed_personality.get('conditional_consistency', 
                                     seed_personality.get('mean_consistency', 0))
    cand_cons = candidate_personality.get('conditional_consistency',
                                          candidate_personality.get('mean_consistency', 0))
    consistency_diff = abs(seed_cons - cand_cons)
    consistency_compat = max(0, 1 - consistency_diff)
    breakdown['semantic']['consistency'] = consistency_compat
    
    semantic_score = (
        token_compat * 0.50 +
        layer_compat * 0.25 +
        consistency_compat * 0.25
    )
    
    # Combinazione finale
    semantic_weight = 1.0 - causal_weight
    total = causal_score * causal_weight + semantic_score * semantic_weight
    
    breakdown['total'] = total
    breakdown['causal_score'] = causal_score
    breakdown['semantic_score'] = semantic_score
    
    return total, breakdown


def compute_coherence(
    members: List[str],
    personalities: Dict,
    graph_data: Optional[Dict] = None,
    tau_edge: float = 0.01
) -> Tuple[float, Dict]:
    """
    Calcola coerenza supernodo
    
    Returns:
        (coherence, breakdown_dict)
    """
    if len(members) <= 1:
        return 1.0, {'single_member': True}
    
    # Raccogli statistiche
    consistencies = []
    peak_tokens = []
    layers = []
    
    for member_key in members:
        if member_key in personalities:
            p = personalities[member_key]
            consistency_val = p.get('conditional_consistency', p.get('consistency_score', 0))
            consistencies.append(consistency_val)
            peak_tokens.append(p['most_common_peak'])
            layers.append(p['layer'])
    
    breakdown = {}
    
    # Factor 1: Consistency homogeneity
    if len(consistencies) > 1:
        consistency_std = np.std(consistencies, ddof=1)
        consistency_coherence = max(0, 1 - consistency_std)
    else:
        consistency_coherence = 1.0
    breakdown['consistency_homogeneity'] = consistency_coherence
    
    # Factor 2: Token diversity (target 50%)
    token_diversity = len(set(peak_tokens)) / len(peak_tokens) if peak_tokens else 0
    diversity_coherence = max(0, 1 - abs(token_diversity - 0.5))
    breakdown['token_diversity'] = diversity_coherence
    breakdown['token_diversity_raw'] = token_diversity
    
    # Factor 3: Layer span
    layer_span = max(layers) - min(layers) if layers else 0
    span_coherence = max(0, 1 - layer_span / 15)
    breakdown['layer_span'] = span_coherence
    breakdown['layer_span_raw'] = layer_span
    
    # Factor 4: Causal density (opzionale)
    causal_density = 0.5  # default
    if graph_data is not None:
        try:
            from scripts.causal_utils import compute_edge_density
            causal_density = compute_edge_density(
                members,
                graph_data,
                graph_data.get('feature_to_idx', {}),
                tau_edge=tau_edge
            )
        except:
            pass
    breakdown['causal_density'] = causal_density
    
    # Combinazione
    total_coherence = (
        consistency_coherence * 0.30 +
        diversity_coherence * 0.20 +
        span_coherence * 0.20 +
        causal_density * 0.30
    )
    breakdown['total'] = total_coherence
    
    return total_coherence, breakdown


def identify_quality_residuals(
    personalities: Dict,
    cicciotti: Dict,
    thresholds: Dict
) -> Tuple[List[str], Dict]:
    """
    Identifica residui di qualità con soglie configurabili
    
    Returns:
        (quality_residuals, stats_dict)
    """
    tau_inf = thresholds.get('tau_inf', 0.000194)
    tau_aff = thresholds.get('tau_aff', 0.65)
    tau_inf_very_high = thresholds.get('tau_inf_very_high', 0.025)
    
    # Feature già usate
    used_features = set()
    for cicciotto in cicciotti.values():
        for member in cicciotto.get('members', []):
            used_features.add(member)
    
    # Ammissione
    admitted = []
    for fkey, personality in personalities.items():
        logit_inf = personality.get('output_impact', 0)
        max_aff = personality.get('max_affinity', 0)
        token = personality.get('most_common_peak', '')
        
        # Criteri OR
        if logit_inf >= tau_inf:
            admitted.append(fkey)
        elif max_aff >= tau_aff:
            admitted.append(fkey)
        
        # Filtro BOS
        if token == '<BOS>' and logit_inf < tau_inf_very_high:
            if fkey in admitted:
                admitted.remove(fkey)
    
    # Residui
    quality_residuals = [f for f in admitted if f not in used_features]
    
    stats = {
        'total_admitted': len(admitted),
        'used_in_cicciotti': len(used_features),
        'quality_residuals': len(quality_residuals),
    }
    
    return quality_residuals, stats


def cluster_residuals(
    residuals: List[str],
    personalities: Dict,
    min_cluster_size: int = 3,
    layer_group_span: int = 3,
    node_inf_high: float = 0.10,
    node_inf_med: float = 0.01,
    min_frequency_ratio: float = 0.02,
    min_frequency_absolute: int = 3
) -> Dict:
    """
    Clustering multi-dimensionale dei residui
    
    Returns:
        clusters_dict
    """
    # Auto-detection token
    token_counts = Counter()
    for fkey in residuals:
        if fkey in personalities:
            token = personalities[fkey].get('most_common_peak', '')
            token_counts[token] += 1
    
    structural_tokens = {'<BOS>', ':', '.', 'the', 'of', 'is', 'in', 'a', 'and'}
    
    min_freq = max(min_frequency_absolute, int(len(residuals) * min_frequency_ratio))
    semantic_tokens = {token for token, count in token_counts.items()
                      if count >= min_freq and token not in structural_tokens}
    
    # Clustering
    clusters = defaultdict(list)
    
    for fkey in residuals:
        if fkey not in personalities:
            continue
        
        p = personalities[fkey]
        layer = p['layer']
        token = p.get('most_common_peak', '')
        
        # Layer group
        layer_group = f"L{(layer//layer_group_span)*layer_group_span}-{(layer//layer_group_span)*layer_group_span+layer_group_span-1}"
        
        # Token classification
        if token in structural_tokens:
            cluster_token = token
        elif token in semantic_tokens:
            cluster_token = token
        else:
            cluster_token = 'RARE'
        
        # Causal tier
        node_inf = p.get('node_influence', 0)
        if node_inf > node_inf_high:
            causal_tier = 'HIGH'
        elif node_inf > node_inf_med:
            causal_tier = 'MED'
        else:
            causal_tier = 'LOW'
        
        cluster_key = f"{layer_group}_{cluster_token}_{causal_tier}"
        clusters[cluster_key].append(fkey)
    
    # Filtra piccoli
    valid_clusters = {}
    cluster_id = 1
    for cluster_key, members in clusters.items():
        if len(members) >= min_cluster_size:
            valid_clusters[f"COMP_{cluster_id}"] = {
                'members': members,
                'n_members': len(members),
                'cluster_signature': cluster_key,
            }
            cluster_id += 1
    
    return valid_clusters


def merge_clusters_jaccard(
    clusters: Dict,
    jaccard_threshold: float = 0.70
) -> Tuple[Dict, Dict]:
    """
    Merge cluster con Jaccard >= threshold
    
    Returns:
        (merged_clusters, merge_log)
    """
    def jaccard(a, b):
        sa, sb = set(a), set(b)
        u = len(sa | sb)
        return (len(sa & sb) / u) if u else 0.0
    
    comp_items = list(clusters.items())
    merged = {}
    used = set()
    merge_log = {}
    
    for i in range(len(comp_items)):
        if comp_items[i][0] in used:
            continue
        
        base_id, base = comp_items[i]
        group_members = set(base['members'])
        merged_ids = []
        
        for j in range(i+1, len(comp_items)):
            cid, c = comp_items[j]
            if cid in used:
                continue
            
            j_sim = jaccard(base['members'], c['members'])
            if j_sim >= jaccard_threshold:
                group_members |= set(c['members'])
                used.add(cid)
                merged_ids.append((cid, j_sim))
        
        merged_id = base_id
        merged[merged_id] = dict(base)
        merged[merged_id]['members'] = list(group_members)
        merged[merged_id]['n_members'] = len(group_members)
        
        if merged_ids:
            merge_log[merged_id] = {
                'base': base_id,
                'merged': merged_ids,
                'n_members_before': len(base['members']),
                'n_members_after': len(group_members)
            }
    
    return merged, merge_log

