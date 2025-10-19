# Experiments - Analisi e Ottimizzazione Supernodi

Questa cartella contiene script sperimentali per analizzare e ottimizzare i supernodi causali.

## Script Disponibili

### 1. generate_and_analyze_graph.py
Genera un attribution graph su Neuronpedia, lo analizza e crea un subgraph con nodi pinnati strategicamente.

```bash
# L'API key viene letta automaticamente dal file .env
# Assicurati che .env contenga: NEURONPEDIA_API_KEY='your-key'
python scripts/experiments/generate_and_analyze_graph.py
```

**Output**: 
- `output/graph_data/{slug}.json` - Grafo completo scaricato
- `output/graph_data/{slug}_subgraph.json` - Configurazione subgraph

**Cosa fa**:
1. Genera un nuovo attribution graph tramite API Neuronpedia
2. Recupera il JSON completo del grafo generato dall'S3
3. Analizza la struttura per identificare nodi importanti (embeddings, features, logit)
4. Seleziona strategicamente 5 nodi da pinnare basandosi su influence e activation
5. Crea supernodi raggruppando nodi correlati (embeddings insieme, features insieme, ecc.)
6. Salva il subgraph su Neuronpedia con i nodi pinnati

**Usa per**: Creare grafici interattivi su Neuronpedia con flusso end-to-end automatizzato.

**Troubleshooting**: Se il grafo non è visibile su Neuronpedia, consulta [TROUBLESHOOTING_NEURONPEDIA.md](TROUBLESHOOTING_NEURONPEDIA.md)

**Script Helper**: Usa `check_graph_status.py` per verificare quando il grafo diventa disponibile:
```bash
# Controllo singolo
python scripts/experiments/check_graph_status.py gemma-2-2b your-slug

# Attende fino a disponibilità (max 5 min)
python scripts/experiments/check_graph_status.py gemma-2-2b your-slug --wait
```

---

### 2. test_custom_upload.py
Test scientifico per riprodurre "Unknown Source Set (custom upload)" su Neuronpedia.

```bash
python scripts/experiments/test_custom_upload.py
```

**Output**: 
- `output/graph_data/test_custom_upload_prepared.json` - Grafo re-upload con slug modificato

**Esperimento**:
1. Prende `test-graph-fox-20251018-230603.json` (generato dall'API, che FUNZIONA)
2. Cambia **SOLO lo slug** → `custom-reupload-TIMESTAMP`
3. Mantiene **TUTTI** gli altri metadata identici
4. Ricarica il grafo come "custom upload"
5. Confronta con l'originale per vedere se appare "Unknown Source Set"

**Usa per**: Isolare se il problema è:
- ✅ Metadata mancanti → se re-upload funziona, erano i metadata
- ❌ Trattamento diverso dei custom upload → se re-upload fallisce con metadata identici

**Test pulito**: Cambiando SOLO lo slug, isoliamo la variabile e identifichiamo la causa esatta del problema.

---

### 3. make_subgraph_nobos_and_pins.py
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

### 4. check_duplicates_and_jaccard.py
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

### 5. curve_pins_vs_scores.py
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

### 6. content_bos_density.py
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

### 7. add_sourceset_to_exports.py
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
- Esegui dopo aver completato almeno `04_cicciotti_supernodes.py` e `05_final_optimized_clustering.py`.
