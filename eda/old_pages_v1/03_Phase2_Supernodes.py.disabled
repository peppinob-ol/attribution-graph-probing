"""Fase 2 - Supernodi Cicciotti"""
import sys
from pathlib import Path

# Aggiungi parent directory al path
parent_dir = Path(__file__).parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import streamlit as st
import pandas as pd
from eda.utils.data_loader import load_cicciotti, load_personalities, load_graph
from eda.utils.plots import plot_scatter_2d
from eda.components.supernode_panel import render_supernode_detail
from eda.config.defaults import PHASE2_DEFAULTS

st.set_page_config(page_title="Fase 2 - Supernodi", page_icon="🌱", layout="wide")

st.title("🌱 Fase 2: Supernodi Cicciotti")

# Carica dati
cicciotti = load_cicciotti()
personalities = load_personalities()
graph_data = load_graph()

if cicciotti is None:
    st.error("Supernodi non disponibili")
    st.stop()

if personalities is None:
    st.error("Personalities non disponibili")
    st.stop()

st.write(f"**Supernodi totali:** {len(cicciotti)}")

# Sidebar: parametri Fase 2
st.sidebar.header("⚙️ Phase 2 Parameters")
st.sidebar.write("*For dry-run and parametric analysis*")

enable_dryrun = st.sidebar.checkbox(
    "Enable dry-run", 
    value=False,
    help="Enable interactive parameter tuning to see how compatibility scores change"
)

dryrun_params = {}
if enable_dryrun:
    st.sidebar.subheader("Compatibility Weights")
    
    dryrun_params['causal_weight'] = st.sidebar.slider(
        "Causal weight", 
        0.4, 0.8, 
        PHASE2_DEFAULTS['causal_weight'], 
        0.05,
        help="Weight for causal compatibility (0-1). Semantic weight = 1 - causal_weight. "
             "Higher values prioritize causal graph connections over semantic similarity. "
             "Default: 0.60 (60% causal, 40% semantic)"
    )
    
    dryrun_params['tau_edge_strong'] = st.sidebar.slider(
        "tau_edge_strong", 
        0.02, 0.10, 
        PHASE2_DEFAULTS['tau_edge_strong'], 
        0.01,
        help="Threshold for considering an edge 'strong' in the attribution graph. "
             "Edges with weight > tau_edge_strong receive a 1.5x boost in compatibility. "
             "Default: 0.05"
    )
    
    st.sidebar.subheader("Growth Thresholds")
    
    dryrun_params['threshold_bootstrap'] = st.sidebar.slider(
        "Bootstrap threshold", 
        0.1, 0.5, 
        PHASE2_DEFAULTS['threshold_bootstrap'], 
        0.05,
        help="Minimum compatibility score to accept a candidate during bootstrap phase. "
             "Bootstrap phase uses 2-hop backward causal connections only. "
             "Lower = more permissive growth. Default: 0.30"
    )
    
    dryrun_params['threshold_normal'] = st.sidebar.slider(
        "Normal threshold", 
        0.3, 0.7, 
        PHASE2_DEFAULTS['threshold_normal'], 
        0.05,
        help="Minimum compatibility score to accept a candidate during normal growth phase. "
             "Normal phase combines causal (60%) and semantic (40%) compatibility. "
             "Higher = more selective, smaller supernodes. Default: 0.45"
    )
    
    dryrun_params['min_coherence'] = st.sidebar.slider(
        "Min coherence", 
        0.3, 0.8, 
        PHASE2_DEFAULTS['min_coherence'], 
        0.05,
        help="Minimum supernode coherence to continue growth. "
             "Coherence = weighted combination of consistency homogeneity (30%), "
             "token diversity (20%), layer span (20%), and causal edge density (30%). "
             "Growth stops if coherence drops below this threshold. Default: 0.50"
    )

# Converti in DataFrame per analisi
sn_data = []
for sn_id, sn in cicciotti.items():
    sn_data.append({
        'id': sn_id,
        'theme': sn.get('narrative_theme', '?'),
        'n_members': len(sn.get('members', [])),
        'final_coherence': sn.get('final_coherence', 0),
        'growth_iterations': sn.get('growth_iterations', 0),
        'seed_layer': sn.get('seed_layer', 0),
        'seed_logit_influence': sn.get('seed_logit_influence', 0),
    })

sn_df = pd.DataFrame(sn_data)

# Tabs
tab1, tab2, tab3 = st.tabs(["Lista", "Analisi", "Dettaglio"])

with tab1:
    st.header("Supernode List")
    
    st.caption("**Cicciotti supernodes** are semantically coherent clusters grown from high-influence seeds "
              "using causal-guided expansion with compatibility scoring.")
    
    # Filtri
    col1, col2, col3 = st.columns(3)
    
    with col1:
        theme_filter = st.multiselect(
            "Theme filter",
            options=sorted(sn_df['theme'].unique()),
            default=[],
            help="Filter by narrative theme (inferred from dominant tokens)"
        )
    
    with col2:
        min_members = st.slider("Min members", 0, int(sn_df['n_members'].max()), 0,
                               help="Minimum number of features in supernode")
    
    with col3:
        min_coherence = st.slider("Min coherence", 0.0, 1.0, 0.0, 0.05,
                                 help="Minimum final_coherence score (0-1)")
    
    # Applica filtri
    filtered_sn = sn_df.copy()
    if theme_filter:
        filtered_sn = filtered_sn[filtered_sn['theme'].isin(theme_filter)]
    filtered_sn = filtered_sn[filtered_sn['n_members'] >= min_members]
    filtered_sn = filtered_sn[filtered_sn['final_coherence'] >= min_coherence]
    
    st.write(f"**Supernodi filtrati:** {len(filtered_sn)}")
    
    # Ordina
    sort_by = st.selectbox("Ordina per", 
                          ['n_members', 'final_coherence', 'growth_iterations', 'seed_logit_influence'],
                          index=0)
    sort_asc = st.checkbox("Ascendente", value=False)
    
    sorted_sn = filtered_sn.sort_values(sort_by, ascending=sort_asc)
    
    st.dataframe(sorted_sn, use_container_width=True, height=400)
    
    # Export
    st.download_button(
        label="📥 Download supernodi CSV",
        data=sorted_sn.to_csv(index=False),
        file_name='supernodes_list.csv',
        mime='text/csv'
    )

with tab2:
    st.header("Analisi Supernodi")
    
    # Scatter plots
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Dimensione vs Coerenza")
        fig1 = plot_scatter_2d(sn_df, 'n_members', 'final_coherence', 
                              color='theme', hover_data=['id'])
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        st.subheader("Growth iterations vs Coerenza")
        fig2 = plot_scatter_2d(sn_df, 'growth_iterations', 'final_coherence',
                              color='theme', hover_data=['id'])
        st.plotly_chart(fig2, use_container_width=True)
    
    # Statistiche per theme
    st.subheader("Statistiche per Theme")
    theme_stats = sn_df.groupby('theme').agg({
        'n_members': ['mean', 'std', 'count'],
        'final_coherence': ['mean', 'std'],
        'growth_iterations': ['mean', 'std']
    }).round(3)
    st.dataframe(theme_stats, use_container_width=True)
    
    # Distribuzione coherence
    st.subheader("Distribuzione Final Coherence")
    import plotly.express as px
    fig_hist = px.histogram(sn_df, x='final_coherence', nbins=20,
                           title='Distribuzione final coherence')
    st.plotly_chart(fig_hist, use_container_width=True)

with tab3:
    st.header("Dettaglio Supernodo")
    
    selected_sn = st.selectbox(
        "Seleziona supernodo",
        options=sorted(cicciotti.keys()),
        format_func=lambda x: f"{x} ({cicciotti[x].get('narrative_theme', '?')}, {len(cicciotti[x].get('members', []))} membri)"
    )
    
    if selected_sn:
        render_supernode_detail(
            selected_sn,
            cicciotti,
            personalities,
            graph_data=graph_data,
            enable_dryrun=enable_dryrun,
            dryrun_params=dryrun_params if enable_dryrun else None
        )

