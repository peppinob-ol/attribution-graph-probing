# Bug Fix: Say X Naming - Occorrenze Token Specifico

**Data**: 2025-10-25  
**Status**: ✅ Risolto  
**Severity**: Alta (naming errato)

---

## Problema

### Bug Identificato

La funzione `name_sayx_node()` raccoglieva **TUTTE** le occorrenze di **TUTTI** i target tokens da **TUTTI** i record, invece di raccogliere solo le occorrenze del **token specifico** selezionato.

Questo causava che `normalize_token_for_naming` scegliesse la **prima occorrenza con maiuscola** tra TUTTI i target, non quella del token selezionato.

### Esempio Feature `7_89264`

**Dati**:
```
feature_key: 7_89264
layer: 7
pred_label: Say "X"
supernode_label (manuale): "Say "Austin""

Tutti i record:
Row 115: peak_token=",",          activation_max=0.82,  target_tokens=[USA, Texas]
Row 116: peak_token=" is",        activation_max=8.96,  target_tokens=[Austin] ← MAX
Row 117: peak_token="entity",     activation_max=0.0,   target_tokens=[entity]
Row 118: peak_token="attribute",  activation_max=0.0,   target_tokens=[attribute]
Row 119: peak_token="relationship", activation_max=0.0, target_tokens=[relationship]
```

**Naming ERRATO** (prima del fix):
```python
# Step 1: Trova record con max activation
max_record = Row 116 (activation_max=8.96)

# Step 2: Estrai target_tokens dal max_record
target_tokens = [{"token": " Austin", ...}]

# Step 3: Un solo target
x_raw = " Austin"

# Step 4: Raccogli TUTTE le occorrenze (PROBLEMA!)
all_x_occurrences = []
for row in feature_records:
    for t in row['target_tokens']:
        all_x_occurrences.append(t['token'])

# Risultato:
all_x_occurrences = [" USA", " Texas", " Austin", "entity", "attribute", "relationship"]
#                      ↑ Prima maiuscola!

# Step 5: Normalizza
x = normalize_token_for_naming(" Austin", all_x_occurrences)
# → Cerca prima occorrenza con maiuscola
# → Trova "USA" (prima nell'array)

supernode_name = "Say (USA)"  ❌ (dovrebbe essere "Say (Austin)")
```

**Naming CORRETTO** (dopo il fix):
```python
# Step 1-3: Identici

# Step 4: Raccogli solo occorrenze di "Austin" (case-insensitive)
x_raw_lower = "austin"
all_x_occurrences = []
for row in feature_records:
    for t in row['target_tokens']:
        if t['token'].strip().lower() == x_raw_lower:
            all_x_occurrences.append(t['token'])

# Risultato:
all_x_occurrences = [" Austin"]  # Solo "Austin"!

# Step 5: Normalizza
x = normalize_token_for_naming(" Austin", [" Austin"])
# → Trova "Austin" (unica occorrenza)

supernode_name = "Say (Austin)"  ✅
```

---

## Causa Root

### Perché Succede?

La funzione `name_sayx_node()` aveva due branch:

1. **Un solo target nel max_record** (linee 920-939)
2. **Multipli target nel max_record** (linee 941-969)

In **entrambi i casi**, la funzione raccoglieva tutte le occorrenze iterando su tutti i record e aggiungendo **TUTTI** i target tokens, senza filtrare per il token specifico selezionato.

### Codice Originale (ERRATO)

```python
# Un solo target
if len(target_tokens) == 1:
    x_raw = str(target_tokens[0].get('token', '?'))
    
    # Raccogli tutte le occorrenze di questo target
    all_x_occurrences = []
    for _, row in feature_records.iterrows():
        try:
            row_targets = json.loads(row.get('target_tokens', '[]'))
            for t in row_targets:
                all_x_occurrences.append(str(t.get('token', '')))  # ❌ Aggiunge TUTTI i token!
        except:
            pass
    
    x = normalize_token_for_naming(x_raw, all_x_occurrences)
    return f"Say ({x})"
```

**Problema**: `all_x_occurrences` contiene **TUTTI** i target tokens di **TUTTI** i record, non solo le occorrenze di `x_raw`.

### Interazione con `normalize_token_for_naming`

```python
def normalize_token_for_naming(token: str, all_occurrences: List[str]) -> str:
    # ...
    
    # Controlla se esiste almeno un'occorrenza con prima lettera maiuscola
    has_uppercase = any(
        occ.strip() and occ.strip()[0].isupper() 
        for occ in all_occurrences 
        if occ.strip()
    )
    
    if has_uppercase:
        # Mantieni la prima occorrenza con maiuscola
        for occ in all_occurrences:
            occ_clean = occ.strip()
            if occ_clean and occ_clean[0].isupper():
                return occ_clean.rstrip(punctuation)  # ← Restituisce la PRIMA maiuscola!
```

**Problema**: Se `all_occurrences = ["USA", "Texas", "Austin"]`, restituisce "USA" (prima maiuscola), anche se il token selezionato era "Austin".

---

## Soluzione

### File Modificato

**`scripts/02_node_grouping.py`** - Funzione `name_sayx_node()` (linee 892-969)

### Modifiche Implementate

#### 1. Branch "Un solo target" (linee 920-939)

**Prima**:
```python
# Raccogli tutte le occorrenze di questo target
all_x_occurrences = []
for _, row in feature_records.iterrows():
    try:
        row_targets = json.loads(row.get('target_tokens', '[]'))
        for t in row_targets:
            all_x_occurrences.append(str(t.get('token', '')))  # ❌ TUTTI i token
    except:
        pass
```

**Dopo**:
```python
# Raccogli solo le occorrenze di QUESTO specifico token (case-insensitive)
x_raw_lower = x_raw.strip().lower()
all_x_occurrences = []
for _, row in feature_records.iterrows():
    try:
        row_targets = json.loads(row.get('target_tokens', '[]'))
        for t in row_targets:
            token_str = str(t.get('token', ''))
            if token_str.strip().lower() == x_raw_lower:  # ✅ Filtra per token specifico
                all_x_occurrences.append(token_str)
    except:
        pass
# Se nessuna occorrenza trovata, usa il token stesso
if not all_x_occurrences:
    all_x_occurrences = [x_raw]
```

#### 2. Branch "Multipli target" (linee 941-969)

**Stesso fix applicato**:
```python
# Raccogli solo le occorrenze di QUESTO specifico token (case-insensitive)
x_raw_lower = x_raw.strip().lower()
all_x_occurrences = []
for _, row in feature_records.iterrows():
    try:
        row_targets = json.loads(row.get('target_tokens', '[]'))
        for t in row_targets:
            token_str = str(t.get('token', ''))
            if token_str.strip().lower() == x_raw_lower:  # ✅ Filtra per token specifico
                all_x_occurrences.append(token_str)
    except:
        pass
# Se nessuna occorrenza trovata, usa il token stesso
if not all_x_occurrences:
    all_x_occurrences = [x_raw]
```

### Cambiamenti Chiave

1. **Filtro case-insensitive**: `token_str.strip().lower() == x_raw_lower`
2. **Solo occorrenze del token selezionato**: Esclude tutti gli altri target tokens
3. **Fallback sicuro**: Se nessuna occorrenza, usa il token stesso

---

## Validazione

### Test Case: Feature `7_89264`

**Prima del fix**:
```
Step 1: Max record → Row 116 (activation_max=8.96)
Step 2: target_tokens → [{"token": " Austin"}]
Step 3: x_raw → " Austin"
Step 4: all_x_occurrences → [" USA", " Texas", " Austin", "entity", "attribute", "relationship"]
Step 5: normalize → "USA" (prima maiuscola)

supernode_name = "Say (USA)"  ❌
```

**Dopo il fix**:
```
Step 1: Max record → Row 116 (activation_max=8.96)
Step 2: target_tokens → [{"token": " Austin"}]
Step 3: x_raw → " Austin"
Step 4: x_raw_lower → "austin"
Step 4a: Filtra per "austin" → all_x_occurrences = [" Austin"]
Step 5: normalize → "Austin" (unica occorrenza)

supernode_name = "Say (Austin)"  ✅
```

### Test Case: Feature con Multipli Target (es. Row 115 di `7_89264`)

**Scenario**: Se Row 115 avesse max activation

**Prima del fix**:
```
Step 1: Max record → Row 115 (activation_max=0.82)
Step 2: target_tokens → [{"token": " USA", "direction": "forward"}, {"token": " Texas", "direction": "backward"}]
Step 3: Tie-break → "Texas" (backward preferito)
Step 4: all_x_occurrences → [" USA", " Texas", " Austin", "entity", "attribute", "relationship"]
Step 5: normalize → "USA" (prima maiuscola)

supernode_name = "Say (USA)"  ❌ (dovrebbe essere "Say (Texas)")
```

**Dopo il fix**:
```
Step 1: Max record → Row 115 (activation_max=0.82)
Step 2: target_tokens → [{"token": " USA", "direction": "forward"}, {"token": " Texas", "direction": "backward"}]
Step 3: Tie-break → "Texas" (backward preferito)
Step 4: x_raw_lower → "texas"
Step 4a: Filtra per "texas" → all_x_occurrences = [" Texas"]
Step 5: normalize → "Texas" (unica occorrenza)

supernode_name = "Say (Texas)"  ✅
```

---

## Impatto

### Feature Affette

**Caratteristiche**:
- `pred_label = 'Say "X"'`
- Multipli target tokens distinti tra i vari record
- Il token selezionato NON è il primo con maiuscola nell'array completo

**Esempi potenziali**:
- `7_89264`: "Say (USA)" → "Say (Austin)" ✅
- Altre feature Say X con target tokens multipli

### Feature Non Affette

**Say X con un solo target unico**: Comportamento invariato (già corretto)
**Semantic**: Nessun impatto (non usa `name_sayx_node`)
**Relationship**: Nessun impatto (non usa `name_sayx_node`)

---

## Coerenza con Altri Fix

Questo bug è **identico** al bug risolto in `name_semantic_node()` (Bug #2 in `BUGFIX_SEMANTIC_NAMING.md`):

### Pattern Comune

**Problema**: Raccogliere **TUTTI** i token invece di filtrare per il token specifico selezionato.

**Soluzione**: Filtro case-insensitive per raccogliere solo le occorrenze del token selezionato.

### Funzioni Affette

1. ✅ `name_semantic_node()` - Fixed in `BUGFIX_SEMANTIC_NAMING.md`
2. ✅ `name_sayx_node()` - Fixed in questo documento
3. ✅ `name_relationship_node()` - Già corretto (usa solo `best_token` dal JSON)

---

## Best Practices Applicate

### 1. Filtro Esplicito per Token Specifico

```python
x_raw_lower = x_raw.strip().lower()
if token_str.strip().lower() == x_raw_lower:
    all_x_occurrences.append(token_str)
```

- Garantisce che solo le occorrenze del token selezionato siano considerate
- Coerente con la logica di naming

### 2. Fallback Sicuro

```python
if not all_x_occurrences:
    all_x_occurrences = [x_raw]
```

- Gestisce edge case (nessuna occorrenza trovata)
- Evita errori di runtime

### 3. Case-Insensitive Matching

```python
x_raw_lower = x_raw.strip().lower()
token_str.strip().lower() == x_raw_lower
```

- Robusto a variazioni di capitalizzazione
- Evita duplicati per lo stesso token con capitalizzazione diversa

---

## Testing

### Test Automatici Necessari

```python
def test_sayx_naming_filters_specific_token():
    """Verifica che name_sayx_node filtri per il token specifico selezionato"""
    df = pd.DataFrame({
        'feature_key': ['7_89264'] * 5,
        'activation_max': [0.82, 8.96, 0.0, 0.0, 0.0],
        'peak_token': [',', ' is', 'entity', 'attribute', 'relationship'],
        'target_tokens': [
            '[{"token": " USA", "index": 8}, {"token": " Texas", "index": 6}]',
            '[{"token": " Austin", "index": 9}]',
            '[{"token": "entity", "index": 1}]',
            '[{"token": "attribute", "index": 1}]',
            '[{"token": "relationship", "index": 1}]'
        ]
    })
    
    name = name_sayx_node('7_89264', df)
    
    # Deve scegliere "Austin" (max activation), non "USA" (prima maiuscola)
    assert name == "Say (Austin)"
```

```python
def test_sayx_naming_multiple_targets_backward():
    """Verifica tie-break con backward preferito"""
    df = pd.DataFrame({
        'feature_key': ['test'] * 1,
        'activation_max': [10.0],
        'peak_token': [','],
        'target_tokens': [
            '[{"token": " USA", "distance": 1, "direction": "forward"}, '
            '{"token": " Texas", "distance": 1, "direction": "backward"}]'
        ]
    })
    
    name = name_sayx_node('test', df)
    
    # Deve scegliere "Texas" (backward preferito), non "USA"
    assert name == "Say (Texas)"
```

### Test Manuali Eseguiti

1. ✅ Feature `7_89264`: "Say (USA)" → "Say (Austin)" (corretto)
2. ✅ Feature con multipli target: Tie-break corretto
3. ✅ Feature con un solo target: Comportamento invariato

---

## Conclusione

Il bug è stato **identificato e risolto**. La funzione `name_sayx_node()` ora:

1. ✅ Filtra correttamente per il token specifico selezionato
2. ✅ Raccoglie solo le occorrenze di quel token (case-insensitive)
3. ✅ Gestisce fallback multipli per robustezza

**Impatto**:
- ✅ Naming accurato per feature Say X con multipli target
- ✅ Coerente con la logica di selezione del token
- ✅ Gestione robusta di edge case

**Pronto per produzione!** 🚀

