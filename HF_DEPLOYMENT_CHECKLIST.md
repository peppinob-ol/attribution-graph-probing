# Hugging Face Spaces - Deployment Checklist

## Pre-Deployment Verification

### Repository Structure
- [x] `README_HF.md` created with HF metadata
- [x] `app_hf.py` entry point in root directory
- [x] `requirements_hf.txt` optimized for HF Spaces
- [x] `.streamlit/config.toml` UI configuration
- [x] `.gitattributes` for Git LFS
- [x] `examples_data/` with Dallas demo files
- [x] `DEPLOYMENT_GUIDE.md` with complete instructions

### Files to Upload to HF Spaces

#### Root Files (Rename as noted)
- [ ] `README_HF.md` → **Rename to `README.md`**
- [ ] `app_hf.py` → Keep name
- [ ] `requirements_hf.txt` → **Rename to `requirements.txt`**
- [ ] `.gitattributes` → Keep name
- [ ] `LICENSE` → Keep name (if exists)

#### Directories
- [ ] `.streamlit/` (with config.toml)
- [ ] `eda/` (entire directory)
- [ ] `scripts/` (entire directory)
- [ ] `examples_data/` (entire directory)
- [ ] `tests/` (optional, recommended)
- [ ] `docs/` (optional, for reference)

#### DO NOT Upload
- [ ] ~~`.env`~~ (API keys - use Secrets instead)
- [ ] ~~`.venv/`~~ (virtual environment)
- [ ] ~~`__pycache__/`~~ (Python cache)
- [ ] ~~`.git/`~~ (git metadata)
- [ ] ~~`output/`~~ (except examples_data/)
- [ ] ~~`.vscode/`~~ (IDE settings)
- [ ] ~~`.idea/`~~ (IDE settings)

---

## Space Configuration

### Basic Settings
- [ ] Space name: `attribution-graph-probing`
- [ ] License: `GPL-3.0`
- [ ] SDK: `Streamlit`
- [ ] Visibility: `Public`
- [ ] Hardware: `CPU Basic (free)` initially

### README.md Metadata (in file header)
```yaml
---
title: Attribution Graph Probing
emoji: 🔬
colorFrom: blue
colorTo: purple
sdk: streamlit
sdk_version: 1.28.0
app_file: app_hf.py
pinned: false
license: gpl-3.0
---
```

### Secrets (Optional - Settings → Repository secrets)
- [ ] `NEURONPEDIA_API_KEY` (for users' own data)
- [ ] `OPENAI_API_KEY` (for users' concept generation)

**Note**: App works without secrets using example data

---

## Build & Deployment

### Initial Deployment
- [ ] Create Space on HF
- [ ] Upload files (web interface or git)
- [ ] Wait for build (~5-10 minutes)
- [ ] Check Logs tab for errors
- [ ] Verify green "Running" status

### Build Checks
- [ ] No dependency conflicts in logs
- [ ] All imports successful
- [ ] No file path errors
- [ ] Streamlit app starts correctly

---

## Post-Deployment Testing

### Homepage (eda/app.py)
- [ ] Page loads without errors
- [ ] Title displays: "🔬 Automating Attribution Graph Analysis"
- [ ] Output folder status shows correctly
- [ ] Links to 3 stage pages work

### Stage 1: Graph Generation
- [ ] Page loads: "00_Graph_Generation.py"
- [ ] Form inputs render correctly
- [ ] API key input field works (if no secrets)
- [ ] Example data can be loaded
- [ ] Visualizations render (scatter plot)

### Stage 2: Probe Prompts  
- [ ] Page loads: "01_Probe_Prompts.py"
- [ ] Graph JSON upload works
- [ ] Example files can be loaded from `examples_data/`
- [ ] Dallas graph JSON loads successfully
- [ ] Concepts table displays
- [ ] Visualizations render (Plotly charts)

### Stage 3: Node Grouping
- [ ] Page loads: "02_Node_Grouping.py"
- [ ] CSV upload works
- [ ] Dallas ENRICHED CSV loads successfully
- [ ] Step 1 executes without errors
- [ ] Step 2 classification works
- [ ] Step 3 naming works
- [ ] Results table displays
- [ ] Summary statistics show

### Example Data Access
- [ ] Dallas JSON files accessible
- [ ] Dallas CSV files accessible
- [ ] Files load without path errors
- [ ] Visualizations work with example data

### Visualizations
- [ ] Plotly charts render (interactive)
- [ ] Matplotlib plots display (if used)
- [ ] Tables display correctly (Pandas DataFrames)
- [ ] Download buttons work (CSV, JSON)

### API Integration (with keys)
- [ ] Neuronpedia API calls work
- [ ] OpenAI API calls work (concept generation)
- [ ] Rate limiting handles correctly
- [ ] Error messages are user-friendly

---

## Performance Verification

### Resource Usage
- [ ] Memory usage < 8GB during normal operation
- [ ] CPU usage reasonable (< 80% sustained)
- [ ] Page load times < 5 seconds
- [ ] No memory leaks (check after 10+ interactions)

### Speed Tests
- [ ] Homepage loads quickly (< 2s)
- [ ] Page navigation smooth (< 1s)
- [ ] File uploads responsive (< 5s for small files)
- [ ] Visualizations render fast (< 3s)

### Concurrent Users (if public)
- [ ] App handles multiple simultaneous sessions
- [ ] No cross-session data leakage
- [ ] Performance degrades gracefully

---

## Documentation Check

### README.md (visible on Space page)
- [ ] HF metadata displays correctly (emoji, colors)
- [ ] Description is clear and accurate
- [ ] Quick start instructions visible
- [ ] API key instructions clear
- [ ] Links work (Neuronpedia, docs)

### In-App Documentation
- [ ] Info boxes display correctly
- [ ] Help text is visible
- [ ] Error messages are helpful
- [ ] Instructions are clear

---

## User Experience

### First-Time User
- [ ] Can understand what the app does
- [ ] Can load and explore example data without API keys
- [ ] Navigation is intuitive
- [ ] Example data demonstrates all features

### Research User (with API keys)
- [ ] Can add API keys easily (secrets or input fields)
- [ ] Can generate new graphs
- [ ] Can analyze their own data
- [ ] Can export results

---

## Maintenance Plan

### Monitoring
- [ ] Check Space Analytics weekly
- [ ] Monitor Logs for errors
- [ ] Track resource usage
- [ ] Note user feedback

### Update Process
- [ ] Test changes locally first
- [ ] Push updates via git or web interface
- [ ] Verify build succeeds
- [ ] Test critical features after update

### Backup
- [ ] Keep local copy of all code
- [ ] Document any HF-specific configurations
- [ ] Export usage analytics periodically

---

## Troubleshooting Reference

### Common Issues

**"Module not found"**
- Solution: Verify all directories uploaded, check import paths

**"Out of memory"**
- Solution: Upgrade to CPU Upgrade tier ($5/month)

**"API key not working"**
- Solution: Check Secrets naming, no extra quotes, restart Space

**"File not found"**
- Solution: Verify examples_data/ uploaded, check relative paths

**"Slow performance"**
- Solution: Consider hardware upgrade, optimize large file loads

---

## Rollback Plan

If deployment fails:

1. Check Logs for specific error
2. Fix locally and test
3. Re-upload fixed files
4. If critical issue: mark Space as private temporarily
5. Document issue and solution

---

## Success Criteria

The deployment is successful when:

- [x] All files uploaded correctly
- [ ] Space builds without errors
- [ ] All 3 stages load and function
- [ ] Example data works perfectly
- [ ] Visualizations render correctly
- [ ] No critical errors in logs
- [ ] Performance is acceptable
- [ ] Documentation is clear
- [ ] Users can accomplish demo workflow

---

## Final Verification

### Quick Test Workflow (5 minutes)

1. **Load Example Data (No API keys needed)**
   - Navigate to Stage 2: Probe Prompts
   - Load: `examples_data/clt-hp-the-capital-of-201020250035-20251020-003525.json`
   - Load: `examples_data/2025-10-21T07-40_export_ENRICHED.csv`
   - Verify visualizations render

2. **Navigate to Stage 3**
   - Load the ENRICHED CSV
   - Run Step 1 → verify token classification
   - Run Step 2 → verify feature classification
   - Run Step 3 → verify naming
   - Check results table displays

3. **Check Downloads**
   - Download CSV from Stage 3
   - Verify file is valid
   - Check JSON downloads work

If all steps pass: **Deployment Successful** ✅

---

## Deployment Status

- **Date**: ___ / ___ / 2025
- **Space URL**: https://huggingface.co/spaces/YOUR_USERNAME/attribution-graph-probing
- **Status**: ⬜ Not Started | ⬜ In Progress | ⬜ Testing | ⬜ Live
- **Deployed By**: _______________
- **Last Verified**: ___ / ___ / 2025

---

**Notes**:
- This is a living document - update as you deploy and discover issues
- Keep this checklist for reference during updates
- Share with collaborators for maintenance

---

**Version**: 1.0  
**Last Updated**: November 2025  
**For Project**: Attribution Graph Probing v2.0.0-clean

