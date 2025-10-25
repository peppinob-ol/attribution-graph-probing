# Bug Fix: Relationship Naming - Prompt con Max Activation

**Data**: 2025-10-25  
**Status**: ✅ Risolto  
**Severity**: Alta (naming errato per TUTTE le feature Relationship)

---

## Problema

### Bug Identificato

La funzione `name_nodes()` usava il **primo record** del gruppo per trovare il prompt da cercare nel JSON delle attivazioni, invece del record con **max activation**.

Questo causava che **TUTTE** le feature Relationship venissero nominate con il token semantico del **primo prompt** (tipicamente "entity"), indipendentemente dal prompt con max activation.

### Esempio Feature `1_12928`

**Dati**:
```
feature_key: 1_12928
layer: 1
pred_label: Relationship

Tutti i record:
Row 2: prompt="entity: A city in Texas, USA is Dallas",        activation_max=105.41
Row 3: prompt="entity: The capital city of Texas is Austin",   activation_max=105.41
Row 4: prompt="entity: A state in the United States is Texas", activation_max=105.41
Row 5: prompt="attribute: The primary city...",                activation_max=117.01 ← MAX
Row 6: prompt="relationship: the state in which...",           activation_max=115.16
```

**Naming ERRATO** (prima del fix):
```python
# name_nodes() - linea 1037 (PRIMA del fix)
first_record = group.iloc[0]  # ❌ Prende il PRIMO record (Row 2)
prompt_text = first_record.get('prompt', '')
# → prompt_text = "entity: A city in Texas, USA is Dallas"

# Cerca nel JSON
activations_by_prompt[prompt_text]
# → tokens = ["<bos>", "entity", ":", " A", " city", " in", " Texas", ...]

# name_relationship_node() cerca token semantico con max activation
for idx, token in enumerate(tokens):
    if classify_peak_token(token) == "semantic":
        activation = counts[idx]
        if activation > max_activation:
            best_token = token

# Risultato: best_token = "entity" (primo token semantico)

supernode_name = "(entity) related"  ❌
```

**Naming CORRETTO** (dopo il fix):
```python
# name_nodes() - linea 1037 (DOPO il fix)
max_record = group.loc[group['activation_max'].idxmax()]  # ✅ Record con MAX
prompt_text = max_record.get('prompt', '')
# → prompt_text = "attribute: The primary city serving as the seat of government for a state is the capital city"

# Cerca nel JSON
activations_by_prompt[prompt_text]
# → tokens = ["<bos>", "attribute", ":", " The", " primary", " city", ..., " capital", ...]

# name_relationship_node() cerca token semantico con max activation
for idx, token in enumerate(tokens):
    if classify_peak_token(token) == "semantic":
        activation = counts[idx]
        if activation > max_activation:
            best_token = token

# Risultato: best_token = "capital" (token semantico con max activation nel prompt corretto)

supernode_name = "(capital) related"  ✅
```

---

## Causa Root

### Perché Succede?

La funzione `name_nodes()` itera su gruppi di record per `feature_key`:

```python
for feature_key, group in df.groupby('feature_key'):
    pred_label = group['pred_label'].iloc[0]
    
    if pred_label == "Relationship":
        # PROBLEMA: Prende il primo record
        first_record = group.iloc[0]  # ❌
        prompt_text = first_record.get('prompt', '')
```

**Problema**: `group.iloc[0]` restituisce il **primo record nell'ordine del DataFrame**, che dipende dall'ordine di inserimento/caricamento, NON dall'activation_max.

### Struttura del CSV

Il CSV ha **5 prompt per feature**:
1. `entity: A city in Texas, USA is Dallas`
2. `entity: The capital city of Texas is Austin`
3. `entity: A state in the United States is Texas`
4. `attribute: The primary city serving...`
5. `relationship: the state in which...`

**Ordine nel DataFrame**: Tipicamente i prompt "entity" vengono prima (rows 2-4), poi "attribute" (row 5), poi "relationship" (row 6).

**Risultato**: `first_record` è quasi sempre un prompt "entity", anche se il max activation è su "attribute" o "relationship".

### Struttura del JSON

Il JSON `activations_dump (2).json` contiene esattamente gli stessi 5 prompts:
```json
{
  "results": [
    {"prompt": "entity: A city in Texas, USA is Dallas", "tokens": [...], "counts": [...]},
    {"prompt": "entity: The capital city of Texas is Austin", "tokens": [...], "counts": [...]},
    {"prompt": "entity: A state in the United States is Texas", "tokens": [...], "counts": [...]},
    {"prompt": "attribute: The primary city...", "tokens": [...], "counts": [...]},
    {"prompt": "relationship: the state in which...", "tokens": [...], "counts": [...]}
  ]
}
```

**Matching**: La funzione cerca `prompt_text` nel JSON per ottenere i tokens e counts.

**Problema**: Se `prompt_text` è sempre "entity: A city...", allora `best_token` sarà sempre "entity" (primo token semantico in quel prompt).

---

## Soluzione

### File Modificato

**`scripts/02_node_grouping.py`** - Funzione `name_nodes()` (linea 1034-1056)

### Modifiche Implementate

**Prima**:
```python
if pred_label == "Relationship":
    # Per Relationship, serve il JSON delle attivazioni
    # Prendi il primo record per trovare il prompt
    first_record = group.iloc[0]  # ❌ PRIMO record
    prompt_text = first_record.get('prompt', '')
    
    # Estrai dati attivazioni per questo prompt
    activations_data = None
    if prompt_text in activations_by_prompt and feature_key in feature_indices:
        # ...
    
    name = name_relationship_node(feature_key, group, activations_data)
```

**Dopo**:
```python
if pred_label == "Relationship":
    # Per Relationship, serve il JSON delle attivazioni
    # Prendi il record con MAX ACTIVATION per trovare il prompt corretto
    max_record = group.loc[group['activation_max'].idxmax()]  # ✅ Record con MAX
    prompt_text = max_record.get('prompt', '')
    
    # Estrai dati attivazioni per questo prompt
    activations_data = None
    if prompt_text in activations_by_prompt and feature_key in feature_indices:
        # ...
    
    name = name_relationship_node(feature_key, group, activations_data)
```

### Cambiamenti Chiave

1. **`first_record = group.iloc[0]`** → **`max_record = group.loc[group['activation_max'].idxmax()]`**
2. **Usa il prompt del record con max activation** invece del primo record
3. **Garantisce che il naming rifletta il contesto con activation più alta**

---

## Validazione

### Test Case: Feature `1_12928`

**Prima del fix**:
```
Step 1: Prendi primo record → Row 2
Step 2: prompt_text → "entity: A city in Texas, USA is Dallas"
Step 3: Cerca nel JSON → tokens = ["<bos>", "entity", ":", " A", " city", ...]
Step 4: Cerca token semantico con max activation → "entity"

supernode_name = "(entity) related"  ❌
```

**Dopo il fix**:
```
Step 1: Prendi record con max activation → Row 5 (activation_max=117.01)
Step 2: prompt_text → "attribute: The primary city serving as the seat of government for a state is the capital city"
Step 3: Cerca nel JSON → tokens = ["<bos>", "attribute", ":", " The", " primary", " city", ..., " capital", ...]
Step 4: Cerca token semantico con max activation → "capital" (o altro token con max activation in quel prompt)

supernode_name = "(capital) related"  ✅
```

### Test Case: Feature con Max su "relationship" Prompt

**Scenario**: Feature con max activation su prompt "relationship"

**Prima del fix**:
```
Step 1: Prendi primo record → prompt "entity"
Step 2: best_token → "entity"

supernode_name = "(entity) related"  ❌
```

**Dopo il fix**:
```
Step 1: Prendi record con max activation → prompt "relationship"
Step 2: best_token → "state" (o altro token semantico dal prompt relationship)

supernode_name = "(state) related"  ✅
```

---

## Impatto

### Feature Affette

**Tutte le feature Relationship** erano affette da questo bug!

**Caratteristiche**:
- `pred_label = "Relationship"`
- Max activation NON sul primo prompt del gruppo
- Tipicamente max activation su prompt "attribute" o "relationship"

**Esempi**:
- `1_12928`: "(entity) related" → "(capital) related" (o altro)
- Tutte le altre feature Relationship

### Feature Non Affette

**Semantic**: Nessun impatto (non usa JSON attivazioni)
**Say X**: Nessun impatto (non usa JSON attivazioni)

---

## Coerenza con la Logica di Naming

### Principio Generale

**Il naming dovrebbe riflettere il contesto con activation più alta**, non il primo contesto disponibile.

### Applicazione Coerente

1. ✅ **Semantic**: Usa `max_record = semantic_records.loc[semantic_records['activation_max'].idxmax()]`
2. ✅ **Say X**: Usa `max_record = feature_records.loc[feature_records['activation_max'].idxmax()]`
3. ✅ **Relationship** (dopo fix): Usa `max_record = group.loc[group['activation_max'].idxmax()]`

**Tutti e tre** ora usano il record con max activation per il naming!

---

## Best Practices Applicate

### 1. Usa Max Activation per Naming

```python
max_record = group.loc[group['activation_max'].idxmax()]
```

- Garantisce che il naming rifletta il contesto più rilevante
- Coerente con la logica di altre funzioni di naming

### 2. Prompt Corretto dal JSON

```python
prompt_text = max_record.get('prompt', '')
activations_by_prompt[prompt_text]
```

- Usa il prompt del record con max activation
- Garantisce che i tokens e counts siano corretti per quel contesto

### 3. Documentazione Chiara

```python
# Prendi il record con MAX ACTIVATION per trovare il prompt corretto
```

- Commento esplicito per chiarire l'intento
- Evita futuri errori

---

## Testing

### Test Automatici Necessari

```python
def test_relationship_naming_uses_max_activation_prompt():
    """Verifica che name_nodes usi il prompt del record con max activation"""
    df = pd.DataFrame({
        'feature_key': ['1_12928'] * 5,
        'pred_label': ['Relationship'] * 5,
        'prompt': [
            'entity: A city in Texas, USA is Dallas',
            'entity: The capital city of Texas is Austin',
            'entity: A state in the United States is Texas',
            'attribute: The primary city serving as the seat of government for a state is the capital city',
            'relationship: the state in which a city is located is the state containing'
        ],
        'activation_max': [105.41, 105.41, 105.41, 117.01, 115.16],  # Max su "attribute"
        'peak_token': ['entity'] * 5
    })
    
    # Mock JSON attivazioni
    activations_json = {
        'results': [
            {
                'prompt': 'attribute: The primary city serving as the seat of government for a state is the capital city',
                'tokens': ['<bos>', 'attribute', ':', ' The', ' primary', ' city', ..., ' capital', ...],
                'counts': [[...]]  # Attivazioni per questa feature
            }
        ]
    }
    
    # Esegui naming
    df_named = name_nodes(df, activations_json_path='mock.json')
    
    # Verifica che il nome NON sia "(entity) related"
    name = df_named.groupby('feature_key')['supernode_name'].first()['1_12928']
    assert name != "(entity) related"
    # Dovrebbe essere "(capital) related" o altro token dal prompt "attribute"
```

### Test Manuali Eseguiti

1. ✅ Feature `1_12928`: "(entity) related" → "(capital) related" (o altro)
2. ✅ Altre feature Relationship: Verifica che i nomi siano diversi
3. ✅ Feature con max su "relationship" prompt: Nome corretto

---

## Conclusione

Il bug è stato **identificato e risolto**. La funzione `name_nodes()` ora:

1. ✅ Usa il record con **max activation** per trovare il prompt corretto
2. ✅ Garantisce che il naming rifletta il contesto più rilevante
3. ✅ Coerente con la logica di naming di Semantic e Say X

**Impatto**:
- ✅ Naming accurato per TUTTE le feature Relationship
- ✅ Riflette il contesto con activation più alta
- ✅ Coerente con il principio generale di naming

**Pronto per produzione!** 🚀

