# Bugfix: Upload Neuronpedia - API Key e Graph JSON

**Data**: 2025-10-25  
**Status**: ✅ Risolto  

---

## Problemi

### Problema 1: API Key non caricata da `.env`

L'API key di Neuronpedia doveva essere inserita manualmente ogni volta, anche se era disponibile nel file `.env`.

### Problema 2: Graph JSON non disponibile dopo Step 3

Quando si caricavano i file di default all'avvio della pagina, il Graph JSON era disponibile. Ma dopo aver eseguito Step 1, 2, 3, la sezione "Upload su Neuronpedia" mostrava:

```
❌ Carica il Graph JSON prima di procedere!
```

Anche se il Graph JSON era stato caricato all'inizio.

---

## Cause

### Causa 1: Mancanza di caricamento `.env`

Il file `.env` non veniva caricato all'avvio della pagina Streamlit, quindi `NEURONPEDIA_API_KEY` non era disponibile.

### Causa 2: Variabili session state non sincronizzate

C'erano due variabili diverse per il Graph JSON:

1. **`graph_to_use`** (linea 281): Usata nella pipeline principale (Step 1-3)
   ```python
   graph_to_use = uploaded_graph if uploaded_graph is not None else st.session_state.get('default_graph')
   ```

2. **`graph_json_uploaded`** (session state): Usata per verificare disponibilità nell'upload Neuronpedia
   ```python
   graph_json_available = st.session_state.get('graph_json_uploaded') is not None
   ```

**Problema**: Quando i file di default venivano caricati all'avvio, solo `default_graph` veniva impostato, ma **non** `graph_json_uploaded`. Quindi la sezione upload non vedeva il Graph JSON disponibile.

---

## Soluzioni

### Soluzione 1: Carica API Key da `.env`

**Aggiunto import**:
```python
import os
from dotenv import load_dotenv

# Carica variabili d'ambiente
load_dotenv()
```

**Modificato input API Key**:
```python
# API Key input (carica da .env se disponibile)
default_api_key = os.getenv("NEURONPEDIA_API_KEY", "")
api_key = st.text_input(
    "API Key Neuronpedia",
    value=default_api_key,  # ← Usa valore da .env
    type="password",
    help="Inserisci la tua API key di Neuronpedia (richiesta per l'upload). Può essere caricata automaticamente da .env"
)
```

**Benefici**:
- ✅ API Key caricata automaticamente se presente in `.env`
- ✅ Utente non deve inserirla manualmente ogni volta
- ✅ Sicurezza: API Key non visibile nel codice

### Soluzione 2: Sincronizza `graph_json_uploaded`

#### Fix 1: Salva al caricamento iniziale

Quando i file di default vengono caricati all'avvio:

```python
if default_graph_path.exists():
    st.session_state['default_graph'] = default_graph_path
    st.session_state['graph_json_uploaded'] = default_graph_path  # ← Salva anche per upload
    st.sidebar.info(f"✅ Graph JSON caricato automaticamente: `{default_graph_path.name}`")
```

#### Fix 2: Salva quando usato in Step 3

Quando `graph_to_use` viene usato in Step 3:

```python
# Determina path al Graph JSON
graph_path = None
if graph_to_use:
    if isinstance(graph_to_use, Path):
        graph_path = str(graph_to_use)
    else:
        # Se è un file caricato, salva temporaneamente
        graph_path = Path("temp_graph.json")
        graph_json_content = json.loads(graph_to_use.read().decode('utf-8'))
        with open(graph_path, 'w', encoding='utf-8') as f:
            json.dump(graph_json_content, f)
    
    # Salva graph_to_use in session state per upload Neuronpedia
    st.session_state['graph_json_uploaded'] = graph_to_use  # ← Sincronizza!
```

**Benefici**:
- ✅ `graph_json_uploaded` sempre sincronizzato con `graph_to_use`
- ✅ Upload Neuronpedia vede il Graph JSON disponibile dopo Step 3
- ✅ Funziona sia con file di default che con file caricati manualmente

---

## Flusso Corretto

### Scenario 1: File di Default

```
1. Avvio pagina
   → Carica default_graph_path
   → Imposta default_graph = Path(...)
   → Imposta graph_json_uploaded = Path(...)  ← FIX!

2. Esegui Step 1, 2, 3
   → Usa graph_to_use (= default_graph)
   → Salva graph_json_uploaded = graph_to_use  ← FIX!

3. Sezione Upload Neuronpedia
   → Controlla graph_json_uploaded
   → ✅ Disponibile!
```

### Scenario 2: File Caricato Manualmente

```
1. Avvio pagina
   → Nessun file di default

2. Utente carica Graph JSON manualmente
   → uploaded_graph = UploadedFile(...)
   → graph_to_use = uploaded_graph

3. Esegui Step 3
   → Usa graph_to_use (= uploaded_graph)
   → Salva graph_json_uploaded = uploaded_graph  ← FIX!

4. Sezione Upload Neuronpedia
   → Controlla graph_json_uploaded
   → ✅ Disponibile!
```

---

## File `.env` Esempio

```bash
# .env
NEURONPEDIA_API_KEY=your_secret_api_key_here
```

**Nota**: Il file `.env` deve essere nella root del progetto (stessa directory di `scripts/`, `eda/`, ecc.).

---

## Testing

### Test 1: API Key da `.env`

1. Crea file `.env` con `NEURONPEDIA_API_KEY=test_key`
2. Avvia Streamlit
3. Vai alla sezione "Upload su Neuronpedia"
4. Verifica che il campo "API Key Neuronpedia" sia pre-compilato con `test_key`

**Risultato atteso**: ✅ API Key caricata automaticamente

### Test 2: Graph JSON Disponibile (File Default)

1. Assicurati che `output/graph_data/clt-hp-the-capital-of-201020250035-20251020-003525.json` esista
2. Avvia Streamlit
3. Verifica messaggio: "✅ Graph JSON caricato automaticamente"
4. Esegui Step 1, 2, 3
5. Vai alla sezione "Upload su Neuronpedia"
6. Verifica che **NON** ci sia il warning "⚠️ Graph JSON non caricato"

**Risultato atteso**: ✅ Graph JSON disponibile per upload

### Test 3: Graph JSON Disponibile (File Manuale)

1. Avvia Streamlit (senza file di default)
2. Carica CSV, JSON, Graph JSON manualmente
3. Esegui Step 1, 2, 3
4. Vai alla sezione "Upload su Neuronpedia"
5. Verifica che **NON** ci sia il warning "⚠️ Graph JSON non caricato"

**Risultato atteso**: ✅ Graph JSON disponibile per upload

### Test 4: Upload Funzionante

1. Completa Step 1, 2, 3
2. Vai alla sezione "Upload su Neuronpedia"
3. Verifica che API Key sia pre-compilata (se in `.env`)
4. Clicca "🚀 Upload su Neuronpedia"
5. Verifica che l'upload proceda senza errori

**Risultato atteso**: ✅ Upload completato con successo

---

## Edge Cases

### Caso 1: `.env` non presente

```python
default_api_key = os.getenv("NEURONPEDIA_API_KEY", "")
# → default_api_key = "" (stringa vuota)
```

**Comportamento**: Campo API Key vuoto, utente deve inserirla manualmente. ✅

### Caso 2: Graph JSON non caricato

```python
graph_json_available = st.session_state.get('graph_json_uploaded') is not None
# → graph_json_available = False
```

**Comportamento**: Warning "⚠️ Graph JSON non caricato", bottone upload disabilitato. ✅

### Caso 3: Utente ricarica la pagina

**Prima del fix**:
- Session state viene resettato
- File di default ricaricati
- `graph_json_uploaded` **NON** impostato
- Upload non disponibile ❌

**Dopo il fix**:
- Session state viene resettato
- File di default ricaricati
- `graph_json_uploaded` **impostato** durante il caricamento
- Upload disponibile ✅

---

## Modifiche ai File

### `eda/pages/02_Node_Grouping.py`

1. **Import aggiunto** (linee 14-19):
   ```python
   import os
   from dotenv import load_dotenv
   
   # Carica variabili d'ambiente
   load_dotenv()
   ```

2. **Salvataggio `graph_json_uploaded` al caricamento iniziale** (linea 71):
   ```python
   st.session_state['graph_json_uploaded'] = default_graph_path
   ```

3. **Salvataggio `graph_json_uploaded` in Step 3** (linea 867):
   ```python
   st.session_state['graph_json_uploaded'] = graph_to_use
   ```

4. **API Key da `.env`** (linee 1037-1043):
   ```python
   default_api_key = os.getenv("NEURONPEDIA_API_KEY", "")
   api_key = st.text_input(
       "API Key Neuronpedia",
       value=default_api_key,
       type="password",
       help="Inserisci la tua API key di Neuronpedia (richiesta per l'upload). Può essere caricata automaticamente da .env"
   )
   ```

---

## Conclusione

Entrambi i problemi sono stati risolti:

1. ✅ **API Key caricata automaticamente da `.env`** se disponibile
2. ✅ **Graph JSON sempre disponibile per upload** dopo Step 3 (sia con file default che caricati manualmente)

**Risultato**: Workflow più fluido e user-friendly! 🎉

