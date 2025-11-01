# Quick Deploy to Hugging Face Spaces

**Fast track guide - 10 minutes to deployment**

---

## Step 1: Create Space (2 min)

1. Go to https://huggingface.co/spaces
2. Click **"Create new Space"**
3. Configure:
   - Owner: YOUR_USERNAME
   - Space name: `attribution-graph-probing`
   - License: `GPL-3.0`
   - Select SDK: **Streamlit**
   - Space hardware: **CPU basic** (free)
   - Visibility: **Public**
4. Click **"Create Space"**

---

## Step 2: Prepare Files (3 min)

### Files to Upload

From your local project, prepare these files:

**Root level:**
- `README_HF.md` (rename to `README.md` when uploading)
- `app_hf.py`
- `requirements_hf.txt` (rename to `requirements.txt` when uploading)
- `LICENSE`

**Directories:**
- `.streamlit/` (entire folder with config.toml)
- `eda/` (entire folder)
- `scripts/` (entire folder)
- `examples_data/` (entire folder with Dallas files)

**Optional but recommended:**
- `tests/`
- `.gitattributes`

**DO NOT upload:**
- `.env` (use Secrets instead)
- `.venv/`, `__pycache__/`, `.git/`
- `output/` (except examples_data)

---

## Step 3: Upload via Web Interface (3 min)

**Method A: Drag and Drop**

1. In your Space, click **"Files and versions"** tab
2. Click **"Add file"** → **"Upload files"**
3. Drag all prepared files and folders
4. Important: Rename before committing:
   - `README_HF.md` → `README.md`
   - `requirements_hf.txt` → `requirements.txt`
5. Add commit message: "Initial deployment"
6. Click **"Commit to main"**

**Method B: Git Clone** (if familiar with git)

```bash
# Clone your space
git clone https://huggingface.co/spaces/YOUR_USERNAME/attribution-graph-probing
cd attribution-graph-probing

# Copy files from your project
# (adjust paths as needed)
cp ../circuit_tracer-prompt_rover/app_hf.py .
cp ../circuit_tracer-prompt_rover/README_HF.md README.md
cp ../circuit_tracer-prompt_rover/requirements_hf.txt requirements.txt
cp -r ../circuit_tracer-prompt_rover/.streamlit .
cp -r ../circuit_tracer-prompt_rover/eda .
cp -r ../circuit_tracer-prompt_rover/scripts .
cp -r ../circuit_tracer-prompt_rover/examples_data .
cp ../circuit_tracer-prompt_rover/LICENSE .

# Commit and push
git add .
git commit -m "Initial deployment"
git push
```

---

## Step 4: Wait for Build (5 min)

1. Go to your Space page
2. Click **"Logs"** tab (or "App" tab shows build progress)
3. Wait for build to complete (~5 minutes first time)
4. Watch for:
   - ✅ "Streamlit app started"
   - ✅ "Your app is running at..."
5. Status should show: 🟢 **Running**

---

## Step 5: Test the App (2 min)

1. Click **"App"** tab
2. Verify homepage loads
3. Navigate to **"01_Probe_Prompts"** page
4. Test loading Dallas example:
   - Upload or select `examples_data/clt-hp-the-capital-of-201020250035-20251020-003525.json`
   - Upload or select `examples_data/2025-10-21T07-40_export_ENRICHED.csv`
   - Verify visualizations appear
5. Navigate to **"02_Node_Grouping"** page
6. Load the ENRICHED CSV and run Step 1

If all loads without errors: **Success!** ✅

---

## Optional: Add API Keys (2 min)

For users to use their own data:

1. Go to **Settings** → **Repository secrets**
2. Click **"New secret"**
3. Add:
   - Name: `NEURONPEDIA_API_KEY`
   - Value: `your-actual-key-here`
   - Click **"Save"**
4. Repeat for:
   - Name: `OPENAI_API_KEY`
   - Value: `your-actual-key-here`
5. **Restart Space**: Settings → Factory reboot

---

## Troubleshooting

### Build fails with "File not found"

- Check that all folders are uploaded: `eda/`, `scripts/`, `examples_data/`
- Check that you renamed `README_HF.md` to `README.md`
- Check that you renamed `requirements_hf.txt` to `requirements.txt`

### "Module not found" error

- Verify `eda/` directory is complete with all `.py` files
- Verify `scripts/` directory is uploaded
- Check Logs tab for specific missing module

### App is slow or crashes

- Check Logs for memory errors
- Consider upgrading to **CPU Upgrade** (Settings → Hardware)
- Cost: ~$5/month for 4 vCPU, 16GB RAM

### Example data doesn't load

- Verify `examples_data/` folder is uploaded completely
- Check all Dallas files are present (JSON and CSV files)
- Try restarting the Space (Settings → Factory reboot)

---

## What to Share

Once deployed, share this URL:

```
https://huggingface.co/spaces/YOUR_USERNAME/attribution-graph-probing
```

The Space page will show:
- Your README with project description
- Interactive app in "App" tab
- Files in "Files" tab
- Usage analytics in Space settings

---

## Next Steps

After successful deployment:

1. ✅ Share with collaborators
2. 📊 Monitor usage (Settings → Analytics)
3. 🔧 Customize README.md with your info
4. 📈 Consider hardware upgrade if needed
5. 🔄 Push updates as you improve the app

---

## Full Documentation

For complete details, see:
- `DEPLOYMENT_GUIDE.md` - Comprehensive guide
- `HF_DEPLOYMENT_CHECKLIST.md` - Verification checklist
- `COMPATIBILITY_NOTES.md` - Platform compatibility

---

**Time to deploy**: ~10-15 minutes  
**Cost**: FREE (CPU basic tier)  
**Status**: Production ready ✅

Good luck! 🚀

