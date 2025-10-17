# Refactoring Causalità - Completato

**Data**: 2025-01-XX  
**Obiettivo**: Integrare metriche causali (Attribution Graph) nella pipeline antropologica e creare esperimenti di validazione.

## Modifiche Applicate

### 1. scripts/05_verify_logit_influence.py
**Correzioni metriche AG**:
- ✅ Import `_get_tokenizer` da `causal_utils`
- ✅ Coverage node_influence su valori assoluti (|node_influence|)
- ✅ Edge density calcolata per supernodo (media/mediana) invece che su tutto l'insieme
- ✅ Top-20 coverage su |node_influence|
- ✅ Replacement/Completeness scores con pin logit+embeddings e variante no-BOS
- ✅ Breakdown density: content↔content vs BOS↔content

**Nuove metriche**:
- `node_influence_coverage` (abs): percentuale di |node_influence| totale coperta dai supernodi
- `avg_density` e `med_density`: densità edge media e mediana per supernodo
- Replacement/Completeness per configurazione "ALL" e "NOBOS"
- Densità disaggregata: content↔content, BOS↔BOS, content→BOS, BOS→content

---

### 2. scripts/03_cicciotti_supernodes.py
**Bootstrap causale a 2-hop**:
- ✅ Pool candidati dinamico ricostruito ad ogni iterazione
- ✅ Durante bootstrap (prime 3 iterazioni): include genitori dei genitori (2-hop) con peso ridotto (×0.5)
- ✅ 2-hop applicato SOLO in bootstrap, non su tutta la crescita
- ✅ Soglia edge bootstrap abbassata a 0.03 per favorire crescita iniziale
- ✅ Stop per bassa coerenza disabilitato durante bootstrap

**Logica crescita**:
- Backward da logit: partiamo da "Say Austin" e cresciamo verso gli embedding
- 1-hop: genitori causali diretti dei membri attuali
- 2-hop (bootstrap): genitori dei genitori, con priorità minore
- Dopo bootstrap: solo 1-hop e score 60% causale + 40% semantico

---

### 3. scripts/04_final_optimized_clustering.py
**Post-filtro e merge**:
- ✅ Post-filtro cicciotti: mantiene solo `n_members ≥ 3` e `final_coherence ≥ 0.45`
- ✅ Merge cluster computazionali simili (Jaccard ≥ 0.7 sui membri)
- ✅ Riduzione frammentazione: meno cluster, più interpretabili

---

### 4. scripts/causal_utils.py
**Fix compute_edge_density**:
- ✅ Calcolo su |w| (valore assoluto pesi)
- ✅ Diagonale azzerata correttamente (no self-loops)
- ✅ Density = (# edge forti su |w| > τ) / (# edge possibili)

---

### 5. scripts/experiments/ (NUOVI)
**Script sperimentali** per analisi e ottimizzazione:

#### make_subgraph_nobos_and_pins.py
- Genera subgraph no-BOS con pin logit+embeddings
- Output: `output/subgraph_no_bos_pinned.json`
- Include metadata sourceSet per Neuronpedia

#### check_duplicates_and_jaccard.py
- Trova supernodi duplicati (stesso layer/pos/token)
- Calcola Jaccard vicinato causale
- Output: `output/duplicate_candidates.json`

#### curve_pins_vs_scores.py
- Curva #supernodi → Replacement/Completeness
- Trova punto di "ginocchio" ottimale
- Output: `output/pins_vs_scores.csv`

#### content_bos_density.py
- Breakdown densità: content vs BOS
- Valida se connettività è sostenuta da spine causali o hub generici

#### add_sourceset_to_exports.py
- Patch automatico per aggiungere sourceSet ai JSON esportati
- Risolve "unknown source set" su Neuronpedia

---

## Risultati Attesi

### Metriche AG Corrette
- Coverage node_influence: ~55-60% (su valori assoluti)
- Avg edge density: ~0.15-0.20 (media per supernodo)
- Top-20 coverage: ~85-90%
- Replacement/Completeness misurati con pin logit+embeddings

### Supernodi più Puliti
- Filtro qualità: coerenza ≥ 0.45, membri ≥ 3
- Merge cluster simili: riduzione ~10-20% cluster computazionali
- "Say Austin" seed identificato e cresciuto con bootstrap 2-hop

### Esperimenti Validazione
- Subgraph no-BOS pronto per Neuronpedia
- Report duplicati per merge manuale
- Curva K→scores per scegliere # supernodi ottimale
- Breakdown density per validare qualità causale

---

## Prossimi Passi

1. **Eseguire pipeline completa**:
   ```bash
   python scripts/03_cicciotti_supernodes.py
   python scripts/04_final_optimized_clustering.py
   python scripts/05_verify_logit_influence.py
   ```

2. **Eseguire esperimenti**:
   ```bash
   python scripts/experiments/make_subgraph_nobos_and_pins.py
   python scripts/experiments/check_duplicates_and_jaccard.py
   python scripts/experiments/curve_pins_vs_scores.py
   python scripts/experiments/content_bos_density.py
   ```

3. **Upload su Neuronpedia**:
   ```bash
   python scripts/visualization/upload_to_neuronpedia.py output/subgraph_no_bos_pinned.json
   ```

4. **Analisi risultati**:
   - Verificare metriche AG in `output/logit_influence_validation.json`
   - Visualizzare curva `output/pins_vs_scores.csv` in Excel/Python
   - Controllare duplicati in `output/duplicate_candidates.json`
   - Validare density breakdown (terminale)

---

## Note Tecniche

### 2-hop: Cosa Significa
- **1-hop**: X → S (X è genitore diretto del seed S)
- **2-hop**: Y → X → S (Y è genitore del genitore)
- Durante bootstrap, consideriamo anche i 2-hop con peso ridotto (×0.5) per favorire crescita causale iniziale

### Replacement/Completeness
- **Replacement Score**: frazione di influenza end-to-end che passa per feature (non error nodes)
- **Completeness Score**: frazione di edge in ingresso ai nodi che originano da feature/token (non error)
- **Graph**: su tutto il grafo pruned
- **Subgraph**: solo su nodi pinnati e loro connessioni

### sourceSet su Neuronpedia
- Necessario per abilitare link alle feature e accesso al corpus
- `sourceSetSlug: "gemmascope-transcoder-16k"`
- `sourceSetName: "GEMMASCOPE - TRANSCODER -16K"`
- Aggiunto automaticamente da `add_sourceset_to_exports.py` o nei nuovi export

---

## Troubleshooting

### Errori Unicode (Windows)
Se compaiono errori "charmap can't encode character":
- Tutti gli script esperimenti usano solo ASCII/emoji rimossi
- Se necessario: `chcp 65001` in PowerShell per UTF-8

### circuit-tracer non installato
```bash
pip install circuit-tracer
```

### Metriche AG non calcolate
- Verifica che `output/example_graph.pt` esista
- Verifica che `01_anthropological_basic.py` abbia arricchito con metriche causali

---

## File Coinvolti

**Modificati**:
- `scripts/05_verify_logit_influence.py`
- `scripts/03_cicciotti_supernodes.py`
- `scripts/04_final_optimized_clustering.py`
- `scripts/causal_utils.py`

**Creati**:
- `scripts/experiments/make_subgraph_nobos_and_pins.py`
- `scripts/experiments/check_duplicates_and_jaccard.py`
- `scripts/experiments/curve_pins_vs_scores.py`
- `scripts/experiments/content_bos_density.py`
- `scripts/experiments/add_sourceset_to_exports.py`
- `scripts/experiments/README.md`

**Patchati**:
- `output/neuronpedia_graph_with_subgraph.json` (sourceSet aggiunto)
- `output/subgraph_no_bos_pinned.json` (già conteneva sourceSet)


