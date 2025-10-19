# 🇮🇹 Guida Rapida - App EDA Supernodi

## 🚀 Installazione e Avvio

### 1. Installa dipendenze

```bash
pip install streamlit plotly pandas seaborn matplotlib
```

Oppure aggiorna tutte le dipendenze del progetto:

```bash
pip install -r requirements.txt
```

### 2. Avvia l'applicazione

Dalla root del progetto:

```bash
streamlit run eda/app.py
```

L'app si aprirà automaticamente nel browser su `http://localhost:8501`

---

## 📊 Struttura dell'App

L'app è organizzata in **5 pagine** principali, accessibili dalla sidebar:

### 1. 📊 Overview - Dashboard Globale
**Cosa mostra:**
- KPI globali del sistema (totale supernodi, coverage, qualità)
- Grafici di riepilogo
- Export JSON/CSV della dashboard

**Quando usarla:**
- Prima visione d'insieme del risultato della pipeline
- Verifica rapida delle metriche principali
- Export per report o presentazioni

---

### 2. 🎭 Fase 1 - Features Explorer
**Cosa mostra:**
- Tutte le features con le loro "personalità" (metriche semantiche + causali)
- Grafici di distribuzione e correlazione
- Archetipi narrativi (Semantic Anchors, Stable Contributors, ecc.)
- Dettaglio singola feature con vicinato causale

**Funzionalità chiave:**
- **Filtri**: layer range, token specifici
- **Grafici**: violin plot per metriche, heatmap correlazioni, scatter plots
- **Dettaglio feature**: 
  - Personalità completa
  - Top 5 genitori/figli causali
  - Grafico vicinato (se grafo disponibile)
  - Attivazioni per prompt

**Quando usarla:**
- Esplorare il comportamento di singole features
- Analizzare correlazioni tra metriche semantiche e causali
- Identificare pattern per layer o token

---

### 3. 🌱 Fase 2 - Supernodi Cicciotti
**Cosa mostra:**
- Lista completa supernodi semantici
- Analisi dimensioni, coerenza, iterazioni di crescita
- Distribuzione membri per layer/token
- Storia della crescita (coherence history)

**Funzionalità chiave:**
- **Lista ordinabile/filtrabile**: per theme, dimensione, coerenza
- **Grafici analisi**: scatter plots per identificare pattern
- **Dettaglio supernodo**: 
  - Coherence evolution durante crescita
  - Tabella membri completa
  - Seed e metriche iniziali
- **Dry-run parametrico**: 
  - Abilita checkbox "Abilita dry-run" nella sidebar
  - Modifica peso causale (0.4-0.8)
  - Modifica threshold crescita (0.3-0.7)
  - Osserva compatibilità candidati ricalcolata

**Quando usarla:**
- Analizzare qualità supernodi semantici
- Capire come parametri influenzano la crescita
- Identificare supernodi outlier (molto grandi/piccoli, bassa coerenza)
- Sperimentare con parametri diversi (dry-run)

**Esempio uso dry-run:**
1. Seleziona supernodo interessante (es. CICCIOTTO_2)
2. Abilita "Abilita dry-run" nella sidebar
3. Modifica "Peso causale" da 0.60 a 0.50 (più peso semantico)
4. Vai al tab "Dry-run" del supernodo
5. Osserva come cambiano gli score di compatibilità per i candidati

---

### 4. 🧪 Cross-Prompt - Validazione
**Cosa mostra:**
- Robustezza dei supernodi su prompt diversi
- Heatmap attivazione (supernodi × prompt)
- Statistiche stabilità (std bassa = più robusto)

**Funzionalità chiave:**
- **Heatmap interattiva**: cambia metrica (n_active_members, avg_consistency, std)
- **Ranking stabilità**: top 10 più stabili/variabili
- **Dettaglio per supernodo**: attivazione specifica per ogni prompt

**Quando usarla:**
- Validare che i supernodi siano robusti (non specifici di un singolo prompt)
- Identificare supernodi troppo variabili
- Capire su quali prompt un supernodo è più attivo

---

### 5. 🏭 Fase 3 - Residui Computazionali
**Cosa mostra:**
- Features non incluse in supernodi semantici ("residui di qualità")
- Clustering multi-dimensionale (layer_group × token × causal_tier)
- Merge automatico cluster simili (Jaccard)
- Confronto coverage baseline vs corrente

**Funzionalità chiave (TUTTO INTERATTIVO):**
- **Soglie ammissione**: modifica tau_inf, tau_aff → residui ricalcolati
- **Clustering**: 
  - Min cluster size (2-10): dimensione minima cluster validi
  - Layer group span (2-5): ampiezza gruppi di layer
  - Node influence thresholds: separazione tier HIGH/MED/LOW
- **Merge Jaccard**: threshold 0.5-0.9 per unire cluster simili
- **Coverage comparison**: vedi impatto delle modifiche su coverage totale

**Quando usarla:**
- Sperimentare con soglie diverse per ammissione residui
- Trovare trade-off ottimale tra coverage e qualità
- Analizzare features computazionali (non semantiche)
- Identificare parametri che massimizzano coverage senza sacrificare qualità

**Esempio uso interattivo:**
1. **Baseline**: nota coverage qualità (es. 79.6%)
2. **Esperimento 1**: Diminuisci `tau_inf` da 0.000194 a 0.0001
   - Più features ammesse come residui
   - Più cluster computazionali
   - Coverage aumenta (es. 81.2%)
3. **Esperimento 2**: Aumenta `min_cluster_size` da 3 a 5
   - Meno cluster validi (troppo piccoli esclusi)
   - Coverage diminuisce leggermente (es. 80.1%)
4. **Esperimento 3**: Diminuisci `jaccard_threshold` da 0.70 a 0.60
   - Più merge tra cluster
   - Meno cluster totali ma più grandi
5. **Confronto**: osserva Δ coverage nel tab "Coverage Analysis"
6. **Export**: salva parametri ottimali con "Export parametri correnti"

---

## 🎛️ Parametri Chiave da Sperimentare

### Fase 2 - Supernodi (Dry-run)

| Parametro | Range | Default | Effetto |
|-----------|-------|---------|---------|
| **Peso causale** | 0.4-0.8 | 0.60 | ↑ peso causale = crescita più vincolata da grafo causale |
| **tau_edge_strong** | 0.02-0.10 | 0.05 | Soglia per considerare edge "forte" |
| **Threshold bootstrap** | 0.1-0.5 | 0.30 | Accettazione fase bootstrap (2-hop causale) |
| **Threshold normale** | 0.3-0.7 | 0.45 | Accettazione fase normale (causale+semantico) |
| **Min coherence** | 0.3-0.8 | 0.50 | Stop crescita se coerenza scende sotto |

**Tip**: Aumenta "threshold normale" per supernodi più selettivi (più piccoli, più coerenti). Diminuiscilo per supernodi più grandi e permissivi.

### Fase 3 - Residui (Ricalcolo real-time)

| Parametro | Range | Default | Effetto |
|-----------|-------|---------|---------|
| **tau_inf** | 0.00001-0.001 | 0.000194 | Soglia logit_influence per ammissione |
| **tau_aff** | 0.50-0.90 | 0.65 | Soglia max_affinity per ammissione |
| **Min cluster size** | 2-10 | 3 | Dimensione minima cluster validi |
| **Jaccard threshold** | 0.5-0.9 | 0.70 | Similarità minima per merge cluster |
| **Node inf HIGH** | 0.05-0.20 | 0.10 | Soglia tier HIGH node_influence |
| **Node inf MED** | 0.005-0.05 | 0.01 | Soglia tier MED node_influence |

**Tip**: Per massimizzare coverage diminuisci `tau_inf` e `min_cluster_size`. Per massimizzare qualità aumentali.

---

## 📥 Export Disponibili

Ogni pagina offre export specifici:

| Pagina | Export | Contenuto |
|--------|--------|-----------|
| **Overview** | `dashboard.json` | KPI globali strutturati |
| | `kpi.csv` | Metriche in formato tabellare |
| **Fase 1** | `features_filtered.csv` | Features con filtri applicati |
| **Fase 2** | `supernodes_list.csv` | Lista supernodi con metriche |
| | `{ID}_members.csv` | Membri di singolo supernodo |
| **Fase 3** | `clusters_current.csv` | Cluster con parametri correnti |
| | `clusters_current.json` | Cluster completi (con membri) |
| | `phase3_parameters.json` | Parametri usati per clustering |

---

## 🎯 Workflow Consigliato

### Per Analisi Esplorativa:
1. **Overview** → KPI globali, orientamento generale
2. **Fase 1** → Esplora features interessanti, analizza correlazioni
3. **Fase 2** → Identifica supernodi chiave, verifica coerenza
4. **Cross-Prompt** → Valida robustezza
5. **Fase 3** → Analizza residui, verifica coverage

### Per Ottimizzazione Parametri:
1. **Fase 2** → Abilita dry-run, sperimenta con peso causale/thresholds
2. **Fase 3** → Modifica soglie ammissione e clustering
3. **Coverage Analysis** → Confronta con baseline
4. **Export parametri ottimali** → Salva configurazione migliore
5. **Riesegui pipeline con parametri ottimizzati** (opzionale)

### Per Validazione Qualità:
1. **Overview** → Verifica KPI globali vs aspettative
2. **Cross-Prompt** → Identifica supernodi instabili
3. **Fase 2** → Analizza supernodi outlier (bassa coerenza, troppo grandi/piccoli)
4. **Fase 1** → Esamina features problematiche nei supernodi outlier
5. **Fase 3** → Verifica che residui siano effettivamente "computazionali" (non semantici persi)

---

## 🐛 Problemi Comuni e Soluzioni

### "Dati essenziali mancanti"
**Causa**: Pipeline non eseguita  
**Soluzione**: 
```bash
python scripts/02_anthropological_basic.py
python scripts/04_cicciotti_supernodes.py
python scripts/05_final_optimized_clustering.py
```

### "Grafo causale non disponibile"
**Causa**: `output/example_graph.pt` assente  
**Effetto**: Metriche causali non calcolabili, dry-run limitato  
**Soluzione**: App funziona comunque con fallback semantico, oppure rigenera grafo

### Cache obsoleta
**Sintomo**: Modifiche dati output non riflesse nell'app  
**Soluzione**: Menu hamburger (top-right) > Clear cache > Riavvia app

### "ModuleNotFoundError: eda"
**Causa**: App avviata da directory sbagliata  
**Soluzione**: `cd c:\Github\circuit_tracer-prompt_rover` poi `streamlit run eda/app.py`

### Performance lente
**Causa**: Grafo molto grande, molte features  
**Soluzione**: 
- Usa filtri per ridurre dataset visualizzato
- Dry-run solo su seed selezionato (non ricalcolo completo)
- Pulisci cache se memoria piena

---

## 📚 Documentazione Completa

- **Documentazione tecnica**: `eda/README.md`
- **Guida validazione**: `eda/VALIDATION.md`
- **Piano implementazione**: `stream.plan.md`
- **Docs pipeline completa**: `docs/supernode_labelling/`

---

## 💡 Tips Avanzati

### Analisi Features Interessanti
1. **Semantic Anchors**: filtra per `archetipo = Semantic Anchors` in Fase 1
2. **High influence**: ordina per `node_influence` descrescente
3. **Inconsistenti**: cerca features con alta `consistency_std`

### Identificare Supernodi Problematici
1. **Bassa coerenza**: filtra `final_coherence < 0.4` in Fase 2
2. **Crescita instabile**: osserva coherence_history con oscillazioni
3. **Troppo grandi**: ordina per `n_members` descrescente, analizza composizione

### Ottimizzare Coverage
1. **Baseline**: nota coverage corrente in Overview
2. **Fase 3**: riduci soglie ammissione (più residui)
3. **Riduci min_cluster_size**: cluster più piccoli validi
4. **Riduci jaccard_threshold**: più merge cluster
5. **Confronta**: Δ coverage positivo = miglioramento

### Export per Presentazioni
1. **Overview**: dashboard.json → importa in notebook/script per grafici custom
2. **Fase 2**: scarica supernodi_list.csv → crea grafici esterni (Excel, matplotlib)
3. **Fase 3**: clusters_current.json → analisi dettagliata residui

---

## ✅ Checklist Prima Presentazione

Prima di mostrare risultati a collaboratori/supervisori:

- [ ] Tutti i dati pipeline presenti (vedi pagina principale app)
- [ ] KPI in Overview sensati (coverage > 70%, coerenza > 0.5)
- [ ] Supernodi validati cross-prompt (heatmap senza troppe aree bianche)
- [ ] Dry-run testato con parametri alternativi
- [ ] Export funzionanti (dashboard.json, kpi.csv)
- [ ] Nessun errore/warning critico nell'app

---

**Buon lavoro con l'app! 🚀**

Per domande o problemi, consulta `eda/VALIDATION.md` per debugging dettagliato.

