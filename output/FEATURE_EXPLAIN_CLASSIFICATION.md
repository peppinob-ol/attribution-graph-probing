# Feature: Spiega Classificazione

**Data**: 2025-10-25  
**Status**: ✅ Implementato

---

## Descrizione

Nuova funzionalità nella pagina Streamlit **Node Grouping** (Step 2) che permette di cercare una `feature_key` specifica e ottenere una spiegazione dettagliata del perché è stata classificata in una determinata classe.

---

## Posizione

**Pagina**: `eda/pages/02_Node_Grouping.py`  
**Sezione**: Step 2 - Dopo la tabella dei risultati  
**Linee**: 391-595

---

## Interfaccia Utente

### Input
```python
feature_to_explain = st.text_input(
    "Cerca feature_key",
    placeholder="es. 22_11998",
    help="Inserisci il feature_key per vedere la spiegazione della classificazione"
)
```

### Output (quando feature trovata)

#### 1. Info Box
```
Feature: 22_11998
Classificazione: Semantic
Subtype: Concept
Confidence: 0.95
Review: ✅ No
```

#### 2. Metriche Aggregate (8 colonne)
- **Layer**: Layer della feature
- **Peak Consistency**: Quanto consistentemente un token è peak
- **N Distinct Peaks**: Numero di token distinti come peak
- **Func vs Sem %**: Differenza % activation functional vs semantic
- **Conf F**: Confidence functional (frazione peak su functional)
- **Conf S**: Confidence semantic (frazione peak su semantic)
- **Sparsity**: Mediana sparsity (quanto è concentrata l'attivazione)
- **K Semantic**: Numero di token semantici distinti

#### 3. Spiegazione Classificazione
Testo generato dinamicamente basato sulla classe e sulle metriche, che spiega:
- Quale regola dell'albero decisionale è stata applicata
- Quali soglie sono state superate (con ✅)
- Interpretazione delle metriche chiave
- Motivazione della classificazione

#### 4. Albero Decisionale Completo (Expander)
Mostra l'ordine di valutazione di tutte le regole con:
- Soglie per ogni regola
- Risultato (✅ MATCH o ❌ No match) per la feature specifica
- Classificazione finale

---

## Esempi di Spiegazione

### Esempio 1: Semantic (Dictionary)

**Input**: `22_11998`

**Output**:
```
La feature 22_11998 è stata classificata come Semantic (Dictionary) perché:

1. Peak Consistency = 0.95 (≥ 0.80 ✅)
   - Il token principale è peak in 95% dei casi in cui appare nel prompt
   - Indica una feature molto selettiva su un token specifico

2. N Distinct Peaks = 1 (≤ 1 ✅)
   - La feature si attiva sempre sullo stesso token
   - Comportamento tipico di feature "dizionario" (es. sempre su "Texas")

Regola applicata: Dictionary Semantic (priorità massima)
```

### Esempio 2: Say "X"

**Input**: `22_45678`

**Output**:
```
La feature 22_45678 è stata classificata come Say "X" perché:

1. Func vs Sem % = 85.3% (≥ 50.0% ✅)
   - La max activation su token funzionali è 85.3% maggiore che su semantici
   - Indica forte preferenza per token funzionali (es. "is", ",")

2. Confidence F = 0.92 (≥ 0.90 ✅)
   - Frazione di peak su token funzionali: 92%
   - Quasi tutti i peak sono su token funzionali

3. Layer = 22 (≥ 7 ✅)
   - Layer alto tipico di feature predittive
   - Say X features sono tipicamente nei layer finali

Regola applicata: Say "X" (predice prossimo token)
```

### Esempio 3: Relationship

**Input**: `1_12345`

**Output**:
```
La feature 1_12345 è stata classificata come Relationship perché:

1. Sparsity = 0.35 (< 0.45 ✅)
   - Sparsity bassa indica attivazione diffusa nel prompt
   - La feature si attiva su multipli token, non concentrata su uno solo

2. K Semantic = 5
   - Numero di token semantici distinti su cui si attiva
   - Indica collegamento tra concetti multipli

3. Layer = 1
   - Layer medio-basso tipico di feature relazionali

Regola applicata: Relationship (collega concetti multipli)
```

### Esempio 4: Semantic (Concept)

**Input**: `7_3144`

**Output**:
```
La feature 7_3144 è stata classificata come Semantic (Concept) perché:

1. Func vs Sem % = 35.2% (< 50.0% ✅)
   - La differenza tra max activation su functional vs semantic è piccola
   - Indica che la feature si attiva principalmente su token semantici

2. Confidence S = 0.78
   - Frazione di peak su token semantici: 78%

3. Layer = 7
   - Layer medio, tipico di feature concettuali

Regola applicata: Semantic Concept
```

---

## Logica di Generazione Spiegazione

### Per Semantic
```python
if peak_cons >= threshold AND n_peaks <= 1:
    → "Dictionary Semantic (priorità massima)"
elif layer <= 3:
    → "Dictionary fallback (layer basso)"
elif func_vs_sem < 50%:
    → "Semantic Concept (preferenza semantici)"
else:
    → "Semantic Concept (confidence S alta)"
```

### Per Say "X"
```python
if func_vs_sem >= 50% AND conf_F >= 0.90 AND layer >= 7:
    → "Say X (predice prossimo token)"
```

### Per Relationship
```python
if sparsity < 0.45:
    → "Relationship (collega concetti multipli)"
```

### Per Review
```python
else:
    → "Richiede review manuale"
    + Mostra motivo (why_review)
```

---

## Albero Decisionale Visualizzato

```
Ordine di valutazione:

1. ✅ Dictionary Semantic: peak_consistency ≥ 0.80 AND n_distinct_peaks ≤ 1
   - Risultato: ✅ MATCH / ❌ No match

2. ✅ Say "X": func_vs_sem ≥ 50.0% AND conf_F ≥ 0.90 AND layer ≥ 7
   - Risultato: ✅ MATCH / ❌ No match

3. ✅ Relationship: sparsity < 0.45
   - Risultato: ✅ MATCH / ❌ No match

4. ✅ Semantic (Concept): layer ≤ 3 OR conf_S ≥ 0.50 OR func_vs_sem < 50.0%
   - Risultato: ✅ MATCH / ❌ No match

5. ⚠️ Review: Casi ambigui

Classificazione finale: [pred_label]
```

---

## Gestione Errori

### Feature non trovata
```python
if len(feature_data) == 0:
    st.warning(f"⚠️ Feature '{feature_to_explain}' non trovata nel dataset")
```

### Impossibile calcolare metriche
```python
if len(feature_metrics_df) == 0:
    st.error("❌ Impossibile calcolare metriche aggregate per questa feature")
```

---

## Dipendenze

### Import
```python
from scripts import node_grouping
```

### Funzioni utilizzate
- `node_grouping.aggregate_feature_metrics(df)`: Ricalcola metriche aggregate per la feature
- `pd.notna()`: Verifica se subtype è presente
- `st.info()`, `st.metric()`, `st.markdown()`, `st.expander()`: UI components

### Variabili di sessione
- `st.session_state['df_classified']`: DataFrame con classificazioni
- `custom_thresholds`: Soglie configurate dall'utente nella sidebar

---

## Workflow Utente

1. **Esegui Step 2** per ottenere classificazioni
2. **Scorri tabella** per identificare feature interessanti
3. **Copia feature_key** dalla tabella (es. `22_11998`)
4. **Incolla** nel campo "Cerca feature_key"
5. **Leggi spiegazione** con metriche e motivazione
6. **(Opzionale) Espandi** "Albero Decisionale Completo" per vedere tutte le regole

---

## Vantaggi

### 1. Trasparenza
- Spiega esattamente perché una feature è stata classificata
- Mostra quali soglie sono state superate
- Rende l'albero decisionale interpretabile

### 2. Debug
- Identifica rapidamente feature classificate in modo inaspettato
- Permette di verificare se le soglie sono appropriate
- Facilita il tuning dei parametri

### 3. Apprendimento
- Aiuta l'utente a capire come funziona l'albero decisionale
- Mostra l'interpretazione delle metriche
- Collega metriche numeriche a significato semantico

### 4. Validazione
- Permette di verificare caso per caso la correttezza
- Confronta con intuizione umana
- Identifica casi limite o ambigui

---

## Estensioni Future

### 1. Confronto con Ground Truth
Se disponibile `supernode_class` nel CSV:
```python
if 'supernode_class' in feature_data.columns:
    ground_truth = feature_data.iloc[0]['supernode_class']
    if ground_truth != pred_label:
        st.warning(f"⚠️ Ground truth: {ground_truth} (diverso da predizione)")
```

### 2. Visualizzazione Metriche
Grafici radar o bar chart per confrontare metriche della feature con medie di classe:
```python
import plotly.graph_objects as go

fig = go.Figure(data=go.Scatterpolar(
    r=[peak_cons, conf_F, conf_S, sparsity],
    theta=['Peak Cons', 'Conf F', 'Conf S', 'Sparsity'],
    fill='toself'
))
st.plotly_chart(fig)
```

### 3. Feature Simili
Trova altre feature con metriche simili:
```python
similar_features = find_similar_features(metrics, df_classified, top_k=5)
st.write("Feature simili:", similar_features)
```

### 4. Suggerimenti Tuning
Se la confidence è bassa, suggerisci modifiche alle soglie:
```python
if record['confidence'] < 0.7:
    st.info("💡 Suggerimento: Considera di abbassare la soglia X per migliorare la confidence")
```

---

## Test

### Test Manuale
1. ✅ Feature esistente → Mostra spiegazione corretta
2. ✅ Feature inesistente → Warning appropriato
3. ✅ Ogni classe (Semantic, Say X, Relationship) → Spiegazione specifica
4. ✅ Feature in review → Mostra motivo review
5. ✅ Albero decisionale → Match corretto evidenziato
6. ✅ Soglie personalizzate → Riflesse nella spiegazione

### Test Automatico (Futuro)
```python
def test_explain_classification():
    # Mock data
    df = pd.DataFrame({...})
    feature_key = "22_11998"
    
    # Generate explanation
    explanation = generate_explanation(feature_key, df, thresholds)
    
    # Assertions
    assert "22_11998" in explanation
    assert "Semantic" in explanation
    assert "✅" in explanation  # Check for passed thresholds
```

---

## Riferimenti

- **Albero Decisionale**: `output/STEP2_FINAL_WITH_PEAK_CONSISTENCY.md`
- **Metriche**: `scripts/02_node_grouping.py` → `aggregate_feature_metrics()`
- **Classificazione**: `scripts/02_node_grouping.py` → `classify_node()`
- **Documentazione Soglie**: `output/STEP2_REVIEW_GATE_B_FINAL.md`

---

## Conclusione

La funzionalità **Spiega Classificazione** rende la pipeline di Node Grouping completamente trasparente e interpretabile, permettendo agli utenti di:
- ✅ Comprendere ogni decisione di classificazione
- ✅ Validare la correttezza delle classificazioni
- ✅ Ottimizzare le soglie basandosi su casi specifici
- ✅ Apprendere il funzionamento dell'albero decisionale

**Pronto per l'uso!** 🚀

