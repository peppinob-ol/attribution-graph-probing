# Guida API Auto-Interp di Neuronpedia

## 🎯 Problema Risolto

L'errore `"No auto-interp key found for user."` indica che **non hai configurato le API keys di OpenAI/Anthropic/Google** nelle impostazioni di Neuronpedia.

## ✅ Soluzione: Configurazione API Keys

### 1. Vai nelle Impostazioni di Neuronpedia
👉 **https://neuronpedia.org/settings**

### 2. Inserisci le tue API Keys
Nella sezione **Auto-Interpretation Settings**, aggiungi le tue API keys per i servizi che vuoi usare:

- **OpenAI**: Per usare modelli come `gpt-4o-mini`, `gpt-4`, etc.
- **Anthropic**: Per usare modelli Claude
- **Google**: Per usare modelli Gemini

### 3. Salva le Impostazioni

Una volta salvate, l'endpoint `/api/explanation/generate` funzionerà correttamente.

---

## 📚 Endpoint Disponibili

### 1. `/api/explanation/generate` - Genera Spiegazione
Genera una nuova spiegazione per una feature specifica.

**Endpoint:** `POST https://www.neuronpedia.org/api/explanation/generate`

**Headers:**
```json
{
  "Content-Type": "application/json",
  "x-api-key": "YOUR_NEURONPEDIA_API_KEY"
}
```

**Body:**
```json
{
  "modelId": "gemma-2-2b",
  "layer": "1-clt-hp",
  "index": 11298,
  "explanationType": "oai_token-act-pair",
  "explanationModelName": "gpt-4o-mini"
}
```

**Parametri:**
- `modelId` (string): ID del modello (es. "gpt2-small", "gemma-2-2b")
- `layer` (string): Layer della feature (es. "8-res-jb", "6-gemmascope-res-16k")
- `index` (number): Indice della feature
- `explanationType` (string): Tipo di spiegazione
  - `"oai_token-act-pair"` - Basato su coppie token-attivazione
  - `"oai_attention-head"` - Per attention heads
- `explanationModelName` (string): Modello da usare (es. "gpt-4o-mini", "claude-3-5-sonnet")
  - Deve essere uno dei modelli disponibili nel dropdown su Neuronpedia

**Risposte:**
- `200`: Spiegazione generata con successo
- `400`: Parametri non validi O "No auto-interp key found for user" O spiegazione già esistente
- `401`: API key non valida
- `404`: Feature non trovata

---

### 2. `/api/feature/{modelId}/{layer}/{index}` - Recupera Feature
Ottiene i dettagli di una feature, incluse le spiegazioni esistenti.

**Endpoint:** `GET https://www.neuronpedia.org/api/feature/{modelId}/{layer}/{index}`

**Headers:**
```json
{
  "x-api-key": "YOUR_NEURONPEDIA_API_KEY"
}
```

**Esempio:**
```
GET https://www.neuronpedia.org/api/feature/gpt2-small/8-res-jb/55
```

**Risposta:** Include un array `explanations` con tutte le spiegazioni generate per quella feature, ognuna con il proprio `id` (explanationId).

---

### 3. `/api/explanation/score` - Score della Spiegazione
Calcola lo score di una spiegazione esistente.

**Endpoint:** `POST https://www.neuronpedia.org/api/explanation/score`

**Headers:**
```json
{
  "Content-Type": "application/json",
  "x-api-key": "YOUR_NEURONPEDIA_API_KEY"
}
```

**Body:**
```json
{
  "explanationId": "cm9n54uhz000xe5mu4iqhpoko",
  "scorerModel": "gpt-4o-mini",
  "scorerType": "recall_alt"
}
```

**Parametri:**
- `explanationId` (string): ID della spiegazione (ottenuto da `/api/feature/{modelId}/{layer}/{index}`)
- `scorerModel` (string): Modello per lo scoring (es. "gpt-4o-mini")
- `scorerType` (string): Tipo di scoring method
  - `"recall_alt"` - Recall alternativo (richiede OpenRouter)
  - `"eleuther_fuzz"` - Fuzzy matching (richiede OpenRouter)
  - `"eleuther_recall"` - Recall Eleuther (richiede OpenRouter)
  - `"eleuther_embedding"` - Embedding-based (richiede OpenRouter)

**⚠️ IMPORTANTE:** Questo endpoint richiede una **OpenRouter API key** configurata su Neuronpedia oltre alle altre keys.

**Workflow completo per lo scoring:**
1. Genera spiegazione con `/api/explanation/generate`
2. Recupera feature con `/api/feature/{modelId}/{layer}/{index}` per ottenere `explanationId`
3. Calcola score con `/api/explanation/score` usando l'`explanationId`

---

## 🔧 Script di Test

### Test Generazione
```bash
python tests/test_explanation_generate.py
```

Testa la generazione di spiegazioni con diversi modelli e features.

### Test Scoring
```bash
python tests/test_explanation_score.py
```

Testa il recupero degli score di spiegazioni esistenti.

---

## ⚠️ Errori Comuni

### 1. `"No auto-interp key found for user."`
**Causa:** Non hai configurato le API keys OpenAI/Anthropic/Google su Neuronpedia.
**Soluzione:** Vai su https://neuronpedia.org/settings e configura le API keys.

### 1b. `"This autointerp type requires an OpenRouter key."`
**Causa:** L'endpoint `/api/explanation/score` richiede una OpenRouter API key.
**Soluzione:** Vai su https://neuronpedia.org/settings e aggiungi anche la tua OpenRouter API key.

### 2. `"An auto-interp with this explanation type and model already exists."`
**Causa:** La spiegazione è già stata generata per quella feature.
**Soluzione:** Non è un errore! La spiegazione esiste già. Usa l'endpoint `/api/explanation/score` per recuperarla.

### 3. `400 Bad Request` (senza messaggio specifico)
**Possibili cause:**
- `modelId`, `layer` o `index` non esistono su Neuronpedia
- `explanationType` non supportato
- `explanationModelName` non valido

### 4. `401 Unauthorized`
**Causa:** La tua NEURONPEDIA_API_KEY non è valida.
**Soluzione:** Verifica la key sul tuo account Neuronpedia.

---

## 📖 Riferimenti

- **Documentazione API:** https://www.neuronpedia.org/api-doc
- **Account Settings:** https://neuronpedia.org/settings
- **GitHub Neuronpedia:** https://github.com/hijohnnylin/neuronpedia

---

## 🎓 Esempio Completo

```python
import os
import requests
from dotenv import load_dotenv

# Carica variabili d'ambiente
load_dotenv()
api_key = os.getenv("NEURONPEDIA_API_KEY")

# Configura la richiesta
url = "https://www.neuronpedia.org/api/explanation/generate"
headers = {
    "x-api-key": api_key,
    "Content-Type": "application/json"
}
payload = {
    "modelId": "gpt2-small",
    "layer": "8-res-jb",
    "index": 55,
    "explanationType": "oai_token-act-pair",
    "explanationModelName": "gpt-4o-mini"
}

# Invia richiesta
response = requests.post(url, headers=headers, json=payload, timeout=60)

# Gestisci risposta
if response.status_code == 200:
    print("✓ Spiegazione generata!")
    print(response.json())
elif response.status_code == 400:
    error = response.json()
    if "No auto-interp key" in error.get("message", ""):
        print("⚠ Configura le API keys su https://neuronpedia.org/settings")
    elif "already exists" in error.get("message", ""):
        print("ℹ Spiegazione già esistente per questa feature")
    else:
        print(f"✗ Errore: {error}")
else:
    print(f"✗ Status: {response.status_code}")
    print(response.text)
```

---

## ✨ Prossimi Passi

1. ✅ Vai su https://neuronpedia.org/settings
2. ✅ Configura le API keys di:
   - OpenAI (per generazione spiegazioni con GPT)
   - Anthropic (opzionale, per Claude)
   - Google (opzionale, per Gemini)
   - **OpenRouter** (necessario per lo scoring delle spiegazioni)
3. ✅ Esegui `python tests/neuronpedia_autointerp_example.py` per testare tutto
4. ✅ Verifica che funzioni tutto correttamente!

## 📝 Script Disponibili

- `tests/neuronpedia_autointerp_example.py` - Script completo con esempi pratici
- `tests/test_explanation_generate.py` - Test per la generazione di spiegazioni
- `tests/test_explanation_score.py` - Test per lo scoring (deprecato, usa l'example sopra)

