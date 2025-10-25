"""Fase 1 - Feature Explorer: Focus su Feature Influenti e Interpretabilità"""
import sys
from pathlib import Path

# Aggiungi parent directory al path
parent_dir = Path(__file__).parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import streamlit as st
import pandas as pd
import numpy as np
from eda.utils.data_loader import load_personalities, load_archetypes, load_acts, load_graph
from eda.utils.plots import (plot_metrics_by_layer, plot_correlation_heatmap,
                             plot_token_distribution, plot_scatter_2d)
from eda.components.feature_panel import render_feature_detail

st.set_page_config(page_title="Fase 1 - Features", page_icon="🎭", layout="wide")

st.title("🎭 Fase 1: Feature Influenti e Interpretabilità")

st.markdown("""
**Domanda chiave**: Le feature più influenti dal grafo sono interpretate correttamente?

Questa pagina si concentra su:
- ⚡ Feature ad alta **node_influence** e **output_impact**
- ⚠️ Feature influenti ma con **bassa consistenza semantica** (possibili falsi negativi)
- ✅ Feature che combinano **alto impatto causale + alta interpretabilità**
""")

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

# Aggiungi classificazione archetipo
if archetypes:
    archetype_map = {}
    for arch_name, features in archetypes.items():
        for feat in features:
            archetype_map[feat['feature_key']] = arch_name
    pers_df['archetype'] = pers_df['feature_key'].map(archetype_map).fillna('unknown')
else:
    pers_df['archetype'] = 'unknown'

# Calcola score compositi
pers_df['semantic_score'] = (
    pers_df['mean_consistency'] * 0.5 + 
    pers_df['max_affinity'] * 0.3 + 
    pers_df['label_affinity'] * 0.2
)

pers_df['causal_impact'] = (
    pers_df['node_influence'].abs() * 0.6 + 
    pers_df['output_impact'] * 0.4
)

# Flag per feature "a rischio" - alta influenza ma bassa semantica
HIGH_IMPACT_THRESHOLD = pers_df['causal_impact'].quantile(0.75)
LOW_SEMANTIC_THRESHOLD = 0.3

pers_df['needs_review'] = (
    (pers_df['causal_impact'] > HIGH_IMPACT_THRESHOLD) & 
    (pers_df['semantic_score'] < LOW_SEMANTIC_THRESHOLD)
)

st.write(f"**Features totali:** {len(pers_df)}")
st.write(f"⚠️ **Features ad alta influenza ma bassa semantica (da rivedere):** {pers_df['needs_review'].sum()}")

# === SIDEBAR: FILTRI INTELLIGENTI ===
st.sidebar.header("🔍 Filtri Intelligenti")

filter_preset = st.sidebar.selectbox(
    "Preset filtri",
    [
        "Tutte le feature",
        "⚡ Top Influenza Causale",
        "✅ Alto Impatto + Alta Semantica", 
        "⚠️ Alto Impatto + Bassa Semantica (REVIEW!)",
        "🎯 Semantic Anchors",
        "❓ Outliers Influenti"
    ],
    help="Preset per esplorare rapidamente feature critiche"
)

# Applica preset
if filter_preset == "⚡ Top Influenza Causale":
    threshold = st.sidebar.slider("Top % per influenza", 5, 50, 10)
    filtered_df = pers_df.nlargest(int(len(pers_df) * threshold / 100), 'causal_impact')
    st.info(f"📊 Mostrando top {threshold}% per influenza causale")
    
elif filter_preset == "✅ Alto Impatto + Alta Semantica":
    filtered_df = pers_df[
        (pers_df['causal_impact'] > HIGH_IMPACT_THRESHOLD) &
        (pers_df['semantic_score'] > 0.5)
    ]
    st.success(f"✅ Feature con alto impatto E alta interpretabilità: {len(filtered_df)}")
    
elif filter_preset == "⚠️ Alto Impatto + Bassa Semantica (REVIEW!)":
    filtered_df = pers_df[pers_df['needs_review']]
    st.warning(f"⚠️ Feature influenti ma poco interpretabili: {len(filtered_df)} - **RICHIEDONO REVISIONE**")
    st.markdown("""
    Queste feature potrebbero essere:
    - **Semantiche ma con descrizioni errate** (Neuronpedia labels sbagliati)
    - **Veramente computazionali** (pattern sintattici, posizionali)
    - **Specializzate su contesti non coperti** dai prompt di test
    """)
    
elif filter_preset == "🎯 Semantic Anchors":
    filtered_df = pers_df[pers_df['archetype'] == 'semantic_anchors']
    st.success(f"🎯 Semantic Anchors: {len(filtered_df)}")
    
elif filter_preset == "❓ Outliers Influenti":
    filtered_df = pers_df[
        (pers_df['archetype'] == 'outliers') &
        (pers_df['causal_impact'] > HIGH_IMPACT_THRESHOLD)
    ]
    st.info(f"❓ Outliers con alta influenza causale: {len(filtered_df)}")
    
else:  # "Tutte le feature"
    filtered_df = pers_df.copy()
    
    # Filtri manuali
    layer_range = st.sidebar.slider(
        "Layer range",
        int(pers_df['layer'].min()),
        int(pers_df['layer'].max()),
        (int(pers_df['layer'].min()), int(pers_df['layer'].max())),
    )
    
    filtered_df = filtered_df[
        (filtered_df['layer'] >= layer_range[0]) &
        (filtered_df['layer'] <= layer_range[1])
    ]

st.write(f"**Features visualizzate:** {len(filtered_df)}")

# === TABS ===
tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Dashboard Influenza",
    "🔬 Analisi Dettagliata", 
    "🎭 Archetipi",
    "🔍 Ispeziona Feature"
])

# === TAB 1: DASHBOARD INFLUENZA ===
with tab1:
    st.header("📊 Dashboard Influenza vs Interpretabilità")
    
    # Metriche chiave
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric(
            "Avg Causal Impact",
            f"{filtered_df['causal_impact'].mean():.3f}",
            help="Media dell'impatto causale (node_influence + output_impact)"
        )
    
    with col2:
        st.metric(
            "Avg Semantic Score", 
            f"{filtered_df['semantic_score'].mean():.3f}",
            help="Media del punteggio semantico (mean_consistency + max_affinity + label_affinity)"
        )
    
    with col3:
        high_impact_high_sem = (
            (filtered_df['causal_impact'] > HIGH_IMPACT_THRESHOLD) &
            (filtered_df['semantic_score'] > 0.5)
        ).sum()
        st.metric(
            "✅ Influenti + Semantiche",
            high_impact_high_sem,
            help="Feature con alta influenza E alta semantica (ideale!)"
        )
    
    with col4:
        needs_review = filtered_df['needs_review'].sum()
        st.metric(
            "⚠️ Da Rivedere",
            needs_review,
            delta=f"{needs_review/len(filtered_df)*100:.1f}%",
            delta_color="inverse",
            help="Feature influenti ma con bassa semantica"
        )
    
    # Scatter principale: Influenza vs Semantica
    st.subheader("🎯 Influenza Causale vs Interpretabilità Semantica")
    
    fig_main = plot_scatter_2d(
        filtered_df,
        x='causal_impact',
        y='semantic_score',
        color='archetype',
        hover_data=['feature_key', 'most_common_peak', 'layer', 'node_influence', 'output_impact'],
        title='Feature Map: Causal Impact vs Semantic Score',
        labels={'causal_impact': 'Causal Impact (↑ più influente)',
                'semantic_score': 'Semantic Score (↑ più interpretabile)'}
    )
    st.plotly_chart(fig_main, use_container_width=True)
    
    st.markdown("""
    **Come leggere il grafico:**
    - 🟢 **Alto-Destra**: Feature ideali (influenti + interpretabili)
    - 🟡 **Alto-Sinistra**: ⚠️ Influenti ma poco interpretabili (da rivedere!)
    - 🔵 **Basso-Destra**: Interpretabili ma poco influenti
    - ⚪ **Basso-Sinistra**: Né influenti né interpretabili
    """)
    
    # Top features per influenza
    st.subheader("⚡ Top 20 Feature per Influenza Causale")
    
    top_impact = filtered_df.nlargest(20, 'causal_impact')[
        ['feature_key', 'layer', 'most_common_peak', 'archetype',
         'causal_impact', 'semantic_score', 'node_influence', 'output_impact',
         'mean_consistency', 'max_affinity', 'needs_review']
    ].copy()
    
    # Colora righe che necessitano review
    def highlight_needs_review(row):
        if row['needs_review']:
            return ['background-color: #fff3cd'] * len(row)
        return [''] * len(row)
    
    st.dataframe(
        top_impact.style.apply(highlight_needs_review, axis=1),
        use_container_width=True,
        height=400
    )
    
    st.caption("💡 Righe evidenziate: feature ad alta influenza ma bassa semantica (richiedono revisione)")
    
    # Distribuzione per archetipo
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Distribuzione Archetipi")
        arch_counts = filtered_df['archetype'].value_counts()
        st.bar_chart(arch_counts)
    
    with col2:
        st.subheader("Influenza per Archetipo")
        arch_impact = filtered_df.groupby('archetype')['causal_impact'].mean().sort_values(ascending=False)
        st.bar_chart(arch_impact)

# === TAB 2: ANALISI DETTAGLIATA ===
with tab2:
    st.header("🔬 Analisi Metriche Dettagliata")
    
    # Metriche per layer
    st.subheader("Metriche per Layer")
    col1, col2 = st.columns(2)
    
    with col1:
        metric1 = st.selectbox(
            "Metrica 1", 
            ['causal_impact', 'semantic_score', 'node_influence', 'output_impact',
             'mean_consistency', 'max_affinity', 'label_affinity'],
            index=0,
            key='layer_metric1'
        )
        fig1 = plot_metrics_by_layer(filtered_df, metric1)
        st.plotly_chart(fig1, use_container_width=True)
    
    with col2:
        metric2 = st.selectbox(
            "Metrica 2",
            ['causal_impact', 'semantic_score', 'node_influence', 'output_impact',
             'mean_consistency', 'max_affinity', 'label_affinity'],
            index=1,
            key='layer_metric2'
        )
        fig2 = plot_metrics_by_layer(filtered_df, metric2)
        st.plotly_chart(fig2, use_container_width=True)
    
    # Correlazioni
    st.subheader("Matrice Correlazioni")
    corr_cols = ['causal_impact', 'semantic_score', 'node_influence', 'output_impact',
                 'mean_consistency', 'max_affinity', 'label_affinity', 
                 'conditional_consistency', 'activation_stability']
    available_cols = [c for c in corr_cols if c in filtered_df.columns]
    
    if len(available_cols) > 1:
        fig_corr = plot_correlation_heatmap(filtered_df, available_cols)
        st.plotly_chart(fig_corr, use_container_width=True)
    
    # Token distribution
    st.subheader("Distribuzione Peak Tokens")
    fig_token = plot_token_distribution(filtered_df, top_n=20)
    st.plotly_chart(fig_token, use_container_width=True)
    
    # Scatter plots personalizzabili
    st.subheader("Scatter Plots Personalizzati")
    col1, col2 = st.columns(2)
    
    with col1:
        x_var = st.selectbox("X axis", available_cols, index=2, key='scatter_x1')
        y_var = st.selectbox("Y axis", available_cols, index=4, key='scatter_y1')
        color_var = st.selectbox("Color", ['archetype', 'layer', 'needs_review', 'most_common_peak'], key='scatter_c1')
        
        fig_s1 = plot_scatter_2d(filtered_df, x_var, y_var, color=color_var,
                                 hover_data=['feature_key', 'most_common_peak'])
        st.plotly_chart(fig_s1, use_container_width=True)
    
    with col2:
        x_var2 = st.selectbox("X axis", available_cols, index=5, key='scatter_x2')
        y_var2 = st.selectbox("Y axis", available_cols, index=6, key='scatter_y2')
        color_var2 = st.selectbox("Color", ['archetype', 'layer', 'needs_review', 'most_common_peak'], key='scatter_c2')
        
        fig_s2 = plot_scatter_2d(filtered_df, x_var2, y_var2, color=color_var2,
                                hover_data=['feature_key', 'most_common_peak'])
        st.plotly_chart(fig_s2, use_container_width=True)
    
    # Tabella completa esportabile
    st.subheader("Tabella Completa Features")
    
    display_cols = ['feature_key', 'layer', 'archetype', 'most_common_peak',
                   'causal_impact', 'semantic_score', 'needs_review',
                   'node_influence', 'output_impact',
                   'mean_consistency', 'max_affinity', 'label_affinity']
    available_display = [c for c in display_cols if c in filtered_df.columns]
    
    sort_by = st.selectbox("Ordina per", available_display, 
                          index=available_display.index('causal_impact') if 'causal_impact' in available_display else 0)
    sort_asc = st.checkbox("Ascendente", value=False)
    
    sorted_df = filtered_df[available_display].sort_values(sort_by, ascending=sort_asc)
    
    st.dataframe(
        sorted_df.style.apply(
            lambda row: ['background-color: #fff3cd'] * len(row) if row.get('needs_review', False) else [''] * len(row),
            axis=1
        ),
        use_container_width=True,
        height=500
    )
    
    # Export
    st.download_button(
        label="📥 Download CSV",
        data=sorted_df.to_csv(index=False),
        file_name='features_filtered.csv',
        mime='text/csv'
    )

# === TAB 3: ARCHETIPI ===
with tab3:
    st.header("🎭 Narrative Archetypes Analysis")
    
    st.info("""
    **Archetipi dopo ottimizzazione soglie:**
    - 🎯 **Semantic Anchors**: Mean consistency ≥0.6, Max affinity ≥0.65 (almeno 2/3 criteri)
    - 📊 **Stable Contributors**: Alta consistency ma affinità media
    - 🎪 **Contextual Specialists**: Alta max affinity ma consistency variabile
    - ⚙️ **Computational Helpers**: Alto node_influence/output_impact ma bassa semantica
    - ❓ **Outliers**: Non classificabili negli altri archetipi
    """)
    
    if archetypes:
        # Statistiche per archetipo
        archetype_stats = []
        for arch_name, features in archetypes.items():
            if not features:
                continue
            
            arch_keys = [f['feature_key'] for f in features]
            arch_df = pers_df[pers_df['feature_key'].isin(arch_keys)]
            
            archetype_stats.append({
                'Archetype': arch_name,
                'Count': len(features),
                'Avg Causal Impact': arch_df['causal_impact'].mean(),
                'Avg Semantic Score': arch_df['semantic_score'].mean(),
                'Avg Node Influence': arch_df['node_influence'].abs().mean(),
                'Needs Review': arch_df['needs_review'].sum()
            })
        
        stats_df = pd.DataFrame(archetype_stats)
        st.dataframe(stats_df, use_container_width=True)
        
        # Dettagli per archetipo
        st.subheader("Esplora Archetipo")
        selected_arch = st.selectbox("Seleziona archetipo", list(archetypes.keys()))
        
        if selected_arch and archetypes[selected_arch]:
            arch_features = archetypes[selected_arch]
            st.write(f"**{selected_arch}:** {len(arch_features)} features")
            
            # Ordina per influenza
            arch_data = []
            for feat in arch_features:
                fkey = feat['feature_key']
                p = personalities.get(fkey, {})
                arch_data.append({
                    'feature_key': fkey,
                    'layer': p.get('layer', 0),
                    'token': p.get('most_common_peak', '?'),
                    'causal_impact': pers_df.loc[fkey, 'causal_impact'] if fkey in pers_df.index else 0,
                    'semantic_score': pers_df.loc[fkey, 'semantic_score'] if fkey in pers_df.index else 0,
                    'node_influence': p.get('node_influence', 0),
                    'mean_cons': p.get('mean_consistency', 0),
                    'max_aff': p.get('max_affinity', 0),
                    'needs_review': pers_df.loc[fkey, 'needs_review'] if fkey in pers_df.index else False
                })
            
            arch_detail_df = pd.DataFrame(arch_data).sort_values('causal_impact', ascending=False)
            
            # Top N
            top_n = st.slider("Mostra top N", 10, 100, 20, key='arch_topn')
            
            st.dataframe(
                arch_detail_df.head(top_n).style.apply(
                    lambda row: ['background-color: #fff3cd'] * len(row) if row.get('needs_review', False) else [''] * len(row),
                    axis=1
                ),
                use_container_width=True
            )
            
            # Download
            st.download_button(
                label=f"📥 Download {selected_arch} CSV",
                data=arch_detail_df.to_csv(index=False),
                file_name=f'{selected_arch}.csv',
                mime='text/csv'
            )
    else:
        st.warning("Archetipi non disponibili")

# === TAB 4: ISPEZIONA FEATURE ===
with tab4:
    st.header("🔍 Ispeziona Singola Feature")
    
    # Opzioni di ricerca
    search_mode = st.radio(
        "Modalità ricerca",
        ["Da lista", "Per feature_key", "Random da 'needs_review'"],
        horizontal=True
    )
    
    if search_mode == "Da lista":
        feature_selection = st.selectbox(
            "Seleziona feature",
            options=sorted(filtered_df['feature_key'].tolist()),
            format_func=lambda x: (
                f"{x} | L{personalities.get(x, {}).get('layer', '?')} | "
                f"{personalities.get(x, {}).get('most_common_peak', '?')}"
                f"{' ⚠️' if x in pers_df.index and pers_df.loc[x, 'needs_review'] else ''}"
            )
        )
    elif search_mode == "Per feature_key":
        feature_selection = st.text_input("Inserisci feature_key (es. 24_13277)")
    else:  # Random da needs_review
        if st.button("🎲 Estrai feature random da rivedere"):
            review_features = filtered_df[filtered_df['needs_review']]['feature_key'].tolist()
            if review_features:
                feature_selection = np.random.choice(review_features)
                st.success(f"Feature estratta: {feature_selection}")
            else:
                st.warning("Nessuna feature da rivedere nel set filtrato")
                feature_selection = None
        else:
            feature_selection = None
    
    if feature_selection and feature_selection in personalities:
        # Alert se needs review
        if feature_selection in pers_df.index and pers_df.loc[feature_selection, 'needs_review']:
            st.warning(f"⚠️ **Feature {feature_selection} richiede revisione**: alta influenza causale ma bassa interpretabilità semantica")
        
        render_feature_detail(
            feature_selection,
            personalities,
            acts_data=acts_data,
            graph_available=(graph_data is not None)
        )
    elif feature_selection:
        st.error(f"Feature {feature_selection} non trovata")
