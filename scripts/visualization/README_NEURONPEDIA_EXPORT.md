# Export Neuronpedia - Pipeline Antropologica

Esporta il grafo con supernodi dalla pipeline antropologica su Neuronpedia per visualizzazione interattiva.

## 🎯 Workflow Completo

### Step 1: Esegui la Pipeline Antropologica

Prima di tutto, esegui la pipeline completa per generare i supernodi:

```powershell
# 1. Analisi antropologica base (con metriche causali)
python scripts/02_anthropological_basic.py

# 2. Calcolo soglie robuste
python scripts/03_compute_thresholds.py

# 3. Costruzione supernodi Cicciotti (backward from logit)
python scripts/04_cicciotti_supernodes.py

# 4. Clustering finale ottimizzato
python scripts/05_final_optimized_clustering.py
```

**Output**: `output/final_anthropological_optimized.json` con supernodi semantici e computazionali.

### Step 2: Genera Graph JSON Base

Il Graph JSON base contiene nodi e link del grafo causale. Devi generarlo usando `circuit-tracer`.

#### Opzione A - Locale (richiede autenticazione HuggingFace)

```bash
# Autentica HuggingFace
huggingface-cli login

# Genera il grafo
python -c "
from circuit_tracer.utils.create_graph_files import create_graph_files

create_graph_files(
    graph_or_path='output/example_graph.pt',
    slug='anthropological-circuit',
    output_path='output/graph_data',
    scan='gemma-2-2b',
    node_threshold=0.8,
    edge_threshold=0.98
)
"
```

#### Opzione B - Da Colab (consigliato)

Su Google Colab (con autenticazione HF già configurata):

```python
from circuit_tracer.utils.create_graph_files import create_graph_files

create_graph_files(
    graph_or_path="output/example_graph.pt",
    slug="anthropological-circuit",
    output_path="output/graph_data",
    scan="gemma-2-2b",
    node_threshold=0.8,
    edge_threshold=0.98
)

# Scarica il file generato: output/graph_data/anthropological-circuit.json
# Copialo nella stessa cartella in locale
```

### Step 3: Aggiungi Supernodi al Grafo

```powershell
python scripts/visualization/fix_neuronpedia_export.py
```

Questo script:
1. Carica il Graph JSON base da `output/graph_data/anthropological-circuit.json`
2. Carica i supernodi da `output/final_anthropological_optimized.json` (dalla pipeline 01→04)
3. Mappa i membri dei supernodi (`layer_feature`) ai `node_id` reali del grafo
4. Crea `output/neuronpedia_graph_with_subgraph.json` con:
   - `qParams.supernodes`: array di supernodi (semantici + computazionali)
   - `qParams.pinnedIds`: tutte le feature evidenziate
   - `qParams.clickedId`: primo nodo selezionato
   - `nodes[].clerp`: etichette dei supernodi sui nodi

**Output**: `output/neuronpedia_graph_with_subgraph.json` (~20-25 MB)

### Step 4: Upload su Neuronpedia

#### Configura API Key

Crea un file `.env` nella root del progetto:

```
NEURONPEDIA_API_KEY=tua_chiave_api_qui
```

#### Upload

```powershell
python scripts/visualization/upload_to_neuronpedia.py
```

Lo script carica il file e restituisce l'URL del grafo. Apri l'URL nel browser per visualizzare!

## 📦 Struttura Output

Il file `neuronpedia_graph_with_subgraph.json` contiene:

```json
{
  "metadata": {
    "slug": "anthropological-circuit",
    "scan": "gemma-2-2b",
    "prompt": "The capital of...",
    "prompt_tokens": [...]
  },
  "qParams": {
    "supernodes": [
      ["CICCIOTTO_1", "node_id_1", "node_id_2", ...],
      ["COMP_5", "node_id_10", "node_id_11", ...],
      ...
    ],
    "pinnedIds": ["node_id_1", "node_id_2", ...],
    "clickedId": "node_id_1",
    "linkType": "both"
  },
  "nodes": [
    {
      "node_id": "20_15589_7",
      "layer": 20,
      "feature": 15589,
      "ctx_idx": 7,
      "clerp": "CICCIOTTO_1",  // ← Etichetta supernodo
      ...
    },
    ...
  ],
  "links": [...]
}
```

## 🔧 Parametri Personalizzabili

### In `fix_neuronpedia_export.py`

- `input_json`: Path al Graph JSON base (default: `output/graph_data/anthropological-circuit.json`)
- `supernodes_file`: Path ai supernodi finali (default: `output/final_anthropological_optimized.json`)
- `output_json`: Path output (default: `output/neuronpedia_graph_with_subgraph.json`)

### In `create_graph_files` (Step 2)

- `node_threshold`: Soglia per includere nodi (default: 0.8)
- `edge_threshold`: Soglia per includere edge (default: 0.98)
- Valori più alti → grafo più piccolo ma meno completo
- Valori più bassi → grafo più grande e dettagliato

## 🐛 Troubleshooting

### ❌ "Graph JSON base non trovato"

**Causa**: Non hai generato il Graph JSON base (Step 2)

**Soluzione**: Esegui Step 2 (Opzione A o B)

### ❌ "Cannot access gated repo"

**Causa**: Tokenizer HuggingFace non autenticato

**Soluzione**: 
- `huggingface-cli login`
- Oppure usa Opzione B (Colab)

### ❌ "Supernodi vuoti o mancanti"

**Causa**: Mismatch tra formato membri e node_id nel grafo

**Verifica**:
- I membri in `final_anthropological_optimized.json` sono nel formato `"layer_feature"` (es. `"10_2257"`)
- Lo script mappa automaticamente a `node_id` nel formato `"layer_feature_ctx"` (es. `"10_2257_7"`)

**Soluzione**: Lo script gestisce automaticamente Cantor pairing e formati diversi

### ❌ "NEURONPEDIA_API_KEY non trovata"

**Causa**: File `.env` mancante o chiave non configurata

**Soluzione**: Crea `.env` nella root con `NEURONPEDIA_API_KEY=tua_chiave`

### ❌ "Upload fallito"

**Possibili cause**:
1. File JSON troppo grande (>50MB)
   - Soluzione: Aumenta `node_threshold` e `edge_threshold` in Step 2
2. JSON non valido
   - Soluzione: Valida su https://www.neuronpedia.org/graph/validator
3. Problema di rete
   - Soluzione: Riprova o usa una connessione più stabile

### ⚠️ UnicodeEncodeError su Windows

```powershell
$env:PYTHONIOENCODING='utf-8'
python scripts/visualization/fix_neuronpedia_export.py
```

## 📚 Riferimenti

- **Schema Graph JSON**: https://www.neuronpedia.org/graph/validator
- **Circuit Tracer**: https://github.com/safety-research/circuit-tracer
- **Neuronpedia API**: https://pypi.org/project/neuronpedia/
- **Pipeline Antropologica**: Vedi `readme.md` nella root del progetto

## 💡 Tips

1. **Riduci dimensione grafo**: Se l'upload fallisce per file troppo grande, aumenta `node_threshold` (es. 0.85) e `edge_threshold` (es. 0.99) quando generi il Graph JSON base.

2. **Test locale**: Prima di uploadare, valida il JSON su https://www.neuronpedia.org/graph/validator

3. **Iterazioni**: Puoi rigenerare il Graph JSON con soglie diverse senza rieseguire la pipeline antropologica (Step 1).

4. **Backup**: Il file `neuronpedia_graph_with_subgraph.json` è riutilizzabile. Salvalo se vuoi rifare l'upload senza rigenerarlo.
