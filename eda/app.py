"""
App Streamlit principale per Circuit Tracer + Probe Rover
"""
import sys
from pathlib import Path

# Aggiungi parent directory al path per import
parent_dir = Path(__file__).parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import streamlit as st

# Configurazione pagina principale
st.set_page_config(
    page_title="Circuit Tracer + Probe Rover",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Header
st.title("🔬 Circuit Tracer + Probe Rover")
st.write("**Analisi Attribution Graphs e Probe Prompting**")

st.markdown("""
Questa applicazione consente di:
- 🌐 **Graph Generation**: Genera attribution graphs su Neuronpedia
- 🔍 **Probe Prompts**: Analizza attivazioni su concepts specifici tramite API

Usa la **sidebar** per navigare tra le pagine.
""")

# Info output folder
st.header("📁 Output Folder")

output_dir = parent_dir / "output"
if output_dir.exists():
    # Conta file per tipo
    json_files = list(output_dir.glob("*.json"))
    pt_files = list(output_dir.glob("*.pt"))
    csv_files = list(output_dir.glob("*.csv"))
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Grafi (.pt)", len(pt_files))
    
    with col2:
        st.metric("JSON", len(json_files))
    
    with col3:
        st.metric("CSV Export", len(csv_files))
    
    st.success(f"✅ Output folder trovata: `{output_dir.relative_to(parent_dir)}`")
else:
    st.warning("⚠️ Cartella output non trovata. Verrà creata al primo export.")

# Quick links
st.header("🚀 Quick Links")

col1, col2 = st.columns(2)

with col1:
    st.page_link("pages/00_Graph_Generation.py", label="🌐 Graph Generation", icon="🌐")

with col2:
    st.page_link("pages/01_Probe_Prompts.py", label="🔍 Probe Prompts", icon="🔍")

# Info progetto
st.sidebar.header("ℹ️ Info")
st.sidebar.write("""
**Project:** circuit_tracer-prompt_rover

**Tools:**
- 🌐 Attribution Graph Generation (Neuronpedia API)
- 🔍 Probe Prompting (OpenAI + Neuronpedia APIs)

**Core Scripts:**
- `scripts/00_neuronpedia_graph_generation.py`
- `scripts/01_probe_prompts.py`
- `scripts/causal_utils.py` (utilities causali)

**Documentation:** 
- Quick start: `QUICK_START_STREAMLIT.md`
- Graph guide: `docs/NEURONPEDIA_EXPORT_GUIDE.md`
- Probe guide: `docs/PROBE_PROMPTS_QUICKSTART.md`
""")

st.sidebar.write("---")
st.sidebar.caption("Version: 2.0.0-clean | Pipeline v2")
st.sidebar.caption("🌐 Neuronpedia Integration | 🔍 Probe Prompting")

