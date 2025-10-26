"""
Main Streamlit App for Circuit Tracer + Probe Rover
Research Project: Automating attribution graph analysis through probe prompting
"""
import sys
from pathlib import Path

# Add parent directory to path for imports
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import streamlit as st

# Main page configuration
st.set_page_config(
    page_title="Automating Attribution Graph Analysis",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Header
st.title("🔬 Automating Attribution Graph Analysis")
st.write("**Research Project: Automated interpretation of sparse features through probe prompting**")

st.markdown("""
This application implements a **three-stage pipeline** for automatically analyzing and interpreting 
attribution graphs from sparse feature models (SAE and/or CLT cross-layer transcoders):

### 🌐 Stage 1: Graph Generation
Generate attribution graphs on Neuronpedia to understand how sparse features contribute to model predictions.
Extract static metrics and select relevant features for downstream analysis.

### 🔍 Stage 2: Probe Prompting  
Analyze feature activations on semantically related concepts using automated probe prompts.
Generate concepts via LLM and measure how features respond across different contexts.

### 🔗 Stage 3: Node Grouping
Automatically classify and name features into interpretable supernodes based on their activation patterns.
Group features by semantic similarity and functional role (Dictionary, Concept, Say "X", Relationship).

---

Use the **sidebar** to navigate between pipeline stages.
""")

# Output folder status
st.header("📁 Output Folder Status")

output_dir = parent_dir / "output"
if output_dir.exists():
    # Count files by type
    json_files = list(output_dir.glob("*.json"))
    pt_files = list(output_dir.glob("*.pt"))
    csv_files = list(output_dir.glob("*.csv"))
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Graphs (.pt)", len(pt_files))
    
    with col2:
        st.metric("JSON Files", len(json_files))
    
    with col3:
        st.metric("CSV Exports", len(csv_files))
    
    st.success(f"✅ Output folder found: `{output_dir.relative_to(parent_dir)}`")
else:
    st.warning("⚠️ Output folder not found. It will be created on first export.")

# Quick access to pipeline stages
st.header("🚀 Pipeline Stages")

col1, col2, col3 = st.columns(3)

with col1:
    st.page_link("pages/00_Graph_Generation.py", label="Stage 1: Graph Generation", icon="🌐")
    st.caption("Generate attribution graphs and extract features from Neuronpedia")

with col2:
    st.page_link("pages/01_Probe_Prompts.py", label="Stage 2: Probe Prompts", icon="🔍")
    st.caption("Analyze feature activations on semantic concepts via API")

with col3:
    st.page_link("pages/02_Node_Grouping.py", label="Stage 3: Node Grouping", icon="🔗")
    st.caption("Classify and name supernodes for interpretability")

# Project info
st.sidebar.header("ℹ️ About")
st.sidebar.write("""

**Documentation:** 
- Full guide: `eda/README.md`

""")

st.sidebar.write("---")
st.sidebar.caption("Version: 2.0.0-clean | Pipeline v2")
st.sidebar.caption("🔬 Automated SAE Feature Interpretation")

