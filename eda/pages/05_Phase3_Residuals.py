"""Fase 3 - Residui Computazionali"""
import streamlit as st
import pandas as pd
import json
from eda.utils.data_loader import load_final, load_personalities, load_thresholds, load_cicciotti, load_graph
from eda.utils.compute import identify_quality_residuals, cluster_residuals, merge_clusters_jaccard
from eda.utils.plots import plot_cluster_sizes, plot_scatter_2d, plot_coverage_comparison
from eda.config.defaults import PHASE3_DEFAULTS

st.set_page_config(page_title="Fase 3 - Residui", page_icon="🏭", layout="wide")

st.title("🏭 Fase 3: Clustering Residui Computazionali")

# Carica dati
final_data = load_final()
personalities = load_personalities()
thresholds_data = load_thresholds()
cicciotti = load_cicciotti()
graph_data = load_graph()

if personalities is None or thresholds_data is None or cicciotti is None:
    st.error("Dati mancanti")
    st.stop()

# Sidebar: parametri Fase 3
st.sidebar.header("⚙️ Parametri Fase 3")

# Thresholds
st.sidebar.subheader("Soglie ammissione")
tau_inf = st.sidebar.number_input(
    "tau_inf (logit influence)",
    value=float(thresholds_data.get('thresholds', {}).get('tau_inf', 0.000194)),
    format="%.6f",
    step=0.000001
)

tau_aff = st.sidebar.number_input(
    "tau_aff (max affinity)",
    value=float(thresholds_data.get('thresholds', {}).get('tau_aff', 0.65)),
    format="%.2f",
    step=0.05
)

tau_inf_very_high = st.sidebar.number_input(
    "tau_inf_very_high (<BOS>)",
    value=float(thresholds_data.get('thresholds', {}).get('tau_inf_very_high', 0.025)),
    format="%.3f",
    step=0.001
)

# Clustering params
st.sidebar.subheader("Clustering")
min_cluster_size = st.sidebar.slider(
    "Min cluster size", 2, 10, PHASE3_DEFAULTS['min_cluster_size']
)

layer_group_span = st.sidebar.slider(
    "Layer group span", 2, 5, PHASE3_DEFAULTS['layer_group_span']
)

node_inf_high = st.sidebar.slider(
    "Node influence HIGH", 0.05, 0.20, PHASE3_DEFAULTS['node_inf_high'], 0.01
)

node_inf_med = st.sidebar.slider(
    "Node influence MED", 0.005, 0.05, PHASE3_DEFAULTS['node_inf_med'], 0.005
)

min_frequency_ratio = st.sidebar.slider(
    "Min frequency ratio (token)", 0.01, 0.05, PHASE3_DEFAULTS['min_frequency_ratio'], 0.005
)

# Merge params
st.sidebar.subheader("Merge")
jaccard_threshold = st.sidebar.slider(
    "Jaccard merge threshold", 0.5, 0.9, PHASE3_DEFAULTS['jaccard_merge_threshold'], 0.05
)

# Calcola con parametri correnti
with st.spinner("Ricalcolo residui..."):
    # Thresholds personalizzati
    custom_thresholds = {
        'tau_inf': tau_inf,
        'tau_aff': tau_aff,
        'tau_inf_very_high': tau_inf_very_high,
    }
    
    quality_residuals, residuals_stats = identify_quality_residuals(
        personalities, cicciotti, custom_thresholds
    )
    
    # Clustering
    clusters = cluster_residuals(
        quality_residuals,
        personalities,
        min_cluster_size=min_cluster_size,
        layer_group_span=layer_group_span,
        node_inf_high=node_inf_high,
        node_inf_med=node_inf_med,
        min_frequency_ratio=min_frequency_ratio
    )
    
    # Arricchimento con stats
    for cluster_id, cluster in clusters.items():
        members = cluster['members']
        if len(members) > 0:
            cluster['avg_layer'] = sum(personalities[m]['layer'] for m in members if m in personalities) / len(members)
            cluster['dominant_token'] = pd.Series([personalities[m].get('most_common_peak', '?') 
                                                   for m in members if m in personalities]).mode()[0]
            cluster['avg_consistency'] = sum(personalities[m].get('conditional_consistency', 0) 
                                            for m in members if m in personalities) / len(members)
            cluster['avg_node_influence'] = sum(personalities[m].get('node_influence', 0) 
                                                for m in members if m in personalities) / len(members)
            cluster['causal_connectivity'] = 0.0  # TODO: calcolo se grafo disponibile
    
    # Merge
    merged_clusters, merge_log = merge_clusters_jaccard(clusters, jaccard_threshold)

# Tabs
tab1, tab2, tab3 = st.tabs(["Residui", "Clusters", "Coverage"])

with tab1:
    st.header("Residui di Qualità")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Total admitted", residuals_stats['total_admitted'])
    
    with col2:
        st.metric("Used in cicciotti", residuals_stats['used_in_cicciotti'])
    
    with col3:
        st.metric("Quality residuals", residuals_stats['quality_residuals'])
    
    st.write("---")
    
    # Breakdown
    if thresholds_data and 'admitted_features' in thresholds_data:
        situational = set(thresholds_data['admitted_features'].get('situational_core', []))
        scaffold = set(thresholds_data['admitted_features'].get('generalizable_scaffold', []))
        
        situational_res = [f for f in quality_residuals if f in situational]
        scaffold_res = [f for f in quality_residuals if f in scaffold]
        overlap_res = [f for f in quality_residuals if f in situational and f in scaffold]
        
        st.subheader("Breakdown")
        col1, col2, col3 = st.columns(3)
        
        with col1:
            st.metric("Situational core", len(situational_res))
        
        with col2:
            st.metric("Generalizable scaffold", len(scaffold_res))
        
        with col3:
            st.metric("Overlap", len(overlap_res))
    
    # Sample residui
    st.subheader("Sample Residui (primi 20)")
    residuals_sample = []
    for fkey in quality_residuals[:20]:
        if fkey in personalities:
            p = personalities[fkey]
            residuals_sample.append({
                'feature': fkey,
                'layer': p.get('layer', 0),
                'token': p.get('most_common_peak', '?'),
                'mean_cons': p.get('mean_consistency', 0),
                'max_aff': p.get('max_affinity', 0),
                'node_inf': p.get('node_influence', 0),
            })
    
    if residuals_sample:
        st.dataframe(pd.DataFrame(residuals_sample), use_container_width=True)

with tab2:
    st.header("Clusters Computazionali")
    
    st.write(f"**Clusters (prima merge):** {len(clusters)}")
    st.write(f"**Clusters (dopo merge):** {len(merged_clusters)}")
    
    if len(merge_log) > 0:
        st.write(f"**Merge eseguiti:** {len(merge_log)}")
        with st.expander("Dettagli merge"):
            st.json(merge_log)
    
    # Converti in DataFrame
    if merged_clusters:
        cluster_df = pd.DataFrame([
            {
                'id': cid,
                'n_members': c['n_members'],
                'signature': c.get('cluster_signature', '?'),
                'token': c.get('dominant_token', '?'),
                'avg_layer': c.get('avg_layer', 0),
                'avg_consistency': c.get('avg_consistency', 0),
                'avg_node_influence': c.get('avg_node_influence', 0),
                'causal_connectivity': c.get('causal_connectivity', 0),
            }
            for cid, c in merged_clusters.items()
        ])
        
        st.subheader("Tabella Clusters")
        st.dataframe(cluster_df, use_container_width=True, height=400)
        
        # Grafici
        st.subheader("Visualizzazioni")
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig1 = plot_cluster_sizes(merged_clusters, title="Distribuzione dimensioni cluster")
            st.plotly_chart(fig1, use_container_width=True)
        
        with col2:
            if 'causal_connectivity' in cluster_df.columns and 'avg_consistency' in cluster_df.columns:
                fig2 = plot_scatter_2d(cluster_df, 'causal_connectivity', 'avg_consistency',
                                      color='token', hover_data=['id'],
                                      title='Connettività causale vs consistenza')
                st.plotly_chart(fig2, use_container_width=True)
        
        # Export
        st.download_button(
            label="📥 Download clusters CSV",
            data=cluster_df.to_csv(index=False),
            file_name='clusters_current.csv',
            mime='text/csv'
        )
        
        st.download_button(
            label="📥 Download clusters JSON",
            data=json.dumps(merged_clusters, indent=2),
            file_name='clusters_current.json',
            mime='application/json'
        )
    else:
        st.info("Nessun cluster valido con parametri correnti")

with tab3:
    st.header("Coverage Analysis")
    
    # Coverage baseline vs corrente
    if final_data:
        baseline_stats = final_data.get('comprehensive_statistics', {})
        
        baseline_coverage = baseline_stats.get('quality_coverage_percentage', 0)
        
        # Coverage corrente
        total_in_cicciotti = sum(len(c.get('members', [])) for c in cicciotti.values())
        total_in_clusters = sum(c['n_members'] for c in merged_clusters.values())
        current_coverage_total = total_in_cicciotti + total_in_clusters
        
        current_coverage_pct = (current_coverage_total / 
                               (current_coverage_total + len(quality_residuals)) * 100
                               if (current_coverage_total + len(quality_residuals)) > 0 else 0)
        
        st.subheader("Confronto Coverage")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.metric("Baseline (precomputed)", f"{baseline_coverage:.1f}%")
            st.metric("Features in semantic", baseline_stats.get('features_in_semantic', 0))
            st.metric("Features in computational", baseline_stats.get('features_in_computational', 0))
        
        with col2:
            st.metric("Corrente (parametri custom)", f"{current_coverage_pct:.1f}%")
            st.metric("Features in semantic", total_in_cicciotti)
            st.metric("Features in computational", total_in_clusters)
        
        # Grafico
        fig_cov = plot_coverage_comparison(baseline_coverage, current_coverage_pct,
                                          title="Coverage: Baseline vs Corrente")
        st.plotly_chart(fig_cov, use_container_width=True)
        
        # Delta
        delta = current_coverage_pct - baseline_coverage
        if delta > 0:
            st.success(f"Δ Coverage: +{delta:.1f}% (miglioramento)")
        elif delta < 0:
            st.warning(f"Δ Coverage: {delta:.1f}% (peggioramento)")
        else:
            st.info("Δ Coverage: 0.0% (invariato)")

# Export parametri
st.sidebar.write("---")
if st.sidebar.button("📥 Export parametri correnti"):
    params_export = {
        'phase3_thresholds': {
            'tau_inf': tau_inf,
            'tau_aff': tau_aff,
            'tau_inf_very_high': tau_inf_very_high,
        },
        'phase3_clustering': {
            'min_cluster_size': min_cluster_size,
            'layer_group_span': layer_group_span,
            'node_inf_high': node_inf_high,
            'node_inf_med': node_inf_med,
            'min_frequency_ratio': min_frequency_ratio,
        },
        'phase3_merge': {
            'jaccard_threshold': jaccard_threshold,
        }
    }
    
    st.sidebar.download_button(
        label="Download parameters.json",
        data=json.dumps(params_export, indent=2),
        file_name='phase3_parameters.json',
        mime='application/json'
    )

