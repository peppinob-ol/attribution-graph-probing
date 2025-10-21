# Pulizia Sistema Thresholds

**Data:** 19 Ottobre 2025  
**Problema:** Due file per calcolare soglie (`03_compute_thresholds.py` e `03b_compute_thresholds_probe_based.py`)  
**Soluzione:** Merge e semplificazione → un solo file

---

## 🎯 Decisione

**File mantenuto:** `scripts/03_compute_thresholds.py`

**File eliminati:**
- `scripts/03b_compute_thresholds_probe_based.py` 
- `output/probe_based_thresholds.json` (non più generato)

---

## 📊 Motivazione (dall'analisi Node Influence)

Dall'analisi in Streamlit è emerso che:

1. **Node Influence è la metrica causale corretta** (non logit_influence)
   - Top-100: **31.7%** della node_influence totale
   - Cicciotti: **25.0%** della node_influence totale

2. **Probe prompts NON catturano tutte le feature causalmente importanti**
   - Solo **31%** delle top-100 per node_influence rispondono ai probe (nuova_max >= 15)
   - Solo **18.4%** della node_influence totale è probe-responsive

3. **Conclusione:**
   - Usare `nuova_max_label_span` (probe) come criterio di **ammissione** era **sbagliato**
   - Le feature causalmente importanti NON sempre rispondono ai probe prompts
   - I probe sono utili per **interpretabilità**, non per **selezione**

---

## ✅ File Modificati

### 1. `scripts/04_cicciotti_supernodes.py`
**Cambiamento:** Rimossa logica di fallback `probe_based_thresholds.json` → `robust_thresholds.json`

```python
# PRIMA:
if os.path.exists("output/probe_based_thresholds.json"):
    ...
else:
    with open("output/robust_thresholds.json", 'r') as f:
        ...

# DOPO:
with open("output/robust_thresholds.json", 'r') as f:
    thresholds_data = json.load(f)
print("✅ Usando robust_thresholds.json (node_influence-based)")
```

### 2. `scripts/05_final_optimized_clustering.py`
**Cambiamento:** 
- Rimossa logica di fallback `probe_based_thresholds.json`
- Rimosso breakdown "Probe-responsive / High-influence" (specifico di probe_based)
- Mantenuto breakdown "Situational core / Generalizable scaffold"

```python
# DOPO:
with open("output/robust_thresholds.json", 'r') as f:
    thresholds_data = json.load(f)
print("✅ Usando robust_thresholds.json (node_influence-based)")
```

---

## 📋 Pipeline Corretto

```bash
# 1. Calcola soglie (NODE INFLUENCE + LOGIT INFLUENCE)
python scripts/03_compute_thresholds.py

# 2. Genera cicciotti semantici
python scripts/04_cicciotti_supernodes.py

# 3. Clustering finale (semantici + computazionali)
python scripts/05_final_optimized_clustering.py
```

**Output:** `output/robust_thresholds.json`

---

## 🔍 Struttura `robust_thresholds.json`

```json
{
  "thresholds": {
    "tau_inf": 0.xxx,           // Logit influence (p80 o p90)
    "tau_node_inf": 0.xxx,      // Node influence (p85, relaxed)
    "tau_inf_very_high": 0.xxx, // Per <BOS> filtering (p90)
    "tau_node_very_high": 0.xxx,// Per <BOS> filtering (p90)
    "tau_aff": 0.60,            // Max affinity
    "tau_cons": 0.40            // Mean consistency (relaxed)
  },
  "admitted_features": {
    "situational_core": [...],      // Solo influence
    "generalizable_scaffold": [...], // Affinity OR consistency
    "total": [...]                   // Union
  },
  "coverage": {
    "coverage_percent": 88.5,
    ...
  }
}
```

---

## 📈 Metriche Chiave

### Coverage (con robust_thresholds)
- **Logit influence:** ~88% coverage
- **Node influence (cicciotti):** ~25% coverage

### Interpretabilità
- **31%** delle top-100 per node_influence sono probe-responsive
- **25%** della node_influence è coperta dai cicciotti
- **18.4%** della node_influence è probe-responsive (nuova_max >= 15)

---

## 💡 Ruolo dei Probe Prompts

**NON PIÙ usati per:**
- ❌ Criteri di ammissione feature
- ❌ Generazione soglie (tau_probe)

**ANCORA usati per:**
- ✅ Seed scoring (priorità in `nuova_max_label_span` + node_influence)
- ✅ Interpretabilità feature (visualizzazione in Streamlit)
- ✅ Analisi qualitativa dei cicciotti

---

## 🎯 Vantaggi

1. **Semplificazione:** Un solo file di thresholds
2. **Chiarezza:** Node influence = metrica causale
3. **Correttezza:** Non escludiamo feature causalmente importanti solo perché non rispondono ai probe
4. **Consistenza:** Tutto il pipeline usa `robust_thresholds.json`

---

## 📊 Visualizzazione

Nuova pagina Streamlit: **`eda/pages/03_Node_Influence_Analysis.py`**

Grafici:
- Distribuzione node_influence (top-N coverage)
- Coverage breakdown (cicciotti vs probe-responsive)
- Scatter plot: node_influence vs probe response
- Distribuzione per layer
- Tabella top-100 per node_influence

Per avviare:
```bash
cd eda
streamlit run app.py
```

---

## ✅ Checklist Pulizia

- [x] Eliminato `03b_compute_thresholds_probe_based.py`
- [x] Aggiornato `04_cicciotti_supernodes.py` (solo robust_thresholds)
- [x] Aggiornato `05_final_optimized_clustering.py` (solo robust_thresholds)
- [x] Verificato che `probe_based_thresholds.json` non venga più generato
- [x] Creata pagina Streamlit per analisi node_influence
- [x] Documentato decisione

---

## 🚀 Prossimi Step

1. Runnare pipeline completo con `robust_thresholds.json`:
   ```bash
   python scripts/03_compute_thresholds.py
   python scripts/04_cicciotti_supernodes.py
   python scripts/05_final_optimized_clustering.py
   ```

2. Verificare coverage in Streamlit (pagina "Node Influence Analysis")

3. Validare risultati per MATS application

---

**Note:** I probe prompts rimangono utili per **interpretabilità** ma non determinano più l'**ammissione** delle feature. La causalità è determinata da **node_influence** (dalla Attribution Graph).







