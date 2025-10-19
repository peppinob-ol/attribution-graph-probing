# Probe Prompts - Guida Rapida (v2.0)

## 🚀 Setup Veloce

### 1. Configura API Keys

Crea o modifica il file `.env` nella root del progetto:

```bash
# .env
NEURONPEDIA_API_KEY=your-neuronpedia-api-key
OPENAI_API_KEY=your-openai-api-key  # Opzionale, solo per generare concepts
```

Oppure usa il comando:
```bash
echo "NEURONPEDIA_API_KEY=your-key" >> .env
echo "OPENAI_API_KEY=your-key" >> .env
```

### 2. Avvia Streamlit

```bash
streamlit run eda/app.py
```

### 3. Naviga a "01_Probe_Prompts"

---

## 📋 Workflow Base

### STEP 1: Carica Graph JSON

**Opzione A - Da File Locale:**
- Seleziona un file da `output/graph_data/*.json`
- Oppure upload manuale

**Opzione B - Da API Neuronpedia:**
- Inserisci Model ID (es: `gemma-2-2b`)
- Inserisci Graph Slug (dall'URL Neuronpedia)
- Clicca "Carica da API"

### STEP 2: Filtra Features

- **Slider**: Imposta "Cumulative Influence Contribution" (consigliato: 95%)
- **Risultato**: Vedi quante features verranno processate
- **Esempio**: 500 features → 95% → ~150 features selezionate

💡 **Tip**: Inizia con 95% per bilanciare copertura e velocità

### STEP 3: Definisci Concepts

**Opzione A - Generazione Automatica:**
1. Tab "🤖 Genera con OpenAI"
2. Il prompt originale è pre-caricato dal graph
3. Scegli numero concepts (es: 5)
4. Clicca "Genera Concepts"

**Opzione B - Manuale:**
1. Tab "✏️ Inserimento Manuale"
2. Modifica il JSON template
3. Clicca "Carica Concepts"

### STEP 4: Modifica Concepts (opzionale)

- Tabella editabile
- Aggiungi/rimuovi righe
- Modifica label, category, description
- Salva come JSON per riuso futuro

### STEP 5: Esegui Analisi

1. **Parametri**:
   - Soglia percentile attivazione (default: 0.9)
   - Calcola baseline (✓ consigliato)
   - Nome file output CSV

2. **Verifica Stima**:
   ```
   Features selezionate: 150
   Concepts: 5
   Baseline: Sì (150 chiamate)
   Totale chiamate: ~900
   Tempo stimato: ~3.0 minuti
   ```

3. **Avvia**: Clicca "▶️ Esegui Analisi"
   - Progress bar in tempo reale
   - Risultati salvati automaticamente in `output/`

### STEP 6: Esplora Risultati

- **Filtri**: Label, Category, Layer
- **Statistiche**: Z-score medio, Picco su Label %, Cosine Similarity
- **Export**: Scarica CSV filtrato

---

## 🎯 Esempi d'Uso

### Esempio 1: Analisi Veloce (5 minuti)

```yaml
Graph: anthropological-circuit.json (500 features)
Cumulative Influence: 90% (→ ~120 features)
Concepts: 3 (generati con OpenAI)
Baseline: Sì
Tempo: ~2 minuti
```

### Esempio 2: Analisi Dettagliata (15 minuti)

```yaml
Graph: large-circuit.json (2000 features)
Cumulative Influence: 95% (→ ~300 features)
Concepts: 10 (inseriti manualmente)
Baseline: Sì
Tempo: ~18 minuti
```

### Esempio 3: Analisi Estensiva (30+ minuti)

```yaml
Graph: complete-circuit.json (5000 features)
Cumulative Influence: 99% (→ ~800 features)
Concepts: 20
Baseline: Sì
Tempo: ~96 minuti
```

💡 **Tip**: Per test rapidi, usa cumulative 80-85% e 2-3 concepts

---

## 📊 Interpretare i Risultati

### Colonne Principali

| Colonna | Significato | Valori Tipici |
|---------|-------------|---------------|
| `z_score` | Quanto l'attivazione devia dalla baseline | >2: significativo |
| `picco_su_label` | Il picco è sul label del concept? | True/False |
| `ratio_max_vs_original` | Rapporto max nuova / max originale | >1: si attiva di più |
| `cosine_similarity` | Similarità pattern attivazione | >0.5: simile |
| `influence` | Influence originale nel graph | Già ordinato |

### Filtri Utili

```python
# Features altamente responsive al concept
df_high_z = df[df['z_score'] > 3]

# Features che si attivano proprio sul label
df_on_label = df[df['picco_su_label'] == True]

# Features con pattern molto diverso da baseline
df_new_pattern = df[df['cosine_similarity'] < 0.3]

# Features che si attivano MOLTO di più del baseline
df_amplified = df[df['ratio_max_vs_original'] > 5]
```

---

## ⚡ Ottimizzazioni

### Ridurre Tempo di Analisi

1. **Abbassa cumulative influence**
   - 95% → 90%: -30% features
   - 90% → 85%: -40% features

2. **Riduci concepts**
   - Focalizzati sui più rilevanti
   - Testa con 2-3, poi espandi

3. **Disabilita baseline**
   - Se non serve confronto con originale
   - Dimezza il numero di chiamate API

4. **Usa cache**
   - Le baseline sono cachate automaticamente
   - Riusa stesso graph per multiple analisi

### Ridurre Costi API

- Le API Neuronpedia sono gratuite (con rate limit)
- Considera: features × concepts = chiamate totali
- Esempio: 100 feat × 10 concepts = 1000 chiamate
- Rate limit: 5 req/sec → ~3.3 min

---

## 🔧 Troubleshooting

### "No data" per alcune features

**Causa**: Feature non esiste su Neuronpedia o non ha attivazioni

**Soluzione**: Normale, vengono skippate automaticamente

### Progress bar si blocca

**Causa**: Timeout di rete o API key scaduta

**Soluzione**: 
1. Controlla console Streamlit per errori
2. Verifica API key
3. Riprova con meno features

### Risultati "NaN" in molte colonne

**Causa**: Baseline non calcolata o label non trovato in tokens

**Soluzione**:
- Abilita "Calcola baseline"
- Verifica che il label sia tokenizzabile (no special chars strani)

### Tempo stimato molto lungo

**Causa**: Troppe features selezionate

**Soluzione**:
- Alza cumulative influence threshold (es: 98%)
- Oppure riduci concepts
- Oppure disabilita baseline

---

## 💡 Best Practices

### 1. Iterazione Rapida
```
1. Test con cumulative 85%, 2 concepts, no baseline (~30 sec)
2. Se i risultati sono interessanti, espandi
3. Full analysis con 95%, 10 concepts, baseline (~15 min)
```

### 2. Naming Conventions
```
# File output CSV
concepts_[graph-name]_[date].csv
concepts_anthropological_20251019.csv
```

### 3. Salva i Concepts
- Dopo generazione OpenAI, salva come JSON
- Riusali per altre analisi
- Crea "concept libraries" tematiche

### 4. Analisi Incrementale
```python
# Script Python per batch analysis
concepts_batch_1 = [...] # primi 10
df1 = analyze_concepts_from_graph_json(...)

concepts_batch_2 = [...] # secondi 10
df2 = analyze_concepts_from_graph_json(...)

# Merge
df_full = pd.concat([df1, df2])
```

---

## 📚 Risorse

- **Documentazione completa**: `docs/cursor/PROBE_PROMPTS_API_MIGRATION.md`
- **Script Python**: `scripts/01_probe_prompts.py`
- **UI Streamlit**: `eda/pages/01_Probe_Prompts.py`
- **API Neuronpedia**: https://www.neuronpedia.org/api-doc

---

## 🆘 Supporto

**Errori comuni**: Vedi sezione Troubleshooting sopra

**Issue GitHub**: [Crea issue](link-to-repo/issues) con:
- Log errore completo
- Graph JSON usato (o almeno metadata)
- Concepts testati
- Parametri analisi

**Debug verbose**:
```python
# In script Python
df = analyze_concepts_from_graph_json(
    ...,
    verbose=True  # Print dettagli in console
)
```

---

**Happy Probing! 🔍**

