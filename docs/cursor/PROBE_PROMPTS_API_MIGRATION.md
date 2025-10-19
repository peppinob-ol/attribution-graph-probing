# Migrazione Probe Prompts a API Neuronpedia

## Sommario

Il sistema Probe Prompts è stato completamente riscritto per utilizzare le **API di Neuronpedia** invece di un modello locale. Questo porta diversi vantaggi:

1. ✅ **Nessun modello locale richiesto** - Niente più download di modelli pesanti
2. ✅ **Analisi più veloce** - Le API sono ottimizzate e parallellizzabili
3. ✅ **Filtraggio per influence** - Slider per selezionare features per cumulative contribution
4. ✅ **Supporto graph JSON** - Carica direttamente i graph da Neuronpedia

---

## Modifiche Principali

### 1. Script `scripts/01_probe_prompts.py`

#### Prima (v1.x)
```python
def analyze_concepts(model, graph, concepts, ...)
```
- Richiedeva un modello SAE locale caricato in memoria
- Usava `model.get_activations()` per calcolare attivazioni
- Processava TUTTE le features del graph

#### Dopo (v2.0)
```python
def analyze_concepts_from_graph_json(graph_json, concepts, api_key, ...)
```
- **Input**: JSON del graph (da file o API Neuronpedia)
- **API calls**: `POST /api/activation/new` per ogni feature/concept
- **Filtraggio automatico**: Solo features rilevanti per cumulative influence
- **Rate limiting**: 5 req/sec automatico
- **Progress callback**: Supporto per progress bar in UI

#### Nuove Funzioni Helper

##### `filter_features_by_influence(features, cumulative_contribution)`
Ordina features per influence (valore assoluto) e seleziona solo quelle che contribuiscono alla soglia cumulativa.

**Esempio:**
```python
# Con cumulative_contribution = 0.95
# Input: 1000 features
# Output: ~150 features (che rappresentano il 95% dell'influence totale)
filtered, threshold, num_selected, num_total = filter_features_by_influence(
    features, 
    cumulative_contribution=0.95
)
```

##### `NeuronpediaAPI`
Client per API Neuronpedia con:
- Rate limiting automatico (5 req/sec)
- Cache per baseline activations
- Gestione errori HTTP

---

### 2. Pagina Streamlit `eda/pages/01_Probe_Prompts.py`

#### Modifiche UI

##### STEP 1: Caricamento Graph JSON
- **Prima**: Seleziona file `.pt` del graph
- **Dopo**: 
  - Tab "📂 Da File": Carica JSON da `output/graph_data/` o upload manuale
  - Tab "🌐 Da URL/API": Fetch diretto da API Neuronpedia

##### STEP 2: Filtraggio Features (NUOVO!)
- **Slider**: "Cumulative Influence Contribution %" (50-100%)
- **Metriche live**:
  - Features Totali
  - Features Selezionate
  - % Features
  - Soglia Influence

##### STEP 3-4: Definizione Concepts (invariato)
- Generazione con OpenAI
- Inserimento manuale
- Carica da file JSON

##### STEP 5: Esegui Analisi
- **Nuovo parametro**: `use_baseline` (checkbox)
- **Stima chiamate API**: Calcola e mostra:
  - Numero features × concepts
  - Chiamate baseline (se abilitato)
  - Tempo stimato (basato su rate limit)
- **Progress bar**: Aggiornamento live durante analisi

##### STEP 6: Visualizzazione Risultati (migliorata)
- Filtri per label, category, layer
- Statistiche rapide
- Export CSV filtrato

#### Rimozioni
- ❌ Sezione "Modello SAE" (sidebar)
- ❌ Caricamento modello locale
- ❌ Dipendenza da `circuit_tracer.ReplacementModel`

#### Aggiunte
- ✅ API Key Neuronpedia (sidebar)
- ✅ Info graph dettagliate (metadata, influence stats)
- ✅ Stima tempo/costo API

---

## Configurazione

### API Keys Richieste

#### 1. Neuronpedia API Key (obbligatoria per analisi)
```bash
# Nel file .env
echo "NEURONPEDIA_API_KEY=your-key" >> .env

# Oppure come environment variable
export NEURONPEDIA_API_KEY="YOUR_KEY"
```

#### 2. OpenAI API Key (opzionale, solo per generazione concepts)
```bash
# Nel file .env
echo "OPENAI_API_KEY=your-key" >> .env

# Oppure come environment variable
export OPENAI_API_KEY="YOUR_KEY"
```

### Ottenere API Key Neuronpedia
1. Vai su https://www.neuronpedia.org
2. Login/Registrati
3. Settings → API Keys
4. Crea nuova key

---

## Workflow d'Uso

### 1. Preparazione Graph JSON

#### Opzione A: Scarica da Neuronpedia
```python
import requests
import json

model_id = "gemma-2-2b"
slug = "my-circuit"
url = f"https://www.neuronpedia.org/api/graph/{model_id}/{slug}"

response = requests.get(url)
graph_json = response.json()

with open("output/graph_data/my-circuit.json", "w") as f:
    json.dump(graph_json, f, indent=2)
```

#### Opzione B: Converti da `.pt` esistente
```python
from circuit_tracer.graph import Graph
import json

# Carica graph .pt
graph = Graph.from_pt("output/my_graph.pt")

# Estrai JSON (se disponibile)
# Nota: potrebbe richiedere modifiche al formato
```

### 2. Lancio Streamlit
```bash
streamlit run eda/app.py
```

### 3. Navigazione UI
1. **Carica Graph**: Seleziona JSON da file o API
2. **Filtra Features**: Scegli soglia cumulative influence (es: 95%)
   - Vedi quante features verranno processate
3. **Definisci Concepts**: 
   - Genera con OpenAI
   - O inserisci manualmente
4. **Esegui Analisi**: 
   - Controlla stima chiamate API
   - Avvia analisi
   - Monitora progress bar
5. **Esplora Risultati**: Filtra, visualizza, scarica CSV

---

## Esempio d'Uso Python

```python
from scripts.probe_prompts import analyze_concepts_from_graph_json
import json

# 1. Carica graph JSON
with open("output/graph_data/anthropological-circuit.json") as f:
    graph_json = json.load(f)

# 2. Definisci concepts
concepts = [
    {
        "label": "Artificial Intelligence",
        "category": "Technology",
        "description": "The simulation of human intelligence by machines"
    },
    {
        "label": "Neural Networks",
        "category": "ML Concept",
        "description": "Computing systems inspired by biological neural networks"
    }
]

# 3. Analizza (con filtraggio influence)
df = analyze_concepts_from_graph_json(
    graph_json=graph_json,
    concepts=concepts,
    api_key="YOUR_NEURONPEDIA_API_KEY",
    cumulative_contribution=0.95,  # Usa solo features che contribuiscono 95%
    use_baseline=True,              # Calcola metriche vs original prompt
    verbose=True,
    output_csv="output/results.csv"
)

# 4. Esplora risultati
print(df.head())

# Features con z-score più alto
top_features = df.nlargest(10, "z_score")
print(top_features[["z_score", "ratio_max_vs_original", "picco_su_label"]])

# Features che si attivano sul label
on_label = df[df["picco_su_label"] == True]
print(f"Features che si attivano sul label: {len(on_label)}")
```

---

## Colonne DataFrame Output

### Identificatori
- `label`: Label del concept
- `category`: Categoria del concept
- `layer`: Layer della feature
- `feature`: Index della feature

### Metriche Original Graph
- `attivazione_vecchio_prompt`: Attivazione nel prompt originale
- `original_position`: Posizione token nel prompt originale
- `influence`: Influence della feature nel graph

### Metriche New Prompt (sequenza completa)
- `nuova_somma_sequenza`: Somma attivazioni su tutta la sequenza
- `nuova_max_sequenza`: Max attivazione nella sequenza
- `nuova_media_sequenza`: Media attivazioni

### Metriche Label Span
- `nuova_somma_label_span`: Somma attivazioni sullo span del label
- `nuova_max_label_span`: Max attivazione nel label
- `nuova_media_label_span`: Media attivazioni nel label
- `nuova_l2_label_span`: L2 norm delle attivazioni nel label
- `picco_su_label`: Boolean, True se max è nel label
- `peak_token`: Token su cui si verifica il picco
- `peak_position`: Posizione del picco
- `label_span_start`: Indice inizio label
- `label_span_end`: Indice fine label

### Metriche Baseline (se `use_baseline=True`)
- `original_max`: Max attivazione nel prompt originale
- `original_density`: Densità attivazioni nel prompt originale
- `ratio_max_vs_original`: Ratio max nuovo / max originale
- `cosine_similarity`: Cosine similarity tra attivazioni

### Metriche Statistiche
- `z_score`: Z-score standard
- `z_score_robust`: Z-score robust (IQR-based)
- `z_score_log`: Z-score log-scaled
- `density_attivazione`: Densità attivazioni (> threshold)
- `normalized_sum_label`: Somma label / lunghezza label
- `normalized_sum_seq`: Somma sequenza / lunghezza sequenza
- `percentile_in_sequence`: Percentile del max nella sequenza

### Metadata
- `prompt`: Prompt completo usato ("label: description")
- `seq_len`: Lunghezza sequenza

---

## Performance e Costi

### Chiamate API
- **Per concept**: `num_features × 1` chiamate
- **Baseline** (opzionale): `num_features × 1` chiamate
- **Totale**: `num_features × (num_concepts + use_baseline)`

### Esempio
- Graph con 500 features
- Cumulative contribution 95% → ~150 features selezionate
- 5 concepts
- Baseline attivo

**Totale chiamate**: 150 × (5 + 1) = **900 chiamate**

**Tempo stimato**: 900 / 5 req/sec = **180 sec ≈ 3 minuti**

### Ottimizzazioni
1. **Filtraggio influence**: Riduci features processate (es: 95% → 150 features invece di 500)
2. **Disabilita baseline**: Se non servono metriche comparative
3. **Riduci concepts**: Analizza solo concepts più rilevanti

---

## Troubleshooting

### Errore: "❌ JSON manca 'metadata.scan' (model_id)"
**Causa**: Il JSON non è un graph valido di Neuronpedia.

**Soluzione**: Verifica che il JSON contenga:
```json
{
  "metadata": {
    "scan": "gemma-2-2b",
    "prompt": "...",
    ...
  },
  "nodes": [...]
}
```

### Errore: "⚠️ API Key Neuronpedia non configurata"
**Causa**: API key mancante.

**Soluzione**: Crea file `.neuronpedia_api_key` o imposta env var.

### Errore: HTTP 429 (Too Many Requests)
**Causa**: Rate limit superato.

**Soluzione**: Il rate limiting è già implementato (5 req/sec). Se persiste, attendi qualche minuto.

### Nessuna feature selezionata dopo filtraggio
**Causa**: Tutte le features hanno influence 0 o molto bassa.

**Soluzione**: Abbassa la soglia cumulative contribution (es: 80% invece di 95%).

### Progress bar bloccata
**Causa**: API call fallita senza propagare errore.

**Soluzione**: Controlla console Streamlit per log errori. Potrebbe essere:
- Timeout di rete
- Feature non esistente su Neuronpedia
- API key scaduta

---

## Compatibilità con Vecchia Versione

### Non più supportato
- ❌ `analyze_concepts(model, graph, concepts)` - rimosso
- ❌ Input: Graph `.pt` object
- ❌ Dipendenza da modello locale

### Come migrare codice esistente

#### Prima (v1.x)
```python
from scripts.probe_prompts import analyze_concepts
from circuit_tracer.graph import Graph
from circuit_tracer import ReplacementModel

model = ReplacementModel.from_pretrained("google/gemma-2-2b", "gemma")
graph = Graph.from_pt("output/my_graph.pt")

df = analyze_concepts(model, graph, concepts)
```

#### Dopo (v2.0)
```python
from scripts.probe_prompts import analyze_concepts_from_graph_json
import json

# 1. Converti .pt → JSON (una volta sola)
# Oppure scarica JSON da Neuronpedia API

with open("output/graph_data/my_graph.json") as f:
    graph_json = json.load(f)

df = analyze_concepts_from_graph_json(
    graph_json, 
    concepts, 
    api_key="YOUR_KEY",
    cumulative_contribution=0.95
)
```

---

## Prossimi Sviluppi

- [ ] Caching intelligente delle API calls
- [ ] Batch processing per ridurre latenza
- [ ] Export risultati in altri formati (Parquet, HDF5)
- [ ] Visualizzazioni interattive dei risultati
- [ ] Integrazione con altri provider di SAE

---

## Riferimenti

- **Neuronpedia API Docs**: https://www.neuronpedia.org/api-doc
- **Script originale**: `scripts/01_probe_prompts.py`
- **UI Streamlit**: `eda/pages/01_Probe_Prompts.py`
- **Esempio notebook**: (da creare)

---

**Versione**: 2.0.0  
**Data**: 2025-10-19  
**Autore**: AI Assistant (Cursor)

