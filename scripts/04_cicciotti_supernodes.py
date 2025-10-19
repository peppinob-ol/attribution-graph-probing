#!/usr/bin/env python3
"""
Implementazione Strategia Supernodi Cicciotti
Approccio: Seed semantici → Crescita narrativa → Clustering residui
"""

import json
import csv
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Set, Optional

class CicciottiSupernodeBuilder:
    """
    Costruttore di supernodi cicciotti basato su analisi antropologica.
    
    Pipeline:
    1. Load archetipi narrativi da analisi antropologica
    2. Seed selection dai semantic_anchors  
    3. Narrative-guided growth per ogni seed
    4. Cross-prompt validation 
    5. Residual processing con clustering
    """
    
    def __init__(self):
        self.archetypes = {}
        self.personalities = {}
        self.acts_data = []
        self.cicciotti_supernodes = {}
        self.graph_data = None
        self.causal_metrics = {}
        self.feature_to_idx = {}
        
    def load_anthropological_results(self):
        """Carica risultati analisi antropologica"""
        print("📥 Caricamento risultati antropologici...")
        
        try:
            # Carica archetipi narrativi
            with open("output/narrative_archetypes.json", 'r') as f:
                self.archetypes = json.load(f)
            
            # Carica personalità complete
            with open("output/feature_personalities_corrected.json", 'r') as f:
                self.personalities = json.load(f)
            
            # Carica dati originali per validation cross-prompt
            with open("output/acts_compared.csv", 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.acts_data = list(reader)
            
            print(f"✅ Caricati archetipi: {[(k, len(v)) for k, v in self.archetypes.items()]}")
            print(f"✅ Caricati {len(self.personalities)} personalità")
            print(f"✅ Caricati {len(self.acts_data)} record attivazioni")
            
            # Carica grafo causale
            try:
                import sys
                sys.path.insert(0, 'scripts')
                from causal_utils import load_attribution_graph
                
                self.graph_data = load_attribution_graph("output/example_graph.pt")
                
                if self.graph_data is not None:
                    # Crea feature_to_idx mapping
                    for i, (layer, pos, feat_idx) in enumerate(self.graph_data['active_features']):
                        feature_key = f"{layer.item()}_{feat_idx.item()}"
                        self.feature_to_idx[feature_key] = i
                    
                    # Estrai causal_metrics dalle personalities
                    for fkey, personality in self.personalities.items():
                        if 'node_influence' in personality:
                            self.causal_metrics[fkey] = {
                                'node_influence': personality['node_influence'],
                                'causal_in_degree': personality.get('causal_in_degree', 0),
                                'causal_out_degree': personality.get('causal_out_degree', 0),
                                'top_parents': personality.get('top_parents', []),
                                'top_children': personality.get('top_children', []),
                                'layer': personality['layer'],
                                'position': personality.get('position', 0)
                            }
                    
                    print(f"✅ Grafo causale caricato: {len(self.feature_to_idx)} feature mappate")
                else:
                    print(f"⚠️ Grafo causale non disponibile, uso solo metriche semantiche")
            except Exception as e:
                print(f"⚠️ Errore caricamento grafo causale: {e}")
                self.graph_data = None
            
            return True
            
        except Exception as e:
            print(f"❌ Errore caricamento: {e}")
            return False
    
    def find_say_austin_seed(self) -> Optional[Dict]:
        """
        Trova il seed "Say Austin": feature alla posizione finale 
        con edge più forte su logit "Austin"
        TODO: rendere indipendente da "Austin" e accettare target_logit_token come argomento
        """
        if self.graph_data is None or not self.causal_metrics:
            print(f"   ⚠️ Grafo causale non disponibile per find_say_austin_seed")
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
            print(f"   ⚠️ Errore find_say_austin_seed: {e}")
        
        return None
    
    def select_semantic_seeds(self) -> List[Dict]:
        """
        BACKWARD FROM LOGIT SEED SELECTION
        
        Criteri: 
        1. Prima: Say Austin (edge diretta a logit)
        2. Poi: Massima node_influence (backward propagation)
        3. Diversità per layer e position
        """
        print(f"\n🌱 SEED SELECTION (BACKWARD FROM LOGIT)")
        print("=" * 50)
        
        # Step 1: Trova Say Austin come primo seed
        selected_seeds = []
        say_austin = self.find_say_austin_seed()
        
        if say_austin and 'personality' in say_austin:
            # Usa say_austin come primo seed
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
            print(f"🎯 Seed primario 'Say Austin': {say_austin['feature_key']} "
                  f"(node_influence={seed_dict['node_influence']:.4f})")
        else:
            print(f"   ⚠️ Say Austin non trovato, procedo con seed generici")
        
        # Usa tutte le feature ammesse come candidati seed
        import json
        import pandas as pd
        
        # Carica robust thresholds (node_influence + logit_influence)
        with open("output/robust_thresholds.json", 'r', encoding='utf-8') as f:
            thresholds_data = json.load(f)
        print("   ✅ Usando robust_thresholds.json (node_influence-based)")
        
        admitted_features = set(thresholds_data['admitted_features']['total'])
        
        print(f"📊 Candidati seed disponibili: {len(admitted_features)}")
        
        # Carica logit influence
        metrics_df = pd.read_csv("output/graph_feature_static_metrics (1).csv")
        metrics_df['feature_key'] = metrics_df['layer'].astype(str) + '_' + metrics_df['feature'].astype(str)
        
        # Ordina per logit_influence, poi max_affinity
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
            
            max_aff = personality.get('max_affinity', 0)
            
            scored_seeds.append({
                'feature_key': fkey,
                'personality': personality,
                'logit_influence': logit_inf,
                'node_influence': personality.get('node_influence', 0),
                'max_affinity': max_aff,
                'nuova_max_label_span': personality.get('nuova_max_label_span', 0),
                'layer': personality['layer'],
                'position': personality.get('position', 0),
                'peak_token': personality['most_common_peak']
            })
        
        # Ordina per PROBE ACTIVATION + INFLUENCE (priorità ai seed che rispondono ai probe)
        # Score composito: nuova_max (0-180) + logit_inf*100 (0-100) + node_inf*50 (0-50)
        def seed_score(s):
            probe = s.get('nuova_max_label_span', 0)
            logit = s.get('logit_influence', 0) * 100
            node = abs(s.get('node_influence', 0)) * 50
            return probe + logit + node
        
        scored_seeds.sort(key=seed_score, reverse=True)
        
        # Diversificazione: seleziona seed diversi per layer e position
        used_layers = set([s['layer'] for s in selected_seeds])
        used_positions = set([s.get('position', -1) for s in selected_seeds])
        used_tokens = set([s['peak_token'] for s in selected_seeds])
        
        for seed in scored_seeds:
            # Skip se già in selected_seeds
            if seed['feature_key'] in [s['feature_key'] for s in selected_seeds]:
                continue
            
            layer = seed['layer']
            token = seed['peak_token']
            position = seed.get('position', -1)
            
            # Criterio di diversificazione
            if len(selected_seeds) < 20:  # Primi 20 sempre
                selected_seeds.append(seed)
                used_layers.add(layer)
                used_positions.add(position)
                used_tokens.add(token)
            elif layer not in used_layers or position not in used_positions:
                # Preferisci diversità su layer e position
                selected_seeds.append(seed)
                used_layers.add(layer)
                used_positions.add(position)
                used_tokens.add(token)
            
            # Max 50 seed per gestibilità
            if len(selected_seeds) >= 50:
                break
        
        print(f"🎯 Seed selezionati: {len(selected_seeds)}")
        print(f"📊 Layer coperti: {sorted(used_layers)}")
        print(f"📍 Positions coperte: {sorted(used_positions)}")
        print(f"🎪 Peak tokens: {sorted(used_tokens)[:10]}...")
        
        # Mostra top 5 per score composito (probe + influence)
        print(f"\n📈 Top 5 seed per score composito (probe+influence):")
        for i, seed in enumerate(selected_seeds[:5]):
            probe = seed.get('nuova_max_label_span', 0)
            logit = seed.get('logit_influence', 0)
            node_inf = seed.get('node_influence', 0)
            print(f"   {i+1}. {seed['feature_key']}: probe={probe:.1f}, logit={logit:.4f}, node={node_inf:.4f}, "
                  f"token='{seed['peak_token']}', pos={seed.get('position', '?')}'")
        
        return selected_seeds
    
    def grow_cicciotto_supernode(self, seed: Dict, global_used_features: set = None) -> Dict:
        """
        Step 2: Crescita narrativa di un singolo supernodo cicciotto
        
        Strategia:
        1. Inizia con seed
        2. Aggiungi stable_contributors narrativamente compatibili
        3. Aggiungi contextual_specialists se coerenti
        4. Stop quando coerenza scende sotto soglia
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
            'total_influence_score': seed['logit_influence'],  # Renamed from narrative_score
            'coherence_history': [1.0]  # Inizia perfettamente coerente
        }
        
        # Aggiungi seed al set globale se fornito
        if global_used_features is not None:
            global_used_features.add(seed_key)
        
        # Crescita iterativa (soglie rilassate per supernodi più grandi)
        max_iterations = 40  # Aumentato per permettere crescita maggiore
        min_coherence = 0.35  # Ulteriormente abbassato per supernodi più grandi
        bootstrap_iterations = 5  # Aumentato per base causale più solida
        
        # Inizializza set used features se non fornito
        if global_used_features is None:
            global_used_features = set()
        
        for iteration in range(max_iterations):
            best_candidate = None
            best_compatibility = 0
            
            # Modalità bootstrap causale (prime 3 iterazioni con 2-hop)
            is_bootstrap = iteration < bootstrap_iterations and self.graph_data is not None
            
            # COSTRUISCI POOL CANDIDATI DINAMICO ad ogni iterazione
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
                                    # Peso ridotto per 2-hop (moltiplica per 0.5)
                                    second_hop_scores[pp_key] = max(second_hop_scores.get(pp_key, 0.0), float(w2) * 0.5)
                    # Unisci mantenendo il max (1-hop ha priorità)
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
            else:
                # Fallback semantico se grafo non disponibile
                for contributor in self.archetypes.get('stable_contributors', []):
                    candidates.append({
                        'feature_key': contributor['feature_key'],
                        'personality': contributor['personality'],
                        'type': 'stable'
                    })
                for specialist in self.archetypes.get('contextual_specialists', []):
                    candidates.append({
                        'feature_key': specialist['feature_key'],
                        'personality': specialist['personality'],
                        'type': 'contextual'
                    })
            
            # Seleziona miglior candidato
            for candidate in candidates:
                # CONTROLLO DUPLICATI: Skip se già nel supernodo corrente O già utilizzato globalmente
                if (candidate['feature_key'] in cicciotto['members'] or 
                    candidate['feature_key'] in global_used_features):
                    continue
                
                # Bootstrap causale: usa solo edge diretta
                if is_bootstrap:
                    # Accetta solo se ha edge diretta forte verso seed o membri esistenti
                    seed_key = cicciotto['seed']
                    cand_key = candidate['feature_key']
                    
                    if seed_key in self.feature_to_idx and cand_key in self.feature_to_idx:
                        seed_idx = self.feature_to_idx[seed_key]
                        cand_idx = self.feature_to_idx[cand_key]
                        adjacency_matrix = self.graph_data['adjacency_matrix']
                        
                        # Edge da candidate a seed (backward)
                        edge_weight = adjacency_matrix[seed_idx, cand_idx].item()
                        
                        # Soglia bootstrap più elastica
                        if edge_weight > 0.03:  # Edge moderatamente forti
                            compatibility = edge_weight * 10  # Normalizza per confronto
                        else:
                            continue
                    else:
                        continue
                else:
                    # Modalità normale: calcola compatibilità causale+semantica
                    compatibility = self.compute_narrative_compatibility(
                        cicciotto, candidate
                    )
                
                # Soglia rilassata per crescita più ampia
                threshold = 0.25 if is_bootstrap else 0.35
                if compatibility > best_compatibility and compatibility > threshold:
                    best_compatibility = compatibility
                    best_candidate = candidate
            
            # Aggiungi miglior candidato se sufficientemente compatibile (soglia rilassata)
            threshold_final = 0.25 if is_bootstrap else 0.35
            if best_candidate and best_compatibility > threshold_final:
                cicciotto['members'].append(best_candidate['feature_key'])
                
                # AGGIUNGI SUBITO AL SET GLOBALE per evitare riutilizzo
                if global_used_features is not None:
                    global_used_features.add(best_candidate['feature_key'])
                
                # Usa conditional_consistency se disponibile per score interno del cluster
                candidate_consistency = best_candidate['personality'].get('conditional_consistency',
                                        best_candidate['personality'].get('mean_consistency',
                                        best_candidate['personality'].get('consistency_score', 0)))
                cicciotto['total_influence_score'] += (
                    candidate_consistency * best_compatibility
                )
                
                # Calcola nuova coerenza del supernodo
                new_coherence = self.compute_supernode_coherence(cicciotto)
                cicciotto['coherence_history'].append(new_coherence)
                
                # Stop se coerenza scende troppo (non durante bootstrap)
                if (not is_bootstrap) and new_coherence < min_coherence:
                    print(f"   🛑 Stop per {seed_key}: coerenza scesa a {new_coherence:.3f}")
                    # Rimuovi ultimo membro sia dal supernodo che dal set globale
                    removed_member = cicciotto['members'].pop()
                    if global_used_features is not None:
                        global_used_features.discard(removed_member)
                    cicciotto['coherence_history'].pop()
                    break
            else:
                # Nessun candidato compatibile trovato
                break
        
        cicciotto['final_coherence'] = cicciotto['coherence_history'][-1]
        cicciotto['growth_iterations'] = len(cicciotto['coherence_history']) - 1
        
        return cicciotto
    
    def compute_narrative_compatibility(self, cicciotto: Dict, candidate: Dict) -> float:
        """
        Calcola compatibilità CAUSALE (60%) + SEMANTICA (40%) tra supernodo e candidato
        
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
            
            # Anchor boost: se edge è molto forte (>0.1), aumenta il peso
            if edge_weight > 0.1:
                direct_edge_score = min(1.0, direct_edge_score * 1.5)  # Boost 50%
            
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
                direct_edge_score * 0.42 +  # 25% di 60% = 0.25 → peso relativo 0.42
                jaccard * 0.33 +             # 20% di 60% = 0.20 → peso relativo 0.33
                position_compat * 0.25       # 15% di 60% = 0.15 → peso relativo 0.25
            )
        else:
            # Fallback se grafo non disponibile: solo position
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
            token_compat * 0.50 +      # 20% di 40% = 0.20 → peso relativo 0.50
            layer_compat * 0.25 +      # 10% di 40% = 0.10 → peso relativo 0.25
            consistency_compat * 0.25  # 10% di 40% = 0.10 → peso relativo 0.25
        )
        
        # ========== COMBINAZIONE FINALE: 60% causale + 40% semantica ==========
        total_compatibility = causal_score * 0.60 + semantic_score * 0.40
        
        return total_compatibility
    
    def compute_supernode_coherence(self, cicciotto: Dict) -> float:
        """
        Calcola coerenza narrativa + causale del supernodo completo
        
        Metrics:
        - Consistency variance tra membri (semantica)
        - Peak token diversity (semantica)
        - Layer span (semantica)
        - Causal edge density (causale)
        """
        
        if len(cicciotto['members']) <= 1:
            return 1.0
        
        # Raccogli statistiche membri
        consistencies = []
        peak_tokens = []
        layers = []
        
        for member_key in cicciotto['members']:
            personality = self.personalities[member_key]
            # Usa conditional_consistency se disponibile, fallback a consistency_score
            consistency_val = personality.get('conditional_consistency', personality.get('consistency_score', 0))
            consistencies.append(consistency_val)
            peak_tokens.append(personality['most_common_peak'])
            layers.append(personality['layer'])
        
        # Coherence factor 1: Consistency homogeneity
        consistency_std = self._std(consistencies) if len(consistencies) > 1 else 0
        consistency_coherence = max(0, 1 - consistency_std)
        
        # Coherence factor 2: Peak token diversity (non troppa)
        token_diversity = len(set(peak_tokens)) / len(peak_tokens)
        diversity_coherence = max(0, 1 - abs(token_diversity - 0.5))  # Target 50% diversity
        
        # Coherence factor 3: Layer span (preferisce compattezza)
        layer_span = max(layers) - min(layers) if layers else 0
        span_coherence = max(0, 1 - layer_span / 15)  # Decade con span
        
        # Coherence factor 4: Causal edge density (nuova metrica causale)
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
            except Exception as e:
                # Fallback silenzioso
                pass
        
        # Combinazione: pesi ribilanciati per includere causal_density
        total_coherence = (
            consistency_coherence * 0.30 +  # Semantica
            diversity_coherence * 0.20 +    # Semantica
            span_coherence * 0.20 +         # Semantica
            causal_density * 0.30           # Causale
        )
        
        return total_coherence
    
    def _std(self, values):
        """Standard deviation"""
        if len(values) <= 1:
            return 0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance ** 0.5
    
    def build_all_cicciotti(self, seeds: List[Dict]) -> Dict:
        """
        Step 3: Costruisce tutti i supernodi cicciotti con controllo duplicati
        """
        print(f"\n🏗️  COSTRUZIONE SUPERNODI CICCIOTTI (NO DUPLICATI)")
        print("=" * 50)
        
        cicciotti = {}
        global_used_features = set()  # Track feature già utilizzate globalmente
        
        for i, seed in enumerate(seeds):
            print(f"🌱 Costruendo supernodo {i+1}/{len(seeds)}: {seed['feature_key']}")
            
            # Skip se seed già utilizzato
            if seed['feature_key'] in global_used_features:
                print(f"   ⚠️ Seed già utilizzato, skip")
                continue
            
            cicciotto = self.grow_cicciotto_supernode(seed, global_used_features)
            
            # Solo supernodi con crescita significativa
            if len(cicciotto['members']) >= 2:
                cicciotti[f"CICCIOTTO_{i+1}"] = cicciotto
                print(f"   ✅ {len(cicciotto['members'])} membri, coerenza {cicciotto['final_coherence']:.3f}")
            else:
                print(f"   ❌ Crescita insufficiente, scartato")
                # Rimuovi seed dal set globale se supernodo scartato
                if seed['feature_key'] in global_used_features:
                    global_used_features.discard(seed['feature_key'])
        
        print(f"\n🎯 Supernodi cicciotti creati: {len(cicciotti)}")
        print(f"📊 Feature totali utilizzate: {len(global_used_features)}")
        return cicciotti
    
    def cross_prompt_validation(self, cicciotti: Dict):
        """
        Step 4: Validazione cross-prompt dei supernodi
        
        Test: i supernodi mantengono coerenza su prompt diversi?
        """
        print(f"\n🧪 VALIDAZIONE CROSS-PROMPT")
        print("=" * 50)
        
        # Raggruppa attivazioni per prompt
        prompt_groups = defaultdict(list)
        for record in self.acts_data:
            prompt_key = record['prompt'][:30] + "..."
            prompt_groups[prompt_key].append(record)
        
        validation_results = {}
        
        for supernode_id, cicciotto in cicciotti.items():
            print(f"🔍 Validando {supernode_id} ({len(cicciotto['members'])} membri)")
            
            prompt_consistency = {}
            
            for prompt_key, records in prompt_groups.items():
                # Trova attivazioni dei membri su questo prompt
                member_activations = []
                
                for record in records:
                    feature_key = f"{record['layer']}_{record['feature']}"
                    if feature_key in cicciotto['members']:
                        try:
                            cosine = float(record.get('cosine_similarity', 0))
                            member_activations.append(cosine)
                        except ValueError:
                            pass
                
                # Calcola consistenza su questo prompt
                if member_activations:
                    prompt_consistency[prompt_key] = {
                        'n_active_members': len(member_activations),
                        'avg_consistency': sum(member_activations) / len(member_activations),
                        'consistency_std': self._std(member_activations)
                    }
                else:
                    prompt_consistency[prompt_key] = {
                        'n_active_members': 0,
                        'avg_consistency': 0,
                        'consistency_std': 0
                    }
            
            validation_results[supernode_id] = prompt_consistency
            
            # Summary per questo supernodo
            active_counts = [p['n_active_members'] for p in prompt_consistency.values()]
            avg_consistencies = [p['avg_consistency'] for p in prompt_consistency.values() if p['avg_consistency'] > 0]
            
            print(f"   📊 Membri attivi per prompt: {active_counts}")
            if avg_consistencies:
                print(f"   📊 Consistenza media: {sum(avg_consistencies)/len(avg_consistencies):.3f}")
        
        return validation_results

def main():
    """Pipeline completa supernodi cicciotti"""
    
    print("🎯 STRATEGIA SUPERNODI CICCIOTTI")
    print("=" * 60)
    
    builder = CicciottiSupernodeBuilder()
    
    # Step 0: Load dati antropologici
    if not builder.load_anthropological_results():
        return
    
    # Step 1: Seed selection
    seeds = builder.select_semantic_seeds()
    
    # Step 2: Costruzione supernodi cicciotti
    cicciotti = builder.build_all_cicciotti(seeds)
    
    # Step 3: Validazione cross-prompt
    validation = builder.cross_prompt_validation(cicciotti)
    
    # Step 4: Salvataggio risultati
    print(f"\n💾 Salvataggio risultati...")
    
    with open("output/cicciotti_supernodes.json", 'w') as f:
        json.dump(cicciotti, f, indent=2)
    
    with open("output/cicciotti_validation.json", 'w') as f:
        json.dump(validation, f, indent=2)
    
    print(f"✅ Pipeline cicciotti completata!")
    print(f"📁 Salvato: output/cicciotti_supernodes.json")
    print(f"📁 Salvato: output/cicciotti_validation.json")
    
    return cicciotti, validation

if __name__ == "__main__":
    main()
