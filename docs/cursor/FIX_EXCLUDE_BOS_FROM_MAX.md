# Fix: Esclusione BOS dal Calcolo del Max Activation

**Data**: 21 Ottobre 2025

## Problema Identificato

Nel calcolare `max_value` e `max_value_index` dal JSON delle activations, veniva considerato anche il **primo elemento** dell'array `values`, che corrisponde sempre al token `<bos>`.

### Esempio Concreto (dall'utente)

```json
"values": [
  424.1778259277344,   ← BOS (indice 0) - DA ESCLUDERE!
  105.41461181640625,  ← Vero max (indice 1)
  68.2294921875,
  78.88206481933594,
  ...
]
```

**Comportamento errato**: 
- `max_value` = 424.17 (indice 0 = BOS) ❌

**Comportamento corretto**:
- `max_value` = 105.41 (indice 1) ✅
- Escludere indice 0 dal calcolo

## Impatto sui Dati

Dal test sui dati reali (`activations_dump (2).json`):

```
Features totali: 53
BOS era il max: 32 (60.4%)  ← Queste erano SBAGLIATE!
BOS non era max: 21 (39.6%)
```

**Il 60% delle features** aveva il valore BOS come massimo, quindi la correzione ha un impatto significativo!

## Soluzione Implementata

### Modifica al Codice

**File**: `eda/pages/01_Probe_Prompts.py`

**Prima** (usava i valori pre-calcolati dal JSON):
```python
max_value = a.get('max_value', None)
max_idx = a.get('max_value_index', None)
```

**Dopo** (calcola escludendo BOS):
```python
# Estrai values e calcola max ESCLUDENDO il primo elemento (BOS)
values = a.get('values', [])
if len(values) > 1:
    # Escludi indice 0 (BOS), trova max tra gli altri
    values_no_bos = values[1:]
    max_value = max(values_no_bos) if values_no_bos else None
    # Indice relativo a values_no_bos, aggiungi 1 per l'offset
    max_idx = values_no_bos.index(max_value) + 1 if max_value is not None else None
else:
    max_value = None
    max_idx = None
```

### Sezioni Modificate

La correzione è stata applicata in **2 posti** nel file:

1. **Linee 1196-1206**: Costruzione di `act_df` per il grafico
   - Usato per aggregare activations per feature/prompt
   - Genera i dati per il grafico "Main Chart: Importance vs Activation"

2. **Linee 1262-1275**: Costruzione della tabella di verifica
   - Usato per mostrare i dati grezzi nella tabella espandibile
   - Include informazioni dettagliate per debug

## Documentazione Aggiornata

### Caption del Grafico Principale

Aggiunto chiarimento sulla caption:

```python
st.caption("""
**Grafico a barre**: Features ordinate per importanza causale (node_influence).
Altezza barra = peak activation (max_value, **escludendo BOS**). Colore = prompt.
Linea rossa = node_influence score.
""")
```

### Note nella Tabella di Verifica

```python
st.caption("""
**Note importanti**:
- `activation_max` è calcolata **ESCLUDENDO** il token BOS (primo elemento di values)
- `peak_token_idx` è la posizione del picco (1+ per esclusione BOS)
- ...
""")
```

## Test Automatico

**Script**: `scripts/test_max_excluding_bos.py`

### Esecuzione

```bash
python scripts/test_max_excluding_bos.py
```

### Output Esempio

```
[1] Feature: 0-clt-hp, index=18753
    values[0] (BOS): 0.00

    VECCHIO (con BOS):
      max_value: 61.58
      max_idx: 7
      token: ,

    NUOVO (senza BOS):
      max_value: 61.58
      max_idx: 7
      token: ,
      -> [OK] Stesso risultato (BOS non era il max)
```

### Verifica Esempio Utente

```
Values: [424.17..., 105.41..., 68.22..., ...]
values[0] (BOS): 424.1778259277344

METODO VECCHIO (con BOS):
  max_value: 424.1778259277344 (indice 0)  ❌

METODO NUOVO (senza BOS):
  max_value: 105.41461181640625 (indice 1)  ✅
  [OK] Conferma: indice 1, valore 105.41461181640625
```

## Impatto sulla Visualizzazione

### Prima della Correzione

- **60% delle features** mostravano activation sbagliata (valore BOS)
- Grafici ingannevoli con picchi artificiali su BOS
- `peak_token` mostrava `<bos>` per 32/53 features
- Node influence comparato con activation sbagliata

### Dopo la Correzione

- ✅ Activation corretta per tutte le features
- ✅ `peak_token` ora mostra il vero token di picco (non BOS)
- ✅ Grafici accurati e significativi
- ✅ Confronto node_influence vs activation ora è corretto

## Colonne nella Tabella di Verifica

| Colonna           | Descrizione                                     | Note           |
|-------------------|-------------------------------------------------|----------------|
| `activation_max`  | Max attivazione **escludendo BOS**              | CORRETTO ✅    |
| `peak_token_idx`  | Indice del picco (1+ per esclusione BOS)        | Range: 1 a T-1 |
| `peak_token`      | Token dove la feature ha il picco               | Mai `<bos>`    |
| `node_influence`  | Max influenza causale dal CSV                   | -              |
| `csv_ctx_idx`     | Contesto dove node_influence è massima          | -              |

## Logica del Calcolo

### Array `values` nel JSON

```
Index:  0      1       2       3       4    ...
Token: <bos> entity    :      A      city  ...
Value: 424.1  105.4   68.2   78.8   74.5   ...
       ↑      ↑
       SKIP   START HERE (max search)
```

### Algoritmo

1. Prendi l'array `values` completo
2. **Escludi** `values[0]` (BOS)
3. Crea `values_no_bos = values[1:]`
4. Trova `max_value = max(values_no_bos)`
5. Trova indice in `values_no_bos`: `idx_in_subset`
6. Converti a indice originale: `max_idx = idx_in_subset + 1`

### Perché +1?

```python
values = [424.1, 105.4, 68.2, 78.8, ...]
         [  0  ,   1  ,  2  ,  3  , ...]  ← indici originali

values_no_bos = [105.4, 68.2, 78.8, ...]
                [  0  ,  1  ,  2  , ...]  ← indici in subset

max_value = 105.4 in values_no_bos
idx_in_subset = 0
max_idx = 0 + 1 = 1  ← indice corretto in array originale
```

## Note Importanti

### Relazione con Filtro BOS

**Attenzione**: Questa correzione è **diversa** dal filtro BOS nell'UI!

- **Filtro BOS nell'UI** (`exclude_bos` checkbox):
  - Rimuove features dove il `peak_token` è `<bos>`
  - Applicato DOPO il calcolo corretto
  - Feature opzionale per l'utente

- **Esclusione BOS dal calcolo**:
  - Calcola il max **sempre** escludendo indice 0
  - Non è opzionale, è la logica corretta
  - Garantisce che `peak_token` non sia mai `<bos>` (a meno che non ci siano solo valori zero)

### Edge Cases

**Caso 1**: Array con un solo elemento
```python
values = [424.1]  # Solo BOS
values_no_bos = []
max_value = None  # Corretto: nessun valore non-BOS
```

**Caso 2**: Tutti valori zero tranne BOS
```python
values = [424.1, 0.0, 0.0, 0.0]
values_no_bos = [0.0, 0.0, 0.0]
max_value = 0.0  # Corretto: il max è zero
max_idx = 1      # Corretto: primo elemento non-BOS
```

**Caso 3**: Array vuoto
```python
values = []
# Gestito: max_value = None, max_idx = None
```

## Conclusioni

✅ **Correzione critica applicata**: BOS ora escluso dal calcolo del max  
✅ **Test automatico**: Verifica con dati reali (60% di features corrette!)  
✅ **Documentazione aggiornata**: Caption e note esplicative  
✅ **Impatto significativo**: 32/53 features (60%) avevano il valore sbagliato  
✅ **Backward compatible**: Non richiede rigenerazione dei JSON  

La correzione garantisce che i grafici e le analisi riflettano il **vero comportamento** delle features, escludendo l'artefatto del token BOS che non è significativo per l'analisi causale.

## File Modificati

1. ✅ `eda/pages/01_Probe_Prompts.py` - Correzione in 2 sezioni + documentazione
2. ✅ `scripts/test_max_excluding_bos.py` - Test con dati reali
3. ✅ `docs/cursor/FIX_EXCLUDE_BOS_FROM_MAX.md` - Questo documento

