# Autoload File Default - Completato

**Data**: 2025-10-25  
**Status**: ✅ Completato

---

## Descrizione

La pagina Streamlit Node Grouping ora carica automaticamente i file di default all'avvio, semplificando il workflow per l'utente.

---

## File Caricati Automaticamente

### 1. CSV Export (Richiesto)
**Path**: `output/2025-10-21T07-40_export_ENRICHED.csv`

**Contenuto**:
- 195 righe (39 feature × 5 prompt)
- Colonne: `feature_key`, `layer`, `prompt`, `activation_max`, `peak_token`, `peak_token_idx`, `supernode_label`, `supernode_class`, `motivation`
- Ground truth manualmente annotato per validazione

### 2. JSON Attivazioni (Opzionale)
**Path**: `output/activations_dump (2).json`

**Contenuto**:
- Attivazioni token-by-token per 5 prompt
- Struttura: `{ "results": [{ "tokens": [...], "counts": [[...]] }] }`
- Necessario per naming accurato di nodi "Relationship"

---

## Implementazione

### Logica di Caricamento

```python
# Percorsi di default
default_csv_path = parent_dir / "output" / "2025-10-21T07-40_export_ENRICHED.csv"
default_json_path = parent_dir / "output" / "activations_dump (2).json"

# Carica automaticamente i file di default se esistono
if 'default_files_loaded' not in st.session_state:
    st.session_state['default_files_loaded'] = False
    
    if default_csv_path.exists():
        st.session_state['default_csv'] = default_csv_path
        st.sidebar.info(f"✅ CSV caricato automaticamente: `{default_csv_path.name}`")
    
    if default_json_path.exists():
        st.session_state['default_json'] = default_json_path
        st.sidebar.info(f"✅ JSON caricato automaticamente: `{default_json_path.name}`")
    
    st.session_state['default_files_loaded'] = True
```

### Priorità File

```python
# Usa file uploadati se disponibili, altrimenti usa default
csv_to_use = uploaded_csv if uploaded_csv is not None else st.session_state.get('default_csv')
json_to_use = uploaded_json if uploaded_json is not None else st.session_state.get('default_json')
```

**Logica**:
1. Se l'utente carica un file tramite uploader → usa quello
2. Altrimenti → usa il file di default (se esiste)
3. Se nessuno dei due → mostra warning

### Gestione Caricamento

```python
# Carica CSV
if isinstance(csv_to_use, Path):
    # File di default (path)
    df = pd.read_csv(csv_to_use)
    csv_name = csv_to_use.name
else:
    # File uploadato (file-like object)
    df = pd.read_csv(csv_to_use)
    csv_name = csv_to_use.name if hasattr(csv_to_use, 'name') else 'uploaded file'

st.success(f"✅ CSV caricato: {csv_name} - {len(df)} righe, {df['feature_key'].nunique()} feature uniche")
```

**Gestione Tipi**:
- `Path`: File di default (path assoluto)
- `UploadedFile`: File caricato tramite `st.file_uploader`

---

## Interfaccia Utente

### Sidebar - Input Files

**All'avvio** (se file esistono):
```
📁 Input Files
✅ CSV caricato automaticamente: `2025-10-21T07-40_export_ENRICHED.csv`
✅ JSON caricato automaticamente: `activations_dump (2).json`

[CSV Export (richiesto)]
[JSON Attivazioni (opzionale)]
```

**Messaggi di successo** (area principale):
```
✅ CSV caricato: 2025-10-21T07-40_export_ENRICHED.csv - 195 righe, 39 feature uniche
✅ JSON attivazioni caricato: activations_dump (2).json - 5 prompt
```

### Override con File Uploader

L'utente può comunque caricare file diversi tramite gli uploader:
1. Click su "Browse files" nell'uploader
2. Seleziona file diverso
3. Il nuovo file sovrascrive il default per quella sessione

---

## Vantaggi

### 1. Workflow Semplificato
**Prima**:
1. Apri Streamlit
2. Click "Browse files" per CSV
3. Naviga a `output/2025-10-21T07-40_export_ENRICHED.csv`
4. Seleziona file
5. Click "Browse files" per JSON
6. Naviga a `output/activations_dump (2).json`
7. Seleziona file
8. Inizia a lavorare

**Dopo**:
1. Apri Streamlit
2. **File già caricati automaticamente**
3. Inizia a lavorare

**Risparmio**: 6 passaggi eliminati

### 2. Esperienza Utente
- ✅ Nessuna navigazione manuale necessaria
- ✅ Messaggi informativi chiari
- ✅ Possibilità di override se necessario
- ✅ Gestione errori (file non esistenti)

### 3. Sviluppo e Test
- ✅ Iterazioni più rapide durante sviluppo
- ✅ Test immediati senza setup manuale
- ✅ Coerenza tra sessioni

### 4. Documentazione
- ✅ File di esempio sempre disponibili
- ✅ Nuovi utenti vedono subito i dati
- ✅ Tutorial e demo più fluidi

---

## Gestione Errori

### File Non Esistenti
```python
if default_csv_path.exists():
    st.session_state['default_csv'] = default_csv_path
    st.sidebar.info(f"✅ CSV caricato automaticamente: `{default_csv_path.name}`")
# Se non esiste, non viene caricato (nessun errore)
```

**Comportamento**:
- Se file non esiste → nessun messaggio, uploader disponibile
- Se file esiste → caricato automaticamente con messaggio info

### Errori di Caricamento
```python
try:
    df = pd.read_csv(csv_to_use)
    st.success(f"✅ CSV caricato: {csv_name}...")
except Exception as e:
    st.error(f"❌ Errore caricamento CSV: {e}")
    st.stop()
```

**Comportamento**:
- Errore parsing CSV → messaggio errore, pipeline si ferma
- Errore parsing JSON → warning, pipeline continua (JSON opzionale)

---

## Casi d'Uso

### Caso 1: Primo Avvio (File Esistono)
1. Utente apre pagina
2. **File caricati automaticamente**
3. Messaggi info nella sidebar
4. Messaggi success nell'area principale
5. Utente può procedere direttamente a Step 1

### Caso 2: Primo Avvio (File Non Esistono)
1. Utente apre pagina
2. Nessun messaggio info
3. Warning: "⬆️ Carica un file CSV per iniziare"
4. Utente usa gli uploader per caricare file

### Caso 3: Override con File Diverso
1. Utente apre pagina
2. File default caricati
3. Utente vuole testare file diverso
4. Usa uploader per caricare nuovo file
5. Nuovo file sovrascrive default per quella sessione

### Caso 4: Sessione Persistente
1. Utente apre pagina (file default caricati)
2. Lavora con i dati
3. Ricarica pagina (F5)
4. File default ricaricati automaticamente
5. **Nota**: Risultati Step 1/2/3 in `session_state` sono persi (comportamento Streamlit normale)

---

## File Modificati

### `eda/pages/02_Node_Grouping.py`

**Linee aggiunte**: 47-75, 267-352

**Modifiche**:
1. **Linee 47-63**: Definizione path default e caricamento automatico
2. **Linee 267-270**: Logica priorità file (uploaded vs default)
3. **Linee 319-352**: Gestione caricamento con supporto Path e UploadedFile

**Totale**: +50 righe

---

## Test Manuali

### Test 1: File Esistono
- ✅ Messaggi info nella sidebar
- ✅ CSV caricato correttamente
- ✅ JSON caricato correttamente
- ✅ Step 1 eseguibile immediatamente

### Test 2: File Non Esistono
- ✅ Nessun messaggio info (corretto)
- ✅ Warning "Carica un file CSV"
- ✅ Uploader funzionanti

### Test 3: Override CSV
- ✅ File default caricato
- ✅ Upload nuovo CSV
- ✅ Nuovo CSV usato al posto del default
- ✅ JSON default ancora attivo

### Test 4: Override JSON
- ✅ File default caricati
- ✅ Upload nuovo JSON
- ✅ Nuovo JSON usato al posto del default
- ✅ CSV default ancora attivo

### Test 5: Reload Pagina
- ✅ File default ricaricati
- ✅ Messaggi info mostrati
- ✅ Session state resettato (comportamento normale)

---

## Configurazione Alternativa

Se l'utente vuole cambiare i file di default, può modificare i path nel codice:

```python
# Linee 48-49 in eda/pages/02_Node_Grouping.py
default_csv_path = parent_dir / "output" / "YOUR_FILE.csv"
default_json_path = parent_dir / "output" / "YOUR_JSON.json"
```

**Alternativa futura**: Aggiungere configurazione tramite file `config.json` o variabili d'ambiente.

---

## Riferimenti

- **File**: `eda/pages/02_Node_Grouping.py`
- **CSV Default**: `output/2025-10-21T07-40_export_ENRICHED.csv`
- **JSON Default**: `output/activations_dump (2).json`

---

## Conclusione

Il caricamento automatico dei file di default migliora significativamente l'esperienza utente, riducendo i passaggi necessari per iniziare a lavorare con la pipeline Node Grouping.

**Vantaggi principali**:
- ✅ Workflow più rapido (6 passaggi eliminati)
- ✅ Esperienza utente migliorata
- ✅ Flessibilità mantenuta (override possibile)
- ✅ Gestione errori robusta

**Pronto per l'uso!** 🚀

