"""Utility per grafici riusabili con plotly e seaborn"""
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
import seaborn as sns
import matplotlib.pyplot as plt
import numpy as np
from typing import Dict, List


def plot_metrics_by_layer(df: pd.DataFrame, metric: str, title: str = None):
    """Violin plot metrica per layer"""
    fig = px.violin(df, x='layer', y=metric, box=True, points='outliers',
                    title=title or f'{metric} per layer')
    fig.update_layout(height=400)
    return fig


def plot_correlation_heatmap(df: pd.DataFrame, columns: List[str], title: str = None):
    """Heatmap correlazioni"""
    corr = df[columns].corr()
    fig = px.imshow(corr, text_auto='.2f', aspect='auto',
                    title=title or 'Correlazioni metriche',
                    color_continuous_scale='RdBu_r')
    fig.update_layout(height=500)
    return fig


def plot_token_distribution(df: pd.DataFrame, layer_col: str = 'layer', 
                            token_col: str = 'most_common_peak', top_n: int = 15):
    """Bar chart token distribution"""
    token_counts = df[token_col].value_counts().head(top_n)
    fig = px.bar(x=token_counts.index, y=token_counts.values,
                 labels={'x': 'Token', 'y': 'Count'},
                 title=f'Top {top_n} token più frequenti')
    fig.update_layout(height=400)
    return fig


def plot_scatter_2d(df: pd.DataFrame, x: str, y: str, color: str = None, 
                    title: str = None, hover_data: List[str] = None, labels: dict = None):
    """Scatter plot 2D con colore opzionale e labels personalizzate"""
    fig = px.scatter(df, x=x, y=y, color=color, hover_data=hover_data,
                     title=title or f'{y} vs {x}', labels=labels)
    fig.update_layout(height=500)
    return fig


def plot_coherence_history(coherence_history: List[float], title: str = None):
    """Line plot storia coerenza"""
    fig = go.Figure()
    fig.add_trace(go.Scatter(
        x=list(range(len(coherence_history))),
        y=coherence_history,
        mode='lines+markers',
        name='Coherence'
    ))
    fig.update_layout(
        title=title or 'Coherence history durante crescita',
        xaxis_title='Iterazione',
        yaxis_title='Coherence',
        height=400
    )
    return fig


def plot_member_distribution(members: List[str], personalities: Dict, 
                             attr: str = 'layer', title: str = None):
    """Distribuzione attributo tra membri"""
    values = []
    for m in members:
        if m in personalities:
            values.append(personalities[m].get(attr, 0))
    
    fig = px.histogram(x=values, nbins=20,
                       labels={'x': attr, 'y': 'Count'},
                       title=title or f'Distribuzione {attr} tra membri')
    fig.update_layout(height=400)
    return fig


def plot_heatmap_prompt_activation(validation_data: Dict, metric: str = 'n_active_members'):
    """Heatmap attivazione per prompt"""
    # Costruisci matrice
    data = []
    supernodes = []
    prompts = set()
    
    for sn_id, prompt_data in validation_data.items():
        supernodes.append(sn_id)
        for prompt_key, stats in prompt_data.items():
            prompts.add(prompt_key)
    
    prompts = sorted(prompts)
    matrix = []
    
    for sn_id in supernodes:
        row = []
        for prompt_key in prompts:
            val = validation_data[sn_id].get(prompt_key, {}).get(metric, 0)
            row.append(val)
        matrix.append(row)
    
    fig = px.imshow(matrix, x=prompts, y=supernodes,
                    labels={'x': 'Prompt', 'y': 'Supernodo', 'color': metric},
                    title=f'{metric} per supernodo e prompt',
                    aspect='auto')
    fig.update_layout(height=max(400, len(supernodes) * 20))
    return fig


def plot_cluster_sizes(clusters: Dict, title: str = None):
    """Istogramma dimensioni cluster"""
    sizes = [c['n_members'] for c in clusters.values()]
    fig = px.histogram(x=sizes, nbins=20,
                       labels={'x': 'N membri', 'y': 'Count'},
                       title=title or 'Distribuzione dimensioni cluster')
    fig.update_layout(height=400)
    return fig


def plot_coverage_comparison(before: float, after: float, title: str = None):
    """Bar chart coverage prima/dopo"""
    fig = go.Figure()
    fig.add_trace(go.Bar(x=['Before', 'After'], y=[before, after],
                         text=[f'{before:.1f}%', f'{after:.1f}%'],
                         textposition='outside'))
    fig.update_layout(
        title=title or 'Coverage comparison',
        yaxis_title='Coverage %',
        height=400,
        showlegend=False
    )
    return fig


def create_feature_neighborhood_graph(feature_key: str, personalities: Dict,
                                      max_neighbors: int = 10):
    """Grafico vicinato feature (top_parents/children)"""
    if feature_key not in personalities:
        return None
    
    p = personalities[feature_key]
    
    # Nodi
    nodes = [feature_key]
    edges_x = []
    edges_y = []
    node_text = [f"{feature_key}<br>token: {p.get('most_common_peak', '?')}"]
    
    # Parents
    for i, (parent_key, weight) in enumerate(p.get('top_parents', [])[:max_neighbors]):
        if parent_key in personalities:
            nodes.append(parent_key)
            pp = personalities[parent_key]
            node_text.append(f"{parent_key}<br>token: {pp.get('most_common_peak', '?')}<br>weight: {weight:.3f}")
    
    # Children
    for i, (child_key, weight) in enumerate(p.get('top_children', [])[:max_neighbors]):
        if child_key in personalities:
            nodes.append(child_key)
            cp = personalities[child_key]
            node_text.append(f"{child_key}<br>token: {cp.get('most_common_peak', '?')}<br>weight: {weight:.3f}")
    
    # Layout semplice: feature al centro
    n_nodes = len(nodes)
    if n_nodes == 1:
        return None
    
    angles = np.linspace(0, 2*np.pi, n_nodes-1, endpoint=False)
    x_pos = [0] + [np.cos(a) for a in angles]
    y_pos = [0] + [np.sin(a) for a in angles]
    
    fig = go.Figure()
    
    # Edge traces (da center a neighbors)
    for i in range(1, n_nodes):
        fig.add_trace(go.Scatter(
            x=[0, x_pos[i]], y=[0, y_pos[i]],
            mode='lines',
            line=dict(width=0.5, color='#888'),
            hoverinfo='none',
            showlegend=False
        ))
    
    # Node trace
    fig.add_trace(go.Scatter(
        x=x_pos, y=y_pos,
        mode='markers+text',
        marker=dict(size=[20 if i==0 else 10 for i in range(n_nodes)],
                   color=['red' if i==0 else 'lightblue' for i in range(n_nodes)]),
        text=[n.split('_')[-1] for n in nodes],  # solo feature_id
        textposition='top center',
        hovertext=node_text,
        hoverinfo='text',
        showlegend=False
    ))
    
    fig.update_layout(
        title=f'Vicinato causale di {feature_key}',
        showlegend=False,
        hovermode='closest',
        height=500,
        xaxis=dict(showgrid=False, zeroline=False, showticklabels=False),
        yaxis=dict(showgrid=False, zeroline=False, showticklabels=False)
    )
    
    return fig

