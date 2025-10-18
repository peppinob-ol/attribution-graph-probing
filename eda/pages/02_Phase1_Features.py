"""Fase 1 - Feature Explorer"""
import streamlit as st
import pandas as pd
import numpy as np
from eda.utils.data_loader import load_personalities, load_archetypes, load_acts, load_graph
from eda.utils.plots import (plot_metrics_by_layer, plot_correlation_heatmap,
                             plot_token_distribution, plot_scatter_2d)
from eda.components.feature_panel import render_feature_detail

st.set_page_config(page_title="Fase 1 - Features", page_icon="🎭", layout="wide")

st.title("🎭 Fase 1: Analisi Antropologica Features")

# Carica dati
personalities = load_personalities()
archetypes = load_archetypes()
acts_data = load_acts()
graph_data = load_graph()

if personalities is None:
    st.error("Personalities non disponibili")
    st.stop()

# Converti in DataFrame
pers_df = pd.DataFrame.from_dict(personalities, orient='index')
pers_df['feature_key'] = pers_df.index

st.write(f"**Features totali:** {len(pers_df)}")

# Sidebar: filtri
st.sidebar.header("Filtri")

layer_range = st.sidebar.slider(
    "Layer range",
    int(pers_df['layer'].min()),
    int(pers_df['layer'].max()),
    (int(pers_df['layer'].min()), int(pers_df['layer'].max()))
)

token_filter = st.sidebar.multiselect(
    "Token filter",
    options=sorted(pers_df['most_common_peak'].unique()),
    default=[]
)

# Applica filtri
filtered_df = pers_df[
    (pers_df['layer'] >= layer_range[0]) &
    (pers_df['layer'] <= layer_range[1])
]

if token_filter:
    filtered_df = filtered_df[filtered_df['most_common_peak'].isin(token_filter)]

st.write(f"**Features filtrate:** {len(filtered_df)}")

# Tabs
tab1, tab2, tab3, tab4 = st.tabs(["Grafici", "Tabella", "Archetipi", "Dettaglio Feature"])

with tab1:
    st.header("Visualizzazioni")
    
    # Metriche per layer
    col1, col2 = st.columns(2)
    
    with col1:
        metric1 = st.selectbox("Metrica 1", 
                               ['mean_consistency', 'max_affinity', 'conditional_consistency',
                                'node_influence', 'output_impact', 'label_affinity'],
                               index=0)
        fig1 = plot_metrics_by_layer(filtered_df, metric1)
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        metric2 = st.selectbox("Metrica 2",
                               ['mean_consistency', 'max_affinity', 'conditional_consistency',
                                'node_influence', 'output_impact', 'label_affinity'],
                               index=1)
        fig2 = plot_metrics_by_layer(filtered_df, metric2)
        st.plotly_chart(fig2, use_container_width=True)
    
    # Correlazioni
    st.subheader("Correlazioni")
    corr_cols = ['mean_consistency', 'max_affinity', 'conditional_consistency',
                 'node_influence', 'output_impact', 'label_affinity']
    available_cols = [c for c in corr_cols if c in filtered_df.columns]
    
    if len(available_cols) > 1:
        fig_corr = plot_correlation_heatmap(filtered_df, available_cols)
        st.plotly_chart(fig_corr, use_container_width=True)
    
    # Token distribution
    st.subheader("Token Distribution")
    fig_token = plot_token_distribution(filtered_df, top_n=15)
    st.plotly_chart(fig_token, use_container_width=True)
    
    # Scatter plots
    st.subheader("Scatter Plots")
    col1, col2 = st.columns(2)
    
    with col1:
        x_var = st.selectbox("X axis", available_cols, index=0, key='scatter_x1')
        y_var = st.selectbox("Y axis", available_cols, index=1, key='scatter_y1')
        color_var = st.selectbox("Color", ['layer', 'most_common_peak', None], key='scatter_c1')
        
        fig_s1 = plot_scatter_2d(filtered_df, x_var, y_var, color=color_var,
                                 hover_data=['feature_key'])
        st.plotly_chart(fig_s1, use_container_width=True)
    
    with col2:
        x_var2 = st.selectbox("X axis", available_cols, index=3, key='scatter_x2')
        y_var2 = st.selectbox("Y axis", available_cols, index=4, key='scatter_y2')
        color_var2 = st.selectbox("Color", ['layer', 'most_common_peak', None], key='scatter_c2')
        
        fig_s2 = plot_scatter_2d(filtered_df, x_var2, y_var2, color=color_var2,
                                hover_data=['feature_key'])
        st.plotly_chart(fig_s2, use_container_width=True)

with tab2:
    st.header("Tabella Features")
    
    # Colonne da mostrare
    display_cols = ['feature_key', 'layer', 'most_common_peak', 'mean_consistency',
                   'max_affinity', 'conditional_consistency', 'node_influence',
                   'output_impact', 'label_affinity']
    available_display = [c for c in display_cols if c in filtered_df.columns]
    
    # Ordinamento
    sort_by = st.selectbox("Ordina per", available_display, index=0)
    sort_asc = st.checkbox("Ascendente", value=False)
    
    sorted_df = filtered_df[available_display].sort_values(sort_by, ascending=sort_asc)
    
    st.dataframe(sorted_df, use_container_width=True, height=500)
    
    # Export
    st.download_button(
        label="📥 Download filtered features CSV",
        data=sorted_df.to_csv(index=False),
        file_name='features_filtered.csv',
        mime='text/csv'
    )

with tab3:
    st.header("Archetipi Narrativi")
    
    if archetypes:
        # Conteggi
        archetype_counts = {k: len(v) for k, v in archetypes.items()}
        
        st.write("**Distribuzione archetipi:**")
        arch_df = pd.DataFrame(list(archetype_counts.items()), 
                               columns=['Archetipo', 'Count'])
        st.bar_chart(arch_df.set_index('Archetipo'))
        
        # Dettagli per archetipo
        selected_arch = st.selectbox("Seleziona archetipo", list(archetypes.keys()))
        
        if selected_arch and archetypes[selected_arch]:
            st.write(f"**{selected_arch}:** {len(archetypes[selected_arch])} features")
            
            # Top N
            top_n = st.slider("Mostra top N", 5, 50, 10)
            arch_features = archetypes[selected_arch][:top_n]
            
            # Mostra dettagli
            arch_data = []
            for feat in arch_features:
                fkey = feat['feature_key']
                p = feat.get('personality', {})
                arch_data.append({
                    'feature': fkey,
                    'layer': p.get('layer', 0),
                    'token': p.get('most_common_peak', '?'),
                    'mean_cons': p.get('mean_consistency', 0),
                    'max_aff': p.get('max_affinity', 0),
                    'node_inf': p.get('node_influence', 0),
                })
            
            st.dataframe(pd.DataFrame(arch_data), use_container_width=True)
    else:
        st.warning("Archetipi non disponibili")

with tab4:
    st.header("Dettaglio Singola Feature")
    
    # Selezione feature
    feature_selection = st.selectbox(
        "Seleziona feature",
        options=sorted(filtered_df['feature_key'].tolist()),
        format_func=lambda x: f"{x} (L{personalities.get(x, {}).get('layer', '?')}, {personalities.get(x, {}).get('most_common_peak', '?')})"
    )
    
    if feature_selection:
        render_feature_detail(
            feature_selection,
            personalities,
            acts_data=acts_data,
            graph_available=(graph_data is not None)
        )

