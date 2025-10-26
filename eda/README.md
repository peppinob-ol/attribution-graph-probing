# Circuit Tracer + Probe Rover - Applicazione Streamlit

**Versione:** 2.0.0-clean | Pipeline v2  
**Data:** Ottobre 2025

---

## Panoramica

Applicazione Streamlit interattiva per l'analisi di attribution graphs e probe prompting su modelli linguistici con Sparse Autoencoders (SAE).

### Funzionalita Principali

1. **Graph Generation** - Genera attribution graphs su Neuronpedia
2. **Probe Prompts** - Analizza attivazioni su concepts specifici
3. **Node Grouping** - Classifica e nomina supernodi per interpretazione

---

## Avvio Rapido

### Prerequisiti

```bash
pip install streamlit plotly pandas seaborn matplotlib numpy requests openai python-dotenv
```

Oppure:

```bash
pip install -r requirements.txt
```

### Configurazione API Keys

Crea un file `.env` nella root del progetto:

```env
NEURONPEDIA_API_KEY='your-neuronpedia-key-here'
OPENAI_API_KEY='your-openai-key-here'
```

### Avvio Applicazione

Dalla root del progetto:

```bash
streamlit run eda/app.py
```

L'app si aprira automaticamente su `http://localhost:8501`

---

## Pagine dell'Applicazione

### Pagina Principale

Dashboard con:
- Link rapidi alle pagine
- Info sulla struttura output folder
- Statistiche file disponibili (grafi, JSON, CSV)

### 00 - Graph Generation

**Genera attribution graphs su Neuronpedia**

#### Funzionalita

- **Generazione Graph**: Crea nuovi attribution graphs tramite API Neuronpedia
- **Estrazione Metriche**: Genera CSV con node_influence, cumulative_influence, frac_external_raw
- **Visualizzazione Interattiva**: Scatter plot Layer vs Context Position con filtri
- **Export Features**: Seleziona e scarica features per analisi successive
- **Grafici Riassuntivi**: Coverage e Strength analysis

#### Parametri Configurabili

**Model & Source Set:**
- Model ID (gemma-2-2b, gpt2-small, gemma-2-9b)
- Source Set Name (gemmascope-transcoder-16k, etc.)
- Max Feature Nodes (100-10000)

**Thresholds:**
- Node Threshold (0.0-1.0, default 0.8)
- Edge Threshold (0.0-1.0, default 0.85)
- Max N Logits (1-50, default 10)
- Desired Logit Probability (0.5-0.99, default 0.95)

#### Output

- Graph JSON salvato in `output/graph_data/`
- CSV metriche statiche in `output/graph_feature_static_metrics.csv`
- Features selezionate JSON per Node Grouping

#### Workflow

1. Configura parametri (model, thresholds)
2. Inserisci prompt da analizzare
3. Genera graph (salvato automaticamente)
4. Genera CSV metriche statiche
5. Visualizza scatter plot e filtra features per cumulative influence
6. Esporta features selezionate (formato completo: features + node_ids)
7. Scarica JSON/CSV per step successivi

---

### 01 - Probe Prompts

**Analizza attivazioni su concepts specifici tramite API**

#### Funzionalita

- **Caricamento Graph**: Da file locale o API Neuronpedia
- **Feature Subset**: Carica un subset di features o usa tutte
- **Generazione Concepts**: Automatica via OpenAI o inserimento manuale
- **Analisi Attivazioni**: Via API Neuronpedia o caricamento JSON pre-calcolato
- **Checkpoint & Recovery**: Salvataggio automatico progressi, ripresa da interruzioni
- **Visualizzazioni**: Main chart (Importance vs Activation), grafici colorati per peak token
- **Coverage Analysis**: Percentuale features attive e coverage dell'importanza causale

#### Parametri Configurabili

**API Keys:**
- Neuronpedia API Key (richiesta)
- OpenAI API Key (per generazione concepts)
- Model OpenAI (gpt-4o-mini, gpt-4o, gpt-3.5-turbo)

**Analisi:**
- Activation Threshold Quantile (0.5-0.99, default 0.9)
- Use Baseline (calcola metriche vs prompt originale)
- Checkpoint Every N Features (5-100, default 10)

#### Output

- CSV con attivazioni: `output/acts_compared.csv`
- Checkpoint JSON (salvati automaticamente in `output/checkpoints/`)
- Grafici interattivi con filtri

#### Workflow

1. Carica Graph JSON (file o API)
2. Carica feature subset (o usa tutte le features del grafo)
3. Genera/carica concepts (OpenAI, manuale o da file)
4. Modifica concepts nella tabella editabile
5. Salva concepts come prompts JSON
6. **Analisi via API**:
   - Configura parametri (threshold, baseline, checkpoint)
   - Esegui analisi (con progress tracking)
   - Visualizza risultati (tabella + grafici)
   - Scarica CSV filtrati
7. **Analisi da JSON** (alternativa):
   - Carica JSON pre-calcolato da Colab
   - Visualizza Main Chart (Importance vs Activation)
   - Analizza grafico colorato per peak token
   - Scarica tabella di verifica dati

#### Main Chart: Importance vs Activation

Grafico a barre stacked che mostra:
- **X-axis**: Features ordinate per node_influence (decrescente)
- **Y-axis (left)**: Activation (max_value, escludendo BOS)
- **Y-axis (right)**: node_influence (linea rossa)
- **Barre colorate**: Per prompt o per peak token

**Filtri:**
- Top N features (10-100)
- Escludi features con peak su BOS

**Tabella di Verifica**:
Dati grezzi usati per il grafico con metriche dettagliate:
- `activation_max`: Picco massimo di attivazione (esclude BOS)
- `activation_sum`: Somma totale attivazioni (esclude BOS)
- `activation_mean`: Media attivazioni normalizzata
- `sparsity_ratio`: Concentrazione attivazione (0=uniforme, 1=molto sparsa)
- `peak_token_idx`: Posizione del picco (>=1, esclude BOS)
- `node_influence`: Valore massimo dal CSV
- `csv_ctx_idx`: Contesto token dove node_influence e massima

**Coverage Analysis**:
- Features Coverage: % features (nel JSON) che si attivano (>0) su almeno un probe prompt
- Importance Coverage: % importanza causale coperta dalle features attive

---

### 02 - Node Grouping

**Classifica e nomina supernodi per interpretazione del grafo**

#### Funzionalita

- **Step 1 - Preparazione**: Classifica token (functional vs semantic), trova target tokens
- **Step 2 - Classificazione**: Assegna classi ai nodi (Semantic, Say X, Relationship)
- **Step 3 - Naming**: Genera nomi descrittivi per ogni supernodo
- **Parametri Configurabili**: Modifica soglie in tempo reale
- **Gestione Soglie**: Salva/carica preset di soglie
- **Spiegazione Classificazione**: Tool interattivo per capire perche una feature e stata classificata
- **Upload Neuronpedia**: Carica subgraph con supernodes per visualizzazione interattiva

#### Input Richiesti

**Obbligatori:**
- CSV Export da Probe Prompts (es. `*_export_ENRICHED.csv`)

**Opzionali:**
- JSON Attivazioni (migliora naming per Relationship)
- Graph JSON (per csv_ctx_idx fallback in Semantic naming)
- Selected Nodes JSON (per upload subgraph accurato)

#### Parametri Configurabili

**Pipeline:**
- Finestra ricerca target (3-15, default 7)

**Dictionary Semantic:**
- Peak Consistency min (0.5-1.0, default 0.8)
- N Distinct Peaks max (1-5, default 1)

**Say X:**
- Func vs Sem % min (0-100%, default 50%)
- Confidence F min (0.5-1.0, default 0.9)
- Layer min (0-30, default 7)

**Relationship:**
- Sparsity max (0.0-1.0, default 0.45)

**Semantic (Concept):**
- Layer max (0-10, default 3)
- Confidence S min (0.0-1.0, default 0.5)
- Func vs Sem % max (0-100%, default 50%)

#### Output

- CSV completo con classificazione e naming
- Summary JSON con statistiche e parametri usati
- Upload su Neuronpedia (opzionale)

#### Workflow

**Step 1: Preparazione**
1. Carica CSV Export (automatico o upload)
2. (Opzionale) Carica JSON Attivazioni
3. Esegui Step 1
4. Verifica statistiche (token funzionali vs semantici)
5. Esamina campione risultati

**Step 2: Classificazione**
1. (Opzionale) Modifica soglie nella sidebar
2. Esegui Step 2
3. Verifica distribuzione classi
4. Filtra per classe e esamina risultati
5. Usa "Spiega Classificazione Feature" per capire le decisioni
6. (Opzionale) Itera modificando soglie

**Step 3: Naming**
1. Esegui Step 3
2. Verifica esempi naming per classe
3. Analizza raggruppamento per supernode_name
4. Download CSV completo e Summary JSON

**Upload Neuronpedia:**
1. Inserisci API Key
2. Configura Display Name
3. (Opzionale) Overwrite ID per aggiornare subgraph esistente
4. Upload e visualizza su Neuronpedia

#### Classi di Supernodi

**Semantic (Dictionary):**
- Si attiva sempre sullo stesso token specifico
- Metriche: peak_consistency alta (>=0.8), n_distinct_peaks = 1
- Naming: Nome del token (es. "Texas")

**Semantic (Concept):**
- Si attiva su token semanticamente simili
- Metriche: conf_S alta (>=0.5), layer medio-basso
- Naming: Token con max activation (es. "city")

**Say "X":**
- Si attiva su token funzionali per predire il prossimo token
- Metriche: func_vs_sem alta (>=50%), conf_F alta (>=0.9), layer alto (>=7)
- Naming: "Say (X)" dove X e il target_token (es. "Say (Austin)")

**Relationship:**
- Collega concetti semantici multipli con attivazione diffusa
- Metriche: sparsity bassa (<0.45), K_sem_distinct alto
- Naming: "(X) related" dove X e il primo token semantico con max attivazione

#### Metriche Chiave

- `peak_consistency_main`: Quanto spesso il token principale e peak quando appare
- `n_distinct_peaks`: Numero di token distinti come peak
- `func_vs_sem_pct`: Differenza % tra max activation su functional vs semantic
- `conf_F / conf_S`: Frazione di peak su token funzionali/semantici
- `sparsity_median`: Mediana sparsity (0=diffusa, 1=concentrata)
- `K_sem_distinct`: Numero di token semantici distinti

---

## Struttura Dati

### File Input

**Graph JSON** (da Graph Generation):
```json
{
  "metadata": {
    "scan": "gemma-2-2b",
    "prompt": "The capital of state containing Dallas is",
    "prompt_tokens": [...]
  },
  "nodes": [
    {
      "node_id": "24_79427_7",
      "feature_type": "cross layer transcoder",
      "layer": 24,
      "activation": 0.123,
      "influence": 0.0042,
      "ctx_idx": 7
    }
  ],
  "links": [...]
}
```

**CSV Export ENRICHED** (da Probe Prompts):
```csv
feature_key,layer,prompt,peak_token,peak_token_idx,activation_max,sparsity_ratio,node_influence,...
24_79427,24,"entity: The capital city of Texas is Austin",Austin,7,12.34,0.85,0.0042,...
```

**JSON Attivazioni** (da batch_get_activations.py):
```json
{
  "model": "gemma-2-2b",
  "source_set": "clt-hp",
  "results": [
    {
      "probe_id": "p1",
      "prompt": "...",
      "tokens": ["<BOS>", "The", "capital", ...],
      "activations": [
        {
          "source": "24-clt-hp",
          "index": 79427,
          "values": [0.0, 0.5, 12.34, ...],
          "max_value": 12.34,
          "max_value_index": 7
        }
      ]
    }
  ]
}
```

### File Output

**CSV Metriche Statiche** (Graph Generation):
```csv
layer,id,ctx_idx,activation,node_influence,cumulative_influence,frac_external_raw
24,79427,7,12.34,0.0042,0.0056,0.23
```

**Selected Features JSON** (Graph Generation, formato completo):
```json
{
  "features": [
    {"layer": 24, "index": 79427},
    {"layer": 12, "index": 5432}
  ],
  "node_ids": [
    "24_79427_7",
    "12_5432_3"
  ],
  "metadata": {
    "n_features": 2,
    "n_nodes": 2,
    "cumulative_threshold": 0.95,
    "exported_at": "2025-10-25T12:00:00"
  }
}
```

**Acts Compared CSV** (Probe Prompts):
```csv
feature_key,label,category,layer,activation_max,z_score,picco_su_label,cosine_similarity,...
24_79427,Austin,entity,24,12.34,2.5,True,0.85,...
```

**Node Grouping CSV** (Node Grouping):
```csv
feature_key,layer,prompt,pred_label,subtype,supernode_name,peak_token,activation_max,...
24_79427,24,"...",Semantic,Dictionary,Austin,Austin,12.34,...
```

**Node Grouping Summary JSON**:
```json
{
  "timestamp": "2025-10-25T12:00:00",
  "n_features": 150,
  "n_unique_names": 45,
  "class_distribution": {
    "Semantic": 120,
    "Relationship": 20,
    "Say \"X\"": 10
  },
  "thresholds_used": {...},
  "top_supernodes": [...]
}
```

---

## Workflow Completo

### Pipeline Standard

```
1. Graph Generation
   ↓
   - Graph JSON
   - CSV metriche statiche
   - Selected Features JSON
   ↓
2. Probe Prompts
   ↓
   - Genera/carica concepts
   - Analizza attivazioni (API o JSON)
   - Acts Compared CSV
   ↓
3. Node Grouping
   ↓
   - Classifica nodi
   - Nomina supernodi
   - Upload su Neuronpedia (opzionale)
```

### Esempio Pratico

**Obiettivo**: Analizzare come il modello predice "Austin" nel prompt "The capital of state containing Dallas is"

1. **Graph Generation**:
   - Prompt: "The capital of state containing Dallas is"
   - Genera graph su Neuronpedia
   - Estrai CSV metriche con node_influence
   - Filtra features per cumulative_influence <= 0.95
   - Esporta Selected Features JSON (50 features)

2. **Probe Prompts**:
   - Carica Graph JSON + Selected Features JSON
   - Genera concepts con OpenAI (Dallas, Austin, Texas, capital, state)
   - Esegui analisi API (checkpoint ogni 10 features)
   - Visualizza Main Chart: feature ordinate per node_influence
   - Scarica Acts Compared CSV

3. **Node Grouping**:
   - Carica Acts Compared CSV + JSON Attivazioni
   - Step 1: Classifica token (functional: "is", "the" / semantic: "Dallas", "Austin")
   - Step 2: Classifica features (90% Semantic, 10% Relationship)
   - Step 3: Nomina supernodi ("Austin", "Dallas", "Texas", "(state) related", etc.)
   - Upload su Neuronpedia per visualizzazione

---

## Troubleshooting

### Problemi Comuni

**"API Key non trovata"**
- Soluzione: Crea file `.env` con le chiavi API

**"Dati essenziali mancanti"**
- Soluzione: Esegui la pipeline completa in ordine (Graph Generation → Probe Prompts → Node Grouping)

**"Grafo causale non disponibile"**
- Soluzione: Genera Graph JSON in Step 00, poi genera CSV metriche statiche

**"ModuleNotFoundError: eda"**
- Soluzione: Avvia da root del progetto: `streamlit run eda/app.py`

**"Checkpoint corrotto"**
- Soluzione: Elimina checkpoint in `output/checkpoints/` e riavvia analisi

**"Naming Relationship non accurato"**
- Soluzione: Fornisci JSON attivazioni completo in Node Grouping

**"Classificazione non soddisfacente"**
- Soluzione: Modifica soglie in Node Grouping sidebar e riesegui Step 2

### Cache Streamlit

Se i dati sembrano obsoleti:
- Menu hamburger (top-right) > Clear cache
- Oppure Settings > Clear cache
- Riavvia l'app

---

## Best Practices

### Graph Generation
1. Inizia con thresholds di default, poi affina
2. Usa filtro cumulative_influence per selezionare features rilevanti
3. Esporta sempre Selected Features JSON (formato completo con node_ids) per Node Grouping

### Probe Prompts
1. Usa checkpoint per analisi lunghe (>100 features)
2. Abilita baseline per confronti robusti
3. Carica JSON pre-calcolato da Colab per analisi veloci
4. Filtra features con peak su BOS per grafici piu puliti
5. Usa tabella di verifica per debug e quality check

### Node Grouping
1. Fornisci sempre JSON attivazioni per naming Relationship accurato
2. Inizia con soglie di default, poi itera su Step 2-3
3. Usa "Spiega Classificazione Feature" per capire decisioni
4. Scarica Summary JSON per documentare parametri usati
5. Carica Selected Nodes JSON per upload Neuronpedia accurato

---

## Performance

**Caricamento:**
- Prima apertura app: < 10 secondi
- Cambio pagina: < 2 secondi

**Cache:**
- Dati caricati con `@st.cache_data`
- Grafici renderizzati on-demand

**Limiti:**
- Graph Generation: max 10000 feature nodes
- Probe Prompts: rate limit API 5 req/sec
- Node Grouping: gestisce dataset fino a 1000 features

---

## Dipendenze

**Core:**
- streamlit >= 1.28
- plotly >= 5.18
- pandas >= 2.0
- numpy >= 1.24

**API:**
- requests >= 2.31
- openai >= 1.0
- python-dotenv >= 1.0

**Visualization:**
- seaborn >= 0.12
- matplotlib >= 3.7

**Optional:**
- scipy (per test statistici in Causal Validation)
- scikit-learn (per ROC curves)

---

## Riferimenti

### Documentazione Tecnica
- Graph Generation: `scripts/00_neuronpedia_graph_generation.py`
- Probe Prompts: `scripts/01_probe_prompts.py`
- Node Grouping: `scripts/02_node_grouping.py`
- Causal Utils: `scripts/causal_utils.py`

### Guide
- Quick Start: `QUICK_START_STREAMLIT.md`
- Neuronpedia Export: `docs/NEURONPEDIA_EXPORT_GUIDE.md`
- Probe Prompts: `docs/PROBE_PROMPTS_QUICKSTART.md`
- Node Grouping: `eda/pages/README_NODE_GROUPING.md`

### Utilities
- Graph Visualization: `eda/utils/graph_visualization.py`
- Data Loader: `eda/utils/data_loader.py`
- Plots: `eda/utils/plots.py`

---

## Sviluppo

### Struttura Codice

```
eda/
├── app.py                          # Entry point
├── pages/                          # Pagine Streamlit
│   ├── 00_Graph_Generation.py
│   ├── 01_Probe_Prompts.py
│   ├── 02_Node_Grouping.py
│   └── README_NODE_GROUPING.md
├── utils/                          # Utilities
│   └── graph_visualization.py
└── README.md                       # Questa guida
```

### Modifiche

Per modificare l'app:
1. Modifica file in `eda/`
2. Streamlit rileva automaticamente cambiamenti
3. Testa con dati reali da `output/`

---

## Supporto

Per domande o problemi:
1. Consulta questa guida
2. Leggi la documentazione tecnica in `docs/`
3. Esamina gli script di backend in `scripts/`
4. Controlla i test in `tests/`

---

**Autore**: Sistema automatizzato  
**Licenza**: Vedi LICENSE  
**Repository**: circuit_tracer-prompt_rover

**Buon lavoro con Circuit Tracer + Probe Rover!** 🔬🌐🔍
