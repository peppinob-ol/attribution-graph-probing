"""Configurazione default per parametri slider e range"""

# Range parametri Fase 2 (crescita supernodi)
PHASE2_DEFAULTS = {
    'causal_weight': 0.60,  # Peso compatibilità causale (0.4-0.8)
    'tau_edge_strong': 0.05,  # Soglia edge forti (0.02-0.10)
    'tau_edge_bootstrap': 0.03,  # Soglia bootstrap (0.01-0.05)
    'bootstrap_iterations': 3,  # Iterazioni bootstrap (0-5)
    'threshold_bootstrap': 0.30,  # Soglia accettazione bootstrap (0.1-0.5)
    'threshold_normal': 0.45,  # Soglia accettazione normale (0.3-0.7)
    'min_coherence': 0.50,  # Coerenza minima (0.3-0.8)
    'max_iterations': 20,  # Iterazioni max (5-30)
    'max_seeds': 50,  # Numero max seed (5-50)
    'diversify': True,  # Diversificazione layer/position
}

# Range parametri Fase 3 (clustering residui)
PHASE3_DEFAULTS = {
    'min_cluster_size': 3,  # Minimo membri cluster (2-10)
    'jaccard_merge_threshold': 0.70,  # Soglia merge Jaccard (0.5-0.9)
    'min_frequency_ratio': 0.02,  # Ratio token semantici (0.01-0.05)
    'min_frequency_absolute': 3,  # Minimo assoluto token
    'layer_group_span': 3,  # Span gruppi layer (2-5)
    'node_inf_high': 0.10,  # Soglia node_influence HIGH (0.05-0.2)
    'node_inf_med': 0.01,  # Soglia node_influence MED (0.005-0.05)
}

# Parametri generali
GENERAL_DEFAULTS = {
    'use_causal_graph': True,  # Usa grafo causale se disponibile
    'archetype_percentile': 75,  # Percentile archetipi (75-90)
}

# Paths output
OUTPUT_PATHS = {
    'personalities': 'output/feature_personalities_corrected.json',
    'archetypes': 'output/narrative_archetypes.json',
    'cicciotti': 'output/cicciotti_supernodes.json',
    'validation': 'output/cicciotti_validation.json',
    'final': 'output/final_anthropological_optimized.json',
    'thresholds': 'output/robust_thresholds.json',
    'static_metrics': 'output/graph_feature_static_metrics (1).csv',
    'acts': 'output/acts_compared.csv',
    'graph': 'output/example_graph.pt',
    'labels': 'output/comprehensive_supernode_labels.json',
}

# Export paths
EXPORT_DIR = 'eda/exports'

