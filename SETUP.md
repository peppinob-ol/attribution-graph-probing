# Setup Ambiente - Circuit Tracer

## Installazione Rapida

### 1. Crea l'ambiente virtuale e installa le dipendenze

```powershell
# Esegui lo script di setup (Windows PowerShell)
.\setup_venv.ps1
```

Oppure manualmente:

```powershell
# Crea venv
python -m venv .venv

# Attiva venv
.\.venv\Scripts\Activate.ps1

# Installa dipendenze
pip install -r requirements.txt
```

### 2. Verifica l'installazione

```powershell
python -c "import torch; print(f'Torch version: {torch.__version__}')"
```

## Dipendenze Principali

- **torch**: Core per il calcolo tensoriale e modelli
- **ipython**: Per visualizzazioni interattive SVG
- **jupyter**: (opzionale) Per notebook interattivi

## Uso Base

### Visualizzazione Supernodes

```python
from scripts.visualization.graph_visualization import (
    create_graph_visualization,
    Supernode,
    InterventionGraph,
    Feature
)

# Vedi examples/visualize_supernodes_example.py per un esempio completo
```

### Eseguire l'esempio

```powershell
# Attiva venv se non già attivo
.\.venv\Scripts\Activate.ps1

# Esegui esempio
python examples/visualize_supernodes_example.py
```

## Struttura del Progetto

```
circuit_tracer-prompt_rover/
├── scripts/
│   └── visualization/
│       ├── graph_visualization.py    # Core visualizzazione
│       └── neuronpedia_export.py     # Export per Neuronpedia
├── examples/
│   └── visualize_supernodes_example.py  # Esempio pratico
├── docs/
│   ├── GRAPH_VISUALIZATION_GUIDE.md  # Guida dettagliata
│   └── QUICK_REFERENCE.md            # Riferimento rapido
├── output/
│   └── final_anthropological_optimized.json  # Supernodes finali
├── requirements.txt                  # Dipendenze Python
└── setup_venv.ps1                    # Script setup automatico
```

## Documentazione

- **📖 Guida completa**: `docs/GRAPH_VISUALIZATION_GUIDE.md`
- **⚡ Riferimento rapido**: `QUICK_REFERENCE.md`
- **🔄 Flusso dati**: `docs/DATA_FLOW.md`

## Troubleshooting

### PowerShell Execution Policy Error

Se ricevi un errore eseguendo `setup_venv.ps1`:

```powershell
Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
```

### Torch Installation Issues

Se hai problemi con torch, installa manualmente:

```powershell
# CPU only (più leggero)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# Con CUDA (GPU NVIDIA)
pip install torch --index-url https://download.pytorch.org/whl/cu118
```

### Import Errors

Assicurati di essere nella directory root del progetto e che venv sia attivo:

```powershell
# Verifica directory
Get-Location

# Verifica venv attivo (dovresti vedere (.venv) nel prompt)
Write-Host $env:VIRTUAL_ENV
```

## Prossimi Passi

1. ✅ Installa l'ambiente
2. 📖 Leggi `docs/GRAPH_VISUALIZATION_GUIDE.md`
3. 🚀 Esegui `examples/visualize_supernodes_example.py`
4. 🔬 Analizza i tuoi supernodes con il grafo visualizer

## Note

- **Python Version**: Richiede Python 3.8+
- **OS**: Ottimizzato per Windows, ma compatibile con Linux/Mac
- **GPU**: Non richiesta per la visualizzazione, utile per l'analisi dei modelli



