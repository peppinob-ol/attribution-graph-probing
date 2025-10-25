# Feature: Total Influence per Supernode Name

**Data**: 2025-10-25  
**Status**: ✅ Implementato  

---

## Descrizione

La sezione **"🔍 Analisi per Supernode Name"** nella pagina Streamlit ora include una nuova colonna **"Total Influence"** che mostra la somma di `node_influence` per ogni `supernode_name`.

### Logica

1. **Prendi `node_influence` una volta per feature**: 
   - Ogni `feature_key` ha lo stesso valore di `node_influence` su tutte le righe (probe prompts)
   - Usiamo `groupby('feature_key')['node_influence'].first()` per prendere 1 valore per feature

2. **Mappa feature → supernode_name**:
   - Ogni `feature_key` ha un `supernode_name` assegnato
   - Usiamo `groupby('feature_key')['supernode_name'].first()`

3. **Somma per supernode_name**:
   - Raggruppiamo per `supernode_name` e sommiamo `node_influence`
   - `total_influence = sum(node_influence for each feature in supernode)`

4. **Ordina per Total Influence**:
   - I supernodi sono ordinati per `Total Influence` decrescente
   - Questo mostra quali supernodi hanno maggiore importanza causale nel grafo

---

## Esempio

### Dataset

```csv
feature_key,supernode_name,node_influence,prompt
20_44686,Texas,0.85,entity: A city in Texas, USA is Dallas
20_44686,Texas,0.85,entity: The capital city of Texas is Austin
20_44686,Texas,0.85,entity: A state in the United States is Texas
7_3144,Austin,0.62,entity: A city in Texas, USA is Dallas
7_3144,Austin,0.62,entity: The capital city of Texas is Austin
1_12928,(Texas) related,0.45,entity: A city in Texas, USA is Dallas
1_12928,(Texas) related,0.45,entity: The capital city of Texas is Austin
```

### Step 1: Prendi node_influence per feature

```python
feature_influence = df.groupby('feature_key')['node_influence'].first()

# Risultato:
# feature_key  node_influence
# 20_44686     0.85
# 7_3144       0.62
# 1_12928      0.45
```

### Step 2: Mappa feature → supernode_name

```python
feature_to_name = df.groupby('feature_key')['supernode_name'].first()

# Risultato:
# feature_key  supernode_name
# 20_44686     Texas
# 7_3144       Austin
# 1_12928      (Texas) related
```

### Step 3: Merge e somma per supernode_name

```python
feature_influence = feature_influence.merge(feature_to_name, on='feature_key')

# Risultato:
# feature_key  node_influence  supernode_name
# 20_44686     0.85            Texas
# 7_3144       0.62            Austin
# 1_12928      0.45            (Texas) related

name_influence = feature_influence.groupby('supernode_name')['node_influence'].sum()

# Risultato:
# supernode_name    total_influence
# Texas             0.85
# Austin            0.62
# (Texas) related   0.45
```

### Step 4: Tabella finale

```
Supernode Name    | N Features | Classe        | Layer Range | Total Influence
------------------|------------|---------------|-------------|----------------
Texas             | 1          | Semantic      | 20          | 0.85
Austin            | 1          | Semantic      | 7           | 0.62
(Texas) related   | 1          | Relationship  | 1           | 0.45
```

**Ordinata per Total Influence decrescente** ✅

---

## Caso con Feature Multiple nello Stesso Supernode

### Dataset

```csv
feature_key,supernode_name,node_influence,prompt
20_44686,Texas,0.85,entity: A city in Texas, USA is Dallas
20_44686,Texas,0.85,entity: The capital city of Texas is Austin
22_11998,Texas,0.73,entity: A city in Texas, USA is Dallas
22_11998,Texas,0.73,entity: The capital city of Texas is Austin
7_3144,Austin,0.62,entity: A city in Texas, USA is Dallas
```

### Calcolo

```python
# Step 1: node_influence per feature
feature_influence:
  20_44686 → 0.85
  22_11998 → 0.73
  7_3144   → 0.62

# Step 2: supernode_name per feature
feature_to_name:
  20_44686 → Texas
  22_11998 → Texas
  7_3144   → Austin

# Step 3: Somma per supernode_name
name_influence:
  Texas  → 0.85 + 0.73 = 1.58  ← Somma di 2 feature!
  Austin → 0.62
```

### Tabella finale

```
Supernode Name | N Features | Classe    | Layer Range | Total Influence
---------------|------------|-----------|-------------|----------------
Texas          | 2          | Semantic  | 20-22       | 1.58
Austin         | 1          | Semantic  | 7           | 0.62
```

**"Texas" ha Total Influence più alta perché include 2 feature!** ✅

---

## Implementazione

### Codice

```python
# Calcola node_influence per feature (prendi 1 valore per feature, non tutte le righe)
if 'node_influence' in df_named.columns:
    # Prendi node_influence per ogni feature_key (usa il primo valore, sono tutti uguali per la stessa feature)
    feature_influence = df_named.groupby('feature_key')['node_influence'].first().reset_index()
    
    # Aggiungi supernode_name per ogni feature
    feature_to_name = df_named.groupby('feature_key')['supernode_name'].first().reset_index()
    feature_influence = feature_influence.merge(feature_to_name, on='feature_key')
    
    # Somma node_influence per supernode_name
    name_influence = feature_influence.groupby('supernode_name')['node_influence'].sum().reset_index()
    name_influence.columns = ['supernode_name', 'total_influence']
else:
    name_influence = None

# Aggregazioni base
name_groups = df_named.groupby('supernode_name').agg({
    'feature_key': 'nunique',
    'pred_label': lambda x: x.mode()[0] if len(x) > 0 else '',
    'layer': lambda x: f"{x.min()}-{x.max()}" if x.min() != x.max() else str(x.min())
}).reset_index()
name_groups.columns = ['Supernode Name', 'N Features', 'Classe', 'Layer Range']

# Aggiungi total_influence se disponibile
if name_influence is not None:
    name_groups = name_groups.merge(
        name_influence.rename(columns={'supernode_name': 'Supernode Name', 'total_influence': 'Total Influence'}),
        on='Supernode Name',
        how='left'
    )
    # Ordina per Total Influence (decrescente)
    name_groups = name_groups.sort_values('Total Influence', ascending=False)
else:
    name_groups = name_groups.sort_values('N Features', ascending=False)

st.dataframe(name_groups, use_container_width=True)
```

### Gestione Edge Cases

1. **`node_influence` non presente nel CSV**:
   - `name_influence = None`
   - Tabella ordinata per `N Features` invece di `Total Influence`
   - Nessuna colonna `Total Influence` mostrata

2. **Feature con `node_influence` mancante (NaN)**:
   - `.first()` prende il primo valore non-NaN se disponibile
   - Se tutti NaN, la somma sarà NaN
   - Ordinamento gestisce NaN correttamente (li mette alla fine)

3. **Supernode con 0 feature** (non dovrebbe succedere):
   - Non appare nella tabella (groupby esclude automaticamente)

---

## Benefici

### 1. Identificazione Supernodi Importanti

I supernodi con **Total Influence** alta sono quelli che:
- Hanno maggiore impatto causale sul grafo
- Includono feature con alto `node_influence`
- Sono candidati per analisi approfondita

**Esempio**:
```
Supernode Name     | N Features | Total Influence
-------------------|------------|----------------
(capital) related  | 3          | 2.45  ← Alta influenza!
Texas              | 2          | 1.58
Austin             | 1          | 0.62
```

### 2. Confronto Supernodi

Possiamo confrontare supernodi con stesso `N Features` ma diverso `Total Influence`:

```
Supernode Name | N Features | Total Influence
---------------|------------|----------------
Texas          | 2          | 1.58  ← Più influente
Dallas         | 2          | 0.92  ← Meno influente
```

**Interpretazione**: "Texas" ha feature con `node_influence` più alta, quindi è più importante causalmente.

### 3. Prioritizzazione Analisi

Ordina i supernodi per importanza causale:
1. Analizza prima i supernodi con `Total Influence` alta
2. Ignora supernodi con `Total Influence` bassa (meno rilevanti)

---

## Testing

### Test Manuale

```python
# Verifica che node_influence sia preso 1 volta per feature
feature_counts = df_named.groupby('feature_key').size()
influence_per_feature = df_named.groupby('feature_key')['node_influence'].first()

assert len(influence_per_feature) == len(feature_counts)  # 1 valore per feature

# Verifica somma per supernode
name_influence = feature_influence.groupby('supernode_name')['node_influence'].sum()

# Esempio: "Texas" ha 2 feature (20_44686, 22_11998)
assert name_influence['Texas'] == 0.85 + 0.73  # = 1.58
```

### Test Automatico

```python
def test_supernode_influence():
    """Verifica calcolo Total Influence per supernode"""
    df = pd.DataFrame({
        'feature_key': ['20_44686', '20_44686', '22_11998', '22_11998', '7_3144'],
        'supernode_name': ['Texas', 'Texas', 'Texas', 'Texas', 'Austin'],
        'node_influence': [0.85, 0.85, 0.73, 0.73, 0.62],
        'prompt': ['p1', 'p2', 'p1', 'p2', 'p1']
    })
    
    # Calcola
    feature_influence = df.groupby('feature_key')['node_influence'].first().reset_index()
    feature_to_name = df.groupby('feature_key')['supernode_name'].first().reset_index()
    feature_influence = feature_influence.merge(feature_to_name, on='feature_key')
    name_influence = feature_influence.groupby('supernode_name')['node_influence'].sum()
    
    # Verifica
    assert name_influence['Texas'] == 1.58  # 0.85 + 0.73
    assert name_influence['Austin'] == 0.62
```

---

## Conclusione

La nuova colonna **"Total Influence"** permette di:

1. ✅ **Identificare supernodi importanti** (alta influenza causale)
2. ✅ **Confrontare supernodi** con stesso numero di feature
3. ✅ **Prioritizzare l'analisi** sui supernodi più rilevanti
4. ✅ **Ordinare automaticamente** per importanza causale

**Risultato**: Analisi più efficace e focalizzata sui supernodi che contano! 🎯

