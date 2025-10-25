# Step 1 — Preparazione Dataset: COMPLETATO ✅

## Obiettivo
Arricchire il CSV di export con:
1. `peak_token_type` (functional vs semantic)
2. `target_tokens` (lista candidati per naming Say(X))
3. `tokens_source` (json vs fallback)

## Risultati

### File Output
- **Input**: `output/2025-10-21T07-40_export.csv` (265 righe)
- **Output**: `output/2025-10-21T07-40_STEP1_FIXED.csv` (265 righe, 15 colonne)

### Statistiche
- **Peak token functional**: 73 (27.5%)
- **Peak token semantic**: 192 (72.5%)
- **Tokens source**:
  - JSON: 0 (nessun JSON fornito)
  - Fallback: 73 (tokenizzazione word+punct)
  - N/A: 192 (semantic, non necessaria ricerca target)
- **Functional senza target**: 17 (23% dei functional) → candidati "Say (?)"

## Implementazione

### 1. Dizionario Functional Tokens
Definito `FUNCTIONAL_TOKEN_MAP` con 50+ token e direzioni:
- **forward**: articoli, preposizioni, verbi ausiliari, pronomi (the, of, is, which, etc.)
- **backward**: (nessuno al momento)
- **both**: congiunzioni, punteggiatura (and, or, ",", ":", etc.)

### 2. Classificatore Peak Token
Logica a 3 livelli:
1. **Punteggiatura** → functional
2. **Nel dizionario** → functional
3. **Euristica function-like** → functional (≤3 lettere, lowercase, NO uppercase/acronimi)
4. **Default** → semantic

### 3. Ricerca Target Tokens
- Se semantic → target = peak_token stesso
- Se functional → cerca primo token semantic nella(e) direzione(i) del dizionario
- Finestra di ricerca: 7 token (parametrizzabile)
- Salta token funzionali intermedi
- **Fix critico**: Aggiustamento indice -1 per tokenizzazione fallback (BOS-excluded)

## Fix Applicati

### Fix 1: Euristica function-like (CRITICO)
**Problema**: "USA" classificato come functional (3 lettere, alpha)
**Soluzione**: Escludi uppercase/acronimi (≥2 caratteri)
```python
if token_stripped.isupper() and len(token_stripped) >= 2:
    return False
```

### Fix 2: Pronomi relativi mancanti (MEDIO)
**Problema**: "which" non nel dizionario → classificato come semantic
**Soluzione**: Aggiunti pronomi relativi/interrogativi: which, who, whom, whose, where, when

### Fix 3: Mismatch indici tokenizzazione (CRITICO)
**Problema**: "is" (idx=8 nel CSV) non trova "Austin" (idx=8 nella tokenizzazione)
**Causa**: CSV ha peak_token_idx BOS-excluded (1-based rispetto al JSON), ma prompt non ha BOS
**Soluzione**: Sottrai 1 dall'indice quando usiamo tokenizzazione fallback
```python
if tokens_source == "fallback" and peak_idx is not None and peak_idx > 0:
    adjusted_idx = peak_idx - 1
```

## Casi di Test Verificati

✅ "Dallas" → semantic, target = "Dallas"
✅ "," → functional (both), targets = ["Dallas", "Texas"]
✅ ":" → functional (both), targets = ["capital", "entity"]
✅ "is" → functional (forward), target = "Austin"
✅ "the" → functional (forward), target = "States"
✅ "USA" → semantic (fix applicato)
✅ "which" → functional (forward), target = "city"

## Limitazioni Note

1. **17 functional senza target**: Casi legittimi (fine frase, solo functional successivi)
2. **Tokenizzazione fallback**: Approssimazione word+punct, può divergere dal tokenizer reale
3. **Finestra fissa**: 7 token, potrebbe non coprire tutti i casi

## Prossimi Step

✅ **Step 1 completato e approvato (Review Gate A)**

→ **Step 2**: Specifica albero decisionale per classificazione (Schema/Relationship/Semantic/Say X)

---

**Script**: `scripts/02_node_grouping.py`
**Comando**: `python scripts/02_node_grouping.py --input <CSV> --output <CSV> --verbose`

