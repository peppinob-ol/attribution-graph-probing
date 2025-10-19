# Circuit Analysis Pipeline: Anthropological Feature Analysis

**Analisi antropologica delle feature di LLM attraverso Circuit Tracing e semantic clustering influence-first.**

---

## 📊 Quick Start

```bash
# Apri il notebook unificato
jupyter notebook circuit_analysis_pipeline.ipynb

# Oppure esegui la pipeline da terminale
python anthropological_basic.py
python compute_thresholds.py
python cicciotti_supernodes.py
python final_optimized_clustering.py
python verify_logit_influence.py
```

---

## 🎯 Overview

Questo progetto implementa un'analisi antropologica delle feature estratte da attribution graph generati con [Circuit Tracer](https://github.com/safety-research/circuit-tracer) (Anthropic).

### Risultati

- ✅ **52.3% logit influence coverage**
- ✅ **23 supernodi** (15 semantici + 8 computazionali)
- ✅ **483 feature** coperte
- ✅ **2.4% BOS leakage** (controllato)

### Metodologia Chiave

- **Influence-First Filtering**: Ammissione basata su causalità (`logit_influence >= τ_inf`)
- **Dual View**: "Situational Core" (causalmente determinante) vs "Generalizable Scaffold" (stabile cross-prompt)
- **Supernodi Semantici**: Clustering narrativo con crescita controllata da coherence
- **Validazione Empirica**: Coverage logit influence + correlazioni metriche

---

## 🔄 Workflow

```
┌──────────────────────────────────────┐
│  FASE COLAB                          │
│  • Circuit Tracer + Gemma-2-2B       │
│  • Prompt: "The capital of state...  │
├──────────────────────────────────────┤
│  OUTPUT:                             │
│  1. example_graph.pt                 │
│  2. graph_feature_static_metrics.csv │
│  3. acts_compared.csv                │
└──────────────────────────────────────┘
              ↓
┌──────────────────────────────────────┐
│  FASE LOCALE                         │
│                                      │
│  Step 1: Anthropological Basic      │
│    → feature_personalities.json      │
│                                      │
│  Step 2: Compute Thresholds         │
│    → robust_thresholds.json          │
│                                      │
│  Step 3: Cicciotti Supernodes       │
│    → cicciotti_supernodes.json       │
│                                      │
│  Step 4: Final Clustering           │
│    → final_optimized.json            │
│                                      │
│  Step 5: Verify Logit Influence     │
│    → logit_influence_validation.json │
└──────────────────────────────────────┘
```

---

## 📁 Struttura Progetto

```
circuit_tracer-prompt_rover/
├── circuit_analysis_pipeline.ipynb  # 🆕 Notebook unificato (START HERE)
│
├── anthropological_basic.py         # Core: analisi personalities
├── compute_thresholds.py            # Calcolo soglie robuste
├── cicciotti_supernodes.py          # Supernodi semantici
├── final_optimized_clustering.py    # Clustering computazionale
├── verify_logit_influence.py        # Validazione coverage
│
├── scripts/
│   ├── 02_anthropological_basic.py   # Pipeline ordinata
│   ├── 03_compute_thresholds.py
│   ├── 04_cicciotti_supernodes.py
│   ├── 05_final_optimized_clustering.py
│   ├── 06_verify_logit_influence.py
│   │
│   ├── visualization/
│   │   ├── visualize_feature_space_3d.py
│   │   └── neuronpedia_export.py
│   │
│   ├── analysis/
│   │   └── analyze_remaining_excluded.py
│   │
│   └── legacy/                       # File vecchi/sperimentali
│
├── output/                           # File generati dalla pipeline
├── docs/                             # Documentazione metodologica
├── figures/                          # Visualizzazioni generate
│
└── README.md                         # Questo file
```

---

## 🚀 Setup

### Prerequisiti

```bash
# Python 3.8+
pip install numpy scipy scikit-learn scikit-image matplotlib pandas
```

### File di Input (da Colab)

Prima di eseguire la pipeline locale, scarica questi file da Colab nella cartella `output/`:

1. **`example_graph.pt`** - Attribution graph (~167MB)
2. **`graph_feature_static_metrics.csv`** - Metriche statiche per feature
3. **`acts_compared.csv`** - Attivazioni su concetti semantici

Vedi `circuit_analysis_pipeline.ipynb` per dettagli su come generare questi file.

---

## 📊 Pipeline Dettagliata

### Step 1: Anthropological Basic

**Calcola metriche antropologiche per ogni feature:**

- `mean_consistency`: Generalizzabilità cross-prompt (media cosine similarity)
- `max_affinity`: Specializzazione semantica (max cosine similarity)
- `conditional_consistency`: Consistency solo quando feature è attiva
- `activation_threshold`: Soglia adattiva (ibrido p75 + Otsu)

**Output:**
- `feature_personalities_corrected.json`
- `feature_typology.json` (generalist/specialist/computational/hybrid)
- `quality_scores.json`
- `metric_correlations.json`

```bash
python anthropological_basic.py
```

### Step 2: Compute Robust Thresholds

**Calcola soglie robuste per influence-first filtering:**

```python
# Criterio ammissione
admitted = (logit_influence >= τ_inf) OR (max_affinity >= τ_aff)

# Eccezione BOS: se peak_token == '<BOS>', richiedi logit_influence >= τ_inf_very_high
```

**Thresholds:**
- **τ_inf**: max(p90, cutoff_80% cumulata) - ~0.0056
- **τ_aff**: 0.60 (configurabile)
- **τ_inf_very_high**: p95 - ~0.0235 (BOS filter)

**Output:** `robust_thresholds.json`

```bash
python compute_thresholds.py
```

### Step 3: Cicciotti Supernodes (Semantic)

**Costruisce supernodi semantici tramite:**

1. **Seed selection influence-first**: Ordina per (logit_influence, max_affinity) decrescente
2. **Narrative-guided growth**: Aggiungi feature con compatibilità narrativa > soglia
3. **Coherence tracking**: Stop quando coherence < soglia minima

**Compatibilità narrativa:**
```python
compatibility = (
    0.4 * cosine_similarity(patterns) +
    0.3 * jaccard_similarity(concept_peaks) +
    0.2 * (1 - abs(consistency_diff)) +
    0.1 * (1 - layer_distance)
)
```

**Output:** `cicciotti_supernodes.json`

```bash
python cicciotti_supernodes.py
```

### Step 4: Final Optimized Clustering

**Clusterizza feature residue (non nei supernodi semantici):**

- Identifica quality residuals con τ_inf/τ_aff
- Clustering per `dominant_token` e `layer_range`
- Merge con supernodi semantici

**Output:** `final_anthropological_optimized.json`

```bash
python final_optimized_clustering.py
```

### Step 5: Verify Logit Influence

**Valida copertura logit influence dei supernodi:**

- Calcola % influence totale coperta
- Breakdown per feature type
- Rating: EXCELLENT (≥80%) / GOOD (60-79%) / MODERATE (40-59%) / WEAK (<40%)

**Output:** `logit_influence_validation.json`

```bash
python verify_logit_influence.py
```

### Step 6: Export Neuronpedia (Opzionale)

**Genera Graph JSON con supernodi per Neuronpedia:**

```powershell
# Step 1: Fix e aggiungi supernodi (gestisce Cantor pairing)
python scripts/visualization/fix_neuronpedia_export.py

# Step 2: Carica su Neuronpedia via API
pip install neuronpedia
python scripts/visualization/upload_to_neuronpedia.py
```

**Output:** `output/neuronpedia_graph_with_subgraph.json` (23.8 MB)
- 112 supernodi (semantici + computazionali)
- 409 feature pinnate
- Conforme allo schema Neuronpedia Attribution Graph

**Note:**
- Il validator UI non funziona per file grandi (>20 MB)
- Usa l'API Python per l'upload
- I supernodi appaiono automaticamente nella sidebar del graph viewer

Vedi `docs/NEURONPEDIA_UPLOAD_COMPLETE.md` per la guida completa.

### Step 7: Visualizzazioni (Opzionale)

```bash
python scripts/visualization/visualize_feature_space_3d.py
```

---

## 📈 Metriche Chiave

### Feature-Level Metrics

| Metrica | Range | Significato |
|---------|-------|-------------|
| `mean_consistency` | 0-1 | Generalizzabilità cross-prompt |
| `max_affinity` | 0-1 | Specializzazione semantica |
| `conditional_consistency` | 0-1 | Consistency quando attiva |
| `logit_influence` | 0-∞ | Impatto causale sull'output |

### Typology Classification

- **Generalist**: Alta consistency + Alta affinity + Bassa influence (es. "of", "the")
- **Specialist**: Bassa consistency + Alta affinity + Alta influence (es. "Capital", "Texas")
- **Computational**: Alta consistency + Bassa affinity (es. position markers)
- **Hybrid**: Combinazioni miste

### Dual View (Influence-First)

1. **Situational Core** (`logit_influence >= τ_inf`)
   - Feature causalmente determinanti per questo prompt specifico
   - Priorità massima per interpretabilità

2. **Generalizable Scaffold** (`max_affinity >= τ_aff OR mean_consistency >= τ_cons`)
   - Feature stabili e riutilizzabili cross-prompt
   - Supporto strutturale del comportamento

---

## 🎯 Risultati

### Coverage Metriche

| Metrica | Target | Attuale | Status |
|---------|--------|---------|--------|
| Logit Influence Coverage | ≥50% | 52.3% | ✅ |
| BOS Leakage | <30% | 2.4% | ✅ |
| Feature Coperte | ≥400 | 483 | ✅ |
| Supernodi | 15-30 | 23 | ✅ |

### Breakdown Supernodi

- **Semantic**: 15 supernodi (cluster narrativi coerenti)
- **Computational**: 8 supernodi (residui quality con logit influence)

---

## 🔧 Troubleshooting

### File mancanti

**Errore:** `FileNotFoundError: output/acts_compared.csv`

**Soluzione:** Scarica i file da Colab. Vedi sezione "Setup".

### Coverage bassa

**Se coverage < 40%:**

1. Analizza feature escluse:
   ```bash
   python scripts/analysis/analyze_remaining_excluded.py
   ```

2. Rilassa thresholds in `compute_thresholds.py`:
   ```python
   tau_aff = 0.50  # invece di 0.60
   ```

3. Riesegui pipeline da step 2

### UnicodeEncodeError (Windows)

```powershell
$env:PYTHONIOENCODING='utf-8'
python script.py
```

---

## 📚 Riferimenti

### Papers

- **Circuit Tracing** (Anthropic, 2025): [Attribution Graphs](https://transformer-circuits.pub/2025/attribution-graphs/)
- **Scaling Monosemanticity** (Anthropic, 2024): [Cross-Layer SAEs](https://transformer-circuits.pub/2024/scaling-monosemanticity/)

### Codice

- **Circuit Tracer Library**: https://github.com/safety-research/circuit-tracer
- **Neuronpedia**: https://www.neuronpedia.org

### Documentazione Interna

- `circuit_analysis_pipeline.ipynb`: Notebook unificato con tutti gli step
- `docs/NEURONPEDIA_EXPORT_GUIDE.md`: Guida export Neuronpedia
- `docs/influence_first_summary.md`: Metodologia influence-first
- `QUICK_REFERENCE.md`: Cheat sheet comandi

---

## 🤝 Contributi

Questo progetto è parte di una research application per MATS (AI Safety).

Per domande o contributi:
- Consulta la documentazione in `docs/`
- Apri un issue su GitHub

---

**Version**: 2.0 (Influence-First)  
**Model**: Gemma-2-2B  
**Last Updated**: 2025-10-09  
**License**: MIT
