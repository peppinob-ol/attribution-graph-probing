#!/usr/bin/env python3
"""
Analisi antropologica delle feature - Solo librerie standard Python
Approccio esplorativo step-by-step
"""

import csv
import json
from collections import defaultdict, Counter
from typing import Dict, List, Tuple

class BasicFeatureAnthropologist:
    """
    Analisi antropologica delle feature senza pandas.
    Approccio sperimentale step-by-step.
    """
    
    def __init__(self):
        self.acts_data = []
        self.static_data = []
        self.existing_supernodes = None
        
    def load_data(self):
        """Step 1: Caricamento dati con controllo qualità."""
        print("📊 Caricamento dati...")
        
        try:
            # Carica acts_compared.csv
            with open("output/acts_compared.csv", 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.acts_data = list(reader)
            
            print(f"✅ Caricati {len(self.acts_data)} record di attivazioni")
            
            # Carica static metrics
            with open("output/graph_feature_static_metrics (1).csv", 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)  
                self.static_data = list(reader)
            
            print(f"✅ Caricati {len(self.static_data)} record di metriche statiche") 
            
            # Carica supernodi esistenti
            with open("output/supernodes_final.json", 'r', encoding='utf-8') as f:
                self.existing_supernodes = json.load(f)
                
            print(f"✅ Caricati {len(self.existing_supernodes)} supernodi esistenti")
            
            return True
            
        except Exception as e:
            print(f"❌ Errore nel caricamento: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def explore_data_structure(self):
        """Step 2: Esplorazione struttura dati - cosa possiamo effettivamente inferire?"""
        
        print("\n🔍 ESPLORAZIONE STRUTTURA DATI")
        print("=" * 50)
        
        if not self.acts_data:
            print("❌ Nessun dato di attivazione caricato")
            return
        
        # Prendi il primo record per vedere le colonne
        first_record = self.acts_data[0]
        print(f"📊 Colonne disponibili ({len(first_record)}):")
        for i, col in enumerate(first_record.keys()):
            print(f"   {i+1:2d}. {col}")
        
        # Analizza distribuzioni base
        prompts = set(r['prompt'] for r in self.acts_data if 'prompt' in r)
        layers = [int(r['layer']) for r in self.acts_data if r['layer'].isdigit()]
        
        print(f"\n🌐 Prompt unici: {len(prompts)}")
        print(f"📊 Layer range: {min(layers) if layers else 'N/A'}-{max(layers) if layers else 'N/A'}")
        
        # Analizza feature uniche  
        unique_features = set((r['layer'], r['feature']) for r in self.acts_data)
        print(f"🧬 Feature uniche: {len(unique_features)}")
        
        # Analizza metriche chiave per presenza/varianza
        key_metrics = ['cosine_similarity', 'ratio_max_vs_original', 
                      'density_attivazione', 'picco_su_label']
        
        print(f"\n📈 Analisi metriche chiave:")
        for metric in key_metrics:
            values = []
            for r in self.acts_data:
                if metric in r and r[metric]:
                    try:
                        val = float(r[metric])
                        if val != 0:  # Solo valori non-zero
                            values.append(val)
                    except ValueError:
                        continue
            
            if values:
                print(f"   {metric}: {len(values)}/{len(self.acts_data)} non-zero "
                      f"(range: {min(values):.3f}-{max(values):.3f})")
            else:
                print(f"   {metric}: Tutti zero o mancanti! ⚠️")
        
        return True
    
    def analyze_feature_personalities(self) -> Dict:
        """
        Step 3: Tentativo di identificare 'personalità' delle feature
        
        DOMANDA CRITICA: Esistono cluster naturali di comportamento?
        """
        
        print("\n🎭 ANALISI PERSONALITÀ FEATURE")
        print("=" * 50)
        
        # Raggruppa dati per feature unica
        feature_data = defaultdict(list)
        
        for record in self.acts_data:
            feature_key = (record['layer'], record['feature'])
            feature_data[feature_key].append(record)
        
        print(f"📊 Feature analizzate: {len(feature_data)}")
        
        # Calcola statistiche per ogni feature
        personalities = {}
        
        for feature_key, records in feature_data.items():
            layer, feature_id = feature_key
            
            # Calcola metriche antropologiche
            cosine_values = []
            ratios = []
            densities = []
            label_peaks = []
            peak_tokens = []
            twera_values = []
            
            for r in records:
                # Cosine similarity
                if r.get('cosine_similarity'):
                    try:
                        cosine_values.append(float(r['cosine_similarity']))
                    except ValueError:
                        pass
                
                # Ratio max vs original
                if r.get('ratio_max_vs_original'):
                    try:
                        ratios.append(float(r['ratio_max_vs_original']))
                    except ValueError:
                        pass
                
                # Density
                if r.get('density_attivazione'):
                    try:
                        densities.append(float(r['density_attivazione']))
                    except ValueError:
                        pass
                
                # Label peaks
                if r.get('picco_su_label'):
                    label_peaks.append(r['picco_su_label'].lower() == 'true')
                
                # Peak tokens
                if r.get('peak_token'):
                    peak_tokens.append(r['peak_token'])
                
                # TWERA
                if r.get('twera_total_in'):
                    try:
                        twera_values.append(float(r['twera_total_in']))
                    except ValueError:
                        pass
            
            # Estrai attivazioni per threshold adattivo
            activations = []
            for r in records:
                if r.get('nuova_somma_sequenza'):
                    try:
                        activations.append(float(r['nuova_somma_sequenza']))
                    except ValueError:
                        pass
            
            # Threshold adattivo per questa feature
            activation_threshold = self._compute_adaptive_threshold(activations) if activations else 0
            
            # Filtra attivazioni sopra threshold
            active_indices = [i for i, act in enumerate(activations) if act > activation_threshold]
            
            # Cosine values solo per attivazioni attive
            active_cosines = [cosine_values[i] for i in active_indices if i < len(cosine_values)]
            
            # Calcola personalità con NUOVE METRICHE
            personality = {
                'layer': int(layer),
                'feature_id': feature_id,
                'n_observations': len(records),
                
                # VECCHIA METRICA (mantenuta per confronto)
                'consistency_score_legacy': sum(cosine_values) / len(cosine_values) if cosine_values else 0,
                
                # NUOVE METRICHE
                'mean_consistency': sum(cosine_values) / len(cosine_values) if cosine_values else 0,  # generalizzabilità
                'max_affinity': max(cosine_values) if cosine_values else 0,  # specializzazione
                'conditional_consistency': sum(active_cosines) / len(active_cosines) if active_cosines else 0,  # consistency quando attiva
                'activation_threshold': activation_threshold,
                
                'consistency_std': self._std(cosine_values) if len(cosine_values) > 1 else 0,
                'label_affinity': sum(label_peaks) / len(label_peaks) if label_peaks else 0,
                'activation_stability': 1 / (1 + self._std(densities)) if len(densities) > 1 else 1,
                'max_ratio': max(ratios) if ratios else 0,
                'most_common_peak': Counter(peak_tokens).most_common(1)[0][0] if peak_tokens else 'unknown',
                'avg_twera': sum(twera_values) / len(twera_values) if twera_values else 0,
            }
            
            personalities[feature_key] = personality
        
        # Merge con dati statici se disponibili
        static_lookup = {}
        for r in self.static_data:
            key = (r['layer'], r['feature'])
            static_lookup[key] = {
                'social_influence': float(r.get('frac_external_raw', 0)),
                'output_impact': float(r.get('logit_influence', 0))
            }
        
        # Aggiungi dati statici
        for feature_key, personality in personalities.items():
            if feature_key in static_lookup:
                personality.update(static_lookup[feature_key])
            else:
                personality['social_influence'] = 0
                personality['output_impact'] = 0
        
        return personalities
    
    def _std(self, values):
        """Calcola deviazione standard manualmente."""
        if len(values) <= 1:
            return 0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance ** 0.5
    
    def _compute_adaptive_threshold(self, activations):
        """Threshold ibrido: min(percentile 75, detection automatica)"""
        if len(activations) < 3:
            return 0
        
        thr_p75 = self._percentile(activations, 75)
        
        # Detection automatica con Otsu (fallback a p75 se fallisce)
        try:
            from skimage.filters import threshold_otsu
            import numpy as np
            thr_auto = threshold_otsu(np.array(activations))
        except:
            thr_auto = thr_p75
        
        return min(thr_p75, thr_auto)
    
    def identify_narrative_archetypes(self, personalities: Dict):
        """
        Step 4: Tentativo di identificare archetipi narrativi
        
        DOMANDA: Ci sono pattern che giustificano i 'ruoli' dalle biografie teoriche?
        """
        
        print("\n🏛️  IDENTIFICAZIONE ARCHETIPI NARRATIVI")
        print("=" * 50)
        
        if not personalities:
            print("❌ Nessuna personalità da analizzare")
            return {}
        
        # Calcola soglie empiriche usando nuove metriche
        mean_consistencies = [p['mean_consistency'] for p in personalities.values()]
        label_affinities = [p['label_affinity'] for p in personalities.values()]
        social_influences = [p['social_influence'] for p in personalities.values()]
        max_affinities = [p['max_affinity'] for p in personalities.values()]
        
        # Usa percentili per soglie
        high_mean_consistency = self._percentile(mean_consistencies, 75)
        high_label_affinity = self._percentile(label_affinities, 75)
        high_social = self._percentile(social_influences, 75)
        high_max_affinity = self._percentile(max_affinities, 75)
        
        print(f"📊 Soglie empiriche:")
        print(f"   Mean consistency alta: {high_mean_consistency:.3f}")
        print(f"   Max affinity alta: {high_max_affinity:.3f}")
        print(f"   Affinità label alta: {high_label_affinity:.3f}")
        print(f"   Influenza sociale alta: {high_social:.3f}")
        
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
                    'feature_key': f"{feature_key[0]}_{feature_key[1]}" if isinstance(feature_key, tuple) else feature_key,
                    'personality': personality
                })
            
            # Stable Contributors: alta mean consistency ma max affinity media
            elif (personality['mean_consistency'] > high_mean_consistency):
                archetypes['stable_contributors'].append({
                    'feature_key': f"{feature_key[0]}_{feature_key[1]}" if isinstance(feature_key, tuple) else feature_key,
                    'personality': personality
                })
            
            # Contextual Specialists: bassa mean consistency ma alta max affinity (specialists!)
            elif (personality['mean_consistency'] < high_mean_consistency and 
                  personality['max_affinity'] > high_max_affinity):
                archetypes['contextual_specialists'].append({
                    'feature_key': f"{feature_key[0]}_{feature_key[1]}" if isinstance(feature_key, tuple) else feature_key,
                    'personality': personality
                })
            
            # Computational Helpers: alta influenza sociale ma basse metriche semantiche
            elif (personality['social_influence'] > high_social and
                  personality['max_affinity'] < high_max_affinity):
                archetypes['computational_helpers'].append({
                    'feature_key': f"{feature_key[0]}_{feature_key[1]}" if isinstance(feature_key, tuple) else feature_key,
                    'personality': personality
                })
            
            # Outliers: comportamento instabile
            else:
                archetypes['outliers'].append({
                    'feature_key': f"{feature_key[0]}_{feature_key[1]}" if isinstance(feature_key, tuple) else feature_key,
                    'personality': personality
                })
        
        print("\n🎭 Archetipi identificati:")
        for archetype, features in archetypes.items():
            print(f"   {archetype}: {len(features)} feature")
            
            # Mostra esempi per i primi archetipi
            if features and archetype in ['semantic_anchors', 'contextual_specialists']:
                print(f"      Esempi: {[f['feature_key'] for f in features[:3]]}")
        
        # Salva archetipi
        with open("output/narrative_archetypes.json", 'w', encoding='utf-8') as f:
            json.dump(archetypes, f, indent=2)
        print(f"\n   Salvati: output/narrative_archetypes.json")
        
        return archetypes
    
    def classify_feature_typology(self, personalities: Dict, logit_influences: Dict) -> Dict:
        """Classifica feature in: Generalist, Specialist, Computational, Hybrid"""
        
        typology = {}
        
        for fkey, p in personalities.items():
            mean_cons = p['mean_consistency']
            max_aff = p['max_affinity']
            logit_inf = logit_influences.get(fkey, 0)
            
            # Thresholds empirici (configurabili)
            if mean_cons > 0.6 and max_aff > 0.6 and logit_inf < 0.3:
                feature_type = 'generalist'
            elif mean_cons < 0.3 and max_aff > 0.6 and logit_inf > 0.2:
                feature_type = 'specialist'
            elif mean_cons > 0.5 and max_aff < 0.5 and logit_inf < 0.2:
                feature_type = 'computational'
            else:
                feature_type = 'hybrid'
            
            typology[fkey] = {
                'type': feature_type,
                'mean_consistency': mean_cons,
                'max_affinity': max_aff,
                'logit_influence': logit_inf,
                'coordinates': [mean_cons, max_aff, logit_inf]
            }
        
        return typology
    
    def compute_interpretability_quality(self, personalities: Dict, logit_influences: Dict,
                                         alpha=0.6, beta=0.2, gamma=0.2) -> Dict:
        """
        Quality = α·InfluenceCoverage + β·MeanConsistency + γ·MaxAffinity
        Default: α=0.6, β=0.2, γ=0.2
        """
        
        total_influence = sum(logit_influences.values())
        
        quality_scores = {}
        for fkey, p in personalities.items():
            influence = logit_influences.get(fkey, 0)
            influence_coverage = influence / total_influence if total_influence > 0 else 0
            
            quality = (
                alpha * influence_coverage +
                beta * p['mean_consistency'] +
                gamma * p['max_affinity']
            )
            
            quality_scores[fkey] = {
                'quality_score': quality,
                'influence_coverage': influence_coverage,
                'weights_used': {'alpha': alpha, 'beta': beta, 'gamma': gamma}
            }
        
        return quality_scores
    
    def compute_metric_correlations(self, personalities: Dict, logit_influences: Dict) -> Dict:
        """Calcola correlazioni empiriche tra metriche"""
        
        mean_cons = [p['mean_consistency'] for p in personalities.values()]
        max_aff = [p['max_affinity'] for p in personalities.values()]
        cond_cons = [p['conditional_consistency'] for p in personalities.values()]
        layers = [p['layer'] for p in personalities.values()]
        influences = [logit_influences.get(k, 0) for k in personalities.keys()]
        
        def corrcoef(x, y):
            """Calcola correlation coefficient manualmente"""
            if len(x) != len(y) or len(x) < 2:
                return 0
            mean_x = sum(x) / len(x)
            mean_y = sum(y) / len(y)
            cov = sum((x[i] - mean_x) * (y[i] - mean_y) for i in range(len(x))) / (len(x) - 1)
            std_x = (sum((xi - mean_x) ** 2 for xi in x) / (len(x) - 1)) ** 0.5
            std_y = (sum((yi - mean_y) ** 2 for yi in y) / (len(y) - 1)) ** 0.5
            return cov / (std_x * std_y) if std_x * std_y > 0 else 0
        
        correlations = {
            'mean_consistency_vs_logit_influence': corrcoef(mean_cons, influences),
            'max_affinity_vs_logit_influence': corrcoef(max_aff, influences),
            'conditional_vs_mean_consistency': corrcoef(cond_cons, mean_cons),
            'layer_vs_mean_consistency': corrcoef(layers, mean_cons),
            'layer_vs_max_affinity': corrcoef(layers, max_aff),
        }
        
        return correlations
    
    def _percentile(self, values, percentile):
        """Calcola percentile manualmente."""
        if not values:
            return 0
        sorted_vals = sorted(values)
        k = (len(sorted_vals) - 1) * percentile / 100
        f = int(k)
        c = k - f
        if f == len(sorted_vals) - 1:
            return sorted_vals[f]
        return sorted_vals[f] * (1 - c) + sorted_vals[f + 1] * c

def main():
    """Esecuzione step-by-step dell'analisi antropologica."""
    
    print("🚀 Avvio analisi antropologica (versione base)...")
    
    try:
        anthropologist = BasicFeatureAnthropologist()
        
        # Step 1: Load data
        print("📥 Step 1: Caricamento dati...")
        if not anthropologist.load_data():
            print("❌ Fallimento nel caricamento dati")
            return
        
        # Step 2: Explore structure
        print("📊 Step 2: Esplorazione struttura...")
        anthropologist.explore_data_structure()
        
        # Step 3: Analyze personalities  
        print("🎭 Step 3: Analisi personalità...")
        personalities = anthropologist.analyze_feature_personalities()
        
        # Step 4: Identify archetypes
        print("🏛️  Step 4: Identificazione archetipi...")
        archetypes = anthropologist.identify_narrative_archetypes(personalities)
        
        # Converte personalities per JSON
        personalities_json = {}
        logit_influences = {}
        for key, personality in personalities.items():
            key_str = f"{key[0]}_{key[1]}"
            personalities_json[key_str] = personality
            logit_influences[key_str] = personality.get('output_impact', 0)
        
        # Step 5: Feature Typology Classification
        print("\n🔬 Step 5: Feature Typology Classification...")
        typology = anthropologist.classify_feature_typology(personalities_json, logit_influences)
        
        type_counts = {}
        for v in typology.values():
            t = v['type']
            type_counts[t] = type_counts.get(t, 0) + 1
        print(f"   Feature types: {type_counts}")
        
        # Step 6: Interpretability Quality Scores
        print("\n📊 Step 6: Interpretability Quality Scores...")
        quality_scores = anthropologist.compute_interpretability_quality(
            personalities_json,
            logit_influences,
            alpha=0.6, beta=0.2, gamma=0.2
        )
        avg_quality = sum(q['quality_score'] for q in quality_scores.values()) / len(quality_scores) if quality_scores else 0
        print(f"   Average quality score: {avg_quality:.4f}")
        
        # Step 7: Metric Correlations
        print("\n📈 Step 7: Metric Correlations...")
        correlations = anthropologist.compute_metric_correlations(
            personalities_json,
            logit_influences
        )
        print(f"   Correlations computed:")
        for metric, corr in correlations.items():
            print(f"      {metric}: {corr:.3f}")
        
        # Step 8: Causal Metrics Enrichment
        print("\n🔗 Step 8: Arricchimento con metriche causali...")
        try:
            import sys
            sys.path.insert(0, 'scripts')
            from causal_utils import load_attribution_graph, compute_causal_metrics
            
            graph_data = load_attribution_graph("output/example_graph.pt")
            
            if graph_data is not None:
                causal_metrics = compute_causal_metrics(graph_data, tau_edge=0.01, top_k=5)
                
                # Merge metriche causali nelle personalities
                enriched_count = 0
                for feature_key, personality in personalities_json.items():
                    if feature_key in causal_metrics:
                        personality.update(causal_metrics[feature_key])
                        enriched_count += 1
                
                print(f"   ✅ {enriched_count}/{len(personalities_json)} personalities arricchite con metriche causali")
                
                # Stats node_influence
                node_influences = [p.get('node_influence', 0) for p in personalities_json.values() 
                                  if 'node_influence' in p]
                if node_influences:
                    avg_ni = sum(node_influences) / len(node_influences)
                    max_ni = max(node_influences)
                    print(f"   📊 Node influence: avg={avg_ni:.4f}, max={max_ni:.4f}")
            else:
                print(f"   ⚠️ Attribution Graph non disponibile, skip metriche causali")
        except Exception as e:
            print(f"   ⚠️ Errore caricamento metriche causali: {e}")
            import traceback
            traceback.print_exc()
        
        # Salvataggio risultati
        print("\n💾 Salvataggio risultati...")
        
        with open("output/feature_personalities_corrected.json", 'w', encoding='utf-8') as f:
            json.dump(personalities_json, f, indent=2)
        
        with open("output/feature_typology.json", 'w', encoding='utf-8') as f:
            json.dump(typology, f, indent=2)
        
        with open("output/quality_scores.json", 'w', encoding='utf-8') as f:
            json.dump(quality_scores, f, indent=2)
        
        with open("output/metric_correlations.json", 'w', encoding='utf-8') as f:
            json.dump(correlations, f, indent=2)
        
        print(f"\n✅ Analisi refined completata!")
        print(f"📁 Salvati:")
        print(f"   - output/feature_personalities_corrected.json")
        print(f"   - output/feature_typology.json")
        print(f"   - output/quality_scores.json")
        print(f"   - output/metric_correlations.json")
        
        return personalities, archetypes
        
    except Exception as e:
        print(f"❌ Errore durante l'analisi: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("Avvio script di analisi antropologica...")
    main()
