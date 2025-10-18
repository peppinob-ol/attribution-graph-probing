# Validation & Testing Guide

## 📋 Checklist Accettazione App

### ✅ Setup Iniziale

- [ ] Dipendenze installate: `pip install streamlit plotly pandas seaborn matplotlib`
- [ ] Dati pipeline presenti in `output/`:
  - [ ] `feature_personalities_corrected.json`
  - [ ] `cicciotti_supernodes.json`
  - [ ] `final_anthropological_optimized.json`
  - [ ] `robust_thresholds.json`
- [ ] App si avvia senza errori: `streamlit run eda/app.py`
- [ ] Pagina principale mostra "Tutti i dati essenziali sono disponibili"

### ✅ Test Overview (01_Overview.py)

- [ ] **KPI corrispondono a file finale**:
  - Aprire `output/final_anthropological_optimized.json`
  - Confrontare `comprehensive_statistics`:
    - `total_supernodes` = Overview "Supernodi totali"
    - `semantic_supernodes` = "Semantici"
    - `computational_supernodes` = "Computazionali"
    - `total_features_covered` = "Features coperte"
    - `coverage_percentage` = "Coverage totale"
    - `quality_coverage_percentage` = "Coverage qualità"
  - Confrontare `quality_metrics`:
    - `semantic_avg_coherence` = "Coerenza semantica"
    - `computational_diversity` = "Diversità comp."

- [ ] **Grafici renderizzano**:
  - Coverage comparison (bar chart)
  - Breakdown supernodi (pie chart)
  - Breakdown features (bar chart)

- [ ] **Export funzionanti**:
  - Download `dashboard.json` → valido JSON, contiene totals/coverage/quality
  - Download `kpi.csv` → CSV valido, 10 righe (metriche)

**Risultato atteso**: KPI Overview = dati da `final_anthropological_optimized.json` ±0.01

---

### ✅ Test Fase 1 - Features (02_Phase1_Features.py)

- [ ] **Tabella features carica**:
  - Mostra tutte le colonne: feature_key, layer, token, metriche
  - Numero righe = numero features in personalities
  - Ordinamento funziona

- [ ] **Filtri funzionanti**:
  - Slider layer range → tabella si aggiorna
  - Multiselect token → tabella filtra
  - Count "Features filtrate" corretto

- [ ] **Grafici renderizzano**:
  - Violin plots per metriche
  - Heatmap correlazioni
  - Token distribution (bar)
  - Scatter plots con colore

- [ ] **Dettaglio feature**:
  - Seleziona feature dal dropdown
  - Tab "Personalità": JSON completo visibile
  - Tab "Vicinato Causale": 
    - Se grafo presente: top_parents/children, grafico
    - Se grafo assente: warning "non disponibile"
  - Tab "Attivazioni": mostra dati se `acts_compared.csv` presente

- [ ] **Export**: Download CSV features funzionante

**Test specifico**: Seleziona feature "24_13277", verifica che node_influence mostrato = valore in `feature_personalities_corrected.json['24_13277']['node_influence']`

---

### ✅ Test Fase 2 - Supernodi (03_Phase2_Supernodes.py)

- [ ] **Lista supernodi**:
  - Numero supernodi = count in `cicciotti_supernodes.json`
  - Tutti i campi popolati (id, theme, n_members, coherence, iterations)
  - Filtri funzionanti (theme, min_members, min_coherence)
  - Ordinamento funzionante

- [ ] **Grafici analisi**:
  - Scatter n_members vs coherence (punti colorati per theme)
  - Scatter iterations vs coherence
  - Statistiche per theme (tabella aggregata)
  - Istogramma coherence distribution

- [ ] **Dettaglio supernodo**:
  - Seleziona supernodo dal dropdown
  - Tab "Overview":
    - Coherence history (line plot) con N punti = growth_iterations + 1
    - Distribuzione layer (histogram)
    - Token distribution (bar chart)
  - Tab "Membri": tabella con tutte le feature, N righe = n_members del supernodo
  - Tab "Crescita": coherence history tabellare, dettagli seed JSON
  - Tab "Dry-run":
    - Se dry-run disabilitato: info message
    - Se abilitato + grafo presente: tabella compatibilità candidati (5 righe top_parents)

- [ ] **Dry-run parametri** (abilita checkbox sidebar):
  - Slider "Peso causale" cambia → ricalcolo compatibilità con nuovo peso
  - Threshold normale cambia → indica quanti candidati accettati/totali
  - Metriche causali/semantiche separate visibili in tabella

**Test specifico**: 
1. Seleziona CICCIOTTO_2
2. Verifica n_members = 20 (da JSON)
3. Verifica final_coherence ≈ 0.505 (da JSON)
4. Coherence history ha 20 punti (iterazioni 0-19)

---

### ✅ Test Cross-Prompt (04_CrossPrompt.py)

- [ ] **Heatmap attivazione**:
  - Heatmap renderizza
  - Assi: supernodi (Y) × prompts (X)
  - Selettore metrica funziona (n_active_members, avg_consistency, std)

- [ ] **Statistiche robustezza**:
  - Top 10 stabili (std bassa)
  - Top 10 variabili (std alta)
  - Scatter stabilità renderizza
  - Export CSV funzionante

- [ ] **Dettaglio supernodo**:
  - Seleziona supernodo
  - Tabella attivazione per prompt (N righe = N prompts)
  - Bar chart per prompt (2 grafici)
  - Summary metrics (avg, std)

**Test specifico**: Seleziona supernodo con dati validation, verifica che avg_active_members calcolato = media manuale dei valori nella tabella

---

### ✅ Test Fase 3 - Residui (05_Phase3_Residuals.py)

- [ ] **Ricalcolo residui**:
  - Metriche iniziali: total_admitted, used_in_cicciotti, quality_residuals
  - Cambia tau_inf slider → count cambia
  - Breakdown situational/scaffold/overlap mostrato
  - Sample residui (tabella 20 righe)

- [ ] **Clusters computazionali**:
  - Count clusters prima/dopo merge mostrato
  - Se merge avvenuti: expander "Dettagli merge" con JSON
  - Tabella clusters con tutte le colonne
  - Grafici:
    - Istogramma dimensioni cluster
    - Scatter connectivity vs consistency
  - Export CSV e JSON funzionanti

- [ ] **Coverage analysis**:
  - Confronto baseline (precomputed) vs corrente (parametri custom)
  - Metriche separate: semantic/computational
  - Bar chart comparison
  - Delta coverage calcolato e colorato (success/warning/info)

- [ ] **Parametri interattivi**:
  - Cambia min_cluster_size → clusters ricalcolati, count aggiornato
  - Cambia jaccard_threshold → merge cambia, count finale diverso
  - Cambia node_inf thresholds → signature cluster cambiano (tier HIGH/MED/LOW)

- [ ] **Export parametri**: Button "Export parametri correnti" → download JSON con tutti i parametri

**Test specifico**:
1. Baseline coverage dalla Overview (es. 79.6%)
2. Vai in Fase 3, aumenta min_cluster_size a 5
3. Coverage corrente dovrebbe essere ≤ baseline (meno cluster validi)
4. Delta coverage mostra diminuzione

---

### ✅ Test Integrità Dati

- [ ] **Coerenza numerica**:
  - Somma `features_in_semantic` + `features_in_computational` = `total_features_covered`
  - `total_supernodes` = `semantic_supernodes` + `computational_supernodes`
  - Coverage % = (total_covered / original_features) × 100

- [ ] **Coerenza supernodi**:
  - Per ogni cicciotto: len(members) = n_members mostrato
  - Final_coherence tra 0 e 1
  - Growth_iterations ≥ 0 e ≤ max_iterations (default 20)

- [ ] **Coerenza features**:
  - Ogni feature ha layer (0-25 per Gemma-2B)
  - Metriche consistency/affinity tra 0 e 1
  - Node_influence può essere negativo (normale)

---

### ✅ Test Performance

- [ ] **Caricamento veloce**:
  - Prima apertura app: < 10 secondi
  - Cambio pagina: < 2 secondi
  - Ricalcolo Fase 3: < 5 secondi (con ~300 residui)

- [ ] **Cache funzionante**:
  - Seconda apertura pagina: istantanea (cache hit)
  - Cambio parametri: solo ricalcolo necessario, non ricaricamento dati

- [ ] **Memory usage**:
  - App non supera 2GB RAM (con grafo caricato)
  - No memory leak su cambio parametri ripetuto

---

### ✅ Test Edge Cases

- [ ] **Grafo assente**:
  - App mostra warning "Grafo causale non disponibile"
  - Metriche causali non disponibili, fallback semantico
  - App continua a funzionare

- [ ] **Dati parziali**:
  - Se manca `validation`: pagina Cross-Prompt mostra errore ma altre pagine OK
  - Se manca `archetypes`: tab Archetipi in Fase 1 mostra warning
  - Se manca `acts`: tab Attivazioni in dettaglio feature mostra warning

- [ ] **Filtri estremi**:
  - Fase 1: filtra layer range vuoto → "Features filtrate: 0"
  - Fase 2: min_coherence = 1.0 → "Supernodi filtrati: 0"
  - Fase 3: min_cluster_size = 100 → "Nessun cluster valido"

---

## 🎯 Criteri Accettazione Finale

L'app è validata se:

1. ✅ **Dashboard KPI** = `final_anthropological_optimized.json` (±0.01 tolleranza)
2. ✅ **Dettagli completi**: feature/supernodo mostrano tutti i dati disponibili
3. ✅ **Dry-run coerente**: compatibilità calcolata con parametri custom produce valori sensati (0-1)
4. ✅ **Export funzionanti**: tutti i download producono file validi (JSON/CSV apribili)
5. ✅ **Grafici renderizzano**: nessun errore plotly, tutti i chart visibili
6. ✅ **Parametri interattivi**: slider cambiano → risultati ricalcolati in tempo reale
7. ✅ **Nessun crash**: navigazione tra pagine senza errori Python/Streamlit
8. ✅ **Fallback graceful**: se dati opzionali mancanti, warning ma app continua

---

## 🐛 Debugging

Se test fallisce:

1. **Verifica dati input**: `ls -la output/*.json output/*.csv`
2. **Controlla logs Streamlit**: terminale dove app è avviata
3. **Pulisci cache**: Menu hamburger > Clear cache
4. **Riavvia app**: Ctrl+C, poi `streamlit run eda/app.py`
5. **Verifica Python version**: ≥3.8 richiesto
6. **Reinstalla dipendenze**: `pip install --upgrade streamlit plotly pandas`

---

## 📊 Risultati Attesi (Dallas-Austin Dataset)

Con dati default:
- Total supernodes: 28 (15 semantici + 13 computazionali)
- Features coperte: ~251
- Coverage qualità: ~79.6%
- Semantic avg coherence: ~0.58
- Garbage identificato: ~1482

Se valori molto diversi:
- Pipeline potrebbe non essere completata
- Parametri default modificati
- Dati corrotti

---

**Status validation**: 
- [ ] Tutti i test passati
- [ ] Problemi identificati e risolti
- [ ] App pronta per uso produttivo

**Data validazione**: _________________

**Validato da**: _________________

