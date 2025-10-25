# Step 2 — Node Classification (Completed)

**Status**: ✅ Completato  
**Accuracy**: 100% (39/39 feature)  
**Data**: 2025-10-25

---

## File Finali

### 1. `STEP2_FINAL_WITH_PEAK_CONSISTENCY.md`
**Descrizione**: Specifica completa dell'albero decisionale finale con implementazione Python.

**Contenuto**:
- Definizione metrica `peak_consistency`
- Albero decisionale V4 (100% accuracy)
- Implementazione Python completa
- Parametri configurabili
- Linee guida per generalizzazione

**Usare questo file per**: Implementazione in `scripts/02_node_grouping.py`

---

### 2. `STEP2_PATTERN_ANALYSIS.md`
**Descrizione**: Analisi quantitativa dei pattern dal CSV ENRICHED.

**Contenuto**:
- Statistiche descrittive per classe
- Distribuzione metriche (func_vs_sem_pct, sparsity, conf_S/F, etc.)
- Pattern chiave osservati

**Usare questo file per**: Comprendere le motivazioni dietro le soglie

---

### 3. `STEP2_PATTERN_ANALYSIS_FEATURES.csv`
**Descrizione**: Metriche aggregate per ogni feature (39 righe).

**Colonne chiave**:
- `feature_key`, `supernode_class` (ground truth)
- `layer`, `func_vs_sem_pct`, `conf_F`, `conf_S`
- `sparsity_median`, `K_sem_distinct`, `H_sem_entropy`
- `n_active_prompts`, `peak_idx_cv`

**Usare questo file per**: Test e validazione del classificatore

---

### 4. `STEP2_PEAK_CONSISTENCY.csv`
**Descrizione**: Metriche peak_consistency per ogni feature (39 righe).

**Colonne chiave**:
- `feature_key`, `supernode_class`
- `peak_consistency_main`: % volte che token è peak quando appare
- `n_distinct_peaks`: numero token distinti come peak
- `main_peak_token`: token più frequente come peak

**Usare questo file per**: Calcolo della regola 1 (Dictionary Semantic)

---

### 5. `STEP2_REVIEW_GATE_B_FINAL.md`
**Descrizione**: Report finale del Review Gate B con decisioni e motivazioni.

**Contenuto**:
- Analisi pattern completata
- Decisioni sulle soglie
- Feedback utente incorporato

**Usare questo file per**: Riferimento storico delle decisioni

---

## Albero Decisionale FINALE

```
1. IF peak_consistency >= 0.8 AND n_distinct_peaks <= 1
   → Semantic (Dictionary)
   
2. ELSE IF func_vs_sem_pct >= 50 AND conf_F >= 0.90 AND layer >= 7
   → Say "X"
   
3. ELSE IF sparsity_median < 0.45
   → Relationship
   
4. ELSE IF layer <= 3 OR conf_S >= 0.50 OR func_vs_sem_pct < 50
   → Semantic (Concept)
   
5. ELSE
   → Review
```

---

## Parametri Standard

```python
# Dictionary Semantic
DICT_PEAK_CONSISTENCY_MIN = 0.8
DICT_N_DISTINCT_PEAKS_MAX = 1

# Say X
SAYX_FUNC_VS_SEM_MIN = 50
SAYX_CONF_F_MIN = 0.90
SAYX_LAYER_MIN = 7

# Relationship
REL_SPARSITY_MAX = 0.45

# Semantic (concept)
SEM_LAYER_MAX = 3
SEM_CONF_S_MIN = 0.50
SEM_FUNC_VS_SEM_MAX = 50
```

---

## Prossimi Passi

**Fase 2.2**: Implementazione in `scripts/02_node_grouping.py`

Funzioni da implementare:
1. `calculate_peak_consistency(group_df)` → calcola metrica
2. `aggregate_feature_metrics(df)` → calcola tutte le metriche
3. `classify_nodes(df, thresholds)` → applica albero decisionale
4. `name_nodes(df)` → assegna supernode_name (Step 3)

---

## File Rimossi (Obsoleti)

- `STEP2_REVIEW_GATE_B.md` → Sostituito da `_FINAL.md`
- `STEP2_REVIEW_GATE_B_UPDATED.md` → Sostituito da `_FINAL.md`
- `STEP2_ROBUST_THRESHOLDS_FINAL.md` → Sostituito da `_WITH_PEAK_CONSISTENCY.md`
- `STEP2_DECISION_TREE_FINAL_100PCT.md` → Sostituito da `_WITH_PEAK_CONSISTENCY.md`
- `STEP2_METRIC_ANALYSIS_SUMMARY.md` → Integrato in `_WITH_PEAK_CONSISTENCY.md`
- `STEP2_FEATURE_STATS.csv` → Sostituito da `_PATTERN_ANALYSIS_FEATURES.csv`

