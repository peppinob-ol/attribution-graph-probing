# Experiments - Analisi e Ottimizzazione Supernodi

Questa cartella contiene script sperimentali per analizzare e ottimizzare i supernodi causali.

## Script Disponibili

### 1. make_subgraph_nobos_and_pins.py
Genera un subgraph JSON senza supernodi BOS e con pin espliciti per logit + embeddings.

```bash
python scripts/experiments/make_subgraph_nobos_and_pins.py
```

**Output**: `output/subgraph_no_bos_pinned.json`

**Cosa fa**:
- Filtra i supernodi semantici che hanno maggioranza di membri BOS
- Pinna il logit "Austin" (o fallback al più probabile)
- Pinna gli embeddings: "Dallas", "capital", "state"
- Aggiunge metadata `sourceSetSlug` per Neuronpedia

**Usa per**: Upload su Neuronpedia con grafo più interpretabile.

---

### 2. check_duplicates_and_jaccard.py
Trova supernodi duplicati sullo stesso layer/posizione/token e calcola Jaccard del vicinato causale.

```bash
python scripts/experiments/check_duplicates_and_jaccard.py
```

**Output**: `output/duplicate_candidates.json`

**Cosa fa**:
- Raggruppa supernodi per (layer, posizione, token) prevalenti
- Calcola Jaccard similarity tra i vicini causali (top parents/children)
- Identifica coppie candidate al merge (Jaccard ≥ 0.7)

**Usa per**: Ridurre frammentazione dei supernodi.

---

### 3. curve_pins_vs_scores.py
Traccia la curva #supernodi → Replacement/Completeness per trovare il punto ottimale.

```bash
python scripts/experiments/curve_pins_vs_scores.py
```

**Output**: `output/pins_vs_scores.csv`

**Cosa fa**:
- Ordina supernodi per somma |node_influence| (più influenti prima)
- Per K=2..30: calcola Replacement/Completeness con i top-K supernodi
- Salva CSV pronto per visualizzazione

**Usa per**: Trovare il "ginocchio" della curva (punto di massima resa interpretativa).

---

### 4. content_bos_density.py
Analizza densità edge: content↔content vs BOS↔content.

```bash
python scripts/experiments/content_bos_density.py
```

**Output**: Stampa a terminale

**Cosa fa**:
- Separa feature content (non-BOS) da feature BOS
- Calcola densità edge interna a ciascun gruppo e tra gruppi
- Stima se la connettività è sostenuta da spine causali o hub generici

**Usa per**: Validare che i supernodi non siano solo "hub BOS".

---

### 5. add_sourceset_to_exports.py
Patch automatico per aggiungere `sourceSetSlug` e `sourceSetName` ai JSON esportati.

```bash
python scripts/experiments/add_sourceset_to_exports.py
```

**Cosa fa**:
- Trova tutti i `*neuronpedia*.json` e `subgraph*.json` in `output/`
- Aggiunge metadata se mancanti:
  - `sourceSetSlug: "gemmascope-transcoder-16k"`
  - `sourceSetName: "GEMMASCOPE - TRANSCODER -16K"`
- Salva in-place

**Usa per**: Risolvere "unknown source set" su Neuronpedia.

---

## Requisiti

- `circuit-tracer` installato (per Replacement/Completeness scores):
  ```bash
  pip install circuit-tracer
  ```

## Note

- Gli script usano i file generati dalla pipeline principale (`01`→`05`).
- Esegui dopo aver completato almeno `03_cicciotti_supernodes.py` e `04_final_optimized_clustering.py`.
