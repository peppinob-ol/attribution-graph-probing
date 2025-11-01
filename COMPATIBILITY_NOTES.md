# Platform Compatibility Notes

This document explains how the repository structure remains compatible with multiple deployment platforms after HF Spaces preparation.

---

## Compatibility Matrix

| Platform | Compatible | Entry Point | Requirements File | Notes |
|----------|-----------|-------------|-------------------|-------|
| **HF Spaces** | ✅ Yes | `app_hf.py` | `requirements_hf.txt` → rename to `requirements.txt` | Primary target |
| **Streamlit Cloud** | ✅ Yes | `eda/app.py` | `requirements.txt` | Original structure |
| **Local Development** | ✅ Yes | `eda/app.py` | `requirements.txt` | Unchanged |
| **Docker** | ✅ Yes | `app_hf.py` or `eda/app.py` | Either requirements file | Flexible |
| **Heroku** | ✅ Yes | `app_hf.py` | `requirements_hf.txt` | Need `Procfile` |
| **AWS/GCP** | ✅ Yes | `app_hf.py` | `requirements_hf.txt` | Standard deployment |

---

## Files Added for HF Spaces

### 1. README_HF.md
- **Purpose**: HF Spaces requires README.md with metadata
- **Compatibility**: Does NOT affect other platforms
- **Usage**: Rename to `README.md` when deploying to HF
- **Original**: `readme.md` remains unchanged for local docs

### 2. app_hf.py
- **Purpose**: Entry point in root directory (HF requirement)
- **Compatibility**: Optional for other platforms
- **Content**: Simply imports and runs `eda/app.py`
- **Original**: `eda/app.py` unchanged and fully functional

### 3. requirements_hf.txt
- **Purpose**: Optimized dependencies for HF Spaces
- **Compatibility**: Can be used on any platform
- **Differences from requirements.txt**:
  - Removed: jupyter, notebook (not needed for deployment)
  - Removed: ipython (not needed for web app)
  - Added: Version constraints for stability
  - Same: All core dependencies (streamlit, plotly, torch, etc.)
- **Original**: `requirements.txt` remains unchanged

### 4. .streamlit/config.toml
- **Purpose**: Streamlit UI configuration
- **Compatibility**: Works on ALL Streamlit deployments
- **Benefits**: Consistent theme, better UX
- **Original**: No conflict (optional file)

### 5. .gitattributes
- **Purpose**: Git LFS configuration for large files
- **Compatibility**: Standard Git feature, works everywhere
- **Benefits**: Better handling of .pt, .pkl files
- **Original**: No conflict

### 6. examples_data/
- **Purpose**: Demo data in accessible location
- **Compatibility**: Just a directory, works everywhere
- **Benefits**: Clear separation from working output/
- **Original**: output/ remains unchanged for actual work

---

## Deployment Instructions by Platform

### Hugging Face Spaces

```bash
# Files to use:
- README_HF.md → rename to README.md
- app_hf.py
- requirements_hf.txt → rename to requirements.txt
- .streamlit/config.toml
- .gitattributes

# Command: None needed, HF auto-detects Streamlit
```

**See**: `DEPLOYMENT_GUIDE.md` for complete instructions

---

### Streamlit Cloud

```bash
# Files to use:
- readme.md (existing)
- eda/app.py
- requirements.txt (existing)

# In Streamlit Cloud dashboard:
- Main file path: eda/app.py
- Python version: 3.9+

# .env secrets:
- Add NEURONPEDIA_API_KEY
- Add OPENAI_API_KEY
```

**No changes needed** - works as before!

---

### Local Development

```bash
# Setup (Windows)
.\setup_venv.ps1

# Or manual:
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt

# Run:
streamlit run eda/app.py

# Files used:
- requirements.txt (existing)
- .env (for API keys)
- eda/app.py (existing)
```

**No changes needed** - works as before!

---

### Docker

**Option 1: Using HF-optimized files**

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements_hf.txt requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "app_hf.py", "--server.port=8501"]
```

**Option 2: Using original structure**

```dockerfile
FROM python:3.9-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8501

CMD ["streamlit", "run", "eda/app.py", "--server.port=8501"]
```

Both work! Choose based on preference.

---

### Heroku

1. Create `Procfile`:
```
web: streamlit run app_hf.py --server.port=$PORT --server.address=0.0.0.0
```

2. Use `requirements_hf.txt`:
```bash
cp requirements_hf.txt requirements.txt
```

3. Deploy:
```bash
git add .
git commit -m "Deploy to Heroku"
git push heroku main
```

4. Set environment variables:
```bash
heroku config:set NEURONPEDIA_API_KEY=your-key
heroku config:set OPENAI_API_KEY=your-key
```

---

## Code Compatibility

### Import Structure

**Original code** (eda/app.py, pages/*.py):
```python
import sys
from pathlib import Path

parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))
```

This works on **all platforms** because:
- Uses relative paths
- Dynamically finds parent directory
- No hardcoded paths

**HF entry point** (app_hf.py):
```python
import sys
from pathlib import Path

project_root = Path(__file__).parent
if str(project_root) not in sys.path:
    sys.path.insert(0, str(project_root))

import os
os.chdir(project_root)

from eda import app
```

This:
- Sets up paths correctly for root-level execution
- Imports original app without modification
- Works on all platforms

---

## Environment Variables

### .env file (Local Development)

```env
NEURONPEDIA_API_KEY='your-key-here'
OPENAI_API_KEY='your-key-here'
```

### HF Spaces Secrets

Settings → Repository secrets:
```
NEURONPEDIA_API_KEY = your-key-here
OPENAI_API_KEY = your-key-here
```

### Streamlit Cloud Secrets

Settings → Secrets:
```toml
NEURONPEDIA_API_KEY = "your-key-here"
OPENAI_API_KEY = "your-key-here"
```

### Code reads all three formats

```python
def load_api_key():
    from dotenv import load_dotenv
    
    # Load .env if exists (local)
    env_file = parent_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    
    # Read from environment (HF, Streamlit Cloud, Heroku)
    return os.environ.get("NEURONPEDIA_API_KEY", "")
```

This works on **all platforms**! ✅

---

## Testing Across Platforms

### Test Locally Before Deploying

1. **Test with original structure**:
```bash
streamlit run eda/app.py
```

2. **Test with HF structure**:
```bash
streamlit run app_hf.py
```

3. **Test with HF requirements**:
```bash
pip install -r requirements_hf.txt
streamlit run app_hf.py
```

All should work identically!

---

## Migration Path

### From Local to HF Spaces

1. ✅ Code unchanged (eda/, scripts/)
2. ✅ Add HF files (README_HF.md, app_hf.py, etc.)
3. ✅ Upload to HF
4. ✅ Set Secrets
5. ✅ Deploy

### From HF Spaces to Streamlit Cloud

1. ✅ Use original files (readme.md, requirements.txt)
2. ✅ Deploy with eda/app.py as main file
3. ✅ Set Secrets
4. ✅ Deploy

### From Either to Docker

1. ✅ Choose structure (HF or original)
2. ✅ Create Dockerfile
3. ✅ Build and run

---

## Backup Strategy

Keep **both structures** in the repository:

```
project/
├── readme.md              # Original local docs
├── README_HF.md           # HF Spaces docs (with metadata)
├── requirements.txt       # Original (full)
├── requirements_hf.txt    # HF optimized
├── app_hf.py              # HF entry point
├── eda/app.py             # Original entry point
└── ...
```

This allows:
- Deploying to HF without breaking local dev
- Deploying to Streamlit Cloud without HF files
- Switching between platforms easily
- Maintaining compatibility with all platforms

---

## Summary

### ✅ What Changed
1. Added HF-specific files (README_HF.md, app_hf.py, requirements_hf.txt)
2. Added configuration files (.streamlit/config.toml, .gitattributes)
3. Added examples_data/ directory for demo

### ✅ What Stayed the Same
1. All original code (eda/, scripts/, tests/)
2. Original requirements.txt
3. Original documentation (readme.md, eda/README.md)
4. Original entry point (eda/app.py)

### ✅ Compatibility Result
- **Local Development**: ✅ Unchanged
- **Streamlit Cloud**: ✅ Unchanged
- **HF Spaces**: ✅ Fully supported
- **Docker**: ✅ Flexible (both structures work)
- **Other Platforms**: ✅ Standard Python app

---

**Conclusion**: The repository is now **multi-platform ready** while maintaining **full backward compatibility**.

---

**Last Updated**: November 2025  
**Project Version**: 2.0.0-clean  
**Compatibility**: All major platforms ✅

