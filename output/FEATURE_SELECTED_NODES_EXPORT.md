# Feature: Export Selected Nodes per Upload Subgraph Accurato

**Data**: 2025-10-26  
**Status**: ✅ Implementato  

---

## Problema Risolto

### Problema Originale

Quando si caricava il subgrafo su Neuronpedia, venivano pinnati **322 nodi** invece dei **~50 nodi** effettivamente selezionati con lo slider in Graph Generation.

**Causa**: Il sistema usava **TUTTI** i `node_id` del Graph JSON che matchavano le feature nei supernodes, invece di usare solo il subset selezionato con lo slider.

### Esempio

```
Graph JSON originale: 322 nodi totali
  - Feature 0_12284: 15 nodi (0_12284_1, 0_12284_2, ..., 0_12284_15)
  - Feature 20_44686: 8 nodi (20_44686_1, 20_44686_2, ..., 20_44686_8)
  - ...

Slider cumulative_influence = 0.5
  → Seleziona 50 nodi (subset)
  → Estrae 43 feature uniche

Probe Prompts
  → Usa le 43 feature

Node Grouping
  → 13 supernodes

Upload Neuronpedia (PRIMA)
  → Pinna TUTTI i 322 nodi ❌

Upload Neuronpedia (DOPO)
  → Pinna solo i 50 nodi selezionati ✅
```

---

## Soluzione Implementata

### Step 1: Export Completo in Graph Generation

Modificato `eda/pages/00_Graph_Generation.py` per esportare **sia features che node_ids**:

**Prima** (solo features):
```json
[
  {"layer": 0, "index": 12284},
  {"layer": 20, "index": 44686}
]
```

**Dopo** (features + node_ids):
```json
{
  "features": [
    {"layer": 0, "index": 12284},
    {"layer": 20, "index": 44686}
  ],
  "node_ids": [
    "0_12284_1",
    "0_12284_3",
    "20_44686_2",
    "20_44686_5"
  ],
  "metadata": {
    "n_features": 2,
    "n_nodes": 4,
    "cumulative_threshold": 0.5,
    "exported_at": "2025-10-26T12:34:56"
  }
}
```

### Step 2: Caricamento in Node Grouping

Aggiunto file uploader in `eda/pages/02_Node_Grouping.py`:

```python
uploaded_nodes_json = st.sidebar.file_uploader(
    "Selected Nodes JSON (opzionale)",
    type=["json"],
    help="File JSON con node_ids selezionati da Graph Generation (per upload subgraph accurato)"
)
```

Caricamento e salvataggio in session state:

```python
selected_nodes_data = None
if nodes_json_to_use:
    try:
        selected_nodes_data = json.load(nodes_json_to_use)
        st.session_state['selected_nodes_data'] = selected_nodes_data
        
        metadata = selected_nodes_data.get('metadata', {})
        n_nodes = metadata.get('n_nodes', len(selected_nodes_data.get('node_ids', [])))
        n_features = metadata.get('n_features', len(selected_nodes_data.get('features', [])))
        
        st.success(f"✅ Selected Nodes JSON caricato: {n_features} features, {n_nodes} nodi")
    except Exception as e:
        st.warning(f"⚠️ Errore caricamento Selected Nodes JSON: {e}")
```

### Step 3: Uso in Upload Subgraph

Modificato `upload_subgraph_to_neuronpedia()` in `scripts/02_node_grouping.py`:

**Nuova signature**:
```python
def upload_subgraph_to_neuronpedia(
    df_grouped: pd.DataFrame,
    graph_json_path: str,
    api_key: str,
    display_name: Optional[str] = None,
    overwrite_id: Optional[str] = None,
    selected_nodes_data: Optional[Dict[str, Any]] = None,  # ← NUOVO!
    verbose: bool = True
) -> Dict[str, Any]:
```

**Logica pinnedIds**:
```python
if selected_nodes_data and 'node_ids' in selected_nodes_data:
    # Usa il subset di node_ids selezionati in Graph Generation
    all_selected_node_ids = selected_nodes_data['node_ids']
    
    # Filtra solo quelli che appartengono alle feature nei supernodes
    feature_keys_in_supernodes = set(feature_to_supernode.keys())
    pinned_ids = []
    
    for node_id in all_selected_node_ids:
        # Estrai feature_key da node_id (es. "0_12284_1" -> "0_12284")
        parts = node_id.split('_')
        if len(parts) >= 2:
            feature_key = f"{parts[0]}_{parts[1]}"
            if feature_key in feature_keys_in_supernodes:
                pinned_ids.append(node_id)
    
    print(f"PinnedIds: {len(pinned_ids)} nodi (da selected_nodes_data)")
else:
    # Fallback: usa tutti i node_id che sono nei supernodes
    pinned_ids = []
    for supernode in supernodes:
        pinned_ids.extend(supernode[1:])
    
    print(f"⚠️ WARNING: selected_nodes_data non fornito, usando tutti i nodi del grafo")
```

**Chiamata in Streamlit**:
```python
# Recupera selected_nodes_data da session state
selected_nodes_data = st.session_state.get('selected_nodes_data')

result = upload_subgraph_to_neuronpedia(
    df_grouped=df_named,
    graph_json_path=graph_path,
    api_key=api_key,
    display_name=display_name,
    overwrite_id=overwrite_id,
    selected_nodes_data=selected_nodes_data,  # ← Passa il dato!
    verbose=False
)
```

---

## Workflow Completo

### 1. Graph Generation

```
1. Carica Graph JSON
2. Usa slider cumulative_influence per filtrare nodi
3. Scatter plot mostra nodi filtrati
4. Esporta:
   - "Download Features + Nodes JSON" → selected_features_with_nodes.json ✅
   - "Download Features JSON (legacy)" → selected_features.json (solo per batch_get_activations)
```

### 2. Probe Prompts

```
1. Carica selected_features.json (o usa solo "features" da selected_features_with_nodes.json)
2. Genera probe prompts
3. Misura attivazioni
4. Esporta CSV
```

### 3. Node Grouping

```
1. Carica CSV Export
2. Carica Graph JSON
3. Carica Selected Nodes JSON (selected_features_with_nodes.json) ← NUOVO!
4. Esegui Step 1, 2, 3
5. Upload su Neuronpedia
   → Usa node_ids da Selected Nodes JSON ✅
```

---

## Formato File

### `selected_features_with_nodes.json`

```json
{
  "features": [
    {"layer": 0, "index": 12284},
    {"layer": 0, "index": 19204},
    {"layer": 20, "index": 44686},
    {"layer": 7, "index": 3144}
  ],
  "node_ids": [
    "0_12284_1",
    "0_12284_3",
    "0_19204_2",
    "20_44686_2",
    "20_44686_5",
    "7_3144_1"
  ],
  "metadata": {
    "n_features": 4,
    "n_nodes": 6,
    "cumulative_threshold": 0.5,
    "exported_at": "2025-10-26T12:34:56.789Z"
  }
}
```

**Nota**: Un feature può avere multipli `node_id` (uno per ogni `ctx_idx` dove appare nel prompt).

---

## Esempio Pratico

### Scenario

- Graph JSON: 322 nodi totali
- Slider: cumulative_influence ≤ 0.5
- Nodi selezionati: 50
- Feature uniche: 43
- Supernodes: 13

### Prima del Fix

```
pinnedIds: [tutti i 322 node_id del grafo] ❌

Risultato su Neuronpedia:
  - 13 supernodes ✅
  - 322 pinned nodes ❌ (troppi!)
```

### Dopo il Fix

```
pinnedIds: [solo i 50 node_id selezionati con lo slider] ✅

Risultato su Neuronpedia:
  - 13 supernodes ✅
  - 50 pinned nodes ✅ (corretto!)
```

---

## Fallback per File Esistenti

Se `selected_nodes_data` non è fornito (file vecchi senza `node_ids`):

```python
# Fallback: usa tutti i node_id che sono nei supernodes
pinned_ids = []
for supernode in supernodes:
    pinned_ids.extend(supernode[1:])

print("⚠️ WARNING: selected_nodes_data non fornito, usando tutti i nodi del grafo")
```

**Comportamento**: Funziona come prima (pinna tutti i nodi), ma mostra un warning.

---

## UI Changes

### Graph Generation (`00_Graph_Generation.py`)

**Prima**:
```
📥 Esporta Feature Selezionate
  Features Uniche: 43
  Layer Unici: 10
  
  [⬇️ Download Features JSON]
```

**Dopo**:
```
📥 Esporta Feature Selezionate
  Features Uniche: 43
  Nodi Selezionati: 50  ← NUOVO!
  Layer Unici: 10
  
  [⬇️ Download Features + Nodes JSON]  ← NUOVO! (formato completo)
  [⬇️ Download Features JSON (legacy)]  (solo features)
```

### Node Grouping (`02_Node_Grouping.py`)

**Sidebar - Input Files**:
```
📁 Input Files
  CSV Export (richiesto): [file uploader]
  JSON Attivazioni (opzionale): [file uploader]
  Graph JSON (opzionale): [file uploader]
  Selected Nodes JSON (opzionale): [file uploader]  ← NUOVO!
```

**Quando caricato**:
```
✅ Selected Nodes JSON caricato: 43 features, 50 nodi
```

---

## Testing

### Test 1: Con Selected Nodes JSON

1. Graph Generation:
   - Slider cumulative_influence = 0.5
   - Download "Features + Nodes JSON"
2. Node Grouping:
   - Carica CSV, Graph JSON, Selected Nodes JSON
   - Esegui Step 1, 2, 3
   - Upload su Neuronpedia
3. Verifica su Neuronpedia:
   - Numero di pinned nodes = numero di nodi in Selected Nodes JSON ✅

### Test 2: Senza Selected Nodes JSON (Fallback)

1. Node Grouping:
   - Carica CSV, Graph JSON (NO Selected Nodes JSON)
   - Esegui Step 1, 2, 3
   - Upload su Neuronpedia
2. Verifica console:
   - Warning: "selected_nodes_data non fornito" ✅
3. Verifica su Neuronpedia:
   - Numero di pinned nodes = tutti i nodi del grafo (comportamento vecchio) ✅

### Test 3: Formato Legacy (solo features)

1. Graph Generation:
   - Download "Features JSON (legacy)"
2. Probe Prompts:
   - Usa features.json (funziona come prima) ✅

---

## Edge Cases

### Caso 1: Node ID non nel Graph JSON

```python
for node_id in all_selected_node_ids:
    parts = node_id.split('_')
    if len(parts) >= 2:  # ← Controlla formato valido
        feature_key = f"{parts[0]}_{parts[1]}"
        if feature_key in feature_keys_in_supernodes:  # ← Controlla se nei supernodes
            pinned_ids.append(node_id)
```

**Comportamento**: Node ID ignorato se formato invalido o feature non nei supernodes.

### Caso 2: Selected Nodes JSON Malformato

```python
try:
    selected_nodes_data = json.load(nodes_json_to_use)
    st.session_state['selected_nodes_data'] = selected_nodes_data
except Exception as e:
    st.warning(f"⚠️ Errore caricamento Selected Nodes JSON: {e}")
```

**Comportamento**: Warning mostrato, fallback a comportamento vecchio.

### Caso 3: Metadata Mancante

```python
metadata = selected_nodes_data.get('metadata', {})
n_nodes = metadata.get('n_nodes', len(selected_nodes_data.get('node_ids', [])))
n_features = metadata.get('n_features', len(selected_nodes_data.get('features', [])))
```

**Comportamento**: Calcola n_nodes e n_features dalla lunghezza degli array.

---

## Benefici

1. ✅ **Upload Accurato**: Solo i nodi selezionati vengono pinnati
2. ✅ **Visualizzazione Pulita**: Neuronpedia mostra solo il subset rilevante
3. ✅ **Backward Compatible**: Funziona anche senza Selected Nodes JSON (fallback)
4. ✅ **Metadata Ricco**: Timestamp, threshold, conteggi nel JSON
5. ✅ **Doppio Export**: Formato completo + legacy per compatibilità

---

## Conclusione

Il sistema ora supporta un workflow end-to-end accurato:

1. ✅ **Graph Generation**: Esporta features + node_ids selezionati
2. ✅ **Probe Prompts**: Usa features (compatibile con entrambi i formati)
3. ✅ **Node Grouping**: Carica e usa node_ids per upload accurato
4. ✅ **Upload Neuronpedia**: Pinna solo i nodi selezionati

**Risultato**: Subgraph su Neuronpedia con il numero corretto di nodi pinnati! 🎉

