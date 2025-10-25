"""Dashboard Overview con KPI globali"""
import sys
from pathlib import Path

# Aggiungi parent directory al path
parent_dir = Path(__file__).parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import streamlit as st
import json
import pandas as pd
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
st.header("Global KPIs")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric("Total supernodes", stats.get('total_supernodes', 0),
             help="Total number of supernodes (semantic + computational)")
    st.metric("Semantic", stats.get('semantic_supernodes', 0),
             help="Cicciotti supernodes: semantically coherent and causally connected clusters")

with col2:
    st.metric("Computational", stats.get('computational_supernodes', 0),
             help="Computational clusters: multi-dimensional grouping of quality residuals")
    st.metric("Features covered", stats.get('total_features_covered', 0),
             help="Total features assigned to any supernode (semantic or computational)")

with col3:
    st.metric("Total coverage", f"{stats.get('coverage_percentage', 0):.1f}%",
             help="Percentage of all features covered by supernodes. "
                  "Formula: (total_features_covered / original_features) × 100")
    st.metric("Quality coverage", f"{stats.get('quality_coverage_percentage', 0):.1f}%",
             help="Coverage of quality features only (admitted by tau_inf or tau_aff thresholds). "
                  "Excludes garbage features.")

with col4:
    st.metric("Garbage identified", stats.get('garbage_features_identified', 0),
             help="Features below quality thresholds (tau_inf AND tau_aff). "
                  "Not processable, excluded from coverage calculation.")
    st.metric("Processable", stats.get('processable_features', 0),
             help="Quality features not yet in supernodes. Candidates for further clustering.")

with col5:
    st.metric("Semantic avg coherence", f"{quality.get('semantic_avg_coherence', 0):.3f}",
             help="Average final_coherence across all semantic supernodes. "
                  "Range [0,1]. Higher = more internally consistent supernodes.")
    st.metric("Computational diversity", quality.get('computational_diversity', 0),
             help="Number of distinct cluster signatures (layer_group × token × causal_tier) "
                  "in computational supernodes.")

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

