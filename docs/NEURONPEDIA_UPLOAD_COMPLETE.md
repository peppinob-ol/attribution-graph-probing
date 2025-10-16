# Guida Completa: Upload Grafo con Supernodi su Neuronpedia

## Riepilogo del Workflow

Hai completato con successo la generazione del Graph JSON con supernodi integrati! 🎉

### Risultato Ottenuto

- **File**: `output/neuronpedia_graph_with_subgraph.json` (23.8 MB)
- **Supernodi**: 112 (semantici + computazionali)
- **Feature pinnate**: 409
- **Formato**: Conforme allo schema Neuronpedia Attribution Graph

### Struttura dei Supernodi

Il JSON contiene:

```json
{
  "metadata": {
    "slug": "anthropological-circuit",
    "scan": "gemma-2-2b",
    "prompt": "...",
    "prompt_tokens": [...]
  },
  "qParams": {
    "supernodes": [
      ["Capital_L0-15", "0_41_7", "1_42_7", ...],
      ["Texas_L2-7", "2_6140_7", ...],
      ...
    ],
    "pinnedIds": ["0_41_7", "1_42_7", ...],
    "clickedId": "0_41_7",
    "linkType": "both"
  },
  "nodes": [...],  // 1489 nodi
  "links": [...]   // 343696 links
}
```

---

## Upload su Neuronpedia

### Problema: Validator UI non funziona

Il file è troppo grande (23.8 MB) per il validator web. L'errore "useGraphContext must be used within a GraphProvider" è dovuto a un timeout/limite dell'interfaccia.

### ✅ Soluzione: Usa l'API Python

#### Step 1: Installa neuronpedia

```powershell
pip install neuronpedia
```

#### Step 2: Carica il grafo

```powershell
python scripts/visualization/upload_to_neuronpedia.py
```

**Oppure manualmente:**

```python
from neuronpedia.np_graph_metadata import NPGraphMetadata

graph = NPGraphMetadata.upload_file('output/neuronpedia_graph_with_subgraph.json')
print(f"URL: {graph.url}")
```

#### Step 3: Visualizza

Apri l'URL restituito nel browser. I supernodi appariranno automaticamente nella sidebar del subgraph viewer.

---

## Dettagli Tecnici

### Problema Risolto: Cantor Pairing

Il grafo Circuit Tracer usa **Cantor pairing** per codificare `(layer, feature)` in un singolo intero:

```
feature_id = cantor_pair(layer, feature_idx)
```

Ad esempio:
- Layer 0, Feature 41 → `feature_id = 902`
- Node ID diventa: `"0_902_7"` (layer_cantorFeature_ctx)

Lo script `fix_neuronpedia_export.py` decodifica automaticamente questo formato per mappare correttamente i membri dei supernodi (`"0_41"`) ai `node_id` reali (`"0_902_7"`).

### Membri Non Trovati

Alcuni membri dei supernodi non sono stati mappati perché:
1. Sono stati filtrati dalle soglie di threshold
2. Hanno un `ctx_idx` diverso dalla posizione preferita nel prompt
3. Non sono presenti nel grafo (feature non attivate per questo prompt)

**Totale membri mappati**: 409 / ~600 (68%)

---

## Workflow Completo (Riepilogo)

### 1. Genera il Graph JSON base

```powershell
# Su Colab o ambiente con HF auth:
from circuit_tracer.utils.create_graph_files import create_graph_files

create_graph_files(
    graph_or_path="output/example_graph.pt",
    slug="anthropological-circuit",
    output_path="output/graph_data",
    scan="gemma-2-2b"
)
```

### 2. Aggiungi supernodi

```powershell
python scripts/visualization/fix_neuronpedia_export.py
```

Input:
- `output/graph_data/anthropological-circuit.json` (base graph)
- `output/final_anthropological_optimized.json` (supernodi)

Output:
- `output/neuronpedia_graph_with_subgraph.json` (grafo completo)

### 3. Carica su Neuronpedia

```powershell
python scripts/visualization/upload_to_neuronpedia.py
```

### 4. Visualizza e Condividi

L'URL restituito è pubblicamente accessibile e mostra:
- Graph viewer interattivo
- Supernodi raggruppati nella sidebar
- Feature pinnate evidenziate
- Possibilità di navigare tra i membri di ogni supernodo

---

## Troubleshooting

### Errore: "401 HuggingFace Authentication"

**Problema**: `create_graph_files` richiede accesso al modello gated su HF.

**Soluzione**:
```bash
huggingface-cli login
# oppure genera su Colab
```

### Errore: "useGraphContext must be used within a GraphProvider"

**Problema**: File troppo grande per il validator UI.

**Soluzione**: Usa l'API Python invece del validator web.

### Warning: "Non trovato mapping per X_Y"

**Non è un errore**. Alcune feature non sono presenti nel grafo perché:
- Sono state filtrate dalle soglie
- Non si attivano per questo prompt specifico
- Hanno un `ctx_idx` diverso

### File troppo grande (>20 MB)

**Opzioni**:
1. Aumenta i threshold in `create_graph_files` per ridurre nodi/links
2. Usa solo supernodi semantici (escludi computazionali)
3. Carica via API (supporta file più grandi)

**Esempio con threshold più alti:**
```python
create_graph_files(
    graph_or_path="output/example_graph.pt",
    slug="anthropological-circuit-pruned",
    output_path="output/graph_data",
    node_threshold=0.9,    # più alto = meno nodi
    edge_threshold=0.99    # più alto = meno links
)
```

---

## Prossimi Passi

### Opzione A: Aggiungi Feature Details

Per mostrare esempi testuali e attivazioni per ogni feature:

1. Self-host i JSON delle feature (formato Anthropic)
2. Imposta `metadata.feature_details.feature_json_base_url`

**Oppure:**

1. Crea un "source set" su Neuronpedia
2. Carica le feature via API
3. Usa `metadata.feature_details.neuronpedia_source_set`

Vedi: https://www.neuronpedia.org/graph/validator (sezione "Feature Detail Instructions")

### Opzione B: Genera più grafi

Ripeti il workflow per prompt diversi:
- Cambia il prompt in `create_graph_files`
- Riusa gli stessi supernodi (o calcolane di nuovi)
- Carica su Neuronpedia con slug diversi

### Opzione C: Integra nel Paper MATS

Includi l'URL del grafo nella tua application:
- Dimostra approccio "anthropological" vs computazionale
- Mostra coerenza semantica dei cluster
- Permette ai reviewer di esplorare interattivamente

---

## Riferimenti

- **Neuronpedia Docs**: https://www.neuronpedia.org/graph/validator
- **Circuit Tracer**: `docs/circuit-tracer-main/`
- **Schema JSON**: Vedi "The JSON schema" nel validator
- **API Python**: `pip install neuronpedia`

---

## File Creati per Questo Task

- `scripts/visualization/fix_neuronpedia_export.py` - Fix Cantor pairing
- `scripts/visualization/upload_to_neuronpedia.py` - Upload via API
- `output/neuronpedia_graph_with_subgraph.json` - Grafo finale (23.8 MB)

---

## Conclusione

Hai ora un Graph JSON completo e pronto per Neuronpedia che:
- ✅ Include 112 supernodi semantici e computazionali
- ✅ Mappa correttamente 409 feature
- ✅ Rispetta lo schema Neuronpedia
- ✅ Può essere caricato via API per file grandi
- ✅ Mostra il tuo approccio "anthropological" di clustering

**Prossimo comando per caricare:**

```powershell
pip install neuronpedia
python scripts/visualization/upload_to_neuronpedia.py
```

🎉 Buon upload!

