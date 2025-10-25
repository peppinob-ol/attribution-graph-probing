# Pagina Node Grouping - Guida Utente

**File**: `eda/pages/02_Node_Grouping.py`  
**Data**: 2025-10-25

---

## Panoramica

La pagina **Node Grouping** è un'interfaccia Streamlit interattiva per classificare e nominare automaticamente i supernodi nel grafo di attribuzione.

### Funzionalità Principali

1. **Upload Files**: Carica CSV export e JSON attivazioni
2. **Step 1 - Preparazione**: Classifica token e trova target tokens
3. **Step 2 - Classificazione**: Assegna classi ai nodi (Semantic, Say X, Relationship)
4. **Step 3 - Naming**: Genera nomi descrittivi per ogni supernodo
5. **Parametri Configurabili**: Modifica soglie e parametri in tempo reale
6. **Download Risultati**: Esporta CSV e JSON summary

---

## Come Usare

### 1. Avvio Applicazione

```bash
cd eda
streamlit run app.py
```

Oppure direttamente:

```bash
streamlit run eda/pages/02_Node_Grouping.py
```

### 2. Upload Files

**Sidebar → Input Files**

- **CSV Export (richiesto)**: File generato da Probe Prompts
  - Es: `output/2025-10-21T07-40_export_ENRICHED.csv`
  - Deve contenere colonne: `feature_key`, `layer`, `prompt`, `peak_token`, `peak_token_idx`, `activation_max`, `sparsity_ratio`

- **JSON Attivazioni (opzionale)**: File con attivazioni token-by-token
  - Es: `output/activations_dump (2).json`
  - Migliora l'accuratezza del naming per Relationship
  - Struttura: `{"results": [{"prompt": "...", "tokens": [...], "counts": [...]}]}`

### 3. Configurazione Parametri

**Sidebar → Parametri Pipeline**

- **Finestra ricerca target** (default: 7): Numero massimo di token da esplorare per trovare target semantici

**Sidebar → Soglie Classificazione**

Espandi le sezioni per modificare le soglie:

#### Dictionary Semantic
- **Peak Consistency (min)**: 0.8 (default)
  - Quanto spesso il token deve essere peak quando appare nel prompt
- **N Distinct Peaks (max)**: 1 (default)
  - Numero massimo di token distinti come peak

#### Say X
- **Func vs Sem % (min)**: 50.0 (default)
  - Differenza % tra max activation su functional vs semantic
- **Confidence F (min)**: 0.90 (default)
  - Frazione di peak su token funzionali
- **Layer (min)**: 7 (default)
  - Layer minimo per Say X (tipicamente layer alti)

#### Relationship
- **Sparsity (max)**: 0.45 (default)
  - Sparsity massima (bassa = attivazione diffusa)

#### Semantic (Concept)
- **Layer (max)**: 3 (default)
  - Layer massimo per fallback Dictionary
- **Confidence S (min)**: 0.50 (default)
  - Frazione di peak su token semantici
- **Func vs Sem % (max)**: 50.0 (default)
  - Differenza % massima per considerare Semantic

### 4. Esecuzione Pipeline

#### Step 1: Preparazione Dataset

1. Clicca **"▶️ Esegui Step 1"**
2. Attendi elaborazione
3. Verifica statistiche:
   - Token Funzionali vs Semantici
   - Tokens da JSON vs Fallback
4. Esamina campione risultati
5. (Opzionale) Download CSV Step 1

**Cosa fa**:
- Classifica ogni `peak_token` come functional o semantic
- Per token funzionali, trova il primo token semantico nella direzione specificata
- Aggiunge colonne: `peak_token_type`, `target_tokens`, `tokens_source`

#### Step 2: Classificazione Nodi

1. (Opzionale) Modifica soglie nella sidebar
2. Clicca **"▶️ Esegui Step 2"**
3. Attendi elaborazione
4. Verifica distribuzione classi:
   - Semantic: ~90%
   - Relationship: ~10%
   - Say X: variabile
5. Controlla warning per feature in review
6. Filtra per classe e esamina risultati
7. (Opzionale) Download CSV Step 2

**Cosa fa**:
- Aggrega metriche per ogni `feature_key`
- Applica albero decisionale per classificare
- Aggiunge colonne: `pred_label`, `subtype`, `confidence`, `review`, `why_review`

**Iterazione**:
- Puoi modificare le soglie e rieseguire Step 2 senza rifare Step 1
- Utile per affinare la classificazione

#### Step 3: Naming Supernodi

1. Clicca **"▶️ Esegui Step 3"**
2. Attendi elaborazione
3. Verifica:
   - Feature Totali vs Nomi Unici
   - Esempi naming per classe
4. Esamina risultati finali
5. Analizza raggruppamento per `supernode_name`
6. Download CSV Completo e Summary JSON

**Cosa fa**:
- Per Relationship: `"(X) related"` (X = primo token semantico con max attivazione)
- Per Semantic: Nome del token con max activation (es. "Texas", "city")
- Per Say X: `"Say (X)"` (X = target_token, es. "Say (Austin)")
- Aggiunge colonna: `supernode_name`

### 5. Download Risultati

**Dopo Step 3**:

- **📥 Download CSV Completo**: File con tutte le colonne aggiunte
  - Formato: `node_grouping_final_YYYYMMDD_HHMMSS.csv`
  - Contiene: tutte le colonne originali + `peak_token_type`, `target_tokens`, `pred_label`, `subtype`, `supernode_name`, etc.

- **📥 Download Summary JSON**: Riepilogo statistiche
  - Formato: `node_grouping_summary_YYYYMMDD_HHMMSS.json`
  - Contiene: timestamp, n_features, distribuzione classi, soglie usate, top supernodes

---

## Interpretazione Risultati

### Classi di Supernodi

#### Semantic (Dictionary)
- **Caratteristiche**: Si attiva sempre sullo stesso token specifico
- **Esempio**: Feature che si attiva solo su "Texas"
- **Metriche**: `peak_consistency` alta (≥0.8), `n_distinct_peaks` = 1
- **Naming**: Nome del token (es. "Texas")

#### Semantic (Concept)
- **Caratteristiche**: Si attiva su token semanticamente simili
- **Esempio**: Feature che si attiva su "city", "capital", "state"
- **Metriche**: `conf_S` alta (≥0.50), layer medio-basso
- **Naming**: Token con max activation (es. "city")

#### Say X
- **Caratteristiche**: Si attiva su token funzionali per predire il prossimo token
- **Esempio**: Feature che si attiva su "is" prima di "Austin"
- **Metriche**: `func_vs_sem` alta (≥50%), `conf_F` alta (≥0.90), layer alto (≥7)
- **Naming**: `"Say (X)"` dove X è il target_token (es. "Say (Austin)")

#### Relationship
- **Caratteristiche**: Collega concetti semantici multipli con attivazione diffusa
- **Esempio**: Feature che si attiva su "city", "capital", "state" insieme
- **Metriche**: `sparsity` bassa (<0.45), `K_sem_distinct` alto
- **Naming**: `"(X) related"` dove X è il primo token semantico con max attivazione

### Metriche Chiave

- **peak_consistency_main**: Quanto spesso il token principale è peak quando appare nel prompt
  - Range: 0.0 - 1.0
  - Interpretazione: 1.0 = sempre peak, 0.5 = 50% delle volte

- **n_distinct_peaks**: Numero di token distinti come peak
  - Range: 1 - N
  - Interpretazione: 1 = sempre lo stesso token, >1 = vari token

- **func_vs_sem_pct**: Differenza % tra max activation su functional vs semantic
  - Range: -100% a +100%
  - Interpretazione: +100% = solo functional, -100% = solo semantic, 0% = uguale

- **conf_F / conf_S**: Frazione di peak su token funzionali/semantici
  - Range: 0.0 - 1.0
  - Interpretazione: `conf_F` + `conf_S` = 1.0

- **sparsity_median**: Mediana sparsity (solo prompt attivi)
  - Range: 0.0 - 1.0
  - Interpretazione: 0.0 = attivazione diffusa, 1.0 = attivazione concentrata

- **K_sem_distinct**: Numero di token semantici distinti
  - Range: 0 - N
  - Interpretazione: Alto = molti token diversi (Relationship/Concept)

---

## Troubleshooting

### Errore: "API Key non trovata"
- **Soluzione**: Non applicabile per Node Grouping (non richiede API key)

### Errore: "Impossibile caricare CSV"
- **Causa**: File CSV corrotto o formato errato
- **Soluzione**: Verifica che il CSV contenga le colonne richieste

### Errore: "Impossibile caricare JSON"
- **Causa**: File JSON corrotto o formato errato
- **Soluzione**: Verifica che il JSON abbia la struttura corretta (`results` array)

### Warning: "N feature richiedono review"
- **Causa**: Casi ambigui che non rientrano chiaramente in una classe
- **Soluzione**: Esamina manualmente le feature con `review=True` e considera di modificare le soglie

### Naming Relationship non accurato
- **Causa**: JSON attivazioni non fornito o non completo
- **Soluzione**: Carica il JSON attivazioni completo con tutti i prompt del CSV

### Classificazione non soddisfacente
- **Causa**: Soglie di default non adatte al dataset
- **Soluzione**: Modifica le soglie nella sidebar e riesegui Step 2

---

## Best Practices

1. **Fornisci sempre il JSON attivazioni** per Relationship naming accurato
2. **Inizia con soglie di default**, poi affina in base ai risultati
3. **Controlla le feature in review** per identificare casi edge
4. **Itera su Step 2 e 3** con soglie diverse senza rifare Step 1
5. **Esamina la distribuzione classi** per verificare che sia ragionevole
6. **Analizza i nomi generati** per verificare che siano interpretabili
7. **Scarica il Summary JSON** per documentare le soglie usate

---

## Integrazione con Altri Step

### Input
- **Da Step 01 (Probe Prompts)**: CSV export con attivazioni
- **Da Step 00 (Graph Generation)**: JSON attivazioni (opzionale)

### Output
- **Per Visualizzazione**: CSV con `supernode_name` per etichette grafo
- **Per Analisi**: CSV completo con tutte le metriche e classificazioni
- **Per Documentazione**: Summary JSON con statistiche e parametri

---

## Riferimenti

- **Script Backend**: `scripts/02_node_grouping.py`
- **Documentazione Tecnica**: `output/STEP3_IMPLEMENTATION_SUMMARY.md`
- **Guida Rapida**: `output/STEP3_READY_FOR_REVIEW.md`
- **Test**: `tests/test_node_naming.py`
- **Piano Originale**: `node.plan.md`

---

## Supporto

Per domande o problemi:
1. Consulta questa guida
2. Leggi la documentazione tecnica in `output/`
3. Esamina gli esempi nel CSV ENRICHED
4. Contatta il team di sviluppo

**Buon lavoro con Node Grouping!** 🔗

