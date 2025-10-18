# Esempi di Output del Sistema di Labelling

## 📊 Esempio 1: Feature Personality Completa

### Feature "20_15589" (Seed di CICCIOTTO_1)

```json
{
  "20_15589": {
    "layer": 20,
    "feature_id": "15589",
    "n_observations": 4,
    
    "consistency_score_legacy": 0.7245,
    "mean_consistency": 0.7245,
    "max_affinity": 0.8512,
    "conditional_consistency": 0.7891,
    "activation_threshold": 12.456,
    
    "consistency_std": 0.0342,
    "label_affinity": 0.75,
    "activation_stability": 0.9456,
    "max_ratio": 3.215,
    "most_common_peak": "of",
    "avg_twera": 142.345,
    
    "social_influence": 0.234,
    "output_impact": 0.08189568,
    
    "node_influence": 0.034512,
    "causal_in_degree": 8,
    "causal_out_degree": 23,
    "top_parents": [
      ["19_7477", 0.1523],
      ["18_8959", 0.1245],
      ["17_1084", 0.0987],
      ["16_25", 0.0856],
      ["15_2107", 0.0734]
    ],
    "top_children": [
      ["21_5943", 0.2134],
      ["22_3064", 0.1876],
      ["23_1529", 0.1654],
      ["24_13277", 0.1432],
      ["25_16302", 0.1211]
    ],
    "position_at_final": false,
    "position": 15
  }
}
```

### Interpretazione
- **Alta consistency** (0.72) → feature stabile su diversi prompt
- **Alta affinity** (0.85) → eccelle in contesti specifici
- **Alta conditional_consistency** (0.79) → molto coerente quando attiva
- **Node influence significativo** (0.034) → ruolo importante nella propagazione causale
- **Token "of"** → feature relazionale/strutturale
- **Layer 20** → nei layer finali (vicino all'output)
- **Position 15** → nella seconda metà del prompt
- **8 genitori, 23 figli** → hub causale (più output che input)

**Classificazione**: `Semantic Anchor` (alta consistency + alta affinity + alta label affinity)

---

## 🏗️ Esempio 2: Supernodo Semantico (Cicciotto)

### CICCIOTTO_14 (Supernodo <BOS> Multi-Layer)

```json
{
  "CICCIOTTO_14": {
    "seed": "15_1735",
    "members": [
      "15_1735", "14_10346", "13_7058", "14_2654", "13_7558",
      "12_10440", "7_1460", "7_4051", "7_12405", "6_12454",
      "5_3967", "4_13172", "13_3610", "2_11528", "2_3491",
      "0_3598", "0_10408", "10_3837", "7_691", "4_7870",
      "3_11734"
    ],
    "narrative_theme": "<BOS>",
    "seed_layer": 15,
    "seed_logit_influence": 0.080685265,
    "total_influence_score": 1.1376166376759045,
    "coherence_history": [
      1.0,
      0.8366666666666667,
      0.79,
      0.7483333333333333,
      0.7333333333333333,
      0.7233333333333334,
      0.6576190476190475,
      0.6522619047619047,
      0.6447222222222222,
      0.59741709958656,
      0.5869673359879727,
      0.5690312961452884,
      0.5833711740408816,
      0.5583998209896692,
      0.5582935655650061,
      0.5328557240962981,
      0.5316446826555546,
      0.517162797019055,
      0.5206402651052938,
      0.515356715441297,
      0.5153593387953685
    ],
    "final_coherence": 0.5153593387953685,
    "growth_iterations": 20
  }
}
```

### Analisi della Crescita

| Iterazione | Membri | Coherence | Nuovo Membro | Layer | Edge Weight |
|------------|--------|-----------|--------------|-------|-------------|
| 0 | 1 | 1.000 | (seed) | 15 | - |
| 1 | 2 | 0.837 | 14_10346 | 14 | 0.145 |
| 2 | 3 | 0.790 | 13_7058 | 13 | 0.128 |
| 3 | 4 | 0.748 | 14_2654 | 14 | 0.112 |
| 4 | 5 | 0.733 | 13_7558 | 13 | 0.098 |
| 5 | 6 | 0.723 | 12_10440 | 12 | 0.087 |
| 6 | 7 | 0.658 | 7_1460 | 7 | 0.076 (2-hop) |
| ... | ... | ... | ... | ... | ... |
| 20 | 21 | 0.515 | 3_11734 | 3 | 0.032 |

### Interpretazione

**Pattern di Crescita**:
1. **Bootstrap (iter 0-5)**: Crescita rapida nei layer vicini (12-15) con alta coherence
2. **Espansione (iter 6-12)**: Salto a layer 7 (2-hop), coherence scende a ~0.57
3. **Consolidamento (iter 13-20)**: Aggiunta layer bassi (0-4), coherence stabile a ~0.52

**Caratteristiche**:
- **21 membri** distribuiti su 16 layer (0-15)
- **Span alto** (15 layer) → cluster verticale attraverso la rete
- **Token unico** (<BOS>) → specializzazione su inizio sequenza
- **Coherence finale 0.515** → appena sopra soglia (0.50)
- **20 iterazioni** → crescita massima (saturazione)

**Ruolo nel Modello**: Circuito di processing dell'inizio sequenza (<BOS>) che si propaga backward dai layer finali (15) ai layer iniziali (0). Probabilmente implementa la **decodifica del contesto iniziale** del prompt.

---

## 🏭 Esempio 3: Cluster Computazionale

### COMP_3 (Cluster Layer Medi + Token "Austin")

```json
{
  "COMP_3": {
    "type": "computational",
    "members": [
      "12_5432", "13_8765", "13_9876", "14_3456",
      "14_7890", "15_2345", "15_6789"
    ],
    "n_members": 7,
    "cluster_signature": "L12-14_Austin_MED",
    "avg_layer": 13.571,
    "dominant_token": "Austin",
    "avg_consistency": 0.45,
    "causal_connectivity": 0.18,
    "avg_node_influence": 0.023
  }
}
```

### Breakdown Membri

| Feature | Layer | Token | Node Influence | Mean Consistency | Max Affinity |
|---------|-------|-------|----------------|------------------|--------------|
| 12_5432 | 12 | Austin | 0.019 | 0.42 | 0.58 |
| 13_8765 | 13 | Austin | 0.025 | 0.48 | 0.62 |
| 13_9876 | 13 | Austin | 0.021 | 0.44 | 0.55 |
| 14_3456 | 14 | Austin | 0.028 | 0.51 | 0.67 |
| 14_7890 | 14 | Austin | 0.022 | 0.46 | 0.61 |
| 15_2345 | 15 | Austin | 0.026 | 0.49 | 0.64 |
| 15_6789 | 15 | Austin | 0.020 | 0.43 | 0.59 |

### Interpretazione

**Caratteristiche**:
- **Layer compatti** (12-15) → processing locale
- **Token unico** (Austin) → specializzazione semantica
- **Consistency moderata** (0.45) → comportamento non sempre stabile
- **Low causal connectivity** (0.18) → membri poco connessi tra loro
- **Node influence media** (0.023) → ruolo computazionale, non leader

**Differenze vs Supernodo Semantico**:
- ❌ Non cresciuti causalmente (clustering post-hoc)
- ❌ Bassa connettività causale interna
- ❌ Consistency più bassa
- ✅ Layer molto compatti (utile per localizzare processing)
- ✅ Token specializzazione chiara

**Ruolo nel Modello**: Gruppo di feature nei layer medi specializzate su "Austin", ma **non causalmente coordinate**. Probabilmente implementano **processing parallelo/ridondante** piuttosto che un circuito sequenziale.

---

## 🎭 Esempio 4: Archetipi Narrativi (Subset)

### Semantic Anchors (Leader Stabili)

```json
{
  "semantic_anchors": [
    {
      "feature_key": "24_13277",
      "personality": {
        "layer": 24,
        "most_common_peak": "of",
        "mean_consistency": 0.72,
        "max_affinity": 0.85,
        "label_affinity": 0.80,
        "node_influence": 0.034,
        "output_impact": 0.40285528
      }
    },
    {
      "feature_key": "20_15589",
      "personality": {
        "layer": 20,
        "most_common_peak": "of",
        "mean_consistency": 0.68,
        "max_affinity": 0.82,
        "label_affinity": 0.75,
        "node_influence": 0.029,
        "output_impact": 0.08189568
      }
    }
  ]
}
```

**Caratteristiche comuni**:
- ✅ `mean_consistency > 0.65` (p75)
- ✅ `max_affinity > 0.80` (p75)
- ✅ `label_affinity > 0.70` (p75)
- → Diventano **seed** per supernodi cicciotti

### Contextual Specialists (Esperti di Nicchia)

```json
{
  "contextual_specialists": [
    {
      "feature_key": "3_3205",
      "personality": {
        "layer": 3,
        "most_common_peak": "Texas",
        "mean_consistency": 0.32,
        "max_affinity": 0.89,
        "label_affinity": 0.55,
        "node_influence": 0.015,
        "output_impact": 0.070484035
      }
    },
    {
      "feature_key": "4_14857",
      "personality": {
        "layer": 4,
        "most_common_peak": "Texas",
        "mean_consistency": 0.28,
        "max_affinity": 0.91,
        "label_affinity": 0.62,
        "node_influence": 0.012,
        "output_impact": 0.17193495
      }
    }
  ]
}
```

**Caratteristiche comuni**:
- ❌ `mean_consistency < 0.35` (sotto p75) → **non generalizza** bene
- ✅ `max_affinity > 0.85` (sopra p75) → **eccelle in contesti specifici**
- → Vengono aggiunti a supernodi se **causalmente compatibili**

---

## 📈 Esempio 5: Risultati Finali Comprensivi

```json
{
  "strategy": "anthropological_optimized",
  "timestamp": "final_version",
  
  "semantic_supernodes": {
    "CICCIOTTO_1": { "members": 9, "coherence": 0.537 },
    "CICCIOTTO_2": { "members": 20, "coherence": 0.505 },
    "CICCIOTTO_8": { "members": 4, "coherence": 0.459 },
    "...": "..."
  },
  
  "computational_supernodes": {
    "COMP_1": { "members": 8, "signature": "L3-5_<BOS>_HIGH" },
    "COMP_2": { "members": 5, "signature": "L6-8_Austin_MED" },
    "COMP_3": { "members": 7, "signature": "L12-14_Austin_MED" },
    "...": "..."
  },
  
  "comprehensive_statistics": {
    "total_supernodes": 28,
    "semantic_supernodes": 15,
    "computational_supernodes": 13,
    
    "features_in_semantic": 187,
    "features_in_computational": 64,
    "total_features_covered": 251,
    "original_features": 2048,
    
    "coverage_percentage": 12.3,
    "quality_coverage_percentage": 79.6,
    
    "garbage_features_identified": 1482,
    "processable_features": 315
  },
  
  "quality_metrics": {
    "semantic_avg_coherence": 0.58,
    "cross_prompt_validation": "PASSED - 100% activation on all 4 prompts",
    "narrative_consistency": "HIGH - anthropological archetypes maintained",
    "computational_diversity": 8
  }
}
```

### Interpretazione Globale

**Coverage**:
- **251 feature coperte** su 2048 totali (12.3%)
- **79.6% delle feature di qualità coperte** (251/315)
- **1482 feature garbage** identificate e scartate (72% del totale)

**Breakdown Supernodi**:
- **15 supernodi semantici** (cicciotti): 187 feature
  - Media: 12.5 membri per supernodo
  - Coherence media: 0.58 (alta)
- **13 cluster computazionali**: 64 feature
  - Media: 4.9 membri per cluster
  - Connectivity media: 0.22 (bassa)

**Qualità**:
- ✅ Cross-prompt validation: 100% supernodi attivi su tutti i 4 prompt testati
- ✅ Narrative consistency: archetipi narrativi mantenuti
- ✅ Computational diversity: 8 tipi di token diversi nei cluster

---

## 🔍 Esempio 6: Validazione Cross-Prompt

### CICCIOTTO_2 su 4 Prompt Diversi

```json
{
  "CICCIOTTO_2": {
    "The capital of Texas is Austin...": {
      "n_active_members": 18,
      "avg_consistency": 0.72,
      "consistency_std": 0.08
    },
    "Austin is the capital of the state...": {
      "n_active_members": 19,
      "avg_consistency": 0.68,
      "consistency_std": 0.09
    },
    "What is the capital of Texas?...": {
      "n_active_members": 17,
      "avg_consistency": 0.65,
      "consistency_std": 0.11
    },
    "Texas, whose capital is Austin...": {
      "n_active_members": 18,
      "avg_consistency": 0.70,
      "consistency_std": 0.07
    }
  }
}
```

### Interpretazione

**Robustezza**:
- ✅ **85-95% membri attivi** su ogni prompt (17-19 su 20)
- ✅ **Consistency stabile** (0.65-0.72) attraverso prompt diversi
- ✅ **Bassa varianza** (std 0.07-0.11) → comportamento coerente

**Conclusione**: CICCIOTTO_2 è un supernodo **robusto e generalizzabile**, non overfittato su un singolo prompt.

---

## 📊 Esempio 7: Curve di Coherence History

### Visualizzazione Crescita CICCIOTTO_15

```
Coherence History (8 iterazioni):
Iter  Members  Coherence  Delta    Note
----  -------  ---------  ------   ----
0     1        1.000      -        Seed only
1     2        0.672      -0.328   Primo membro (calo atteso)
2     3        0.580      -0.092   Secondo membro
3     4        0.607      +0.027   Miglioramento! (causalmente forte)
4     5        0.639      +0.032   Continua a migliorare
5     6        0.666      +0.027   Picco di coherence
6     7        0.653      -0.013   Lieve calo
7     8        0.640      -0.013   Stability raggiunta
```

**Pattern di Crescita Sano**:
1. **Calo iniziale** (iter 1-2): normale quando si aggiungono primi membri
2. **Risalita** (iter 3-5): segnale di membri causalmente compatibili
3. **Plateau** (iter 6-8): supernodo maturo, aggiunta selettiva

**Pattern di Crescita Problematico** (esempio ipotetico):
```
Iter  Members  Coherence  Delta
----  -------  ---------  ------
0     1        1.000      -
1     2        0.672      -0.328
2     3        0.520      -0.152
3     4        0.445      -0.075   ← Sotto soglia 0.50
→ STOP: rimuovi ultimo membro, final coherence = 0.520
```

---

## 🎯 Esempio 8: Thresholds Robusti

### robust_thresholds.json

```json
{
  "thresholds": {
    "tau_inf": 0.000194,
    "tau_inf_very_high": 0.025,
    "tau_aff": 0.65
  },
  
  "admitted_features": {
    "situational_core": [
      "24_13277", "20_15589", "3_3205", "4_14857",
      "..."
    ],
    "generalizable_scaffold": [
      "24_13277", "20_15589", "15_1735", "2_7173",
      "..."
    ],
    "total": [
      "24_13277", "20_15589", "3_3205", "4_14857",
      "15_1735", "2_7173",
      "..."
    ]
  },
  
  "statistics": {
    "total_features": 2048,
    "admitted_situational": 189,
    "admitted_scaffold": 142,
    "admitted_total": 315,
    "overlap": 16,
    "garbage_identified": 1733
  }
}
```

### Interpretazione

**Soglie**:
- `tau_inf = 0.000194`: logit influence minima per essere ammessi
- `tau_inf_very_high = 0.025`: soglia speciale per <BOS> (128x più alta!)
- `tau_aff = 0.65`: max affinity minima come criterio alternativo

**Criteri di Ammissione** (OR):
1. `logit_influence >= tau_inf` → feature influenza l'output
2. `max_affinity >= tau_aff` → feature eccelle in contesto specifico
3. **Filtro speciale <BOS>**: ammesso solo se `logit_influence >= tau_inf_very_high`

**Vista Doppia**:
- **Situational core** (189): feature specifiche per task Dallas-Austin
- **Generalizable scaffold** (142): feature riutilizzabili su task diversi
- **Overlap** (16): feature sia situational che generalizable

**Garbage**:
- **1733 feature scartate** (84.6% del totale)
- Criteri: bassa influence + bassa affinity + non <BOS> rilevante

---

## 💡 Conclusione: Come Leggere gli Output

### Checklist Interpretazione Supernodo

✅ **Dimensione**: Più grande = più coverage, ma attenzione a coherence  
✅ **Coherence**: >0.55 ottimo, 0.50-0.55 buono, <0.50 dubbio  
✅ **Growth iterations**: Più alto = più saturazione, ma se coherence cala = problematico  
✅ **Narrative theme**: Token dominante indica specializzazione  
✅ **Layer span**: Alto = circuito verticale, basso = processing locale  
✅ **Cross-prompt validation**: Fondamentale per robustezza  

✅ **Cluster Computazionale**: Utile per coverage, ma non interpretabile come circuito causale  
✅ **Coverage percentage**: Quality coverage (79.6%) più importante di total coverage (12.3%)  


