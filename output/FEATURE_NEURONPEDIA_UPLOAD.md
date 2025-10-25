# Feature: Upload Subgrafo su Neuronpedia

**Data**: 2025-10-25  
**Status**: ✅ Implementato  

---

## Descrizione

Implementata la funzionalità per caricare il subgrafo con i supernodes su Neuronpedia, permettendo la visualizzazione interattiva del grafo raggruppato.

### Componenti

1. **`scripts/02_node_grouping.py`**: Funzione `upload_subgraph_to_neuronpedia()`
2. **`eda/pages/02_Node_Grouping.py`**: Interfaccia Streamlit per l'upload

---

## Funzione: `upload_subgraph_to_neuronpedia()`

### Signature

```python
def upload_subgraph_to_neuronpedia(
    df_grouped: pd.DataFrame,
    graph_json_path: str,
    api_key: str,
    display_name: Optional[str] = None,
    overwrite_id: Optional[str] = None,
    verbose: bool = True
) -> Dict[str, Any]:
```

### Parametri

- **`df_grouped`**: DataFrame con colonna `supernode_name` (output di `name_nodes()`)
- **`graph_json_path`**: Path al Graph JSON originale
- **`api_key`**: API key di Neuronpedia (richiesta per l'upload)
- **`display_name`**: Nome visualizzato per il subgrafo (opzionale, default: `"{slug} (grouped)"`)
- **`overwrite_id`**: ID del subgrafo da sovrascrivere (opzionale, se vuoto crea nuovo subgrafo)
- **`verbose`**: Stampa info dettagliate

### Returns

Response JSON da Neuronpedia API (contiene URL del subgrafo, ID, ecc.)

---

## Logica di Funzionamento

### Step 1: Carica Graph JSON

```python
with open(graph_json_path, 'r', encoding='utf-8') as f:
    graph_json = json.load(f)

metadata = graph_json.get('metadata', {})
slug = metadata.get('slug', 'unknown')
model_id = metadata.get('scan', 'gemma-2-2b')
nodes = graph_json.get('nodes', [])
q_params = graph_json.get('qParams', {})
```

**Estrae**:
- `slug`: Identificatore del grafo originale
- `model_id`: Modello (es. "gemma-2-2b")
- `nodes`: Lista di nodi del grafo
- `qParams`: Parametri query (pinnedIds, ecc.)

### Step 2: Crea Mapping `node_id` → `feature_key`

```python
node_id_to_feature = {}
for node in nodes:
    node_id = node.get('node_id', '')  # es. "0_12284_1"
    parts = node_id.split('_')
    if len(parts) >= 2:
        layer = parts[0]    # "0"
        feature = parts[1]  # "12284"
        feature_key = f"{layer}_{feature}"  # "0_12284"
        node_id_to_feature[node_id] = feature_key
```

**Formato `node_id`**: `"layer_feature_ctx_idx"` (es. `"0_12284_1"`)  
**Formato `feature_key`**: `"layer_feature"` (es. `"0_12284"`)

### Step 3: Crea Mapping `feature_key` → `supernode_name`

```python
feature_to_supernode = df_grouped.groupby('feature_key')['supernode_name'].first().to_dict()

# Esempio:
# {
#   "0_12284": "The",
#   "20_44686": "Texas",
#   "7_3144": "Austin",
#   "1_12928": "(Texas) related"
# }
```

### Step 4: Raggruppa `node_id` per `supernode_name`

```python
supernode_groups = {}  # {supernode_name: [node_ids]}

for node_id, feature_key in node_id_to_feature.items():
    supernode_name = feature_to_supernode.get(feature_key)
    if supernode_name:
        if supernode_name not in supernode_groups:
            supernode_groups[supernode_name] = []
        supernode_groups[supernode_name].append(node_id)

# Esempio:
# {
#   "Texas": ["20_44686_1", "20_44686_2", "20_44686_3"],
#   "Austin": ["7_3144_1", "7_3144_2"],
#   "(Texas) related": ["1_12928_1", "1_12928_2", "1_12928_3"]
# }
```

### Step 5: Converti in Formato Neuronpedia

```python
supernodes = []
for supernode_name, node_ids in supernode_groups.items():
    if len(node_ids) > 0:
        supernodes.append([supernode_name] + node_ids)

# Formato Neuronpedia: [["supernode_name", "node_id1", "node_id2", ...], ...]
# Esempio:
# [
#   ["Texas", "20_44686_1", "20_44686_2", "20_44686_3"],
#   ["Austin", "7_3144_1", "7_3144_2"],
#   ["(Texas) related", "1_12928_1", "1_12928_2", "1_12928_3"]
# ]
```

### Step 6: Prepara Payload

```python
payload = {
    "modelId": model_id,                    # "gemma-2-2b"
    "slug": slug,                           # "clt-hp-the-capital-of-..."
    "displayName": display_name,            # "Node Grouping - 2025-10-25"
    "pinnedIds": pinned_ids,                # Tutti i node_id (o da qParams)
    "supernodes": supernodes,               # [["name", "id1", "id2"], ...]
    "clerps": [],                           # Non gestito per ora
    "pruningThreshold": pruning_threshold,  # 0.8 (da metadata)
    "densityThreshold": density_threshold,  # 0.99 (default)
    "overwriteId": overwrite_id or ""       # "" = nuovo, altrimenti sovrascrive
}
```

### Step 7: Upload via API

```python
response = requests.post(
    "https://www.neuronpedia.org/api/graph/subgraph/save",
    headers={
        "Content-Type": "application/json",
        "x-api-key": api_key
    },
    json=payload,
    timeout=30
)

response.raise_for_status()
result = response.json()
```

**Response** (esempio):
```json
{
  "success": true,
  "id": "abc123",
  "url": "https://neuronpedia.org/gemma-2-2b/subgraph/abc123"
}
```

---

## Interfaccia Streamlit

### Posizione

Alla fine della pagina `eda/pages/02_Node_Grouping.py`, dopo "💾 Download Risultati".

### Componenti

1. **API Key Input**:
   ```python
   api_key = st.text_input(
       "API Key Neuronpedia",
       type="password",
       help="Inserisci la tua API key di Neuronpedia (richiesta per l'upload)"
   )
   ```

2. **Display Name Input**:
   ```python
   display_name = st.text_input(
       "Display Name",
       value=f"Node Grouping - {datetime.now().strftime('%Y-%m-%d %H:%M')}",
       help="Nome visualizzato per il subgrafo su Neuronpedia"
   )
   ```

3. **Overwrite ID Input** (opzionale):
   ```python
   overwrite_id = st.text_input(
       "Overwrite ID (opzionale)",
       value="",
       help="Se fornito, sovrascrive un subgrafo esistente invece di crearne uno nuovo"
   )
   ```

4. **Bottone Upload**:
   ```python
   if st.button("🚀 Upload su Neuronpedia", disabled=not (api_key and graph_json_available)):
       # ... upload logic ...
   ```

### Validazioni

- ✅ API Key richiesta
- ✅ Graph JSON deve essere caricato
- ✅ Bottone disabilitato se mancano requisiti
- ✅ Warning se Graph JSON non disponibile

### Feedback

- **Spinner** durante upload: `"Uploading su Neuronpedia..."`
- **Success**: `"✅ Upload completato!"` + JSON response
- **Link**: Se disponibile nella response, mostra link al subgrafo
- **Error**: Mostra errore + traceback

---

## Esempio di Utilizzo

### Da CLI (Script)

```bash
python scripts/02_node_grouping.py \
  --input output/2025-10-21T07-40_export.csv \
  --output output/2025-10-21T07-40_GROUPED.csv \
  --json output/activations_dump.json \
  --graph output/graph_data/clt-hp-the-capital-of-201020250035-20251020-003525.json
```

Poi:

```python
import pandas as pd
from scripts.node_grouping_02 import upload_subgraph_to_neuronpedia

df_grouped = pd.read_csv("output/2025-10-21T07-40_GROUPED.csv")

result = upload_subgraph_to_neuronpedia(
    df_grouped=df_grouped,
    graph_json_path="output/graph_data/clt-hp-the-capital-of-201020250035-20251020-003525.json",
    api_key="YOUR_API_KEY",
    display_name="My Grouped Subgraph",
    verbose=True
)

print(f"Subgrafo caricato: {result['url']}")
```

### Da Streamlit

1. Completa Step 1, 2, 3
2. Scorri fino a "🌐 Upload su Neuronpedia"
3. Inserisci API Key
4. (Opzionale) Modifica Display Name
5. (Opzionale) Inserisci Overwrite ID per sovrascrivere subgrafo esistente
6. Clicca "🚀 Upload su Neuronpedia"
7. Attendi conferma
8. Clicca link per visualizzare su Neuronpedia

---

## Edge Cases e Gestione Errori

### Caso 1: Graph JSON Mancante

```python
if not graph_json_available:
    st.warning("⚠️ Graph JSON non caricato. Carica il Graph JSON in Step 3 per abilitare l'upload.")
```

**Soluzione**: Carica Graph JSON in Step 3 prima di procedere.

### Caso 2: API Key Mancante

```python
if not api_key:
    st.error("❌ Inserisci la tua API Key!")
```

**Soluzione**: Inserisci API Key valida.

### Caso 3: Feature Non nel Graph JSON

```python
for node_id, feature_key in node_id_to_feature.items():
    supernode_name = feature_to_supernode.get(feature_key)
    if supernode_name:  # ← Controlla se esiste
        supernode_groups[supernode_name].append(node_id)
```

**Comportamento**: Feature non presenti nel Graph JSON vengono ignorate (non causano errore).

### Caso 4: Nessun Supernode

```python
if len(node_ids) > 0:  # ← Solo supernodes con almeno 1 nodo
    supernodes.append([supernode_name] + node_ids)
```

**Comportamento**: Supernodes vuoti vengono esclusi dal payload.

### Caso 5: Errore API

```python
try:
    response = requests.post(...)
    response.raise_for_status()
except requests.exceptions.RequestException as e:
    if verbose:
        print(f"❌ Errore upload: {e}")
        print(f"Response status: {e.response.status_code}")
        print(f"Response body: {e.response.text}")
    raise
```

**Comportamento**: Mostra dettagli errore (status code, body) e rilancia eccezione.

### Caso 6: Timeout

```python
response = requests.post(..., timeout=30)
```

**Comportamento**: Timeout dopo 30 secondi (evita hang infinito).

---

## Testing

### Test Manuale

1. **Verifica Mapping**:
   ```python
   # Controlla che tutti i node_id siano mappati correttamente
   assert len(node_id_to_feature) == len(nodes)
   
   # Controlla che tutti i feature_key abbiano un supernode_name
   for feature_key in feature_to_supernode.keys():
       assert feature_key in df_grouped['feature_key'].values
   ```

2. **Verifica Supernodes**:
   ```python
   # Controlla che tutti i supernodes abbiano almeno 1 nodo
   for sn in supernodes:
       assert len(sn) > 1  # [name, node_id1, ...]
   
   # Controlla che il formato sia corretto
   for sn in supernodes:
       assert isinstance(sn[0], str)  # Nome
       assert all(isinstance(node_id, str) for node_id in sn[1:])  # Node IDs
   ```

3. **Verifica Payload**:
   ```python
   # Controlla che il payload sia valido
   assert payload['modelId'] == 'gemma-2-2b'
   assert payload['slug'] == 'clt-hp-the-capital-of-201020250035-20251020-003525'
   assert len(payload['supernodes']) > 0
   assert len(payload['pinnedIds']) > 0
   ```

### Test Automatico

```python
def test_upload_subgraph():
    """Test upload subgrafo su Neuronpedia"""
    df_grouped = pd.DataFrame({
        'feature_key': ['0_12284', '20_44686', '7_3144'],
        'supernode_name': ['The', 'Texas', 'Austin']
    })
    
    graph_json_path = 'output/graph_data/clt-hp-the-capital-of-201020250035-20251020-003525.json'
    api_key = 'test_key'
    
    # Mock requests.post
    with patch('requests.post') as mock_post:
        mock_post.return_value.json.return_value = {'success': True, 'id': 'abc123'}
        
        result = upload_subgraph_to_neuronpedia(
            df_grouped=df_grouped,
            graph_json_path=graph_json_path,
            api_key=api_key,
            verbose=False
        )
        
        # Verifica chiamata API
        assert mock_post.called
        assert mock_post.call_args[1]['headers']['x-api-key'] == api_key
        assert 'supernodes' in mock_post.call_args[1]['json']
        
        # Verifica result
        assert result['success'] == True
        assert result['id'] == 'abc123'
```

---

## Benefici

1. ✅ **Visualizzazione Interattiva**: Esplora il grafo raggruppato su Neuronpedia
2. ✅ **Condivisione Facile**: Condividi URL del subgrafo con altri ricercatori
3. ✅ **Integrazione Completa**: Workflow end-to-end da generazione a visualizzazione
4. ✅ **Overwrite Support**: Aggiorna subgrafi esistenti senza creare duplicati
5. ✅ **Robustezza**: Gestione errori completa e validazioni

---

## Limitazioni e Future Improvements

### Limitazioni Attuali

1. **Clerps non supportati**: Il campo `clerps` è sempre vuoto
2. **pinnedIds**: Usa tutti i nodi o quelli da `qParams` (non personalizzabile da UI)
3. **Timeout fisso**: 30 secondi (potrebbe essere insufficiente per grafi molto grandi)

### Future Improvements

1. **Selezione Supernodes**: Permettere di selezionare quali supernodes uploadare
2. **Preview Payload**: Mostrare payload JSON prima dell'upload
3. **Batch Upload**: Supportare upload di più subgrafi in batch
4. **Clerps Support**: Aggiungere supporto per clerps (se necessario)
5. **Configurazione Thresholds**: Permettere di modificare `pruningThreshold` e `densityThreshold` da UI

---

## Conclusione

L'upload su Neuronpedia completa il workflow di Node Grouping:

1. ✅ **Step 1**: Preparazione dataset (peak/target tokens)
2. ✅ **Step 2**: Classificazione nodi (Semantic, Say X, Relationship)
3. ✅ **Step 3**: Naming supernodi
4. ✅ **Step 4**: Upload su Neuronpedia ← **NUOVO!**

**Risultato**: Workflow completo da generazione grafo a visualizzazione interattiva con supernodes! 🎉

