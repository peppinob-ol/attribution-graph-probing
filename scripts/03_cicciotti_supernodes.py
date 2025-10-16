#!/usr/bin/env python3
"""
Implementazione Strategia Supernodi Cicciotti
Approccio: Seed semantici → Crescita narrativa → Clustering residui
"""

import json
import csv
from collections import defaultdict, Counter
from typing import Dict, List, Tuple, Set

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
            
            return True
            
        except Exception as e:
            print(f"❌ Errore caricamento: {e}")
            return False
    
    def select_semantic_seeds(self) -> List[Dict]:
        """
        INFLUENCE-FIRST SEED SELECTION
        
        Criteri: 
        1. Massima logit_influence
        2. In caso di pari merito, max_affinity più alta
        3. Diversità per layer e peak_token
        """
        print(f"\n🌱 SEED SELECTION (INFLUENCE-FIRST)")
        print("=" * 50)
        
        # Usa tutte le feature ammesse come candidati seed
        import json
        import pandas as pd
        with open("output/robust_thresholds.json", 'r', encoding='utf-8') as f:
            thresholds_data = json.load(f)
        
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
                'max_affinity': max_aff,
                'layer': personality['layer'],
                'peak_token': personality['most_common_peak']
            })
        
        # Ordina per logit_influence DESC, poi max_affinity DESC
        scored_seeds.sort(key=lambda x: (x['logit_influence'], x['max_affinity']), reverse=True)
        
        # Diversificazione: seleziona seed diversi per layer e peak_token
        selected_seeds = []
        used_layers = set()
        used_tokens = set()
        
        for seed in scored_seeds:
            layer = seed['layer']
            token = seed['peak_token']
            
            # Criterio di diversificazione
            if len(selected_seeds) < 20:  # Primi 20 sempre
                selected_seeds.append(seed)
                used_layers.add(layer)
                used_tokens.add(token)
            elif layer not in used_layers or token not in used_tokens:
                selected_seeds.append(seed)
                used_layers.add(layer)
                used_tokens.add(token)
            
            # Max 50 seed per gestibilità
            if len(selected_seeds) >= 50:
                break
        
        print(f"🎯 Seed selezionati: {len(selected_seeds)}")
        print(f"📊 Layer coperti: {sorted(used_layers)}")
        print(f"🎪 Peak tokens: {sorted(used_tokens)[:10]}...")
        
        # Mostra top 5 per influence
        print(f"\n📈 Top 5 seed per logit_influence:")
        for i, seed in enumerate(selected_seeds[:5]):
            print(f"   {i+1}. {seed['feature_key']}: influence={seed['logit_influence']:.4f}, "
                  f"affinity={seed['max_affinity']:.3f}, token='{seed['peak_token']}'")
        
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
        
        # Pool di candidati per crescita
        candidates = []
        
        # Aggiungi stable_contributors
        for contributor in self.archetypes.get('stable_contributors', []):
            candidates.append({
                'feature_key': contributor['feature_key'],
                'personality': contributor['personality'],
                'type': 'stable'
            })
        
        # Aggiungi contextual_specialists  
        for specialist in self.archetypes.get('contextual_specialists', []):
            candidates.append({
                'feature_key': specialist['feature_key'],
                'personality': specialist['personality'],
                'type': 'contextual'
            })
        
        # Crescita iterativa
        max_iterations = 20
        min_coherence = 0.6
        
        # Inizializza set used features se non fornito
        if global_used_features is None:
            global_used_features = set()
        
        for iteration in range(max_iterations):
            best_candidate = None
            best_compatibility = 0
            
            for candidate in candidates:
                # CONTROLLO DUPLICATI: Skip se già nel supernodo corrente O già utilizzato globalmente
                if (candidate['feature_key'] in cicciotto['members'] or 
                    candidate['feature_key'] in global_used_features):
                    continue
                
                # Calcola compatibilità narrativa
                compatibility = self.compute_narrative_compatibility(
                    cicciotto, candidate
                )
                
                if compatibility > best_compatibility and compatibility > 0.5:
                    best_compatibility = compatibility
                    best_candidate = candidate
            
            # Aggiungi miglior candidato se sufficientemente compatibile
            if best_candidate and best_compatibility > 0.5:
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
                
                # Stop se coerenza scende troppo
                if new_coherence < min_coherence:
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
        Calcola compatibilità narrativa tra supernodo esistente e candidato
        
        Fattori:
        - Peak token similarity
        - Layer proximity  
        - Consistency compatibility
        - Thematic coherence
        """
        
        seed_personality = self.personalities[cicciotto['seed']]
        candidate_personality = candidate['personality']
        
        # Factor 1: Token thematic similarity
        seed_token = seed_personality['most_common_peak']
        candidate_token = candidate_personality['most_common_peak']
        
        # Gruppi tematici (semplificato)
        geographic_tokens = {'Dallas', 'Texas', 'Austin', 'state', 'State', 'city'}
        relation_tokens = {'of', 'in', 'is', 'the', ':', '.'}
        
        token_compatibility = 0
        if seed_token in geographic_tokens and candidate_token in geographic_tokens:
            token_compatibility = 0.8
        elif seed_token in relation_tokens and candidate_token in relation_tokens:
            token_compatibility = 0.7
        elif seed_token == candidate_token:
            token_compatibility = 1.0
        else:
            token_compatibility = 0.3  # Diverso ma non incompatibile
        
        # Factor 2: Layer proximity (preferisce layer vicini)
        layer_distance = abs(seed_personality['layer'] - candidate_personality['layer'])
        layer_compatibility = max(0, 1 - layer_distance / 10)  # Decade con distanza
        
        # Factor 3: Consistency compatibility (usa conditional_consistency se disponibile)
        consistency_diff = abs(
            seed_personality.get('conditional_consistency', seed_personality.get('consistency_score', 0)) - 
            candidate_personality.get('conditional_consistency', candidate_personality.get('consistency_score', 0))
        )
        consistency_compatibility = max(0, 1 - consistency_diff)
        
        # Combinazione pesata
        total_compatibility = (
            token_compatibility * 0.4 +
            layer_compatibility * 0.3 + 
            consistency_compatibility * 0.3
        )
        
        return total_compatibility
    
    def compute_supernode_coherence(self, cicciotto: Dict) -> float:
        """
        Calcola coerenza narrativa del supernodo completo
        
        Metrics:
        - Consistency variance tra membri
        - Peak token diversity
        - Layer span
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
        
        # Combinazione
        total_coherence = (
            consistency_coherence * 0.4 +
            diversity_coherence * 0.3 +
            span_coherence * 0.3
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
