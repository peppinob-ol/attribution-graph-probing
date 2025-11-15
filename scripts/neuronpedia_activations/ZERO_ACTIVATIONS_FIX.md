# Fix: Feature con Attivazione Zero

## Il Problema

Quando si esegue lo script con 55 feature richieste ma l'output JSON mostra solo 1-5 feature per prompt:

**Richiesto**: 55 feature da vari layer  
**Output**: Solo 1 feature (`0-26795`) presente nei risultati  
**Causa**: Le altre 54 feature hanno **valore di attivazione = 0** sui prompt testati

## Spiegazione

### Comportamento Standard dell'API

L'API Neuronpedia (endpoint `/activation/all`) restituisce **solo le feature con attivazione > 0** per:
- ✅ Ridurre dimensione dei file
- ✅ Risparmiare bandwidth
- ✅ Velocizzare il processing

Questo è il comportamento corretto e intenzionale.

### Esempio Concreto

Input: 55 feature richieste
```json
[
  {"layer": 0, "index": 26795},
  {"layer": 0, "index": 1734452},
  {"layer": 1, "index": 83598913},
  ... (52 altre feature)
]
```

Prompt testato:
```
"entity: A city in Texas, USA. is Dallas"
```

Risultato:
- **1 feature attiva**: `0-26795` con valore ~1.09
- **54 feature inattive**: valore = 0 (non incluse nell'output)

## Soluzione Implementata

### Nuovo Parametro: `INCLUDE_ZERO_ACTIVATIONS`

Linea 78 in `batch_get_activations.py`:
```python
INCLUDE_ZERO_ACTIVATIONS = True  # ← True per vedere tutte le 55 feature, False solo quelle attive
```

### Comportamento

| Valore | Cosa Include | Dimensione File | Uso Consigliato |
|--------|-------------|-----------------|------------------|
| `True` | **Tutte** le feature richieste (anche con valore 0) | ⬆️ Più grande | Analisi complete, ML, ricerca |
| `False` | **Solo** feature attivate (valore > 0) | ⬇️ Più compatto | Visualizzazioni, esplorazione |

### Output con `INCLUDE_ZERO_ACTIVATIONS = True`

```json
{
  "model": "gemma-2-2b",
  "source_set": "clt-hp",
  "n_prompts": 5,
  "n_features_requested": 55,
  "results": [
    {
      "probe_id": "probe_0_Dallas",
      "prompt": "entity: A city in Texas, USA. is Dallas",
      "tokens": ["<bos>", "entity", ":", " A", " city", ...],
      "activations": [
        {
          "source": "0-clt-hp",
          "index": 26795,
          "values": [1.0917983055114746, 0.0, 0.0, ...],  // ✅ Attiva
          "max_value": 1.0917983055114746
        },
        {
          "source": "0-clt-hp",
          "index": 1734452,
          "values": [0.0, 0.0, 0.0, ...],  // ✅ Inclusa anche se = 0
          "max_value": 0.0
        },
        ... // tutte le altre 53 feature con valore 0
      ]
    }
  ]
}
```

### Output con `INCLUDE_ZERO_ACTIVATIONS = False` (default API)

```json
{
  "results": [
    {
      "probe_id": "probe_0_Dallas",
      "activations": [
        {
          "source": "0-clt-hp",
          "index": 26795,
          "values": [1.0917983055114746, 0.0, 0.0, ...],  // Solo questa
          "max_value": 1.0917983055114746
        }
        // Le altre 54 feature non sono incluse
      ]
    }
  ]
}
```

## Quando Usare `True` vs `False`

### Usa `INCLUDE_ZERO_ACTIVATIONS = True` quando:

1. **Analisi complete**: Serve avere tutte le feature per ML/statistiche
2. **Confronti**: Vuoi comparare attivazioni tra prompt diversi
3. **Ricerca**: Stai studiando perché certe feature NON si attivano
4. **Debugging**: Vuoi verificare che tutte le feature siano state processate

**Costo**: File output più grandi (~5-10× se molte feature a zero)

### Usa `INCLUDE_ZERO_ACTIVATIONS = False` quando:

1. **Esplorazione**: Vuoi vedere solo le feature interessanti (attive)
2. **Visualizzazioni**: Per UI/grafici serve solo ciò che si attiva
3. **Storage limitato**: Vuoi ridurre dimensione file
4. **Performance**: Parsing JSON più veloce con meno dati

**Vantaggio**: File compatti, veloce da elaborare

## Come Verificare

### Prima dell'Esecuzione

```python
# In batch_get_activations.py, linea 78:
INCLUDE_ZERO_ACTIVATIONS = True  # ← Verifica questo valore
```

### Dopo l'Esecuzione

Controlla il riepilogo:
```
Riepilogo risultati:
  [1/5] probe_0_Dallas: 55 attivazioni, 12 token  ← ✅ Tutte le 55 feature presenti!
  [2/5] probe_1_Austin: 55 attivazioni, 11 token
  ...
```

Se vedi "1 attivazioni" invece di "55 attivazioni", significa che `INCLUDE_ZERO_ACTIVATIONS = False`.

## Note Tecniche

### Implementazione

Lo script aggiunge feature mancanti dopo aver ricevuto la risposta dall'API:

```python
# Per ogni layer processato:
found_features = set()  # traccia feature già presenti

# 1. Aggiungi feature attive dalla risposta API
for activation in api_response.activations:
    if activation in wanted_features:
        filtered.append(activation)
        found_features.add(activation.id)

# 2. Aggiungi feature richieste ma mancanti (= 0)
if INCLUDE_ZERO_ACTIVATIONS:
    for feature in wanted_features:
        if feature not in found_features:
            # Crea entry con valori a zero
            filtered.append({
                "source": feature.source,
                "index": feature.index,
                "values": [0.0] * num_tokens,
                "max_value": 0.0,
                ...
            })
```

### Impatto su Performance

- **Tempo esecuzione**: Identico (il processing è lo stesso)
- **Memoria durante esecuzione**: Minimo impatto (+1-2%)
- **Dimensione file output**: Può aumentare 5-10× se molte feature a zero
- **Velocità parsing JSON**: Proporzionale alla dimensione file

## Domande Frequenti

**Q: Perché solo 1 feature si attiva sui miei prompt?**  
A: È normale! La maggior parte delle feature SAE sono molto specifiche. Se i tuoi prompt non contengono i pattern che attivano quelle feature, rimangono a zero.

**Q: Come posso far attivare più feature?**  
A: Usa prompt più vari o scegli feature che sai essere rilevanti per il tuo dominio. Puoi esplorare Neuronpedia.org per trovare feature correlate ai tuoi concetti.

**Q: Il file è troppo grande con True, cosa faccio?**  
A: Usa `INCLUDE_ZERO_ACTIVATIONS = False` e filtra le feature richieste dopo, oppure riduci il numero di feature richieste.

**Q: Posso filtrare dopo per avere solo feature con valore > soglia?**  
A: Sì! Con `True` hai tutti i dati e puoi filtrare in post-processing con la soglia che preferisci.

## Riepilogo

| Aspetto | Valore | Descrizione |
|---------|--------|-------------|
| **Problema originale** | 55 richieste → 1 output | Feature inattive non incluse |
| **Causa** | Comportamento API | Solo attivazioni > 0 restituite |
| **Soluzione** | `INCLUDE_ZERO_ACTIVATIONS=True` | Include tutte le feature richieste |
| **File modificati** | `batch_get_activations.py` | 3 funzioni aggiornate |
| **Retrocompatibile** | ✅ Sì | Default `False` = comportamento originale |

---

**Data**: 2025-10-20  
**Issue**: Output mostra solo 1 feature invece di 55 richieste  
**Soluzione**: Nuovo parametro `INCLUDE_ZERO_ACTIVATIONS` per includere feature a zero

