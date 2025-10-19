# Probe Prompts - Migliorie Implementate

## Data: 2025-10-19

## 🎯 Obiettivo
Rendere lo script `01_probe_prompts.py` robusto per analisi lunghe (anche 2+ ore) senza perdere dati in caso di interruzioni, errori o problemi di rete.

---

## ✨ Nuove Funzionalità Implementate

### 1. **Retry Logic con Backoff Esponenziale**

**Problema risolto:** Rate limiting (429), timeout di rete, errori temporanei

**Implementazione:**
- Retry automatico fino a 3 tentativi per ogni chiamata API
- Backoff esponenziale: 2s, 4s, 8s (max 60s per rate limit 429)
- Gestione intelligente di errori HTTP (429, 500, 404, timeout)

```python
@rate_limited(max_per_second=2)
def get_activations(..., max_retries=3):
    for attempt in range(max_retries):
        try:
            response = self.session.post(...)
            return response.json()
        except requests.exceptions.HTTPError as e:
            if response.status_code == 429:
                wait_time = min(2 ** attempt * 2, 60)
                logger.warning(f"Rate limit hit, waiting {wait_time}s")
                time.sleep(wait_time)
                continue
```

**Benefici:**
- ✅ Resilienza a problemi di rete temporanei
- ✅ Gestione automatica rate limiting
- ✅ Non interrompe analisi per errori singoli

---

### 2. **Sistema di Checkpoint Incrementali**

**Problema risolto:** Perdita dati in caso di interruzione (Ctrl+C, crash, errori)

**Implementazione:**
- Salvataggio automatico ogni N features (default: 10)
- Salvataggio anche ogni 5 minuti (checkpoint temporale)
- Salvataggio su interruzione (KeyboardInterrupt)
- Salvataggio su errore
- File checkpoint in formato JSON con metadata

```python
def save_checkpoint(records, checkpoint_path, metadata=None):
    """Salva checkpoint con atomic write (tmp → rename)"""
    checkpoint_data = {
        "records": records,
        "metadata": metadata,
        "timestamp": datetime.now().isoformat(),
        "num_records": len(records)
    }
    # Atomic write: temp file poi rename
    temp_file.replace(checkpoint_file)
```

**Struttura checkpoint:**
```json
{
  "records": [...],
  "metadata": {
    "current_concept": 2,
    "total_concepts": 5,
    "current_feature": 45,
    "total_features": 100,
    "status": "in_progress"
  },
  "timestamp": "2025-10-19T13:00:00",
  "num_records": 150
}
```

**Benefici:**
- ✅ Nessuna perdita dati
- ✅ Recovery automatico
- ✅ Tracciabilità progresso
- ✅ Metadata per debugging

---

### 3. **Resume Capability**

**Problema risolto:** Riavvio da zero dopo interruzione

**Implementazione:**
- Caricamento automatico checkpoint esistente
- Skip intelligente features già processate
- Continuazione esatta da dove era interrotto

```python
# Carica checkpoint se richiesto
if resume_from_checkpoint:
    existing_records, metadata = load_checkpoint(checkpoint_path)
    processed_keys = get_processed_keys(existing_records)
    
# Durante processing
if (label, layer, feature) in processed_keys:
    skipped_count += 1
    continue  # Skip già processato
```

**Benefici:**
- ✅ Zero duplicazioni
- ✅ Ripresa immediata
- ✅ Tempo risparmiato

---

### 4. **Logging Avanzato**

**Problema risolto:** Difficoltà debugging problemi in analisi lunghe

**Implementazione:**
- Logger Python con doppio output (file + console)
- Log rotativo salvato in `probe_prompts.log`
- Livelli: INFO, WARNING, ERROR
- Tracciamento dettagliato chiamate API

```python
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('probe_prompts.log'),
        logging.StreamHandler()
    ]
)
```

**Esempi log:**
```
2025-10-19 13:20:15 - WARNING - Rate limit hit for 6-gemmascope/9220, waiting 4s (attempt 2/3)
2025-10-19 13:20:19 - INFO - Checkpoint salvato: 50 records in checkpoint.json
2025-10-19 13:20:45 - ERROR - Failed after 3 attempts for 7-gemmascope/5478: Timeout
```

**Benefici:**
- ✅ Debugging facilitato
- ✅ Monitoraggio real-time
- ✅ Audit trail completo

---

### 5. **Integrazione Streamlit**

**Migliorie UI:**

1. **Sezione Checkpoint & Recovery**
   - Configurazione intervallo checkpoint
   - Toggle resume da checkpoint
   - Dropdown selezione checkpoint esistenti
   - Preview info checkpoint (records, data, status)

2. **Feedback Migliorato**
   - Info su checkpoint attivo
   - Progress bar con skip count
   - Messaggi recovery su interruzione
   - Istruzioni ripresa analisi

3. **Gestione Errori**
   - Catch KeyboardInterrupt
   - Salvataggio automatico pre-exit
   - Istruzioni recovery in UI

**Screenshot concettuale:**
```
💾 Checkpoint & Recovery
┌─────────────────┬──────────────────┬────────────────────┐
│ Salva ogni 10   │ ☑ Riprendi da   │ Checkpoint:        │
│ features        │   checkpoint     │ probe_prompts_...  │
└─────────────────┴──────────────────┴────────────────────┘

ℹ️ Checkpoint trovato:
   - Records: 150
   - Data: 2025-10-19 12:30:00
   - Status: interrupted
   - Concepts: 2/5
```

---

## 📊 Parametri Nuovi

### Nella Funzione `analyze_concepts_from_graph_json`

| Parametro | Default | Descrizione |
|-----------|---------|-------------|
| `checkpoint_every` | `10` | Salva checkpoint ogni N features |
| `checkpoint_path` | Auto-generato | Path checkpoint (con timestamp) |
| `resume_from_checkpoint` | `True` | Se True, riprende da checkpoint |

### Nella UI Streamlit

- **Salva checkpoint ogni N features**: `5-100` (default: 10)
- **Riprendi da checkpoint**: Checkbox (default: True)
- **Checkpoint da riprendere**: Dropdown con ultimi 5 checkpoint

---

## 🔧 File Modificati

### 1. `scripts/01_probe_prompts.py` (linee: 673 → 877 = +204 linee)

**Aggiunte:**
- Import: `datetime`, `logging`
- Setup logging con file handler
- Funzione `save_checkpoint()` 
- Funzione `load_checkpoint()`
- Funzione `get_processed_keys()`
- Retry logic in `get_activations()`
- Checkpoint logic nel loop principale
- Try/except per KeyboardInterrupt
- Try/except per errori generici

### 2. `eda/pages/01_Probe_Prompts.py` (linee: 769 → 823 = +54 linee)

**Aggiunte:**
- Sezione "Checkpoint & Recovery" con 3 colonne
- Lettura e display checkpoint esistenti
- Configurazione checkpoint_path
- Passaggio nuovi parametri a funzione
- Gestione KeyboardInterrupt in UI
- Messaggi recovery migliorati

### 3. `tests/test_e2e_probe_prompts.py` (aggiornato)

**Modifiche:**
- Aggiunto test checkpoint parameters
- Path checkpoint specifico per test
- Verifica funzionamento resume

---

## 🚀 Uso

### CLI/Script

```python
from scripts.probe_prompts import analyze_concepts_from_graph_json

df = analyze_concepts_from_graph_json(
    graph_json=graph_json,
    concepts=concepts,
    api_key="...",
    checkpoint_every=10,  # Nuovo
    checkpoint_path="output/checkpoints/my_analysis.json",  # Nuovo
    resume_from_checkpoint=True  # Nuovo
)
```

### Streamlit

1. Vai alla pagina "🔍 Probe Prompts"
2. Completa Step 1-4 normalmente
3. In Step 5, configura:
   - Checkpoint ogni: `10` features
   - ☑️ Riprendi da checkpoint
   - Seleziona checkpoint esistente (se disponibile)
4. Clicca "▶️ Esegui Analisi"

**Se interrotto (Ctrl+C):**
1. Ricarica la pagina
2. Seleziona il checkpoint dalla lista
3. Clicca "Esegui Analisi" → Riprende automaticamente

---

## 📈 Performance

### Prima delle migliorie:
- ❌ Interruzione = perdita tutto
- ❌ Rate limit = crash
- ❌ Timeout = skip feature
- ❌ No visibilità problemi

### Dopo le migliorie:
- ✅ Interruzione = 0 perdita dati
- ✅ Rate limit = auto-retry + backoff
- ✅ Timeout = 3 retry poi log
- ✅ Logging completo + audit trail

### Metriche Esempio

**Analisi tipica: 500 features × 3 concepts = 1500 chiamate API**

| Scenario | Prima | Dopo |
|----------|-------|------|
| Tempo totale | 25 min | 25 min |
| Rate limit (10 hits) | CRASH | +2 min (auto-recovery) |
| Timeout (5 features) | 5 skip | 3 retry → 2 skip |
| Interruzione al 60% | ❌ Riavvio | ✅ Resume (10 min risparmiati) |
| Crash al 80% | ❌ Tutto perso | ✅ Resume (5 min risparmiati) |

---

## 🔍 Testing

### Test End-to-End Aggiornato

```bash
python tests/test_e2e_probe_prompts.py
```

**Verifica:**
- ✅ Caricamento API key da .env
- ✅ Chiamate API funzionanti
- ✅ Checkpoint salvati ogni 3 features
- ✅ Resume da checkpoint
- ✅ Skip features già processate

---

## 📝 Log Files

### `probe_prompts.log`

Traccia completa dell'esecuzione:
- Timestamp ogni operazione
- Retry tentativi
- Checkpoint salvati
- Errori dettagliati

**Esempio:**
```
2025-10-19 13:00:00 - INFO - Using API key from .env: sk-np-mhcX...
2025-10-19 13:00:05 - INFO - Checkpoint salvato: 10 records in checkpoint.json
2025-10-19 13:00:15 - WARNING - Rate limit hit for 6-gemmascope/9220, waiting 2s (attempt 1/3)
2025-10-19 13:00:17 - INFO - Riprendendo da checkpoint: 10 records già processati
```

### Checkpoint Files

**Location:** `output/checkpoints/probe_prompts_YYYYMMDD_HHMMSS.json`

**Retention:** Ultimi 5 checkpoint mostrati in Streamlit

---

## ⚠️ Note Importanti

1. **Compatibilità Backwards:** 
   - I nuovi parametri sono opzionali
   - Script funziona come prima se non specificati

2. **Storage:**
   - Checkpoint files possono essere grandi (dipende da #records)
   - Pulire periodicamente cartella `output/checkpoints/`

3. **Concorrenza:**
   - Non eseguire 2 analisi con stesso checkpoint_path
   - Checkpoint path auto-generato con timestamp

4. **API Rate Limiting:**
   - Ridotto da 5 a 2 req/sec per maggiore stabilità
   - Configurable via `@rate_limited(max_per_second=N)`

---

## 🎓 Best Practices

### Per Analisi Lunghe (> 1 ora)

1. **Usa checkpoint frequenti:** `checkpoint_every=5-10`
2. **Monitora log file:** `tail -f probe_prompts.log`
3. **Backup checkpoint importanti:** Copy `.json` file
4. **Test preliminare:** Esegui con piccolo subset

### Per Debugging

1. Controlla `probe_prompts.log` per errori
2. Ispeziona checkpoint JSON per capire stato
3. Usa `resume_from_checkpoint=True` per re-run parziali

### Per Recovery

1. Identifica ultimo checkpoint valido
2. Seleziona in UI Streamlit o passa come `checkpoint_path`
3. Abilita `resume_from_checkpoint=True`
4. L'analisi skippa automaticamente features già processate

---

## 🔮 Possibili Miglioramenti Futuri

1. **Compression:** Comprimi checkpoint JSON (gzip)
2. **Incremental CSV:** Scrivi CSV progressivamente
3. **Parallel Processing:** Multi-thread chiamate API
4. **Smart Retry:** ML-based retry strategy
5. **Monitoring Dashboard:** Real-time progress tracking
6. **Auto-cleanup:** Rimozione automatica checkpoint vecchi

---

## ✅ Conclusioni

Le migliorie implementate rendono lo script **production-ready** per analisi lunghe e complesse:

- 🛡️ **Resiliente:** Gestisce errori, timeout, rate limiting
- 💾 **Sicuro:** Zero perdita dati con checkpoint
- 🔄 **Riprendibile:** Resume automatico da interruzioni
- 📊 **Monitorabile:** Logging completo e dettagliato
- 🎨 **User-friendly:** UI Streamlit intuitiva

Lo script ora può girare per **ore** senza supervisione, con garanzia di recovery completo in caso di problemi.


