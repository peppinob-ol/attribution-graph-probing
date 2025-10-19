# Quick Start - EDA App Supernodi

## 🚀 Avvio in 3 Passi

### 1. Installa dipendenze

```bash
pip install streamlit plotly pandas seaborn matplotlib
```

### 2. Verifica dati disponibili

Assicurati che la pipeline sia stata eseguita:

```bash
# Se non ancora fatto, esegui:
python scripts/02_anthropological_basic.py
python scripts/04_cicciotti_supernodes.py
python scripts/05_final_optimized_clustering.py
```

Verifica che esistano:
- `output/feature_personalities_corrected.json`
- `output/cicciotti_supernodes.json`
- `output/final_anthropological_optimized.json`
- `output/robust_thresholds.json`

### 3. Avvia app

```bash
# Dalla root del progetto:
streamlit run eda/app.py
```

L'app si aprirà automaticamente su `http://localhost:8501`

## 🎯 Cosa Fare Dopo l'Avvio

1. **Controlla Overview** → Dashboard KPI globali
2. **Esplora Features** (Fase 1) → Filtra per layer/token, analizza correlazioni
3. **Analizza Supernodi** (Fase 2) → Abilita dry-run e sperimenta con parametri
4. **Valida Robustezza** (Cross-Prompt) → Verifica stabilità su prompt diversi
5. **Sperimenta Residui** (Fase 3) → Cambia soglie e osserva coverage

## ⚙️ Parametri Chiave da Sperimentare

### Fase 2 (Supernodi)
- **Peso causale**: 0.60 → prova 0.50 o 0.70 e osserva compatibilità candidati
- **Threshold normale**: 0.45 → aumenta (supernodi più piccoli) o diminuisci (più grandi)
- **Min coherence**: 0.50 → valore di stop per crescita

### Fase 3 (Residui)
- **Min cluster size**: 3 → aumenta per cluster più grandi
- **Jaccard merge**: 0.70 → diminuisci per più merge, aumenta per cluster distinti
- **Node influence thresholds**: separano tier HIGH/MED/LOW

## 📥 Export Utili

- **Overview**: `dashboard.json`, `kpi.csv`
- **Fase 1**: `features_filtered.csv` (con filtri applicati)
- **Fase 2**: `supernodes_list.csv`, membri singolo supernodo
- **Fase 3**: `clusters_current.csv`, `phase3_parameters.json`

## 🐛 Problemi Comuni

**"Dati essenziali mancanti"**
→ Esegui la pipeline completa prima dell'app

**"Grafo causale non disponibile"**
→ `output/example_graph.pt` mancante, alcune funzionalità limitate ma app funziona

**"ModuleNotFoundError: eda"**
→ Avvia da root del progetto: `streamlit run eda/app.py`

**Cache obsoleta**
→ Menu hamburger > Clear cache, oppure riavvia app

## 📚 Documentazione Completa

Vedi `eda/README.md` per dettagli completi.

---

**Tip**: Usa la sidebar per navigare tra pagine e configurare parametri!

