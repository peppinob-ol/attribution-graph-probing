# Bug Fix: Semantic Naming con csv_ctx_idx Fallback

**Data**: 2025-10-25  
**Status**: ✅ Implementato  
**Severity**: Media (naming errato per feature Semantic con solo peak funzionali)

---

## Problema

### Bug Identificato

Feature **Semantic** con **solo peak funzionali** (es. `0_40780`) venivano nominate usando il peak token funzionale con max activation, invece del token semantico corretto dalla posizione originale del grafo.

### Esempio Feature `0_40780`

**Dati**:
```
feature_key: 0_40780
layer: 0
pred_label: Semantic (Dictionary fallback)
csv_ctx_idx: 7

Tutti i record:
- Row 20: peak_token=" is",    activation_max=50.74
- Row 21: peak_token=" is",    activation_max=48.96
- Row 22: peak_token=" the",   activation_max=53.07
- Row 23: peak_token=" is",    activation_max=50.94
- Row 24: peak_token=" which", activation_max=59.61 ← MAX
```

**Naming ERRATO** (prima del fix):
```python
# Fallback su tutti i record attivi
semantic_records = feature_records[feature_records['activation_max'] > 0]
# Trova max activation
max_record = semantic_records.loc[semantic_records['activation_max'].idxmax()]
# → peak_token = " which" (59.61)

supernode_name = "which"  # ❌ Token funzionale!
```

**Naming CORRETTO** (dopo il fix):
```python
# Controlla se TUTTI i record attivi sono funzionali
all_functional = all(semantic_records['peak_token_type'] == 'functional')

if all_functional and csv_ctx_idx and graph_json_path:
    # Usa il token dal Graph JSON alla posizione csv_ctx_idx
    csv_ctx_idx = 7
    
    # Graph JSON: metadata.prompt_tokens
    prompt_tokens = ["<bos>", "The", " capital", " of", " state", " containing", " Dallas", " is"]
    #                   0       1        2          3       4          5             6         7
    
    token_from_graph = prompt_tokens[7]  # " is"
    
    supernode_name = "is"  # ✅ Corretto!
```

---

## Causa Root

### Perché Succede?

Feature Semantic di **layer basso** (es. layer 0) possono essere classificate come "Dictionary" perché:
- Si attivano **sempre** sullo stesso token funzionale (es. "is")
- Hanno `peak_consistency_main >= 0.8` (alta consistenza)
- Hanno `n_distinct_peaks <= 1` (un solo peak distinto)

Tuttavia, nei probe prompts, il token "is" può apparire in **posizioni diverse** rispetto al prompt originale del grafo, causando:
- `peak_token` nei probe prompts = token funzionale (es. "is", "the", "which")
- `peak_token_type` = "functional" (classificato come funzionale)

**Ma**: Il nodo nel grafo originale si riferisce al token alla posizione `csv_ctx_idx = 7`, che è il token semantico corretto.

### Esempio Concreto

**Graph JSON originale**:
```json
{
  "metadata": {
    "prompt": "<bos>The capital of state containing Dallas is",
    "prompt_tokens": [
      "<bos>",      // 0
      "The",        // 1
      " capital",   // 2
      " of",        // 3
      " state",     // 4
      " containing",// 5
      " Dallas",    // 6
      " is"         // 7 ← csv_ctx_idx
    ]
  }
}
```

**Nodo nel grafo**: Feature `0_40780` si riferisce al token alla posizione 7 (`" is"`) nel prompt originale.

**Probe prompts**:
```
entity: A city in Texas, USA is Dallas
        ↑ "is" appare alla posizione 9 (diversa!)

entity: The capital city of Texas is Austin
        ↑ "is" appare alla posizione 8

entity: A state in the United States is Texas
        ↑ "the" appare alla posizione 6 (diverso token!)
```

**Problema**: I probe prompts hanno strutture diverse, quindi il peak token può variare anche se la feature si attiva sempre sullo stesso concetto.

---

## Soluzione

### File Modificati

#### 1. `scripts/02_node_grouping.py` - Funzione `name_semantic_node()`

**Modifiche** (linee 804-889):

**Aggiunto parametro `graph_json_path`**:
```python
def name_semantic_node(
    feature_key: str,
    feature_records: pd.DataFrame,
    graph_json_path: Optional[str] = None  # ← NUOVO
) -> str:
```

**Aggiunto fallback per csv_ctx_idx**:
```python
# Se ancora nessuno, fallback su tutti i record attivi
if len(semantic_records) == 0:
    semantic_records = feature_records[feature_records['activation_max'] > 0]
    
    # Controlla se TUTTI i record attivi sono funzionali
    if len(semantic_records) > 0:
        all_functional = all(
            semantic_records['peak_token_type'] == 'functional'
        )
        
        # Se tutti funzionali E abbiamo csv_ctx_idx E graph_json_path
        if all_functional and 'csv_ctx_idx' in feature_records.columns and graph_json_path:
            # Usa il token dal Graph JSON alla posizione csv_ctx_idx
            csv_ctx_idx = feature_records.iloc[0].get('csv_ctx_idx')
            
            if pd.notna(csv_ctx_idx) and graph_json_path:
                try:
                    with open(graph_json_path, 'r', encoding='utf-8') as f:
                        graph_json = json.load(f)
                    
                    prompt_tokens = graph_json.get('metadata', {}).get('prompt_tokens', [])
                    csv_ctx_idx_int = int(csv_ctx_idx)
                    
                    if 0 <= csv_ctx_idx_int < len(prompt_tokens):
                        token_from_graph = prompt_tokens[csv_ctx_idx_int]
                        
                        # Normalizza
                        all_occurrences = [token_from_graph]
                        return normalize_token_for_naming(token_from_graph, all_occurrences)
                except Exception as e:
                    # Se fallisce, continua con la logica normale
                    pass
```

#### 2. `scripts/02_node_grouping.py` - Funzione `name_nodes()`

**Aggiunto parametro `graph_json_path`**:
```python
def name_nodes(
    df: pd.DataFrame,
    activations_json_path: Optional[str] = None,
    graph_json_path: Optional[str] = None,  # ← NUOVO
    verbose: bool = True
) -> pd.DataFrame:
```

**Passa `graph_json_path` a `name_semantic_node()`**:
```python
elif pred_label == "Semantic":
    name = name_semantic_node(feature_key, group, graph_json_path)
```

#### 3. `scripts/02_node_grouping.py` - CLI `main()`

**Aggiunto argomento `--graph`**:
```python
parser.add_argument(
    "--graph",
    type=str,
    default=None,
    help="Path opzionale al Graph JSON (per csv_ctx_idx fallback in Semantic naming)"
)
```

**Passa `graph_json_path` a `name_nodes()`**:
```python
df_final = name_nodes(
    df_classified,
    activations_json_path=args.json,
    graph_json_path=args.graph,  # ← NUOVO
    verbose=args.verbose
)
```

#### 4. `eda/pages/02_Node_Grouping.py` - Streamlit

**Aggiunto caricamento Graph JSON**:
```python
# Percorsi di default
default_graph_path = parent_dir / "output" / "graph_data" / "clt-hp-the-capital-of-201020250035-20251020-003525.json"

# Carica automaticamente
if default_graph_path.exists():
    st.session_state['default_graph'] = default_graph_path
    st.sidebar.info(f"✅ Graph JSON caricato automaticamente: `{default_graph_path.name}`")

# File uploader
uploaded_graph = st.sidebar.file_uploader(
    "Graph JSON (opzionale)",
    type=["json"],
    help="File Graph JSON originale (per csv_ctx_idx fallback in Semantic naming)"
)

# Usa file caricato o default
graph_to_use = uploaded_graph if uploaded_graph is not None else st.session_state.get('default_graph')
```

**Passa `graph_json_path` a `name_nodes()`**:
```python
# Determina path al Graph JSON
graph_path = None
if graph_to_use:
    if isinstance(graph_to_use, Path):
        graph_path = str(graph_to_use)
    else:
        # Se è un file caricato, salva temporaneamente
        graph_path = Path("temp_graph.json")
        graph_json_content = json.loads(graph_to_use.read().decode('utf-8'))
        with open(graph_path, 'w', encoding='utf-8') as f:
            json.dump(graph_json_content, f)

df_named = name_nodes(
    st.session_state['df_classified'],
    activations_json_path=str(json_path) if json_path else None,
    graph_json_path=graph_path,  # ← NUOVO
    verbose=False
)

# Rimuovi file temporanei
if graph_path and Path(graph_path).name == "temp_graph.json" and Path(graph_path).exists():
    Path(graph_path).unlink()
```

---

## Logica del Fallback

### Ordine di Priorità per Naming Semantic

1. **Peak semantici attivi** (`peak_token_type='semantic'` AND `activation_max > 0`)
   - Usa il peak semantico con max activation
   - Esempio: "Texas" (31.10) invece di "Dallas" (21.18)

2. **Peak semantici inattivi** (`peak_token_type='semantic'` AND `activation_max = 0`)
   - Usa il peak semantico anche se inattivo
   - Esempio: "attribute" (0.0) se è l'unico semantico

3. **Tutti funzionali + csv_ctx_idx + Graph JSON** ✅ NUOVO
   - Se TUTTI i peak sono funzionali
   - E `csv_ctx_idx` è disponibile
   - E `graph_json_path` è fornito
   - → Usa il token dal Graph JSON alla posizione `csv_ctx_idx`
   - Esempio: `0_40780` → "is" (dal grafo originale)

4. **Fallback finale: Max activation tra tutti i record attivi**
   - Se nessuna delle condizioni sopra è soddisfatta
   - Usa il peak token con max activation (anche se funzionale)
   - Esempio: "which" (59.61) se nessun altro fallback disponibile

---

## Validazione

### Test Case: Feature `0_40780`

**Prima del fix**:
```
Step 1: Filtra semantici attivi → VUOTO (tutti funzionali)
Step 2: Filtra semantici inattivi → VUOTO (nessun semantico)
Step 3: Fallback su record attivi → 5 righe (tutti funzionali)
Step 4: Max activation → " which" (59.61)

supernode_name = "which"  ❌
```

**Dopo il fix**:
```
Step 1: Filtra semantici attivi → VUOTO (tutti funzionali)
Step 2: Filtra semantici inattivi → VUOTO (nessun semantico)
Step 3: Fallback su record attivi → 5 righe (tutti funzionali)
  3a: Controlla all_functional → TRUE
  3b: Controlla csv_ctx_idx → 7 (disponibile)
  3c: Controlla graph_json_path → Disponibile
  3d: Carica Graph JSON → prompt_tokens
  3e: Estrai token alla posizione 7 → " is"

supernode_name = "is"  ✅
```

### Test Case: Feature Semantic Normale (es. `20_44686`)

**Comportamento invariato**:
```
Step 1: Filtra semantici attivi → 2 righe ("Dallas", "Texas")
Step 2: Max activation tra semantici → "Texas" (31.10)

supernode_name = "Texas"  ✅ (già corretto)
```

---

## Impatto

### Feature Affette

**Caratteristiche**:
- `pred_label = "Semantic"`
- Tutti i `peak_token_type = "functional"`
- `csv_ctx_idx` disponibile nel CSV
- Graph JSON fornito

**Esempi potenziali**:
- `0_40780`: "which" → "is" ✅
- Altre feature layer 0-1 con comportamento simile

### Feature Non Affette

**Semantic con peak semantici**: Comportamento invariato (già corretto)
**Say X**: Nessun impatto (non usa `name_semantic_node`)
**Relationship**: Nessun impatto (non usa `name_semantic_node`)

---

## Uso

### CLI

```bash
python scripts/02_node_grouping.py \
  --input output/2025-10-21T07-40_export_ENRICHED.csv \
  --output output/2025-10-21T07-40_export_GROUPED.csv \
  --json output/activations_dump\ \(2\).json \
  --graph output/graph_data/clt-hp-the-capital-of-201020250035-20251020-003525.json
```

### Streamlit

1. Carica CSV Export (auto: `output/2025-10-21T07-40_export_ENRICHED.csv`)
2. Carica JSON Attivazioni (auto: `output/activations_dump (2).json`)
3. Carica Graph JSON (auto: `output/graph_data/clt-hp-the-capital-of-201020250035-20251020-003525.json`)
4. Esegui Step 1, 2, 3
5. Verifica che `0_40780` sia nominata "is" invece di "which"

---

## Best Practices

### 1. Fornisci Sempre il Graph JSON

Per feature Semantic di layer basso, il Graph JSON è **essenziale** per un naming corretto.

### 2. Verifica `csv_ctx_idx`

Assicurati che il CSV abbia la colonna `csv_ctx_idx` popolata correttamente.

### 3. Gestione Errori

Il fallback è **sicuro**: se il Graph JSON non è disponibile o `csv_ctx_idx` manca, la funzione usa il fallback normale (max activation).

---

## Conclusione

Il bug è stato **identificato e risolto**. La funzione `name_semantic_node()` ora:

1. ✅ Filtra correttamente per peak semantici
2. ✅ Usa `csv_ctx_idx` + Graph JSON per feature con solo peak funzionali
3. ✅ Gestisce fallback multipli per robustezza

**Impatto**:
- ✅ Naming accurato per feature Semantic layer basso
- ✅ Coerente con la posizione originale nel grafo
- ✅ Gestione robusta di edge case

**Pronto per produzione!** 🚀

