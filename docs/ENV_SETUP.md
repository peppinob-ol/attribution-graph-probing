# Configurazione Environment Variables (.env)

## Setup Iniziale

Crea un file `.env` nella root del progetto con le tue API keys:

```bash
# Crea il file .env
touch .env  # Linux/Mac
# oppure
New-Item .env  # Windows PowerShell
```

## Contenuto File .env

```env
# Neuronpedia API Key (obbligatoria per Probe Prompts)
NEURONPEDIA_API_KEY=your-neuronpedia-api-key-here

# OpenAI API Key (opzionale, solo per generazione automatica concepts)
OPENAI_API_KEY=your-openai-api-key-here
```

## Come Ottenere le API Keys

### Neuronpedia API Key

1. Vai su https://www.neuronpedia.org
2. Fai login o registrati
3. Naviga a **Settings** → **API Keys**
4. Clicca su "Create New Key"
5. Copia la key generata

### OpenAI API Key (Opzionale)

1. Vai su https://platform.openai.com/api-keys
2. Fai login
3. Clicca su "Create new secret key"
4. Copia la key (non sarà più visibile dopo!)

## Verifica Configurazione

### Da Streamlit

1. Avvia: `streamlit run eda/app.py`
2. Naviga a "01_Probe_Prompts"
3. Nella sidebar dovresti vedere:
   - ✅ **API Key Neuronpedia caricata**
   - ✅ **API Key OpenAI caricata** (se configurata)

### Da Python

```python
import os
from dotenv import load_dotenv

load_dotenv()

neuronpedia_key = os.environ.get("NEURONPEDIA_API_KEY")
openai_key = os.environ.get("OPENAI_API_KEY")

print(f"Neuronpedia: {'✅' if neuronpedia_key else '❌'}")
print(f"OpenAI: {'✅' if openai_key else '❌'}")
```

## Troubleshooting

### API Key non viene caricata

**Causa 1**: File `.env` non nella root corretta

```bash
# Verifica posizione
pwd  # Deve essere: .../circuit_tracer-prompt_rover/
ls -la | grep .env  # Deve mostrare .env
```

**Causa 2**: Formato errato nel file

```bash
# ❌ ERRATO (con spazi o quotes)
NEURONPEDIA_API_KEY = "your-key"

# ✅ CORRETTO (senza spazi, senza quotes)
NEURONPEDIA_API_KEY=your-key
```

**Causa 3**: Caratteri invisibili

```bash
# Rimuovi caratteri nascosti
dos2unix .env  # Linux/Mac
# oppure
notepad .env  # Windows, salva come UTF-8 senza BOM
```

### Streamlit non trova le keys

**Soluzione**: Riavvia completamente Streamlit

```bash
# 1. Ferma Streamlit (Ctrl+C)
# 2. Verifica .env
cat .env  # Linux/Mac
type .env  # Windows

# 3. Riavvia
streamlit run eda/app.py
```

### Keys come Environment Variables (alternativa a .env)

Se preferisci non usare `.env`, imposta direttamente:

**Linux/Mac (Bash/Zsh)**:
```bash
export NEURONPEDIA_API_KEY="your-key"
export OPENAI_API_KEY="your-key"

# Per renderlo permanente, aggiungi a ~/.bashrc o ~/.zshrc
echo 'export NEURONPEDIA_API_KEY="your-key"' >> ~/.bashrc
```

**Windows (PowerShell)**:
```powershell
$env:NEURONPEDIA_API_KEY="your-key"
$env:OPENAI_API_KEY="your-key"

# Per renderlo permanente (System)
[System.Environment]::SetEnvironmentVariable('NEURONPEDIA_API_KEY', 'your-key', 'User')
```

**Windows (CMD)**:
```cmd
set NEURONPEDIA_API_KEY=your-key
set OPENAI_API_KEY=your-key

# Per renderlo permanente
setx NEURONPEDIA_API_KEY "your-key"
```

## Security Best Practices

### ⚠️ NON committare .env

Il file `.env` è già in `.gitignore`, ma verifica:

```bash
# Verifica che .env sia ignorato
git status  # NON deve mostrare .env

# Se appare, aggiungilo a .gitignore
echo ".env" >> .gitignore
```

### ⚠️ NON condividere le keys

- Non inviare `.env` via email/chat
- Non fare screenshot con keys visibili
- Non pubblicare keys in issues/forum

### ✅ Rotazione periodica

- Rigenera le keys ogni 3-6 mesi
- Revoca keys vecchie su Neuronpedia/OpenAI
- Aggiorna `.env` con nuove keys

### ✅ Keys separate per sviluppo/produzione

```env
# .env.development
NEURONPEDIA_API_KEY=dev-key-here
OPENAI_API_KEY=dev-key-here

# .env.production
NEURONPEDIA_API_KEY=prod-key-here
OPENAI_API_KEY=prod-key-here
```

Carica il file appropriato:
```python
from dotenv import load_dotenv
load_dotenv('.env.development')  # o .env.production
```

## Riferimenti

- **python-dotenv docs**: https://pypi.org/project/python-dotenv/
- **Neuronpedia API**: https://www.neuronpedia.org/api-doc
- **OpenAI API**: https://platform.openai.com/docs

---

**Nota**: Il file `.env` contiene informazioni sensibili. Trattalo come una password!







