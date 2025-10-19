"""Utilità per visualizzazione interattiva dei grafi estratti"""
import pandas as pd
import plotly.express as px
import streamlit as st


def create_scatter_plot_with_filter(graph_data):
    """
    Crea uno scatter plot interattivo con filtro per cumulative influence
    
    Args:
        graph_data: Dizionario contenente i dati del grafo (nodes, metadata, etc)
    """
    if 'nodes' not in graph_data:
        st.warning("⚠️ Nessun nodo trovato nei dati del grafo")
        return
    
    # Estrai prompt_tokens dalla metadata per mappare ctx_idx -> token
    prompt_tokens = graph_data.get('metadata', {}).get('prompt_tokens', [])
    
    # Crea mapping ctx_idx -> token
    token_map = {i: token for i, token in enumerate(prompt_tokens)}
    
    # Estrai i nodi con ctx_idx, layer e influence
    # Mappa layer 'E' (embeddings) a -1, numeri restano numeri
    scatter_data = []
    for node in graph_data['nodes']:
        layer_val = node.get('layer', '')
        
        try:
            # Mappa embedding layer a -1
            if str(layer_val).upper() == 'E':
                layer_numeric = -1
            else:
                # Prova a convertire a int
                layer_numeric = int(layer_val)
            
            # Gestisci influence: usa valore minimo se mancante o zero
            influence_val = node.get('influence', 0)
            if influence_val is None or influence_val == 0:
                influence_val = 0.001  # Valore minimo per visibilità
            
            # Ottieni ctx_idx e mappa al token
            ctx_idx_val = node.get('ctx_idx', 0)
            token_str = token_map.get(ctx_idx_val, f"ctx_{ctx_idx_val}")
            
            scatter_data.append({
                'layer': layer_numeric,
                'ctx_idx': ctx_idx_val,
                'token': token_str,
                'id': node.get('node_id', ''),
                'influence': influence_val,
                'feature': node.get('feature', 0)
            })
        except (ValueError, TypeError):
            # Salta nodi con layer non valido
            continue
    
    if not scatter_data:
        st.warning("⚠️ Nessun nodo valido trovato per il plot")
        return
    
    scatter_df = pd.DataFrame(scatter_data)
    
    # Pulisci NaN e valori invalidi
    scatter_df['influence'] = scatter_df['influence'].fillna(0.001)
    scatter_df['influence'] = scatter_df['influence'].replace(0, 0.001)
    
    # === BINNING PER EVITARE SOVRAPPOSIZIONI (stile Neuronpedia) ===
    # Per ogni combinazione (ctx_idx, layer), distribuiamo i nodi su sub-colonne
    import numpy as np
    
    bin_width = 0.3  # Larghezza della sub-colonna
    scatter_df['sub_column'] = 0
    
    for (ctx, layer), group in scatter_df.groupby(['ctx_idx', 'layer']):
        n_nodes = len(group)
        if n_nodes > 1:
            # Calcola quante sub-colonne servono (max 5 per evitare troppa dispersione)
            n_bins = min(5, int(np.ceil(np.sqrt(n_nodes))))
            # Assegna ogni nodo a una sub-colonna
            for i, idx in enumerate(group.index):
                sub_col = (i % n_bins) - (n_bins - 1) / 2  # Centra attorno a 0
                scatter_df.at[idx, 'sub_column'] = sub_col * bin_width
    
    # Applica offset per creare sub-colonne
    scatter_df['ctx_idx_display'] = scatter_df['ctx_idx'] + scatter_df['sub_column']
    
    # === FILTRO PER CUMULATIVE INFLUENCE ===
    st.markdown("### 🎚️ Filtra Features per Influence")
    st.write("""
    Seleziona la percentuale di cumulative influence contribution per cui vuoi filtrare le features. 
    Le features sono ordinate per influence (valore assoluto) decrescente.
    """)
    
    cumulative_contribution = st.slider(
        "Cumulative Influence Contribution (%)",
        min_value=1,
        max_value=100,
        value=100,
        step=1,
        key="cumulative_slider_main",  # Key univoca
        help="Percentuale di contributo cumulativo di influence da mantenere. Riduci per vedere solo i nodi più influenti."
    ) / 100.0
    
    # Filtra per cumulative influence
    num_total = len(scatter_df)
    
    if cumulative_contribution < 1.0:
        # Ordina per influence decrescente
        scatter_sorted = scatter_df.sort_values('influence', ascending=False, key=abs)
        
        # Calcola influence cumulativa
        total_influence = scatter_sorted['influence'].abs().sum()
        
        if total_influence > 0:
            scatter_sorted['cumulative'] = scatter_sorted['influence'].abs().cumsum() / total_influence
            scatter_filtered = scatter_sorted[scatter_sorted['cumulative'] <= cumulative_contribution]
            
            # Soglia di influence (ultimo valore incluso)
            if len(scatter_filtered) > 0:
                threshold_influence = scatter_filtered['influence'].abs().min()
            else:
                threshold_influence = 0.0
        else:
            scatter_filtered = scatter_sorted
            threshold_influence = 0.0
    else:
        scatter_filtered = scatter_df
        threshold_influence = scatter_df['influence'].abs().min()
    
    num_selected = len(scatter_filtered)
    
    # Mostra statistiche filtro
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Features Totali", num_total)
    
    with col2:
        st.metric("Features Selezionate", num_selected)
    
    with col3:
        pct = (num_selected / num_total * 100) if num_total > 0 else 0
        st.metric("% Features", f"{pct:.1f}%")
    
    with col4:
        st.metric("Soglia Influence", f"{threshold_influence:.6f}")
    
    # Conta embeddings (layer -1) e features nel dataset filtrato
    n_embeddings = len(scatter_filtered[scatter_filtered['layer'] == -1])
    n_features = len(scatter_filtered[scatter_filtered['layer'] >= 0])
    st.info(f"📊 Visualizzando {len(scatter_filtered)} nodi filtrati: {n_embeddings} embeddings (layer -1) + {n_features} features")
    
    # Usa il dataframe filtrato per il plot
    scatter_df = scatter_filtered
    
    # Ricalcola le sub-colonne per il dataset filtrato
    scatter_df = scatter_df.copy()
    scatter_df['sub_column'] = 0
    
    for (ctx, layer), group in scatter_df.groupby(['ctx_idx', 'layer']):
        n_nodes = len(group)
        if n_nodes > 1:
            n_bins = min(5, int(np.ceil(np.sqrt(n_nodes))))
            for i, idx in enumerate(group.index):
                sub_col = (i % n_bins) - (n_bins - 1) / 2
                scatter_df.at[idx, 'sub_column'] = sub_col * bin_width
    
    scatter_df['ctx_idx_display'] = scatter_df['ctx_idx'] + scatter_df['sub_column']
    
    # Applica scala logaritmica per il raggio (maggiore differenziazione)
    # Usa log(influence + 1) con un fattore moltiplicativo per amplificare le differenze
    scatter_df['influence_log'] = np.log10(scatter_df['influence'] + 1) ** 2 * 100
    
    # Crea scatter plot con sub-colonne
    fig = px.scatter(
        scatter_df,
        x='ctx_idx_display',  # Usa posizione con offset
        y='layer',
        size='influence_log',  # Usa scala logaritmica
        color_discrete_sequence=['#808080'],  # Grigio
        labels={
            'id': 'Node ID',
            'ctx_idx_display': 'Context Position',
            'ctx_idx': 'ctx_idx',
            'layer': 'Layer',
            'influence': 'Influence',
            'token': 'Token',
            'feature': 'Feature'
        },
        title='Distribuzione Features per Layer e Context Position',
        hover_data={
            'ctx_idx': True,
            'token': True,
            'layer': True,
            'id': True,
            'feature': True,
            'influence': ':.4f',
            'ctx_idx_display': False,  # Nascondi la posizione modificata
            'influence_log': False  # Nascondi il valore logaritmico
        }
    )
    
    # Personalizza il layout con alta trasparenza e outline marcato
    fig.update_traces(
        marker=dict(
            sizemode='area',
            sizeref=2.*max(scatter_df['influence_log'])/(50.**2),  # Divisore più alto = cerchi più piccoli
            sizemin=0.05,  # Dimensione minima ridotta
            opacity=0.2,  # Trasparenza alta
            line=dict(width=2, color='#d6d0d0')  # Contorno spesso e visibile
        )
    )
    
    # Crea tick labels personalizzate per l'asse x (ctx_idx: token)
    unique_ctx = sorted(scatter_df['ctx_idx'].unique())
    tick_labels = [f"{ctx}: {token_map.get(ctx, '')}" for ctx in unique_ctx]
    
    fig.update_layout(
        template='plotly_white',
        height=600,
        showlegend=False,
        xaxis=dict(
            gridcolor='lightgray',
            tickmode='array',
            tickvals=unique_ctx,
            ticktext=tick_labels,
            tickangle=-45
        ),
        yaxis=dict(gridcolor='lightgray')
    )
    
    st.plotly_chart(fig, use_container_width=True)
    
    # === GRAFICO DISTRIBUZIONE CUMULATIVA INFLUENCE ===
    st.markdown("### 📈 Analisi Distribuzione Influence")
    
    try:
        # Crea curva cumulativa
        # Riordina per influence decrescente
        sorted_df = scatter_filtered.sort_values('influence', ascending=False, key=abs).reset_index(drop=True)
        
        if len(sorted_df) == 0:
            st.warning("⚠️ Nessun dato disponibile per la curva cumulativa")
            return
        
        sorted_df['rank'] = range(1, len(sorted_df) + 1)
        sorted_df['rank_pct'] = sorted_df['rank'] / len(sorted_df) * 100
        
        # Calcola influence cumulativa
        total_inf = sorted_df['influence'].abs().sum()
        
        if total_inf == 0:
            st.warning("⚠️ Influence totale è zero, impossibile calcolare la distribuzione")
            return
        
        sorted_df['cumulative_influence'] = sorted_df['influence'].abs().cumsum()
        sorted_df['cumulative_influence_pct'] = sorted_df['cumulative_influence'] / total_inf * 100
        
        # Crea due subplot: curva cumulativa + histogram
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        
        fig_dist = make_subplots(
            rows=1, cols=2,
            subplot_titles=('Curva Cumulativa Influence', 'Distribuzione Influence (Log Scale)'),
            horizontal_spacing=0.12
        )
        
        # Plot 1: Curva cumulativa
        fig_dist.add_trace(
            go.Scatter(
                x=sorted_df['rank_pct'],
                y=sorted_df['cumulative_influence_pct'],
                mode='lines',
                name='Cumulativa',
                line=dict(color='#4CAF50', width=3),
                hovertemplate='<b>Top %{x:.1f}% nodi</b><br>Cumulativa: %{y:.1f}% influence<extra></extra>'
            ),
            row=1, col=1
        )
        
        # Aggiungi marker per lo slider corrente
        # Usa direttamente i valori del dataset filtrato
        current_pct = 100.0  # Stiamo visualizzando il 100% del dataset filtrato
        current_cum_inf = 100.0  # La cumulativa del dataset filtrato arriva sempre al 100%
        
        fig_dist.add_trace(
            go.Scatter(
                x=[current_pct],
                y=[current_cum_inf],
                mode='markers',
                name='Slider Corrente',
                marker=dict(size=15, color='#FF5722', symbol='diamond', line=dict(width=2, color='white')),
                hovertemplate=f'<b>Slider: {cumulative_contribution*100:.0f}%</b><br>Nodi: {current_pct:.1f}%<br>Influence: {current_cum_inf:.1f}%<extra></extra>'
            ),
            row=1, col=1
        )
        
        # Linee di riferimento (80/20, 90/10, 95/5)
        for pct, label in [(80, '80%'), (90, '90%'), (95, '95%')]:
            fig_dist.add_hline(y=pct, line_dash="dash", line_color="gray", opacity=0.5, row=1, col=1)
            fig_dist.add_annotation(x=100, y=pct, text=label, showarrow=False, xanchor='left', row=1, col=1)
        
        # Plot 2: Histogram (log scale)
        fig_dist.add_trace(
            go.Histogram(
                x=sorted_df['influence'],
                nbinsx=50,
                name='Distribuzione',
                marker=dict(color='#2196F3', opacity=0.7),
                hovertemplate='Influence: %{x:.4f}<br>Count: %{y}<extra></extra>'
            ),
            row=1, col=2
        )
        
        # Layout
        fig_dist.update_xaxes(title_text="% Nodi (ordinati per influence)", row=1, col=1)
        fig_dist.update_yaxes(title_text="% Influence Cumulativa", row=1, col=1)
        fig_dist.update_xaxes(title_text="Influence (log scale)", type="log", row=1, col=2)
        fig_dist.update_yaxes(title_text="Conteggio", row=1, col=2)
        
        fig_dist.update_layout(
            height=400,
            showlegend=True,
            template='plotly_white',
            legend=dict(x=0.02, y=0.98, xanchor='left', yanchor='top')
        )
        
        st.plotly_chart(fig_dist, use_container_width=True)
        
        # Statistiche chiave
        col1, col2, col3, col4 = st.columns(4)
        
        # Trova percentili chiave con controlli sicuri
        top_10_idx = int(len(sorted_df) * 0.1)
        top_20_idx = int(len(sorted_df) * 0.2)
        
        top_10_pct = sorted_df['cumulative_influence_pct'].iloc[top_10_idx] if top_10_idx < len(sorted_df) else 0
        top_20_pct = sorted_df['cumulative_influence_pct'].iloc[top_20_idx] if top_20_idx < len(sorted_df) else 0
        
        with col1:
            st.metric("Top 10% nodi", f"{top_10_pct:.1f}% influence")
        with col2:
            st.metric("Top 20% nodi", f"{top_20_pct:.1f}% influence")
        with col3:
            gini = 1 - 2 * np.trapz(sorted_df['cumulative_influence_pct'] / 100, sorted_df['rank_pct'] / 100)
            st.metric("Gini Coefficient", f"{gini:.3f}", help="0 = uguale, 1 = concentrato")
        with col4:
            median_inf = sorted_df['influence'].abs().median()
            st.metric("Median Influence", f"{median_inf:.4f}")
    
    except Exception as e:
        st.error(f"❌ Errore nella creazione del grafico di distribuzione: {str(e)}")
        import traceback
        st.code(traceback.format_exc())

