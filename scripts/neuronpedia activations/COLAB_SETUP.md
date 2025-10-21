# Setup Rapido per Google Colab

## 1. Setup Runtime
1. Vai a **Runtime > Change runtime type**
2. Seleziona **Hardware accelerator: T4 GPU** (o superiore come V100/A100)
3. Clicca **Save**

## 2. Upload File Input
Carica i tuoi file JSON (oppure usa gli esempi forniti):

```python
# Upload file da locale
from google.colab import files
uploaded = files.upload()  # Seleziona prompts.json e features.json
```

Oppure copia gli esempi:
```python
!cp example_prompts.json /content/prompts.json
!cp example_features.json /content/features.json
```

## 3. Esegui lo Script
Copia il contenuto di `batch_get_activations.py` in una cella e esegui.

## 4. Download Risultati
```python
from google.colab import files
files.download('/content/activations_dump.json')
```

## Troubleshooting

### GPU Out of Memory
Se vedi errore `CUDA out of memory`:
1. Vai a **Runtime > Restart session**
2. Ri-esegui la cella

### Formato JSON Non Valido
Controlla che i tuoi JSON seguano il formato negli esempi:
- `example_prompts.json` - lista di stringhe o oggetti con id/text
- `example_features.json` - lista di oggetti con layer/index

### Memoria Insufficiente / OOM per SAE Pesanti
Il modello Gemma-2-2b richiede ~10 GB di GPU.

**Per SAE set leggeri** (es. `res-jb`):
- T4 (15 GB): OK
- Lascia `CHUNK_BY_LAYER = False`

**Per SAE set pesanti** (es. `clt-hp`, transcoders):
- T4 (15 GB): **Insufficiente** - i SAE clt-hp richiedono altri ~10-12 GB
- Soluzioni:
  1. **Usa V100/A100** (Runtime > Change runtime type > GPU type)
  2. **Oppure imposta** `CHUNK_BY_LAYER = True` (più lento ma usa meno memoria)
  3. **Oppure usa SAE più leggeri** come `gemmascope-res-16k`

Con `CHUNK_BY_LAYER = True`, i layer vengono processati uno alla volta anziché tutti insieme.

