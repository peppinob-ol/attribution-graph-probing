# Riepilogo Sessione: Fix Feature Key Matching & Tabella Verifica

**Data**: 21 Ottobre 2025

## Problema Iniziale

L'utente ha segnalato l'errore:
```
❌ Nessuna feature del JSON coincide con quelle nel CSV node_influence
```

## 1. Diagnosi del Bug

### Causa Identificata

Il matching tra activations JSON e CSV node_influence usava colonne sbagliate:

**Logica Corretta:**
- JSON: `layer` (estratto da `source`) + `index` → `feature_key = "0_18753"`
- CSV: `layer` + `id` (colonna 3) → `feature_key = "0_18753"`

**Bug nel Codice:**
- CSV usava `layer` + `feature` (colonna 2) → `feature_key = "0_4144732580"` ❌

### Esempio Concreto

**JSON:**
```json
{
  "source": "0-clt-hp",
  "index": 91045
}
```

**CSV:**
```csv
layer,feature,id,ctx_idx,token,...
0,4144732580,91045,7, is,...
```

**Feature Key corretta:** `0_91045` (non `0_4144732580`)

## 2. Correzioni Applicate

### File Modificati

#### A. `eda/pages/01_Probe_Prompts.py` (linea 1170)

**Prima:**
```python
feats_csv['feature_key'] = feats_csv['layer'].astype(int).astype(str) + '_' + feats_csv['feature'].astype(int).astype(str)
```

**Dopo:**
```python
feats_csv['feature_key'] = feats_csv['layer'].astype(int).astype(str) + '_' + feats_csv['id'].astype(int).astype(str)
```

#### B. `eda/utils/data_loader.py` (linea 86)

**Prima:**
```python
df['feature_key'] = df['layer'].astype(str) + '_' + df['feature'].astype(str)
```

**Dopo:**
```python
df['feature_key'] = df['layer'].astype(str) + '_' + df['id'].astype(str)
```

**Nota:** Questa funzione attualmente non è usata, ma è stata corretta per consistenza.

### Verifica della Correzione

**Script di test:** `tests/test_feature_key_matching.py`

**Risultato:**
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
```

✅ **100% delle features nel JSON matchano con il CSV!**

## 3. Feature Aggiunta: Tabella di Verifica Dati

### Posizione

**File:** `eda/pages/01_Probe_Prompts.py`  
**Sezione:** "📈 Main Chart: Importance vs Activation"  
**Linee:** 1231-1327

### Funzionalità

Aggiunto un expander "🔍 Tabella di Verifica Dati (JSON + CSV)" che mostra:

1. **Tutte le colonne utili:**
   - Dal JSON: `feature_key`, `layer`, `index`, `source`, `prompt`, `activation_max`, `activation_sum`, `peak_token`, `peak_token_idx`
   - Dal CSV: `node_influence`

2. **Formato dati:**
   - Una riga per ogni combinazione `feature × prompt`
   - Esempio: feature `0_32742` testata su 5 prompt = 5 righe

3. **Merge completo:**
   - Left join JSON ← CSV
   - Include anche righe con `node_influence = NaN` se la feature non è nel CSV

4. **Statistiche:**
   - Righe totali (combinazioni feature × prompt)
   - Features uniche
   - Prompts unici
   - Righe senza node_influence
   - Avviso se filtro BOS è attivo

5. **Export:**
   - Pulsante download per salvare la tabella come CSV

### Ordinamento

Tabella ordinata per:
1. `node_influence` (decrescente, NaN alla fine)
2. `feature_key` (alfabetico)

## 4. Note Tecniche

### Colonne del CSV

- `layer`: Layer del modello (-1 per embeddings)
- `feature`: Hash/ID Neuronpedia (NON usare per matching!)
- `id`: ID sequenziale del nodo nel grafo (USARE per matching!)
- `ctx_idx`: Posizione del token
- `token`: Token dove si attiva la feature
- `activation`: Valore di attivazione
- `node_influence`: Influenza marginale sul logit
- `cumulative_influence`: Influenza cumulativa

### Feature Key Non Univoche

Nel CSV, `feature_key` può ripetersi perché lo stesso nodo (layer + id) può attivarsi in **contesti diversi** (diversi `ctx_idx`).

**Esempio:**
```csv
layer,feature,id,ctx_idx,token,node_influence
0,175865634,18753,3, of,0.0017
0,175865634,18753,7, is,0.0076
```

Entrambe le righe hanno `feature_key = '0_18753'` ma contesti diversi.

### Grafo PyTorch vs JSON vs CSV

**Tutti usano lo stesso identificatore:**
- Grafo .pt: `feat_idx` in `active_features`
- JSON: `index` in activations
- CSV: `id` (colonna 3)

Il campo `feature` nel CSV è un **hash diverso** (da Neuronpedia) e NON deve essere usato per il matching.

## 5. File Creati/Modificati

### File Modificati
1. ✅ `eda/pages/01_Probe_Prompts.py` - Fix feature_key + tabella verifica
2. ✅ `eda/utils/data_loader.py` - Fix feature_key (funzione non usata)

### File Creati
3. ✅ `tests/test_feature_key_matching.py` - Test automatico
4. ✅ `docs/cursor/FIX_FEATURE_KEY_MATCHING.md` - Documentazione fix
5. ✅ `docs/cursor/SESSION_SUMMARY_FEATURE_KEY_FIX.md` - Questo file

### File Rimossi
6. ✅ `scripts/verify_json_csv_match.py` - Temporaneo, sostituito dal test

## 6. Come Usare

### Verifica Matching

Per verificare che il matching funzioni:

```bash
python tests/test_feature_key_matching.py
```

Dovrebbe mostrare 100% match rate.

### Tabella di Verifica nell'App

1. Avvia l'app Streamlit: `python -m streamlit run eda/app.py`
2. Vai alla pagina **01_Probe_Prompts**
3. Carica un file JSON con activations
4. Scorri fino a "📈 Main Chart: Importance vs Activation"
5. Espandi **"🔍 Tabella di Verifica Dati (JSON + CSV)"**
6. Verifica i dati e scarica il CSV se necessario

### Colonne nella Tabella

- `feature_key`: Identificatore unico (layer_id)
- `layer`: Layer del modello
- `index`: ID nel grafo (= id nel CSV)
- `source`: Source set del JSON (es. "0-clt-hp")
- `prompt`: Prompt testato (troncato a 50 char)
- `activation_max`: Massima attivazione della feature sul prompt
- `activation_sum`: Somma attivazioni su tutti i token
- `peak_token`: Token dove la feature ha il picco
- `peak_token_idx`: Indice del peak token
- `node_influence`: Influenza causale dal CSV (può essere NaN)

## 7. Risultati

- ✅ **100% match rate** tra JSON e CSV
- ✅ Grafico "Main Chart" ora funziona correttamente
- ✅ Tabella di verifica per debug disponibile
- ✅ Test automatico per prevenire regressioni
- ✅ Documentazione completa

## Conclusioni

Il problema era un semplice errore nella scelta della colonna CSV da usare per il matching. La correzione è stata applicata, verificata con test automatici, e una tabella di debug è stata aggiunta per facilitare future verifiche.

L'utente può ora:
1. Vedere il grafico con dati corretti
2. Verificare manualmente i dati nella tabella
3. Scaricare i dati per analisi esterne
4. Essere sicuro che il matching sia corretto al 100%

