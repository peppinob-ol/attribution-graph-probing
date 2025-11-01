# Deployment Guide - Hugging Face Spaces

Complete step-by-step guide for deploying Attribution Graph Probing on Hugging Face Spaces.

---

## Prerequisites

1. **Hugging Face Account**: Create one at [huggingface.co](https://huggingface.co)
2. **Git & Git LFS**: Install from [git-scm.com](https://git-scm.com) and [git-lfs.github.com](https://git-lfs.github.com)
3. **API Keys** (optional, for your own data):
   - Neuronpedia API Key
   - OpenAI API Key

---

## Deployment Methods

### Method 1: Direct Upload (Easiest)

1. **Create Space**
   - Go to [huggingface.co/spaces](https://huggingface.co/spaces)
   - Click "Create new Space"
   - Configure:
     - Name: `attribution-graph-probing`
     - License: GPL-3.0
     - SDK: **Streamlit**
     - Visibility: Public
     - Hardware: CPU Basic (free)

2. **Upload Files via Web Interface**
   - Click "Files" tab
   - Upload ALL files except:
     - `.git/`
     - `__pycache__/`
     - `.venv/`
     - `output/` (except `examples_data/`)
     - `.env`

3. **Critical Files to Upload**
   ```
   README_HF.md (rename to README.md in Space)
   app_hf.py
   requirements_hf.txt (rename to requirements.txt)
   .streamlit/config.toml
   .gitattributes
   eda/ (entire directory)
   scripts/ (entire directory)
   examples_data/ (entire directory)
   tests/ (optional)
   ```

4. **Wait for Build**
   - HF will automatically detect and build
   - Check "Logs" tab for progress
   - Build time: ~5-10 minutes

5. **Test the App**
   - Once running, click the app URL
   - Navigate through the 3 stages
   - Load Dallas example data to verify

---

### Method 2: Git Push (Recommended for Updates)

1. **Create Space on HF**
   - Same as Method 1, step 1

2. **Clone the Space Repository**
   ```bash
   git clone https://huggingface.co/spaces/YOUR_USERNAME/attribution-graph-probing
   cd attribution-graph-probing
   ```

3. **Install Git LFS**
   ```bash
   git lfs install
   ```

4. **Copy Files from Your Local Repo**
   ```bash
   # From your project directory
   # Copy files to the cloned Space directory
   cp -r eda/ ../attribution-graph-probing/
   cp -r scripts/ ../attribution-graph-probing/
   cp -r examples_data/ ../attribution-graph-probing/
   cp -r tests/ ../attribution-graph-probing/
   
   # Copy root files
   cp app_hf.py ../attribution-graph-probing/
   cp requirements_hf.txt ../attribution-graph-probing/requirements.txt
   cp README_HF.md ../attribution-graph-probing/README.md
   cp .gitattributes ../attribution-graph-probing/
   cp -r .streamlit/ ../attribution-graph-probing/
   ```

5. **Commit and Push**
   ```bash
   cd ../attribution-graph-probing
   git add .
   git commit -m "Initial deployment"
   git push
   ```

6. **Monitor Build**
   - Go to your Space page
   - Check "Logs" tab
   - Wait for build to complete

---

### Method 3: GitHub Sync (Advanced)

1. **Create Space on HF**
   - Same as Method 1, step 1

2. **Connect GitHub Repository**
   - In Space Settings → "Repository"
   - Click "Link external repository"
   - Enter your GitHub repo URL
   - Select branch: `main` or `hf-spaces` (create dedicated branch)

3. **Auto-sync**
   - HF will automatically sync on every push to GitHub
   - This is ideal for continuous deployment

---

## Configuration

### API Keys (Secrets)

**For Users to Use Their Own Data:**

1. Go to Space Settings → "Repository secrets"
2. Add variables:
   ```
   NEURONPEDIA_API_KEY = your-neuronpedia-key
   OPENAI_API_KEY = your-openai-key
   ```

**Note**: These are optional. The app works with example data without keys.

### Hardware Upgrade (Optional)

If the app is slow or crashes:

1. Go to Space Settings → "Hardware"
2. Upgrade options:
   - **CPU Upgrade** (4 vCPU, 16GB RAM) - ~$5/month
   - **T4 Small** (GPU) - ~$60/month (not needed for this app)

For this app, **CPU Upgrade** is sufficient if needed.

---

## File Structure for HF Spaces

```
attribution-graph-probing/
├── README.md                    # HF metadata + documentation
├── app_hf.py                    # Entry point (points to eda/app.py)
├── requirements.txt             # Python dependencies
├── .streamlit/
│   └── config.toml              # Streamlit UI config
├── .gitattributes               # Git LFS config
├── eda/                         # Main Streamlit app
│   ├── app.py
│   ├── pages/
│   │   ├── 00_Graph_Generation.py
│   │   ├── 01_Probe_Prompts.py
│   │   └── 02_Node_Grouping.py
│   ├── utils/
│   └── README.md
├── scripts/                     # Backend scripts
│   ├── 00_neuronpedia_graph_generation.py
│   ├── 01_probe_prompts.py
│   ├── 02_node_grouping.py
│   └── causal_utils.py
├── examples_data/               # Demo data (Dallas)
│   ├── README.md
│   ├── *.json
│   └── *.csv
└── tests/                       # Optional: test suite
```

---

## Verification Checklist

After deployment, verify:

- [ ] Space is running (green status)
- [ ] No errors in Logs tab
- [ ] Homepage loads correctly
- [ ] Sidebar navigation works (3 stage pages)
- [ ] Dallas example files are accessible
- [ ] File upload works in each stage
- [ ] Visualizations render (Plotly charts)
- [ ] API key input fields work (if no secrets set)

---

## Troubleshooting

### Build Fails

**Error: "Could not find a version that satisfies the requirement..."**

Solution: Check `requirements.txt` versions, ensure compatibility

**Error: "Out of memory during build"**

Solution: Remove unnecessary dependencies (jupyter, notebook) from requirements

### App Crashes on Load

**Error: "Module not found"**

Solution: Verify all directories (eda/, scripts/) are uploaded

**Error: "FileNotFoundError"**

Solution: Check paths in `app_hf.py`, ensure they're relative to project root

### Slow Performance

Solution: Upgrade to CPU Upgrade hardware tier ($5/month)

### API Keys Not Working

Check:
1. Secrets are named exactly: `NEURONPEDIA_API_KEY`, `OPENAI_API_KEY`
2. No extra quotes in the secret values
3. Restart the Space after adding secrets (Settings → "Factory reboot")

---

## Maintenance

### Update the App

**Via Web Interface:**
1. Go to Files tab
2. Upload modified files
3. Space rebuilds automatically

**Via Git:**
```bash
cd attribution-graph-probing
git pull  # Get latest from HF
# Make changes locally
git add .
git commit -m "Update: description"
git push
```

### Monitor Usage

- **Analytics**: Space Settings → "Analytics" (views, sessions)
- **Logs**: Check for errors or warnings
- **Hardware**: Monitor CPU/RAM usage

---

## Compatibility

### Other Platforms

The repository structure remains compatible with:

- **Streamlit Cloud**: Use original `requirements.txt`, run `streamlit run eda/app.py`
- **Local Development**: Same as always
- **Docker**: Create Dockerfile based on `requirements_hf.txt`
- **Heroku**: Add `Procfile` with Streamlit command

### Changes Made for HF Spaces

1. **README_HF.md** → Contains HF metadata (yaml header)
2. **app_hf.py** → Entry point in root (HF requirement)
3. **requirements_hf.txt** → Optimized dependencies
4. **.streamlit/config.toml** → UI theme and settings
5. **.gitattributes** → Git LFS for large files
6. **examples_data/** → Demo data in accessible location

Original files remain unchanged:
- `eda/app.py` - Works as before
- `scripts/*.py` - Backend unchanged
- `readme.md` - Local documentation
- `requirements.txt` - Local development

---

## Cost Estimate

**Free Tier (CPU Basic):**
- RAM: 16GB
- CPU: 2 vCPU
- Storage: 50GB
- Cost: **FREE** ✅

**Recommended for Production (CPU Upgrade):**
- RAM: 16GB (shared)
- CPU: 4 vCPU
- Storage: 50GB
- Cost: **~$5/month**

This app does NOT need GPU.

---

## Support

**HF Spaces Documentation:**
- https://huggingface.co/docs/hub/spaces

**Project Documentation:**
- Local: `readme.md`, `eda/README.md`
- Space: README.md (visible on Space page)

**Community:**
- HF Discord: https://hf.co/join/discord
- HF Forums: https://discuss.huggingface.co

---

## Next Steps

After deployment:

1. ✅ Verify all features work
2. 📣 Share the Space URL with collaborators
3. 📊 Monitor usage and performance
4. 🔄 Iterate based on feedback
5. 📈 Consider upgrading hardware if needed

---

**Deployment Date**: November 2025  
**Version**: 2.0.0-clean  
**Platform**: Hugging Face Spaces  
**Status**: Ready for Production ✅

