# Step 2.1 — Analisi Pattern dal CSV ENRICHED

## Obiettivo

Estrarre pattern quantitativi dalle tue classificazioni manuali per definire regole euristiche.

---

## Statistiche Generali

- **Righe totali**: 195
- **Feature uniche**: 39
- **Prompt unici**: 5
- **Prompt types**: 3 (entity, attribute, relationship)

### Distribuzione Classi (Ground Truth)

- **Semantic**: 19 feature (48.7%)
- **Say "X"**: 16 feature (41.0%)
- **Relationship**: 4 feature (10.3%)

---

## Classe: Relationship

**N. feature**: 4

**Feature keys**: 1_12928, 1_52044, 1_57794, 1_72774

### Motivazioni Tipiche

1. "layer ≤ 3, altissima attivazione, varianza bassa, attivazioni uniformi e molto alte su ruoli semantici generali; funzione di scaffolding concettuale del prompt"
2. "layer medio-basso, più picchi distinti, max activation diversa da media activation"

### Statistiche Descrittive

| Metrica | Min | Q25 | Median | Q75 | Max | Mean |
|---------|-----|-----|--------|-----|-----|------|
| Layer | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| N. prompt attivi (act>0) | 5.000 | 5.000 | 5.000 | 5.000 | 5.000 | 5.000 |
| N. peak tokens distinti | 3.000 | 3.000 | 3.500 | 4.000 | 4.000 | 3.500 |
| K (token semantici distinti) | 3.000 | 3.000 | 3.500 | 4.000 | 4.000 | 3.500 |
| H (entropia semantica) | 1.371 | 1.371 | 1.646 | 1.922 | 1.922 | 1.646 |
| Share functional peaks | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| Conf_S (dominanza semantic) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| Conf_F (dominanza functional) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| Func vs Sem % (max act diff) | -100.000 | -100.000 | -100.000 | -100.000 | -100.000 | -100.000 |
| U_cv (varianza intra-feature) | 0.390 | 1.022 | 1.353 | 1.632 | 2.103 | 1.300 |
| G_group_cv (varianza tra prompt types) | 0.865 | 0.941 | 0.980 | 1.004 | 1.034 | 0.965 |
| Sparsity (mean, solo act>0) | 0.256 | 0.265 | 0.278 | 0.291 | 0.300 | 0.278 |
| Sparsity (median, solo act>0) | 0.231 | 0.245 | 0.266 | 0.286 | 0.294 | 0.265 |
| Sparsity (min, solo act>0) | 0.190 | 0.194 | 0.203 | 0.217 | 0.235 | 0.208 |
| Sparsity (max, solo act>0) | 0.320 | 0.341 | 0.381 | 0.414 | 0.414 | 0.374 |
| Activation max (media) | 95.293 | 106.086 | 110.171 | 112.413 | 117.679 | 108.328 |
| Activation mean (media) | 70.394 | 76.505 | 79.224 | 80.461 | 82.125 | 77.742 |
| Peak idx CV (stabilità posizione) | 0.000 | 0.000 | 0.281 | 0.579 | 0.632 | 0.298 |
| Peak idx (moda) | 1.000 | 1.000 | 2.500 | 4.000 | 4.000 | 2.500 |

### Pattern Chiave Osservati

- **Layer**: range 1-1, moda 1
- **Dominanza semantic**: conf_S medio 1.00 (>0.6)
- **Alta varianza intra-feature**: U_cv medio 1.30
- **Alta varianza tra prompt types**: G_group_cv medio 0.96
- **Alta diversità semantic tokens**: K medio 3.5 (≥3)
- **Bassa sparsity**: median 0.26 (<0.4, attivazioni diffuse)
- **Peak posizione moderatamente stabile**: CV medio 0.298

---

## Classe: Semantic

**N. feature**: 19

**Feature keys**: 0_1861, 0_230, 0_32742, 0_37567, 0_39374, 0_40780, 0_40936, 0_49560, 0_5200, 0_55815, 0_91045, 0_95057, 16_89970, 18_56027, 1_89326, 20_44686, 22_11998, 7_24743, 7_3144

### Motivazioni Tipiche

1. "attivazione non nettamente più forte su token funzionale 'is' prima di 'Austin, presenza di attivazioni forti token semantici Texas e Dallas, scelgo Texas perché più forte"
2. "diverse functional token (nessuna semantica), ma influenza massima su is"
3. " si attiva solo su Texas"

### Statistiche Descrittive

| Metrica | Min | Q25 | Median | Q75 | Max | Mean |
|---------|-----|-----|--------|-----|-----|------|
| Layer | 0.000 | 0.000 | 0.000 | 7.000 | 22.000 | 4.789 |
| N. prompt attivi (act>0) | 1.000 | 2.000 | 3.000 | 5.000 | 5.000 | 3.211 |
| N. peak tokens distinti | 1.000 | 1.000 | 3.000 | 3.500 | 5.000 | 2.737 |
| K (token semantici distinti) | 0.000 | 0.000 | 3.000 | 3.000 | 4.000 | 2.105 |
| H (entropia semantica) | -0.000 | 0.000 | 1.371 | 1.511 | 2.000 | 0.981 |
| Share functional peaks | 0.000 | 0.000 | 0.200 | 1.000 | 1.000 | 0.411 |
| Conf_S (dominanza semantic) | 0.000 | 0.000 | 0.060 | 1.000 | 1.000 | 0.479 |
| Conf_F (dominanza functional) | 0.000 | 0.000 | 0.955 | 1.000 | 1.000 | 0.522 |
| Func vs Sem % (max act diff) | -100.000 | -100.000 | -10.970 | 100.000 | 100.000 | -5.086 |
| U_cv (varianza intra-feature) | 0.168 | 0.962 | 1.246 | 1.946 | 147.681 | 9.179 |
| G_group_cv (varianza tra prompt types) | 0.393 | 0.794 | 0.927 | 0.979 | 1.205 | 0.871 |
| Sparsity (mean, solo act>0) | 0.621 | 0.851 | 0.899 | 0.901 | 0.929 | 0.861 |
| Sparsity (median, solo act>0) | 0.638 | 0.847 | 0.900 | 0.900 | 0.929 | 0.860 |
| Sparsity (min, solo act>0) | 0.519 | 0.807 | 0.865 | 0.889 | 0.929 | 0.827 |
| Sparsity (max, solo act>0) | 0.708 | 0.900 | 0.900 | 0.944 | 0.944 | 0.898 |
| Activation max (media) | 6.671 | 8.627 | 22.285 | 41.499 | 52.666 | 25.997 |
| Activation mean (media) | 0.587 | 1.288 | 2.591 | 4.335 | 20.174 | 4.087 |
| Peak idx CV (stabilità posizione) | 0.000 | 0.253 | 0.704 | 0.954 | 1.444 | 0.698 |
| Peak idx (moda) | 1.000 | 1.000 | 1.000 | 7.500 | 9.000 | 3.421 |

### Pattern Chiave Osservati

- **Layer**: range 0-22, moda 0
- **Dominanza mista**: conf_S=0.48, conf_F=0.52
- **Alta varianza intra-feature**: U_cv medio 9.18
- **Alta varianza tra prompt types**: G_group_cv medio 0.87
- **Diversità semantic tokens moderata**: K medio 2.1
- **Alta sparsity**: median 0.86 (>0.8, picchi localizzati)
- **Peak posizione variabile**: CV medio 0.698 (>0.5, posizioni diverse)

---

## Classe: Say "X"

**N. feature**: 16

**Feature keys**: 12_87969, 16_98048, 17_1822, 17_98126, 18_3623, 18_61980, 19_13946, 19_54790, 20_74108, 21_16875, 21_61721, 21_84338, 22_32893, 22_74186, 22_81571, 7_89264

### Motivazioni Tipiche

1. "attivazione nettamente più forte su token funzionale 'is' prima di 'Austin, altra attivazione molto più lieve su token funzionale 'is' prima di 'Capital' parola semanticante vicina'"
2. "attivazione nettamente più forte su token funzionale 'is' prima di Capital, altra attivazione più lieve su token funzionale 'is' prima di 'Austin' parola semanticante vicina'"
3. "unica attivazione su token funzionale 'is' prima di 'Austin'"

### Statistiche Descrittive

| Metrica | Min | Q25 | Median | Q75 | Max | Mean |
|---------|-----|-----|--------|-----|-----|------|
| Layer | 7.000 | 17.000 | 19.000 | 21.000 | 22.000 | 18.250 |
| N. prompt attivi (act>0) | 1.000 | 1.000 | 2.000 | 2.000 | 3.000 | 1.750 |
| N. peak tokens distinti | 3.000 | 3.750 | 4.000 | 4.250 | 5.000 | 4.000 |
| K (token semantici distinti) | 1.000 | 2.000 | 3.000 | 3.000 | 3.000 | 2.500 |
| H (entropia semantica) | -0.000 | 0.918 | 1.500 | 1.521 | 1.585 | 1.209 |
| Share functional peaks | 0.200 | 0.200 | 0.400 | 0.400 | 0.600 | 0.350 |
| Conf_S (dominanza semantic) | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 | 0.000 |
| Conf_F (dominanza functional) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |
| Func vs Sem % (max act diff) | 100.000 | 100.000 | 100.000 | 100.000 | 100.000 | 100.000 |
| U_cv (varianza intra-feature) | 1.225 | 1.644 | 1.929 | 2.000 | 3.376 | 2.028 |
| G_group_cv (varianza tra prompt types) | 0.351 | 0.393 | 0.408 | 0.645 | 1.124 | 0.560 |
| Sparsity (mean, solo act>0) | 0.858 | 0.888 | 0.889 | 0.894 | 0.917 | 0.889 |
| Sparsity (median, solo act>0) | 0.858 | 0.889 | 0.889 | 0.894 | 0.917 | 0.889 |
| Sparsity (min, solo act>0) | 0.835 | 0.869 | 0.889 | 0.889 | 0.889 | 0.878 |
| Sparsity (max, solo act>0) | 0.862 | 0.889 | 0.900 | 0.901 | 0.944 | 0.901 |
| Activation max (media) | 1.834 | 3.534 | 7.370 | 9.600 | 22.372 | 7.920 |
| Activation mean (media) | 0.185 | 0.388 | 0.906 | 1.214 | 2.318 | 0.926 |
| Peak idx CV (stabilità posizione) | 0.783 | 0.889 | 1.090 | 1.167 | 1.167 | 1.044 |
| Peak idx (moda) | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 | 1.000 |

### Pattern Chiave Osservati

- **Layer**: range 7-22, moda 21
- **Dominanza functional**: conf_F medio 1.00 (>0.6)
- **Alta varianza intra-feature**: U_cv medio 2.03
- **Alta varianza tra prompt types**: G_group_cv medio 0.56
- **Diversità semantic tokens moderata**: K medio 2.5
- **Alta sparsity**: median 0.89 (>0.8, picchi localizzati)
- **Peak posizione variabile**: CV medio 1.044 (>0.5, posizioni diverse)

---

## Feature Engineering: Metriche Aggiuntive Necessarie?

### Metriche Già Implementate

Le seguenti metriche sono già calcolate in `supernode_classifier (2).py`:

1. **`layer`**: Layer della feature
2. **`U_cv`**: Coefficient of Variation delle z-score (varianza intra-feature)
3. **`G_group_cv`**: Group CV (varianza tra prompt types)
4. **`K_sem_distinct`**: N. token semantici distinti
5. **`H_sem_entropy`**: Entropia dei token semantici
6. **`conf_S` / `conf_F`**: Bootstrap confidence per dominanza semantic/functional
7. **`share_F`**: Frazione di peak functional
8. **`U_q20_layer` / `H_q70_layer`**: Quantili per layer (soglie relative)

### Analisi Motivazioni: Feature Mancanti?

Concetti chiave dalle motivazioni:

- **layer**: 2 motivazioni contengono questi termini
- **varianza**: 1 motivazioni contengono questi termini
- **attivazione**: 5 motivazioni contengono questi termini
- **picchi**: 6 motivazioni contengono questi termini
- **token_type**: 11 motivazioni contengono questi termini
- **sparsity**: 0 motivazioni contengono questi termini
- **max_vs_mean**: 1 motivazioni contengono questi termini

### Metriche Aggiuntive Proposte

Basandomi sulle motivazioni, propongo:

1. **`act_max_vs_mean_ratio`**: `activation_max / activation_mean` (per "max diversa da media")
   - Relationship: ratio alto (più picchi distinti)
   - Semantic: ratio basso (attivazioni uniformi)

2. **`n_peaks_above_threshold`**: N. prompt con attivazione > soglia (es. median + 1*MAD)
   - Relationship: multiple peaks
   - Semantic/Say X: single peak

3. **`peak_concentration`**: Gini coefficient dei peak tokens
   - Dictionary semantic: alta concentrazione (K≈1)
   - Relationship: bassa concentrazione (K≥3)

**Decisione**: Le metriche esistenti sembrano sufficienti. `act_max_vs_mean_ratio` potrebbe essere utile ma è già catturato da `sparsity_ratio` e `U_cv`. Procediamo senza feature engineering aggiuntivo.

---

## Potenziali Ambiguità tra Classi

### Relationship: Sottogruppi Osservati

Relationship ha 4 feature con pattern eterogenei:

- **K_sem_distinct**: range 3-4, median 3.5
- **peak_idx_cv**: range 0.00-0.63, median 0.28
- **Sparsity median**: range 0.23-0.29, median 0.27
- **Osservazione**: Include sia meta-tokens (K=3, peak_idx_cv≈0) che semantic (K=4, peak_idx_cv>0.5)

### Semantic vs Say "X"

- **Layer**: Semantic 0-22, Say X 7-22
- **conf_S**: Semantic 0.48, Say X 0.00
- **conf_F**: Semantic 0.52, Say X 1.00
- **share_F**: Semantic 0.41, Say X 0.35
- **Separazione**: conf_S alto → Semantic; conf_F alto + layer alto → Say X

---

## File Output

- **Report**: `output/STEP2_PATTERN_ANALYSIS.md`
- **Feature aggregate**: `output/STEP2_PATTERN_ANALYSIS_FEATURES.csv`

---

**Fase 2.1 COMPLETATA ✅**
**Prossimo**: Review Gate B — Verifica pattern e approvazione per Fase 2.2
