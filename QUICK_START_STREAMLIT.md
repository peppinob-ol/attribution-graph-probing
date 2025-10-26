# Quick Start - Streamlit App

**Attribution Graph Probing - Pipeline v2.0.0-clean**

---

## 🚀 Quick Launch

### Windows PowerShell
```powershell
.\start_streamlit.ps1
```

### Linux/Mac
```bash
source .venv/bin/activate
streamlit run eda/app.py
```

### Alternative (any OS)
```bash
cd eda
streamlit run app.py
```

The app will automatically open at `http://localhost:8501`

---

## 📊 Application Structure

### Homepage

Main dashboard with:
- **Quick links** to the 3 pipeline stages
- **Output folder status** (JSON, CSV, PT files)
- **Project info** and version

### Stage 1: Graph Generation

**Page:** `00_Graph_Generation.py`

**What it does:**
- Generates attribution graphs on Neuronpedia via API
- Extracts static metrics for each feature node
- Visualizes feature distribution (layer × context position)
- Selects relevant features for Stage 2

**Main UI:**
- Input form: Model, Source Set, Prompt, Target
- Threshold configuration (node, edge, max features)
- Interactive graph visualization (scatter plot)
- Export selected features

**Output:**
- `output/graph_data/*.json` - Complete graph
- `output/*_static_metrics.csv` - Metrics per feature
- `output/*_selected_features.json` - Selected features

### Stage 2: Probe Prompts

**Page:** `01_Probe_Prompts.py`

**What it does:**
- Generates semantic concepts related to the prompt (via OpenAI)
- Gets activations for each feature on each concept (via Neuronpedia)
- Calculates metrics: peak tokens, consistency, sparsity, confidence
- Automatic checkpoints for resuming from interruptions

**Main UI:**
- Load graph JSON (from Stage 1)
- Automatic or manual concept generation
- Cumulative influence threshold configuration
- Checkpoint & Recovery section
- Real-time progress bar

**Output:**
- `output/*_export.csv` - Base dataset
- `output/*_export_ENRICHED.csv` - With aggregated metrics
- `output/checkpoints/*.json` - Checkpoints for resume

**Special Features:**
- Automatic retry with exponential backoff
- Intelligent rate limiting
- Automatic resume from interruptions (Ctrl+C safe)

### Stage 3: Node Grouping

**Page:** `02_Node_Grouping.py`

**What it does:**
- **Step 1**: Classifies peak tokens (functional vs semantic)
- **Step 2**: Classifies features into supernodes (decision tree)
- **Step 3**: Assigns automatic names based on patterns
- **Upload**: Upload to Neuronpedia for interactive visualization

**Main UI:**
- Upload CSV from Stage 2
- Threshold configuration (sidebar)
- 3 sequential steps with intermediate results
- "Explain Feature Classification" tool
- Upload to Neuronpedia

**Output:**
- `output/*_GROUPED.csv` - Final CSV with classification and naming
- `output/*_SUMMARY.json` - Statistics and parameters

**Supernode Categories:**
- **Semantic (Dictionary)**: Specific tokens (e.g., "capital", "of")
- **Semantic (Concept)**: Related concepts (e.g., "Capital", "Texas")
- **Say "X"**: Output prediction (e.g., 'Say "Austin"')
- **Relationship**: Relationships between entities

---

## 📁 Output Files

### After Stage 1
```
output/
├── graph_data/
│   └── my_graph_YYYYMMDD_HHMMSS.json
├── my_graph_static_metrics.csv
└── my_graph_selected_features.json
```

### After Stage 2
```
output/
├── YYYYMMDD_HHMMSS_export.csv
├── YYYYMMDD_HHMMSS_export_ENRICHED.csv
└── checkpoints/
    └── probe_prompts_YYYYMMDD_HHMMSS.json
```

### After Stage 3
```
output/
├── YYYYMMDD_HHMMSS_GROUPED.csv
└── YYYYMMDD_HHMMSS_SUMMARY.json
```

---

## ⚙️ Configuration

### API Keys

Create `.env` in the root:
```env
NEURONPEDIA_API_KEY='your-key-here'
OPENAI_API_KEY='your-key-here'
```

### Default Thresholds

Classification thresholds in Stage 3 are configurable in the sidebar:

**Dictionary Semantic:**
- Peak Consistency min: 0.8
- N Distinct Peaks max: 1

**Say "X":**
- Func vs Sem % min: 50%
- Confidence F min: 0.9
- Layer min: 7

**Relationship:**
- Sparsity max: 0.45

**Semantic (Concept):**
- Layer max: 3
- Confidence S min: 0.5

See `eda/config/defaults.py` for advanced configurations.

---

## 🔄 Typical Workflow

### 1. Generate Graph (5 min)

1. Go to **Stage 1: Graph Generation**
2. Enter:
   - Model: `gemma-2-2b`
   - Source: `gemmascope-transcoder-16k`
   - Prompt: `"The capital of Texas is"`
   - Target: `" Austin"`
3. Click **"Generate Graph"**
4. Wait for generation (1-5 min)
5. Visualize feature distribution
6. Select features (e.g., top 100 by node_influence)
7. Download JSON and CSV

### 2. Probe Prompts (15 min)

1. Go to **Stage 2: Probe Prompts**
2. Load the graph JSON from Stage 1
3. Generate concepts automatically (or enter manually)
4. Configure:
   - Cumulative Influence: 95%
   - Checkpoint every: 10 features
5. Click **"Run Analysis"**
6. Wait (~10-20 min for 100 features × 5 concepts)
7. Download CSV Export and ENRICHED

**Note:** If interrupted, resume from checkpoint!

### 3. Node Grouping (2 min)

1. Go to **Stage 3: Node Grouping**
2. Load the ENRICHED CSV from Stage 2
3. (Optional) Load activations JSON and graph JSON
4. **Step 1**: Click "Run Step 1"
   - Verify functional vs semantic token statistics
5. **Step 2**: (Optional: modify thresholds) → "Run Step 2"
   - Verify class distribution
   - Use "Explain Classification" for debugging
6. **Step 3**: Click "Run Step 3"
   - Verify naming by class
7. Download GROUPED CSV and SUMMARY
8. (Optional) Upload to Neuronpedia

---

## 🐛 Troubleshooting

### App won't open

**Error:** `streamlit: command not found`

**Solution:**
```bash
pip install streamlit
# or
source .venv/bin/activate
```

### Blank page or import error

**Error:** `Module 'eda' not found`

**Solution:** Launch from project root:
```bash
streamlit run eda/app.py
```

### API Key not found

**Error:** `API key not found in .env`

**Solution:**
1. Create `.env` in root (not in `eda/`)
2. Format: `NEURONPEDIA_API_KEY='sk-np-...'`
3. Restart Streamlit

### Checkpoint not found

**Error:** `No checkpoint found`

**Solution:** Normal for first run. Checkpoints are created automatically.

### Rate Limit

**Error:** `429 Too Many Requests`

**Solution:** Automatic retry handles this. Wait a few seconds, it will resume automatically.

### Unicode Error (Windows)

**Error:** `UnicodeEncodeError`

**Solution:**
```powershell
$env:PYTHONIOENCODING='utf-8'
.\start_streamlit.ps1
```

---

## 💡 Tips & Best Practices

### For Graph Generation

- Use **Max Feature Nodes** between 100-500 for quick analyses
- Increase **Node Threshold** (0.85-0.9) for cleaner graphs
- Always save the graph JSON for Stage 2

### For Probe Prompts

- Generate 5-10 concepts for good coverage
- Use **Checkpoint every 10** for long analyses
- Monitor `probe_prompts.log` for debugging
- If interrupted, use the dropdown to resume

### For Node Grouping

- Always load the **ENRICHED** CSV (not the base one)
- Iterate on Step 2 by modifying thresholds without redoing Step 1
- Use "Explain Classification" to understand decisions
- Save SUMMARY.json for traceability

---

## 📖 Documentation

- **Complete Guide**: `eda/README.md` (600+ lines)
- **Main README**: `readme.md`
- **Environment Setup**: `SETUP.md`
- **Node Grouping Details**: `eda/pages/README_NODE_GROUPING.md`

---

## 🔗 Useful Links

- **Neuronpedia**: https://www.neuronpedia.org
- **Circuit Tracer**: https://github.com/safety-research/circuit-tracer
- **Paper**: https://transformer-circuits.pub/2025/attribution-graphs/

---

## 📞 Support

**Common issues:** See Troubleshooting section above

**Logs:** `probe_prompts.log` for API call details

**Tests:** `tests/` for programmatic usage examples

---

**Version:** 2.0.0-clean | Pipeline v2  
**Last Updated:** October 2025  
**License:** GPL-3.0
