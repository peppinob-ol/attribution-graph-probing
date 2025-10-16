# Visualizzazione Supernodes - Guida Rapida

## Setup Completato ✓

L'ambiente è ora configurato e pronto all'uso!

### Cosa è stato installato:
- ✓ Ambiente virtuale `.venv`
- ✓ PyTorch 2.8.0
- ✓ IPython, Jupyter, Notebook
- ✓ NumPy, Matplotlib
- ✓ Tutte le dipendenze necessarie

---

## 🚀 Inizia Subito

### 1. Visualizza i Tuoi Supernodes (Script Python)

```powershell
# Attiva venv
.\.venv\Scripts\Activate.ps1

# Esegui visualizzazione
python scripts/visualize_my_supernodes.py
```

**Output**: 
- Analisi completa dei 41 supernodes
- Statistiche per tema
- Grafo SVG salvato in `output/my_supernodes_circuit.svg`

**Per vedere il grafo**: Apri `output/my_supernodes_circuit.svg` nel browser!

---

### 2. Visualizza in Jupyter Notebook (Interattivo)

```powershell
# Attiva venv
.\.venv\Scripts\Activate.ps1

# Lancia Jupyter
jupyter notebook visualize_supernodes.ipynb
```

Il notebook ti permette di:
- Esplorare i supernodes interattivamente
- Modificare visualizzazioni in tempo reale
- Simulare interventi
- Salvare risultati personalizzati

---

## 📊 Risultati Analisi

### I Tuoi Supernodes:
- **Totale**: 41 supernodes
- **Temi principali**:
  - Capital: 19 supernodes (tema dominante)
  - <BOS>: 15 supernodes
  - of, state, Dallas, in, Texas, city: 1-2 supernodes ciascuno

### Top Supernodes per Influenza:
1. **CICCIOTTO_43** (<BOS>): influenza totale 14.15
2. **CICCIOTTO_50** (city): influenza totale 11.65
3. **CICCIOTTO_31** (of): influenza totale 11.21
4. **CICCIOTTO_48** (Texas): influenza totale 10.33
5. **CICCIOTTO_39** (<BOS>): influenza totale 9.15

---

## 🔍 Come Funziona la Visualizzazione

### Struttura del Grafo

```
Input Layer (Embeddings)
    ↓
Intermediate Layers (Supernodes semantici)
    ↓ [Connessioni causali]
    ↓
Output Layer (Predizioni)
```

### Interpretazione Visiva

**Elementi del grafo**:
- **Nodi grigi**: Attivi (>25% attivazione)
- **Nodi grigi chiari**: Spenti (≤25%)
- **Nodi arancioni**: Nodi sostitutivi (interventi)
- **Badge bianchi**: Percentuale attivazione
- **Badge arancioni**: Interventi applicati

**Esempio di lettura**:
```
[Capital] 100% → [Texas] 100% → [Say Austin] 100%
```
Significa: il concetto "Capital" attiva "Texas" che attiva "Say Austin"

---

## 📁 File Creati

```
circuit_tracer-prompt_rover/
├── .venv/                                    [NEW] Ambiente virtuale
├── requirements.txt                          [NEW] Dipendenze
├── setup_venv.ps1                            [NEW] Script setup automatico
├── SETUP.md                                  [NEW] Guida setup
├── README_VISUALIZATION.md                   [NEW] Questa guida
│
├── scripts/
│   └── visualize_my_supernodes.py           [NEW] Script visualizzazione
│
├── examples/
│   └── visualize_supernodes_example.py      [NEW] Esempio semplificato
│
├── docs/
│   └── GRAPH_VISUALIZATION_GUIDE.md         [NEW] Guida completa (236 righe)
│
├── output/
│   └── my_supernodes_circuit.svg            [NEW] Grafo visualizzato
│
└── visualize_supernodes.ipynb               [NEW] Notebook interattivo
```

---

## 📖 Documentazione

### Guide Dettagliate:
1. **`docs/GRAPH_VISUALIZATION_GUIDE.md`**
   - Spiegazione completa del sistema
   - Workflow dettagliato
   - Esempi di interventi
   - Casi d'uso avanzati

2. **`SETUP.md`**
   - Istruzioni setup complete
   - Troubleshooting
   - Configurazione avanzata

3. **`QUICK_REFERENCE.md`**
   - Comandi rapidi
   - Riferimenti veloci

---

## 🎯 Prossimi Passi

### Livello 1: Esplorazione Base
1. ✓ Apri `output/my_supernodes_circuit.svg` nel browser
2. ✓ Esegui `scripts/visualize_my_supernodes.py`
3. ✓ Leggi `docs/GRAPH_VISUALIZATION_GUIDE.md`

### Livello 2: Personalizzazione
1. Modifica temi in `visualize_my_supernodes.py` (linea 141):
   ```python
   focus_themes = ['Capital', 'Texas', 'Dallas']  # Cambia questi
   ```
2. Cambia numero max nodi (linea 143):
   ```python
   max_nodes=10  # Aumenta o riduci
   ```

### Livello 3: Analisi Avanzata
1. Apri `visualize_supernodes.ipynb` in Jupyter
2. Simula interventi sui nodi
3. Crea grafi personalizzati per prompt diversi

### Livello 4: Integrazione con Modello Reale
Per usare attivazioni reali invece di simulate:
1. Carica un modello (es. con TransformerLens)
2. Ottieni attivazioni: `logits, acts = model.get_activations(prompt)`
3. Inizializza supernodes: `graph.initialize_node(node, acts)`
4. Visualizza con attivazioni reali!

---

## 💡 Suggerimenti

### Modifica Focus Temi
Per analizzare supernodes diversi, edita `scripts/visualize_my_supernodes.py`:

```python
# Linea ~250
focus_themes = ['Capital', 'Texas', 'Dallas', 'state']

# Prova con:
focus_themes = ['Capital']  # Solo Capital
# oppure:
focus_themes = None  # Tutti i temi
```

### Esporta Più Grafi
Esegui lo script più volte con temi diversi:

```powershell
# Grafo 1: Focus su Capital
python scripts/visualize_my_supernodes.py
# (modifica script per cambiare temi)

# Grafo 2: Focus su BOS
python scripts/visualize_my_supernodes.py
```

Ogni esecuzione sovrascrive `output/my_supernodes_circuit.svg`, quindi rinominalo se vuoi conservarlo.

---

## 🔧 Troubleshooting

### Problema: "ModuleNotFoundError"
**Soluzione**: Assicurati che venv sia attivo
```powershell
.\.venv\Scripts\Activate.ps1
```

### Problema: SVG non si apre
**Soluzione**: Usa un browser moderno (Chrome, Firefox, Edge)

### Problema: "Import Error" in Jupyter
**Soluzione**: Installa kernel Jupyter nel venv
```powershell
.\.venv\Scripts\python.exe -m ipykernel install --user --name=circuit_tracer
```

### Problema: Encoding errors (emoji)
**Soluzione**: Gli script sono stati aggiornati per evitare emoji. Se vedi ancora errori:
```powershell
chcp 65001  # Imposta UTF-8 in PowerShell
```

---

## 📞 Supporto

- **Guida completa**: `docs/GRAPH_VISUALIZATION_GUIDE.md`
- **Setup**: `SETUP.md`
- **Quick ref**: `QUICK_REFERENCE.md`
- **Esempio**: `examples/visualize_supernodes_example.py`

---

## ✨ Filosofia del Tool

Questo strumento implementa il framework **Attribution Graphs** di Anthropic:

1. **Decomposizione**: Comportamento = ∑ circuiti semantici
2. **Validazione**: Ogni circuito è testabile con interventi
3. **Interpretabilità**: Supernodes hanno nomi semantici, non solo numeri

### Workflow Scientifico:
```
Ipotesi → Costruzione Grafo → Misurazione → Visualizzazione → Intervento → Validazione
```

I tuoi supernodes rappresentano **gruppi coerenti di features** che contribuiscono semanticamente all'output del modello. La visualizzazione ti permette di:
- Vedere le relazioni causali
- Testare ipotesi con interventi
- Validare l'interpretabilità

---

## 🎉 Conclusione

Hai ora tutto il necessario per:
- ✓ Visualizzare i tuoi 41 supernodes
- ✓ Esplorare circuiti causali
- ✓ Simulare interventi
- ✓ Esportare grafi SVG

**Inizia con**:
```powershell
.\.venv\Scripts\Activate.ps1
python scripts/visualize_my_supernodes.py
```

Poi apri `output/my_supernodes_circuit.svg` e esplora! 🚀

---

*Ultima modifica: 2025-10-09*



