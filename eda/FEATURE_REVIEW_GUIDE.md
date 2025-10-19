# Guida: Revisione Feature Influenti

## Obiettivo

**Domanda chiave**: Le feature più influenti dal grafo sono interpretate correttamente?

**Problema**: Non vogliamo perdere feature semantiche importanti che potrebbero essere classificate male perché:
- Le descrizioni Neuronpedia originali sono errate/incomplete
- La feature è semantica ma specializzata su contesti non coperti dai test
- La feature combina semantica + computazionale in modo non standard

## Come Usare la Pagina "02_Phase1_Features"

### 🎯 Workflow Raccomandato

#### 1. **Preset "⚠️ Alto Impatto + Bassa Semantica (REVIEW!)"**

Inizia sempre da qui per vedere feature critiche:

```
Filtro Preset → "⚠️ Alto Impatto + Bassa Semantica (REVIEW!)"
```

Questo mostra feature con:
- `causal_impact > percentile_75` (alto impatto sulla predizione)
- `semantic_score < 0.3` (bassa interpretabilità)

**Azione**: Queste feature DEVONO essere ispezionate manualmente per capire se sono:
- ✅ **Veramente computazionali** (OK, classificazione corretta)
- ⚠️ **Semantiche ma con label errati** (da correggere!)
- 🤔 **Specializzate** (semantiche ma su contesti specifici non testati)

#### 2. **Dashboard Influenza: Scatter Plot Principale**

Guarda il grafico "Influenza Causale vs Interpretabilità Semantica":

- **Quadrante Alto-Destra** (✅ ideale): Feature influenti + interpretabili
  - Queste sono le migliori: alto impatto e chiara semantica
  
- **Quadrante Alto-Sinistra** (⚠️ ATTENZIONE): Influenti ma poco interpretabili
  - **Qui si nascondono i falsi negativi!**
  - Clicca su questi punti per ispezionare nel dettaglio

- **Quadrante Basso-Destra**: Interpretabili ma poco influenti
  - Meno prioritarie ma comunque interessanti

- **Quadrante Basso-Sinistra**: Né influenti né interpretabili
  - Probabilmente outliers reali, bassa priorità

#### 3. **Top 20 Feature per Influenza**

La tabella sotto il grafico mostra le feature più influenti.

**Righe evidenziate in giallo**: richiedono revisione urgente!

**Cosa guardare**:
- `most_common_peak`: Il token è semanticamente rilevante?
- `mean_consistency`: Se = 0, le descrizioni Neuronpedia sono sbagliate
- `max_affinity`: Se > 0.5, la feature è specializzata (non generica)
- `archetype`: La classificazione ha senso dato l'impatto?

#### 4. **Ispeziona Feature Singolarmente**

Nel tab "🔍 Ispeziona Feature":

- **Modalità "Random da 'needs_review'"**: estrai casualmente una feature da rivedere
- Guarda attivazioni cross-prompt (se disponibili)
- Verifica se il `most_common_peak` e le descrizioni corrispondono al comportamento reale

### 📊 Metriche Chiave

#### Causal Impact
```python
causal_impact = abs(node_influence) * 0.6 + output_impact * 0.4
```

Misura quanto la feature influenza causalmente la predizione finale:
- `node_influence`: impatto sulla rete (può essere positivo o negativo)
- `output_impact`: influenza diretta sui logits di output

**Soglia alta**: percentile 75

#### Semantic Score
```python
semantic_score = mean_consistency * 0.5 + max_affinity * 0.3 + label_affinity * 0.2
```

Misura quanto la feature è interpretabile semanticamente:
- `mean_consistency`: generalizzabilità (similarità media con descrizione)
- `max_affinity`: specializzazione (max similarità)
- `label_affinity`: quanto si attiva sul token target

**Soglia bassa**: 0.3

#### Needs Review Flag
```python
needs_review = (causal_impact > high) AND (semantic_score < low)
```

Feature marcate con questo flag sono **priorità massima** per revisione manuale.

## 🔍 Casi d'Uso Specifici

### Caso 1: Feature con consistency=0 ma alta influenza

**Esempio**: `4_13154`, `14_2268` dai probe prompts

```
mean_consistency: 0.0
node_influence: 0.4+
peak_token: "Texas" (semantico!)
```

**Diagnosi**: La descrizione Neuronpedia è errata/assente, ma la feature risponde a prompt semantici.

**Azione**: 
1. Verifica attivazioni sui probe prompts (se disponibili)
2. Controlla il `most_common_peak` - è semantico?
3. Se semantica, considera di aggiornare la label

### Caso 2: Semantic Anchor con bassa influenza

Feature ben interpretate ma non influenti causalmente.

**Azione**: Probabilmente OK, potrebbero essere feature importanti in altri task/contesti.

### Caso 3: Outlier con altissima node_influence

**Esempio**: `25_4717` con node_influence = 0.061, attivazione esplosiva su "Capital" (180.0)

```
archetype: outliers
causal_impact: alto
semantic_score: 0.0
max_ratio: 312000 (!!!)
```

**Diagnosi**: Comportamento estremo, potrebbe essere un artefatto o una feature molto specializzata.

**Azione**: Ispeziona graficamente le attivazioni, potrebbe essere un caso edge.

## 🎯 Preset Filtri: Quando Usarli

| Preset | Quando usarlo |
|--------|---------------|
| **⚡ Top Influenza Causale** | Vuoi vedere le feature più importanti per la predizione |
| **✅ Alto Impatto + Alta Semantica** | Vuoi vedere feature ideali (interpretabili E influenti) |
| **⚠️ Alto Impatto + Bassa Semantica** | **START HERE**: identifica falsi negativi |
| **🎯 Semantic Anchors** | Esplora feature con migliore interpretabilità |
| **❓ Outliers Influenti** | Trova feature non classificate ma importanti |

## 💡 Tips

1. **Colora sempre per `archetype`** negli scatter plot per vedere pattern di classificazione

2. **Ordina tabelle per `causal_impact` descrescente** per prioritizzare feature influenti

3. **Esporta CSV** delle feature "needs_review" per analisi offline

4. **Usa layer_range** per vedere se pattern cambiano per profondità del modello

5. **Cross-riferimento con probe prompts**: Se hai attivazioni su probe prompts specifici, confronta con `most_common_peak` per validare semantica

## 🚨 Red Flags

Feature che richiedono **revisione immediata**:

- ⚠️ `causal_impact > 0.3` AND `mean_consistency = 0.0`
- ⚠️ `node_influence > 0.4` AND classificata come "outlier"
- ⚠️ `most_common_peak` semantico (es. "Texas", "Capital") ma `semantic_score < 0.2`
- ⚠️ Tra le top 20 per influenza ma archetype = "outliers" o "computational_helpers"

## 📈 Metriche di Successo

Una buona analisi dovrebbe portare a:

1. **Zero feature semantiche perse**: Tutte le feature con alto impatto + peak token semantico devono essere identificate

2. **Bassa percentuale "needs_review"** nel top 10% influenza: Significa che le feature più importanti sono ben interpretate

3. **Correlazione causal_impact vs semantic_score > 0.3**: Le feature influenti tendono a essere interpretabili (sistema sano)

4. **Semantic anchors nel top 25% per influenza**: Le feature più interpretabili sono anche causalmente rilevanti






