# Guida Export Neuronpedia - Supernodi Antropologici

## 📋 Files Generati

### Versione Standard
- `output/neuronpedia_url.txt` - URL Neuronpedia base
- `output/neuronpedia_supernodes.json` - Dati supernodi JSON

### Versione Improved ⭐ (RACCOMANDATO)
- `output/neuronpedia_url_improved.txt` - URL con nomi distintivi
- `output/neuronpedia_supernodes_improved.json` - Dati supernodi migliorati

---

## 🚀 Come Visualizzare i Supernodi su Neuronpedia

### Metodo 1: URL Diretto

1. **Apri il file**: `output/neuronpedia_url_improved.txt`
2. **Copia l'intero URL** (sarà molto lungo, è normale)
3. **Incolla nella barra degli indirizzi del browser**
4. **Premi Invio**

Neuronpedia caricherà automaticamente il grafo con i tuoi supernodi!

### Metodo 2: Crea Grafo Manualmente su Neuronpedia

Se l'URL è troppo lungo per il tuo browser:

1. Vai su https://www.neuronpedia.org/gemma-2-2b
2. Crea un nuovo grafo (Create Graph)
3. Carica i supernodi dal file JSON (`neuronpedia_supernodes_improved.json`)

---

## 📊 Cosa Contiene l'Export

### Supernodi Semantici (15)
Cluster tematici basati su "narrative theme":

| Nome Supernode | Feature | Layer Range | Descrizione |
|----------------|---------|-------------|-------------|
| `Capital_L0-15` | 21 | Layers 0-15 | Cluster Capital early-mid layers |
| `Capital_L13-16` | 7 | Layers 13-16 | Cluster Capital mid layers |
| `Capital_L15-18` | 19 | Layers 15-18 | Cluster Capital mid-high layers |
| `Capital_L17-19` | 4 | Layers 17-19 | Cluster Capital high layers |
| `<BOS>_L10-21` | 10 | Layers 10-21 | BOS tokens processing |
| `<BOS>_L16-25` | 6 | Layers 16-25 | BOS tokens late layers |
| ... | ... | ... | ... |

### Supernodi Computazionali (8)
Cluster basati su token dominante e numero membri:

| Nome Supernode | Feature | Avg Layer | Token |
|----------------|---------|-----------|-------|
| `<BOS>_L24_n74` | 74 | 24 | `<BOS>` |
| `of_L4_n46` | 46 | 4 | `of` |
| `Texas_L9_n34` | 34 | 9 | `Texas` |
| `of_L6_n32` | 32 | 6 | `of` |
| `of_L9_n31` | 31 | 9 | `of` |
| `<BOS>_L22_n30` | 30 | 22 | `<BOS>` |
| `state_L9_n24` | 24 | 9 | `state` |
| `Dallas_L6_n24` | 24 | 6 | `Dallas` |

**Totale: 483 feature** coperte nei supernodi.

---

## 🎯 Cosa Puoi Fare su Neuronpedia

### 1. **Esplorare le Feature**
- Clicca su qualsiasi nodo per vedere le feature individuali
- Visualizza gli esempi di attivazione
- Leggi le interpretazioni automatiche

### 2. **Vedere le Connessioni**
- Il grafo mostra le connessioni tra supernodi
- Edge weights indicano la forza delle connessioni
- Puoi filtrare per pruning threshold

### 3. **Fare Interventions** (come nel tutorial)
- Clicca su un supernode
- Imposta "intervention value" (es. 0 per disattivare, 2 per amplificare)
- Osserva come cambiano le top predictions

### 4. **Modificare le Labels**
- Clicca su un supernode name
- Modifica il nome per renderlo più descrittivo
- Le modifiche sono salvate nell'URL

### 5. **Condividere**
- L'URL contiene tutto lo stato del grafo
- Condividi l'URL per mostrare i tuoi supernodi ad altri
- Aggiungi all'application MATS

---

## ⚙️ Parametri Configurabili

### Nel file `export_to_neuronpedia_improved.py`:

```python
url, data = export_to_neuronpedia_improved(
    prompt="Your custom prompt",           # Cambia prompt
    pos=10,                                 # Specifica token position
    max_supernodes=20,                      # Più supernodi semantici
    include_computational=True,             # Includi/escludi computational
    model_name='gemma-2-2b',               # Modello su Neuronpedia
    slug='my-custom-circuit'                # Nome univoco per il grafo
)
```

### Parametri URL:

- `pruningThreshold`: 0.6 (default) - soglia per pruning edges
- `densityThreshold`: 0.99 (default) - densità massima grafo
- `pinnedIds`: feature sempre visibili nel grafo

---

## 🔍 Differenze tra Versione Standard e Improved

| Aspetto | Standard | Improved |
|---------|----------|----------|
| Nomi supernodi | Duplicati (tutti "Capital") | Distintivi con layer range |
| Computational | Solo 5 | Top 8 per rilevanza |
| Feature totali | 172 | 483 |
| Usabilità | Media | Alta ✅ |

**Raccomandazione**: Usa sempre la versione **Improved** per visualizzazioni migliori.

---

## 🐛 Troubleshooting

### "URL troppo lungo"
- Alcuni browser hanno limiti su lunghezza URL
- **Soluzione 1**: Usa Chrome/Firefox (limiti più alti)
- **Soluzione 2**: Riduci `max_supernodes` e rigenera
- **Soluzione 3**: Usa Neuronpedia API per upload diretto

### "Supernodi non si vedono"
- Verifica che il formato sia `layer_feature_pos` (es. `12_12493_8`)
- Controlla che `pos` sia corretto per il tuo prompt
- Assicurati che il modello sia `gemma-2-2b` su Neuronpedia

### "Feature non esistono"
- Neuronpedia deve avere le feature del tuo modello indicizzate
- Verifica su neuronpedia.org se le feature esistono
- Usa la versione corretta del modello (es. gemma-2-2b non gemma-2-2b-it)

---

## 📝 Note Importanti

### Posizione Token (`pos`)

⚠️ **Critico**: Il parametro `pos` deve corrispondere alla posizione del token nel prompt per cui hai generato gli attribution graphs.

**Nel codice attuale**:
```python
pos = len(prompt.split()) - 1  # Ultima posizione (stima)
```

**Se i tuoi dati usano posizioni diverse**:
1. Verifica in `output/basic_anthropological_analysis.json` quale posizione è stata usata
2. Passa il valore esatto a `pos` quando chiami la funzione

### Formato Feature Neuronpedia

Neuronpedia usa il formato: `layer_feature_pos`

- `layer`: layer del modello (0-25 per Gemma-2-2B)
- `feature`: feature index nel transcoder
- `pos`: posizione token nel prompt

**Esempio**: `12_12493_8` = layer 12, feature 12493, position 8

---

## 🎓 Per l'Application MATS

### Come Includere nell'Application

1. **Screenshot del Grafo**
   - Apri l'URL su Neuronpedia
   - Fai screenshot del grafo completo
   - Aggiungi a `MATS_Application_Draft.md`

2. **URL come Supplemento**
   - Includi l'URL nella sezione "Supplementary Materials"
   - Permette ai reviewer di esplorare interattivamente

3. **Metriche da Evidenziare**
   - 483 feature coperte
   - 23 supernodi (15 semantici + 8 computazionali)
   - 52.3% logit influence coverage (post influence-first refactoring)
   - Controlled BOS leakage: 2.4%

---

## 🔗 Links Utili

- **Neuronpedia**: https://www.neuronpedia.org
- **Circuit Tracing Paper**: https://transformer-circuits.pub/2025/attribution-graphs/
- **Tutorial Notebook**: https://github.com/safety-research/circuit-tracer/blob/main/demos/circuit_tracing_tutorial.ipynb
- **Neuronpedia Docs**: https://www.neuronpedia.org/docs

---

## 📞 Contatti

Per domande sull'export Neuronpedia o problemi con la visualizzazione:
- Consulta la documentazione Neuronpedia
- Verifica che il modello e le feature siano indicizzati su Neuronpedia
- Usa il Discord di Neuronpedia per supporto

---

**Generated**: 2025-10-08
**Export Scripts**: `export_to_neuronpedia.py`, `export_to_neuronpedia_improved.py`
**Files**: `output/neuronpedia_url_improved.txt`, `output/neuronpedia_supernodes_improved.json`



