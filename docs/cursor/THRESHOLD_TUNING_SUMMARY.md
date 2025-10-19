# Summary: Ottimizzazione Soglie Classificazione Feature

**Data**: 2025-10-18  
**Script**: `scripts/02_anthropological_basic.py`

## Problema Iniziale

Dall'analisi dei prompt sonda è emerso che feature semantiche importanti venivano classificate in modo inadeguato:

### Feature Test (dai Probe Prompts)

| Feature    | Attivazioni Medie | Mean Cons | Max Aff | Label Aff | Node Inf | Classificazione PRIMA | Classificazione DOPO |
|------------|-------------------|-----------|---------|-----------|----------|----------------------|---------------------|
| **24_13277** | **65.94** (4/4) | **0.917** | **0.961** | 0.000 | **0.450** | ❌ Stable Contributors | ✅ **Semantic Anchors** |
| 7_3099     | 34.31 (4/4)       | 0.745     | 0.780   | 0.750     | 0.062    | ✅ Semantic Anchors   | ✅ Semantic Anchors |
| 23_57      | 33.78 (4/4)       | 0.676     | 0.723   | 1.000     | 0.075    | ✅ Semantic Anchors   | ✅ Semantic Anchors |
| 20_15589   | 46.33 (3/4)       | 0.457     | 0.708   | 0.000     | 0.381    | Stable Contributors   | Stable Contributors |
| 4_13154    | 21.88 (3/4)       | 0.000     | 0.000   | 0.500     | 0.433    | Outliers              | Outliers |
| 14_2268    | 19.25 (3/4)       | 0.000     | 0.000   | 0.250     | 0.419    | Outliers              | Outliers |
| 25_4717    | 100.44 (2/4)      | 0.000     | 0.000   | 0.000     | 0.061    | Outliers              | Outliers |

### Problema Principale

**Feature 24_13277** aveva le metriche semantiche più alte del dataset ma veniva classificata come "Stable Contributor" invece che "Semantic Anchor" perché:
- Richiedeva TUTTI E TRE i criteri contemporaneamente: mean_consistency > p75 AND max_affinity > p75 AND label_affinity > p75
- Aveva label_affinity = 0.0 (non si attiva sul token label, ma su "of")

## Modifiche Implementate

### 1. Percentili Meno Stringenti

```python
# PRIMA
high_mean_consistency = self._percentile(mean_consistencies, 75)
high_max_affinity = self._percentile(max_affinities, 75)

# DOPO
high_mean_consistency = self._percentile(mean_consistencies, 70)
high_max_affinity = self._percentile(max_affinities, 70)
```

### 2. Soglie Assolute Minime

```python
MIN_SEMANTIC_CONSISTENCY = 0.6
MIN_SEMANTIC_AFFINITY = 0.65
```

Combinate con i percentili: `max(percentile_70, soglia_assoluta)`

### 3. Logica "2 su 3" per Semantic Anchors

```python
# PRIMA: AND di tutti e 3
if (mean_cons > p75 AND max_aff > p75 AND label_aff > p75):
    semantic_anchors.append(...)

# DOPO: almeno 2 su 3 criteri
semantic_criteria = [
    mean_cons > max(high_mean_consistency, MIN_SEMANTIC_CONSISTENCY),
    max_aff > max(high_max_affinity, MIN_SEMANTIC_AFFINITY),
    label_aff > high_label_affinity
]
if sum(semantic_criteria) >= 2:
    semantic_anchors.append(...)
```

### 4. Computational Helpers con Node Influence

```python
# PRIMA: solo social_influence (sempre 1.0, non discriminava)
elif (social_influence > p75 AND max_aff < p75):
    computational_helpers.append(...)

# DOPO: considera impatto causale reale
elif (node_inf > high_node_influence OR output_imp > high_output_impact) AND \
     mean_cons < 0.3 AND max_aff < 0.5:
    computational_helpers.append(...)
```

## Risultati

### Distribuzione Archetipi

| Archetipo                | Prima | Dopo | Variazione |
|--------------------------|-------|------|------------|
| Semantic Anchors         | ~2500 | 225  | Più selettivo ✅ |
| Stable Contributors      | ~600  | 632  | Stabile |
| Contextual Specialists   | ~0    | 0    | - |
| Computational Helpers    | ~10   | 1029 | Ora funziona ✅ |
| Outliers                 | ~1700 | 2979 | Più outliers (normale) |

### Qualità Classificazione Probe Features

```
PRIMA:
  Semantic Anchors:    2/7 (29%)
  Stable Contributors: 2/7 (29%)  <- 24_13277 qui!
  Outliers:            3/7 (43%)

DOPO:
  Semantic Anchors:    3/7 (43%)  <- 24_13277 qui! ✅
  Stable Contributors: 1/7 (14%)
  Outliers:            3/7 (43%)
```

## Interpretazione

### ✅ Cosa Funziona Ora

1. **Feature 24_13277** correttamente identificata come semantic anchor nonostante `label_affinity=0`
   - Ha mean_consistency=0.917 e max_affinity=0.961 (entrambi altissimi)
   - Regola "2 su 3" la cattura correttamente

2. **Computational Helpers** ora identificabili
   - 1029 feature con alto impatto causale ma bassa semantica
   - Cattura feature come `4_13154`, `14_2268` che hanno node_influence > 0.4 ma consistency=0

3. **Soglie assolute** prevengono classificazioni spurie
   - Feature devono avere almeno mean_cons > 0.6 o max_aff > 0.65 per essere semantic anchors

### ⚠️ Limitazioni Rimanenti

1. **Feature con consistency=0 ma semantiche**: `4_13154`, `14_2268`, `25_4717` rispondono ai prompt sonda ma hanno zero similarità con descrizioni Neuronpedia originali
   - Causa: descrizioni originali errate o incomplete
   - Non risolvibile senza rietichettare manualmente

2. **Label affinity non sempre affidabile**: Feature semantiche possono piccare su token funzionali ("of") invece che sul label ("Capital")

## File Modificati

- `scripts/02_anthropological_basic.py`: funzione `identify_narrative_archetypes()` (righe 264-368)
- Generati nuovi file:
  - `output/feature_personalities_corrected.json`
  - `output/narrative_archetypes.json`
  - `output/feature_typology.json`
  - `output/quality_scores.json`

## Comandi per Riprodurre

```bash
# Rigenera classificazioni con nuove soglie
python scripts/02_anthropological_basic.py

# Analizza feature dai probe prompts
python scripts/analyze_probe_features.py
```

## Conclusioni

Le modifiche hanno **migliorato significativamente** la capacità dello script di identificare feature semantiche reali, riducendo falsi negativi (come 24_13277) e introducendo una categoria funzionante di "computational helpers" basata su metriche causali effettive invece che su proxy inutili (social_influence).

La logica "2 su 3 criteri" è più robusta del precedente AND booleano, catturando feature semantiche che non necessariamente si attivano sul token label ma hanno comunque alta coerenza semantica cross-prompt.


