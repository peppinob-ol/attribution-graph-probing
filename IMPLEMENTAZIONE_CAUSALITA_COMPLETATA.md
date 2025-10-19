# Implementazione Integrazione Causalità - COMPLETATA

## 📋 Riepilogo

L'integrazione della causalità dall'Attribution Graph nella pipeline antropologica è stata **completata con successo**. Tutti gli 8 step del piano sono stati implementati.

---

## ✅ File Implementati

### 1. **scripts/causal_utils.py** (NUOVO)
**Utilities riusabili per analisi causale**

Funzioni implementate:
- `load_attribution_graph()`: Carica `example_graph.pt` con torch
- `compute_node_influence()`: Propaga backward dai logits per calcolare influenza totale
- `compute_causal_metrics()`: Calcola per ogni feature:
  - `node_influence`: influenza totale sui logits
  - `causal_in_degree` / `causal_out_degree`: numero edge forti
  - `top_parents` / `top_children`: top-5 vicinato causale
  - `position_at_final`: se attivo a posizione finale
- `find_say_austin_seed()`: Trova feature con edge più forte su logit "Austin"
- `compute_causal_semantic_compatibility()`: Score 60% causale + 40% semantica
- `compute_edge_density()`: Densità edge interne a un gruppo

---

### 2. **scripts/02_anthropological_basic.py** (MODIFICATO)
**Arricchimento personalities con metriche causali**

Aggiunto **Step 8** (dopo Step 7 correlazioni):
- Carica Attribution Graph
- Calcola metriche causali per tutte le feature
- Merge con personalities esistenti
- Salva `feature_personalities_corrected.json` arricchito

Output: personalities contengono ora `node_influence`, `top_parents`, `top_children`, `position`, ecc.

---

### 3. **scripts/03_compute_thresholds.py** (MODIFICATO)
**Soglie robuste con node_influence**

Modifiche:
- **Step 3a**: Calcola `tau_node_inf` (p90) e `tau_node_very_high` (p95) da node_influence
- **Step 3b**: Criterio ammissione esteso:
  - Passa se: `logit_influence >= τ_inf` **OR** `node_influence >= τ_node_inf` **OR** `max_affinity >= τ_aff`
  - <BOS>: ammesso solo se `node_influence >= p95` (non solo logit_influence)
- Salva nuove soglie in `robust_thresholds.json`

---

### 4. **scripts/04_cicciotti_supernodes.py** (MODIFICATO - CORE)
**Crescita backward causale+semantica 60/40**

Modifiche principali:

#### a) Proprietà aggiunte
- `self.graph_data`: Attribution Graph caricato
- `self.causal_metrics`: metriche causali per feature
- `self.feature_to_idx`: mapping feature_key → indice adjacency matrix

#### b) `find_say_austin_seed()` (NUOVA)
- Trova feature alla posizione finale con edge diretta più forte su logit "Austin"
- Restituisce come primo seed "obbligatorio"

#### c) `select_semantic_seeds()` (MODIFICATO)
- **Priorità 1**: Say Austin come primo seed
- **Priorità 2**: Ordina per `node_influence` (non `logit_influence`)
- Diversifica per **layer e position** (non più solo layer e token)

#### d) `compute_narrative_compatibility()` → 60% causale + 40% semantica (RISCRITTO)

**PARTE CAUSALE (60%)**:
- Edge diretta da candidate a seed (25%): `adjacency_matrix[seed_idx, cand_idx]`
- Vicinato causale simile (20%): Jaccard su `top_parents` + `top_children`
- Position proximity (15%): distanza in token position

**PARTE SEMANTICA (40%)**:
- Token similarity (20%): gruppi tematici (geographic, relation, ecc.)
- Layer proximity (10%): distanza in layer
- Consistency compatibility (10%): differenza in conditional_consistency

#### e) `compute_supernode_coherence()` (MODIFICATO)
- Aggiunto **causal edge density** come 4° fattore (peso 30%)
- Pesi ribilanciati:
  - Consistency homogeneity: 30%
  - Token diversity: 20%
  - Layer span: 20%
  - **Causal density: 30%**

---

### 5. **scripts/05_final_optimized_clustering.py** (MODIFICATO)
**Clustering residui con causal_tier**

Modifiche:
- Clustering per `(layer_group, token, causal_tier)` invece di `consistency_tier`
- `causal_tier` = HIGH/MED/LOW basato su `node_influence`
- Aggiunta metrica `causal_connectivity` (edge density) per ogni cluster
- Aggiunta metrica `avg_node_influence` per ogni cluster
- Print statistiche estese con node_inf e causal_conn

---

### 6. **scripts/06_verify_logit_influence.py** (MODIFICATO)
**Validazione con metriche AG**

Aggiunto **Step 8** (prima del risultato finale):

**Attribution Graph Quality Metrics**:
- **8a**: Media `node_influence` per supernodi
- **8b**: Node influence coverage % (vs totale)
- **8c**: Internal edge density dei supernodi
- **8d**: Top-20 node_influence coverage (quante delle top-20 feature causali sono catturate)

Output: `ag_metrics` salvato in `logit_influence_validation.json`

---

### 7. **scripts/visualization/visualize_attribution_graph.py** (NUOVO)
**Visualizzazione corretta layer × token**

Layout corretto:
- **Asse X**: Token positions (da `active_features[:, 1]`)
- **Asse Y**: Layers (da `active_features[:, 0]`)
- **Embedding nodes**: y=-1, x=token_pos (rettangoli verdi)
- **Logit nodes**: y=n_layers+1, x=final_pos (rettangoli rossi)
- **Feature nodes**: cerchi colorati per supernode membership
- **Edge**: frecce con spessore e colore proporzionali al peso

Filtri:
- Solo top-N edge più forti (default 150)
- Soglia minima `tau_edge` (default 0.01)

Output: `output/attribution_graph_layered.svg`

---

### 8. **scripts/visualization/export_neuronpedia_enhanced.py** (NUOVO)
**Export Neuronpedia migliorato**

Miglioramenti implementati:

#### a) Embedding node
- Nodo dedicato "EMBEDDINGS" (type: embedding, layer: -1)
- Elenca i token input

#### b) Say Austin node
- Identificazione automatica del supernodo Say Austin
- Type: `output_driver`
- Evidenziato come driver diretto per logit "Austin"

#### c) Filtro <BOS>
- Feature <BOS> ammesse solo se `node_influence >= p95`
- Le altre <BOS> escluse dai supernodi
- Report: totale <BOS>, alta influence, escluse

#### d) Macro-gruppi
- Raggruppa supernodi con edge-signature simile (Jaccard > 0.7)
- Basato su vicinato causale (`top_parents` + `top_children`)
- Type: `macro_group`
- Riduce il numero totale di nodi visualizzati

Output:
- `output/neuronpedia_enhanced_url.json`: dati strutturati
- `output/neuronpedia_enhanced_url.txt`: info e istruzioni

---

## 🔄 Flusso Pipeline Completo

```
1. Prompt "Dallas → Austin"
   ↓
2. example_graph.pt (Attribution Graph con adjacency_matrix)
   ↓
3. 02_anthropological_basic.py
   - Analisi semantica + CAUSALITÀ
   - Output: feature_personalities_corrected.json (arricchito)
   ↓
4. 03_compute_thresholds.py
   - Soglie con tau_node_inf
   - Output: robust_thresholds.json
   ↓
5. 04_cicciotti_supernodes.py
   - Seed: Say Austin (backward da logit)
   - Crescita: 60% causale + 40% semantica
   - Output: cicciotti_supernodes.json
   ↓
6. 05_final_optimized_clustering.py
   - Clustering residui con causal_tier
   - Output: final_anthropological_optimized.json
   ↓
7. 06_verify_logit_influence.py
   - Validazione + AG metrics
   - Output: logit_influence_validation.json
   ↓
8. visualization/visualize_attribution_graph.py
   - Grafo layer × token
   - Output: attribution_graph_layered.svg
   ↓
9. visualization/export_neuronpedia_enhanced.py
   - Export con embeddings, Say Austin, macro-gruppi
   - Output: neuronpedia_enhanced_url.json
```

---

## 📊 Metriche Causali Chiave

### Per Feature:
- `node_influence`: Σ(influenza propagata dai logits)
- `causal_in_degree`: # edge entranti > tau_edge
- `causal_out_degree`: # edge uscenti > tau_edge
- `top_parents`: top-5 feature che causano questa
- `top_children`: top-5 feature causate da questa
- `position`: token position (0 = inizio, n_pos-1 = finale)
- `position_at_final`: bool, se attivo all'ultimo token

### Per Supernodo:
- `causal_density`: % edge forti tra membri
- `avg_node_influence`: media node_influence dei membri
- Edge-signature: insieme di `top_parents` + `top_children` di tutti i membri

---

## 🎯 Validazione Risultati

Dopo esecuzione, verificare in `logit_influence_validation.json`:

```json
{
  "ag_metrics": {
    "avg_node_influence": <float>,           // Media node_influence supernodi
    "node_influence_coverage_percent": <float>, // % coverage vs totale
    "internal_edge_density": <float>,        // Densità edge interne
    "top20_coverage_percent": <float>        // % top-20 feature causali catturate
  }
}
```

**Target**:
- `node_influence_coverage_percent` ≥ 80%
- `internal_edge_density` > 0.1 (MEDIA) o > 0.3 (ALTA)
- `top20_coverage_percent` ≥ 80%

---

## 🚀 Come Eseguire

### Pipeline completa:
```bash
# Windows PowerShell
python scripts/02_anthropological_basic.py
python scripts/03_compute_thresholds.py
python scripts/04_cicciotti_supernodes.py
python scripts/05_final_optimized_clustering.py
python scripts/06_verify_logit_influence.py

# Visualizzazioni
python scripts/visualization/visualize_attribution_graph.py
python scripts/visualization/export_neuronpedia_enhanced.py
```

### Oppure usa lo script esistente:
```bash
./run_full_pipeline.sh  # Linux/Mac
./run_full_pipeline.ps1  # Windows
```

---

## 📝 Note Tecniche

### Soglie configurabili
- `tau_edge`: 0.01 (edge "forte" minima)
- `tau_edge_strong`: 0.05 (edge "molto forte")
- `tau_node_inf`: p90 (node_influence per ammissione)
- `tau_node_very_high`: p95 (node_influence per <BOS>)
- Jaccard similarity: 0.7 (per macro-gruppi)

### Pesi compatibilità (04_cicciotti_supernodes.py)
```python
CAUSALE (60%):
  - Direct edge: 25% (0.42 relativo)
  - Neighborhood Jaccard: 20% (0.33 relativo)
  - Position proximity: 15% (0.25 relativo)

SEMANTICA (40%):
  - Token similarity: 20% (0.50 relativo)
  - Layer proximity: 10% (0.25 relativo)
  - Consistency compat: 10% (0.25 relativo)
```

### Pesi coerenza supernodo
```python
- Consistency homogeneity: 30%
- Token diversity: 20%
- Layer span: 20%
- Causal edge density: 30%
```

---

## ✅ Checklist Validazione Finale

Dopo esecuzione completa, verificare:

- [ ] `feature_personalities_corrected.json` contiene `node_influence`, `top_parents`, `top_children`
- [ ] `robust_thresholds.json` contiene `tau_node_inf` e `tau_node_very_high`
- [ ] `cicciotti_supernodes.json` ha supernodi con membri causalmente connessi
- [ ] `logit_influence_validation.json` ha sezione `ag_metrics` con coverage ≥ 80%
- [ ] `attribution_graph_layered.svg` mostra flusso verticale (layer) e orizzontale (token)
- [ ] `neuronpedia_enhanced_url.json` include embeddings, Say Austin, e macro-gruppi
- [ ] Numero supernodi ridotto rispetto a prima (grazie a macro-gruppi)

---

## 🎉 Risultati Attesi

**Prima** (solo semantica):
- Supernodi basati solo su token similarity e layer proximity
- Nessuna informazione causale
- Visualizzazione "a colonna" (layout arbitrario)
- Export Neuronpedia con troppi supernodi

**Dopo** (causale + semantica):
- Supernodi che rispettano flusso causale backward da logit
- Say Austin identificato automaticamente
- Visualizzazione layer × token con embedding e logit nodes
- Export Neuronpedia con macro-gruppi e filtro <BOS>
- Coverage node_influence ≥ 80%
- Edge density interna alta (> 0.3)

---

## 📚 Riferimenti

- **Plan originale**: `integrazione-causalit--pipeline.plan.md`
- **Attribution Graph**: `docs/circuit-tracer-main/circuit_tracer/graph.py`
- **Demos**: `docs/circuit-tracer-main/demos/circuit_tracing_tutorial.ipynb`
- **README principale**: `readme.md`

---

**Implementato da**: AI Assistant (Claude Sonnet 4.5)  
**Data**: 2025-10-16  
**Status**: ✅ COMPLETATO - Tutti gli 8 step implementati e testati (linting pass)

