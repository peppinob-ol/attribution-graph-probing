# Review Gate B — Step 2.1: Analisi Pattern (FINALE)

## AGGIORNAMENTO IMPORTANTE

✅ **Schema → Relationship**: Le 2 feature classificate come "Schema" sono in realtà **Relationship**.

**Motivazione**: Spiegherai nei prossimi step perché anche i meta-tokens rappresentano relazioni.

---

## Modifiche Applicate

✅ **1. Meta-tokens INCLUSI**: "entity", "attribute", "relationship" contano come semantic tokens
✅ **2. Sparsity solo per activation > 0**: Esclude prompt inattivi (più rappresentativo)
✅ **3. Peak position CV**: Misura stabilità posizione (no overfitting)
✅ **4. Schema → Relationship**: Ora abbiamo solo 3 classi (Relationship, Semantic, Say X)

---

## Pattern Finali per Classe

### 1. Relationship (4 feature: 1_12928, 1_57794, 1_52044, 1_72774)

**Sottogruppi identificati**:

#### A. Relationship "meta-token" (ex-Schema: 1_12928, 1_57794)
| Metrica | Valore | Interpretazione |
|---------|--------|-----------------|
| Layer | 1 | ✅ Layer bassissimo |
| **K_sem_distinct** | 3 | ✅ 3 meta-tokens: "entity", "attribute", "relationship" |
| **H_sem_entropy** | 1.37 | ✅ Entropia alta (3 token diversi) |
| **Sparsity median (act>0)** | 0.23 | ✅ BASSA = attivazioni diffuse |
| **peak_idx_cv** | 0.0 | ✅ **Posizione perfettamente stabile** (sempre idx=1) |
| **peak_idx_mode** | 1 | ✅ Sempre prima posizione |

**Pattern**: Attivazioni su meta-tokens (ruoli semantici generali), posizione stabile, attivazioni diffuse.

#### B. Relationship "semantic" (originali: 1_52044, 1_72774)
| Metrica | Valore | Interpretazione |
|---------|--------|-----------------|
| Layer | 1 | ✅ Layer basso |
| **K_sem_distinct** | 4 | ✅ 4 token semantici distinti |
| **H_sem_entropy** | 1.92 | ✅ Entropia alta |
| **Sparsity median (act>0)** | 0.25 | ✅ Bassa (attivazioni su più token) |
| **peak_idx_cv** | 0.60 | ✅ **Posizione variabile** (4, 5, 14, 17) |
| **peak_idx_mode** | 4 | ✅ Spesso posizione 4 |

**Pattern**: Attivazioni su token semantici diversi, posizione varia, attivazioni diffuse.

#### Relationship AGGREGATA (tutte e 4)
| Metrica | Min | Median | Max | Mean |
|---------|-----|--------|-----|------|
| Layer | 1 | 1 | 1 | 1.0 |
| K_sem_distinct | 3 | 3.5 | 4 | 3.5 |
| H_sem_entropy | 1.37 | 1.65 | 1.92 | 1.65 |
| conf_S / conf_F | 1.0 / 0.0 | 1.0 / 0.0 | 1.0 / 0.0 | 1.0 / 0.0 |
| U_cv | 0.39 | 1.35 | 2.10 | 1.30 |
| Sparsity median | 0.23 | 0.24 | 0.29 | 0.25 |
| peak_idx_cv | 0.0 | 0.30 | 0.63 | 0.30 |

**Discriminanti chiave**:
- `K_sem_distinct ≥ 3` (alta diversità)
- `layer ≤ 5` (layer basso)
- `conf_S ≥ 0.6` (dominanza semantic)
- `sparsity_median < 0.4` (attivazioni diffuse)
- `peak_idx_cv` varia (0.0-0.63), ma sempre `< 1.0`

---

### 2. Semantic (19 feature)

| Metrica | Valore (median) | Interpretazione |
|---------|-----------------|-----------------|
| Layer | 0 (range 0-22) | ✅ Prevalenza layer bassi |
| **n_active_prompts** | 3/5 | ⚠️ Non sempre attivo |
| **K_sem_distinct** | 1 | ✅ Bassa diversità (dictionary-like) |
| conf_S / conf_F | 1.0 / 0.0 | ✅ Dominanza semantic (median) |
| **Sparsity median (act>0)** | 0.89 | ✅ **ALTA** = picchi localizzati |
| **peak_idx_cv** | 0.45 | ✅ Posizione moderatamente stabile |

**Discriminanti chiave**:
- `conf_S ≥ 0.6` (dominanza semantic)
- `K_sem_distinct` basso (0-2, median=1)
- `sparsity_median > 0.5` (picchi localizzati)
- **NON** Relationship (K < 3 o layer > 5)

---

### 3. Say "X" (16 feature)

| Metrica | Valore (median) | Interpretazione |
|---------|-----------------|-----------------|
| Layer | 19 (range 7-22) | ✅ Layer alto |
| **n_active_prompts** | 2/5 | ✅ Attivo solo su alcuni prompt (selettivo) |
| **K_sem_distinct** | 0 | ✅ Nessun semantic token |
| conf_S / conf_F | 0.0 / 1.0 | ✅ Dominanza functional perfetta |
| **Sparsity median (act>0)** | 0.89 | ✅ **ALTA** = picchi localizzati su "is" |
| **peak_idx_cv** | 1.08 | ✅ Posizione variabile |

**Discriminanti chiave**:
- `layer ≥ 7` (layer alto)
- `conf_F ≥ 0.8` (dominanza functional)
- `share_F ≥ 0.8` (100% peak functional)
- `K_sem_distinct ≤ 1`

---

## Separazione tra Classi

### Relationship vs Semantic

| Metrica | Relationship | Semantic | Discriminante |
|---------|--------------|----------|---------------|
| **K_sem_distinct** | 3-4 (median=3.5) | 0-2 (median=1) | ✅ **CHIAVE** |
| **Layer** | 1 (fisso) | 0-22 (median=0) | ⚠️ Overlap |
| **Sparsity median** | 0.24 | 0.89 | ✅ **CHIAVE** |
| **conf_S** | 1.0 | 1.0 (median) | ❌ Uguale |

**Regola**: `K_sem_distinct >= 3 AND sparsity_median < 0.4 AND layer <= 5` → Relationship

### Semantic vs Say "X"

| Metrica | Semantic | Say X | Discriminante |
|---------|----------|-------|---------------|
| **Layer** | 0-22 (median=0) | 7-22 (median=19) | ✅ **CHIAVE** |
| **conf_F** | 0.0 (median) | 1.0 (fisso) | ✅ **PERFETTO** |
| **share_F** | 0.5 (median) | 1.0 (fisso) | ✅ **PERFETTO** |

**Regola**: `layer >= 7 AND conf_F >= 0.8 AND share_F >= 0.8` → Say X

### Relationship vs Say "X"

| Metrica | Relationship | Say X | Discriminante |
|---------|--------------|-------|---------------|
| **Layer** | 1 | 7-22 | ✅ **PERFETTO** |
| **K_sem_distinct** | 3-4 | 0 | ✅ **PERFETTO** |
| **conf_S / conf_F** | 1.0 / 0.0 | 0.0 / 1.0 | ✅ **PERFETTO** |

**Regola**: Layer e conf_S/conf_F separano perfettamente.

---

## Albero Decisionale FINALE

```
1. IF layer >= 7 AND conf_F >= 0.8 AND share_F >= 0.8 AND K_sem_distinct <= 1
     → Say "X"

2. ELSE IF layer <= 5 AND K_sem_distinct >= 3 AND conf_S >= 0.6 AND sparsity_median < 0.4
     → Relationship

3. ELSE IF conf_S >= 0.6
     → Semantic

4. ELSE IF layer <= 2 AND conf_F >= 0.6 AND K_sem_distinct <= 1
     → Semantic (anchor low, semantic su functional token)

5. ELSE
     → Fallback (voto tra classi con soglie rilassate)
```

**Note**:
- **Ordine regole**: Say X → Relationship → Semantic → Fallback
- Say X ha priorità (layer alto + functional)
- Relationship richiede K≥3 + sparsity bassa + layer basso
- Semantic è catch-all per conf_S alta
- **Nessuna distinzione** tra Relationship "meta-token" e "semantic" (entrambe Relationship)

---

## Sottotipi Relationship (Osservati ma NON Classificati)

### Relationship A: "Meta-token" (2 feature)
- K=3 (entity, attribute, relationship)
- peak_idx_cv=0.0 (posizione stabile, sempre idx=1)
- Sparsity 0.23 (diffuso)
- **Pattern**: Ruoli semantici generali, scaffolding concettuale

### Relationship B: "Semantic" (2 feature)
- K=4 (token semantici diversi)
- peak_idx_cv=0.60 (posizione variabile)
- Sparsity 0.25 (diffuso)
- **Pattern**: Concetti collegati (city, state, capital, containing)

**Decisione**: Entrambi sono **Relationship**, non serve distinguerli nell'albero decisionale (per ora).

---

## Metriche Finali Implementate

### Metriche Base
✅ `layer`, `U_cv`, `G_group_cv`, `K_sem_distinct`, `H_sem_entropy`, `conf_S`, `conf_F`, `share_F`

### Metriche Aggiunte (Step 2.1)
✅ **`n_active_prompts`**: N. prompt con activation > 0
✅ **`sparsity_mean/median/min/max`**: Calcolate solo per prompt attivi
✅ **`peak_idx_cv`**: CV della posizione (stabilità)
✅ **`peak_idx_mean/std/mode/min/max`**: Statistiche posizione

### Decisioni Feature Engineering
✅ Meta-tokens INCLUSI come semantic
✅ Sparsity solo per activation > 0
✅ Peak position CV (no overfitting)
✅ Schema → Relationship (3 classi totali)

---

## Validazione Pattern

### Relationship (4 feature)
- ✅ K=3-4 (alta diversità)
- ✅ Sparsity 0.23-0.29 (bassa = diffuso)
- ✅ peak_idx_cv=0.0-0.63 (varia, ma < 1.0)
- ✅ Sempre attivo (5/5 prompt)
- ✅ Layer 1 (basso)
- ✅ conf_S=1.0 (dominanza semantic)

### Semantic (19 feature)
- ✅ K=0-2 (median=1, dictionary-like)
- ✅ Sparsity 0.89 (ALTA = picchi localizzati)
- ✅ Spesso inattivo (median 3/5 prompt)
- ✅ Layer variabile (0-22)

### Say X (16 feature)
- ✅ K=0 (solo functional)
- ✅ Sparsity 0.89 (ALTA = picchi localizzati su "is")
- ✅ Molto selettivo (median 2/5 prompt attivi)
- ✅ Layer alto (7-22)
- ✅ conf_F=1.0 (dominanza functional)

---

## Distribuzione Classi

- **Relationship**: 4 feature (10.3%)
  - Ex-Schema (meta-token): 2 feature
  - Semantic: 2 feature
- **Semantic**: 19 feature (48.7%)
- **Say "X"**: 16 feature (41.0%)

**Totale**: 39 feature, 3 classi

---

## Approvazione Review Gate B

- [x] Schema → Relationship (aggiornato)
- [x] Meta-tokens inclusi come semantic
- [x] Sparsity calcolata solo per activation > 0
- [x] Peak position CV (stabilità)
- [x] Pattern estratti rispecchiano la logica decisionale
- [x] Separazione tra 3 classi è chiara
- [x] Albero decisionale robusto e validato
- [x] **Pronto per Fase 2.2** (implementazione classificatore)

---

## File Output

- **Report analisi**: `output/STEP2_PATTERN_ANALYSIS.md`
- **Feature aggregate**: `output/STEP2_PATTERN_ANALYSIS_FEATURES.csv`
- **CSV ENRICHED aggiornato**: `output/2025-10-21T07-40_export_ENRICHED.csv` (Schema → Relationship)
- **Review Gate B (finale)**: `output/STEP2_REVIEW_GATE_B_FINAL.md` (questo file)

---

**Fase 2.1 COMPLETATA ✅**
**3 classi**: Relationship (4), Semantic (19), Say "X" (16)
**Prossimo**: Fase 2.2 — Implementazione classificatore con albero decisionale validato
