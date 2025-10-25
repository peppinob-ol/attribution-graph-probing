# Step 3 — Proposta Naming Supernodi

**Data**: 2025-10-25  
**Status**: Proposta per review

---

## Obiettivo

Assegnare un `supernode_name` a ogni feature basandosi su:
1. La classe predetta (`pred_label`)
2. Il record con `activation_max` più alta per quella feature
3. I `target_tokens` (per Say X)

---

## Regole di Naming per Classe

### 1. Relationship

**Regola**: Nome fisso = `"Relationship"`

**Motivazione**: 
- Relationship collegano concetti semantici multipli
- Non ha senso dare un nome specifico (es. "city-capital-region")
- Il nome generico è più interpretabile

**Esempio**:
```
feature_key: 1_12928
pred_label: Relationship
supernode_name: "Relationship"
```

---

### 2. Semantic

**Regola**: Nome = `peak_token` del record con `activation_max` globale più alta

**Procedura**:
1. Filtra tutti i record per `feature_key`
2. Trova il record con `activation_max` massima
3. Prendi il `peak_token` di quel record
4. Normalizza: lowercase, strip whitespace

**Casi edge**:
- Se `peak_token` è vuoto/null → `"Semantic (unknown)"`
- Se `peak_token` è punteggiatura → `"punctuation"`
- Se `peak_token` è token funzionale → usa comunque (potrebbe essere Dictionary su "is", "the", etc.)

**Sottotipi**:
- **Dictionary** (subtype="Dictionary"): Nome = token specifico (es. "austin", "texas")
- **Concept** (subtype="Concept"): Nome = concetto (es. "city", "capital")

**Esempi**:
```
feature_key: 0_1861
pred_label: Semantic
subtype: Dictionary
Records:
  - prompt: "entity: Texas", peak_token: "Texas", activation_max: 115.2
  - prompt: "entity: Austin", peak_token: "Texas", activation_max: 98.3
  - prompt: "attribute: capital", peak_token: "Texas", activation_max: 102.1
supernode_name: "texas"  # Lowercase del peak_token con max activation
```

```
feature_key: 0_32742
pred_label: Semantic
subtype: Concept
Records:
  - prompt: "entity: Texas", peak_token: "containing", activation_max: 45.2
  - prompt: "relationship: ...", peak_token: "containing", activation_max: 52.8
supernode_name: "containing"
```

---

### 3. Say "X"

**Regola**: Nome = `"Say (X)"` dove X è il `target_token` del record con `activation_max` globale più alta

**Procedura**:
1. Filtra tutti i record per `feature_key`
2. Trova il record con `activation_max` massima
3. Estrai `target_tokens` (JSON array) di quel record
4. **Selezione di X**:
   - Se `target_tokens` è vuoto → X = "?"
   - Se 1 solo target → X = quel token
   - Se 2+ target (es. "both" direction):
     - **Tie-break 1**: Preferisci `distance` minore (più vicino al peak)
     - **Tie-break 2**: Se stesso distance, usa il primo (forward > backward)

**Normalizzazione X**:
- Lowercase
- Strip whitespace
- Se vuoto → "?"

**Casi edge**:
- `target_tokens = []` → `"Say (?)"`
- `target_tokens = [{"token": "Austin", ...}]` → `"Say (austin)"`
- `target_tokens = [{"token": "city", "distance": 2}, {"token": "Texas", "distance": 1}]` → `"Say (texas)"` (distance minore)

**Esempi**:
```
feature_key: 17_98126
pred_label: Say "X"
Records:
  - prompt: "entity: A city in Texas, USA is Dallas", 
    peak_token: "is", 
    activation_max: 8.2,
    target_tokens: [{"token": "Dallas", "index": 9, "distance": 1, "direction": "forward"}]
  - prompt: "attribute: The capital city of Texas is Austin",
    peak_token: "is",
    activation_max: 12.5,
    target_tokens: [{"token": "Austin", "index": 8, "distance": 1, "direction": "forward"}]
supernode_name: "Say (austin)"  # Record con max=12.5
```

```
feature_key: 17_1822
pred_label: Say "X"
Records:
  - prompt: "entity: A city in Texas, USA is Dallas",
    peak_token: ",",
    activation_max: 15.3,
    target_tokens: [
      {"token": "Texas", "index": 5, "distance": 1, "direction": "backward"},
      {"token": "USA", "index": 7, "distance": 1, "direction": "forward"}
    ]
supernode_name: "Say (texas)"  # Stesso distance, preferisci backward (primo nell'array)
```

**DOMANDA**: Per tie-break con stesso distance, preferire forward o backward? O prendere il primo nell'array (che dipende dall'ordine di ricerca)?

---

## Implementazione Proposta

```python
def name_node(
    feature_key: str,
    pred_label: str,
    subtype: Optional[str],
    feature_records: pd.DataFrame
) -> str:
    """
    Assegna supernode_name a una feature.
    
    Args:
        feature_key: chiave della feature
        pred_label: classe predetta
        subtype: sottotipo (per Semantic)
        feature_records: DataFrame con tutti i record per questa feature
        
    Returns:
        supernode_name: str
    """
    # Regola 1: Relationship
    if pred_label == "Relationship":
        return "Relationship"
    
    # Trova record con activation_max massima
    max_record = feature_records.loc[feature_records['activation_max'].idxmax()]
    
    # Regola 2: Semantic
    if pred_label == "Semantic":
        peak_token = str(max_record['peak_token']).strip().lower()
        
        # Casi edge
        if not peak_token or peak_token == 'nan':
            return "Semantic (unknown)"
        if is_punctuation(peak_token):
            return "Semantic (punct)"
        
        return peak_token
    
    # Regola 3: Say "X"
    if pred_label == 'Say "X"':
        # Estrai target_tokens
        target_tokens_json = max_record.get('target_tokens', '[]')
        try:
            target_tokens = json.loads(target_tokens_json)
        except:
            target_tokens = []
        
        # Nessun target
        if not target_tokens:
            return "Say (?)"
        
        # Un solo target
        if len(target_tokens) == 1:
            x = str(target_tokens[0].get('token', '?')).strip().lower()
            return f"Say ({x})"
        
        # Multipli target: tie-break per distance
        # Ordina per distance (crescente), poi per ordine originale
        sorted_targets = sorted(target_tokens, key=lambda t: t.get('distance', 999))
        x = str(sorted_targets[0].get('token', '?')).strip().lower()
        return f"Say ({x})"
    
    # Fallback
    return pred_label


def name_nodes(df: pd.DataFrame, verbose: bool = True) -> pd.DataFrame:
    """
    Step 3: Assegna supernode_name a tutte le feature.
    
    Args:
        df: DataFrame classificato (con pred_label, subtype)
        verbose: stampa info
        
    Returns:
        DataFrame con colonna supernode_name
    """
    df = df.copy()
    df['supernode_name'] = ''
    
    if verbose:
        print(f"\n=== Step 3: Naming Supernodi ===")
    
    # Aggrega per feature_key
    for feature_key, group in df.groupby('feature_key'):
        pred_label = group['pred_label'].iloc[0]
        subtype = group['subtype'].iloc[0] if 'subtype' in group.columns else None
        
        # Assegna nome
        name = name_node(feature_key, pred_label, subtype, group)
        df.loc[df['feature_key'] == feature_key, 'supernode_name'] = name
    
    if verbose:
        # Statistiche
        n_features = df['feature_key'].nunique()
        n_unique_names = df.groupby('feature_key')['supernode_name'].first().nunique()
        
        print(f"Naming completato:")
        print(f"  - {n_features} feature")
        print(f"  - {n_unique_names} nomi unici")
        
        # Conta per tipo
        name_counts = df.groupby('feature_key').agg({
            'pred_label': 'first',
            'supernode_name': 'first'
        })['pred_label'].value_counts()
        
        print(f"\nNomi per classe:")
        for label, count in name_counts.items():
            print(f"  - {label:15s}: {count:3d}")
        
        # Mostra alcuni esempi
        print(f"\nEsempi:")
        for label in ['Relationship', 'Semantic', 'Say "X"']:
            examples = df[df['pred_label'] == label].groupby('feature_key')['supernode_name'].first().head(3)
            if len(examples) > 0:
                print(f"  {label}:")
                for name in examples:
                    print(f"    - {name}")
    
    return df
```

---

## Domande per Review

### 1. Relationship

**Q**: Va bene nome fisso `"Relationship"` o preferisci qualcosa di più specifico?

**Opzioni alternative**:
- A) `"Relationship"` (fisso, proposta attuale)
- B) `"Relationship (N)"` dove N = numero di token semantici distinti (K)
- C) Concatenare i 2-3 token più frequenti: `"city-capital-region"`
- D) Usare il token con max activation: `"city"` (come Semantic)

**Mia raccomandazione**: A (fisso), perché Relationship è un concetto astratto di collegamento, non un token specifico.

---

### 2. Semantic — Casi con peak_token funzionale

**Q**: Se Semantic ha `peak_token` funzionale (es. Dictionary su "is"), usare comunque "is" come nome?

**Scenario**: Feature layer 0 che si attiva sempre su "is"
- `peak_token = "is"` (functional)
- `pred_label = "Semantic"` (Dictionary fallback per layer <= 3)
- `supernode_name = "is"` ?

**Opzioni**:
- A) Usa "is" (proposta attuale)
- B) Usa `target_tokens` se disponibile
- C) Aggiungi prefisso: `"Semantic (is)"`

**Mia raccomandazione**: A, perché se è Dictionary su "is", il nome dovrebbe essere "is".

---

### 3. Say X — Tie-break con distance uguale

**Q**: Se 2 target hanno stesso distance, quale preferire?

**Scenario**: `peak_token = ","` con direction="both"
- `target_tokens = [{"token": "Texas", "distance": 1, "backward"}, {"token": "USA", "distance": 1, "forward"}]`

**Opzioni**:
- A) Primo nell'array (backward, perché cercato prima)
- B) Preferisci sempre forward (più naturale per predizione)
- C) Preferisci sempre backward (contesto precedente)
- D) Usa activation locale (se disponibile in `target_tokens`)

**Mia raccomandazione**: B (forward), perché Say X predice il token SUCCESSIVO, quindi forward è più semanticamente corretto.

---

### 4. Say X — Nessun target trovato

**Q**: `"Say (?)"` va bene o preferisci altro?

**Opzioni**:
- A) `"Say (?)"` (proposta attuale)
- B) `"Say (unknown)"`
- C) Usa `peak_token`: `"Say (is)"` (il token funzionale stesso)
- D) Segnala per review: `"Say (REVIEW)"`

**Mia raccomandazione**: A, perché "?" è conciso e indica chiaramente che manca informazione.

---

### 5. Normalizzazione token

**Q**: Lowercase + strip va bene o serve altro?

**Considerazioni**:
- Nomi propri: "Austin" → "austin" (perde maiuscola)
- Punteggiatura: "entity:" → "entity:" (mantiene ":")
- Spazi: " Texas " → "texas"

**Opzioni**:
- A) Lowercase + strip (proposta attuale)
- B) Mantieni case originale
- C) Rimuovi anche punteggiatura trailing (es. "entity:" → "entity")

**Mia raccomandazione**: C (lowercase + strip + rimuovi punct trailing), per avere nomi più puliti.

---

### 6. Nomi duplicati

**Q**: Cosa fare se 2+ feature hanno stesso `supernode_name`?

**Scenario**: 
- `0_1861` → "texas" (Dictionary layer 0)
- `7_24743` → "texas" (Concept layer 7)

**Opzioni**:
- A) Lascia duplicati (proposta attuale) — il nome è lo stesso concetto
- B) Aggiungi suffisso: "texas_1", "texas_2"
- C) Aggiungi layer: "texas (L0)", "texas (L7)"
- D) Aggiungi subtype: "texas (Dict)", "texas (Concept)"

**Mia raccomandazione**: D (aggiungi subtype se diverso), per distinguere Dictionary da Concept quando hanno stesso token.

---

## Proposta Finale Aggiornata

Basandomi sulle mie raccomandazioni:

```python
def name_node_v2(
    feature_key: str,
    pred_label: str,
    subtype: Optional[str],
    layer: int,
    feature_records: pd.DataFrame
) -> str:
    """Versione aggiornata con raccomandazioni."""
    
    # Regola 1: Relationship
    if pred_label == "Relationship":
        return "Relationship"
    
    # Trova record con activation_max massima
    max_record = feature_records.loc[feature_records['activation_max'].idxmax()]
    
    # Regola 2: Semantic
    if pred_label == "Semantic":
        peak_token = str(max_record['peak_token']).strip().lower()
        
        # Rimuovi punteggiatura trailing
        peak_token = peak_token.rstrip(punctuation)
        
        # Casi edge
        if not peak_token or peak_token == 'nan':
            return "Semantic (unknown)"
        if is_punctuation(peak_token):
            return "Semantic (punct)"
        
        # Aggiungi subtype se Concept (per distinguere da Dictionary)
        if subtype == "Concept":
            return f"{peak_token} (Concept)"
        
        return peak_token
    
    # Regola 3: Say "X"
    if pred_label == 'Say "X"':
        target_tokens_json = max_record.get('target_tokens', '[]')
        try:
            target_tokens = json.loads(target_tokens_json)
        except:
            target_tokens = []
        
        if not target_tokens:
            return "Say (?)"
        
        if len(target_tokens) == 1:
            x = str(target_tokens[0].get('token', '?')).strip().lower().rstrip(punctuation)
            return f"Say ({x})"
        
        # Tie-break: distance minore, poi preferisci forward
        def sort_key(t):
            distance = t.get('distance', 999)
            direction = t.get('direction', '')
            # Forward ha priorità (0), backward (1)
            dir_priority = 0 if direction == 'forward' else 1
            return (distance, dir_priority)
        
        sorted_targets = sorted(target_tokens, key=sort_key)
        x = str(sorted_targets[0].get('token', '?')).strip().lower().rstrip(punctuation)
        return f"Say ({x})"
    
    return pred_label
```

---

## Test Cases Proposti

```python
# Test 1: Relationship
assert name_node("1_12928", "Relationship", None, 1, df) == "Relationship"

# Test 2: Semantic Dictionary
# peak_token = "Texas" con max activation
assert name_node("0_1861", "Semantic", "Dictionary", 0, df) == "texas"

# Test 3: Semantic Concept
# peak_token = "city" con max activation
assert name_node("7_24743", "Semantic", "Concept", 7, df) == "city (Concept)"

# Test 4: Say X con 1 target
# target_tokens = [{"token": "Austin", ...}]
assert name_node("17_98126", 'Say "X"', None, 17, df) == "Say (austin)"

# Test 5: Say X con 2 target, distance uguale
# target_tokens = [{"token": "Texas", "distance": 1, "backward"}, 
#                  {"token": "USA", "distance": 1, "forward"}]
assert name_node("17_1822", 'Say "X"', None, 17, df) == "Say (usa)"  # forward preferito

# Test 6: Say X senza target
# target_tokens = []
assert name_node("18_3623", 'Say "X"', None, 18, df) == "Say (?)"

# Test 7: Semantic con punct trailing
# peak_token = "entity:"
assert name_node("0_95057", "Semantic", "Dictionary", 0, df) == "entity"
```

---

## Decisioni Finali (Feedback Utente)

1. **Relationship**: `"(X) related"` dove X è il primo token semantico dal prompt originale con max activation ✅
2. **Semantic con subtype**: NO "(Concept)", solo il token ✅
3. **Say X tie-break**: Preferire **backward** (contesto) ✅
4. **Say X no target**: `"Say (?)"` ✅
5. **Normalizzazione**: 
   - Rimuovi punteggiatura trailing ✅
   - **NO lowercase**: Se esiste occorrenza con maiuscola, mantieni maiuscola per tutti ✅
   - Strip whitespace ✅
6. **Nomi duplicati**: OK, lasciali ✅

---

## Implementazione Finale Approvata

```python
def normalize_token(token: str, all_occurrences: List[str]) -> str:
    """
    Normalizza un token mantenendo maiuscola se presente in almeno un'occorrenza.
    
    Args:
        token: token da normalizzare
        all_occurrences: tutte le occorrenze di questo token nel dataset
        
    Returns:
        token normalizzato
    """
    # Strip whitespace
    token = str(token).strip()
    
    # Rimuovi punteggiatura trailing
    token = token.rstrip(punctuation)
    
    # Se vuoto, return
    if not token:
        return token
    
    # Controlla se esiste almeno un'occorrenza con prima lettera maiuscola
    has_uppercase = any(occ.strip()[0].isupper() for occ in all_occurrences if occ.strip())
    
    if has_uppercase:
        # Mantieni la prima occorrenza con maiuscola
        for occ in all_occurrences:
            occ_clean = occ.strip()
            if occ_clean and occ_clean[0].isupper():
                return occ_clean.rstrip(punctuation)
    
    # Altrimenti lowercase
    return token.lower()


def name_node_final(
    feature_key: str,
    pred_label: str,
    subtype: Optional[str],
    feature_records: pd.DataFrame,
    activations_data: Optional[Dict] = None
) -> str:
    """
    Assegna supernode_name a una feature (versione finale approvata).
    
    Args:
        feature_key: chiave della feature
        pred_label: classe predetta
        subtype: sottotipo (per Semantic)
        feature_records: DataFrame con tutti i record per questa feature
        activations_data: Dict con 'tokens' e 'counts' dal JSON attivazioni (per Relationship)
        
    Returns:
        supernode_name: str
    """
    # Regola 1: Relationship → "(X) related"
    if pred_label == "Relationship":
        # Trova record con activation_max massima
        max_record = feature_records.loc[feature_records['activation_max'].idxmax()]
        
        # Estrai primo token semantico con max attivazione dal prompt originale
        if activations_data and 'tokens' in activations_data and 'counts' in activations_data:
            tokens = activations_data['tokens']
            counts = activations_data['counts']  # [n_features x n_tokens]
            
            # Prompt originale: tutti i token tranne l'ultimo
            original_tokens = tokens[:-1]
            
            # Trova indice della feature nel counts
            layer, latent = feature_key.split('_')
            # (assumendo che counts sia già filtrato per questa feature)
            
            # Trova token semantici con max attivazione
            max_activation = -1
            best_token = None
            
            for idx, token in enumerate(original_tokens):
                if classify_peak_token(token) == "semantic":
                    activation = counts[idx]  # attivazione su questo token
                    if activation > max_activation:
                        max_activation = activation
                        best_token = token
            
            if best_token:
                # Normalizza (mantieni maiuscola se presente)
                all_occurrences = [best_token]
                x = normalize_token(best_token, all_occurrences)
                return f"({x}) related"
        
        # Fallback: usa peak_token del record con max activation
        peak_token = str(max_record['peak_token']).strip()
        all_occurrences = feature_records['peak_token'].astype(str).tolist()
        x = normalize_token(peak_token, all_occurrences)
        return f"({x}) related"
    
    # Trova record con activation_max massima
    max_record = feature_records.loc[feature_records['activation_max'].idxmax()]
    
    # Regola 2: Semantic → peak_token (no lowercase se ha maiuscola)
    if pred_label == "Semantic":
        peak_token = str(max_record['peak_token']).strip()
        
        # Casi edge
        if not peak_token or peak_token == 'nan':
            return "Semantic (unknown)"
        if is_punctuation(peak_token):
            return "punctuation"
        
        # Normalizza: mantieni maiuscola se presente
        all_occurrences = feature_records['peak_token'].astype(str).tolist()
        return normalize_token(peak_token, all_occurrences)
    
    # Regola 3: Say "X" → target_token (no lowercase se ha maiuscola)
    if pred_label == 'Say "X"':
        target_tokens_json = max_record.get('target_tokens', '[]')
        try:
            target_tokens = json.loads(target_tokens_json)
        except:
            target_tokens = []
        
        if not target_tokens:
            return "Say (?)"
        
        if len(target_tokens) == 1:
            x_raw = str(target_tokens[0].get('token', '?'))
            # Raccogli tutte le occorrenze di questo target
            all_x_occurrences = []
            for _, row in feature_records.iterrows():
                try:
                    row_targets = json.loads(row.get('target_tokens', '[]'))
                    for t in row_targets:
                        all_x_occurrences.append(str(t.get('token', '')))
                except:
                    pass
            x = normalize_token(x_raw, all_x_occurrences)
            return f"Say ({x})"
        
        # Tie-break: distance minore, poi preferisci BACKWARD (contesto)
        def sort_key(t):
            distance = t.get('distance', 999)
            direction = t.get('direction', '')
            # Backward ha priorità (0), forward (1)
            dir_priority = 0 if direction == 'backward' else 1
            return (distance, dir_priority)
        
        sorted_targets = sorted(target_tokens, key=sort_key)
        x_raw = str(sorted_targets[0].get('token', '?'))
        
        # Raccogli tutte le occorrenze
        all_x_occurrences = []
        for _, row in feature_records.iterrows():
            try:
                row_targets = json.loads(row.get('target_tokens', '[]'))
                for t in row_targets:
                    all_x_occurrences.append(str(t.get('token', '')))
            except:
                pass
        
        x = normalize_token(x_raw, all_x_occurrences)
        return f"Say ({x})"
    
    # Fallback
    return pred_label
```

---

## Test Cases Aggiornati

```python
# Test 1: Relationship con prompt originale
# original_prompt = "the capital of the state containing dallas is"
# Primo token semantico = "capital"
assert name_node_final("1_12928", "Relationship", None, df, 
                       "the capital of the state containing dallas is") == "(capital) related"

# Test 2: Semantic Dictionary con maiuscola
# peak_token occorrenze: ["Texas", "texas", "Texas"]
# Ha maiuscola → mantieni "Texas"
assert name_node_final("0_1861", "Semantic", "Dictionary", df) == "Texas"

# Test 3: Semantic Concept (no suffix)
# peak_token = "city"
assert name_node_final("7_24743", "Semantic", "Concept", df) == "city"

# Test 4: Say X con 1 target, maiuscola
# target_tokens = [{"token": "Austin", ...}]
assert name_node_final("17_98126", 'Say "X"', None, df) == "Say (Austin)"

# Test 5: Say X con 2 target, distance uguale, preferisci backward
# target_tokens = [{"token": "Texas", "distance": 1, "backward"}, 
#                  {"token": "USA", "distance": 1, "forward"}]
assert name_node_final("17_1822", 'Say "X"', None, df) == "Say (Texas)"  # backward preferito

# Test 6: Say X senza target
assert name_node_final("18_3623", 'Say "X"', None, df) == "Say (?)"

# Test 7: Semantic con punct trailing
# peak_token = "entity:"
assert name_node_final("0_95057", "Semantic", "Dictionary", df) == "entity"

# Test 8: Semantic con punteggiatura
# peak_token = ","
assert name_node_final("X_XXXX", "Semantic", "Dictionary", df) == "punctuation"
```

---

## Note Implementative

### 1. Prompt Originale per Relationship

**Requisito**: Serve il prompt originale completo (es. "the capital of the state containing dallas is") + JSON attivazioni

**Fonte dati**:
- JSON attivazioni (`activations_dump (2).json`) contiene:
  - `prompt`: prompt completo (es. "entity: A city in Texas, USA is Dallas")
  - `tokens`: array di token (incluso `<bos>`)
  - `counts`: matrice [n_features × n_tokens] con attivazioni
  
**Ricostruzione prompt originale**:
- Prompt completo: `"entity: A city in Texas, USA is Dallas"`
- Prompt originale: Tutto tranne l'ultimo token → `"entity: A city in Texas, USA is"`
- Logica: `tokens[:-1]` (escludi ultimo token, che è il completamento)

**Estrazione primo token semantico con max attivazione**:
1. Dal prompt originale (`tokens[:-1]`), identifica tutti i token semantici
2. Per ogni token semantico, prendi l'attivazione della feature Relationship in quel token
3. Scegli il token con attivazione massima (anche se non è il peak globale)
4. Usa quel token per naming: `"(X) related"`

**Esempio**:
```
prompt: "entity: A city in Texas, USA is Dallas"
tokens: ["<bos>", "entity", ":", " A", " city", " in", " Texas", ",", " USA", " is", " Dallas"]
original_tokens: ["<bos>", "entity", ":", " A", " city", " in", " Texas", ",", " USA", " is"]
semantic_tokens: ["entity", "city", "Texas", "USA"]

feature: 1_12928 (Relationship)
activations sui semantic tokens:
  - entity: 2.3
  - city: 1.8
  - Texas: 4.5  ← MAX
  - USA: 3.1

supernode_name: "(Texas) related"
```

**Implementazione**: Passare `activations_json_path` come parametro a `name_nodes()`

### 2. Normalizzazione Maiuscola

**Logica**: 
- Se ALMENO UN'occorrenza ha prima lettera maiuscola → usa quella con maiuscola
- Altrimenti → lowercase

**Esempio**:
- Occorrenze: ["texas", "Texas", "texas"] → "Texas"
- Occorrenze: ["austin", "austin"] → "austin"
- Occorrenze: ["Dallas", "dallas"] → "Dallas"

### 3. Tie-break Say X

**Ordine di priorità**:
1. Distance minore (più vicino al peak)
2. **Backward > Forward** (contesto precedente)

**Esempio**:
```python
targets = [
    {"token": "Texas", "distance": 1, "direction": "backward"},
    {"token": "USA", "distance": 1, "direction": "forward"}
]
# Result: "Say (Texas)" (backward ha priorità)
```

---

## Prossimi Passi

1. ✅ Feedback ricevuto
2. ⏭️ Implementare in `scripts/02_node_grouping.py`
3. ⏭️ Testare su dataset reale
4. ⏭️ Review finale

**Procedo con l'implementazione?**

