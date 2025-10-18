# Code Snippets: Implementazione Sistema Labelling

## 🎭 Fase 1: Analisi Antropologica

### 1.1 Calcolo Personalità Feature

```python
def analyze_feature_personalities(self) -> Dict:
    """
    Calcola 'personalità' per ogni feature basata su comportamento cross-prompt
    """
    # Raggruppa dati per feature unica
    feature_data = defaultdict(list)
    
    for record in self.acts_data:
        feature_key = (record['layer'], record['feature'])
        feature_data[feature_key].append(record)
    
    personalities = {}
    
    for feature_key, records in feature_data.items():
        layer, feature_id = feature_key
        
        # Raccogli metriche comportamentali
        cosine_values = []
        activations = []
        peak_tokens = []
        
        for r in records:
            if r.get('cosine_similarity'):
                try:
                    cosine_values.append(float(r['cosine_similarity']))
                except ValueError:
                    pass
            
            if r.get('nuova_somma_sequenza'):
                try:
                    activations.append(float(r['nuova_somma_sequenza']))
                except ValueError:
                    pass
            
            if r.get('peak_token'):
                peak_tokens.append(r['peak_token'])
        
        # Threshold adattivo per questa feature
        activation_threshold = self._compute_adaptive_threshold(activations)
        
        # Filtra attivazioni attive
        active_indices = [i for i, act in enumerate(activations) 
                         if act > activation_threshold]
        active_cosines = [cosine_values[i] for i in active_indices 
                         if i < len(cosine_values)]
        
        # Calcola personalità
        personality = {
            'layer': int(layer),
            'feature_id': feature_id,
            'n_observations': len(records),
            
            # NUOVE METRICHE (vs vecchia consistency_score)
            'mean_consistency': sum(cosine_values) / len(cosine_values) if cosine_values else 0,
            'max_affinity': max(cosine_values) if cosine_values else 0,
            'conditional_consistency': sum(active_cosines) / len(active_cosines) if active_cosines else 0,
            'activation_threshold': activation_threshold,
            
            'consistency_std': self._std(cosine_values) if len(cosine_values) > 1 else 0,
            'most_common_peak': Counter(peak_tokens).most_common(1)[0][0] if peak_tokens else 'unknown',
        }
        
        personalities[feature_key] = personality
    
    return personalities
```

### 1.2 Threshold Adattivo (Otsu + Percentile)

```python
def _compute_adaptive_threshold(self, activations):
    """
    Threshold ibrido: min(percentile 75, detection automatica Otsu)
    """
    if len(activations) < 3:
        return 0
    
    # Percentile 75
    thr_p75 = self._percentile(activations, 75)
    
    # Detection automatica con Otsu (fallback a p75 se fallisce)
    try:
        from skimage.filters import threshold_otsu
        import numpy as np
        thr_auto = threshold_otsu(np.array(activations))
    except:
        thr_auto = thr_p75
    
    # Prendi il minimo (più conservativo)
    return min(thr_p75, thr_auto)

def _percentile(self, values, percentile):
    """Calcola percentile manualmente"""
    if not values:
        return 0
    sorted_vals = sorted(values)
    k = (len(sorted_vals) - 1) * percentile / 100
    f = int(k)
    c = k - f
    if f == len(sorted_vals) - 1:
        return sorted_vals[f]
    return sorted_vals[f] * (1 - c) + sorted_vals[f + 1] * c
```

### 1.3 Classificazione Archetipi Narrativi

```python
def identify_narrative_archetypes(self, personalities: Dict):
    """
    Classifica feature in archetipi basandosi su soglie empiriche (percentile 75)
    """
    # Calcola soglie empiriche
    mean_consistencies = [p['mean_consistency'] for p in personalities.values()]
    max_affinities = [p['max_affinity'] for p in personalities.values()]
    label_affinities = [p['label_affinity'] for p in personalities.values()]
    
    high_mean_consistency = self._percentile(mean_consistencies, 75)
    high_max_affinity = self._percentile(max_affinities, 75)
    high_label_affinity = self._percentile(label_affinities, 75)
    
    archetypes = {
        'semantic_anchors': [],
        'stable_contributors': [],
        'contextual_specialists': [],
        'computational_helpers': [],
        'outliers': []
    }
    
    for feature_key, personality in personalities.items():
        # Semantic Anchors: alta mean consistency + alta max affinity + alta label affinity
        if (personality['mean_consistency'] > high_mean_consistency and 
            personality['max_affinity'] > high_max_affinity and
            personality['label_affinity'] > high_label_affinity):
            archetypes['semantic_anchors'].append({
                'feature_key': f"{feature_key[0]}_{feature_key[1]}",
                'personality': personality
            })
        
        # Stable Contributors: alta mean consistency ma max affinity media
        elif personality['mean_consistency'] > high_mean_consistency:
            archetypes['stable_contributors'].append({
                'feature_key': f"{feature_key[0]}_{feature_key[1]}",
                'personality': personality
            })
        
        # Contextual Specialists: bassa mean consistency ma alta max affinity
        elif (personality['mean_consistency'] < high_mean_consistency and 
              personality['max_affinity'] > high_max_affinity):
            archetypes['contextual_specialists'].append({
                'feature_key': f"{feature_key[0]}_{feature_key[1]}",
                'personality': personality
            })
        
        # Altri: computational helpers o outliers
        else:
            archetypes['outliers'].append({
                'feature_key': f"{feature_key[0]}_{feature_key[1]}",
                'personality': personality
            })
    
    return archetypes
```

---

## 🌱 Fase 2: Costruzione Cicciotti

### 2.1 Seed Selection (Backward from Logit)

```python
def find_say_austin_seed(self) -> Optional[Dict]:
    """
    Trova seed primario: feature alla posizione finale con edge diretta forte a logit "Austin"
    """
    if self.graph_data is None or not self.causal_metrics:
        return None
    
    try:
        from causal_utils import find_say_austin_seed as find_seed_util
        
        say_austin_info = find_seed_util(
            self.graph_data,
            self.causal_metrics,
            target_logit_token="Austin",
            tau_edge=0.01
        )
        
        if say_austin_info:
            # Arricchisci con personality
            fkey = say_austin_info['feature_key']
            if fkey in self.personalities:
                say_austin_info['personality'] = self.personalities[fkey]
            
            return say_austin_info
        
    except Exception as e:
        print(f"⚠️ Errore find_say_austin_seed: {e}")
    
    return None

def select_semantic_seeds(self) -> List[Dict]:
    """
    BACKWARD FROM LOGIT SEED SELECTION
    
    1. Prima: Say Austin (edge diretta a logit)
    2. Poi: Massima node_influence (backward propagation)
    3. Diversità per layer e position
    """
    selected_seeds = []
    
    # Step 1: Trova Say Austin come primo seed
    say_austin = self.find_say_austin_seed()
    
    if say_austin and 'personality' in say_austin:
        seed_dict = {
            'feature_key': say_austin['feature_key'],
            'personality': say_austin['personality'],
            'logit_influence': say_austin['personality'].get('output_impact', 0),
            'node_influence': say_austin['causal_metrics'].get('node_influence', 0),
            'max_affinity': say_austin['personality'].get('max_affinity', 0),
            'layer': say_austin['layer'],
            'peak_token': say_austin['personality'].get('most_common_peak', '?'),
            'position': say_austin['position'],
            'is_say_austin': True
        }
        selected_seeds.append(seed_dict)
    
    # Step 2: Carica feature ammesse e ordina per node_influence
    with open("output/robust_thresholds.json", 'r') as f:
        thresholds_data = json.load(f)
    
    admitted_features = set(thresholds_data['admitted_features']['total'])
    
    # Carica logit influence
    metrics_df = pd.read_csv("output/graph_feature_static_metrics (1).csv")
    metrics_df['feature_key'] = metrics_df['layer'].astype(str) + '_' + metrics_df['feature'].astype(str)
    
    # Ordina per node_influence DESC, poi max_affinity DESC
    scored_seeds = []
    for fkey in admitted_features:
        if fkey not in self.personalities:
            continue
        
        personality = self.personalities[fkey]
        
        # Trova logit influence
        influence_row = metrics_df[metrics_df['feature_key'] == fkey]
        if len(influence_row) == 0:
            continue
        logit_inf = influence_row.iloc[0]['logit_influence']
        
        scored_seeds.append({
            'feature_key': fkey,
            'personality': personality,
            'logit_influence': logit_inf,
            'node_influence': personality.get('node_influence', 0),
            'max_affinity': personality.get('max_affinity', 0),
            'layer': personality['layer'],
            'position': personality.get('position', 0),
            'peak_token': personality['most_common_peak']
        })
    
    scored_seeds.sort(key=lambda x: (x.get('node_influence', 0), x['max_affinity']), reverse=True)
    
    # Step 3: Diversificazione
    used_layers = set([s['layer'] for s in selected_seeds])
    used_positions = set([s.get('position', -1) for s in selected_seeds])
    
    for seed in scored_seeds:
        if seed['feature_key'] in [s['feature_key'] for s in selected_seeds]:
            continue
        
        layer = seed['layer']
        position = seed.get('position', -1)
        
        # Primi 20 sempre, poi preferisci diversità
        if len(selected_seeds) < 20:
            selected_seeds.append(seed)
            used_layers.add(layer)
            used_positions.add(position)
        elif layer not in used_layers or position not in used_positions:
            selected_seeds.append(seed)
            used_layers.add(layer)
            used_positions.add(position)
        
        # Max 50 seed
        if len(selected_seeds) >= 50:
            break
    
    return selected_seeds
```

### 2.2 Crescita Supernodo con Controllo Duplicati

```python
def grow_cicciotto_supernode(self, seed: Dict, global_used_features: set = None) -> Dict:
    """
    Crescita narrativa di un singolo supernodo cicciotto
    
    Strategia:
    1. Bootstrap (3 iterazioni): solo edge dirette forti, 2-hop backward
    2. Normale: compatibilità causale+semantica
    3. Stop quando coerenza scende sotto soglia
    """
    seed_key = seed['feature_key']
    seed_personality = seed['personality']
    
    # Inizializza supernodo
    cicciotto = {
        'seed': seed_key,
        'members': [seed_key],
        'narrative_theme': seed_personality['most_common_peak'],
        'seed_layer': seed_personality['layer'],
        'seed_logit_influence': seed['logit_influence'],
        'total_influence_score': seed['logit_influence'],
        'coherence_history': [1.0]
    }
    
    # Aggiungi seed al set globale
    if global_used_features is not None:
        global_used_features.add(seed_key)
    
    # Crescita iterativa
    max_iterations = 20
    min_coherence = 0.50
    bootstrap_iterations = 3
    
    if global_used_features is None:
        global_used_features = set()
    
    for iteration in range(max_iterations):
        best_candidate = None
        best_compatibility = 0
        
        # Modalità bootstrap causale (prime 3 iterazioni con 2-hop)
        is_bootstrap = iteration < bootstrap_iterations and self.graph_data is not None
        
        # COSTRUISCI POOL CANDIDATI DINAMICO
        candidates = []
        
        if self.graph_data and self.causal_metrics:
            # BACKWARD: raccogli genitori causali dei membri attuali
            parent_scores = {}
            for member_key in cicciotto['members']:
                if member_key in self.causal_metrics:
                    for parent_key, weight in self.causal_metrics[member_key].get('top_parents', []):
                        if parent_key in self.personalities:
                            parent_scores[parent_key] = max(parent_scores.get(parent_key, 0.0), float(weight))
            
            # Durante BOOTSTRAP aggiungi anche genitori dei genitori (2-hop)
            if is_bootstrap and len(parent_scores) > 0:
                second_hop_scores = {}
                for pkey in list(parent_scores.keys()):
                    if pkey in self.causal_metrics:
                        for pp_key, w2 in self.causal_metrics[pkey].get('top_parents', []):
                            if pp_key in self.personalities:
                                # Peso ridotto per 2-hop
                                second_hop_scores[pp_key] = max(second_hop_scores.get(pp_key, 0.0), float(w2) * 0.5)
                # Unisci mantenendo il max
                for k, v in second_hop_scores.items():
                    parent_scores[k] = max(parent_scores.get(k, 0.0), v)
            
            # Ordina per peso edge e aggiungi come candidati
            for parent_key, weight in sorted(parent_scores.items(), key=lambda x: x[1], reverse=True):
                if global_used_features and parent_key in global_used_features:
                    continue
                candidates.append({
                    'feature_key': parent_key,
                    'personality': self.personalities[parent_key],
                    'type': 'causal_parent',
                    'edge_weight': weight
                })
        
        # Seleziona miglior candidato
        for candidate in candidates:
            # CONTROLLO DUPLICATI: Skip se già nel supernodo O già utilizzato globalmente
            if (candidate['feature_key'] in cicciotto['members'] or 
                candidate['feature_key'] in global_used_features):
                continue
            
            # Bootstrap causale: usa solo edge diretta
            if is_bootstrap:
                seed_key_iter = cicciotto['seed']
                cand_key = candidate['feature_key']
                
                if seed_key_iter in self.feature_to_idx and cand_key in self.feature_to_idx:
                    seed_idx = self.feature_to_idx[seed_key_iter]
                    cand_idx = self.feature_to_idx[cand_key]
                    adjacency_matrix = self.graph_data['adjacency_matrix']
                    
                    # Edge da candidate a seed (backward)
                    edge_weight = adjacency_matrix[seed_idx, cand_idx].item()
                    
                    if edge_weight > 0.03:
                        compatibility = edge_weight * 10  # Normalizza
                    else:
                        continue
                else:
                    continue
            else:
                # Modalità normale: calcola compatibilità causale+semantica
                compatibility = self.compute_narrative_compatibility(
                    cicciotto, candidate
                )
            
            # Soglia più permissiva per bootstrap
            threshold = 0.3 if is_bootstrap else 0.45
            if compatibility > best_compatibility and compatibility > threshold:
                best_compatibility = compatibility
                best_candidate = candidate
        
        # Aggiungi miglior candidato se sufficientemente compatibile
        threshold_final = 0.3 if is_bootstrap else 0.45
        if best_candidate and best_compatibility > threshold_final:
            cicciotto['members'].append(best_candidate['feature_key'])
            
            # AGGIUNGI SUBITO AL SET GLOBALE
            if global_used_features is not None:
                global_used_features.add(best_candidate['feature_key'])
            
            # Update score
            candidate_consistency = best_candidate['personality'].get('conditional_consistency',
                                    best_candidate['personality'].get('mean_consistency', 0))
            cicciotto['total_influence_score'] += candidate_consistency * best_compatibility
            
            # Calcola nuova coerenza
            new_coherence = self.compute_supernode_coherence(cicciotto)
            cicciotto['coherence_history'].append(new_coherence)
            
            # Stop se coerenza scende troppo
            if (not is_bootstrap) and new_coherence < min_coherence:
                # Rimuovi ultimo membro
                removed_member = cicciotto['members'].pop()
                if global_used_features is not None:
                    global_used_features.discard(removed_member)
                cicciotto['coherence_history'].pop()
                break
        else:
            # Nessun candidato compatibile
            break
    
    cicciotto['final_coherence'] = cicciotto['coherence_history'][-1]
    cicciotto['growth_iterations'] = len(cicciotto['coherence_history']) - 1
    
    return cicciotto
```

### 2.3 Compatibilità Narrativa (60% Causale + 40% Semantica)

```python
def compute_narrative_compatibility(self, cicciotto: Dict, candidate: Dict) -> float:
    """
    Calcola compatibilità CAUSALE (60%) + SEMANTICA (40%)
    
    CAUSALE:
    - Edge diretta (25%)
    - Vicinato causale simile (20%)
    - Position proximity (15%)
    
    SEMANTICA:
    - Token similarity (20%)
    - Layer proximity (10%)
    - Consistency compatibility (10%)
    """
    seed_personality = self.personalities[cicciotto['seed']]
    candidate_personality = candidate['personality']
    seed_key = cicciotto['seed']
    cand_key = candidate['feature_key']
    
    # ========== PARTE CAUSALE (60%) ==========
    causal_score = 0.0
    
    if self.graph_data is not None and seed_key in self.feature_to_idx and cand_key in self.feature_to_idx:
        seed_idx = self.feature_to_idx[seed_key]
        cand_idx = self.feature_to_idx[cand_key]
        adjacency_matrix = self.graph_data['adjacency_matrix']
        
        # 1. Edge diretta da candidate a seed (backward growth) - 25%
        tau_edge_strong = 0.05
        edge_weight = adjacency_matrix[seed_idx, cand_idx].item()
        direct_edge_score = min(1.0, edge_weight / tau_edge_strong)
        
        # Anchor boost: se edge molto forte (>0.1), aumenta il peso
        if edge_weight > 0.1:
            direct_edge_score = min(1.0, direct_edge_score * 1.5)
        
        # 2. Vicinato causale simile (Jaccard) - 20%
        seed_neighbors = set()
        if seed_key in self.causal_metrics:
            seed_neighbors.update([p[0] for p in self.causal_metrics[seed_key].get('top_parents', [])])
            seed_neighbors.update([c[0] for c in self.causal_metrics[seed_key].get('top_children', [])])
        
        cand_neighbors = set()
        if cand_key in self.causal_metrics:
            cand_neighbors.update([p[0] for p in self.causal_metrics[cand_key].get('top_parents', [])])
            cand_neighbors.update([c[0] for c in self.causal_metrics[cand_key].get('top_children', [])])
        
        jaccard = 0.0
        if len(seed_neighbors | cand_neighbors) > 0:
            jaccard = len(seed_neighbors & cand_neighbors) / len(seed_neighbors | cand_neighbors)
        
        # 3. Position proximity - 15%
        seed_pos = seed_personality.get('position', 0)
        cand_pos = candidate_personality.get('position', 0)
        pos_distance = abs(seed_pos - cand_pos)
        position_compat = max(0, 1 - pos_distance / 5)
        
        causal_score = (
            direct_edge_score * 0.42 +
            jaccard * 0.33 +
            position_compat * 0.25
        )
    else:
        # Fallback se grafo non disponibile
        seed_pos = seed_personality.get('position', 0)
        cand_pos = candidate_personality.get('position', 0)
        pos_distance = abs(seed_pos - cand_pos)
        causal_score = max(0, 1 - pos_distance / 5)
    
    # ========== PARTE SEMANTICA (40%) ==========
    
    # 1. Token similarity - 20%
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
    
    # 2. Layer proximity - 10%
    layer_distance = abs(seed_personality['layer'] - candidate_personality['layer'])
    layer_compat = max(0, 1 - layer_distance / 10)
    
    # 3. Consistency compatibility - 10%
    seed_cons = seed_personality.get('conditional_consistency',
                                    seed_personality.get('mean_consistency', 0))
    cand_cons = candidate_personality.get('conditional_consistency',
                                         candidate_personality.get('mean_consistency', 0))
    consistency_diff = abs(seed_cons - cand_cons)
    consistency_compat = max(0, 1 - consistency_diff)
    
    semantic_score = (
        token_compat * 0.50 +
        layer_compat * 0.25 +
        consistency_compat * 0.25
    )
    
    # ========== COMBINAZIONE FINALE ==========
    total_compatibility = causal_score * 0.60 + semantic_score * 0.40
    
    return total_compatibility
```

### 2.4 Coerenza del Supernodo

```python
def compute_supernode_coherence(self, cicciotto: Dict) -> float:
    """
    Calcola coerenza narrativa + causale del supernodo
    
    Metrics:
    - Consistency variance tra membri (semantica) - 30%
    - Peak token diversity (semantica) - 20%
    - Layer span (semantica) - 20%
    - Causal edge density (causale) - 30%
    """
    if len(cicciotto['members']) <= 1:
        return 1.0
    
    # Raccogli statistiche membri
    consistencies = []
    peak_tokens = []
    layers = []
    
    for member_key in cicciotto['members']:
        personality = self.personalities[member_key]
        consistency_val = personality.get('conditional_consistency', 
                                         personality.get('consistency_score', 0))
        consistencies.append(consistency_val)
        peak_tokens.append(personality['most_common_peak'])
        layers.append(personality['layer'])
    
    # Factor 1: Consistency homogeneity
    consistency_std = self._std(consistencies) if len(consistencies) > 1 else 0
    consistency_coherence = max(0, 1 - consistency_std)
    
    # Factor 2: Peak token diversity (target 50%)
    token_diversity = len(set(peak_tokens)) / len(peak_tokens)
    diversity_coherence = max(0, 1 - abs(token_diversity - 0.5))
    
    # Factor 3: Layer span (preferisce compattezza)
    layer_span = max(layers) - min(layers) if layers else 0
    span_coherence = max(0, 1 - layer_span / 15)
    
    # Factor 4: Causal edge density
    causal_density = 0.5  # Default se grafo non disponibile
    if self.graph_data is not None and len(cicciotto['members']) > 1:
        try:
            from causal_utils import compute_edge_density
            causal_density = compute_edge_density(
                cicciotto['members'],
                self.graph_data,
                self.feature_to_idx,
                tau_edge=0.01
            )
        except Exception:
            pass
    
    # Combinazione finale
    total_coherence = (
        consistency_coherence * 0.30 +
        diversity_coherence * 0.20 +
        span_coherence * 0.20 +
        causal_density * 0.30
    )
    
    return total_coherence
```

---

## 🏭 Fase 3: Clustering Residui

### 3.1 Auto-Detection Token Significativi

```python
def identify_significant_tokens(self, features):
    """Identifica automaticamente token strutturali vs semantici"""
    
    # Raccogli tutti i token
    token_counts = Counter()
    for feature_key in features:
        if feature_key in self.personalities:
            token = self.personalities[feature_key]['most_common_peak']
            token_counts[token] += 1
    
    # Token strutturali sempre presenti
    structural_tokens = {'<BOS>', ':', '.', 'the', 'of', 'is', 'in', 'a', 'and'}
    
    # Token semantici: frequenti ma non strutturali
    min_frequency = max(3, len(features) // 50)  # 2% delle feature
    
    semantic_tokens = set()
    for token, count in token_counts.items():
        if count >= min_frequency and token not in structural_tokens:
            semantic_tokens.add(token)
    
    # Token rari: tutto il resto
    rare_tokens = set(token_counts.keys()) - structural_tokens - semantic_tokens
    
    return structural_tokens, semantic_tokens, rare_tokens
```

### 3.2 Clustering Multi-Dimensionale

```python
def quality_clustering(self, features):
    """Clustering ottimizzato per feature di qualità - SENZA HARDCODING"""
    
    if len(features) < 10:
        return {}
    
    # Auto-detection token
    structural_tokens, semantic_tokens, rare_tokens = self.identify_significant_tokens(features)
    
    # Raggruppa per caratteristiche simili
    clusters = defaultdict(list)
    
    for feature_key in features:
        if feature_key not in self.personalities:
            continue
        
        personality = self.personalities[feature_key]
        
        # Dimensione 1: Layer group (gruppi di 3)
        layer = personality['layer']
        layer_group = f"L{(layer//3)*3}-{(layer//3)*3+2}"
        
        # Dimensione 2: Token classification
        token = personality['most_common_peak']
        if token in structural_tokens:
            cluster_token = token
        elif token in semantic_tokens:
            cluster_token = token
        else:
            cluster_token = 'RARE'
        
        # Dimensione 3: Causal tier
        node_inf = personality.get('node_influence', 0)
        tau_node_high = 0.1
        tau_node_med = 0.01
        
        if node_inf > tau_node_high:
            causal_tier = 'HIGH'
        elif node_inf > tau_node_med:
            causal_tier = 'MED'
        else:
            causal_tier = 'LOW'
        
        cluster_key = f"{layer_group}_{cluster_token}_{causal_tier}"
        clusters[cluster_key].append(feature_key)
    
    # Filtra cluster troppo piccoli
    valid_clusters = {}
    cluster_id = 1
    
    for cluster_key, members in clusters.items():
        if len(members) >= 3:
            # Calcola causal_connectivity se disponibile
            causal_connectivity = 0.0
            try:
                from causal_utils import load_attribution_graph, compute_edge_density
                
                graph_data = load_attribution_graph("output/example_graph.pt")
                if graph_data is not None:
                    feature_to_idx = {}
                    for i, (layer, pos, feat_idx) in enumerate(graph_data['active_features']):
                        fkey = f"{layer.item()}_{feat_idx.item()}"
                        feature_to_idx[fkey] = i
                    
                    causal_connectivity = compute_edge_density(
                        members,
                        graph_data,
                        feature_to_idx,
                        tau_edge=0.01
                    )
            except:
                pass
            
            valid_clusters[f"COMP_{cluster_id}"] = {
                'type': 'computational',
                'members': members,
                'n_members': len(members),
                'cluster_signature': cluster_key,
                'avg_layer': sum(self.personalities[m]['layer'] for m in members) / len(members),
                'dominant_token': Counter([self.personalities[m]['most_common_peak'] for m in members]).most_common(1)[0][0],
                'avg_consistency': sum(self.personalities[m].get('conditional_consistency', 0) for m in members) / len(members),
                'causal_connectivity': causal_connectivity,
                'avg_node_influence': sum(self.personalities[m].get('node_influence', 0) for m in members) / len(members)
            }
            cluster_id += 1
    
    return valid_clusters
```

### 3.3 Merge Cluster Simili (Jaccard)

```python
def merge_similar_clusters(computational_clusters, jaccard_threshold=0.7):
    """Merge cluster computazionali con Jaccard >= threshold"""
    
    def jaccard(a, b):
        sa, sb = set(a), set(b)
        u = len(sa | sb)
        return (len(sa & sb) / u) if u else 0.0
    
    comp_items = list(computational_clusters.items())
    merged = {}
    used = set()
    
    for i in range(len(comp_items)):
        if comp_items[i][0] in used:
            continue
        
        base_id, base = comp_items[i]
        group_members = set(base['members'])
        
        for j in range(i+1, len(comp_items)):
            cid, c = comp_items[j]
            if cid in used:
                continue
            
            if jaccard(base['members'], c['members']) >= jaccard_threshold:
                group_members |= set(c['members'])
                used.add(cid)
        
        merged_id = base_id
        merged[merged_id] = dict(base)
        merged[merged_id]['members'] = list(group_members)
        merged[merged_id]['n_members'] = len(group_members)
    
    return merged
```

---

## 🔧 Utilities Causali

### Compute Edge Density (Connettività Causale)

```python
def compute_edge_density(
    feature_keys: List[str],
    graph_data: Dict,
    feature_to_idx: Dict[str, int],
    tau_edge: float = 0.01
) -> float:
    """
    Calcola densità di edge causali all'interno di un insieme di feature
    
    edge_density = (numero edge forti) / (numero possibili edge)
    """
    if len(feature_keys) < 2:
        return 0.0
    
    # Filtra solo feature presenti nel grafo
    valid_features = [fkey for fkey in feature_keys if fkey in feature_to_idx]
    
    if len(valid_features) < 2:
        return 0.0
    
    # Converti a indici
    indices = [feature_to_idx[fkey] for fkey in valid_features]
    
    # Estrai sub-matrice
    adjacency_matrix = graph_data['adjacency_matrix']
    
    # Conta edge forti
    strong_edges = 0
    possible_edges = 0
    
    for i in indices:
        for j in indices:
            if i != j:
                possible_edges += 1
                if adjacency_matrix[i, j].item() > tau_edge:
                    strong_edges += 1
    
    edge_density = strong_edges / possible_edges if possible_edges > 0 else 0.0
    
    return edge_density
```

---

## 🚀 Esecuzione Pipeline Completa

```python
def run_full_pipeline():
    """Esegue pipeline completa di labelling"""
    
    print("=" * 60)
    print("PIPELINE LABELLING SUPERNODI")
    print("=" * 60)
    
    # FASE 1: Analisi Antropologica
    print("\n📊 FASE 1: Analisi Antropologica")
    anthropologist = BasicFeatureAnthropologist()
    anthropologist.load_data()
    personalities = anthropologist.analyze_feature_personalities()
    archetypes = anthropologist.identify_narrative_archetypes(personalities)
    
    # FASE 2: Costruzione Cicciotti
    print("\n🌱 FASE 2: Costruzione Supernodi Semantici")
    builder = CicciottiSupernodeBuilder()
    builder.load_anthropological_results()
    seeds = builder.select_semantic_seeds()
    cicciotti = builder.build_all_cicciotti(seeds)
    validation = builder.cross_prompt_validation(cicciotti)
    
    # FASE 3: Clustering Residui
    print("\n🏭 FASE 3: Clustering Residui Computazionali")
    clusterer = OptimizedFinalClustering()
    clusterer.load_data()
    quality_residuals = clusterer.identify_quality_residuals()
    computational_clusters = clusterer.quality_clustering(quality_residuals)
    final_results = clusterer.create_final_comprehensive_results(computational_clusters)
    
    # Salvataggio
    print("\n💾 Salvataggio risultati...")
    with open("output/final_anthropological_optimized.json", 'w') as f:
        json.dump(final_results, f, indent=2)
    
    print("✅ Pipeline completata!")
    print(f"📊 {final_results['comprehensive_statistics']['total_supernodes']} supernodi creati")
    print(f"📈 {final_results['comprehensive_statistics']['quality_coverage_percentage']:.1f}% coverage qualità")
    
    return final_results

if __name__ == "__main__":
    results = run_full_pipeline()
```


