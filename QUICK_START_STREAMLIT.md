# Quick Start - Streamlit EDA

## 🚀 Avvio Rapido

### Windows PowerShell
```powershell
.\start_streamlit.ps1
```

### Alternative (manuale)
```bash
cd eda
streamlit run app.py
```

---

## 📊 Pagine Disponibili

### 1. **Home** (Welcome)
Panoramica del sistema e check disponibilità dati

### 2. **Phase 1: Features** 
Analisi feature individuali, personalità, archetipi narrativi

### 3. **Node Influence Analysis** ⭐ NUOVO
Analisi causale con node_influence:
- Coverage distribution (top-N)
- Node influence vs probe response
- Feature causali nei cicciotti
- Breakdown interpretabilità

### 4. **Phase 2: Attribution Graph**
Visualizzazione grafo causale

### 5. **Phase 3: Cicciotti**
Analisi supernodi semantici (cicciotti)

### 6. **Phase 4: Causal Validation**
Validazione causale e cross-prompt

### 7. **Phase 5: Final Clustering**
Risultati finali: semantici + computazionali

---

## 🎯 Focus: Node Influence Analysis

Questa pagina mostra l'analisi critica della **causalità** (node_influence) vs **interpretabilità** (probe prompts):

### Metriche Chiave:
- **Top-100 Coverage:** % di node_influence coperta dalle top-100 feature
- **Cicciotti Coverage:** ~25% della node_influence totale
- **Probe-Responsive:** Solo 31% delle top-100 rispondono ai probe

### Grafici:
1. **Distribution Chart:** Come si concentra l'influenza (top-50, 100, 200, ...)
2. **Coverage Breakdown:** Pie chart (cicciotti + probe, solo cicciotti, solo probe, non interpretabili)
3. **Scatter Plot:** node_influence vs probe response (interattivo, colorato per status cicciotti)
4. **Layer Distribution:** node_influence per layer

### Parametri Configurabili:
- **Soglia probe-responsive:** default 15, range 0-100
- **Top-N:** default 100, range 20-500

### Export:
- Summary JSON con tutti i KPI
- CSV top-N feature

---

## 📁 File di Output Necessari

Prima di avviare Streamlit, assicurati di aver eseguito il pipeline:

```bash
# Pipeline completo
python scripts/02_anthropological_basic.py
python scripts/03_compute_thresholds.py
python scripts/04_cicciotti_supernodes.py
python scripts/05_final_optimized_clustering.py
```

File necessari in `output/`:
- `feature_personalities_corrected.json` ✓
- `robust_thresholds.json` ✓
- `cicciotti_supernodes.json` ✓
- `final_optimized_clustering.json` ✓

---

## ⚙️ Configurazione

File di configurazione: `eda/config/defaults.py`

Percorsi output, soglie di default, colori grafici.

---

## 🐛 Troubleshooting

**Errore: "File does not exist: app.py"**
→ Assicurati di essere nella cartella `eda/` o usa `.\start_streamlit.ps1`

**Errore: "Module 'eda' not found"**
→ Il path è configurato automaticamente in `app.py`, verifica di avviare da `eda/`

**Pagine vuote o dati mancanti**
→ Verifica che i file di output esistano con `check_data_availability()` (mostrato in Home)

---

## 📚 Documentazione

- Pipeline completo: `docs/cursor/PIPELINE_THRESHOLDS_CLEANUP.md`
- Feature interpretability: `docs/cursor/FEATURE_INTERPRETABILITY_IMPROVEMENTS.md`
- Causality refactoring: `docs/cursor/REFACTORING_CAUSALITY_COMPLETE.md`

---

**Ultima modifica:** 19 Ottobre 2025  
**Versione pipeline:** v2.0 (node_influence-based)



