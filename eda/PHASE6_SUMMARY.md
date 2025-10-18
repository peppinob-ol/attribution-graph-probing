# Phase 6: Causal Validation - Implementation Summary

## 🎯 Obiettivo

Validare se **l'attivazione cross-prompt** delle feature su `acts_compared.csv` può predire la loro **importanza causale** nel pathway che porta all'output "Austin".

## ❓ Domanda di Ricerca

**"Le feature causalmente importanti per l'output 'Austin' si attivano distintamente su prompt semanticamente correlati?"**

Se SÌ → attivazione cross-prompt è un buon proxy per importanza causale  
Se NO → serve approccio diverso o prompt diversi

---

## 📊 Implementazione

### File Creati

1. **`eda/pages/06_Causal_Validation.py`** (500+ righe)
   - Pagina Streamlit completa con 5 tabs
   - Analisi statistica (Mann-Whitney, Chi-Square)
   - ROC/Precision-Recall curves
   - Visualizzazioni interattive

2. **`eda/CAUSAL_VALIDATION_GUIDE.md`** (400+ righe)
   - Guida completa all'uso della pagina
   - Interpretazione risultati
   - Troubleshooting
   - Scenari di validazione

3. **`eda/PHASE6_SUMMARY.md`** (questo file)
   - Riepilogo implementazione

### Modifiche ai File Esistenti

- **`eda/app.py`**: Aggiunto link a pagina 06
- **`eda/README.md`**: Documentata nuova pagina

---

## 🔬 Funzionalità Implementate

### 1. **Configurazione Analisi** (Sidebar)

#### Definizione Importanza Causale
- **Metrica primaria**:
  - `node_influence` (backward propagation)
  - `output_impact` (direct logit influence)
  - `combined` (weighted combination, configurabile)
- **Percentile**: Top N% features considerate "importanti" (default 90th)

#### Metriche di Attivazione
- Selezione da `acts_compared.csv`:
  - `nuova_max_label_span` (default)
  - `normalized_sum_label`
  - `nuova_somma_label_span`
  - `twera_total_in`
  - `cosine_similarity`
- **Threshold**: Soglia per considerare feature "attiva"

#### Filtro Prompt
- Selezione multipla prompt da analizzare
- Default: primi 3 prompt

---

### 2. **Calcolo Importanza Causale**

**Output**:
- Total features, important features (sopra percentile)
- Threshold importanza
- % features importanti
- Distribuzione histogram con linea percentile

**Logica**:
```python
if metric == 'combined':
    importance = weight × node_influence + (1-weight) × output_impact
else:
    importance = selected_metric

is_important = importance >= percentile_threshold
```

---

### 3. **Analisi Cross-Prompt**

**Merge dati**:
- `acts_compared.csv` + `feature_personalities_corrected.json`
- Filtra per prompt selezionati
- Aggrega per feature_key

**Statistiche**:
- Mean/Median activation per gruppo (important vs unimportant)
- Count features attive (sopra threshold)
- **Mann-Whitney U Test**:
  - H1: Important features have higher activation
  - p < 0.05 = significant

---

### 4. **Tab 1: Main Chart** 📊

**Stacked Bar Chart**:
- X: Features ordinate per importanza (DESC)
- Y (left): Activation metric
- Y (right): Importance score (linea rossa)
- Bars: Stacked per prompt (colori diversi)

**Slider**: Top N features da mostrare (10-100)

**Interpretazione**:
- Left (important) → tall colored bars ✅
- Right (unimportant) → short gray bars ✅
- Linea rossa decrescente (importance)

**Export**: CSV con dati chart

---

### 5. **Tab 2: ROC Analysis** 📈

**ROC Curve**:
- True Positive Rate vs False Positive Rate
- AUC (Area Under Curve):
  - 1.0 = perfect
  - 0.9-1.0 = excellent
  - 0.8-0.9 = good
  - 0.7-0.8 = fair
  - 0.5-0.7 = poor
  - 0.5 = random

**Precision-Recall Curve**:
- Trade-off precision/recall
- Baseline = % important features (random)

**Optimal Threshold**:
- Threshold che massimizza F1 score
- Precision, Recall, F1 a threshold ottimale

**Metriche**:
- AUC con interpretazione
- Features analyzed

---

### 6. **Tab 3: Feature Ranking** 🏆

**Due Tabelle Side-by-Side**:

1. **Top 20 by Causal Importance**:
   - Features con highest importance_score
   - Include max_activation cross-prompt

2. **Top 20 by Activation**:
   - Features con highest activation
   - Include importance_score

**Overlap Analysis**:
- **Both**: In entrambe top 20 ✅
- **Only important**: Alta importanza, bassa attivazione ⚠️
- **Only activated**: Alta attivazione, bassa importanza ⚠️

**Venn Diagram** (bar chart):
- Visualizza overlap

**Interpretazione**:
- Overlap > 50% = good alignment
- Overlap < 30% = poor alignment

---

### 7. **Tab 4: Prompt Comparison** 🔄

**Heatmap**: Feature × Prompt
- Rows: Top N features (per importanza)
- Cols: Prompts selezionati
- Color: Activation intensity

**Slider**: N features da mostrare (10-50)

**Violin Plots**:
- Distribuzione activation per prompt
- Separato per important vs unimportant
- Fino a 5 prompt (per leggibilità)

**Pattern da cercare**:
- Horizontal bands: feature generalista (attiva su molti prompt)
- Vertical bands: prompt discriminativo (attiva molte feature importanti)
- Clusters: co-attivazione gruppi feature

---

### 8. **Tab 5: Token Analysis** 🔤

**Peak on Label Analysis**:
- Contingency table: `is_important` × `picco_su_label`
- Normalizzato per row (% within group)
- **Chi-Square Test**: associazione significativa?

**Interpretation**:
- Important features dovrebbero avere % più alta di peak on label
- p < 0.05 = significant association

**Peak Token Distribution**:
- Top 15 token per gruppo (important vs unimportant)
- Bar charts side-by-side

**Expected**:
- Important: "Austin", "Texas", "capital", "city"
- Unimportant: `<BOS>`, punteggiatura, stopwords

---

### 9. **Summary & Conclusions** 📋

**Key Findings** (auto-generated):
- AUC value + interpretation
- Mean activation difference
- Statistical significance (Mann-Whitney)
- Top 20 overlap %

**Recommendations** (conditional):
- Se AUC > 0.8: ✅ "Good predictor, use for feature selection"
- Se AUC 0.6-0.8: ⚠️ "Moderate, combine with other metrics"
- Se AUC < 0.6: ❌ "Poor predictor, consider alternatives"

---

### 10. **Export** 📥

**1. Analysis Summary JSON**:
```json
{
  "configuration": {
    "importance_metric": "node_influence",
    "importance_percentile": 90,
    "activation_metric": "nuova_max_label_span",
    "activation_threshold": 0.5,
    "selected_prompts": [...]
  },
  "results": {
    "n_important": 50,
    "n_total": 500,
    "importance_threshold": 0.0234,
    "auc": 0.87,
    "mann_whitney_pvalue": 0.0001,
    "top20_overlap": 14
  }
}
```

**2. Feature Importance + Activation CSV**:
- Tutte le feature con importance_score e max_activation
- Per ulteriori analisi in notebook

---

## 🎓 Scenari di Validazione

### Scenario 1: **Strong Validation** ✅

**Condizioni**:
- AUC > 0.85
- Mann-Whitney p < 0.001
- Top 20 overlap > 60%
- Peak on label % significativamente più alta per important

**Conclusione**: Attivazione cross-prompt è **reliable proxy** per importanza causale

**Azione**: Usare activation filtering per feature selection

---

### Scenario 2: **Moderate Validation** ⚠️

**Condizioni**:
- AUC 0.65-0.85
- Mann-Whitney p < 0.05
- Top 20 overlap 30-60%

**Conclusione**: Attivazione ha **some predictive power** ma non sufficiente da sola

**Azione**: Combinare con altre metriche (node_influence, output_impact)

---

### Scenario 3: **Weak/No Validation** ❌

**Condizioni**:
- AUC < 0.65
- Mann-Whitney p > 0.05
- Top 20 overlap < 30%

**Conclusione**: Attivazione **non predice** importanza causale

**Possibili Cause**:
1. Prompt non rilevanti
2. Feature importanti sono computational (bassa attivazione semantica)
3. Noise in `acts_compared.csv`
4. Wrong activation metric

**Azione**:
- Provare prompt diversi
- Filtrare per archetipi (solo Semantic Anchors)
- Verificare qualità dati
- Testare altre metriche

---

## 📚 Documentazione

### Guide Create

1. **`CAUSAL_VALIDATION_GUIDE.md`**:
   - Uso completo della pagina
   - Interpretazione tab per tab
   - Scenari di validazione
   - Troubleshooting
   - Advanced analysis (archetype-specific, layer-wise, prompt engineering)

2. **Aggiornamenti README**:
   - Sezione pagina 06
   - Link a guida validazione

---

## 🔧 Dipendenze

**Nuove** (già in requirements.txt):
- `scipy`: per test statistici (Mann-Whitney, Chi-Square)
- `sklearn`: per ROC/Precision-Recall curves

**Esistenti**:
- `streamlit`, `pandas`, `numpy`, `plotly`

---

## ✅ Testing Checklist

- [x] Pagina si carica senza errori
- [x] Configurazione sidebar funziona
- [x] Calcolo importanza causale corretto
- [x] Merge acts_compared + personalities OK
- [x] Mann-Whitney test eseguito
- [x] ROC curve renderizza
- [x] Precision-Recall curve renderizza
- [x] Main chart (stacked bar) funziona
- [x] Heatmap feature×prompt renderizza
- [x] Token analysis (contingency + chi-square) OK
- [x] Export JSON e CSV funzionanti
- [x] Tooltip e help text presenti
- [x] Nessun linter error

---

## 🚀 Utilizzo

### Quick Start

1. **Avvia app**: `streamlit run eda/app.py`
2. **Naviga a**: 🔬 Causal Validation (pagina 06)
3. **Configura**:
   - Importance metric: `node_influence` (default)
   - Activation metric: `nuova_max_label_span` (default)
   - Percentile: 90 (default)
4. **Analizza tabs**:
   - Main Chart: overview visuale
   - ROC Analysis: AUC e optimal threshold
   - Feature Ranking: overlap analysis
   - Prompt Comparison: heatmap e violin
   - Token Analysis: peak on label
5. **Conclusioni**: Summary section
6. **Export**: Download JSON e CSV

---

## 💡 Pro Tips

1. **Start with defaults**: Esegui prima con parametri default
2. **Compare metrics**: Prova tutte le activation metrics per trovare best predictor
3. **Iterate**: Se AUC basso, cambia prompt o metric
4. **Cross-validate**: Se AUC alto, valida su prompt held-out
5. **Document**: Export summary JSON per reproducibilità

---

## 🔮 Future Enhancements

Possibili estensioni:

1. **Archetype-specific analysis**: ROC separato per archetipo
2. **Layer-wise analysis**: AUC per layer group
3. **Prompt engineering**: Ranking prompt per discriminative power
4. **Interactive threshold**: Slider per vedere precision/recall in real-time
5. **Subgraph integration**: Overlay con pruned subgraph membership
6. **Causal path visualization**: Sankey diagram con activation overlay

---

## 📊 Metriche Chiave

### Input
- `acts_compared.csv`: 19,462 righe (esempio)
- `feature_personalities_corrected.json`: ~500 features
- Prompts: variabile (tipicamente 3-10)

### Output
- AUC: 0.0-1.0 (target > 0.8)
- Mann-Whitney p-value: target < 0.05
- Top 20 overlap: target > 50%
- Optimal F1 threshold: per feature selection

---

## 🎯 Acceptance Criteria

✅ **Pagina funzionante se**:
1. Tutti i tab renderizzano senza errori
2. ROC curve mostra AUC corretto
3. Main chart ordina feature per importanza
4. Statistical tests eseguiti correttamente
5. Export producono file validi
6. Tooltip e help text completi
7. Documentazione chiara e completa

---

**Implementato**: 2025-10-18  
**Versione**: 1.0.0  
**Status**: ✅ Complete & Tested


