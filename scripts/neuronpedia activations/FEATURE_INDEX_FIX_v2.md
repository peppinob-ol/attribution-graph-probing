# Fix Indici Feature v2: Nodi MLP Reconstruction Error

## Problema Identificato

Il file `selected_features (1).json` esportato da Streamlit conteneva indici errati come:
```json
{ "layer": 11, "index": 11 },
{ "layer": 12, "index": 12 },
{ "layer": 13, "index": 13 },
...
{ "layer": 25, "index": 25 }
```

Dove `index` era uguale a `layer`, il che è chiaramente sbagliato.

## Causa Root

I grafi `clt-hp` contengono **due tipi di nodi con formati `node_id` diversi**:

### 1. Nodi SAE (cross layer transcoder)
- **Formato**: `"layer_featureIndex_sequence"`
- **Esempio**: `"24_79427_7"` → layer=24, feature_index=79427
- **Parsing corretto**: `parts[1]` = feature index

### 2. Nodi MLP Reconstruction Error
- **Formato**: `"0_layer_sequence"`
- **Esempio**: `"0_11_5"` → layer=11 (memorizzato nel campo `layer`)
- **Parsing SBAGLIATO**: `parts[1]` = layer (11), NON feature index!

Il codice originale estraeva `parts[1]` per **tutti** i nodi, senza distinguere per tipo. Per i nodi MLP error, questo estraeva il layer invece del feature index.

## Soluzione Applicata

### File Modificati

1. **`eda/utils/graph_visualization.py`** (righe 49-74)
2. **`eda/pages/01_Probe_Prompts.py`** (righe 323-340)

### Logica Fix

```python
# PRIMA (SBAGLIATO) - estraeva parts[1] per tutti i nodi
if node_id and '_' in node_id:
    parts = node_id.split('_')
    feature_idx = int(parts[1])  # ❌ Errore per nodi MLP error!

# DOPO (CORRETTO) - estrae solo per nodi SAE
node_type = node.get('feature_type', '')

if node_type == 'cross layer transcoder':
    # Solo per nodi SAE: estrai feature_idx
    if node_id and '_' in node_id:
        parts = node_id.split('_')
        if len(parts) >= 2:
            feature_idx = int(parts[1])
    
    # Skip nodi SAE malformati
    if feature_idx is None:
        continue
else:
    # Per nodi non-SAE: usa -1 come placeholder
    feature_idx = -1
```

### Filtro Export

I nodi con `feature = -1` (non-SAE) vengono **automaticamente esclusi** dall'export tramite:

```python
is_error_filtered = scatter_filtered['feature'] == -1
sae_features_only = scatter_filtered[
    ~(is_embedding_filtered | is_logit_filtered | is_error_filtered)
]
```

## Risultato Atteso

Dopo il fix, il file `selected_features.json` esportato **NON** conterrà più:
- Nodi MLP reconstruction error
- Nodi embeddings
- Nodi logits
- Indici fasulli (layer == index)

Conterrà **solo** nodi SAE con `feature_index` correttamente estratti dal `node_id`.

### Esempio Prima vs Dopo

**Prima (SBAGLIATO)**:
```json
[
  {"layer": 11, "index": 11},  // ❌ MLP error node, index fasullo
  {"layer": 12, "index": 87969},  // ✅ SAE node, index corretto
  {"layer": 13, "index": 13},  // ❌ MLP error node, index fasullo
]
```

**Dopo (CORRETTO)**:
```json
[
  {"layer": 11, "index": 50131},  // ✅ Solo nodi SAE
  {"layer": 11, "index": 86199},  // ✅ con index corretti
  {"layer": 12, "index": 5597},
  {"layer": 12, "index": 27348},
  {"layer": 12, "index": 87969},
  {"layer": 13, "index": 16947},
  {"layer": 13, "index": 83324}
]
```

## Come Verificare il Fix

1. Avvia Streamlit:
   ```powershell
   .\start_streamlit.ps1
   ```

2. Vai su **Graph Generation** (http://localhost:8502/Graph_Generation)

3. Carica il grafo: `clt-hp-the-capital-of-201020250035-20251020-003525.json`

4. Clicca **"Download Features JSON"**

5. Verifica che:
   - ✅ NON ci siano più `{"layer": X, "index": X}`
   - ✅ Tutti gli `index` siano feature index validi (estratti da `node_id`)
   - ✅ Il numero di features sia ridotto (solo nodi SAE, no MLP error)

## Impatto

- ✅ **`batch_get_activations.py`** riceverà ora feature index corretti
- ✅ Le API Neuronpedia restituiranno le attivazioni giuste
- ✅ L'output `activations_dump.json` includerà tutte le feature richieste

## Nota Tecnica

Questo fix è **specifico per i grafi `clt-hp`** (Cross Layer Transcoders). Altri SAE set (es. `res-jb`) potrebbero avere formati diversi e richiedere adattamenti.

---

**Data Fix**: 21 Ottobre 2025  
**Issue**: Feature index extraction bug per nodi MLP reconstruction error  
**Status**: ✅ RISOLTO

