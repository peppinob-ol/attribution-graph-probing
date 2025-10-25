# Feature: Token Semantici Estesi per Relationship Naming

**Data**: 2025-10-25  
**Status**: ✅ Implementato  

---

## Descrizione

Il naming dei nodi **Relationship** ora usa un **pool esteso di token semantici** che include:
1. Token semantici dal **prompt originale del grafo**
2. Token dai **nomi delle feature Semantic** (supernode_name)

Questo permette di catturare concetti fondamentali come "Texas" che non sono nel prompt originale ma emergono come feature Semantic importanti.

---

## Ordine di Esecuzione

### Prima (ERRATO)
```
1. Relationship naming
2. Semantic naming
3. Say X naming
```

### Dopo (CORRETTO)
```
1. Semantic naming    ← Prima!
2. Say X naming
3. Relationship naming ← Ultima, usa i nomi Semantic
4. top_activations_probe_original (per tutte)
```

**Motivo**: I nomi Semantic devono essere calcolati PRIMA per essere inclusi nel pool di token ammessi per Relationship.

---

## Logica di Costruzione del Pool

### FASE 1: Naming Semantic e Say X

```python
for feature_key, group in df.groupby('feature_key'):
    pred_label = group['pred_label'].iloc[0]
    
    if pred_label == "Semantic":
        name = name_semantic_node(feature_key, group, graph_json_path)
        df.loc[df['feature_key'] == feature_key, 'supernode_name'] = name
    
    elif pred_label == 'Say "X"':
        name = name_sayx_node(feature_key, group)
        df.loc[df['feature_key'] == feature_key, 'supernode_name'] = name
```

### FASE 2: Raccogli Token Semantici Estesi

```python
semantic_labels = set()

# 1. Raccogli dai nomi Semantic
for feature_key, group in df.groupby('feature_key'):
    pred_label = group['pred_label'].iloc[0]
    if pred_label == "Semantic":
        supernode_name = group['supernode_name'].iloc[0]
        if supernode_name and supernode_name not in ['Semantic (unknown)', 'punctuation']:
            # Normalizza: lowercase e strip
            semantic_labels.add(supernode_name.strip().lower())

# 2. Aggiungi token dal prompt originale
if graph_tokens_original:
    for token in graph_tokens_original:
        if token.strip() not in ['<bos>', '<eos>', '<pad>', '<unk>']:
            if classify_peak_token(token) == "semantic":
                semantic_labels.add(token.strip().lower())

# 3. Converti in lista (set evita duplicati automaticamente)
extended_semantic_tokens = list(semantic_labels)
```

### FASE 3: Naming Relationship

```python
for feature_key, group in df.groupby('feature_key'):
    pred_label = group['pred_label'].iloc[0]
    
    if pred_label == "Relationship":
        name = name_relationship_node(
            feature_key, 
            group, 
            activations_by_prompt, 
            extended_semantic_tokens  # ← Pool esteso!
        )
        df.loc[df['feature_key'] == feature_key, 'supernode_name'] = name
```

### FASE 4: Calcola top_activations_probe_original

```python
for feature_key, group in df.groupby('feature_key'):
    top_activations = get_top_activations_original(
        activations_by_prompt,
        feature_key,
        extended_semantic_tokens  # ← Usa pool esteso
    )
    top_activations_json = json.dumps(top_activations)
    df.loc[df['feature_key'] == feature_key, 'top_activations_probe_original'] = top_activations_json
```

---

## Esempio Pratico

### Dataset

**Prompt originale del grafo**:
```
"The capital of state containing Dallas is"
Tokens: ["<bos>", "The", " capital", " of", " state", " containing", " Dallas", " is"]
Token semantici: ["capital", "state", "containing", "dallas"]
```

**Feature Semantic nel CSV**:
- `20_44686` (Semantic) → `supernode_name = "Texas"`
- `7_3144` (Semantic) → `supernode_name = "Austin"`

### Pool Esteso

**Prima** (solo prompt originale):
```python
semantic_tokens = ["capital", "state", "containing", "dallas"]
```

**Dopo** (prompt originale + Semantic labels):
```python
semantic_tokens = ["capital", "state", "containing", "dallas", "texas", "austin"]
#                                                               ↑ Aggiunti!
```

### Naming Relationship `1_12928`

**Attivazioni sui probe prompts**:
```
Probe "entity: A city in Texas, USA is Dallas":
  - " Dallas" → 91.24
  - " Texas" → 100.97  ← MAX!

Probe "entity: The capital city of Texas is Austin":
  - " capital" → 33.0
  - " Austin" → 53.0

...
```

**Prima** (senza "Texas" nel pool):
```python
# "Texas" non è nel pool, quindi viene ignorato
# Trova: "Dallas" → 91.24 (max tra i token ammessi)
supernode_name = "(Dallas) related"
```

**Dopo** (con "Texas" nel pool):
```python
# "Texas" è nel pool (da feature Semantic)
# Trova: "Texas" → 100.97 (max globale!)
supernode_name = "(Texas) related"  ✅
```

---

## Gestione Varianti e Duplicati

### Normalizzazione

Tutti i token sono normalizzati a **lowercase** per il matching:

```python
semantic_labels.add(supernode_name.strip().lower())
# "Texas" → "texas"
# " Dallas" → "dallas"
# "AUSTIN" → "austin"
```

### Matching Case-Insensitive

```python
probe_token_lower = probe_token.strip().lower()

if probe_token_lower in semantic_tokens_original:
    # Match! (es. " Texas" matches "texas")
    activation = values[idx]
```

### Display con Case Originale

```python
# Mantieni il case originale del probe token per display
token_display[probe_token_lower] = probe_token.strip()
# "texas" → " Texas" (come appare nel probe)
```

### Duplicati Automaticamente Evitati

```python
semantic_labels = set()  # ← Set evita duplicati

# Se "dallas" è sia nel prompt originale che in un Semantic label:
semantic_labels.add("dallas")  # Prima volta
semantic_labels.add("dallas")  # Seconda volta (ignorato dal set)

# Risultato: "dallas" appare una sola volta
```

---

## Modifiche alle Funzioni

### `get_top_activations_original()`

**Prima**:
```python
def get_top_activations_original(
    activations_by_prompt: Optional[Dict],
    feature_key: str,
    graph_tokens_original: Optional[List[str]]  # ← Lista di token raw
) -> List[Dict[str, Any]]:
    # Estrae token semantici da graph_tokens_original
    semantic_tokens_original = []
    for token in graph_tokens_original:
        if classify_peak_token(token) == "semantic":
            semantic_tokens_original.append(token.strip().lower())
```

**Dopo**:
```python
def get_top_activations_original(
    activations_by_prompt: Optional[Dict],
    feature_key: str,
    semantic_tokens_list: Optional[List[str]]  # ← Lista già lowercase
) -> List[Dict[str, Any]]:
    # semantic_tokens_list è già pronta
    semantic_tokens_original = semantic_tokens_list
```

### `name_relationship_node()`

**Prima**:
```python
def name_relationship_node(
    feature_key: str,
    feature_records: pd.DataFrame,
    activations_by_prompt: Optional[Dict] = None,
    graph_tokens_original: Optional[List[str]] = None  # ← Token raw
) -> str:
    # Estrae token semantici da graph_tokens_original
    semantic_tokens_original = []
    for token in graph_tokens_original:
        if classify_peak_token(token) == "semantic":
            semantic_tokens_original.append(token.strip().lower())
```

**Dopo**:
```python
def name_relationship_node(
    feature_key: str,
    feature_records: pd.DataFrame,
    activations_by_prompt: Optional[Dict] = None,
    semantic_tokens_list: Optional[List[str]] = None  # ← Lista già lowercase
) -> str:
    # semantic_tokens_list è già pronta
    semantic_tokens_original = semantic_tokens_list
```

---

## Benefici

### 1. Cattura Concetti Emergenti

Feature Semantic come "Texas" che non sono nel prompt originale ma sono fondamentali per il grafo vengono ora incluse nel naming di Relationship.

### 2. Naming Più Accurato

Il token con **max activation globale** viene scelto, anche se non è nel prompt originale.

**Esempio**: "Texas" (100.97) > "Dallas" (91.24)

### 3. Coerenza tra Feature

I nomi delle feature Semantic influenzano direttamente il naming delle feature Relationship, creando una gerarchia semantica coerente.

### 4. Robustezza

- **Duplicati evitati**: Set garantisce unicità
- **Case-insensitive matching**: Gestisce varianti
- **Case originale preservato**: Display mantiene il case del probe

---

## Edge Cases

### Caso 1: Nessuna Feature Semantic

```python
# Se non ci sono feature Semantic nel CSV
semantic_labels = set()  # Vuoto

# Usa solo token dal prompt originale
if graph_tokens_original:
    for token in graph_tokens_original:
        # ...
        semantic_labels.add(token.strip().lower())

# Risultato: Solo token originali (comportamento precedente)
```

### Caso 2: Semantic con Nome Speciale

```python
# Feature Semantic con nome "Semantic (unknown)" o "punctuation"
if supernode_name and supernode_name not in ['Semantic (unknown)', 'punctuation']:
    semantic_labels.add(supernode_name.strip().lower())
# → Questi nomi speciali vengono esclusi dal pool
```

### Caso 3: Graph JSON Mancante

```python
# Se graph_json_path non è fornito
graph_tokens_original = None

# Usa solo nomi Semantic
semantic_labels = set()
for feature_key, group in df.groupby('feature_key'):
    if pred_label == "Semantic":
        semantic_labels.add(supernode_name.strip().lower())

# Risultato: Solo nomi Semantic (nessun token originale)
```

---

## Testing

### Test Manuale

```python
# Verifica che "Texas" sia nel pool
extended_semantic_tokens = [...]
assert "texas" in extended_semantic_tokens

# Verifica naming Relationship
df_rel = df[df['pred_label'] == 'Relationship']
name_1_12928 = df_rel[df_rel['feature_key'] == '1_12928']['supernode_name'].iloc[0]
assert name_1_12928 == "(Texas) related"  # Non "(Dallas) related"
```

### Test Automatico

```python
def test_extended_semantic_tokens():
    """Verifica che i nomi Semantic siano inclusi nel pool"""
    df = pd.DataFrame({
        'feature_key': ['20_44686', '1_12928'],
        'pred_label': ['Semantic', 'Relationship'],
        # ...
    })
    
    # Esegui naming
    df_final = name_nodes(df, activations_json_path='...', graph_json_path='...')
    
    # Verifica che Semantic sia stato nominato prima
    assert df_final[df_final['feature_key'] == '20_44686']['supernode_name'].iloc[0] == "Texas"
    
    # Verifica che Relationship usi "Texas"
    assert df_final[df_final['feature_key'] == '1_12928']['supernode_name'].iloc[0] == "(Texas) related"
```

---

## Conclusione

Il sistema ora:

1. ✅ **Nomina Semantic e Say X per primi**
2. ✅ **Raccoglie token semantici estesi** (prompt originale + Semantic labels)
3. ✅ **Nomina Relationship usando il pool esteso**
4. ✅ **Calcola top_activations con il pool esteso**
5. ✅ **Gestisce varianti case-insensitive**
6. ✅ **Evita duplicati automaticamente**

**Risultato**: Naming più accurato e semanticamente coerente per feature Relationship! 🚀

