# Documentation Index - Circuit Tracer + Prompt Rover

Guida completa a tutti i file di documentazione del progetto.

---

## 📚 Documentazione Principale

### 1. **README.md** 📘
**Tipo**: Documentazione completa  
**Lunghezza**: ~1000 righe  
**Per chi**: Nuovi utenti, contributor, reviewers

**Contenuto**:
- Panoramica architettura completa
- Setup iniziale e requisiti
- Descrizione dettagliata di tutte le 6 fasi della pipeline
- Spiegazione di ogni script Python con input/output
- Metodologia influence-first completa
- Troubleshooting e debugging
- Metriche di successo
- Riferimenti e links

**Quando usarlo**: Prima lettura del progetto, onboarding

---

### 2. **QUICK_REFERENCE.md** ⚡
**Tipo**: Cheat sheet  
**Lunghezza**: ~200 righe  
**Per chi**: Utenti esperti che hanno già letto il README

**Contenuto**:
- Quick start commands
- Tabella file Python con input/output
- Metriche chiave formule
- Thresholds influence-first
- Risultati attuali summary
- Common issues fixes
- Key algorithms snippets

**Quando usarlo**: Reference rapido durante lo sviluppo

---

### 3. **DATA_FLOW.md** 🔄
**Tipo**: Diagrammi di flusso e dipendenze  
**Lunghezza**: ~600 righe  
**Per chi**: Developer che modificano la pipeline

**Contenuto**:
- Flow chart completo ASCII art
- File dependencies matrix
- Execution order (sequential e parallel)
- Data format specifications per ogni JSON
- Iteration scenarios (cosa rifare quando modifichi X)
- Data flow by phase dettagliato
- Critical dependencies
- File size estimates

**Quando usarlo**: Quando modifichi la pipeline o aggiungi features

---

## 🚀 Execution Scripts

### 4. **run_full_pipeline.sh** 🐧
**Tipo**: Bash script per Linux/Mac  
**Lunghezza**: ~400 righe  
**Per chi**: Utenti Linux/Mac

**Contenuto**:
- Script bash completo per eseguire tutte le fasi
- Error handling con exit codes
- Progress reporting con colori
- Summary finale con metriche estratte dai JSON
- Next steps suggeriti

**Come usarlo**:
```bash
chmod +x run_full_pipeline.sh
./run_full_pipeline.sh
```

---

### 5. **run_full_pipeline.ps1** 🪟
**Tipo**: PowerShell script per Windows  
**Lunghezza**: ~400 righe  
**Per chi**: Utenti Windows

**Contenuto**:
- Script PowerShell completo con UTF-8 encoding
- Error handling con exit codes
- Progress reporting con colori PowerShell
- Summary finale con metriche estratte dai JSON
- Next steps suggeriti

**Come usarlo**:
```powershell
.\run_full_pipeline.ps1
```

---

## 🎨 Neuronpedia Export

### 6. **NEURONPEDIA_EXPORT_GUIDE.md** 🌐
**Tipo**: Guida completa export Neuronpedia  
**Lunghezza**: ~500 righe  
**Per chi**: Utenti che vogliono visualizzare i supernodi su Neuronpedia

**Contenuto**:
- Files generati dall'export
- Come visualizzare supernodi su Neuronpedia (metodo URL + manuale)
- Tabelle supernodi semantici e computazionali
- Cosa puoi fare su Neuronpedia (esplorare, interventions, modificare, condividere)
- Parametri configurabili
- Differenze versione standard vs improved
- Troubleshooting (URL troppo lungo, supernodi non visibili, etc.)
- Note su posizione token (`pos`)
- Come includere nell'application MATS
- Links utili

**Quando usarlo**: Dopo aver generato l'export, prima di aprire Neuronpedia

---

### 7. **NEURONPEDIA_QUICK_START.txt** ⚡
**Tipo**: Quick reference per export Neuronpedia  
**Lunghezza**: ~100 righe  
**Per chi**: Utenti che vogliono un riassunto rapido

**Contenuto**:
- Riassunto export completato
- Come visualizzare su Neuronpedia (4 step)
- Lista supernodi inclusi
- Cosa puoi fare su Neuronpedia
- Metriche chiave post influence-first
- Riferimento a guida completa

**Quando usarlo**: Reference immediato dopo export

---

## 📊 Results & Summaries

### 8. **influence_first_summary.md** 📈
**Tipo**: Report metodologico refactoring influence-first  
**Lunghezza**: ~176 righe  
**Per chi**: Reviewer MATS, paper submission

**Contenuto**:
- Problema originale (consistency-based filtering)
- Soluzione influence-first dettagliata
- Risultati "before vs after"
- Breakdown per feature type
- BOS leakage control
- Dual view: situational core vs generalizable scaffold
- Controlli di qualità
- Implicazioni metodologiche

**Quando usarlo**: Per capire il rationale del refactoring, per paper

---

### 9. **RISULTATI_FINALI.txt** 📋
**Tipo**: Riassunto risultati concisi  
**Lunghezza**: ~124 righe  
**Per chi**: Quick review, executive summary

**Contenuto**:
- Metriche finali chiave (coverage 52.3%, BOS 2.4%, etc.)
- Breakdown per feature type
- Supernodi generati (23 totali)
- Thresholds utilizzati
- Confronto before/after refactoring
- Status files output

**Quando usarlo**: Per un colpo d'occhio veloce sui risultati

---

### 10. **IMPLEMENTAZIONE_COMPLETATA.md** ✅
**Tipo**: Report completamento implementazione  
**Lunghezza**: Variabile  
**Per chi**: Developer, project tracking

**Contenuto**:
- Cosa è stato implementato
- Risultati chiave
- File generati
- Implicazioni metodologiche
- Prossimi passi suggeriti

**Quando usarlo**: Fine implementazione, handoff

---

## 📝 Planning & Design

### 11. **plan.md** 📐
**Tipo**: Piano originale refactoring metodologico  
**Lunghezza**: ~364 righe  
**Per chi**: Developer che implementano modifiche

**Contenuto**:
- Obiettivi refactoring
- File da modificare con line numbers
- Code snippets per ogni modifica
- Nuovi metodi da aggiungere
- Pipeline esecuzione
- Output attesi
- To-dos checklist

**Quando usarlo**: Durante implementazione di nuove features

---

## 🎓 Application & Context

### 12. **MATS_Application_Draft.md** 📄
**Tipo**: Application MATS (AI Safety)  
**Lunghezza**: ~369 righe  
**Per chi**: Review committee, context del progetto

**Contenuto**:
- Research proposal
- Metodologia antropologica
- Risultati preliminari
- Obiettivi e milestones
- Motivazioni AI Safety

**Quando usarlo**: Per comprendere il contesto del progetto

---

### 13. **MATS_Visualizations_Guide.md** 📊
**Tipo**: Guida visualizzazioni per application  
**Lunghezza**: ~163 righe  
**Per chi**: Preparazione materiali per application

**Contenuto**:
- Quali visualizzazioni creare
- Come presentare i risultati
- Best practices per grafici
- Screenshot suggestions

**Quando usarlo**: Preparazione presentation/paper

---

## 🔧 Code Documentation

### 14. **Python Scripts** (inline documentation)

Ogni script Python contiene:
- **Docstrings** per funzioni e classi
- **Commenti inline** per logica complessa
- **Type hints** dove appropriato
- **Usage examples** nei main()

**Scripts principali**:
- `anthropological_basic.py` - Core metrics
- `compute_thresholds.py` - Thresholds calculation
- `cicciotti_supernodes.py` - Semantic clustering
- `final_optimized_clustering.py` - Computational clustering
- `verify_logit_influence.py` - Validation
- `visualize_feature_space_3d.py` - 3D plot
- `export_to_neuronpedia.py` / `export_to_neuronpedia_improved.py` - Export
- `analyze_remaining_excluded.py` - Excluded analysis

---

## 📂 Directory Structure

```
circuit_tracer-prompt_rover/
│
├── README.md                              # Documentazione principale
├── QUICK_REFERENCE.md                     # Cheat sheet
├── DATA_FLOW.md                           # Diagrammi flusso
├── DOCUMENTATION_INDEX.md                 # Questo file
│
├── run_full_pipeline.sh                   # Script bash
├── run_full_pipeline.ps1                  # Script PowerShell
│
├── NEURONPEDIA_EXPORT_GUIDE.md           # Guida export Neuronpedia
│
├── influence_first_summary.md             # Report refactoring
├── RISULTATI_FINALI.txt                   # Risultati concisi
├── IMPLEMENTAZIONE_COMPLETATA.md          # Report completamento
│
├── plan.md                                # Piano refactoring
├── MATS_Application_Draft.md              # Application context
├── MATS_Visualizations_Guide.md           # Guida visualizzazioni
│
├── anthropological_basic.py               # Core script
├── compute_thresholds.py                  # Thresholds script
├── cicciotti_supernodes.py               # Semantic clustering
├── final_optimized_clustering.py          # Computational clustering
├── verify_logit_influence.py              # Validation script
├── visualize_feature_space_3d.py         # Visualization script
├── export_to_neuronpedia_improved.py      # Export script
├── analyze_remaining_excluded.py          # Analysis script
│
├── output/                                # Output directory
│   ├── gemma_sae_graph.json              # INPUT
│   ├── feature_personalities_corrected.json
│   ├── feature_typology.json
│   ├── robust_thresholds.json
│   ├── cicciotti_supernodes.json
│   ├── final_anthropological_optimized.json
│   ├── logit_influence_validation.json
│   ├── feature_space_3d.png
│   ├── neuronpedia_url_improved.txt
│   ├── neuronpedia_supernodes_improved.json
│   └── NEURONPEDIA_QUICK_START.txt
│
└── docs/                                  # Additional docs (se presenti)
```

---

## 🗺️ Reading Path by Use Case

### **New User - First Time**

1. **README.md** - Leggi per intero
2. **QUICK_REFERENCE.md** - Bookmark per reference
3. **run_full_pipeline.ps1** (Windows) o **.sh** (Linux) - Esegui
4. **NEURONPEDIA_EXPORT_GUIDE.md** - Leggi prima di usare export

### **Developer - Modifying Pipeline**

1. **DATA_FLOW.md** - Studia dipendenze
2. **plan.md** - Vedi design originale
3. **README.md** (Phase sections) - Capire fase specifica
4. **Python scripts** (inline docs) - Codice

### **Reviewer - Understanding Results**

1. **RISULTATI_FINALI.txt** - Quick overview
2. **influence_first_summary.md** - Metodologia
3. **MATS_Application_Draft.md** - Context
4. **README.md** (Methodology section) - Details

### **Paper Writing - Research Context**

1. **influence_first_summary.md** - Core methodology
2. **MATS_Application_Draft.md** - Research goals
3. **README.md** (Metodologia Influence-First) - Technical details
4. **MATS_Visualizations_Guide.md** - Figures

### **Troubleshooting - Issues**

1. **QUICK_REFERENCE.md** (Common Issues) - Quick fixes
2. **README.md** (Troubleshooting section) - Detailed fixes
3. **DATA_FLOW.md** (Critical Dependencies) - Dependency issues
4. **NEURONPEDIA_EXPORT_GUIDE.md** (Troubleshooting) - Export issues

---

## 🔍 Search by Topic

### **Influence-First Methodology**
- **README.md** § "Metodologia Influence-First"
- **influence_first_summary.md** (entire file)
- **DATA_FLOW.md** § "Phase 2: Threshold Determination"
- **plan.md** § "nuovo criterio di ammissione"

### **Metrics (mean_consistency, max_affinity, etc.)**
- **README.md** § "Fase 2: Analisi Feature Personalities"
- **QUICK_REFERENCE.md** § "Metriche Chiave"
- **plan.md** § "1.2 Modificare analyze_feature_personalities"

### **Thresholds (τ_inf, τ_aff, τ_cons)**
- **README.md** § "compute_thresholds.py"
- **QUICK_REFERENCE.md** § "Thresholds Influence-First"
- **DATA_FLOW.md** § "robust_thresholds.json"

### **Supernodes (Cicciotti)**
- **README.md** § "Fase 3: Costruzione Supernodi Semantici"
- **DATA_FLOW.md** § "Phase 3: Semantic Clustering"
- **Python**: `cicciotti_supernodes.py`

### **Neuronpedia Export**
- **NEURONPEDIA_EXPORT_GUIDE.md** (entire file)
- **NEURONPEDIA_QUICK_START.txt** (quick reference)
- **README.md** § "export_to_neuronpedia_improved.py"
- **Python**: `export_to_neuronpedia_improved.py`

### **Coverage & Validation**
- **RISULTATI_FINALI.txt** (summary)
- **influence_first_summary.md** § "Risultati Finali"
- **README.md** § "verify_logit_influence.py"
- **Output**: `logit_influence_validation.json`

### **BOS Leakage**
- **influence_first_summary.md** § "BOS Leakage Control"
- **README.md** § "BOS Leakage Control"
- **QUICK_REFERENCE.md** § "BOS filter"

### **Feature Typology**
- **README.md** § "classify_feature_typology"
- **QUICK_REFERENCE.md** § "Typology Classification"
- **DATA_FLOW.md** § "feature_typology.json"

---

## 📞 Quick Links by File Type

### Markdown Documentation (.md)
- `README.md` - Main documentation
- `QUICK_REFERENCE.md` - Cheat sheet
- `DATA_FLOW.md` - Flow diagrams
- `DOCUMENTATION_INDEX.md` - This file
- `NEURONPEDIA_EXPORT_GUIDE.md` - Export guide
- `influence_first_summary.md` - Methodology report
- `IMPLEMENTAZIONE_COMPLETATA.md` - Implementation report
- `plan.md` - Design plan
- `MATS_Application_Draft.md` - Application
- `MATS_Visualizations_Guide.md` - Viz guide

### Text Files (.txt)
- `RISULTATI_FINALI.txt` - Results summary
- `output/NEURONPEDIA_QUICK_START.txt` - Export quick start

### Scripts (Execution)
- `run_full_pipeline.sh` - Bash (Linux/Mac)
- `run_full_pipeline.ps1` - PowerShell (Windows)

### Python Scripts (.py)
- See "Directory Structure" section above

### Output Files (.json, .png)
- See `output/` directory listing above

---

## 🆘 Help & Support

### Where to Start
**I'm completely new**: Start with **README.md**

### I Want To...
- **Run the pipeline**: Use `run_full_pipeline.ps1` (Windows) or `.sh` (Linux)
- **Understand a specific phase**: Read relevant section in **README.md**
- **Modify the pipeline**: Study **DATA_FLOW.md** first
- **Export to Neuronpedia**: Read **NEURONPEDIA_EXPORT_GUIDE.md**
- **Fix an error**: Check **QUICK_REFERENCE.md** § "Common Issues"
- **Understand results**: Read **RISULTATI_FINALI.txt** then **influence_first_summary.md**
- **Write a paper**: Read **influence_first_summary.md** and **MATS_Application_Draft.md**

### Contact & Contribution
- Check existing documentation first
- For bugs: Include error message + which script
- For features: Describe use case + expected behavior

---

**Last Updated**: 2025-10-08  
**Documentation Version**: 2.0  
**Total Documentation Files**: 14 (+ 8 Python scripts with inline docs)




