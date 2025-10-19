"""Analisi Node Influence vs Probe Response"""
import sys
from pathlib import Path

# Aggiungi parent directory al path
parent_dir = Path(__file__).parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import streamlit as st
import json
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from eda.utils.data_loader import load_personalities, load_cicciotti

st.set_page_config(page_title="Node Influence Analysis", page_icon="🎯", layout="wide")

st.title("🎯 Node Influence vs Probe Response")
st.write("Analisi della causalità (node_influence) e interpretabilità (probe prompts)")

# Carica dati
personalities = load_personalities()
cicciotti = load_cicciotti()

if personalities is None:
    st.error("Dati personalities non disponibili")
    st.stop()

if cicciotti is None:
    st.warning("Dati cicciotti non disponibili")
    cicciotti = {}

# Prepara dataframe
st.sidebar.header("⚙️ Configurazione")

# Threshold configurabili
probe_threshold = st.sidebar.slider(
    "Soglia probe-responsive",
    min_value=0.0,
    max_value=100.0,
    value=15.0,
    step=5.0,
    help="Soglia nuova_max_label_span per considerare una feature 'probe-responsive'"
)

top_n = st.sidebar.slider(
    "Top-N feature da analizzare",
    min_value=20,
    max_value=500,
    value=100,
    step=20,
    help="Numero di top feature per node_influence da mostrare"
)

# Estrai cicciotti features
cicc_features = set()
for c in cicciotti.values():
    cicc_features.update(c['members'])

# Costruisci dataframe
data = []
for fkey, p in personalities.items():
    # Estrai layer dalla feature key
    try:
        layer = int(fkey.split('_')[0])
    except:
        layer = -1
    
    data.append({
        'feature': fkey,
        'layer': layer,
        'node_influence': abs(p.get('node_influence', 0)),
        'logit_influence': abs(p.get('logit_influence', 0)),
        'nuova_max_label_span': p.get('nuova_max_label_span', 0),
        'mean_consistency': p.get('mean_consistency', 0),
        'max_affinity': p.get('max_affinity', 0),
        'peak_token': p.get('most_common_peak', '?'),
        'in_cicciotti': fkey in cicc_features
    })

df = pd.DataFrame(data)

# Ordina per node_influence
df = df.sort_values('node_influence', ascending=False).reset_index(drop=True)

# Statistiche globali
total_node_inf = df['node_influence'].sum()
total_logit_inf = df['logit_influence'].sum()

# KPI principali
st.header("📊 KPI Globali")

col1, col2, col3, col4, col5 = st.columns(5)

with col1:
    st.metric(
        "Total Node Influence",
        f"{total_node_inf:.2f}",
        help="Somma dei valori assoluti di node_influence per tutte le feature"
    )

with col2:
    st.metric(
        "Total Logit Influence",
        f"{total_logit_inf:.2f}",
        help="Somma dei valori assoluti di logit_influence per tutte le feature"
    )

with col3:
    top_n_node_inf = df.head(top_n)['node_influence'].sum()
    top_n_coverage = (top_n_node_inf / total_node_inf) * 100
    st.metric(
        f"Top-{top_n} Coverage",
        f"{top_n_coverage:.1f}%",
        help=f"Percentuale di node_influence coperta dalle top-{top_n} feature"
    )

with col4:
    cicc_node_inf = df[df['in_cicciotti']]['node_influence'].sum()
    cicc_coverage = (cicc_node_inf / total_node_inf) * 100
    st.metric(
        "Cicciotti Coverage",
        f"{cicc_coverage:.1f}%",
        help="Percentuale di node_influence coperta dai cicciotti"
    )

with col5:
    probe_responsive = df[df['nuova_max_label_span'] >= probe_threshold]
    probe_node_inf = probe_responsive['node_influence'].sum()
    probe_coverage = (probe_node_inf / total_node_inf) * 100
    st.metric(
        "Probe-Responsive",
        f"{probe_coverage:.1f}%",
        help=f"Coverage di feature con nuova_max >= {probe_threshold}"
    )

# Grafici principali
st.header("📈 Visualizzazioni")

# ROW 1: Distribuzione coverage
col1, col2 = st.columns(2)

with col1:
    st.subheader("Distribuzione Node Influence")
    
    # Calcola coverage per vari top-N
    top_ns = [50, 100, 200, 500, 1000, 2000, 3000]
    coverage_data = []
    for n in top_ns:
        if n <= len(df):
            topn_inf = df.head(n)['node_influence'].sum()
            coverage = (topn_inf / total_node_inf) * 100
            coverage_data.append({'Top-N': n, 'Coverage (%)': coverage})
    
    cov_df = pd.DataFrame(coverage_data)
    
    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=cov_df['Top-N'],
        y=cov_df['Coverage (%)'],
        text=cov_df['Coverage (%)'].round(1),
        textposition='auto',
        marker_color='indianred'
    ))
    fig.update_layout(
        xaxis_title="Top-N Feature",
        yaxis_title="Coverage (%)",
        height=400,
        showlegend=False
    )
    st.plotly_chart(fig, use_container_width=True)
    
    st.info(f"Le top-{top_n} feature coprono **{top_n_coverage:.1f}%** della node_influence totale")

with col2:
    st.subheader("Coverage Breakdown")
    
    # Pie chart: Cicciotti vs Probe-responsive vs Resto
    cicc_only = df[df['in_cicciotti'] & (df['nuova_max_label_span'] < probe_threshold)]['node_influence'].sum()
    probe_only = df[(~df['in_cicciotti']) & (df['nuova_max_label_span'] >= probe_threshold)]['node_influence'].sum()
    both = df[df['in_cicciotti'] & (df['nuova_max_label_span'] >= probe_threshold)]['node_influence'].sum()
    neither = df[(~df['in_cicciotti']) & (df['nuova_max_label_span'] < probe_threshold)]['node_influence'].sum()
    
    fig = go.Figure(data=[go.Pie(
        labels=['Cicciotti + Probe', 'Solo Cicciotti', 'Solo Probe', 'Non interpretabili'],
        values=[both, cicc_only, probe_only, neither],
        marker_colors=['#2ecc71', '#3498db', '#f39c12', '#95a5a6'],
        hole=0.3,
        textinfo='label+percent'
    )])
    fig.update_layout(
        title=f"Composizione Node Influence (probe >= {probe_threshold})",
        height=400
    )
    st.plotly_chart(fig, use_container_width=True)
    
    st.success(f"**{both+cicc_only:.2f}** ({((both+cicc_only)/total_node_inf*100):.1f}%) nei Cicciotti")

# ROW 2: Scatter plot node_influence vs probe
st.subheader(f"Node Influence vs Probe Response (Top-{top_n})")

top_n_df = df.head(top_n).copy()
top_n_df['index_rank'] = range(1, len(top_n_df) + 1)

# Colora per stato cicciotti
top_n_df['status'] = top_n_df.apply(
    lambda row: 'In Cicciotti' if row['in_cicciotti'] else 'Non in Cicciotti',
    axis=1
)

fig = px.scatter(
    top_n_df,
    x='node_influence',
    y='nuova_max_label_span',
    color='status',
    hover_data=['feature', 'peak_token', 'layer'],
    color_discrete_map={'In Cicciotti': '#2ecc71', 'Non in Cicciotti': '#e74c3c'},
    labels={
        'node_influence': 'Node Influence',
        'nuova_max_label_span': 'Probe Response (nuova_max)',
        'status': 'Status'
    }
)

# Aggiungi linea threshold probe
fig.add_hline(
    y=probe_threshold,
    line_dash="dash",
    line_color="gray",
    annotation_text=f"Probe threshold = {probe_threshold}"
)

fig.update_layout(height=500)
st.plotly_chart(fig, use_container_width=True)

# Statistiche top-N
col1, col2, col3 = st.columns(3)

with col1:
    in_cicc = top_n_df['in_cicciotti'].sum()
    st.metric(f"Top-{top_n} in Cicciotti", f"{in_cicc}/{top_n}")

with col2:
    probe_resp = (top_n_df['nuova_max_label_span'] >= probe_threshold).sum()
    st.metric(f"Probe-responsive", f"{probe_resp}/{top_n}")

with col3:
    both_count = ((top_n_df['in_cicciotti']) & (top_n_df['nuova_max_label_span'] >= probe_threshold)).sum()
    st.metric("Entrambi", f"{both_count}/{top_n}")

# ROW 3: Distribuzione per layer
st.subheader("Distribuzione Node Influence per Layer")

layer_data = df.groupby('layer').agg({
    'node_influence': 'sum',
    'feature': 'count'
}).reset_index()
layer_data.columns = ['Layer', 'Total Node Influence', 'N Features']
layer_data = layer_data[layer_data['Layer'] >= 0]  # Rimuovi layer invalidi

fig = go.Figure()

fig.add_trace(go.Bar(
    x=layer_data['Layer'],
    y=layer_data['Total Node Influence'],
    name='Node Influence',
    marker_color='steelblue'
))

fig.update_layout(
    xaxis_title="Layer",
    yaxis_title="Total Node Influence",
    height=400,
    showlegend=True
)

st.plotly_chart(fig, use_container_width=True)

# Tabella top-N
st.header(f"📋 Top-{top_n} Feature per Node Influence")

# Filtra colonne per tabella
display_cols = ['feature', 'layer', 'node_influence', 'nuova_max_label_span', 
                'peak_token', 'mean_consistency', 'in_cicciotti']
table_df = top_n_df[display_cols].copy()

# Formatta numeri
table_df['node_influence'] = table_df['node_influence'].apply(lambda x: f"{x:.4f}")
table_df['nuova_max_label_span'] = table_df['nuova_max_label_span'].apply(lambda x: f"{x:.1f}")
table_df['mean_consistency'] = table_df['mean_consistency'].apply(lambda x: f"{x:.3f}")

# Colora righe cicciotti
def highlight_cicciotti(row):
    if row['in_cicciotti']:
        return ['background-color: #d5f4e6'] * len(row)
    else:
        return [''] * len(row)

st.dataframe(
    table_df.style.apply(highlight_cicciotti, axis=1),
    use_container_width=True,
    height=400
)

st.caption("💚 Righe verdi = feature nei cicciotti")

# Analisi dettagliata probe-responsive
st.header("🔬 Analisi Probe-Responsive")

probe_df = df[df['nuova_max_label_span'] >= probe_threshold].copy()

col1, col2 = st.columns(2)

with col1:
    st.metric("N Feature Probe-Responsive", len(probe_df))
    st.metric("Node Influence Totale", f"{probe_node_inf:.2f}")
    st.metric("% Totale Node Influence", f"{probe_coverage:.1f}%")

with col2:
    probe_in_cicc = probe_df['in_cicciotti'].sum()
    probe_not_cicc = len(probe_df) - probe_in_cicc
    
    st.metric("In Cicciotti", f"{probe_in_cicc}/{len(probe_df)}")
    st.metric("Non in Cicciotti", f"{probe_not_cicc}/{len(probe_df)}")
    
    # Percentuale probe-responsive nei cicciotti
    if probe_in_cicc > 0:
        pct = (probe_in_cicc / len(probe_df)) * 100
        st.metric("% Catturate da Cicciotti", f"{pct:.1f}%")

# Top probe-responsive NON in cicciotti
st.subheader(f"Top-20 Probe-Responsive NON nei Cicciotti (soglia >= {probe_threshold})")

not_in_cicc = probe_df[~probe_df['in_cicciotti']].sort_values('node_influence', ascending=False).head(20)

if len(not_in_cicc) > 0:
    display_cols_2 = ['feature', 'layer', 'node_influence', 'nuova_max_label_span', 'peak_token']
    table_df_2 = not_in_cicc[display_cols_2].copy()
    table_df_2['node_influence'] = table_df_2['node_influence'].apply(lambda x: f"{x:.4f}")
    table_df_2['nuova_max_label_span'] = table_df_2['nuova_max_label_span'].apply(lambda x: f"{x:.1f}")
    
    st.dataframe(table_df_2, use_container_width=True)
    
    st.warning("⚠️ Queste feature sono causalmente importanti E probe-responsive, ma non sono state catturate dai cicciotti")
else:
    st.success("✅ Tutte le feature probe-responsive sono state catturate dai cicciotti!")

# Export
st.header("💾 Export")

col1, col2 = st.columns(2)

with col1:
    # Export summary JSON
    summary = {
        'total_node_influence': float(total_node_inf),
        'total_features': len(df),
        f'top_{top_n}_coverage_pct': float(top_n_coverage),
        'cicciotti_coverage_pct': float(cicc_coverage),
        'probe_responsive_coverage_pct': float(probe_coverage),
        f'probe_threshold': float(probe_threshold),
        f'top_{top_n}_in_cicciotti': int(in_cicc),
        f'top_{top_n}_probe_responsive': int(probe_resp),
        'probe_responsive_total': len(probe_df),
        'probe_responsive_in_cicciotti': int(probe_in_cicc)
    }
    
    st.download_button(
        label="📥 Download summary.json",
        data=json.dumps(summary, indent=2),
        file_name='node_influence_summary.json',
        mime='application/json'
    )

with col2:
    # Export top-N CSV
    export_df = top_n_df[['feature', 'layer', 'node_influence', 'nuova_max_label_span', 
                          'peak_token', 'in_cicciotti']].copy()
    
    st.download_button(
        label=f"📥 Download top-{top_n}.csv",
        data=export_df.to_csv(index=False),
        file_name=f'top_{top_n}_node_influence.csv',
        mime='text/csv'
    )

# Info
st.sidebar.header("ℹ️ Info")
st.sidebar.write(f"**Total feature:** {len(df)}")
st.sidebar.write(f"**Feature in cicciotti:** {len(cicc_features)}")
st.sidebar.write(f"**N cicciotti:** {len(cicciotti)}")
st.sidebar.write("---")
st.sidebar.write("**Metriche:**")
st.sidebar.write("- `node_influence`: backward propagation da logits")
st.sidebar.write("- `nuova_max_label_span`: max attivazione su probe prompts")





