# Export Neuronpedia con Supernodi

Script per esportare il grafo da `.pt` a Graph JSON con supernodi integrati, pronto per caricamento su Neuronpedia.

## Utilizzo Rapido

```powershell
python scripts/visualization/neuronpedia_export_clean.py
```

## Requisiti

1. **File .pt**: `output/example_graph.pt` (generato da Circuit Tracer)
2. **Supernodi**: `output/final_anthropological_optimized.json`
3. **Personalities**: `output/feature_personalities_corrected.json`
4. **Graph JSON base** (una delle opzioni):
   - Opzione A: Generalo localmente con autenticazione HF
   - Opzione B: Generalo su Colab e copialo in `output/graph_data/anthropological-circuit.json`

## Workflow Completo

### Step 1: Genera Graph JSON base (se necessario)

**Opzione A - Locale con HF auth:**
```bash
huggingface-cli login
python scripts/visualization/neuronpedia_export_clean.py
```

**Opzione B - Da Colab:**
```python
# Su Colab (con autenticazione HF già configurata)
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

### Step 2: Aggiungi Supernodi

Una volta che hai il Graph JSON base:

```powershell
python scripts/visualization/neuronpedia_export_clean.py
```

Questo script:
1. Cerca `output/graph_data/anthropological-circuit.json` (o lo genera se manca)
2. Carica i tuoi supernodi da `output/final_anthropological_optimized.json`
3. Mappa i membri (`layer_feature`) ai `node_id` reali del grafo
4. Crea `output/neuronpedia_graph_with_subgraph.json` con:
   - `qParams.supernodes`: i tuoi grouping
   - `qParams.pinnedIds`: tutte le feature dei supernodi
   - `qParams.clickedId`: primo nodo selezionato
   - `nodes[].clerp`: etichette dei supernodi sui nodi

### Step 3: Carica su Neuronpedia

**Opzione A - Validator UI:**
1. Vai su https://www.neuronpedia.org/graph/validator
2. Carica `output/neuronpedia_graph_with_subgraph.json`
3. Clicca "Validate JSON" e poi "Upload"

**Opzione B - Python API:**
```python
from neuronpedia.np_graph_metadata import NPGraphMetadata

graph_meta = NPGraphMetadata.upload_file('output/neuronpedia_graph_with_subgraph.json')
print(graph_meta.url)  # Apri questo URL nel browser
```

## Output

Il file generato `output/neuronpedia_graph_with_subgraph.json` contiene:

- **metadata**: slug, scan (model), prompt, prompt_tokens
- **qParams**: 
  - `supernodes`: [[nome, node_id1, node_id2, ...], ...]
  - `pinnedIds`: [node_id1, node_id2, ...]
  - `clickedId`: primo nodo
- **nodes**: lista nodi con `clerp` (label) aggiunta
- **links**: collegamenti causali

## Personalizzazione

Per modificare i parametri, edita lo script o chiamalo da Python:

```python
# Usa direttamente fix_neuronpedia_export.py
# Modifica i parametri all'interno dello script se necessario
python scripts/visualization/fix_neuronpedia_export.py
```

## Troubleshooting

### Errore "Cannot access gated repo"
- **Causa**: Tokenizer di HuggingFace non autenticato
- **Soluzione 1**: `huggingface-cli login` prima di eseguire
- **Soluzione 2**: Genera il Graph JSON base su Colab e copialo localmente

### Errore "Graph JSON non trovato"
- **Causa**: Il Graph JSON base non esiste
- **Soluzione**: Vedi Step 1 sopra per generarlo

### Supernodi vuoti o mancanti
- **Causa**: Mismatch tra membri e `node_id` nel grafo
- **Verifica**: I membri in `final_anthropological_optimized.json` sono nel formato `layer_feature` (es. `"10_2257"`)
- **Soluzione**: Lo script mappa automaticamente a `node_id` (`layer_feature_ctx`) usando l'ultimo token del prompt

### UnicodeEncodeError su Windows
```powershell
$env:PYTHONIOENCODING='utf-8'
python scripts/visualization/neuronpedia_export_clean.py
```

## Riferimenti

- Schema Graph JSON: https://www.neuronpedia.org/graph/validator
- Circuit Tracer: https://github.com/safety-research/circuit-tracer
- Neuronpedia API: https://pypi.org/project/neuronpedia/



