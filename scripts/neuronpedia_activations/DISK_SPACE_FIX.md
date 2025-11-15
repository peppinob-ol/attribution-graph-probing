# Fix: Gestione Spazio Disco per SAE Pesanti (clt-hp)

## Problema

Durante l'esecuzione su Google Colab con il SAE set `clt-hp`, lo script si bloccava con l'errore:

```
RuntimeError: Data processing error: CAS service error : IO Error: No space left on device (os error 28)
```

**Causa**: I decoder SAE del set `clt-hp` sono estremamente pesanti (8-15 GB per layer). Anche processando un layer alla volta, la cache di Hugging Face (`~/.cache/huggingface/hub/`) accumulava i file scaricati senza liberarli, esaurendo lo spazio disco disponibile su Colab.

## Soluzione Implementata

### 1. Pulizia Cache all'Avvio
Lo script ora pulisce automaticamente la cache HF prima di iniziare, rimuovendo eventuali SAE `clt-hp` precedentemente scaricati:

```python
# Rimuove cache SAE vecchi (pattern: models--mntss--clt-*)
for item in os.listdir(HF_CACHE_DIR):
    if "mntss--clt-" in item and os.path.isdir(item_path):
        shutil.rmtree(item_path, ignore_errors=True)
```

### 2. Pulizia Cache Dopo Ogni Layer
Dopo aver processato ogni layer, lo script:
- Scarica il SAE del layer (unload dalla GPU)
- **Cancella immediatamente i file dalla cache HF**
- Libera la memoria GPU

Questo garantisce che lo spazio disco venga riciclato continuamente durante l'esecuzione.

### 3. Monitoraggio Spazio Disco
Lo script ora mostra:
- Spazio disco disponibile all'avvio
- Dimensione della cache HF prima della pulizia
- Avvisi se lo spazio è insufficiente

## Output Atteso

```
Pulizia cache Hugging Face (spazio disco)...
  Cache HF attuale: 12.34 GB
  Rimuovo cache SAE: models--mntss--clt-gemma-2-2b-2.5M (11.50 GB)
  ✓ Liberati 11.50 GB di spazio disco
  Spazio disco: 45.23 GB liberi / 107.7 GB totali

[1/5] Processando prompt 'probe_0_Dallas'...
    Layer 0 [1/15]... OK (unloaded + cleaned)
    Layer 1 [2/15]... OK (unloaded + cleaned)
    ...
```

## Requisiti Minimi

Per eseguire lo script con `clt-hp` su Colab:
- **GPU**: T4 o superiore (per il modello gemma-2-2b)
- **Spazio disco libero**: ~15-20 GB (lo script ricicla lo spazio, ma serve spazio temporaneo per il download)
- **Memoria GPU**: ~6-8 GB

## Note Tecniche

### Perché CHUNK_BY_LAYER=True?
Con `CHUNK_BY_LAYER=True`, lo script:
1. Processa un solo layer per volta
2. Carica il SAE on-demand quando serve
3. Scarica immediatamente il SAE dopo l'uso
4. Cancella i file dalla cache HF

Questo approccio:
- ✓ Riduce memoria GPU
- ✓ Riduce spazio disco necessario
- ✗ Aumenta leggermente i tempi (più download sequenziali)

### Alternative Considerate

1. **Montare Google Drive e usarlo come cache**:
   ```python
   os.environ["HF_HOME"] = "/content/drive/MyDrive/hf_cache"
   ```
   - Pro: Più spazio disponibile (~15 GB Colab free)
   - Contro: I/O più lento su Drive

2. **Colab Pro/Pro+**:
   - Colab Pro: ~50 GB disco, GPU migliori
   - Colab Pro+: ~200 GB disco, GPU A100

3. **Esecuzione locale/cloud**:
   - Con disco sufficiente, non serve pulizia cache
   - Riutilizza i SAE già scaricati (più veloce)

## Ottimizzazione Velocità (v2)

### Problema Prestazioni

La versione iniziale del fix funzionava ma era **molto lenta** perché:
- Processava prompt-by-prompt
- Ogni prompt richiedeva tutti i layer
- Dopo ogni layer la cache veniva pulita
- **Risultato**: ogni layer veniva ri-scaricato per ogni prompt (5 prompt × 15 layer = 75 download invece di 15)

### Soluzione Ottimizzata

**Strategia layer-by-layer per tutti i prompt**:

```python
def run_layer_by_layer_all_prompts(prompts, features):
    for layer in layers:
        # Scarica il layer UNA SOLA VOLTA
        # Processa TUTTI i prompt con questo layer
        for prompt in prompts:
            process(prompt, layer)
        # Pulisce cache (una sola volta dopo tutti i prompt)
        cleanup_cache()
```

### Confronto Prestazioni

**Versione 1 (prompt-by-prompt)**:
- 5 prompt × 15 layer × 1 min download = **~75 minuti**
- Ogni layer viene scaricato 5 volte

**Versione 2 (layer-by-layer) - ATTUALE**:
- 15 layer × 1 download × 1 min + 5 prompt × 15 layer × 2 sec processing = **~17 minuti**
- Ogni layer viene scaricato 1 sola volta
- **4-5× più veloce!**

### Output Atteso (v2)

```
⚡ OTTIMIZZAZIONE: processando 15 layer per 5 prompt
   (ogni layer viene scaricato 1 sola volta)

  Layer 0 [1/15] - processando 5 prompt... ✓ (cleaned)
  Layer 1 [2/15] - processando 5 prompt... ✓ (cleaned)
  Layer 3 [3/15] - processando 5 prompt... ✓ (cleaned)
  ...
  Layer 24 [15/15] - processando 5 prompt... ✓ (cleaned)

============================================================
Riepilogo risultati:
  [1/5] probe_0_Dallas: 55 attivazioni, 12 token
  [2/5] probe_1_Austin: 55 attivazioni, 11 token
  ...
```

## Test

Script testato con:
- ✓ 5 prompt, 55 feature
- ✓ Layer 0-25 di gemma-2-2b
- ✓ SAE set: clt-hp (mntss/clt-gemma-2-2b-2.5M)
- ✓ Google Colab T4 GPU (free tier)
- ✓ Tempo esecuzione: ~15-20 minuti (vs ~75 minuti v1)

## Modifiche al Codice

File modificato: `batch_get_activations.py`

### v1 (Fix spazio disco)
1. **Linee 114-183**: Cleanup cache HF e check spazio disco
2. **Linee 485-500**: Cleanup cache dopo ogni layer processato
3. **Linea 69**: Commento esplicativo su gestione spazio disco

### v2 (Ottimizzazione velocità)
4. **Linee 510-615**: Nuova funzione `run_layer_by_layer_all_prompts()`
5. **Linee 626-653**: Main loop usa strategia layer-by-layer
6. **Linee 66-74**: Documentazione strategia ottimizzata

---

**Data**: 2025-10-20  
**Issue v1**: Errore "No space left on device" con clt-hp su Colab  
**Soluzione v1**: Pulizia aggressiva cache HF durante esecuzione  
**Issue v2**: Re-download continuo dei layer (molto lento)  
**Soluzione v2**: Processare layer-by-layer per tutti i prompt (4-5× più veloce)

