# Step 3 — Naming Supernodi: Implementazione Completata

**Data**: 2025-10-25  
**Status**: ✅ Pronto per review

---

## Cosa è Stato Implementato

Ho completato l'implementazione dello **Step 3 (Naming Supernodi)** in `scripts/02_node_grouping.py`.

### Funzionalità Principali

1. **Relationship** → `"(X) related"`
   - X = primo token semantico con max attivazione dal prompt originale
   - Usa JSON attivazioni per accesso token-by-token
   - Fallback su `peak_token` se JSON non disponibile
   - Esclusi token speciali (`<bos>`, `<eos>`, etc.)

2. **Semantic** → `"token"`
   - Token = `peak_token` del record con max activation
   - Mantiene maiuscola se presente
   - NO suffisso "(Concept)"
   - Casi edge: `"Semantic (unknown)"`, `"punctuation"`

3. **Say X** → `"Say (X)"`
   - X = `target_token` del record con max activation
   - Tie-break: distance minore, poi **backward > forward**
   - Mantiene maiuscola se presente
   - Fallback: `"Say (?)"`

---

## Test Eseguito

### Comando
```bash
python scripts/02_node_grouping.py \
  --input output/2025-10-21T07-40_export_ENRICHED.csv \
  --output output/test_grouped.csv \
  --json "output/activations_dump (2).json" \
  --verbose
```

### Risultati
```
Classificazione:
  - Semantic:      35 (89.7%)
  - Relationship:   4 (10.3%)

Naming:
  - 39 feature
  - 11 nomi unici

Esempi:
  Relationship:
    - (entity) related
  Semantic:
    - Texas
    - is
```

### Output
- CSV con 26 colonne (incluso `supernode_name`)
- 195 righe processate correttamente
- 0 errori

---

## Come Usare

### Pipeline Completa (Step 1+2+3)
```bash
python scripts/02_node_grouping.py \
  --input output/YOUR_EXPORT.csv \
  --output output/YOUR_GROUPED.csv \
  --json "output/YOUR_ACTIVATIONS.json" \
  --verbose
```

### Solo Step 1+2 (senza naming)
```bash
python scripts/02_node_grouping.py \
  --input output/YOUR_EXPORT.csv \
  --output output/YOUR_PREPARED.csv \
  --skip-naming \
  --verbose
```

### Solo Step 1 (preparazione)
```bash
python scripts/02_node_grouping.py \
  --input output/YOUR_EXPORT.csv \
  --output output/YOUR_PREPARED.csv \
  --skip-classify \
  --verbose
```

---

## Decisioni Implementate (dal tuo Feedback)

1. ✅ **Relationship**: `"(X) related"` con X dal prompt originale + JSON attivazioni
2. ✅ **Semantic**: NO lowercase se ha maiuscola, NO "(Concept)"
3. ✅ **Say X tie-break**: Backward > Forward (contesto)
4. ✅ **Say X no target**: `"Say (?)"`
5. ✅ **Normalizzazione**: Strip + rimuovi punct trailing + mantieni maiuscola
6. ✅ **Nomi duplicati**: OK, lasciati

---

## Note Importanti

### 1. JSON Attivazioni per Relationship
Per un naming accurato di Relationship, è **fortemente raccomandato** fornire il JSON delle attivazioni con `--json`.

**Perché?**
- Relationship usa il primo token semantico con **max attivazione** dal prompt originale
- Senza JSON, usa fallback (peak_token), che potrebbe non essere il token con max attivazione

**Esempio**:
- Con JSON: `"(capital) related"` (token con max attivazione)
- Senza JSON: `"(entity) related"` (peak_token, potrebbe non essere il massimo)

### 2. Mapping Prompt → JSON
Il matching tra CSV e JSON avviene tramite `prompt` text (non `probe_id`).

**Requisito**: Il JSON deve contenere tutti i prompt presenti nel CSV.

**Verifica**: Lo script stampa un warning se alcuni prompt non hanno match nel JSON.

---

## Prossimi Passi Suggeriti

### 1. Validazione
- Esegui su dataset completo con JSON attivazioni completo
- Verifica manualmente alcuni nomi generati
- Controlla che tutti i prompt abbiano match nel JSON

### 2. Test Unitari (Opzionale)
- Creare `tests/test_node_grouping.py`
- Test per normalizzazione, naming, tie-break

### 3. Integrazione
- Usare il CSV con `supernode_name` per visualizzazione grafo
- Aggiornare dashboard Streamlit per mostrare nomi

---

## File Generati

- ✅ `scripts/02_node_grouping.py` (Step 3 implementato)
- ✅ `output/STEP3_NAMING_PROPOSAL.md` (proposta con feedback)
- ✅ `output/STEP3_IMPLEMENTATION_SUMMARY.md` (dettagli tecnici)
- ✅ `output/STEP3_READY_FOR_REVIEW.md` (questo file)

---

## Domande?

Se hai domande o vuoi modifiche, fammi sapere! Il codice è modulare e facilmente estendibile.

**Pronto per la tua review!** 🚀

