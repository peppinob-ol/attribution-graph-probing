# Circuit Tracing + Strategia Antropologica per Supernodi

Documentazione tecnica per analisi interpretabilità meccanicistica basata su Circuit Tracing (Anthropic) con estensione metodologica originale per supernodi antropologici.

**Attribuzione:** Questo progetto utilizza il framework Circuit Tracing sviluppato da Anthropic come base per implementare metodologie originali di automated concept probing e strategia antropologica per supernodi. Tutti i contributi originali sono chiaramente identificati nelle sezioni appropriate.

## 1. Fondamenta Teoriche (Anthropic)

### 1.1 Circuit Tracing - Lavoro Originale Anthropic

**Sviluppato da:** Anthropic Research Team (2024-2025)

**Riferimenti principali:**
- Paper: "Circuit Tracing: Revealing Computational Graphs in Language Models" (Anthropic, 2025)
- Repository: anthropics/circuit-tracer  
- Companion paper: "On the Biology of a Large Language Model" (Claude 3.5 Haiku analysis)
- Interface interattiva: neuronpedia.org

**Innovazioni chiave sviluppate da Anthropic:**
- Cross-Layer Transcoders (CLT) invece di SAE per-layer tradizionali
- Attribution graphs per prompt specifici invece di analisi globali
- Local replacement model con attention patterns e normalizzazioni frozen
- Linearizzazione degli effetti feature-feature tramite stop-gradients
- Metodologia di circuit tracing manuale con clicking interattivo

### 1.2 Differenze da Approcci Precedenti

**vs. Activation Patching classico:**
- Circuit tracing usa feature interpretabili invece di neuroni MLP
- Attribution graphs mostrano effetti diretti lineari quantificabili

**vs. SAE standard:**
- CLT bridgiano multiple layer MLP, riducendo path length nei grafi
- Evita amplification chains di feature simili attraverso layer

**vs. Mechanistic Interpretability tradizionale:**
- Focus su prompt-specific mechanisms invece di task-general circuits
- Attribution quantificata matematicamente invece di analisi qualitativa

## 2. Contributo Originale: Automated Concept Probing

### 2.1 Estensione del Circuit Tracing Anthropic

**Problema identificato:** Il circuit tracing di Anthropic richiede analisi manuale esperta (~2 ore per prompt, come documentato nel podcast transcript).

**Background metodologico:** Prompt Rover tool precedentemente sviluppato per black box concept extraction da testi LLM, con:
- Automated concept extraction (LLM + spaCy)
- Semantic embedding e graph analysis
- Interactive visualization di relazioni concettuali

**Soluzione proposta:** Integrazione dell'approccio black box (Prompt Rover) con white box analysis (Circuit Tracing Anthropic) per automatizzazione sistematica dell'interpretazione feature.

### 2.2 Architettura del Sistema di Concept Probing

**Step 1: Baseline Attribution Graph (utilizzo framework Anthropic)**
- Input: "The capital of state containing Dallas is"
- Modello: google/gemma-2-2b + Gemma Scope transcoders (Anthropic)
- Attribution graph generation: circuit-tracer library (Anthropic)
- Output: `output/example_graph.pt` (167MB, ~6362 active features)

**Step 2: Automated Concept Extraction (basato su Prompt Rover tool)**
- Metodologia derivata dal tool "Prompt Rover" per black box concept extraction
- LLM prompt per extraction strutturata (eredita approccio `extract_concepts_with_llm`)
- Alternative spaCy-based extraction come fallback (eredita `extract_concepts_alternative`)
- Output format: JSON con label, category, description
- Concetti estratti: entities, relationships, attributes dal prompt originale

**Step 3: Feature Sensitivity Probing (contributo originale)**
Per ogni feature nel grafo originale:
- Test attivazione su label solo
- Test attivazione su "label: description"
- Calcolo metriche comparative per validazione automatica

### 2.3 Metriche di Analisi (bridging black box + white box)

**Approccio ibrido:** Le metriche combinano dati strutturali da Circuit Tracing Anthropic con metodologie di concept sensitivity derivate da Prompt Rover.

**Metriche Statiche** (derivate da attribution graphs Anthropic):
- `frac_external_raw`: 1 - self-weight sul residual stream
- `logit_influence`: norma influenza diretta+indiretta sul logit

**Metriche Dinamiche** (sviluppate per concept probing, metodologia Prompt Rover adattata):
- `attivazione_vecchio_prompt`: valore baseline dal grafo Anthropic
- `nuova_somma_sequenza`: somma attivazioni su nuova sequenza (concept span detection)
- `nuova_somma_label_span`: somma solo su span del label (eredita `_find_subsequence` da Prompt Rover)
- `picco_su_label`: boolean se picco cade su token del concept (adaptation concept-token mapping)
- `cosine_similarity`: similarità con pattern originale (semantic consistency da Prompt Rover)
- `z_score`: deviazione standard rispetto a baseline
- `z_score_robust`: versione IQR-based più robusta
- `density_attivazione`: percentuale token attivi sopra soglia
- `ratio_max_vs_original`: rapporto picchi nuovo/originale
- `twera_total_in`: Target-Weighted Expected Residual Attribution

## 3. Implementazione Tecnica (framework Anthropic + estensioni)

### 3.1 Configurazione Modello (basato su framework Anthropic)

**Configurazione Attribution (parametri standard Anthropic):**
- `max_n_logits = 10`: top logits da attribuire
- `desired_logit_prob = 0.95`: soglia probabilità cumulativa
- `batch_size = 256`: batch size per backward passes
- `max_feature_nodes = 8192`: limite feature nodes nel grafo

### 3.2 Funzioni Core (estensioni al framework Anthropic)

**Feature Analysis Functions (sviluppate per questo progetto):**
- `get_feature_activations_clean()`: estrazione attivazioni allineate al BOS
- `analyze_concepts()`: analisi comparativa sistematica
- `_find_subsequence()`: localizzazione span del label nella sequenza
- `compute_static_metrics()`: calcolo metriche statiche del grafo

## 4. Innovazioni Metodologiche (contributi originali)

### 4.1 Concept-Feature Mapping
- **Problema identificato**: Come validare sistematicamente le ipotesi sui ruoli delle feature derivate da circuit tracing Anthropic?
- **Approccio black box precedente (Prompt Rover)**: Concept extraction automatica da output testuale senza accesso a stati interni
- **Adattamento white box**: Applicazione delle tecniche di concept extraction per interpretare feature interne specifiche
- **Soluzione sviluppata**: Automated probing che usa concetti estratti automaticamente (Prompt Rover) per validare feature interpretation (Circuit Tracing Anthropic)

### 4.2 Multi-Level Sensitivity Analysis
**Label vs Label+Description testing (metodologia originale):**
- Distingue feature che rispondono al token vs al concetto semantico
- Identifica feature polisemantiche vs monosemantiche
- Quantifica robustezza della rappresentazione

### 4.3 TWERA Integration
**Target-Weighted Expected Residual Attribution (estensione metodologica):**
- Rimuove "interference" dai virtual weights
- Usa co-activation statistics per filtering
- Formula: `V_ij^TWERA = (E[a_j * a_i] / E[a_j]) * V_ij`

## 5. Contributo Principale: Strategia Antropologica per Supernodi

**Nota:** Questa sezione descrive metodologia completamente originale, sviluppata indipendentemente dal lavoro Anthropic per automatizzare la creazione di supernodi interpretativi.

### 5.1 Motivazione e Approccio

**Problema del Circuit Tracing Manuale:** Come documentato nel podcast transcript Anthropic, il processo di raggruppamento feature ("lumping together nodes") richiede esperienza e tempo significativo.

**Soluzione Antropologica Proposta:** Analisi sistematica delle "personalità" delle feature per automatizzare la creazione di supernodi coerenti.

### 5.2 Metodologia Implementata

La strategia antropologica introduce un approccio sistematico per la creazione di supernodi basato su analisi comportamentale delle feature. Il metodo si articola in tre fasi:

**Fase 1: Analisi Biografica delle Feature**
- Classificazione in archetipi comportamentali basata su metriche quantitative
- Identificazione di semantic anchors (127 feature) con alta affinità per label e consistenza cross-prompt
- Separazione di feature computazionali da quelle semantiche

**Fase 2: Costruzione Supernodi Semantici ("Cicciotti")**
- Selezione di 37 seed diversificati per layer e peak token
- Crescita narrativa controllata con validation della coerenza interna
- Controllo duplicati globale per evitare sovrapposizioni

**Fase 3: Clustering Residui Computazionali**
- Auto-detection di token strutturali vs semantici per generalizzabilità
- Clustering deterministico basato su layer groups, token types e consistency tiers
- Filtraggio qualitativo delle feature (esclusione garbage layer-0)

### 5.3 File di Implementazione (codice originale)

**Pipeline Strategia Antropologica:**
- `anthropological_basic.py`: Analisi biografica delle 4,865 feature
- `cicciotti_supernodes.py`: Costruzione 37 supernodi semantici
- `final_optimized_clustering.py`: Clustering 17 supernodi computazionali
- `anthropological_strategy_summary.md`: Documentazione metodologica dettagliata

### 5.4 Risultati Quantitativi

| Metrica | Valore | Note |
|---------|--------|------|
| **Supernodi Totali** | 54 | 37 semantici + 17 computazionali |
| **Feature Coperte** | 891 | 18.3% del dataset, zero duplicati |
| **Coverage Qualità** | 83.7% | Escludendo feature non-informative |
| **Coerenza Semantica** | 0.842 | Media supernodi cicciotti |
| **Diversità Computazionale** | 7 token types | Range layer 1-25 |
| **Cross-Prompt Stability** | 100% | Tutti i membri attivi su tutti i prompt |

### 5.5 Innovazioni Metodologiche (contributi originali)

- **Classificazione automatica** delle feature in archetipi comportamentali
- **Crescita controllata** dei supernodi con metriche di coerenza narrativa
- **Auto-detection** dei pattern token per generalizzabilità cross-dominio
- **Separazione intelligente** tra feature semantiche e computazionali
- **Quality filtering** per eliminazione automatica di feature non-informative

## 6. Dataset e Output

### 6.1 File Input (basati su framework Anthropic)
- `output/acts_compared.csv`: 19,460 record di attivazioni comparative
- `output/graph_feature_static_metrics (1).csv`: 6,588 metriche strutturali  
- `output/example_graph.pt`: Grafo attribution generato con circuit-tracer Anthropic

### 6.2 File Output (risultati strategia antropologica)
- `output/final_anthropological_optimized.json`: 54 supernodi finali
- `output/feature_personalities_corrected.json`: Analisi biografica complete
- `output/narrative_archetypes.json`: Classificazione archetipi
- `output/cicciotti_supernodes.json`: 37 supernodi semantici
- `output/cicciotti_validation.json`: Risultati validazione cross-prompt

## 7. Utilizzo

### 7.1 Requisiti
- Framework circuit-tracer di Anthropic per generazione attribution graphs
- Dataset di attivazioni comparative già processato

### 7.2 Riproduzione Pipeline Antropologica

```bash
# 1. Analisi biografica delle feature (da attribution graph Anthropic)
python anthropological_basic.py

# 2. Costruzione supernodi semantici con strategia cicciotti
python cicciotti_supernodes.py

# 3. Clustering computazionale residui
python final_optimized_clustering.py
```

### 7.3 Output e Validazione

**Risultati finali**: `output/final_anthropological_optimized.json`
- 37 supernodi semantici con crescita narrativa controllata
- 17 supernodi computazionali con clustering deterministico
- Metriche di qualità e validazione cross-prompt per ogni supernodo

**Controlli automatici integrati:**
- Integrità (zero duplicati tra supernodi)
- Coerenza semantica (soglia 0.6)
- Stabilità cross-prompt (100% attivazione)
- Quality filtering (esclusione feature non-informative)

## 8. Attribuzioni e Riferimenti

### 8.1 Lavoro Anthropic (fondamenta)
- **Circuit Tracing framework**: Anthropic Research Team
- **Attribution graphs**: Metodo Anthropic
- **Cross-Layer Transcoders**: Tecnologia Anthropic
- **Neuronpedia interface**: Anthropic + comunità

### 8.2 Contributi Originali (questo progetto)
- **Prompt Rover tool**: Framework black box per concept extraction automatica (base metodologica)
- **Automated concept probing**: Integrazione black box + white box per validazione feature
- **Strategia antropologica**: Metodologia completa per supernodi basata su analisi biografica
- **Crescita cicciotti controllata**: Algoritmo per supernodi semantici con controllo duplicati
- **Quality-first clustering**: Approccio deterministico per supernodi computazionali

### 8.3 Documentazione Tecnica
- `anthropological_strategy_summary.md`: Metodologia antropologica dettagliata
- `docs/prompt_rover_README.md`: Documentazione tool Prompt Rover (base concept extraction)
- `docs/podcast_transcript`: Trascrizione discussione ricercatori Anthropic
- `docs/Anthropic_circuit_tracing.md.txt`: Paper Circuit Tracing originale Anthropic
- `docs/github_circuit_tracer.txt`: Documentazione repository Anthropic

## 9. Conclusioni

Questo progetto rappresenta un bridge metodologico tra approcci black box e white box per l'interpretabilità dei modelli linguistici:

- **Foundation black box**: Il tool Prompt Rover fornisce metodologie di concept extraction automatica per analisi comportamentale dei modelli senza accesso agli stati interni

- **Foundation white box**: Il Circuit Tracing di Anthropic fornisce accesso dettagliato agli stati interni tramite attribution graphs e feature interpretation

- **Integrazione metodologica**: La strategia antropologica combina i due approcci, utilizzando tecniche di concept extraction (black box) per automatizzare l'interpretazione di componenti interne (white box)

Il risultato dimostra come metodologie sviluppate per analisi comportamentale esterna possano essere adattate per comprendere automaticamente la struttura interna dei modelli, aprendo possibilità per ibridazione tra interpretabilità black box e mechanistic interpretability.