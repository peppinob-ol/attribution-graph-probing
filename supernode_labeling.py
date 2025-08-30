#!/usr/bin/env python3
"""
Sistema di labeling automatico per supernodi antropologici
Genera label descrittivi e interpretativi per i supernodi
"""

import json
import csv
from collections import Counter, defaultdict
from typing import Dict, List, Tuple, Optional

class SupernodeLabeler:
    """
    Generatore di label interpretativi per supernodi antropologici
    
    Strategie:
    1. Pattern Analysis: Analizza token patterns e layer distributions
    2. Semantic Clustering: Raggruppa token semanticamente simili  
    3. LLM Auto-Interpretation: Usa LLM per generare descrizioni
    4. Context Analysis: Considera il ruolo nel circuito completo
    """
    
    def __init__(self):
        self.supernodes_data = {}
        self.personalities = {}
        self.acts_data = []
        self.labeled_supernodes = {}
        
    def load_data(self):
        """Carica dati necessari per labeling"""
        print("📥 Caricamento dati per labeling...")
        
        try:
            # Supernodi finali
            with open("output/final_anthropological_optimized.json", 'r') as f:
                results = json.load(f)
                self.supernodes_data = {
                    **results.get('semantic_supernodes', {}),
                    **results.get('computational_supernodes', {})
                }
            
            # Personalità feature
            with open("output/feature_personalities_corrected.json", 'r') as f:
                self.personalities = json.load(f)
            
            # Dati attivazioni
            with open("output/acts_compared.csv", 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                self.acts_data = list(reader)
            
            print(f"✅ Caricati {len(self.supernodes_data)} supernodi")
            print(f"✅ Caricati {len(self.personalities)} personalità")
            print(f"✅ Caricati {len(self.acts_data)} record attivazioni")
            
            return True
            
        except Exception as e:
            print(f"❌ Errore: {e}")
            return False
    
    def analyze_supernode_patterns(self, supernode_id: str, members: List[str]) -> Dict:
        """
        Strategia 1: Pattern Analysis
        Analizza pattern quantitativi dei membri del supernodo
        """
        
        # Raccogli statistiche membri
        layers = []
        peak_tokens = []
        consistencies = []
        avg_twera = 0
        label_affinities = []
        
        for member in members:
            if member in self.personalities:
                p = self.personalities[member]
                layers.append(p['layer'])
                peak_tokens.append(p['most_common_peak'])
                consistencies.append(p['consistency_score'])
                avg_twera += p.get('avg_twera', 0)
                label_affinities.append(p.get('label_affinity', 0))
        
        if len(members) > 0:
            avg_twera /= len(members)
        
        # Analizza pattern
        pattern_analysis = {
            'layer_distribution': {
                'min': min(layers) if layers else 0,
                'max': max(layers) if layers else 0,
                'most_common': Counter(layers).most_common(1)[0] if layers else (0, 0),
                'span': (max(layers) - min(layers)) if layers else 0
            },
            
            'token_patterns': {
                'dominant_token': Counter(peak_tokens).most_common(1)[0] if peak_tokens else ('unknown', 0),
                'token_diversity': len(set(peak_tokens)),
                'all_tokens': dict(Counter(peak_tokens))
            },
            
            'behavioral_metrics': {
                'avg_consistency': sum(consistencies) / len(consistencies) if consistencies else 0,
                'consistency_std': self._std(consistencies) if len(consistencies) > 1 else 0,
                'avg_label_affinity': sum(label_affinities) / len(label_affinities) if label_affinities else 0,
                'avg_twera': avg_twera
            },
            
            'size_metrics': {
                'n_members': len(members),
                'layer_concentration': (Counter(layers).most_common(1)[0][1] / len(layers)) if layers else 0
            }
        }
        
        return pattern_analysis
    
    def generate_pattern_based_label(self, supernode_id: str, pattern_analysis: Dict) -> str:
        """
        Genera label basato su pattern analysis quantitativo
        """
        
        token_info = pattern_analysis['token_patterns']
        layer_info = pattern_analysis['layer_distribution']
        behavioral = pattern_analysis['behavioral_metrics']
        size = pattern_analysis['size_metrics']
        
        # Token dominante
        dominant_token, token_count = token_info['dominant_token']
        token_dominance = token_count / size['n_members'] if size['n_members'] > 0 else 0
        
        # Layer characterization
        layer_span = layer_info['span']
        layer_focus = layer_info['most_common'][0] if layer_info['most_common'][1] > 0 else 0
        
        # Behavioral characterization
        consistency = behavioral['avg_consistency']
        label_affinity = behavioral['avg_label_affinity']
        
        # Genera nome basato su pattern
        name_parts = []
        
        # Parte 1: Token semantic
        if dominant_token != '<BOS>' and token_dominance > 0.5:
            if dominant_token in {'of', 'is', 'the', 'in', ':', '.'}:
                name_parts.append(f"Structural-{dominant_token}")
            else:
                name_parts.append(f"Entity-{dominant_token}")
        else:
            name_parts.append("Mixed-tokens")
        
        # Parte 2: Layer characterization
        if layer_span <= 2:
            name_parts.append(f"L{layer_focus}")
        elif layer_span <= 5:
            name_parts.append(f"L{layer_info['min']}-{layer_info['max']}")
        else:
            name_parts.append("Cross-layer")
        
        # Parte 3: Behavioral type
        if consistency > 0.7 and label_affinity > 0.5:
            name_parts.append("Stable")
        elif consistency > 0.5:
            name_parts.append("Consistent")
        elif label_affinity > 0.5:
            name_parts.append("Label-focused")
        else:
            name_parts.append("Variable")
        
        # Costruisci nome finale
        pattern_label = "_".join(name_parts)
        return f"{pattern_label} ({size['n_members']})"
    
    def generate_semantic_interpretation_prompt(self, supernode_id: str, pattern_analysis: Dict) -> str:
        """
        Strategia 2: Genera prompt per LLM auto-interpretation
        """
        
        token_info = pattern_analysis['token_patterns']
        layer_info = pattern_analysis['layer_distribution']
        behavioral = pattern_analysis['behavioral_metrics']
        
        # Costruisci contesto per LLM
        context = f"""
Analizza questo supernodo di feature neurali e fornisci un nome interpretativo conciso (max 3-4 parole).

CONTESTO: Questo è un cluster di {pattern_analysis['size_metrics']['n_members']} feature neurali che si attivano insieme in un modello linguistico sul prompt "The capital of state containing Dallas is".

PATTERN QUANTITATIVI:
- Token più frequente: "{token_info['dominant_token'][0]}" (appare in {token_info['dominant_token'][1]}/{pattern_analysis['size_metrics']['n_members']} feature)
- Layer range: {layer_info['min']}-{layer_info['max']} (span: {layer_info['span']})
- Consistenza cross-prompt: {behavioral['avg_consistency']:.3f}
- Affinità per label: {behavioral['avg_label_affinity']:.3f}
- Diversità token: {token_info['token_diversity']} tipi unici

TUTTI I TOKEN: {list(token_info['all_tokens'].keys())}

ESEMPI SIMILI DA ANTHROPIC:
- "Texas" (per feature che si attivano su token Texas)
- "Say a capital" (per feature che promuovono output di capitali)
- "State containment" (per relazioni geografiche)
- "Entity disambiguation" (per disambiguazione nomi)

ISTRUZIONI:
Fornisci un nome descrittivo che catturi il ruolo semantico di questo cluster nel circuito neurale.
Il nome deve essere:
1. Conciso (max 4 parole)
2. Interpretativo (descrive cosa fa il cluster)
3. Specifico al contesto geografico-fattuale

Nome suggerito:"""

        return context
    
    def generate_llm_based_labels(self, use_mock=True) -> Dict[str, str]:
        """
        Strategia 3: Auto-interpretation con LLM
        
        Args:
            use_mock: Se True, usa mock responses invece di chiamate LLM reali
        """
        print(f"\n🤖 GENERAZIONE LABEL CON LLM AUTO-INTERPRETATION")
        print("=" * 50)
        
        llm_labels = {}
        
        for supernode_id, data in self.supernodes_data.items():
            members = data.get('members', [])
            if not members:
                continue
            
            # Analizza pattern per questo supernodo
            pattern_analysis = self.analyze_supernode_patterns(supernode_id, members)
            
            if use_mock:
                # Mock interpretation basata su pattern
                llm_label = self.generate_mock_interpretation(supernode_id, pattern_analysis)
            else:
                # TODO: Implementare chiamata LLM reale
                prompt = self.generate_semantic_interpretation_prompt(supernode_id, pattern_analysis)
                llm_label = "TODO_LLM_CALL"  # Placeholder
            
            llm_labels[supernode_id] = llm_label
            
            print(f"   {supernode_id}: {llm_label}")
        
        return llm_labels
    
    def generate_mock_interpretation(self, supernode_id: str, pattern_analysis: Dict) -> str:
        """
        Genera interpretazione mock basata su pattern per testing
        """
        
        token_info = pattern_analysis['token_patterns']
        layer_info = pattern_analysis['layer_distribution']
        behavioral = pattern_analysis['behavioral_metrics']
        
        dominant_token = token_info['dominant_token'][0]
        layer_focus = layer_info['most_common'][0]
        consistency = behavioral['avg_consistency']
        label_affinity = behavioral['avg_label_affinity']
        
        # Regole euristica per generare interpretazioni mock
        
        # Geographic entity detection
        if dominant_token in {'Dallas', 'Texas', 'Austin'}:
            if layer_focus <= 5:
                return f"Entity: {dominant_token}"
            else:
                return f"Geographic: {dominant_token}"
        
        # Structural/relational patterns  
        elif dominant_token in {'of', 'in', 'state', 'capital'}:
            if consistency > 0.6:
                if dominant_token == 'of':
                    return "Containment Relations"
                elif dominant_token == 'state':
                    return "State References"
                elif dominant_token == 'capital':
                    return "Capital Concepts"
                else:
                    return f"Structural: {dominant_token}"
            else:
                return f"Variable: {dominant_token}"
        
        # Output generation patterns
        elif layer_focus >= 20:
            if label_affinity > 0.5:
                return f"Output: {dominant_token}"
            else:
                return "Late Processing"
        
        # Middle layer processing
        elif 10 <= layer_focus <= 19:
            if consistency > 0.7:
                return f"Semantic: {dominant_token}"
            else:
                return f"Integration: {dominant_token}"
        
        # Early processing
        elif layer_focus <= 9:
            if dominant_token == '<BOS>':
                return f"Input Processing L{layer_focus}"
            else:
                return f"Early: {dominant_token}"
        
        # Fallback
        else:
            return f"Mixed: {dominant_token}"
    
    def validate_label_quality(self, supernode_id: str, label: str, pattern_analysis: Dict) -> Dict:
        """
        Strategia 4: Valida qualità del label generato
        """
        
        quality_metrics = {
            'interpretability': 0,
            'specificity': 0, 
            'consistency_with_data': 0,
            'brevity': 0,
            'overall_score': 0
        }
        
        # Interpretability: evita nomi generici
        generic_terms = {'Mixed', 'Variable', 'Unknown', 'Other', 'Cluster'}
        if not any(term in label for term in generic_terms):
            quality_metrics['interpretability'] = 1
        
        # Specificity: include informazioni specifiche
        token_info = pattern_analysis['token_patterns']
        dominant_token = token_info['dominant_token'][0]
        if dominant_token != '<BOS>' and dominant_token in label:
            quality_metrics['specificity'] = 1
        
        # Consistency: coerente con behavioral patterns
        behavioral = pattern_analysis['behavioral_metrics']
        if behavioral['avg_consistency'] > 0.6 and 'Stable' in label:
            quality_metrics['consistency_with_data'] += 0.5
        if behavioral['avg_label_affinity'] > 0.5 and ('Entity' in label or 'Output' in label):
            quality_metrics['consistency_with_data'] += 0.5
        
        # Brevity: non troppo lungo
        if len(label.split()) <= 4:
            quality_metrics['brevity'] = 1
        
        # Overall score
        quality_metrics['overall_score'] = sum(quality_metrics.values()) / 4
        
        return quality_metrics
    
    def generate_comprehensive_labels(self) -> Dict[str, Dict]:
        """
        Genera label usando tutte le strategie e sceglie il migliore
        """
        print(f"\n🏷️  GENERAZIONE LABEL COMPRENSIVA")
        print("=" * 50)
        
        comprehensive_labels = {}
        
        for supernode_id, data in self.supernodes_data.items():
            members = data.get('members', [])
            if not members:
                continue
            
            print(f"\n🔍 Labeling {supernode_id} ({len(members)} membri)")
            
            # Strategia 1: Pattern Analysis
            pattern_analysis = self.analyze_supernode_patterns(supernode_id, members)
            pattern_label = self.generate_pattern_based_label(supernode_id, pattern_analysis)
            
            # Strategia 2: Mock LLM Interpretation
            mock_llm_label = self.generate_mock_interpretation(supernode_id, pattern_analysis)
            
            # Strategia 3: Context-aware labeling (per i semantici)
            context_label = self.generate_context_aware_label(supernode_id, pattern_analysis, data)
            
            # Valida qualità label
            pattern_quality = self.validate_label_quality(supernode_id, pattern_label, pattern_analysis)
            mock_quality = self.validate_label_quality(supernode_id, mock_llm_label, pattern_analysis)
            context_quality = self.validate_label_quality(supernode_id, context_label, pattern_analysis)
            
            # Scegli miglior label
            candidates = [
                (pattern_label, pattern_quality['overall_score'], 'pattern'),
                (mock_llm_label, mock_quality['overall_score'], 'mock_llm'),
                (context_label, context_quality['overall_score'], 'context')
            ]
            
            best_label, best_score, best_method = max(candidates, key=lambda x: x[1])
            
            comprehensive_labels[supernode_id] = {
                'final_label': best_label,
                'quality_score': best_score,
                'method_used': best_method,
                'all_candidates': {
                    'pattern': pattern_label,
                    'mock_llm': mock_llm_label,
                    'context': context_label
                },
                'pattern_analysis': pattern_analysis
            }
            
            print(f"   ✅ Label scelto: '{best_label}' (score: {best_score:.3f}, metodo: {best_method})")
        
        return comprehensive_labels
    
    def generate_context_aware_label(self, supernode_id: str, pattern_analysis: Dict, supernode_data: Dict) -> str:
        """
        Strategia 3: Context-aware labeling
        Considera il ruolo del supernodo nel circuito completo
        """
        
        token_info = pattern_analysis['token_patterns']
        layer_info = pattern_analysis['layer_distribution']
        behavioral = pattern_analysis['behavioral_metrics']
        
        dominant_token = token_info['dominant_token'][0]
        layer_focus = layer_info['most_common'][0]
        supernode_type = supernode_data.get('type', 'unknown')
        
        # Context-aware interpretation per tipo
        if supernode_type == 'semantic':
            # Supernodi semantici: focus su ruolo semantico
            
            if dominant_token == 'Capital' and behavioral['avg_consistency'] > 0.7:
                return "Capital Cities Concept"
            elif dominant_token == 'Texas' and layer_focus > 15:
                return "Texas State Recognition"
            elif dominant_token == 'Dallas' and layer_focus < 10:
                return "Dallas Entity Detection"
            elif dominant_token == 'Austin' and layer_focus > 20:
                return "Austin Capital Output"
            elif 'of' in token_info['all_tokens'] and behavioral['avg_label_affinity'] > 0.4:
                return "Geographic Relations"
            elif layer_focus > 20:
                return f"Output Generation: {dominant_token}"
            else:
                return f"Semantic Processing: {dominant_token}"
                
        else:  # computational
            # Supernodi computazionali: focus su ruolo computazionale
            
            cluster_signature = supernode_data.get('cluster_signature', '')
            if 'HIGH' in cluster_signature:
                return f"High-Confidence {dominant_token} Processing"
            elif 'MED' in cluster_signature:
                return f"Medium-Level {dominant_token} Computation"
            elif 'LOW' in cluster_signature:
                return f"Low-Level {dominant_token} Routing"
            elif layer_focus <= 5:
                return f"Early Processing: {dominant_token}"
            elif layer_focus >= 20:
                return f"Late Processing: {dominant_token}"
            else:
                return f"Mid Computation: {dominant_token}"
    
    def create_labeled_visualization_data(self, comprehensive_labels: Dict) -> Dict:
        """
        Crea dati per visualizzazione con label migliorati
        """
        print(f"\n📊 CREAZIONE DATI VISUALIZZAZIONE CON LABEL")
        print("=" * 50)
        
        labeled_data = {
            'supernodes': [],
            'statistics': {
                'total_supernodes': len(comprehensive_labels),
                'avg_quality_score': sum(data['quality_score'] for data in comprehensive_labels.values()) / len(comprehensive_labels),
                'label_methods': Counter(data['method_used'] for data in comprehensive_labels.values())
            }
        }
        
        # Converti ogni supernodo con label migliorato
        for supernode_id, label_data in comprehensive_labels.items():
            supernode_info = self.supernodes_data.get(supernode_id, {})
            
            labeled_supernode = {
                'original_id': supernode_id,
                'interpretive_label': label_data['final_label'],
                'quality_score': label_data['quality_score'],
                'labeling_method': label_data['method_used'],
                'n_members': len(supernode_info.get('members', [])),
                'supernode_type': supernode_info.get('type', 'unknown'),
                
                # Pattern insights
                'dominant_token': label_data['pattern_analysis']['token_patterns']['dominant_token'][0],
                'layer_range': f"{label_data['pattern_analysis']['layer_distribution']['min']}-{label_data['pattern_analysis']['layer_distribution']['max']}",
                'avg_consistency': label_data['pattern_analysis']['behavioral_metrics']['avg_consistency']
            }
            
            labeled_data['supernodes'].append(labeled_supernode)
        
        # Ordina per quality score
        labeled_data['supernodes'].sort(key=lambda x: x['quality_score'], reverse=True)
        
        print(f"✅ {len(labeled_data['supernodes'])} supernodi etichettati")
        print(f"📊 Score qualità medio: {labeled_data['statistics']['avg_quality_score']:.3f}")
        print(f"📋 Metodi usati: {dict(labeled_data['statistics']['label_methods'])}")
        
        return labeled_data
    
    def _std(self, values):
        """Standard deviation"""
        if len(values) <= 1:
            return 0
        mean = sum(values) / len(values)
        variance = sum((x - mean) ** 2 for x in values) / (len(values) - 1)
        return variance ** 0.5

def main():
    """Pipeline completa di labeling supernodi"""
    
    print("🏷️  SISTEMA LABELING SUPERNODI ANTROPOLOGICI")
    print("=" * 60)
    
    labeler = SupernodeLabeler()
    
    if not labeler.load_data():
        return
    
    # Genera label comprensivi
    comprehensive_labels = labeler.generate_comprehensive_labels()
    
    # Crea dati visualizzazione con label
    labeled_visualization_data = labeler.create_labeled_visualization_data(comprehensive_labels)
    
    # Salva risultati
    print(f"\n💾 Salvataggio risultati labeling...")
    
    with open("output/comprehensive_supernode_labels.json", 'w') as f:
        json.dump(comprehensive_labels, f, indent=2)
    
    with open("output/labeled_visualization_data.json", 'w') as f:
        json.dump(labeled_visualization_data, f, indent=2)
    
    print(f"✅ Labeling completato!")
    print(f"📁 Label completi: output/comprehensive_supernode_labels.json")
    print(f"📁 Dati visualizzazione: output/labeled_visualization_data.json")
    
    # Summary top 10
    print(f"\n🏆 TOP 10 LABEL GENERATI:")
    for i, supernode in enumerate(labeled_visualization_data['supernodes'][:10]):
        print(f"   {i+1:2d}. {supernode['interpretive_label']} "
              f"(score: {supernode['quality_score']:.3f}, "
              f"metodo: {supernode['labeling_method']}, "
              f"membri: {supernode['n_members']})")
    
    return comprehensive_labels, labeled_visualization_data

if __name__ == "__main__":
    main()
