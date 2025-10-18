# 🎭 Sistema di Labelling dei Supernodi

## 📚 Documentazione Completa

Benvenuto nella documentazione del sistema di labelling dei supernodi! Questo sistema implementa un approccio **ibrido causale-semantico** per identificare e organizzare circuiti computazionali nei modelli linguistici.

---

## 🗺️ Navigazione Rapida

### 📖 Guida Principale
**[SISTEMA_LABELLING_SUPERNODI.md](./SISTEMA_LABELLING_SUPERNODI.md)**  
Documento principale che descrive l'intera architettura del sistema:
- Metafora del "Villaggio delle Feature"
- Architettura a 3 fasi (Antropologica → Cicciotti → Residui)
- Casi concreti completi (CICCIOTTO_2, COMP_5)
- Statistiche finali e interpretazione

**Quando leggerlo**: Inizia da qui per capire l'approccio generale e la filosofia del sistema.

---

### 🔄 Diagramma di Sequenza
**[SEQUENCE_DIAGRAM.md](./SEQUENCE_DIAGRAM.md)**  
Flussi sequenziali dettagliati:
- Pipeline completa end-to-end (User → Output)
- Crescita di singolo supernodo (iterazione per iterazione)
- Calcolo metriche causali (node_influence, vicinato)
- Decision flow: quando accettare/rifiutare candidati

**Quando leggerlo**: Dopo la guida principale, per capire il flusso operativo e le decisioni prese ad ogni step.

---

### 📊 Esempi di Output
**[OUTPUT_EXAMPLES.md](./OUTPUT_EXAMPLES.md)**  
Subset dei dati reali di output:
- Feature personality completa (20_15589)
- Supernodo semantico (CICCIOTTO_14 con 21 membri)
- Cluster computazionale (COMP_3)
- Archetipi narrativi (semantic anchors, contextual specialists)
- Risultati finali comprensivi
- Validazione cross-prompt
- Curve di coherence history

**Quando leggerlo**: Per vedere esempi concreti di come appaiono i dati in output e come interpretarli.

---

### 💻 Code Snippets
**[CODE_SNIPPETS.md](./CODE_SNIPPETS.md)**  
Implementazione completa delle funzioni chiave:
- Fase 1: Analisi antropologica (personalities, archetipi)
- Fase 2: Costruzione cicciotti (seed selection, crescita, compatibilità)
- Fase 3: Clustering residui (auto-detection token, multi-dimensional clustering)
- Utilities causali (edge density, vicinato)

**Quando leggerlo**: Per comprendere l'implementazione tecnica o per riutilizzare parti del codice.

---

### 🧮 Metriche Causali
**[CAUSAL_METRICS.md](./CAUSAL_METRICS.md)**  
Guida completa alle metriche causali:
- Node Influence (backward propagation dai logit)
- Causal In-Degree / Out-Degree (genitori/figli causali)
- Top Parents / Top Children (vicinato causale)
- Position at Final (feature finali)
- Edge Density (connettività causale)

**Quando leggerlo**: Per approfondire la parte causale del sistema e capire come le metriche guidano la crescita dei supernodi.

---

## 🎯 Percorsi di Lettura Consigliati

### 👤 Per Utenti Non Tecnici
1. [SISTEMA_LABELLING_SUPERNODI.md](./SISTEMA_LABELLING_SUPERNODI.md) → Leggi solo:
   - Metafora del Villaggio
   - Architettura a 3 Fasi (overview)
   - Caso Concreto: CICCIOTTO_2
   - Conclusioni
2. [OUTPUT_EXAMPLES.md](./OUTPUT_EXAMPLES.md) → Leggi:
   - Esempio 2: Supernodo Semantico
   - Esempio 5: Risultati Finali Comprensivi

### 🔬 Per Ricercatori (Interpretability/Mechanistic)
1. [SISTEMA_LABELLING_SUPERNODI.md](./SISTEMA_LABELLING_SUPERNODI.md) → Leggi tutto
2. [CAUSAL_METRICS.md](./CAUSAL_METRICS.md) → Focus su:
   - Node Influence (algoritmo e esempi)
   - Edge Density
   - Comparazione Semantico vs Causale
3. [SEQUENCE_DIAGRAM.md](./SEQUENCE_DIAGRAM.md) → Studia:
   - Flusso Calcolo Metriche Causali
   - Decision Flow per candidati
4. [OUTPUT_EXAMPLES.md](./OUTPUT_EXAMPLES.md) → Analizza:
   - Feature Personality Completa
   - Esempio 7: Curve di Coherence

### 💻 Per Sviluppatori (Implementazione)
1. [SISTEMA_LABELLING_SUPERNODI.md](./SISTEMA_LABELLING_SUPERNODI.md) → Overview veloce
2. [CODE_SNIPPETS.md](./CODE_SNIPPETS.md) → Leggi tutto:
   - Implementazione completa delle 3 fasi
   - Utilities causali
   - Pipeline completa
3. [SEQUENCE_DIAGRAM.md](./SEQUENCE_DIAGRAM.md) → Studia flussi operativi
4. [CAUSAL_METRICS.md](./CAUSAL_METRICS.md) → Soglie e tuning

### 🎓 Per Studenti (Apprendimento)
1. [SISTEMA_LABELLING_SUPERNODI.md](./SISTEMA_LABELLING_SUPERNODI.md) → Leggi in ordine:
   - Metafora del Villaggio (intuizione)
   - Fase 1: Analisi Antropologica (concepts)
   - Caso Concreto: CICCIOTTO_2 (esempio passo-passo)
2. [OUTPUT_EXAMPLES.md](./OUTPUT_EXAMPLES.md) → Esplora tutti gli esempi
3. [CODE_SNIPPETS.md](./CODE_SNIPPETS.md) → Leggi codice annotato
4. [CAUSAL_METRICS.md](./CAUSAL_METRICS.md) → Approfondisci metriche

---

## 🔑 Concetti Chiave

### Sistema Ibrido: 60% Causale + 40% Semantica

Il sistema combina:
- **Metriche causali** (node_influence, edge density, vicinato) → catturano la **struttura computazionale**
- **Metriche semantiche** (consistency, affinity, token) → catturano il **significato**

**Perché ibrido?**
- Solo causale: troppo meccanico, perde interpretabilità semantica
- Solo semantico: raggruppa feature per significato senza considerare collaborazione causale
- Ibrido: supernodi che sono sia **circuiti causali** che **gruppi semantici coerenti**

---

### Crescita Organica con Controllo Qualità

I supernodi **non sono pre-definiti**, ma crescono iterativamente:
1. **Inizia con seed** (feature con alta node_influence)
2. **Aggiungi genitori causali** compatibili (backward growth)
3. **Monitora coerenza** ad ogni aggiunta
4. **Stop quando coerenza scende** sotto soglia

**Vantaggi**:
- ✅ Supernodi rispecchiano **circuiti naturali** del modello
- ✅ Controllo duplicati globale (ogni feature in un solo supernodo)
- ✅ Quality gate (coherence threshold) previene supernodi caotici

---

### Dual Coverage: Semantica + Computazionale

**Supernodi Semantici (Cicciotti)**:
- Crescita causale backward da seed influenti
- Alta coerenza semantica + alta connettività causale
- Interpretabili come **circuiti meccanicistici**
- Esempio: CICCIOTTO_2 (20 membri, coherence 0.505)

**Cluster Computazionali**:
- Clustering post-hoc di residui di qualità
- Bassa connettività causale, alta similarità semantica
- Utili per **copertura completa** ma meno interpretabili meccanicisticamente
- Esempio: COMP_3 (7 membri, connectivity 0.18)

**Coverage Finale**: 79.6% delle feature di qualità coperte (251/315)

---

### Auto-Detection vs Hardcoding

Il sistema evita hardcoding:
- ❌ Non token hardcoded (auto-detection structural/semantic/rare)
- ❌ Non thresholds fissi (percentili empirici adattivi)
- ❌ Non domini specifici (generalizzabile oltre Dallas-Austin)

**Vantaggi**:
- ✅ Funziona su **qualsiasi task** senza modifiche
- ✅ Thresholds si adattano alla **distribuzione dei dati**
- ✅ Token classification è **domain-agnostic**

---

## 📈 Metriche di Successo

### Coverage
- **12.3%** delle feature totali (251/2048)
- **79.6%** delle feature di qualità (251/315)
- **72%** garbage identificato e scartato (1482/2048)

### Qualità
- **Coherence media**: 0.58 (supernodi semantici)
- **Cross-prompt validation**: 100% (tutti supernodi attivi su 4 prompt)
- **Narrative consistency**: Alta (archetipi mantenuti)

### Struttura
- **28 supernodi totali**: 15 semantici + 13 computazionali
- **Media membri**: 12.5 (semantici), 4.9 (computazionali)
- **Diversity**: 8 tipi di token nei cluster computazionali

---

## 🛠️ Utilizzo Pratico

### Eseguire la Pipeline

```bash
# PowerShell (Windows)
.\run_full_pipeline.ps1

# Bash (Linux/Mac)
bash run_full_pipeline.sh
```

### Output Generati

```
output/
  feature_personalities_corrected.json    # Personalità di ogni feature
  narrative_archetypes.json               # Classificazione in archetipi
  cicciotti_supernodes.json               # Supernodi semantici
  cicciotti_validation.json               # Validazione cross-prompt
  final_anthropological_optimized.json    # Risultati finali completi
  robust_thresholds.json                  # Soglie influence-first
```

### Interpretare i Risultati

Vedi [OUTPUT_EXAMPLES.md](./OUTPUT_EXAMPLES.md) sezione "Come Leggere gli Output" per checklist interpretazione.

---

## 🎓 Contributi e Sviluppi Futuri

### Limitazioni Attuali
1. Dipendenza da Attribution Graph (fallback a semantica se assente)
2. Computational cost O(n²) per seed (necessita ottimizzazione per >1000 feature)
3. Threshold sensitivity (tau_edge, tau_inf richiedono tuning per dataset diversi)

### Sviluppi Futuri
1. **LLM-Generated Labels**: Integrare LLM per label descrittive automatiche
2. **Multi-Prompt Clustering**: Identificare supernodi task-agnostic vs task-specific
3. **Hierarchical Supernodes**: Meta-supernodi che raggruppano supernodi simili
4. **Causal Attention Flow**: Tracciare edge causali con attention weights
5. **Intervention-Based Metrics**: Misurare influence via ablation causale

---

## 📞 Contatti e Riferimenti

### Repository
- **GitHub**: [circuit_tracer-prompt_rover](https://github.com/...)
- **Branch**: `add_causality`

### File Correlati nel Progetto
```
scripts/
  01_anthropological_basic.py        # Fase 1: Analisi antropologica
  03_cicciotti_supernodes.py         # Fase 2: Costruzione cicciotti
  04_final_optimized_clustering.py   # Fase 3: Clustering residui
  causal_utils.py                    # Utilities metriche causali

docs/
  supernode_labelling/               # Questa documentazione
  IMPLEMENTAZIONE_CAUSALITA_COMPLETATA.md  # Storia implementazione
```

---

## 🎯 Quick Start

**5 minuti per capire il sistema**:
1. Leggi la **Metafora del Villaggio** in [SISTEMA_LABELLING_SUPERNODI.md](./SISTEMA_LABELLING_SUPERNODI.md#-metafora-centrale-il-villaggio-delle-feature)
2. Guarda il **Diagramma di Sequenza Completo** in [SEQUENCE_DIAGRAM.md](./SEQUENCE_DIAGRAM.md#-flusso-completo-end-to-end)
3. Esplora un **Caso Concreto** in [OUTPUT_EXAMPLES.md](./OUTPUT_EXAMPLES.md#-esempio-2-supernodo-semantico-cicciotto)

**30 minuti per implementazione**:
1. Leggi [CODE_SNIPPETS.md](./CODE_SNIPPETS.md) sezione "Fase 2: Costruzione Cicciotti"
2. Studia [CAUSAL_METRICS.md](./CAUSAL_METRICS.md) sezione "Node Influence"
3. Esegui la pipeline e analizza output

**2 ore per mastery completa**:
Leggi tutti i documenti in ordine seguendo il percorso "Per Sviluppatori" sopra.

---

## ✨ Riconoscimenti

Questo sistema è stato sviluppato come parte del progetto **circuit_tracer-prompt_rover** per l'analisi meccanicistica di modelli linguistici (Gemma-2B).

**Approccio**: Anthropological AI Interpretation (ispirato a Neel Nanda, SAE interpretability)

**Innovazioni**:
- Sistema ibrido causale-semantico (60/40)
- Crescita organica backward from logit
- Auto-detection completa (no hardcoding)
- Dual coverage (semantica + computazionale)

---

## 📝 Changelog

### v1.0 (Ottobre 2025)
- ✅ Implementazione sistema completo 3 fasi
- ✅ Documentazione completa (5 file)
- ✅ Metriche causali integrate (node_influence, edge_density)
- ✅ Validazione cross-prompt
- ✅ Auto-detection token e thresholds

---

**Buona esplorazione! 🚀**

Per domande o contributi, apri una issue nel repository.


