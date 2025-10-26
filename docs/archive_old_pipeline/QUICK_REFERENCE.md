# Quick Reference - Anthropological Feature Analysis Pipeline

**TL;DR**: Pipeline per analisi antropologica di feature LLM con influence-first filtering.

---

## 🚀 Quick Start

```bash
# Pipeline completa (in ordine)
python anthropological_basic.py          # 1. Analisi personalities
python compute_thresholds.py            # 2. Calcola thresholds
python cicciotti_supernodes.py          # 3. Supernodi semantici
python final_optimized_clustering.py    # 4. Clustering computazionale
python verify_logit_influence.py        # 5. Validazione
python visualize_feature_space_3d.py    # 6. Visualizzazioni
python export_to_neuronpedia_improved.py # 7. Export Neuronpedia
```

---

## 📊 File Python - Cheat Sheet

| Script | Input | Output | Scopo |
|--------|-------|--------|-------|
| `anthropological_basic.py` | `gemma_sae_graph.json` | `feature_personalities_corrected.json`<br>`feature_typology.json`<br>`quality_scores.json`<br>`metric_correlations.json` | Calcola metriche feature (consistency, affinity, influence) e classifica in typology |
| `compute_thresholds.py` | `feature_personalities_corrected.json` | `robust_thresholds.json` | Calcola τ_inf, τ_aff, τ_cons per influence-first filtering |
| `cicciotti_supernodes.py` | `feature_personalities_corrected.json` | `cicciotti_supernodes.json` | Crea supernodi semantici (seed influence-first) |
| `final_optimized_clustering.py` | `cicciotti_supernodes.json`<br>`robust_thresholds.json` | `final_anthropological_optimized.json` | Clustering computazionale + merge finale |
| `verify_logit_influence.py` | `final_anthropological_optimized.json` | `logit_influence_validation.json` | Valida coverage logit influence |
| `visualize_feature_space_3d.py` | `feature_typology.json` | `feature_space_3d.png` | Plot 3D dello spazio typology |
| `export_to_neuronpedia_improved.py` | `final_anthropological_optimized.json` | `neuronpedia_url_improved.txt` | Export supernodi su Neuronpedia |
| `analyze_remaining_excluded.py` | `final_anthropological_optimized.json`<br>`robust_thresholds.json` | `excluded_features_analysis.json` | Analisi feature escluse |

---

## 🔑 Metriche Chiave

### Feature-Level Metrics

```python
# Generalizzabilità (stabilità cross-prompt)
mean_consistency = mean(cosine_similarities)  # 0-1

# Specializzazione (affinità semantica)
max_affinity = max(cosine_similarities)  # 0-1

# Consistency condizionale (solo quando attiva)
conditional_consistency = mean(cosines[activations > threshold])  # 0-1

# Causalità (impatto su output)
logit_influence = from_circuit_tracer()  # 0-1

# Threshold attivazione adattivo
activation_threshold = min(p75(activations), otsu(activations))
```

### Typology Classification

| Type | Condition | Esempio |
|------|-----------|---------|
| **Generalist** | High consistency + High affinity + Low influence | "of", "the" |
| **Specialist** | Low consistency + High affinity + High influence | "Capital", "Texas" |
| **Computational** | High consistency + Low affinity + Low influence | Token position markers |
| **Hybrid** | Mixed properties | Various |

### Quality Score

```python
Quality = α·InfluenceCoverage + β·MeanConsistency + γ·MaxAffinity
# Default: α=0.6, β=0.2, γ=0.2
```

---

## 🎯 Thresholds Influence-First

```python
# Admissione feature
admitted = (logit_influence >= τ_inf) OR (max_affinity >= τ_aff)

# Thresholds
τ_inf = max(p80_cumulative, p90)  # ~0.0056
τ_aff = 0.60
τ_cons = 0.60  # Solo labeling, non filter

# BOS filter
if token == '<BOS>' and logit_influence < τ_inf_very_high:
    exclude()  # τ_inf_very_high = p95 (~0.0235)
```

---

## 📈 Risultati Attuali

| Metrica | Valore | Target | Status |
|---------|--------|--------|--------|
| **Logit Influence Coverage** | 52.3% | ≥50% | ✅ |
| **BOS Leakage** | 2.4% | <30% | ✅ |
| **Feature Coperte** | 483 | ≥400 | ✅ |
| **Supernodi** | 23 | 15-30 | ✅ |
| **Situational Core** | 89 features | - | - |
| **Generalizable Scaffold** | 124 features | - | - |

---

## 🔧 Common Issues

### Coverage troppo bassa

```bash
# 1. Analizza feature escluse
python analyze_remaining_excluded.py

# 2. Rilassa thresholds in compute_thresholds.py:
τ_aff = 0.50  # invece di 0.60

# 3. Rigenera pipeline da step 2
```

### KeyError: 'consistency_score'

```python
# Usa graceful fallback
consistency = p.get('conditional_consistency',
               p.get('mean_consistency',
                p.get('consistency_score', 0)))
```

### UnicodeEncodeError (Windows)

```powershell
$env:PYTHONIOENCODING='utf-8'
python script.py
```

---

## 📁 Output Files Reference

### Core Outputs

```
output/
├── feature_personalities_corrected.json  # Tutte metriche per feature
├── feature_typology.json                 # Classificazione per tipo
├── robust_thresholds.json                # Thresholds influence-first
├── final_anthropological_optimized.json  # Supernodi finali
└── logit_influence_validation.json       # Validazione coverage
```

### Visualizations & Export

```
output/
├── feature_space_3d.png                  # Plot 3D typology
├── neuronpedia_url_improved.txt          # URL Neuronpedia
└── neuronpedia_supernodes_improved.json  # Supernodi formato Neuronpedia
```

---

## 🧪 Key Algorithms

### Seed Selection (Influence-First)

```python
def select_seeds(features):
    return sorted(features,
                  key=lambda f: (f['logit_influence'], f['max_affinity']),
                  reverse=True)
```

### Narrative Compatibility

```python
def compute_compatibility(seed, candidate):
    return (
        0.4 * cosine_similarity(patterns) +
        0.3 * jaccard_similarity(concept_peaks) +
        0.2 * (1 - abs(consistency_diff)) +
        0.1 * (1 - layer_distance)
    )
```

### Adaptive Threshold

```python
def adaptive_threshold(activations):
    thr_p75 = percentile(activations, 75)
    thr_otsu = otsu_threshold(activations)
    return min(thr_p75, thr_otsu)
```

---

## 🌐 Neuronpedia Export

```bash
# 1. Genera export
python export_to_neuronpedia_improved.py

# 2. Apri output/neuronpedia_url_improved.txt
# 3. Copia URL completo
# 4. Incolla nel browser

# Risultato: grafo interattivo con 23 supernodi, 483 feature
```

**Features**:
- Nomi distintivi con layer range (es. `Capital_L0-15`)
- Supernodi semantici + computazionali
- Interventions interattive
- Condivisibile via URL

---

## 📚 Documentation

| File | Scopo |
|------|-------|
| `README.md` | Documentazione completa pipeline |
| `QUICK_REFERENCE.md` | Questo file - cheat sheet |
| `NEURONPEDIA_EXPORT_GUIDE.md` | Guida export Neuronpedia |
| `influence_first_summary.md` | Metodologia influence-first |
| `plan.md` | Piano refactoring originale |

---

## 🔗 Links Utili

- **Circuit Tracer**: https://github.com/safety-research/circuit-tracer
- **Neuronpedia**: https://www.neuronpedia.org
- **Paper**: https://transformer-circuits.pub/2025/attribution-graphs/

---

**Version**: 2.0 (Influence-First)  
**Model**: Gemma-2-2B  
**Last Updated**: 2025-10-08




