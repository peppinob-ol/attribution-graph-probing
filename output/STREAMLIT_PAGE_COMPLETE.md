# Pagina Streamlit Node Grouping - Completata

**Data**: 2025-10-25  
**Status**: ✅ Completato

---

## Riepilogo Modifiche

### File Creati

1. **`eda/pages/02_Node_Grouping.py`** (580 righe)
   - Interfaccia Streamlit completa per Node Grouping
   - 3 step interattivi con visualizzazioni complete
   - Configurazione parametri e soglie in tempo reale
   - Download risultati CSV e JSON

2. **`eda/pages/README_NODE_GROUPING.md`**
   - Guida utente completa
   - Istruzioni passo-passo
   - Interpretazione risultati
   - Troubleshooting e best practices

---

## Caratteristiche Implementate

### Upload Files
- ✅ CSV Export (richiesto): `2025-10-21T07-40_export_ENRICHED.csv`
- ✅ JSON Attivazioni (opzionale): `activations_dump (2).json`

### Configurazione Parametri
- ✅ Finestra ricerca target (slider 3-15, default 7)
- ✅ Soglie Dictionary Semantic (consistency, n_peaks)
- ✅ Soglie Say X (func_vs_sem, conf_F, layer)
- ✅ Soglie Relationship (sparsity)
- ✅ Soglie Semantic Concept (layer, conf_S, func_vs_sem)

### Step 1: Preparazione Dataset
- ✅ Classificazione token (functional vs semantic)
- ✅ Calcolo target_tokens
- ✅ Statistiche aggregate
- ✅ **Tabella completa** (tutte le righe, height=400px)
- ✅ Download CSV Step 1

### Step 2: Classificazione Nodi
- ✅ Aggregazione metriche per feature
- ✅ Applicazione albero decisionale
- ✅ Visualizzazione distribuzione classi
- ✅ Warning per feature in review
- ✅ Filtro multiselect per classe
- ✅ **Tabella completa filtrata** (height=400px)
- ✅ Download CSV Step 2
- ✅ Iterazione: modifica soglie e riesegui

### Step 3: Naming Supernodi
- ✅ Naming Relationship: `"(X) related"`
- ✅ Naming Semantic: token con max activation
- ✅ Naming Say X: `"Say (X)"`
- ✅ Statistiche (feature totali, nomi unici)
- ✅ Esempi per classe
- ✅ Filtro multiselect per classe
- ✅ **Tabella completa filtrata** (height=400px)
- ✅ Analisi per supernode_name (raggruppamento)
- ✅ Download CSV finale
- ✅ Download Summary JSON

---

## Modifica Recente: Tabelle Complete

### Prima (Campioni)
```python
# Step 1: prime 10 righe
st.dataframe(df_prepared[display_cols].head(10), use_container_width=True)

# Step 2: prime 20 righe
st.dataframe(df_filtered[display_cols].head(20), use_container_width=True)

# Step 3: prime 20 righe
st.dataframe(df_filtered_final[display_cols].head(20), use_container_width=True)
```

### Dopo (Tabelle Complete)
```python
# Step 1: tutte le righe
st.dataframe(df_prepared[display_cols], use_container_width=True, height=400)

# Step 2: tutte le righe (filtrate)
st.dataframe(df_filtered[display_cols], use_container_width=True, height=400)

# Step 3: tutte le righe (filtrate)
st.dataframe(df_filtered_final[display_cols], use_container_width=True, height=400)
```

### Vantaggi
- ✅ **Visualizzazione completa**: Tutte le righe visibili con scroll
- ✅ **Altezza fissa**: 400px per evitare tabelle troppo lunghe
- ✅ **Filtri**: Multiselect per classe mantiene la visualizzazione completa
- ✅ **Contatore**: Mostra numero totale righe visualizzate
- ✅ **Esportazione**: Download CSV per analisi offline

---

## Come Usare

### Avvio
```bash
cd eda
streamlit run app.py
```

### Workflow Completo
1. **Upload Files**
   - CSV: `output/2025-10-21T07-40_export_ENRICHED.csv`
   - JSON: `output/activations_dump (2).json` (opzionale)

2. **Step 1: Preparazione**
   - Clicca "▶️ Esegui Step 1"
   - Verifica statistiche (functional/semantic, json/fallback)
   - **Esamina tabella completa** (scroll per vedere tutte le righe)
   - Download CSV Step 1 (opzionale)

3. **Step 2: Classificazione**
   - (Opzionale) Modifica soglie nella sidebar
   - Clicca "▶️ Esegui Step 2"
   - Verifica distribuzione classi
   - **Filtra per classe** e esamina tabella completa
   - Download CSV Step 2 (opzionale)
   - **Iterazione**: Modifica soglie e riesegui senza rifare Step 1

4. **Step 3: Naming**
   - Clicca "▶️ Esegui Step 3"
   - Verifica esempi naming per classe
   - **Filtra per classe** e esamina tabella completa
   - Analizza raggruppamento per supernode_name
   - **Download CSV finale** (richiesto per analisi successive)
   - Download Summary JSON (documentazione)

---

## Visualizzazione Tabelle

### Caratteristiche
- **Scroll verticale**: Altezza fissa 400px con scroll interno
- **Scroll orizzontale**: Automatico per colonne che non entrano
- **Ordinamento**: Click su header colonna per ordinare
- **Ricerca**: Ctrl+F nel browser per cercare nella tabella
- **Selezione**: Click su riga per evidenziare
- **Copia**: Seleziona celle e copia con Ctrl+C

### Colonne Visualizzate

#### Step 1
- `feature_key`: Identificativo feature (es. "1_12928")
- `prompt`: Testo del prompt
- `peak_token`: Token con max activation
- `peak_token_type`: "functional" o "semantic"
- `target_tokens`: JSON array con target (per functional)
- `tokens_source`: "json", "fallback", o "n/a"

#### Step 2
- `feature_key`, `layer`, `prompt`, `peak_token`, `peak_token_type`
- `pred_label`: Classe predetta ("Semantic", "Say \"X\"", "Relationship")
- `subtype`: Sottotipo (es. "Dictionary", "Concept")
- `confidence`: Confidenza classificazione (0.0-1.0)
- `review`: True se richiede review manuale

#### Step 3
- `feature_key`, `layer`, `prompt`, `peak_token`, `pred_label`, `subtype`
- **`supernode_name`**: Nome generato (es. "Texas", "Say (Austin)", "(capital) related")
- `confidence`: Confidenza classificazione

---

## Filtri e Analisi

### Filtro per Classe (Step 2 e 3)
```python
selected_classes = st.multiselect(
    "Filtra per classe",
    options=['Semantic', 'Say "X"', 'Relationship'],
    default=['Semantic', 'Say "X"', 'Relationship']
)
```

**Uso**:
- Deseleziona classi per nasconderle
- Utile per focalizzarsi su una classe specifica
- Il contatore mostra righe filtrate

### Analisi per Supernode Name (Step 3)
```
| Supernode Name    | N Features | Classe      | Layer Range |
|-------------------|------------|-------------|-------------|
| Texas             | 5          | Semantic    | 0-20        |
| Say (Austin)      | 8          | Say "X"     | 16-22       |
| (capital) related | 4          | Relationship| 1           |
```

**Informazioni**:
- Quante feature hanno lo stesso nome
- Classe predominante
- Range di layer

---

## Download Risultati

### CSV Step 1 (Opzionale)
- Nome: `node_grouping_step1_YYYYMMDD_HHMMSS.csv`
- Contenuto: Tutte le colonne originali + `peak_token_type`, `target_tokens`, `tokens_source`
- Uso: Debug, analisi intermedia

### CSV Step 2 (Opzionale)
- Nome: `node_grouping_step2_YYYYMMDD_HHMMSS.csv`
- Contenuto: Step 1 + `pred_label`, `subtype`, `confidence`, `review`, `why_review`
- Uso: Validazione classificazione, tuning soglie

### CSV Finale (Richiesto)
- Nome: `node_grouping_final_YYYYMMDD_HHMMSS.csv`
- Contenuto: Tutte le colonne + **`supernode_name`**
- Uso: Input per visualizzazione grafo, analisi finale

### Summary JSON (Documentazione)
- Nome: `node_grouping_summary_YYYYMMDD_HHMMSS.json`
- Contenuto:
  ```json
  {
    "timestamp": "2025-10-25T...",
    "n_features": 39,
    "n_unique_names": 11,
    "class_distribution": {
      "Semantic": 35,
      "Relationship": 4
    },
    "thresholds_used": {...},
    "top_supernodes": [...]
  }
  ```
- Uso: Documentazione esperimento, riproducibilità

---

## Best Practices

1. ✅ **Fornisci JSON attivazioni** per Relationship naming accurato
2. ✅ **Esamina tabelle complete** prima di procedere allo step successivo
3. ✅ **Usa filtri** per focalizzarti su classi specifiche
4. ✅ **Itera su Step 2** con soglie diverse per ottimizzare classificazione
5. ✅ **Controlla review warnings** per identificare casi ambigui
6. ✅ **Scarica Summary JSON** per documentare parametri usati
7. ✅ **Verifica naming** nella tabella Step 3 prima di esportare

---

## Riferimenti

- **Script Backend**: `scripts/02_node_grouping.py`
- **Guida Utente**: `eda/pages/README_NODE_GROUPING.md`
- **Documentazione Tecnica**: `output/STEP3_IMPLEMENTATION_SUMMARY.md`
- **Piano Originale**: `node.plan.md`
- **Test**: `tests/test_node_naming.py`

---

## Conclusione

La pagina Streamlit Node Grouping è **completa e pronta per l'uso**. Tutte le tabelle mostrano i risultati completi con scroll, permettendo una visualizzazione e analisi approfondita di ogni step della pipeline.

**Modifiche richieste implementate**: ✅
- Tabelle complete invece di campioni
- Altezza fissa con scroll per usabilità
- Contatori per numero righe visualizzate

**Pronto per produzione!** 🚀

