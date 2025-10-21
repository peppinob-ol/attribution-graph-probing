# Fix: Matching tra Activations JSON e CSV Node Influence

## Problema Rilevato

Le feature nel file `activations_dump (2).json` non venivano matchate correttamente con quelle nel CSV `graph_feature_static_metrics.csv`, generando l'errore:

```
❌ Nessuna feature del JSON coincide con quelle nel CSV node_influence
```

## Causa del Bug

### Logica Corretta di Matching

Il matching dovrebbe avvenire su:
- **Layer**: Estratto dal campo `source` del JSON (es. `"0-clt-hp"` → layer `0`)
- **ID**: Il campo `index` del JSON deve corrispondere alla colonna `id` (3ª colonna) del CSV

### Esempio Corretto

**JSON:**
```json
{
  "source": "0-clt-hp",
  "index": 91045
}
```

**CSV:**
```csv
layer,feature,id,ctx_idx,token,activation,...
0,4144732580,91045,7, is,2.5,...
```

**Feature Key:** `0_91045` (layer + id)

### Bug nel Codice

Il codice costruiva erroneamente la `feature_key` usando la colonna `feature` invece di `id`:

```python
# ❌ ERRATO
feats_csv['feature_key'] = feats_csv['layer'].astype(str) + '_' + feats_csv['feature'].astype(str)
# Risultato: '0_4144732580'

# ✅ CORRETTO
feats_csv['feature_key'] = feats_csv['layer'].astype(str) + '_' + feats_csv['id'].astype(str)
# Risultato: '0_91045'
```

Mentre il JSON usava già correttamente:
```python
layer = int(a['source'].split('-')[0])
idx = int(a['index'])
feature_key = f"{layer}_{idx}"  # '0_91045' ✓
```

## Correzioni Applicate

### 1. `eda/pages/01_Probe_Prompts.py` (linea 1170)

**Prima:**
```python
feats_csv['feature_key'] = feats_csv['layer'].astype(int).astype(str) + '_' + feats_csv['feature'].astype(int).astype(str)
```

**Dopo:**
```python
feats_csv['feature_key'] = feats_csv['layer'].astype(int).astype(str) + '_' + feats_csv['id'].astype(int).astype(str)
```

### 2. `eda/utils/data_loader.py` (linea 86)

**Prima:**
```python
df['feature_key'] = df['layer'].astype(str) + '_' + df['feature'].astype(str)
```

**Dopo:**
```python
df['feature_key'] = df['layer'].astype(str) + '_' + df['id'].astype(str)
```

## Verifica della Correzione

### Test Automatico

Creato test in `tests/test_feature_key_matching.py` che verifica:
1. CSV costruisce le `feature_key` correttamente usando `id`
2. JSON estrae le `feature_key` usando `source` (layer) + `index`
3. Le `feature_key` dal JSON matchano al 100% con quelle del CSV

### Risultati del Test

```
[TEST] FEATURE_KEY MATCHING

[INFO] CSV: 234 feature_key uniche su 321 righe totali
[OK] CSV feature_key corretto: 0_18753
[OK] Test CSV passed: 321 righe con feature_key corrette

[OK] Test JSON passed: 53 feature_keys estratte
   Esempio: 0_18753 OK

============================================================
TEST MATCHING JSON-CSV
============================================================
Features JSON:        53
Features CSV:         234
Match:                53 (100.0%)
Solo in JSON:         0
============================================================
[OK] Test matching passed: 100.0% match rate
[OK] Example key '0_18753' found in both JSON and CSV

[OK] TUTTI I TEST PASSATI!
```

## Note Importanti

### Feature Key Non Univoche nel CSV

La `feature_key` (layer + id) può apparire più volte nel CSV perché:
- Lo stesso nodo può attivarsi in **diversi contesti** (token positions)
- Ogni riga ha un `ctx_idx` diverso che indica la posizione del token

**Esempio:**
```csv
layer,feature,id,ctx_idx,token
0,175865634,18753,3, of
0,175865634,18753,7, is
```

Entrambe le righe hanno `feature_key = '0_18753'` ma si riferiscono a contesti diversi.

### Colonne del CSV

- `layer`: Layer del modello (-1 per embeddings)
- `feature`: Hash/ID della feature nel dataset Neuronpedia (NON usare per matching!)
- `id`: ID sequenziale del nodo nel grafo (usare per matching!)
- `ctx_idx`: Posizione del token nella sequenza
- `token`: Token dove la feature si attiva
- `activation`: Valore di attivazione
- `node_influence`: Influenza marginale del nodo sul logit finale
- `cumulative_influence`: Influenza cumulativa

## Script di Verifica

Due script sono disponibili per verificare il matching:

1. **`scripts/verify_json_csv_match.py`**: Verifica dettagliata con report JSON
2. **`tests/test_feature_key_matching.py`**: Test automatico con assertions

## Conclusione

Con queste correzioni:
- ✅ 100% delle feature nel JSON matchano con quelle nel CSV
- ✅ Il grafico "Top Features by Node Influence" ora funziona correttamente
- ✅ L'analisi di causalità può procedere con i dati corretti

## Data

21 Ottobre 2025

