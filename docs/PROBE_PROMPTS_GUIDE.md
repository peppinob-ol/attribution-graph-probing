# Guida: Probe Prompts - Analisi Concepts

## Introduzione

Il modulo **Probe Prompts** permette di analizzare come le features di un grafo di attribuzione si attivano su concepts specifici. Puoi generare automaticamente i concepts tramite OpenAI o definirli manualmente, e ottenere metriche dettagliate sulle attivazioni.

## Setup

### 1. Requisiti

Assicurati di avere installato tutte le dipendenze:

```powershell
pip install -r requirements.txt
```

Le dipendenze principali sono:
- `circuit_tracer` (per caricare modelli SAE)
- `openai>=1.0.0` (per generazione automatica concepts)
- `streamlit>=1.28.0` (per l'interfaccia)
- `torch`, `pandas`, `numpy`

### 2. API Key OpenAI (Opzionale)

Se vuoi usare la generazione automatica dei concepts, crea un file `.openai_api_key` nella root del progetto:

```powershell
# Crea il file con la tua API key
echo "sk-your-openai-key-here" > .openai_api_key
```

Oppure imposta la variabile d'ambiente:

```powershell
$env:OPENAI_API_KEY = "sk-your-openai-key-here"
```

## Avvio

Lancia l'applicazione Streamlit:

```powershell
streamlit run eda/app.py
```

Poi naviga alla pagina **"🔍 Probe Prompts"** dalla sidebar.

## Workflow

### Step 1: Carica il Modello SAE

**Nella sidebar:**
1. Seleziona il modello (es. `google/gemma-2-2b`)
2. Seleziona il transcoder (es. `gemma`)
3. Clicca **"🔄 Ricarica Modello"**
4. Attendi il caricamento (può richiedere 1-2 minuti)
5. Verifica che appaia "✅ Modello attivo"

**Modelli supportati:**
- `google/gemma-2-2b` con transcoder `gemma` (Gemma Scope)
- `meta-llama/Llama-3.2-1B` con transcoder `llama`

### Step 2: Seleziona un Grafo

1. Nella sezione **"1️⃣ Seleziona Grafo"**, scegli un file `.pt`
2. Il file deve essere un grafo salvato con `circuit_tracer` (es. `output/example_graph.pt`)
3. Opzionale: espandi "Mostra info grafo" per vedere dettagli

### Step 3: Definisci i Concepts

Hai 3 opzioni:

#### Opzione A: Generazione Automatica con OpenAI

1. Tab **"🤖 Genera con OpenAI"**
2. Il prompt originale viene caricato automaticamente dal grafo
3. Opzionalmente aggiungi l'output del modello
4. Seleziona quanti concepts generare (1-20)
5. Clicca **"🤖 Genera Concepts con OpenAI"**
6. I concepts vengono estratti automaticamente

**Formato concepts:**
```json
[
  {
    "label": "Dallas",
    "category": "entity",
    "description": "a major city located in the state of Texas"
  },
  {
    "label": "Texas",
    "category": "entity",
    "description": "the U.S. state in which Dallas is located"
  }
]
```

#### Opzione B: Inserimento Manuale

1. Tab **"✏️ Inserimento Manuale"**
2. Scrivi o incolla il JSON dei concepts
3. Clicca **"Carica Concepts Manualmente"**

#### Opzione C: Carica da File

1. Tab **"📂 Carica da File"**
2. Upload di un file `.json` con l'array di concepts

### Step 4: Modifica i Concepts

Nella sezione **"3️⃣ Modifica Concepts"**:

1. Usa la tabella interattiva per:
   - **Modificare** label, category, description
   - **Aggiungere** righe (bottone `+` in basso)
   - **Eliminare** righe (seleziona e premi `Delete`)

2. Le modifiche sono salvate automaticamente in `st.session_state`

3. Puoi salvare i concepts modificati:
   - **"💾 Salva Concepts come JSON"**: salva in `output/concepts_edited.json`
   - **"⬇️ Scarica Concepts"**: download diretto del file

### Step 5: Esegui l'Analisi

Nella sezione **"4️⃣ Esegui Analisi"**:

1. Configura parametri:
   - **Soglia percentile attivazione** (0.5-0.99): percentile per calcolare densità
   - **Nome file output**: nome del CSV (default `acts_compared.csv`)

2. Clicca **"▶️ Esegui Analisi"**

3. L'analisi calcola per ogni (concept, layer, feature):
   - Attivazioni su label span e sequenza completa
   - Z-scores (standard, robust IQR, log-scaled)
   - TWERA (Total Weighted Edge-Regulated Activation)
   - Densità, cosine similarity, ratio vs original
   - Peak token e posizione

4. Risultati salvati in `output/acts_compared.csv`

### Step 6: Visualizza Risultati

Nella sezione **"5️⃣ Risultati"**:

1. **Filtri**: Seleziona label, category, layer da visualizzare

2. **Tabella interattiva**: Scorri e ordina i risultati

3. **Statistiche rapide**:
   - Features totali
   - Z-score medio
   - % picco su label
   - Cosine similarity media

4. **Download**: Scarica risultati filtrati come CSV

## Output CSV

Il file `output/acts_compared.csv` contiene queste colonne:

### Identificatori
- `label`: Label del concept
- `category`: Categoria del concept (entity, relationship, attribute, etc.)
- `layer`: Layer del SAE
- `feature`: Indice della feature

### Attivazioni
- `attivazione_vecchio_prompt`: Attivazione originale sul prompt del grafo
- `nuova_somma_sequenza`: Somma attivazioni su tutta la sequenza del concept
- `nuova_somma_label_span`: Somma attivazioni sullo span del label
- `nuova_max_label_span`: Max attivazione sullo span
- `nuova_media_label_span`: Media attivazioni sullo span
- `nuova_l2_label_span`: Norma L2 attivazioni sullo span

### Metriche Comparative
- `ratio_max_vs_original`: Ratio tra max attivazione concept e original
- `cosine_similarity`: Similarità coseno tra sequenze attivazioni
- `density_attivazione`: Frazione di token con attivazione > soglia
- `normalized_sum_label`: Somma normalizzata per lunghezza label
- `normalized_sum_seq`: Somma normalizzata per lunghezza sequenza

### Z-Scores
- `z_score`: Z-score standard (max - original) / std
- `z_score_robust`: Z-score robust basato su IQR
- `z_score_log`: Z-score log-scaled

### TWERA
- `twera_total_in`: Total Weighted Edge-Regulated Activation

### Metadata
- `picco_su_label`: Boolean, se il picco cade sullo span del label
- `peak_token`: Token con attivazione massima
- `label_span_start`, `label_span_end`: Posizioni dello span
- `seq_len`: Lunghezza sequenza
- `prompt`: Prompt usato ("label: description")

## Esempio d'Uso Programmatico

Puoi usare lo script anche da Python:

```python
from scripts.probe_prompts import analyze_concepts
from circuit_tracer import ReplacementModel
from circuit_tracer.graph import Graph

# Carica modello
model = ReplacementModel.from_pretrained(
    "google/gemma-2-2b", 
    "gemma", 
    dtype=torch.bfloat16
)

# Carica grafo
graph = Graph.from_pt("output/example_graph.pt")

# Definisci concepts
concepts = [
    {
        "label": "Dallas", 
        "category": "entity", 
        "description": "a major city located in the state of Texas"
    },
    {
        "label": "Texas", 
        "category": "entity", 
        "description": "the U.S. state in which Dallas is located"
    },
]

# Esegui analisi
df = analyze_concepts(
    model=model,
    graph=graph,
    concepts=concepts,
    activation_threshold_quantile=0.9,
    output_csv="output/acts_compared.csv"
)

# Analizza risultati
print(df.head())
print(f"Z-score medio: {df['z_score'].mean():.2f}")
print(f"Picco su label: {df['picco_su_label'].sum()} / {len(df)}")
```

## Tips & Tricks

### 1. Generazione Concepts Efficace

- **Sii specifico**: Descrizioni chiare aiutano a generare concepts migliori
- **Includi l'output**: Se disponibile, l'output del modello migliora la qualità
- **Numero ottimale**: 5-10 concepts di solito bastano per un'analisi completa

### 2. Interpretazione Z-Scores

- **z_score > 2**: Attivazione significativamente più alta sul concept
- **z_score_robust**: Più robusto a outlier rispetto a z_score standard
- **z_score_log**: Utile per visualizzare ordini di magnitudine diversi

### 3. TWERA

- Alto TWERA indica che la feature è ben collegata ad altre features attive
- Utile per identificare hub nel circuito

### 4. Performance

- **Modelli grandi**: Il caricamento può richiedere 1-2 minuti e 8-16GB RAM
- **Batch size**: Se hai problemi di memoria, riduci il batch size nel codice
- **GPU**: Fortemente consigliata per analisi su grafi grandi

## Troubleshooting

### Errore: "Modello SAE non caricato"
**Soluzione**: Clicca "🔄 Ricarica Modello" nella sidebar prima di eseguire l'analisi.

### Errore: "circuit_tracer non trovato"
**Soluzione**: Installa circuit_tracer:
```powershell
pip install circuit_tracer
```

### Errore: "API Key OpenAI non valida"
**Soluzione**: Verifica che la key nel file `.openai_api_key` sia corretta.

### Risultati vuoti
**Possibili cause**:
- Grafo senza features attive
- Concepts non trovati nella sequenza
- Soglia troppo alta

**Soluzione**: Controlla il grafo e abbassa la soglia percentile.

## Riferimenti

- [Circuit Tracer Documentation](https://github.com/safety-research/circuit-tracer)
- [Gemma Scope Paper](https://arxiv.org/abs/2408.05147)
- [OpenAI API Docs](https://platform.openai.com/docs)

## Supporto

Per domande o problemi, consulta:
- `docs/supernode_labelling/README.md` - Overview sistema labelling
- `eda/METRICS_GLOSSARY.md` - Glossario metriche
- `eda/GUIDA_RAPIDA.md` - Guida rapida EDA

