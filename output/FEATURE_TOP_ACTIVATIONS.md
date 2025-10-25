# Feature: top_activations_probe_original

**Data**: 2025-10-25  
**Status**: ✅ Implementato  

---

## Descrizione

Aggiunta colonna `top_activations_probe_original` al CSV output che contiene un array JSON ordinato per activation (desc) con le top attivazioni sui **token semantici del prompt originale** attraverso **tutti i probe prompts**.

---

## Formato

```json
[
  {"tk": " capital", "act": 72.0},
  {"tk": " Dallas", "act": 37.0},
  {"tk": " state", "act": 25.0},
  {"tk": " containing", "act": 15.0}
]
```

**Campi**:
- `tk`: Token (con case originale preservato)
- `act`: Activation massima su quel token tra tutti i probe prompts

**Ordinamento**: Decrescente per `act` (activation più alta prima)

---

## Logica di Calcolo

### Step 1: Estrai Token Semantici dal Prompt Originale

```python
graph_tokens_original = ["<bos>", "The", " capital", " of", " state", " containing", " Dallas", " is"]

semantic_tokens_original = []
for token in graph_tokens_original:
    if token.strip() not in ['<bos>', '<eos>', '<pad>', '<unk>']:
        if classify_peak_token(token) == "semantic":
            semantic_tokens_original.append(token.strip().lower())

# Risultato: ["the", "capital", "state", "containing", "dallas"]
```

### Step 2: Cerca Token in TUTTI i Probe Prompts

```python
token_activations = {}  # {token_lower: max_activation}

for probe_prompt in all_probes:
    probe_tokens = probe_prompt['tokens']
    counts = probe_prompt['counts'][feature_idx]
    
    for idx, probe_token in enumerate(probe_tokens):
        probe_token_lower = probe_token.strip().lower()
        
        if probe_token_lower in semantic_tokens_original:
            activation = counts[idx]
            
            # Mantieni il MAX per ogni token
            if token_lower not in token_activations or activation > token_activations[token_lower]:
                token_activations[token_lower] = activation
```

### Step 3: Ordina per Activation Desc

```python
result = []
for token_lower in sorted(token_activations.keys(), key=lambda t: token_activations[t], reverse=True):
    result.append({
        "tk": token_display[token_lower],  # Case originale
        "act": float(token_activations[token_lower])
    })
```

---

## Esempio Pratico

### Feature `1_12928` (Relationship)

**Prompt originale**:
```
"The capital of state containing Dallas is"
Tokens: ["<bos>", "The", " capital", " of", " state", " containing", " Dallas", " is"]
Token semantici: ["The", " capital", " state", " containing", " Dallas"]
```

**Probe prompts** (5):
1. `"entity: A city in Texas, USA is Dallas"`
2. `"entity: The capital city of Texas is Austin"`
3. `"entity: A state in the United States is Texas"`
4. `"attribute: The primary city serving as the seat of government for a state is the capital city"`
5. `"relationship: the state in which a city is located is the state containing"`

**Attivazioni raccolte**:
```
Token "The":
  - Probe 2 ("entity: The capital...") → activation 15.0
  - Probe 4 ("attribute: The primary...") → activation 12.0
  → MAX: 15.0

Token "capital":
  - Probe 2 ("entity: The capital city...") → activation 50.0
  - Probe 4 ("attribute: ... the capital city") → activation 72.0
  → MAX: 72.0

Token "Dallas":
  - Probe 1 ("entity: ... is Dallas") → activation 37.0
  → MAX: 37.0

Token "state":
  - Probe 3 ("entity: A state in...") → activation 20.0
  - Probe 5 ("relationship: the state in which...") → activation 25.0
  → MAX: 25.0

Token "containing":
  - Probe 5 ("relationship: ... state containing") → activation 15.0
  → MAX: 15.0
```

**Output finale** (ordinato per activation desc):
```json
[
  {"tk": " capital", "act": 72.0},
  {"tk": " Dallas", "act": 37.0},
  {"tk": " state", "act": 25.0},
  {"tk": " The", "act": 15.0},
  {"tk": " containing", "act": 15.0}
]
```

---

## Funzione Implementata

### `get_top_activations_original()`

**File**: `scripts/02_node_grouping.py` (linee 748-810)

**Signature**:
```python
def get_top_activations_original(
    activations_by_prompt: Optional[Dict],
    feature_idx: Optional[int],
    graph_tokens_original: Optional[List[str]]
) -> List[Dict[str, Any]]:
```

**Parametri**:
- `activations_by_prompt`: Dict con attivazioni per ogni probe prompt
- `feature_idx`: Indice della feature nell'array counts
- `graph_tokens_original`: Lista di tokens dal prompt originale del grafo

**Returns**:
- Lista di dict `[{"tk": token, "act": activation}, ...]` ordinata per activation desc
- Lista vuota `[]` se mancano i dati necessari

---

## Integrazione in `name_nodes()`

**File**: `scripts/02_node_grouping.py` (linee 1198-1205)

```python
# Calcola top_activations_probe_original per tutte le feature
top_activations = get_top_activations_original(
    activations_by_prompt,
    feature_idx,
    graph_tokens_original
)
top_activations_json = json.dumps(top_activations) if top_activations else "[]"
df.loc[df['feature_key'] == feature_key, 'top_activations_probe_original'] = top_activations_json
```

**Note**:
- Calcolata per **TUTTE le feature**, non solo Relationship
- Se mancano dati (Graph JSON, Activations JSON), la colonna contiene `"[]"`
- Formato JSON string per compatibilità CSV

---

## Utilizzo

### Nel CSV Output

```csv
feature_key,layer,pred_label,supernode_name,top_activations_probe_original,...
1_12928,1,Relationship,"(capital) related","[{""tk"":"" capital"",""act"":72.0},{""tk"":"" Dallas"",""act"":37.0}]",...
```

### Parsing in Python

```python
import json
import pandas as pd

df = pd.read_csv('output.csv')

for idx, row in df.iterrows():
    top_acts = json.loads(row['top_activations_probe_original'])
    
    if top_acts:
        print(f"Feature {row['feature_key']}:")
        for item in top_acts:
            print(f"  {item['tk']}: {item['act']}")
```

### Parsing in Streamlit

```python
import json

top_acts = json.loads(row['top_activations_probe_original'])

if top_acts:
    st.write("**Top Activations (Prompt Originale)**:")
    for item in top_acts[:5]:  # Top 5
        st.write(f"- `{item['tk']}`: {item['act']:.2f}")
```

---

## Benefici

### 1. Trasparenza

Mostra **quali token del prompt originale** hanno le attivazioni più alte, permettendo di:
- Verificare il naming di Relationship
- Capire quali concetti sono più rilevanti per la feature
- Debug e validazione

### 2. Analisi

Permette analisi come:
- Distribuzione delle attivazioni sui token originali
- Confronto tra feature diverse
- Identificazione di pattern

### 3. Validazione

Consente di verificare che:
- Il token scelto per naming è effettivamente quello con max activation
- Le attivazioni sono coerenti con il comportamento atteso
- Non ci sono token "nascosti" con attivazioni alte

---

## Edge Cases

### Caso 1: Nessun Token Semantico Originale

```python
graph_tokens_original = ["<bos>", " is", " the"]  # Solo funzionali

# Risultato:
top_activations_probe_original = "[]"
```

### Caso 2: Token Non Trovato nei Probe Prompts

```python
graph_tokens_original = ["<bos>", " rare_token"]
# "rare_token" non appare in nessun probe prompt

# Risultato:
top_activations_probe_original = "[]"
```

### Caso 3: Graph JSON o Activations JSON Mancanti

```python
# Se graph_json_path o activations_json_path non forniti

# Risultato:
top_activations_probe_original = "[]"
```

---

## Testing

### Test Manuale

```python
# Feature 1_12928
top_acts = json.loads(df[df['feature_key'] == '1_12928']['top_activations_probe_original'].iloc[0])

assert len(top_acts) > 0
assert top_acts[0]['tk'] == " capital"  # Token con max activation
assert top_acts[0]['act'] == 72.0
assert top_acts[1]['act'] <= top_acts[0]['act']  # Ordinato desc
```

### Test Automatico

```python
def test_top_activations_ordered():
    """Verifica che top_activations sia ordinato per activation desc"""
    top_acts = get_top_activations_original(
        activations_by_prompt,
        feature_idx=0,
        graph_tokens_original=["<bos>", "The", " capital", " Dallas"]
    )
    
    # Verifica ordinamento
    for i in range(len(top_acts) - 1):
        assert top_acts[i]['act'] >= top_acts[i+1]['act']
```

---

## Conclusione

La colonna `top_activations_probe_original` fornisce:

✅ **Trasparenza** sul processo di naming  
✅ **Validazione** delle scelte automatiche  
✅ **Analisi** delle attivazioni sui token originali  
✅ **Debug** facilitato per feature problematiche  

**Pronto per l'uso!** 🚀

