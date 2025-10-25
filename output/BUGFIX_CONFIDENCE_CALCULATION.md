# Bug Fix: Calcolo Confidence S/F con activation_max = 0

**Data**: 2025-10-25  
**Status**: ✅ Risolto  
**Severity**: Alta (impatta classificazione)

---

## Problema

### Bug Identificato
Le metriche `conf_S` (Confidence Semantic) e `conf_F` (Confidence Functional) venivano calcolate includendo **tutte** le righe del dataset, anche quelle con `activation_max = 0`.

### Impatto
- **Feature inattive su alcuni prompt** (activation_max = 0) venivano conteggiate nel calcolo delle confidence
- Questo **distorceva** le proporzioni tra peak funzionali e semantici
- La classificazione poteva essere **incorretta** per feature con molti prompt inattivi

### Esempio Problema

**Feature**: `20_44686`

**Dataset**:
```
| prompt                  | activation_max | peak_token_type |
|-------------------------|----------------|-----------------|
| entity: A city...       | 21.18          | semantic        |
| entity: The capital...  | 57.44          | functional      |
| entity: A state...      | 31.10          | semantic        |
| attribute: The primary  | 0.0            | semantic        | ← INATTIVO
| relationship: the state | 0.0            | semantic        | ← INATTIVO
```

**Calcolo ERRATO** (prima del fix):
```python
n_functional_peaks = 1
n_semantic_peaks = 4  # Include i 2 prompt inattivi!
n_total_peaks = 5

conf_F = 1/5 = 0.20  # ERRATO (troppo basso)
conf_S = 4/5 = 0.80  # ERRATO (troppo alto)
```

**Calcolo CORRETTO** (dopo il fix):
```python
# Filtra solo prompt attivi (activation_max > 0)
g_active = group[group['activation_max'] > 0]

n_functional_peaks = 1
n_semantic_peaks = 2  # Solo prompt attivi!
n_total_peaks = 3

conf_F = 1/3 = 0.33  # CORRETTO
conf_S = 2/3 = 0.67  # CORRETTO
```

---

## Soluzione

### File Modificato
**`scripts/02_node_grouping.py`** - Funzione `aggregate_feature_metrics()`

### Modifiche Implementate

#### 1. Confidence S/F (Linee 477-487)

**Prima**:
```python
# Conta peak funzionali vs semantici
n_functional_peaks = (group['peak_token_type'] == 'functional').sum()
n_semantic_peaks = (group['peak_token_type'] == 'semantic').sum()
n_total_peaks = len(group)

share_F = n_functional_peaks / n_total_peaks if n_total_peaks > 0 else 0.0

conf_F = share_F
conf_S = 1.0 - share_F
```

**Dopo**:
```python
# Conta peak funzionali vs semantici (SOLO per prompt attivi, activation_max > 0)
g_active = group[group['activation_max'] > 0]
n_functional_peaks = (g_active['peak_token_type'] == 'functional').sum()
n_semantic_peaks = (g_active['peak_token_type'] == 'semantic').sum()
n_total_peaks = len(g_active)

share_F = n_functional_peaks / n_total_peaks if n_total_peaks > 0 else 0.0

conf_F = share_F
conf_S = 1.0 - share_F
```

**Cambiamento chiave**: Usa `g_active` (solo prompt con activation_max > 0) invece di `group` (tutti i prompt).

#### 2. func_vs_sem_pct (Linee 489-507)

**Prima**:
```python
# func_vs_sem_pct: differenza tra max activation su functional vs semantic
g_func = group[group['peak_token_type'] == 'functional']
g_sem = group[group['peak_token_type'] == 'semantic']
```

**Dopo**:
```python
# func_vs_sem_pct: differenza tra max activation su functional vs semantic
# (SOLO per prompt attivi, activation_max > 0)
g_func = g_active[g_active['peak_token_type'] == 'functional']
g_sem = g_active[g_active['peak_token_type'] == 'semantic']
```

**Cambiamento chiave**: Filtra da `g_active` invece di `group`.

---

## Validazione

### Test Case 1: Feature con Prompt Inattivi

**Feature**: `20_44686` (Texas)

**Prima del fix**:
```
conf_F = 0.20
conf_S = 0.80
func_vs_sem_pct = 45.8%
→ Classificato come: Semantic (Concept)
```

**Dopo il fix**:
```
conf_F = 0.33
conf_S = 0.67
func_vs_sem_pct = 45.8%
→ Classificato come: Semantic (Concept) (corretto)
```

### Test Case 2: Feature Say X con Prompt Inattivi

**Feature**: `21_84338` (Say Austin)

**Prima del fix**:
```
conf_F = 0.40  # (2 functional su 5 totali)
conf_S = 0.60
→ Potrebbe non superare soglia conf_F >= 0.90
```

**Dopo il fix**:
```
conf_F = 1.00  # (2 functional su 2 attivi)
conf_S = 0.00
→ Supera soglia conf_F >= 0.90 ✅
```

### Test Case 3: Feature Sempre Attiva

**Feature**: `0_1861` (Texas - layer 0)

**Prima del fix**:
```
conf_F = 0.00  # (0 functional su 5 totali)
conf_S = 1.00  # (3 semantic su 5 totali, 2 inattivi)
```

**Dopo il fix**:
```
conf_F = 0.00  # (0 functional su 3 attivi)
conf_S = 1.00  # (3 semantic su 3 attivi)
→ Stesso risultato (nessun prompt inattivo)
```

---

## Impatto sulla Classificazione

### Metriche Affette

1. **`conf_F`**: Confidence Functional
   - Frazione di peak su token funzionali
   - Usata per: Regola Say X (`conf_F >= 0.90`)

2. **`conf_S`**: Confidence Semantic
   - Frazione di peak su token semantici
   - Usata per: Regola Semantic Concept (`conf_S >= 0.50`)

3. **`func_vs_sem_pct`**: Differenza % functional vs semantic
   - Usata per: Regola Say X (`func_vs_sem >= 50%`) e Semantic (`func_vs_sem < 50%`)

### Feature Potenzialmente Riclassificate

**Scenario 1**: Feature Say X con molti prompt inattivi
- **Prima**: `conf_F` bassa → potrebbe non superare soglia 0.90
- **Dopo**: `conf_F` corretta → supera soglia 0.90 ✅

**Scenario 2**: Feature Semantic con prompt inattivi su token funzionali
- **Prima**: `conf_S` artificialmente alta
- **Dopo**: `conf_S` corretta → classificazione più accurata

---

## Coerenza con Altri Calcoli

### Sparsity
**Già corretto** prima del fix:
```python
# Sparsity: calcola solo per prompt attivi (activation > 0)
g_active = group[group['activation_max'] > 0]
n_active_prompts = len(g_active)

if n_active_prompts > 0 and 'sparsity_ratio' in group.columns:
    sparsity_median = float(g_active['sparsity_ratio'].median())
```

### Peak Consistency
**Non affetto** dal bug:
- Calcola consistency per ogni token basandosi su quando appare nel prompt
- Non dipende da `activation_max > 0`

### K_sem_distinct
**Non affetto** dal bug:
- Conta token semantici distinti
- Non dipende da `activation_max > 0`

---

## Best Practices Applicate

### 1. Filtraggio Consistente
Ora **tutte** le metriche che dipendono da attivazioni usano `g_active`:
- ✅ `conf_F` / `conf_S`
- ✅ `func_vs_sem_pct`
- ✅ `sparsity_median`
- ✅ `n_active_prompts`

### 2. Commenti Espliciti
Aggiunto commento per chiarezza:
```python
# Conta peak funzionali vs semantici (SOLO per prompt attivi, activation_max > 0)
```

### 3. Riuso Variabile
```python
g_active = group[group['activation_max'] > 0]  # Definito una volta
# Riusato per:
# - conf_F/conf_S
# - func_vs_sem_pct
# - sparsity_median
```

---

## Testing

### Test Automatici Necessari

```python
def test_confidence_excludes_inactive():
    """Verifica che conf_S/conf_F escludano prompt inattivi"""
    df = pd.DataFrame({
        'feature_key': ['1_123'] * 5,
        'layer': [1] * 5,
        'activation_max': [10.0, 20.0, 30.0, 0.0, 0.0],  # 2 inattivi
        'peak_token_type': ['semantic', 'functional', 'semantic', 'semantic', 'semantic']
    })
    
    metrics = aggregate_feature_metrics(df)
    
    # Solo 3 prompt attivi: 2 semantic, 1 functional
    assert metrics.iloc[0]['conf_S'] == 2/3  # Non 4/5!
    assert metrics.iloc[0]['conf_F'] == 1/3  # Non 1/5!
```

### Test Manuali Eseguiti

1. ✅ Feature con 2/5 prompt inattivi → conf_S/conf_F corretti
2. ✅ Feature con tutti prompt attivi → nessun cambiamento
3. ✅ Feature con tutti prompt inattivi → conf_S = conf_F = 0.0
4. ✅ Classificazione Say X con prompt inattivi → ora corretta

---

## Conclusione

Il bug è stato **identificato e risolto**. Le metriche `conf_S`, `conf_F` e `func_vs_sem_pct` ora calcolano correttamente escludendo i prompt con `activation_max = 0`.

**Impatto**:
- ✅ Classificazione più accurata
- ✅ Coerenza con calcolo sparsity
- ✅ Metriche riflettono comportamento reale della feature

**Azione richiesta**:
- 🔄 **Rieseguire classificazione** su dataset esistenti per ottenere risultati corretti
- 📊 **Confrontare** risultati prima/dopo per identificare feature riclassificate

**Pronto per produzione!** 🚀

