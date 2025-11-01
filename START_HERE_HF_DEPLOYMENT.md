# 🚀 START HERE - Deploy to Hugging Face Spaces

**Quick reference guide for deploying your app**

---

## ✅ READY TO DEPLOY

Everything is prepared! Your repository is now ready for Hugging Face Spaces deployment.

---

## 📦 What Was Created

### 10 New Files for HF Spaces

| File | Purpose | Size |
|------|---------|------|
| `README_HF.md` | Space page docs (with HF metadata) | 1.8 KB |
| `app_hf.py` | Entry point for HF | 0.5 KB |
| `requirements_hf.txt` | Optimized dependencies | 0.7 KB |
| `.streamlit/config.toml` | UI configuration | 0.4 KB |
| `.gitattributes` | Git LFS setup | 0.5 KB |
| `DEPLOYMENT_GUIDE.md` | Complete deployment guide | 9.5 KB |
| `HF_DEPLOYMENT_CHECKLIST.md` | Verification checklist | 8.2 KB |
| `COMPATIBILITY_NOTES.md` | Platform compatibility | 7.8 KB |
| `QUICK_DEPLOY_HF.md` | Fast deployment guide | 4.2 KB |
| `HF_DEPLOYMENT_SUMMARY.md` | Detailed summary | 6.5 KB |

### Dallas Example Data

- ✅ Copied to `examples_data/` (11 files, ~15 MB)
- ✅ Includes: Graph JSON, activations, CSVs, all stages
- ✅ Allows demo without API keys

---

## 🎯 Next Steps (Choose One)

### Option 1: FAST DEPLOYMENT (10 minutes) ⚡

**Perfect for**: First-time deployment, getting started quickly

**Follow**: `QUICK_DEPLOY_HF.md`

Steps:
1. Create Space on HF (2 min)
2. Upload files via web (3 min)
3. Wait for build (5 min)
4. Test with Dallas example (2 min)

**Total time**: ~10-15 minutes

---

### Option 2: DETAILED DEPLOYMENT (20 minutes) 📚

**Perfect for**: Understanding everything, Git workflow

**Follow**: `DEPLOYMENT_GUIDE.md`

Choose method:
- Method 1: Web upload (easiest)
- Method 2: Git push (recommended for updates)
- Method 3: GitHub sync (advanced)

**Total time**: ~20-30 minutes

---

### Option 3: CHECKLIST-DRIVEN (30 minutes) ✓

**Perfect for**: Systematic verification, production deployment

**Follow**: `HF_DEPLOYMENT_CHECKLIST.md`

- Pre-deployment verification
- Upload with checklist
- Post-deployment testing
- Success criteria validation

**Total time**: ~30 minutes

---

## 📋 WHAT TO UPLOAD

### Essential Files

```
attribution-graph-probing/
├── README.md                    ← Rename from README_HF.md
├── app_hf.py                    ← Upload as-is
├── requirements.txt             ← Rename from requirements_hf.txt
├── .streamlit/config.toml       ← Upload in .streamlit/ folder
├── .gitattributes               ← Upload as-is
├── eda/                         ← Entire directory
├── scripts/                     ← Entire directory
├── examples_data/               ← Entire directory (Dallas)
└── LICENSE                      ← Upload as-is
```

### Do NOT Upload

❌ `.env` - Use Secrets instead  
❌ `.venv/`, `__pycache__/` - Build artifacts  
❌ `output/` - Working files (except examples_data)  
❌ `.git/`, `.vscode/`, `.idea/` - Dev files

---

## ⚙️ Space Configuration

When creating your Space:

```
Name: attribution-graph-probing
License: GPL-3.0
SDK: Streamlit
Hardware: CPU Basic (free)
Visibility: Public
```

---

## 🔑 API Keys (Optional)

Your app works **without API keys** using Dallas example data.

For users to analyze their own data:

**Add in Space Settings → Secrets:**
```
NEURONPEDIA_API_KEY = your-key-here
OPENAI_API_KEY = your-key-here
```

---

## ✅ Compatibility Guaranteed

**Your original files are UNCHANGED:**
- ✅ `eda/app.py` - Works as before
- ✅ `requirements.txt` - Original preserved
- ✅ `readme.md` - Local docs intact
- ✅ All scripts - Unchanged

**You can still:**
- ✅ Run locally: `streamlit run eda/app.py`
- ✅ Deploy to Streamlit Cloud (original structure)
- ✅ Use Docker, Heroku, etc.

**See**: `COMPATIBILITY_NOTES.md` for details

---

## 🎬 Quick Start Commands

### Test Locally First (Recommended)

```bash
# Test original structure
streamlit run eda/app.py

# Test HF structure
streamlit run app_hf.py
```

Both should work identically!

### Deploy to HF (Git Method)

```bash
# Clone your new Space
git clone https://huggingface.co/spaces/YOUR_USERNAME/attribution-graph-probing
cd attribution-graph-probing

# Copy files (adjust paths as needed)
cp ../circuit_tracer-prompt_rover/README_HF.md README.md
cp ../circuit_tracer-prompt_rover/app_hf.py .
cp ../circuit_tracer-prompt_rover/requirements_hf.txt requirements.txt
cp -r ../circuit_tracer-prompt_rover/.streamlit .
cp -r ../circuit_tracer-prompt_rover/eda .
cp -r ../circuit_tracer-prompt_rover/scripts .
cp -r ../circuit_tracer-prompt_rover/examples_data .

# Commit and push
git add .
git commit -m "Initial deployment"
git push
```

---

## 📊 Resource Estimates

### Free Tier (CPU Basic)
- **RAM**: 16GB
- **CPU**: 2 vCPU  
- **Storage**: 50GB
- **Cost**: **FREE** ✅
- **Performance**: Good for most usage

### If Needed (CPU Upgrade)
- **RAM**: 16GB
- **CPU**: 4 vCPU
- **Cost**: ~**$5/month**
- **When**: Heavy concurrent usage

**GPU NOT needed** for this app

---

## 📚 Documentation Map

Choose based on your need:

| When You Need... | Read This |
|------------------|-----------|
| **Deploy in 10 min** | `QUICK_DEPLOY_HF.md` |
| **Understand everything** | `DEPLOYMENT_GUIDE.md` |
| **Verify step-by-step** | `HF_DEPLOYMENT_CHECKLIST.md` |
| **Multi-platform info** | `COMPATIBILITY_NOTES.md` |
| **Overview of changes** | `HF_DEPLOYMENT_SUMMARY.md` |
| **Quick reference** | This file! |

---

## 🆘 Quick Troubleshooting

**Build fails?**  
→ Check Logs tab, verify all folders uploaded

**Module not found?**  
→ Verify `eda/` and `scripts/` directories uploaded

**Example data doesn't load?**  
→ Check `examples_data/` uploaded completely

**Slow or crashes?**  
→ Check Logs, consider CPU Upgrade ($5/month)

**API keys not working?**  
→ Check Secrets naming exactly: `NEURONPEDIA_API_KEY`, `OPENAI_API_KEY`

---

## ✨ What Makes This Ready

1. ✅ **All files created** (10 new deployment files)
2. ✅ **Example data prepared** (Dallas complete dataset)
3. ✅ **Compatibility maintained** (original structure unchanged)
4. ✅ **Documentation complete** (5 detailed guides)
5. ✅ **Tested structure** (app_hf.py tested)
6. ✅ **Multi-platform ready** (works everywhere)

---

## 🎯 Recommended Path

For first-time deployment:

1. **Read**: `QUICK_DEPLOY_HF.md` (5 min read)
2. **Test locally**: `streamlit run app_hf.py` (2 min)
3. **Create Space** on HF (2 min)
4. **Upload files** via web interface (3 min)
   - Remember to rename:
     - `README_HF.md` → `README.md`
     - `requirements_hf.txt` → `requirements.txt`
5. **Wait for build** (5-10 min)
6. **Test** with Dallas example (2 min)
7. **Share** your Space URL! 🎉

**Total**: ~20-25 minutes

---

## 🎉 You're Ready!

Everything is set up for a smooth deployment to Hugging Face Spaces.

Your app will:
- ✅ Work with the Dallas example (no API keys needed)
- ✅ Allow users to add their own API keys
- ✅ Run on free tier (with upgrade option)
- ✅ Maintain compatibility with local development
- ✅ Be accessible to the research community

---

## 📍 Where to Begin

👉 **Start here**: Open `QUICK_DEPLOY_HF.md` and follow the steps!

Good luck with your deployment! 🚀

---

**Project**: Attribution Graph Probing v2.0.0-clean  
**Platform**: Hugging Face Spaces  
**Status**: ✅ READY TO DEPLOY  
**Estimated Time**: 20-30 minutes  
**Cost**: FREE (CPU Basic tier)

