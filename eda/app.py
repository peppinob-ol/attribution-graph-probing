"""
App Streamlit principale per EDA pipeline supernodi
"""
import streamlit as st
from eda.utils.data_loader import check_data_availability

# Configurazione pagina principale
st.set_page_config(
    page_title="EDA Supernodi",
    page_icon="🔬",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Header
st.title("🔬 EDA Sistema Labelling Supernodi")
st.write("**Analisi esplorativa della pipeline antropologica per supernodi**")

st.markdown("""
Questa applicazione consente di:
- 📊 **Overview**: Dashboard KPI globali
- 🎭 **Fase 1**: Esplorare feature e personalità
- 🌱 **Fase 2**: Analizzare supernodi cicciotti con dry-run parametrico
- 🧪 **Cross-Prompt**: Validare robustezza cross-prompt
- 🏭 **Fase 3**: Clustering residui con parametri configurabili

Usa la **sidebar** per navigare tra le pagine e configurare parametri.
""")

# Verifica disponibilità dati
st.header("Stato Dati")

data_status = check_data_availability()

col1, col2 = st.columns(2)

with col1:
    st.subheader("Dati Essenziali")
    for key in ['personalities', 'archetypes', 'cicciotti', 'validation', 'final', 'thresholds']:
        status = "✅" if data_status.get(key, False) else "❌"
        st.write(f"{status} {key}")

with col2:
    st.subheader("Dati Opzionali")
    for key in ['static_metrics', 'acts', 'graph', 'labels']:
        status = "✅" if data_status.get(key, False) else "⚠️"
        st.write(f"{status} {key}")

# Avvisi
missing_essential = [k for k in ['personalities', 'cicciotti', 'final', 'thresholds'] 
                     if not data_status.get(k, False)]

if missing_essential:
    st.error(f"⚠️ Dati essenziali mancanti: {', '.join(missing_essential)}")
    st.write("Esegui la pipeline completa prima di usare l'app:")
    st.code("""
# Windows PowerShell
.\\run_full_pipeline.ps1

# Linux/Mac
bash run_full_pipeline.sh
    """)
else:
    st.success("✅ Tutti i dati essenziali sono disponibili!")

if not data_status.get('graph', False):
    st.warning("⚠️ Grafo causale non disponibile. Alcune funzionalità (edge density, vicinato) non saranno utilizzabili.")

# Quick links
st.header("Quick Links")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.page_link("pages/01_Overview.py", label="📊 Overview", icon="📊")

with col2:
    st.page_link("pages/02_Phase1_Features.py", label="🎭 Features", icon="🎭")

with col3:
    st.page_link("pages/03_Phase2_Supernodes.py", label="🌱 Supernodi", icon="🌱")

with col4:
    st.page_link("pages/04_CrossPrompt.py", label="🧪 Cross-Prompt", icon="🧪")

with col5:
    st.page_link("pages/05_Phase3_Residuals.py", label="🏭 Residui", icon="🏭")

# Info progetto
st.sidebar.header("ℹ️ Info")
st.sidebar.write("""
**Progetto:** circuit_tracer-prompt_rover

**Pipeline:**
1. Analisi antropologica features
2. Costruzione supernodi semantici (cicciotti)
3. Clustering residui computazionali

**Documentazione:** `docs/supernode_labelling/`
""")

st.sidebar.write("---")
st.sidebar.caption("Versione: 1.0.0 | Streamlit EDA")

