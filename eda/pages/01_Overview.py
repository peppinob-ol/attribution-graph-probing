"""Dashboard Overview con KPI globali"""
import streamlit as st
import json
import pandas as pd
from pathlib import Path
from eda.utils.data_loader import load_final, load_cicciotti
from eda.utils.plots import plot_coverage_comparison
from eda.config.defaults import EXPORT_DIR

st.set_page_config(page_title="Overview", page_icon="📊", layout="wide")

st.title("📊 Dashboard Overview")
st.write("KPI globali del sistema di labelling supernodi")

# Carica dati
final_data = load_final()

if final_data is None:
    st.error("Dati finali non disponibili")
    st.stop()

stats = final_data.get('comprehensive_statistics', {})
quality = final_data.get('quality_metrics', {})

# KPI principali
st.header("KPI Globali")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Supernodi totali", stats.get('total_supernodes', 0))
    st.metric("Semantici", stats.get('semantic_supernodes', 0))

with col2:
    st.metric("Computazionali", stats.get('computational_supernodes', 0))
    st.metric("Features coperte", stats.get('total_features_covered', 0))

with col3:
    st.metric("Coverage totale", f"{stats.get('coverage_percentage', 0):.1f}%")
    st.metric("Coverage qualità", f"{stats.get('quality_coverage_percentage', 0):.1f}%")

with col4:
    st.metric("Garbage identificato", stats.get('garbage_features_identified', 0))
    st.metric("Processabili", stats.get('processable_features', 0))

with col5:
    st.metric("Coerenza semantica", f"{quality.get('semantic_avg_coherence', 0):.3f}")
    st.metric("Diversità comp.", quality.get('computational_diversity', 0))

# Grafici
st.header("Visualizzazioni")

col1, col2 = st.columns(2)

with col1:
    st.subheader("Coverage")
    # Coverage semantici vs totale
    semantic_cov = (stats.get('features_in_semantic', 0) / 
                   stats.get('original_features', 1) * 100)
    total_cov = stats.get('coverage_percentage', 0)
    
    fig = plot_coverage_comparison(semantic_cov, total_cov, 
                                   title="Coverage: Semantici vs Totale")
    st.plotly_chart(fig, use_container_width=True)

with col2:
    st.subheader("Breakdown supernodi")
    # Pie chart semantic vs computational
    import plotly.graph_objects as go
    
    fig = go.Figure(data=[go.Pie(
        labels=['Semantici', 'Computazionali'],
        values=[stats.get('semantic_supernodes', 0), 
               stats.get('computational_supernodes', 0)],
        hole=0.3
    )])
    fig.update_layout(title="Semantic vs Computational", height=400)
    st.plotly_chart(fig, use_container_width=True)

# Dettagli qualità
st.header("Metriche di Qualità")

col1, col2 = st.columns(2)

with col1:
    st.write("**Cross-prompt validation:**")
    st.success(quality.get('cross_prompt_validation', 'N/A'))
    
    st.write("**Narrative consistency:**")
    st.info(quality.get('narrative_consistency', 'N/A'))

with col2:
    # Breakdown features
    st.write("**Breakdown features:**")
    breakdown_data = {
        'Categoria': ['Semantici', 'Computazionali', 'Processabili (residui)', 'Garbage'],
        'Count': [
            stats.get('features_in_semantic', 0),
            stats.get('features_in_computational', 0),
            stats.get('processable_features', 0),
            stats.get('garbage_features_identified', 0)
        ]
    }
    st.bar_chart(pd.DataFrame(breakdown_data).set_index('Categoria'))

# Dati raw
with st.expander("📋 Dati completi (JSON)"):
    st.json(final_data)

# Export
st.header("Export")

col1, col2 = st.columns(2)

with col1:
    # Export dashboard JSON
    dashboard_json = {
        'totals': {
            'supernodes': stats.get('total_supernodes', 0),
            'semantic': stats.get('semantic_supernodes', 0),
            'computational': stats.get('computational_supernodes', 0),
        },
        'coverage': {
            'features': stats.get('total_features_covered', 0),
            'quality_pct': stats.get('quality_coverage_percentage', 0),
        },
        'quality': {
            'semantic_avg_coherence': quality.get('semantic_avg_coherence', 0),
            'computational_diversity': quality.get('computational_diversity', 0),
        },
        'garbage': {
            'identified': stats.get('garbage_features_identified', 0),
            'processable': stats.get('processable_features', 0),
        }
    }
    
    st.download_button(
        label="📥 Download dashboard.json",
        data=json.dumps(dashboard_json, indent=2),
        file_name='dashboard.json',
        mime='application/json'
    )

with col2:
    # Export KPI CSV
    kpi_data = {
        'metric': [
            'total_supernodes', 'semantic_supernodes', 'computational_supernodes',
            'total_features_covered', 'coverage_percentage', 'quality_coverage_percentage',
            'garbage_features_identified', 'processable_features',
            'semantic_avg_coherence', 'computational_diversity'
        ],
        'value': [
            stats.get('total_supernodes', 0),
            stats.get('semantic_supernodes', 0),
            stats.get('computational_supernodes', 0),
            stats.get('total_features_covered', 0),
            stats.get('coverage_percentage', 0),
            stats.get('quality_coverage_percentage', 0),
            stats.get('garbage_features_identified', 0),
            stats.get('processable_features', 0),
            quality.get('semantic_avg_coherence', 0),
            quality.get('computational_diversity', 0),
        ]
    }
    kpi_df = pd.DataFrame(kpi_data)
    
    st.download_button(
        label="📥 Download kpi.csv",
        data=kpi_df.to_csv(index=False),
        file_name='kpi.csv',
        mime='text/csv'
    )

# Info sistema
st.sidebar.header("ℹ️ Info Sistema")
st.sidebar.write(f"**Strategy:** {final_data.get('strategy', 'N/A')}")
st.sidebar.write(f"**Timestamp:** {final_data.get('timestamp', 'N/A')}")
st.sidebar.write(f"**Original features:** {stats.get('original_features', 0)}")

