# EDA App per Sistema Labelling Supernodi

App Streamlit per analisi esplorativa della pipeline di labelling supernodi.

## 🚀 Avvio Rapido

### Prerequisiti

Assicurati di aver eseguito la pipeline completa:

```bash
# Windows PowerShell
.\run_full_pipeline.ps1

# Linux/Mac
bash run_full_pipeline.sh
```

Questo genererà tutti i file necessari in `output/`.

### Installazione Dipendenze

```bash
pip install streamlit plotly pandas seaborn matplotlib numpy
```

Oppure:

```bash
pip install -r requirements.txt
```

### Avvio App

```bash
streamlit run eda/app.py
```

L'app si aprirà automaticamente nel browser su `http://localhost:8501`

## 📊 Struttura

### Pagine

1. **📊 Overview** (`01_Overview.py`)
   - Dashboard KPI globali
   - Coverage analysis
   - Export dashboard.json e kpi.csv

2. **🎭 Fase 1 - Features** (`02_Phase1_Features.py`)
   - Explorer features con filtri
   - Grafici (violin, correlazioni, scatter)
   - Archetipi narrativi
   - Dettaglio singola feature con vicinato causale

3. **🌱 Fase 2 - Supernodi** (`03_Phase2_Supernodes.py`)
   - Lista e analisi supernodi cicciotti
   - Coherence history e distribuzione membri
   - Dry-run crescita con parametri configurabili
   - Export dettagli supernodo

4. **🧪 Cross-Prompt** (`04_CrossPrompt.py`)
   - Heatmap attivazione per prompt
   - Statistiche robustezza
   - Analisi worst/best prompt per supernodo

5. **🏭 Fase 3 - Residui** (`05_Phase3_Residuals.py`)
   - Ricalcolo residui con soglie configurabili
   - Clustering on-the-fly multi-dimensionale
   - Merge Jaccard interattivo
   - Coverage comparison baseline vs corrente

6. **🔬 Causal Validation** (`06_Causal_Validation.py`)
   - Validazione cross-prompt: attivazione predice importanza causale?
   - ROC/AUC analysis: activation as predictor
   - Stacked bar chart: importanza vs attivazione per prompt
   - Feature ranking overlap analysis
   - Token analysis (peak on label, peak token distribution)

### Componenti Riusabili

- `components/feature_panel.py`: Pannello dettaglio feature
- `components/supernode_panel.py`: Pannello dettaglio supernodo con dry-run

### Utilities

- `utils/data_loader.py`: Caricamento dati con cache
- `utils/compute.py`: Funzioni ricalcolo (compatibilità, coerenza, clustering)
- `utils/plots.py`: Grafici plotly/seaborn riusabili

### Config

- `config/defaults.py`: Range parametri e default

## 🎛️ Parametri Configurabili

### Fase 2 (Supernodi)

Attivabili con checkbox "Abilita dry-run":

- **Compatibilità:**
  - Peso causale (0.4-0.8, default 0.60)
  - tau_edge_strong (0.02-0.10, default 0.05)
  
- **Crescita:**
  - Threshold bootstrap (0.1-0.5, default 0.30)
  - Threshold normale (0.3-0.7, default 0.45)
  - Min coherence (0.3-0.8, default 0.50)

### Fase 3 (Residui)

- **Soglie ammissione:**
  - tau_inf, tau_aff, tau_inf_very_high
  
- **Clustering:**
  - Min cluster size (2-10, default 3)
  - Layer group span (2-5, default 3)
  - Node influence thresholds (HIGH/MED)
  - Min frequency ratio token semantici
  
- **Merge:**
  - Jaccard threshold (0.5-0.9, default 0.70)

## 📥 Export

L'app consente di esportare:

- Dashboard JSON e KPI CSV (Overview)
- Features filtrate CSV/JSON (Fase 1)
- Supernodi dettagli JSON (Fase 2)
- Clusters correnti CSV/JSON (Fase 3)
- Parametri correnti JSON (tutte le fasi)

File salvati in `eda/exports/` (quando implementato)

## 🔍 Funzionalità Chiave

### Analisi Features

- Filtri per layer e token
- Grafici correlazioni metriche (semantiche + causali)
- Dettaglio feature con:
  - Personalità completa
  - Top parents/children causali
  - Grafico vicinato (se grafo disponibile)
  - Attivazioni per prompt

### Analisi Supernodi

- Lista ordinabile/filtrabile
- Coherence history graficata
- Distribuzione layer/token membri
- Dry-run: ricalcolo compatibilità con parametri custom
- Confronto con versione salvata

### Validazione Cross-Prompt

- Heatmap n_active_members per (supernodo × prompt)
- Ranking stabilità (std bassa)
- Dettaglio per supernodo: attivazione e consistency per prompt

### Clustering Residui

- Ricalcolo in tempo reale con slider
- Confronto coverage baseline vs corrente
- Merge Jaccard visualizzato con log
- Scatter connettività causale vs consistenza

## ⚠️ Note

### Grafo Causale

Se `output/example_graph.pt` non è disponibile:
- Metriche causali non calcolabili
- Edge density non disponibile
- Grafico vicinato non disponibile
- Dry-run limitato a metriche semantiche

L'app continua a funzionare con fallback semantico.

### Performance

- Caricamenti con cache Streamlit (@st.cache_data/resource)
- Dry-run limitato a seed selezionato (non ricalcolo completo)
- Ricalcolo Fase 3 in memoria (no scrittura file)

### Dati Richiesti

**Essenziali:**
- `output/feature_personalities_corrected.json`
- `output/cicciotti_supernodes.json`
- `output/final_anthropological_optimized.json`
- `output/robust_thresholds.json`

**Opzionali:**
- `output/narrative_archetypes.json`
- `output/cicciotti_validation.json`
- `output/graph_feature_static_metrics (1).csv`
- `output/acts_compared.csv`
- `output/example_graph.pt`
- `output/comprehensive_supernode_labels.json`

## 🐛 Troubleshooting

### Import Error

Se ottieni `ModuleNotFoundError: No module named 'eda'`:

```bash
# Esegui da root del progetto
cd c:\Github\circuit_tracer-prompt_rover
streamlit run eda/app.py
```

### Dati Mancanti

Se l'app segnala dati mancanti, esegui prima la pipeline:

```bash
python scripts/01_anthropological_basic.py
python scripts/03_cicciotti_supernodes.py
python scripts/04_final_optimized_clustering.py
```

### Cache Problemi

Se i dati sembrano obsoleti, pulisci la cache:

```bash
# Riavvia l'app, poi nella UI:
# Menu (hamburger) > Clear cache
```

Oppure nella sidebar: Settings > Clear cache

## 📚 References

- **Full documentation**: `docs/supernode_labelling/`
- **Metrics glossary**: `eda/METRICS_GLOSSARY.md` - Complete reference for all metrics
- **Interpretation guide**: `eda/INTERPRETATION_GUIDE.md` - Practical interpretation examples
- **Causal validation guide**: `eda/CAUSAL_VALIDATION_GUIDE.md` - Cross-prompt activation analysis
- **Quick guide (Italian)**: `eda/GUIDA_RAPIDA.md`
- **Implementation plan**: `stream.plan.md`
- **Pipeline scripts**: `scripts/01_anthropological_basic.py`, `scripts/03_cicciotti_supernodes.py`, `scripts/04_final_optimized_clustering.py`

## 💡 Using Tooltips

The app includes extensive tooltips and help text:
- **Hover over metrics** (st.metric) to see definitions and ranges
- **Hover over parameters** (sliders, inputs) to see calculation formulas and effects
- **Read info boxes** for context-specific explanations
- **Check captions** below charts for interpretation guidance

## 🔧 Sviluppo

Per modificare l'app:

1. Modifica file in `eda/`
2. Streamlit rileva automaticamente cambiamenti e ricarica
3. Testa con dati reali da `output/`

### Struttura Codice

```
eda/
├── app.py                    # Entry point
├── pages/                    # Pagine Streamlit
│   ├── 01_Overview.py
│   ├── 02_Phase1_Features.py
│   ├── 03_Phase2_Supernodes.py
│   ├── 04_CrossPrompt.py
│   └── 05_Phase3_Residuals.py
├── components/               # Componenti riusabili
│   ├── feature_panel.py
│   └── supernode_panel.py
├── utils/                    # Utilities
│   ├── data_loader.py
│   ├── compute.py
│   └── plots.py
├── config/                   # Configurazione
│   └── defaults.py
└── exports/                  # Output esportati
```

## ✅ Accettazione

L'app è considerata funzionante se:
- ✅ Dashboard KPI corrispondono a `final_anthropological_optimized.json`
- ✅ Dettagli feature/supernodo completi e visualizzati correttamente
- ✅ Dry-run compatibilità coerente con crescita salvata (entro tolleranze)
- ✅ Export CSV/JSON funzionanti
- ✅ Ricalcolo Fase 3 produce risultati sensati
- ✅ Grafici renderizzano correttamente

## 🎯 Sviluppi Futuri

- [ ] Calcolo edge_density per cluster computazionali (se grafo presente)
- [ ] Export automatico in `eda/exports/` con timestamp
- [ ] Dry-run completo crescita supernodo (non solo compatibilità)
- [ ] Confronto parametri: side-by-side baseline vs custom
- [ ] Integrazione label LLM (se disponibili)
- [ ] Visualizzazione gerarchica supernodi (networkx/graphviz)

---

**Versione:** 1.0.0  
**Autore:** Sistema automatizzato
**Data:** 2025-10-18

