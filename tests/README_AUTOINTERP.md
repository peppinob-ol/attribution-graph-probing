# 🧠 Neuronpedia Auto-Interp API - Guida Completa

## ✅ Problema Risolto

L'errore nel tuo JSON originale era:
```json
{
  "modelId": "gemma-2-2b",
  "layer": "1-clt-hp",
  "index": 11298  // <-- MANCAVA LA VIRGOLA QUI
  "explanationType": "oai_token-act-pair",
  "explanationModelName": "o4-mini"
}
```

**E l'errore principale era:** `"No auto-interp key found for user."`

Questo significa che devi configurare le API keys su Neuronpedia!

---

## 🎯 Soluzione Rapida

### 1. Configura le API Keys
Vai su: **https://neuronpedia.org/settings**

Configura:
- ✅ **OpenAI API Key** (per generare spiegazioni con GPT-4, GPT-4o-mini, etc.)
- ✅ **OpenRouter API Key** (necessaria per lo scoring delle spiegazioni)
- ⚪ Anthropic (opzionale, per Claude)
- ⚪ Google (opzionale, per Gemini)

### 2. Testa l'API
```bash
python tests/neuronpedia_autointerp_example.py
```

---

## 📚 API Endpoints Documentati

### 1️⃣ Genera Spiegazione
**Endpoint:** `POST /api/explanation/generate`

```python
import requests

url = "https://www.neuronpedia.org/api/explanation/generate"
headers = {
    "x-api-key": "YOUR_NEURONPEDIA_API_KEY",
    "Content-Type": "application/json"
}
payload = {
    "modelId": "gemma-2-2b",
    "layer": "1-clt-hp",
    "index": 11298,  # <-- Correzione: virgola aggiunta
    "explanationType": "oai_token-act-pair",
    "explanationModelName": "gpt-4o-mini"
}

response = requests.post(url, json=payload, headers=headers)
```

**Parametri:**
- `modelId`: ID del modello (es. "gpt2-small", "gemma-2-2b")
- `layer`: Layer della feature (es. "8-res-jb", "1-clt-hp")
- `index`: Indice numerico della feature
- `explanationType`: Tipo di spiegazione
  - `"oai_token-act-pair"` - Token-activation pairs
  - `"oai_attention-head"` - Attention heads
- `explanationModelName`: Modello per generare la spiegazione
  - `"gpt-4o-mini"` (raccomandato, veloce ed economico)
  - `"gpt-4"`
  - `"claude-3-5-sonnet"`
  - Altri disponibili su Neuronpedia

---

### 2️⃣ Recupera Feature
**Endpoint:** `GET /api/feature/{modelId}/{layer}/{index}`

```python
url = "https://www.neuronpedia.org/api/feature/gpt2-small/8-res-jb/55"
headers = {"x-api-key": "YOUR_NEURONPEDIA_API_KEY"}

response = requests.get(url, headers=headers)
feature_data = response.json()

# Estrai le spiegazioni
explanations = feature_data.get("explanations", [])
explanation_id = explanations[0]["id"]  # Necessario per lo scoring
```

---

### 3️⃣ Calcola Score Spiegazione
**Endpoint:** `POST /api/explanation/score`

⚠️ **IMPORTANTE:** Richiede **OpenRouter API key** configurata!

```python
url = "https://www.neuronpedia.org/api/explanation/score"
headers = {
    "x-api-key": "YOUR_NEURONPEDIA_API_KEY",
    "Content-Type": "application/json"
}
payload = {
    "explanationId": "cm9n54uhz000xe5mu4iqhpoko",  # Da GET /api/feature
    "scorerModel": "gpt-4o-mini",
    "scorerType": "recall_alt"
}

response = requests.post(url, json=payload, headers=headers)
score_data = response.json()
score_value = score_data["score"]["value"]  # Valore tra 0 e 1
```

**Parametri scorerType:**
- `"recall_alt"` - Recall alternativo (default)
- `"eleuther_fuzz"` - Fuzzy matching
- `"eleuther_recall"` - Recall Eleuther
- `"eleuther_embedding"` - Embedding-based

---

## 🛠️ Script Disponibili

### 1. Script Completo con Esempi
```bash
python tests/neuronpedia_autointerp_example.py
```

Questo script mostra:
- ✅ Come generare spiegazioni
- ✅ Come recuperare feature esistenti
- ✅ Come calcolare lo score delle spiegazioni
- ✅ Gestione completa degli errori

### 2. Test Generazione
```bash
python tests/test_explanation_generate.py
```

Testa la generazione di spiegazioni con diversi modelli.

### 3. Test Scoring
```bash
python tests/test_explanation_score.py
```

Testa il workflow completo: Feature → explanationId → Score

---

## ⚠️ Errori Comuni & Soluzioni

### Errore: `"No auto-interp key found for user."`
**Causa:** API keys non configurate su Neuronpedia.
**Soluzione:** 
1. Vai su https://neuronpedia.org/settings
2. Aggiungi OpenAI API key (o Anthropic/Google)
3. Riprova

---

### Errore: `"This autointerp type requires an OpenRouter key."`
**Causa:** Manca la OpenRouter API key (necessaria per lo scoring).
**Soluzione:**
1. Crea account su https://openrouter.ai/
2. Ottieni una API key
3. Aggiungila su https://neuronpedia.org/settings
4. Riprova

---

### Errore: `"An auto-interp with this explanation type and model already exists."`
**Causa:** La spiegazione è già stata generata!
**Soluzione:** Non è un errore! Usa `/api/feature/{modelId}/{layer}/{index}` per recuperare la spiegazione esistente.

---

### Errore: `400 Bad Request` (generico)
**Possibili cause:**
- ✗ `modelId`, `layer` o `index` non esistono su Neuronpedia
- ✗ `explanationType` non supportato (usa "oai_token-act-pair" o "oai_attention-head")
- ✗ `explanationModelName` non valido
- ✗ Parametri mancanti o formato JSON errato

---

### Errore: `401 Unauthorized`
**Causa:** NEURONPEDIA_API_KEY non valida.
**Soluzione:**
1. Verifica la tua API key su https://neuronpedia.org/account
2. Aggiorna il file `.env`

---

## 🎓 Workflow Completo

### Per Generare e Scorare una Spiegazione:

```python
from tests.neuronpedia_autointerp_example import NeuronpediaAutoInterp
import os

# 1. Inizializza il client
api_key = os.getenv("NEURONPEDIA_API_KEY")
client = NeuronpediaAutoInterp(api_key)

# 2. Genera spiegazione
result = client.generate_explanation(
    model_id="gpt2-small",
    layer="8-res-jb",
    index=55,
    explanation_type="oai_token-act-pair",
    explanation_model="gpt-4o-mini"
)

if not result["success"]:
    if result["error"] == "already_exists":
        print("Spiegazione già esistente!")
    elif result["error"] == "no_autointerp_keys":
        print("Configura le API keys su https://neuronpedia.org/settings")

# 3. Recupera la feature per ottenere explanationId
feature = client.get_feature("gpt2-small", "8-res-jb", 55)
explanations = feature["data"]["explanations"]
explanation_id = explanations[0]["id"]

# 4. Calcola lo score
score_result = client.score_explanation(
    explanation_id=explanation_id,
    scorer_model="gpt-4o-mini",
    scorer_type="recall_alt"
)

if score_result["success"]:
    score_value = score_result["data"]["score"]["value"]
    print(f"Score: {score_value}")
```

---

## 📖 Documentazione Completa

Per informazioni dettagliate, consulta:
- **Guida Completa:** `tests/NEURONPEDIA_AUTOINTERP_GUIDE.md`
- **API Docs Ufficiali:** https://www.neuronpedia.org/api-doc
- **GitHub Neuronpedia:** https://github.com/hijohnnylin/neuronpedia

---

## ✨ Checklist Finale

Prima di usare l'API, verifica:

- [ ] NEURONPEDIA_API_KEY configurata nel `.env`
- [ ] OpenAI API key su https://neuronpedia.org/settings
- [ ] OpenRouter API key su https://neuronpedia.org/settings (se vuoi fare scoring)
- [ ] Hai testato con `python tests/neuronpedia_autointerp_example.py`
- [ ] Hai verificato che `modelId`, `layer` e `index` esistano su Neuronpedia

---

## 🎉 Riassunto

**Il tuo JSON originale aveva:**
1. ✗ Virgola mancante dopo `"index": 11298`
2. ✗ API keys non configurate su Neuronpedia

**Ora hai:**
1. ✅ JSON corretto
2. ✅ 3 script pronti all'uso
3. ✅ Documentazione completa
4. ✅ Gestione errori completa
5. ✅ Guida step-by-step

**Per iniziare:**
```bash
# 1. Configura API keys su https://neuronpedia.org/settings
# 2. Esegui il test
python tests/neuronpedia_autointerp_example.py
```

🎯 **Tutto funzionante!**

