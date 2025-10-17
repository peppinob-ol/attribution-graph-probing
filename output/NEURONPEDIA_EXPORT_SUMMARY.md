# Summary: Export Neuronpedia con Supernodi

## Cosa è stato fatto

Ho creato un sistema completo per esportare il tuo lavoro su Neuronpedia con i supernodi già integrati, evitando URL troppo lunghi.

## File Creati

### 1. `scripts/visualization/%neuronpedia_export_clean.py`
Script principale che:
- Parte da `output/example_graph.pt`
- Genera (o riusa) un Graph JSON base
- Carica i tuoi supernodi da `output/final_anthropological_optimized.json`
- Mappa i membri (`layer_feature`) ai `node_id` reali nel grafo
- Crea `output/neuronpedia_graph_with_subgraph.json` con:
  - `qParams.supernodes`: [[nome, node_id, ...], ...]
  - `qParams.pinnedIds`: tutti i node_id dei supernodi
  - `qParams.clickedId`: primo nodo selezionato
  - `nodes[].clerp`: etichette dei supernodi sui nodi

### 2. `scripts/visualization/README_NEURONPEDIA_EXPORT.md`
Guida completa con:
- Istruzioni step-by-step
- Troubleshooting
- Opzioni per gestire autenticazione HuggingFace
- Esempi di personalizzazione

### 3. Aggiornamento `readme.md`
- Aggiunto Step 6 con istruzioni export Neuronpedia
- Link alla guida dettagliata

## Come Usarlo

### Metodo 1: Automatico (con Graph JSON già esistente)

Se hai già generato `output/graph_data/anthropological-circuit.json`:

```powershell
python scripts/visualization/neuronpedia_export_clean.py
```

Output: `output/neuronpedia_graph_with_subgraph.json`

### Metodo 2: Con Generazione da Colab

1. **Su Colab** (con HF auth):
```python
from circuit_tracer.utils.create_graph_files import create_graph_files

create_graph_files(
    graph_or_path="output/example_graph.pt",
    slug="anthropological-circuit",
    output_path="output/graph_data",
    scan="gemma-2-2b"
)
```

2. **Scarica** `output/graph_data/anthropological-circuit.json` e copialo in locale

3. **In locale**:
```powershell
python scripts/visualization/neuronpedia_export_clean.py
```

### Caricamento su Neuronpedia

**Opzione A - UI:**
1. https://www.neuronpedia.org/graph/validator
2. Carica `output/neuronpedia_graph_with_subgraph.json`
3. Valida e upload

**Opzione B - API:**
```python
from neuronpedia.np_graph_metadata import NPGraphMetadata

graph = NPGraphMetadata.upload_file('output/neuronpedia_graph_with_subgraph.json')
print(graph.url)  # Apri nel browser
```

## Vantaggi

✅ **No URL lunghi**: tutto in un file JSON  
✅ **Supernodi integrati**: appaiono automaticamente nell'UI  
✅ **Mapping automatico**: converte `layer_feature` → `node_id`  
✅ **Etichette sui nodi**: `clerp` mostra il nome del supernodo  
✅ **Riutilizzabile**: salva il JSON per condivisione  

## Struttura Output

```json
{
  "metadata": {
    "slug": "anthropological-circuit",
    "scan": "gemma-2-2b",
    "prompt": "The capital of state containing Dallas is",
    "prompt_tokens": ["The", " capital", ...]
  },
  "qParams": {
    "supernodes": [
      ["Capital_L10-16", "10_2257_6", "12_12493_6", ...],
      ["Texas_L4-7", "4_14857_5", "5_11299_5", ...],
      ...
    ],
    "pinnedIds": ["10_2257_6", "12_12493_6", ...],
    "clickedId": "10_2257_6",
    "linkType": "both"
  },
  "nodes": [
    {
      "node_id": "10_2257_6",
      "feature": 2257,
      "layer": 10,
      "ctx_idx": 6,
      "clerp": "Capital_L10-16",
      ...
    },
    ...
  ],
  "links": [...]
}
```

## Prossimi Passi

1. **Test del workflow completo**:
   - Genera il Graph JSON base (Colab o locale con HF auth)
   - Esegui lo script export
   - Carica su Neuronpedia
   - Verifica che i supernodi appaiano correttamente

2. **Se vuoi testi/esempi per feature** (opzionale):
   - Aggiungi `metadata.feature_details.feature_json_base_url` (self-host)
   - O usa `metadata.feature_details.neuronpedia_source_set` (carica via API)
   - Schema: https://www.neuronpedia.org/graph/validator

3. **Personalizzazione**:
   - Modifica `slug` per identificatori custom
   - Filtra supernodi (solo semantici/computazionali)
   - Ajusta `node_threshold` / `edge_threshold`

## Riferimenti

- **Schema Graph JSON**: https://www.neuronpedia.org/graph/validator
- **Circuit Tracer**: https://github.com/safety-research/circuit-tracer
- **Neuronpedia API**: https://pypi.org/project/neuronpedia/
- **Guida dettagliata**: `scripts/visualization/README_NEURONPEDIA_EXPORT.md`



