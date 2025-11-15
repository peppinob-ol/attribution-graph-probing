# File di Esempio per batch_get_activations.py

## File Forniti

### `example_prompts.json`
Esempio di file prompts con 3 prompt di test.
Formato: lista di oggetti con `id` e `text`.

### `example_features.json`
Esempio di file features con 3 feature sui layer 10 e 15.
Formato: lista di oggetti con `layer` e `index`.

**IMPORTANTE**: Gli esempi sono configurati per il modello di default `gemma-2-2b` con SAE set `clt-hp` (Circuit Tracer Transcoders).

## Compatibilità Modello/SAE

Se cambi `MODEL_ID` in `batch_get_activations.py`, devi anche cambiare `SOURCE_SET`:

| Modello | SAE Set Compatibili |
|---------|---------------------|
| `gpt2-small` | `res-jb` |
| `gemma-2-2b` | `gemmascope-res-16k`, `gemmascope-transcoder-16k`, `clt-hp` |
| `gemma-2-2b-it` | `gemmascope-res-16k`, `gemmascope-transcoder-16k` |

**Nota**: `clt-hp` è il "Circuit Tracer Transcoders" di Hanna & Piotrowski - vedi [Neuronpedia](https://www.neuronpedia.org/transcoders-hp)

## Layer Validi per Modello

| Modello | Layer Disponibili |
|---------|-------------------|
| `gpt2-small` | 0-11 (12 layer) |
| `gemma-2-2b` | 0-25 (26 layer) |

Assicurati che i layer nelle feature siano validi per il modello scelto!

## Uso Rapido

1. Copia gli esempi:
```python
!cp example_prompts.json /content/prompts.json
!cp example_features.json /content/features.json
```

2. Esegui `batch_get_activations.py`

3. Risultati salvati in `/content/activations_dump.json`

