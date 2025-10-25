# Review Gate A — Step 1: Preparazione Dataset

## Obiettivo
Arricchire il CSV di export con:
1. `peak_token_type` (functional vs semantic)
2. `target_tokens` (lista candidati per naming Say(X))
3. `tokens_source` (json vs fallback)

---

## Statistiche Finali

**Input**: `output/2025-10-21T07-40_export.csv` (265 righe)
**Output**: `output/2025-10-21T07-40_STEP1_FIXED.csv` (265 righe, 15 colonne)

### Classificazione Peak Tokens
- **Functional**: 73 (27.5%)
- **Semantic**: 192 (72.5%)

### Tokens Source
- **JSON**: 0 (nessun JSON fornito)
- **Fallback**: 73 (tokenizzazione word+punct dal prompt)
- **N/A**: 192 (semantic, non necessaria ricerca target)

### Target Tokens
- **Functional con target trovato**: 56 (77%)
- **Functional senza target**: 17 (23%) → diventeranno "Say (?)" nel naming

---

## Campione di Verifica (10 casi rappresentativi)

**Tutti i casi sono stati verificati automaticamente contro il CSV finale.**

### Caso 1: Semantic token — "Dallas"
```
Feature: 20_44686
Prompt: "entity: A city in Texas, USA is Dallas"
peak_token: " Dallas" (idx=10)
peak_token_type: semantic ✓
target_tokens: [{"token": " Dallas", "index": 10, "distance": 0, "direction": "self"}]
```
**Verifica**: ✅ Corretto. Token semantico, target = se stesso.

---

### Caso 2: Functional token — "," (punteggiatura, direzione BOTH)
```
Feature: 0_18753
Prompt: "entity: A city in Texas, USA is Dallas"
peak_token: "," (idx=7 nel CSV, idx=6 nella tokenizzazione fallback)
peak_token_type: functional ✓
target_tokens: [
  {"token": "USA", "index": 7, "distance": 1, "direction": "forward"},
  {"token": "Texas", "index": 5, "distance": 1, "direction": "backward"}
]
Tokenizzazione: [..., "Texas"(5), ","(6), "USA"(7), ...]
```
**Verifica**: ✅ Corretto. Punteggiatura → both, trovati 2 candidati semantici adiacenti.

---

### Caso 3: Functional token — ":" (punteggiatura, direzione BOTH)
```
Feature: 0_18753
Prompt: "entity: The capital city of Texas is Austin"
peak_token: ":" (idx=2)
peak_token_type: functional ✓
target_tokens: [
  {"token": "capital", "index": 3, "distance": 2, "direction": "forward"},
  {"token": "entity", "index": 1, "distance": 1, "direction": "backward"}
]
```
**Verifica**: ✅ Corretto. ":" salta "The" (functional) e trova "capital" (semantic).

---

### Caso 4: Functional token — "is" (verbo ausiliare, direzione FORWARD)
```
Feature: 20_44686
Prompt: "entity: The capital city of Texas is Austin"
peak_token: " is" (idx=8)
peak_token_type: functional ✓
target_tokens: [{"token": "Austin", "index": 8, "distance": 1, "direction": "forward"}]
tokens_source: fallback
```
**Verifica**: ✅ Corretto. "is" trova "Austin" come target (fix applicato: aggiustamento indice BOS).

---

### Caso 5: Functional token — "the" (articolo, direzione FORWARD)
```
Feature: 0_40780
Prompt: "entity: A state in the United States is Texas"
peak_token: " the" (idx=6)
peak_token_type: functional ✓
target_tokens: [{"token": "United", "index": 6, "distance": 1, "direction": "forward"}]
```
**Verifica**: ✅ Corretto. "the" trova "United" (primo token semantic dopo "the").
**Nota**: "States" è a distanza 2, ma "United" è il primo semantic trovato.

---

### Caso 6: Semantic token — "USA" (acronimo uppercase)
```
Feature: 1_52044
Prompt: "entity: A city in Texas, USA is Dallas"
peak_token: " USA" (idx=8)
peak_token_type: semantic ✓
target_tokens: [{"token": " USA", "index": 8, "distance": 0, "direction": "self"}]
```
**Verifica**: ✅ Corretto. "USA" classificato come semantic (fix applicato: esclusi acronimi uppercase dall'euristica function-like).

---

### Caso 7: Functional token — "which" (pronome relativo, direzione FORWARD)
```
Feature: 0_40780
Prompt: "relationship: the state in which a city is located is the state containing"
peak_token: " which" (idx=6)
peak_token_type: functional ✓
target_tokens: [{"token": "city", "index": 7, "distance": 2, "direction": "forward"}]
```
**Verifica**: ✅ Corretto. "which" classificato come functional (fix applicato: aggiunto al dizionario) e trova "city" (salta "a" che è functional).

---

### Caso 8: Semantic token — "entity" (categoria prompt)
```
Feature: 1_12928
Prompt: "entity: A city in Texas, USA is Dallas"
peak_token: "entity" (idx=1)
peak_token_type: semantic ✓
target_tokens: [{"token": "entity", "index": 1, "distance": 0, "direction": "self"}]
```
**Verifica**: ✅ Corretto. "entity" è semantic (anche se è una categoria, non un contenuto).

---

### Caso 9: Semantic token — "capital"
```
Feature: 1_52044
Prompt: "entity: The capital city of Texas is Austin"
peak_token: " capital" (idx=4)
peak_token_type: semantic ✓
target_tokens: [{"token": " capital", "index": 4, "distance": 0, "direction": "self"}]
```
**Verifica**: ✅ Corretto. Token semantico.

---

### Caso 10: Functional token — "is" (altro esempio)
```
Feature: 22_11998
Prompt: "entity: The capital city of Texas is Austin"
peak_token: " is" (idx=8)
peak_token_type: functional ✓
target_tokens: [{"token": "Austin", "index": 8, "distance": 1, "direction": "forward"}]
```
**Verifica**: ✅ Corretto. Stesso comportamento del Caso 4.

---

## Fix Applicati Durante lo Step 1

### Fix 1: Euristica function-like (CRITICO)
**Problema iniziale**: "USA" classificato come functional (3 lettere, alpha)
**Soluzione**: Escludi uppercase/acronimi (≥2 caratteri)
```python
if token_stripped.isupper() and len(token_stripped) >= 2:
    return False
```
**Risultato**: ✅ "USA" ora correttamente semantic

### Fix 2: Pronomi relativi mancanti (MEDIO)
**Problema iniziale**: "which" non nel dizionario → classificato come semantic
**Soluzione**: Aggiunti pronomi relativi/interrogativi al dizionario
```python
"which": "forward",
"who": "forward",
"whom": "forward",
"whose": "forward",
"where": "forward",
"when": "forward",
```
**Risultato**: ✅ "which" ora correttamente functional

### Fix 3: Mismatch indici tokenizzazione (CRITICO)
**Problema iniziale**: "is" (idx=8 nel CSV) non trovava "Austin" (idx=8 nella tokenizzazione)
**Causa**: CSV ha peak_token_idx BOS-excluded (1-based rispetto al JSON), ma prompt non ha BOS
**Soluzione**: Sottrai 1 dall'indice quando usiamo tokenizzazione fallback
```python
if tokens_source == "fallback" and peak_idx is not None and peak_idx > 0:
    adjusted_idx = peak_idx - 1
```
**Risultato**: ✅ "is" trova correttamente "Austin" (e tutti gli altri functional tokens)

**Impatto totale fix**: Functional senza target: 56 → 17 (miglioramento 70%)

---

## Verifica Automatica

**Data**: 2025-10-25
**Metodo**: Script Python che verifica tutti i 10 casi documentati contro il CSV finale
**Risultato**: ✅ **10/10 casi verificati correttamente**

Dettagli verifica:
- ✅ peak_token corretto per tutti i casi
- ✅ peak_token_type corretto per tutti i casi
- ✅ target_tokens con direzioni e distanze corrette
- ✅ Fix applicati verificati (USA semantic, which functional, is trova Austin)

**Log completo**: `output/STEP1_VERIFICATION_RESULTS.txt`

---

## Implementazione Tecnica

### Dizionario Functional Tokens
50+ token con direzioni definite:
- **forward** (40+): articoli (the, a, an), preposizioni (of, in, to, for, with, on, at, from, by, about, as, over, under, between, through), verbi ausiliari (is, are, was, were, be, been, being, has, have, had, do, does, did, can, could, will, would, should, may, might, must), pronomi (it, its, this, these, those, which, who, whom, whose, where, when), congiunzioni (if, because, so, than, that)
- **both** (4): congiunzioni (and, or, but), punteggiatura (tutte)

### Classificatore Peak Token
Logica a cascata:
1. Punteggiatura → functional
2. Nel dizionario → functional
3. Euristica function-like → functional (≤3 lettere, lowercase, NO uppercase/acronimi)
4. Default → semantic

### Ricerca Target Tokens
- Finestra: 7 token (parametrizzabile)
- Salta token funzionali intermedi
- Restituisce lista con metadati: token, index, distance, direction
- Gestione BOS: aggiustamento indice -1 per tokenizzazione fallback

---

## Functional Tokens Senza Target (17 casi)

Casi legittimi dove non c'è un token semantico entro la finestra di ricerca:
- Token funzionali a fine frase
- Token funzionali seguiti solo da altri token funzionali
- Casi edge con tokenizzazione particolare

→ Questi diventeranno **"Say (?)"** nel naming (Step 4).

---

## Approvazione Review Gate A

- [x] Implementazione completata
- [x] Fix critici applicati e verificati
- [x] Test su 265 righe eseguito con successo
- [x] Campione di 10 casi verificato automaticamente (10/10 OK)
- [x] Documentazione completa
- [x] **Pronto per Step 2**

---

## File Output

**CSV finale**: `output/2025-10-21T07-40_STEP1_FIXED.csv`

**Nuove colonne aggiunte**:
- `peak_token_type` (functional/semantic)
- `target_tokens` (JSON array)
- `tokens_source` (json/fallback/n/a)

**Script**: `scripts/02_node_grouping.py`

**Comando**:
```bash
python scripts/02_node_grouping.py --input output/2025-10-21T07-40_export.csv --output output/2025-10-21T07-40_STEP1_FIXED.csv --verbose
```

---

**Step 1 COMPLETATO ✅**
**Prossimo**: Step 2 — Specifica albero decisionale per classificazione (Schema/Relationship/Semantic/Say X)
