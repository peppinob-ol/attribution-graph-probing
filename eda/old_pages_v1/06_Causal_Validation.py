"""Fase 6 - Causal Validation: Cross-Prompt Activation Analysis"""
import sys
from pathlib import Path

# Aggiungi parent directory al path
parent_dir = Path(__file__).parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import streamlit as st
import pandas as pd
import numpy as np
import json
import plotly.express as px
import plotly.graph_objects as go
from scipy import stats
from sklearn.metrics import roc_curve, auc, precision_recall_curve
from eda.utils.data_loader import load_personalities, load_acts, load_cicciotti, load_graph
from eda.config.defaults import OUTPUT_PATHS

st.set_page_config(page_title="Causal Validation", page_icon="🔬", layout="wide")

st.title("🔬 Causal Validation: Cross-Prompt Analysis")

st.info("""
**Research Question**: Do features causally important for the output 'Austin' activate distinctively 
on semantically related prompts? Can cross-prompt activation patterns help identify causal importance?
""")

# Carica dati
personalities = load_personalities()
acts_data = load_acts()
cicciotti = load_cicciotti()
graph_data = load_graph()

if personalities is None or acts_data is None:
    st.error("Required data not available: personalities and acts_compared.csv needed")
    st.stop()

# Arricchisci personalities con feature_key
for fkey, p in personalities.items():
    p['feature_key'] = fkey

# Sidebar: configurazione analisi
st.sidebar.header("⚙️ Analysis Configuration")

# Definizione importanza causale
st.sidebar.subheader("Causal Importance Definition")

importance_metric = st.sidebar.selectbox(
    "Primary metric",
    ['node_influence', 'output_impact', 'combined'],
    help="Metric to define 'causally important' features:\n"
         "• node_influence: Backward propagation from logits\n"
         "• output_impact: Direct logit influence\n"
         "• combined: Weighted combination"
)

if importance_metric == 'combined':
    weight_node_inf = st.sidebar.slider(
        "Weight node_influence", 0.0, 1.0, 0.7, 0.1,
        help="Weight for node_influence in combined score. output_impact weight = 1 - this"
    )

importance_percentile = st.sidebar.slider(
    "Top percentile (important)",
    50, 99, 90, 1,
    help="Features above this percentile are considered 'causally important'"
)

# Metriche di attivazione
st.sidebar.subheader("Activation Metrics")

activation_metric = st.sidebar.selectbox(
    "Activation metric",
    ['nuova_max_label_span', 'normalized_sum_label', 'nuova_somma_label_span', 
     'twera_total_in', 'cosine_similarity'],
    help="Metric from acts_compared.csv to measure activation strength"
)

activation_threshold = st.sidebar.slider(
    "Activation threshold",
    0.0, 5.0, 0.5, 0.1,
    help="Minimum activation value to consider feature 'active'"
)

# Filtro prompt
st.sidebar.subheader("Prompt Filtering")

all_prompts = acts_data['prompt'].unique()
st.sidebar.write(f"Total prompts: {len(all_prompts)}")

selected_prompts = st.sidebar.multiselect(
    "Focus on prompts",
    options=all_prompts,
    default=list(all_prompts[:3]) if len(all_prompts) >= 3 else list(all_prompts),
    help="Select prompts to analyze. Leave empty for all."
)

if not selected_prompts:
    selected_prompts = list(all_prompts)

# Filtro BOS
exclude_bos_peak = st.sidebar.checkbox(
    "Exclude features peaking on <BOS>",
    value=False,
    help="Exclude features where peak_token is '<BOS>'. "
         "Structural BOS tokens often have high activation but low causal relevance."
)

# Calcola importanza causale
st.header("1. Causal Importance Calculation")

col1, col2, col3 = st.columns(3)

# Crea DataFrame features con metriche causali
features_df = pd.DataFrame.from_dict(personalities, orient='index')

if importance_metric == 'node_influence':
    features_df['importance_score'] = features_df['node_influence'].fillna(0)
elif importance_metric == 'output_impact':
    features_df['importance_score'] = features_df['output_impact'].fillna(0)
else:  # combined
    features_df['importance_score'] = (
        weight_node_inf * features_df['node_influence'].fillna(0) +
        (1 - weight_node_inf) * features_df['output_impact'].fillna(0)
    )

# Definisci soglia importanza
importance_threshold = features_df['importance_score'].quantile(importance_percentile / 100)
features_df['is_important'] = features_df['importance_score'] >= importance_threshold

n_important = features_df['is_important'].sum()
n_total = len(features_df)

with col1:
    st.metric("Total features", n_total)
    st.metric("Important features", n_important,
             help=f"Features above {importance_percentile}th percentile")

with col2:
    st.metric("Importance threshold", f"{importance_threshold:.4f}",
             help=f"Threshold for {importance_metric}")
    st.metric("% Important", f"{n_important/n_total*100:.1f}%")

with col3:
    st.metric("Metric used", importance_metric)
    if importance_metric == 'combined':
        st.metric("Node inf. weight", f"{weight_node_inf:.1f}")

# Distribuzione importanza
with st.expander("📊 Importance Score Distribution"):
    fig_dist = px.histogram(
        features_df, 
        x='importance_score',
        nbins=50,
        title=f"Distribution of {importance_metric}",
        labels={'importance_score': importance_metric}
    )
    fig_dist.add_vline(x=importance_threshold, line_dash="dash", 
                       annotation_text=f"{importance_percentile}th percentile")
    st.plotly_chart(fig_dist, use_container_width=True)

# Merge con acts_data
st.header("2. Cross-Prompt Activation Analysis")

# Filtra acts per prompt selezionati
acts_filtered = acts_data[acts_data['prompt'].isin(selected_prompts)].copy()

# Crea feature_key in acts
acts_filtered['feature_key'] = (
    acts_filtered['layer'].astype(str) + '_' + 
    acts_filtered['feature'].astype(str)
)

# Filtro BOS se richiesto - PRIMA del merge per influenzare tutto
n_total_before_filter = len(acts_filtered)
if exclude_bos_peak:
    acts_filtered = acts_filtered[acts_filtered['peak_token'] != '<BOS>'].copy()
    n_excluded_bos = n_total_before_filter - len(acts_filtered)
    
    # Anche filtra le feature da features_df per coerenza
    bos_features = acts_filtered[acts_filtered['peak_token'] == '<BOS>']['feature_key'].unique()
    # Ma manteniamo features_df originale per importanza, filtriamo solo acts
else:
    n_excluded_bos = 0

# Merge con importanza
acts_merged = acts_filtered.merge(
    features_df[['feature_key', 'is_important', 'importance_score']],
    on='feature_key',
    how='left'
)

acts_merged['is_important'] = acts_merged['is_important'].fillna(False)

# Info display e debug BOS filter
col_info1, col_info2, col_info3 = st.columns(3)
with col_info1:
    st.write(f"**Activation records**: {len(acts_merged)}")
    st.caption(f"From {len(selected_prompts)} prompts")
with col_info2:
    if exclude_bos_peak:
        st.warning(f"🚫 Excluded {n_excluded_bos} records")
        st.caption(f"with peak_token='<BOS>'")
    else:
        # Conta quanti BOS ci sono nei dati
        n_bos_in_data = (acts_merged['peak_token'] == '<BOS>').sum()
        if n_bos_in_data > 0:
            st.info(f"ℹ️ {n_bos_in_data} records have <BOS> peak")
            st.caption("(not excluded)")
with col_info3:
    # Unique features con BOS peak
    bos_features = acts_merged[acts_merged['peak_token'] == '<BOS>']['feature_key'].unique()
    n_unique_bos_features = len(bos_features)
    if n_unique_bos_features > 0:
        st.metric("Unique features with <BOS> peak", n_unique_bos_features)
        # Quante sono importanti?
        bos_important = acts_merged[
            (acts_merged['peak_token'] == '<BOS>') & 
            (acts_merged['is_important'])
        ]['feature_key'].nunique()
        if bos_important > 0:
            st.caption(f"⚠️ {bos_important} are causally important!")

# Statistiche per gruppo
important_acts = acts_merged[acts_merged['is_important']]
unimportant_acts = acts_merged[~acts_merged['is_important']]

col1, col2 = st.columns(2)

with col1:
    st.subheader("Important Features")
    st.write(f"Records: {len(important_acts)}")
    if len(important_acts) > 0:
        st.write(f"Mean {activation_metric}: {important_acts[activation_metric].mean():.3f}")
        st.write(f"Median: {important_acts[activation_metric].median():.3f}")
        st.write(f"Active (>{activation_threshold}): {(important_acts[activation_metric] > activation_threshold).sum()}")

with col2:
    st.subheader("Unimportant Features")
    st.write(f"Records: {len(unimportant_acts)}")
    if len(unimportant_acts) > 0:
        st.write(f"Mean {activation_metric}: {unimportant_acts[activation_metric].mean():.3f}")
        st.write(f"Median: {unimportant_acts[activation_metric].median():.3f}")
        st.write(f"Active (>{activation_threshold}): {(unimportant_acts[activation_metric] > activation_threshold).sum()}")

# Test statistico
if len(important_acts) > 0 and len(unimportant_acts) > 0:
    statistic, pvalue = stats.mannwhitneyu(
        important_acts[activation_metric].dropna(),
        unimportant_acts[activation_metric].dropna(),
        alternative='greater'
    )
    
    st.write("---")
    st.write("**Mann-Whitney U Test** (H1: Important features have higher activation)")
    col1, col2 = st.columns(2)
    with col1:
        st.metric("U-statistic", f"{statistic:.2f}")
    with col2:
        st.metric("p-value", f"{pvalue:.2e}",
                 delta="Significant ✅" if pvalue < 0.05 else "Not significant ❌")

# Tabs per diverse analisi
tab1, tab2, tab3, tab4, tab5 = st.tabs([
    "Main Chart", "ROC Analysis", "Feature Ranking", "Prompt Comparison", "Token Analysis"
])

with tab1:
    st.header("📊 Main Chart: Importance vs Activation")
    
    if exclude_bos_peak:
        st.info("🚫 **BOS Filter Active**: Features with peak_token='<BOS>' are excluded from activation data")
    
    st.caption("""
    **Stacked bar chart**: Features ordered by causal importance (left = most important).
    Bar height = activation strength. Color = prompt type.
    """)
    
    # Prepara dati per stacked bar
    # Top N features per importanza
    top_n = st.slider("Show top N features", 10, 100, 50, 10)
    
    top_features = features_df.nlargest(top_n, 'importance_score')['feature_key'].tolist()
    
    # Pivot per prompt
    pivot_data = acts_merged[acts_merged['feature_key'].isin(top_features)].pivot_table(
        index='feature_key',
        columns='prompt',
        values=activation_metric,
        aggfunc='max',
        fill_value=0
    )
    
    # Ordina per importanza
    pivot_data = pivot_data.reindex(top_features)
    
    # Stacked bar chart
    fig_main = go.Figure()
    
    for i, prompt in enumerate(selected_prompts):
        if prompt in pivot_data.columns:
            fig_main.add_trace(go.Bar(
                name=prompt[:30] + '...' if len(prompt) > 30 else prompt,
                x=pivot_data.index,
                y=pivot_data[prompt],
                hovertemplate=f'<b>{prompt}</b><br>Feature: %{{x}}<br>{activation_metric}: %{{y:.3f}}<extra></extra>'
            ))
    
    # Linea importanza (asse secondario)
    importance_line = features_df.set_index('feature_key').loc[top_features, 'importance_score']
    
    fig_main.add_trace(go.Scatter(
        name='Importance Score',
        x=importance_line.index,
        y=importance_line.values,
        mode='lines+markers',
        line=dict(color='red', width=2),
        yaxis='y2',
        hovertemplate='<b>Importance</b><br>Feature: %{x}<br>Score: %{y:.4f}<extra></extra>'
    ))
    
    title_suffix = " [BOS EXCLUDED]" if exclude_bos_peak else ""
    fig_main.update_layout(
        title=f"Top {top_n} Features: {activation_metric} by Prompt + Importance Score{title_suffix}",
        xaxis_title="Feature (ordered by importance)",
        yaxis_title=activation_metric,
        yaxis2=dict(
            title='Importance Score',
            overlaying='y',
            side='right'
        ),
        barmode='stack',
        height=600,
        hovermode='x unified',
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
    )
    
    st.plotly_chart(fig_main, use_container_width=True)
    
    # Debug info: BOS features in top N
    if not exclude_bos_peak:
        # Conta quante delle top N hanno BOS peak
        top_features_set = set(top_features)
        bos_in_top = acts_merged[
            (acts_merged['feature_key'].isin(top_features_set)) & 
            (acts_merged['peak_token'] == '<BOS>')
        ]['feature_key'].unique()
        
        if len(bos_in_top) > 0:
            with st.expander(f"🔍 Debug: {len(bos_in_top)} of top {top_n} features have <BOS> peaks"):
                st.write("**Features with <BOS> peak in current top N:**")
                bos_details = []
                for fkey in bos_in_top:
                    if fkey in features_df.index:
                        f = features_df.loc[fkey]
                        bos_details.append({
                            'feature': fkey,
                            'importance_score': f['importance_score'],
                            'is_important': f['is_important'],
                            'layer': f.get('layer', '?'),
                            'node_influence': f.get('node_influence', 0),
                            'output_impact': f.get('output_impact', 0)
                        })
                
                if bos_details:
                    bos_df = pd.DataFrame(bos_details).sort_values('importance_score', ascending=False)
                    st.dataframe(bos_df, use_container_width=True)
                    st.caption("💡 Try enabling 'Exclude features peaking on <BOS>' to see the effect")
        else:
            st.success(f"✅ None of the top {top_n} features peak on <BOS> - all are semantic!")
    
    # Export
    st.download_button(
        label="📥 Download chart data CSV",
        data=pivot_data.to_csv(),
        file_name='importance_vs_activation.csv',
        mime='text/csv'
    )

with tab2:
    st.header("📈 ROC Analysis: Activation as Predictor")
    
    st.caption("""
    **ROC Curve**: Using activation metric to predict causal importance.
    AUC = 1.0 (perfect), 0.5 (random). Higher = better predictor.
    """)
    
    # Prepara dati per ROC
    # Aggrega per feature (max activation across prompts)
    feature_agg = acts_merged.groupby('feature_key').agg({
        activation_metric: 'max',
        'is_important': 'first',
        'importance_score': 'first'
    }).reset_index()
    
    # Rimuovi NaN
    feature_agg = feature_agg.dropna(subset=[activation_metric, 'is_important'])
    
    if len(feature_agg) > 10:
        # ROC curve
        fpr, tpr, thresholds_roc = roc_curve(
            feature_agg['is_important'],
            feature_agg[activation_metric]
        )
        roc_auc = auc(fpr, tpr)
        
        fig_roc = go.Figure()
        
        fig_roc.add_trace(go.Scatter(
            x=fpr, y=tpr,
            mode='lines',
            name=f'ROC (AUC = {roc_auc:.3f})',
            line=dict(color='blue', width=2)
        ))
        
        fig_roc.add_trace(go.Scatter(
            x=[0, 1], y=[0, 1],
            mode='lines',
            name='Random (AUC = 0.5)',
            line=dict(color='gray', dash='dash')
        ))
        
        fig_roc.update_layout(
            title=f'ROC Curve: {activation_metric} predicting Causal Importance',
            xaxis_title='False Positive Rate',
            yaxis_title='True Positive Rate',
            height=500
        )
        
        st.plotly_chart(fig_roc, use_container_width=True)
        
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("AUC", f"{roc_auc:.3f}",
                     help="Area Under Curve. 1.0 = perfect, 0.5 = random")
        with col2:
            interpretation = "Excellent" if roc_auc > 0.9 else "Good" if roc_auc > 0.8 else "Fair" if roc_auc > 0.7 else "Poor"
            st.metric("Interpretation", interpretation)
        with col3:
            st.metric("Features analyzed", len(feature_agg))
        
        # Precision-Recall curve
        st.subheader("Precision-Recall Curve")
        
        precision, recall, thresholds_pr = precision_recall_curve(
            feature_agg['is_important'],
            feature_agg[activation_metric]
        )
        
        fig_pr = go.Figure()
        
        fig_pr.add_trace(go.Scatter(
            x=recall, y=precision,
            mode='lines',
            name='Precision-Recall',
            line=dict(color='green', width=2)
        ))
        
        # Baseline (random)
        baseline = feature_agg['is_important'].sum() / len(feature_agg)
        fig_pr.add_hline(y=baseline, line_dash="dash", 
                        annotation_text=f"Random baseline ({baseline:.2f})")
        
        fig_pr.update_layout(
            title='Precision-Recall Curve',
            xaxis_title='Recall',
            yaxis_title='Precision',
            height=500
        )
        
        st.plotly_chart(fig_pr, use_container_width=True)
        
        # Optimal threshold
        f1_scores = 2 * (precision[:-1] * recall[:-1]) / (precision[:-1] + recall[:-1] + 1e-10)
        optimal_idx = np.argmax(f1_scores)
        optimal_threshold = thresholds_pr[optimal_idx]
        
        st.write(f"**Optimal threshold** (max F1): {optimal_threshold:.3f}")
        st.write(f"At this threshold: Precision = {precision[optimal_idx]:.3f}, Recall = {recall[optimal_idx]:.3f}, F1 = {f1_scores[optimal_idx]:.3f}")
        
    else:
        st.warning("Not enough data for ROC analysis (need >10 features)")

with tab3:
    st.header("🏆 Feature Ranking: Top Important vs Top Activated")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Top 20 by Causal Importance")
        
        top_important = features_df.nlargest(20, 'importance_score')[
            ['feature_key', 'importance_score', 'layer', 'most_common_peak', 
             'node_influence', 'output_impact']
        ].copy()
        
        # Aggiungi max activation
        max_acts = acts_merged.groupby('feature_key')[activation_metric].max()
        top_important['max_activation'] = top_important['feature_key'].map(max_acts).fillna(0)
        
        st.dataframe(top_important, use_container_width=True, height=400)
    
    with col2:
        st.subheader(f"Top 20 by {activation_metric}")
        
        top_activated = acts_merged.groupby('feature_key').agg({
            activation_metric: 'max',
            'is_important': 'first',
            'importance_score': 'first',
            'layer': 'first',
            'peak_token': 'first'
        }).nlargest(20, activation_metric).reset_index()
        
        st.dataframe(top_activated, use_container_width=True, height=400)
    
    # Overlap analysis
    st.subheader("Overlap Analysis")
    
    top_important_set = set(top_important['feature_key'])
    top_activated_set = set(top_activated['feature_key'])
    
    overlap = top_important_set & top_activated_set
    only_important = top_important_set - top_activated_set
    only_activated = top_activated_set - top_important_set
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        st.metric("Overlap (in both top 20)", len(overlap),
                 help="Features that are both causally important AND highly activated")
    
    with col2:
        st.metric("Only important", len(only_important),
                 help="Causally important but low activation (potential false negatives)")
    
    with col3:
        st.metric("Only activated", len(only_activated),
                 help="Highly activated but not causally important (potential false positives)")
    
    # Venn diagram (simplified as bars)
    venn_data = pd.DataFrame({
        'Category': ['Both', 'Only Important', 'Only Activated'],
        'Count': [len(overlap), len(only_important), len(only_activated)]
    })
    
    fig_venn = px.bar(venn_data, x='Category', y='Count',
                     title='Top 20 Overlap',
                     color='Category')
    st.plotly_chart(fig_venn, use_container_width=True)

with tab4:
    st.header("🔄 Prompt Comparison")
    
    st.caption("Compare activation patterns across different prompts")
    
    # Heatmap: Feature × Prompt
    st.subheader("Heatmap: Top Features × Prompts")
    
    top_n_heatmap = st.slider("Features to show", 10, 50, 30, 5, key='heatmap_n')
    
    top_features_heatmap = features_df.nlargest(top_n_heatmap, 'importance_score')['feature_key'].tolist()
    
    heatmap_data = acts_merged[acts_merged['feature_key'].isin(top_features_heatmap)].pivot_table(
        index='feature_key',
        columns='prompt',
        values=activation_metric,
        aggfunc='max',
        fill_value=0
    )
    
    heatmap_data = heatmap_data.reindex(top_features_heatmap)
    
    fig_heatmap = px.imshow(
        heatmap_data,
        labels=dict(x="Prompt", y="Feature", color=activation_metric),
        aspect='auto',
        title=f"Activation Heatmap: Top {top_n_heatmap} Features",
        color_continuous_scale='Viridis'
    )
    fig_heatmap.update_layout(height=max(400, top_n_heatmap * 15))
    
    st.plotly_chart(fig_heatmap, use_container_width=True)
    
    # Violin per prompt
    st.subheader("Activation Distribution by Prompt")
    
    # Separa important vs unimportant
    fig_violin = go.Figure()
    
    for prompt in selected_prompts[:5]:  # Limita a 5 per leggibilità
        prompt_data_imp = acts_merged[
            (acts_merged['prompt'] == prompt) & 
            (acts_merged['is_important'])
        ][activation_metric]
        
        prompt_data_unimp = acts_merged[
            (acts_merged['prompt'] == prompt) & 
            (~acts_merged['is_important'])
        ][activation_metric]
        
        fig_violin.add_trace(go.Violin(
            y=prompt_data_imp,
            name=f"{prompt[:20]}... (Important)",
            box_visible=True,
            meanline_visible=True
        ))
        
        fig_violin.add_trace(go.Violin(
            y=prompt_data_unimp,
            name=f"{prompt[:20]}... (Unimportant)",
            box_visible=True,
            meanline_visible=True,
            line_color='lightgray'
        ))
    
    fig_violin.update_layout(
        title=f"Distribution of {activation_metric} by Prompt and Importance",
        yaxis_title=activation_metric,
        height=500
    )
    
    st.plotly_chart(fig_violin, use_container_width=True)

with tab5:
    st.header("🔤 Token Analysis")
    
    st.caption("Analyze `peak_token` and `picco_su_label` patterns")
    
    # picco_su_label per important vs unimportant
    st.subheader("Peak on Label Analysis")
    
    contingency = pd.crosstab(
        acts_merged['is_important'],
        acts_merged['picco_su_label'],
        normalize='index'
    ) * 100
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Contingency Table** (% within group)")
        st.dataframe(contingency)
        
        # Chi-square test
        contingency_counts = pd.crosstab(
            acts_merged['is_important'],
            acts_merged['picco_su_label']
        )
        
        chi2, pval, dof, expected = stats.chi2_contingency(contingency_counts)
        
        st.write(f"**Chi-Square Test**: χ² = {chi2:.2f}, p = {pval:.2e}")
        if pval < 0.05:
            st.success("✅ Significant association between importance and peak on label")
        else:
            st.warning("❌ No significant association")
    
    with col2:
        fig_picco = px.bar(
            contingency.T,
            barmode='group',
            title='% Peak on Label by Importance',
            labels={'value': '% of features', 'picco_su_label': 'Peak on Label'}
        )
        st.plotly_chart(fig_picco, use_container_width=True)
    
    # Token frequency
    st.subheader("Peak Token Distribution")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Important Features**")
        token_freq_imp = acts_merged[acts_merged['is_important']]['peak_token'].value_counts().head(15)
        st.bar_chart(token_freq_imp)
    
    with col2:
        st.write("**Unimportant Features**")
        token_freq_unimp = acts_merged[~acts_merged['is_important']]['peak_token'].value_counts().head(15)
        st.bar_chart(token_freq_unimp)

# Summary e conclusioni
st.header("📋 Summary & Conclusions")

summary_col1, summary_col2 = st.columns(2)

with summary_col1:
    st.subheader("Key Findings")
    
    # Calcola metriche chiave
    if len(feature_agg) > 10:
        st.write(f"**AUC**: {roc_auc:.3f} - Activation {'can' if roc_auc > 0.7 else 'cannot'} predict causal importance")
    
    if len(important_acts) > 0 and len(unimportant_acts) > 0:
        mean_diff = important_acts[activation_metric].mean() - unimportant_acts[activation_metric].mean()
        st.write(f"**Mean activation difference**: {mean_diff:.3f}")
        st.write(f"**Statistical significance**: {'Yes ✅' if pvalue < 0.05 else 'No ❌'}")
    
    overlap_pct = len(overlap) / 20 * 100
    st.write(f"**Top 20 overlap**: {overlap_pct:.0f}%")

with summary_col2:
    st.subheader("Recommendations")
    
    if 'roc_auc' in locals() and roc_auc > 0.8:
        st.success("✅ Cross-prompt activation is a good predictor of causal importance")
        st.write("→ Can be used for feature selection/filtering")
    elif 'roc_auc' in locals() and roc_auc > 0.6:
        st.info("⚠️ Cross-prompt activation has moderate predictive power")
        st.write("→ Use in combination with other metrics")
    else:
        st.warning("❌ Cross-prompt activation is not a reliable predictor")
        st.write("→ Consider other approaches or different prompts")
    
    if 'pvalue' in locals() and pvalue < 0.05:
        st.write("✅ Significant difference in activation between important/unimportant features")
    
    if overlap_pct > 50:
        st.write("✅ Good alignment between importance and activation rankings")

# Export finale
st.header("📥 Export Analysis")

export_data = {
    'configuration': {
        'importance_metric': importance_metric,
        'importance_percentile': importance_percentile,
        'activation_metric': activation_metric,
        'activation_threshold': activation_threshold,
        'selected_prompts': selected_prompts,
        'exclude_bos_peak': exclude_bos_peak,
        'n_excluded_bos': n_excluded_bos if exclude_bos_peak else 0,
    },
    'results': {
        'n_important': int(n_important),
        'n_total': int(n_total),
        'importance_threshold': float(importance_threshold),
        'auc': float(roc_auc) if 'roc_auc' in locals() else None,
        'mann_whitney_pvalue': float(pvalue) if 'pvalue' in locals() else None,
        'top20_overlap': int(len(overlap)) if 'overlap' in locals() else None,
    }
}

st.download_button(
    label="📥 Download analysis summary JSON",
    data=json.dumps(export_data, indent=2),
    file_name='causal_validation_summary.json',
    mime='application/json'
)

st.download_button(
    label="📥 Download feature importance + activation CSV",
    data=feature_agg.to_csv(index=False) if 'feature_agg' in locals() else '',
    file_name='feature_importance_activation.csv',
    mime='text/csv'
)

