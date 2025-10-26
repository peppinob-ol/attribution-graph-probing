# Feature: Embeddings e Logit Target nei PinnedIds

**Data**: 2025-10-26  
**Status**: ✅ Implementato  

---

## Descrizione

Oltre ai nodi feature selezionati, il subgrafo su Neuronpedia deve includere anche:
1. **Embeddings** (layer "E"): Token di input
2. **Logit Target**: Token predetto con probabilità più alta

Questi nodi sono essenziali per visualizzare il grafo completo (input → features → output).

---

## Implementazione

### Logica Aggiunta

```python
# Dopo aver raccolto i feature nodes...

# Raccogli tutti i supernode_name (normalizzati a lowercase per matching)
supernode_names_lower = set()
for supernode_name in set(feature_to_supernode.values()):
    if supernode_name:
        supernode_names_lower.add(supernode_name.strip().lower())

# Estrai prompt_tokens per mappare ctx_idx → token
prompt_tokens = metadata.get('prompt_tokens', [])

# Aggiungi embeddings e logit target dal Graph JSON
embeddings_and_logits = []
for node in nodes:
    node_id = node.get('node_id', '')
    feature_type = node.get('feature_type', '')
    is_target_logit = node.get('is_target_logit', False)
    
    # Aggiungi embeddings (layer "E") SOLO se il token corrisponde a un supernode_name
    if feature_type == 'embedding':
        ctx_idx = node.get('ctx_idx', -1)
        if 0 <= ctx_idx < len(prompt_tokens):
            token = prompt_tokens[ctx_idx].strip().lower()
            if token in supernode_names_lower:  # ← Filtro!
                embeddings_and_logits.append(node_id)
    
    # Aggiungi logit target
    elif feature_type == 'logit' and is_target_logit:
        embeddings_and_logits.append(node_id)

# Combina feature nodes + embeddings + logits
pinned_ids.extend(embeddings_and_logits)
```

### Esempi di Nodi

**Embedding**:
```json
{
  "node_id": "E_2_0",
  "feature": 0,
  "layer": "E",
  "ctx_idx": 0,
  "feature_type": "embedding",
  "influence": 0.069,
  "activation": null
}
```

**Logit Target**:
```json
{
  "node_id": "27_22605_7",
  "feature": 22605,
  "layer": "27",
  "ctx_idx": 7,
  "feature_type": "logit",
  "token_prob": 0.332,
  "is_target_logit": true,
  "clerp": "Output \" Austin\" (p=0.332)"
}
```

---

## Output Verbose

```
=== Upload Subgrafo su Neuronpedia ===
  Graph JSON: 322 nodi, 43 feature uniche
  Supernodes: 13 gruppi
    - Totale nodi raggruppati: 50
  
  PinnedIds (features): 50 nodi (da selected_nodes_data, filtrati per supernodes)
    - Nodi totali in selected_nodes_data: 50
    - Nodi feature nei supernodes: 50
  
  PinnedIds (embeddings + logits): +4 nodi  ← NUOVO! (filtrati)
    - Embeddings filtrati: 3 (solo "capital", "is", "of")
    - Logit target: 1 (" Austin")
  PinnedIds (totale): 54 nodi
```

**Breakdown**:
- 50 nodi feature (selezionati con slider)
- 3 embeddings (solo token che corrispondono a supernode_name: "capital", "is", "of")
- 1 logit target (token predetto: " Austin")
- **Totale: 54 nodi**

**Embeddings esclusi**: "The", "state", "containing", "Dallas" (non hanno supernode corrispondente)

---

## Benefici

1. ✅ **Grafo Completo**: Visualizza input → features → output
2. ✅ **Context Visibile**: Embeddings mostrano i token di input
3. ✅ **Predizione Visibile**: Logit target mostra il token predetto
4. ✅ **Interpretabilità**: Più facile capire il flusso del grafo

---

## Esempio Visivo

```
Input (Embeddings - FILTRATI)
  E_2_1 ("capital") ✅ → ha supernode "capital"
  E_2_2 ("of") ✅ → ha supernode "of"
  E_2_4 ("is") ✅ → ha supernode "is"
  
  E_2_0 ("The") ❌ → nessun supernode corrispondente
  E_2_3 ("state") ❌ → nessun supernode corrispondente
  ...
    ↓
Features (Supernodes)
  Texas (20_44686)
  (capital) related (1_12928)
  Say (Austin) (7_3144)
  capital (1 feature)
  is (1 feature)
  of (1 feature)
  ...
    ↓
Output (Logit Target)
  27_22605_7 (" Austin", p=0.332) ✅ → sempre incluso
```

**Logica**: Un embedding viene pinnato solo se il suo token corrisponde a un `supernode_name` esistente. Questo evita di pinnare token irrilevanti come "the" che non hanno un supernode dedicato.

---

## Edge Cases

### Caso 1: Nessun Embedding Corrispondente

Se nessun token di input corrisponde a un supernode_name:
```python
if token in supernode_names_lower:
    embeddings_and_logits.append(node_id)
# → Lista vuota per embeddings, solo logit target
```

**Esempio**: Se i supernodes sono solo "Say (Austin)", "(Texas) related", nessun embedding viene aggiunto (nessun token di input corrisponde esattamente).

### Caso 2: Multipli Logit Target

Se ci sono più logit con `is_target_logit=True` (possibile):
```python
elif feature_type == 'logit' and is_target_logit:
    embeddings_and_logits.append(node_id)
# → Tutti vengono aggiunti
```

### Caso 3: Nessun Logit Target

Se nessun logit ha `is_target_logit=True`:
```python
# → Lista contiene solo embeddings filtrati, nessun errore
```

### Caso 4: Token con Capitalizzazione Diversa

Se il supernode è "Texas" ma l'embedding è " texas":
```python
token = prompt_tokens[ctx_idx].strip().lower()  # → "texas"
supernode_names_lower.add(supernode_name.strip().lower())  # → "texas"
# → Match! ✅
```

**Normalizzazione**: Sia il token che il supernode_name sono convertiti a lowercase per il matching.

---

## Testing

### Test 1: Verifica Embeddings

```python
# Conta embeddings nel Graph JSON
embeddings = [n for n in nodes if n['feature_type'] == 'embedding']
assert len(embeddings) == len(prompt_tokens)  # Uno per token
```

### Test 2: Verifica Logit Target

```python
# Conta logit target
logit_targets = [n for n in nodes if n['feature_type'] == 'logit' and n['is_target_logit']]
assert len(logit_targets) >= 1  # Almeno uno
```

### Test 3: Verifica PinnedIds

```python
# Verifica che embeddings e logits siano nei pinnedIds
pinned_ids = upload_subgraph_to_neuronpedia(...)
assert any(pid.startswith('E_') for pid in pinned_ids)  # Embeddings
assert any('_target_logit' in pid or 'logit' in pid for pid in pinned_ids)  # Logits (formato varia)
```

---

## Conclusione

Il subgrafo ora include:
1. ✅ **Feature nodes selezionati** (con slider)
2. ✅ **Embeddings** (input tokens)
3. ✅ **Logit target** (output token)

**Risultato**: Visualizzazione completa del flusso input → features → output! 🎉

