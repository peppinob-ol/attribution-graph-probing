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
            
            # Calcola personalità
            personality = {
                'layer': int(layer),
                'feature_id': feature_id,
                'n_observations': len(records),
                
                # Consistency metrics
                'consistency_score': sum(cosine_values) / len(cosine_values) if cosine_values else 0,
                'consistency_std': self._std(cosine_values) if len(cosine_values) > 1 else 0,
                
                # Label affinity 
                'label_affinity': sum(label_peaks) / len(label_peaks) if label_peaks else 0,
                
                # Activation stability
                'activation_stability': 1 / (1 + self._std(densities)) if len(densities) > 1 else 1,
                'max_ratio': max(ratios) if ratios else 0,
                
                # Peak behavior
                'most_common_peak': Counter(peak_tokens).most_common(1)[0][0] if peak_tokens else 'unknown',
                
                # Energy
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
        
        # Calcola soglie empiriche
        consistency_scores = [p['consistency_score'] for p in personalities.values()]
        label_affinities = [p['label_affinity'] for p in personalities.values()]
        social_influences = [p['social_influence'] for p in personalities.values()]
        
        # Usa percentili per soglie
        high_consistency = self._percentile(consistency_scores, 75)
        high_label_affinity = self._percentile(label_affinities, 75)
        high_social = self._percentile(social_influences, 75)
        
        print(f"📊 Soglie empiriche:")
        print(f"   Consistenza alta: {high_consistency:.3f}")
        print(f"   Affinità label alta: {high_label_affinity:.3f}")
        print(f"   Influenza sociale alta: {high_social:.3f}")
        
        archetypes = {
            'semantic_heavy': [],
            'computational': [],
            'outliers': [],
            'stable_workers': []
        }
        
        for feature_key, personality in personalities.items():
            # Semantic Heavy: alta consistenza + alta affinità label
            if (personality['consistency_score'] > high_consistency and 
                personality['label_affinity'] > high_label_affinity):
                archetypes['semantic_heavy'].append((feature_key, personality))
            
            # Computational: bassa consistenza ma alta influenza sociale
            elif (personality['consistency_score'] < high_consistency and 
                  personality['social_influence'] > high_social):
                archetypes['computational'].append((feature_key, personality))
            
            # Outlier: comportamento instabile
            elif (personality['max_ratio'] > 2 or 
                  personality['consistency_std'] > self._percentile([p['consistency_std'] for p in personalities.values()], 90)):
                archetypes['outliers'].append((feature_key, personality))
            
            # Stable workers: tutto il resto con buona consistenza
            elif personality['consistency_score'] > 0.3:
                archetypes['stable_workers'].append((feature_key, personality))
        
        print("\n🎭 Archetipi identificati:")
        for archetype, features in archetypes.items():
            print(f"   {archetype}: {len(features)} feature")
            
            # Mostra esempi per i primi archetipi
            if features and archetype in ['semantic_heavy', 'computational']:
                print(f"      Esempi: {[f[0] for f in features[:3]]}")
        
        return archetypes
    
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
        
        # Salvataggio risultati preliminari come JSON
        print("💾 Salvataggio risultati...")
        
        # Converte personalities per JSON
        personalities_json = {}
        for key, personality in personalities.items():
            personalities_json[f"{key[0]}_{key[1]}"] = personality
        
        with open("output/feature_personalities_preliminary.json", 'w') as f:
            json.dump(personalities_json, f, indent=2)
        
        print(f"\n✅ Analisi preliminare completata!")
        print(f"📁 Salvato: output/feature_personalities_preliminary.json")
        
        return personalities, archetypes
        
    except Exception as e:
        print(f"❌ Errore durante l'analisi: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    print("🔬 Avvio script di analisi antropologica...")
    main()
