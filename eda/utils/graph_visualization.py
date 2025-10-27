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
    skipped_nodes = []  # Per logging nodi problematici
    
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
            
            # Estrai feature_index dal node_id SOLO per nodi SAE
            # Formato SAE: "layer_featureIndex_sequence" → es. "24_79427_7"
            # Altri tipi (MLP error, embeddings, logits) usano formati diversi
            node_id = node.get('node_id', '')
            node_type = node.get('feature_type', '')
            feature_idx = None
            
            if node_type == 'cross layer transcoder':
                # Solo per nodi SAE: estrai feature_idx da node_id
                if node_id and '_' in node_id:
                    parts = node_id.split('_')
                    if len(parts) >= 2:
                        try:
                            # Il secondo elemento è il feature_index
                            feature_idx = int(parts[1])
                        except (ValueError, IndexError):
                            pass
                
                # Se il parsing fallisce per un nodo SAE, skippa!
                if feature_idx is None:
                    skipped_nodes.append(f"layer={layer_val}, node_id={node_id}, type=SAE")
                    continue  # Salta nodi SAE malformati
            else:
                # Per nodi non-SAE (embeddings, logits, MLP error, ecc.):
                # usa -1 come placeholder - NON estrarre da node_id!
                feature_idx = -1
            
            scatter_data.append({
                'layer': layer_numeric,
                'ctx_idx': ctx_idx_val,
                'token': token_str,
                'id': node_id,
                'influence': influence_val,
                'feature': feature_idx  # Ora contiene l'indice corretto o -1 per non-features!
            })
        except (ValueError, TypeError):
            # Salta nodi con layer non valido
            continue
    
    # Log nodi skippati se ce ne sono
    if skipped_nodes:
        st.warning(f"⚠️ {len(skipped_nodes)} nodi feature con node_id malformato sono stati skippati")
        with st.expander("Dettagli nodi skippati"):
            for node_info in skipped_nodes[:10]:  # Mostra solo i primi 10
                st.text(node_info)
            if len(skipped_nodes) > 10:
                st.text(f"... e altri {len(skipped_nodes) - 10} nodi")
    
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
    st.markdown("### 🎚️ Filtra Features per Cumulative Influence Coverage")
    
    # Calcola il massimo valore di influence presente nei dati
    max_influence = scatter_df['influence'].max()
    
    # Mostra il node_threshold usato durante la generazione (se disponibile)
    node_threshold_used = graph_data.get('metadata', {}).get('node_threshold', None)
    
    if node_threshold_used is not None:
        st.info(f"""
        **Il campo `influence` è la copertura cumulativa (0-{max_influence:.2f})** calcolata dal pruning del circuit tracer.Quando i nodi sono ordinati per influenza decrescente, un nodo con `influence=0.65` significa che 
        **fino a quel nodo** viene coperto il 65% dell'influenza totale.
        """)
    else:
        st.info(f"""
        **Il campo `influence` è la copertura cumulativa (0-{max_influence:.2f})** calcolata dal pruning del circuit tracer.
        
        Quando i nodi sono ordinati per influenza decrescente, un nodo con `influence=0.65` significa che 
        **fino a quel nodo** viene coperto il 65% dell'influenza totale.
        """)
    
    cumulative_threshold = st.slider(
        "Cumulative Influence Threshold",
        min_value=0.0,
        max_value=float(max_influence),
        value=float(max_influence),
        step=0.01,
        key="cumulative_slider_main",
        help=f"Mantieni solo i nodi con influence ≤ threshold. Range: 0.0 - {max_influence:.2f} (max nei dati)"
    )
    
    # Checkbox per filtrare reconstruction error nodes
    filter_error_nodes = st.checkbox(
        "Escludi Reconstruction Error Nodes (feature = -1)",
        value=False,
        key="filter_error_checkbox",
        help="I reconstruction error nodes rappresentano la parte del modello non spiegata dalle features SAE"
    )
    
    # Filtra usando direttamente il campo influence dal JSON
    num_total = len(scatter_df)
    
    # Identifica reconstruction error nodes (feature = -1) - KPI verrà calcolato dopo
    is_error_node = scatter_df['feature'] == -1
    n_error_total = is_error_node.sum()
    pct_error_nodes = (n_error_total / num_total * 100) if num_total > 0 else 0
    
    # Identifica embeddings e logits da mantenere sempre
    is_embedding = scatter_df['layer'] == -1  # Layer 'E' mappato a -1
    # Logits hanno layer massimo (es. layer 27 per gemma-2-2b con 26 layer + 1)
    max_layer = scatter_df['layer'].max()
    is_logit = scatter_df['layer'] == max_layer
    
    # Applica filtri combinati: influence threshold + error nodes (se checkbox attivo)
    if cumulative_threshold < 1.0:
        mask_influence = scatter_df['influence'] <= cumulative_threshold
        mask_keep = mask_influence | is_embedding | is_logit
    else:
        mask_keep = pd.Series([True] * len(scatter_df), index=scatter_df.index)
    
    # Applica filtro error nodes se checkbox attivo
    if filter_error_nodes:
        # Escludi error nodes (feature = -1), ma mantieni embeddings/logits
        mask_not_error = (scatter_df['feature'] != -1) | is_embedding | is_logit
        mask_keep = mask_keep & mask_not_error
    
    scatter_filtered = scatter_df[mask_keep].copy()
    
    # Soglia di influence effettiva (max influence tra i nodi filtrati, escludendo embeddings/logits)
    feature_nodes_filtered = scatter_filtered[~((scatter_filtered['layer'] == -1) | (scatter_filtered['layer'] == max_layer))]
    if len(feature_nodes_filtered) > 0:
        threshold_influence = feature_nodes_filtered['influence'].max()
    else:
        threshold_influence = 0.0
    
    num_selected = len(scatter_filtered)
    
    # Conta embeddings, features e error nodes nel dataset filtrato (prima di rimuovere logit)
    is_embedding_filtered = scatter_filtered['layer'] == -1
    max_layer_filtered = scatter_filtered['layer'].max()
    is_logit_filtered = scatter_filtered['layer'] == max_layer_filtered
    is_error_filtered = scatter_filtered['feature'] == -1
    
    n_embeddings = len(scatter_filtered[is_embedding_filtered])
    n_error_nodes = len(scatter_filtered[is_error_filtered & ~is_embedding_filtered & ~is_logit_filtered])
    n_features = len(scatter_filtered[~(is_embedding_filtered | is_logit_filtered | is_error_filtered)])
    n_logits_excluded = len(scatter_filtered[is_logit_filtered])
    n_error_excluded = n_error_total - n_error_nodes if filter_error_nodes else 0
    
    # Mostra statistiche filtro
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Nodi Totali", num_total)
    
    with col2:
        st.metric("Nodi Selezionati", num_selected)
    
    with col3:
        pct = (num_selected / num_total * 100) if num_total > 0 else 0
        st.metric("% Nodi", f"{pct:.1f}%")
    
    with col4:
        st.metric("Soglia Influence", f"{threshold_influence:.6f}")
    

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
    
    # Calcola node_influence (marginal influence) per il raggio dei cerchi/quadrati
    # Se non presente nel JSON (vecchi grafi), calcoliamo al volo
    if 'node_influence' not in scatter_df.columns:
        # Calcola marginal influence come differenza tra cumulative consecutive
        df_sorted_by_cumul = scatter_df.sort_values('influence').reset_index(drop=True)
        df_sorted_by_cumul['node_influence'] = df_sorted_by_cumul['influence'].diff()
        df_sorted_by_cumul.loc[0, 'node_influence'] = df_sorted_by_cumul.loc[0, 'influence']
        
        # Remap al dataframe originale
        node_id_to_marginal = dict(zip(df_sorted_by_cumul['id'], df_sorted_by_cumul['node_influence']))
        scatter_df['node_influence'] = scatter_df['id'].map(node_id_to_marginal).fillna(scatter_df['influence'])
    
    # CALCOLA KPI ERROR NODES (ora che node_influence è disponibile)
    # Usa scatter_df (dataset completo prima della rimozione logit) per i KPI globali
    is_error_in_complete = scatter_df['feature'] == -1
    total_node_influence = scatter_df['node_influence'].sum()
    error_node_influence = scatter_df[is_error_in_complete]['node_influence'].sum()
    pct_error_influence = (error_node_influence / total_node_influence * 100) if total_node_influence > 0 else 0
    
    # Mostra KPI reconstruction error nodes (prima del plot)
    col1, col2 = st.columns(2)
    with col1:
        st.metric(
            "% Nodi Error", 
            f"{pct_error_nodes:.1f}%",
            help=f"{n_error_total} nodi su {num_total} totali sono reconstruction error (feature=-1)"
        )
    with col2:
        st.metric(
            "% Node Influence (Error)", 
            f"{pct_error_influence:.1f}%",
            help=f"I reconstruction error nodes contribuiscono al {pct_error_influence:.1f}% della node_influence totale"
        )
    
        # Messaggio info con breakdown
    info_parts = [f"{n_embeddings} embeddings", f"{n_features} features"]
    if n_error_nodes > 0:
        info_parts.append(f"{n_error_nodes} error nodes")
    
    excluded_parts = [f"{n_logits_excluded} logits"]
    if n_error_excluded > 0:
        excluded_parts.append(f"{n_error_excluded} error nodes")
    
    st.info(f"📊 Visualizzando {n_embeddings + n_features + n_error_nodes} nodi: {', '.join(info_parts)} ({', '.join(excluded_parts)} esclusi)")
    
    
    # Identifica i 2 gruppi: embeddings e features (escludi logits)
    is_embedding_group = scatter_df['layer'] == -1
    max_layer = scatter_df['layer'].max()
    is_logit_group = scatter_df['layer'] == max_layer
    is_feature_group = ~(is_embedding_group | is_logit_group)
    
    # RIMUOVI I LOGIT dal dataset
    scatter_df = scatter_df[~is_logit_group].copy()
    
    # Ricalcola le maschere dopo il filtro
    is_embedding_group = scatter_df['layer'] == -1
    is_feature_group = scatter_df['layer'] != -1
    
    # Aggiungi colonna per il tipo di nodo (solo 2 tipi ora)
    scatter_df['node_type'] = 'feature'
    scatter_df.loc[is_embedding_group, 'node_type'] = 'embedding'
    
    # Calcola influence_log normalizzato per gruppo con formula più aggressiva
    # Ogni gruppo ha la sua scala basata sul max del gruppo
    scatter_df['influence_log'] = 0.0
    
    for group_name, group_mask in [('embedding', is_embedding_group), 
                                     ('feature', is_feature_group)]:
        if group_mask.sum() > 0:
            group_data = scatter_df[group_mask]['node_influence'].abs()
            # Normalizza rispetto al max del gruppo
            max_in_group = group_data.max()
            if max_in_group > 0:
                normalized = group_data / max_in_group
                # Formula più aggressiva: usa power 3 per estremizzare le differenze
                # normalized^3 rende i valori bassi molto più piccoli e i valori alti più grandi
                # Moltiplica per 1000 per avere un buon range di grandezza
                scatter_df.loc[group_mask, 'influence_log'] = (normalized ** 3) * 1000 + 10
            else:
                scatter_df.loc[group_mask, 'influence_log'] = 10  # Valore minimo default
    
    # Crea scatter plot con simboli diversi per gruppo (solo embeddings e features)
    symbol_map = {
        'embedding': 'square',
        'feature': 'circle'
    }
    
    fig = px.scatter(
        scatter_df,
        x='ctx_idx_display',  # Usa posizione con offset
        y='layer',
        size='influence_log',  # Usa scala aggressiva (power 3) normalizzata per gruppo
        symbol='node_type',  # Simbolo diverso per tipo
        symbol_map=symbol_map,
        color='node_type',  # Colore diverso per tipo
        color_discrete_map={
            'embedding': '#4CAF50',  # Verde per embeddings
            'feature': '#808080'     # Grigio per features
        },
        labels={
            'id': 'Node ID',
            'ctx_idx_display': 'Context Position',
            'ctx_idx': 'ctx_idx',
            'layer': 'Layer',
            'influence': 'Cumulative Influence',
            'node_influence': 'Node Influence',
            'node_type': 'Node Type',
            'token': 'Token',
            'feature': 'Feature'
        },
        title='Features per Layer e Position (grandezza: node_influence^3 normalizzata per gruppo)',
        hover_data={
            'ctx_idx': True,
            'token': True,
            'layer': True,
            'node_type': True,
            'id': True,
            'feature': True,
            'node_influence': ':.6f',  # Influenza marginale (grandezza simbolo)
            'influence': ':.4f',  # Cumulative influence (filtro slider)
            'ctx_idx_display': False,  # Nascondi la posizione modificata
            'influence_log': False  # Nascondi il valore logaritmico
        }
    )
    
    # Personalizza il layout con alta trasparenza e outline marcato
    # Applica a tutte le tracce (embeddings, features, logits)
    max_influence_log = scatter_df['influence_log'].max()
    
    fig.update_traces(
        marker=dict(
            sizemode='area',
            sizeref=2.*max_influence_log/(50.**2) if max_influence_log > 0 else 1,
            sizemin=2,  # Dimensione minima
            opacity=0.3,  # Trasparenza medio-alta
            line=dict(width=1.5, color='white')  # Contorno bianco per distinguere
        )
    )
    
    # Crea tick labels personalizzate per l'asse x (ctx_idx: token)
    unique_ctx = sorted(scatter_df['ctx_idx'].unique())
    tick_labels = [f"{ctx}: {token_map.get(ctx, '')}" for ctx in unique_ctx]
    
    fig.update_layout(
        template='plotly_white',
        height=600,
        showlegend=True,  # Mostra legenda per i 3 gruppi
        legend=dict(
            title="Tipo Nodo",
            orientation="v",
            yanchor="top",
            y=0.99,
            xanchor="left",
            x=0.99,
            bgcolor="rgba(255,255,255,0.8)"
        ),
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
    
    # Mostra statistiche per gruppo
    with st.expander("📊 Statistiche per Gruppo (Normalizzazione Grandezza)", expanded=False):
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("**🟩 Embeddings (quadrati verdi)**")
            emb_data = scatter_df[scatter_df['node_type'] == 'embedding']
            if len(emb_data) > 0:
                st.metric("Nodi", len(emb_data))
                st.metric("Max node_influence", f"{emb_data['node_influence'].max():.6f}")
                st.metric("Mean node_influence", f"{emb_data['node_influence'].mean():.6f}")
                st.metric("Min node_influence", f"{emb_data['node_influence'].min():.6f}")
            else:
                st.info("Nessun embedding nel dataset filtrato")
        
        with col2:
            st.markdown("**⚪ Features (cerchi grigi)**")
            feat_data = scatter_df[scatter_df['node_type'] == 'feature']
            if len(feat_data) > 0:
                st.metric("Nodi", len(feat_data))
                st.metric("Max node_influence", f"{feat_data['node_influence'].max():.6f}")
                st.metric("Mean node_influence", f"{feat_data['node_influence'].mean():.6f}")
                st.metric("Min node_influence", f"{feat_data['node_influence'].min():.6f}")
            else:
                st.info("Nessuna feature nel dataset filtrato")
        
        st.info("""
        💡 **Formula grandezza**: `grandezza = (node_influence_normalizzata)³ × 1000 + 10`
        
        La dimensione è normalizzata **per gruppo** e usa **power 3** per estremizzare le differenze:
        - Un nodo con 50% del max → grandezza = 0.5³ = 12.5% (molto più piccolo)
        - Un nodo con 80% del max → grandezza = 0.8³ = 51.2%
        - Un nodo con 100% del max → grandezza = 1.0³ = 100%
        
        I 2 gruppi (embeddings e features) hanno scale indipendenti.
        Nota di cautela: nel JSON il campo “influence” è la cumulativa pre-pruning, quindi stimare la node_influence come differenza tra cumulativi consecutivi è solo una proxy normalizzata (da rinormalizzare sul set corrente), perché il grafo può essere già potata topologicamente e la selezione non coincide con un prefisso contiguo dei nodi ordinati.
        """)
    
    # === GRAFICO PARETO: NODE INFLUENCE (solo features, no embeddings/logits) ===
    st.markdown("### 📈 Analisi Pareto Node Influence (solo Features)")
    
    try:
        # Filtra solo features (scatter_df ha già rimosso i logit e ha node_type)
        features_only = scatter_df[scatter_df['node_type'] == 'feature'].copy()
        
        if len(features_only) == 0:
            st.warning("⚠️ Nessuna feature trovata nel dataset filtrato")
            return
        
        # Ordina per node_influence decrescente
        sorted_df = features_only.sort_values('node_influence', ascending=False).reset_index(drop=True)
        
        # Calcola rank e percentile
        sorted_df['rank'] = range(1, len(sorted_df) + 1)
        sorted_df['rank_pct'] = sorted_df['rank'] / len(sorted_df) * 100
        
        # Calcola node_influence cumulativa (somma progressiva)
        total_node_inf = sorted_df['node_influence'].sum()
        
        if total_node_inf == 0:
            st.warning("⚠️ Total Node influence is 0")
            return
        
        sorted_df['cumulative_node_influence'] = sorted_df['node_influence'].cumsum()
        sorted_df['cumulative_node_influence_pct'] = sorted_df['cumulative_node_influence'] / total_node_inf * 100
        
        # Crea grafico Pareto con doppio asse Y
        import plotly.graph_objects as go
        from plotly.subplots import make_subplots
        
        # Crea subplot con asse Y secondario
        fig_pareto = make_subplots(specs=[[{"secondary_y": True}]])
        
        # Barra: node_influence individuale (limita a primi 100 nodi per leggibilità)
        display_limit = min(100, len(sorted_df))
        
        fig_pareto.add_trace(
            go.Bar(
                x=sorted_df['rank'][:display_limit],
                y=sorted_df['node_influence'][:display_limit],
                name='Node Influence',
                marker=dict(color='#2196F3', opacity=0.6),
                hovertemplate='<b>Rank: %{x}</b><br>Node Influence: %{y:.6f}<extra></extra>'
            ),
            secondary_y=False
        )
        
        # Linea: cumulativa % (usa tutti i nodi)
        fig_pareto.add_trace(
            go.Scatter(
                x=sorted_df['rank_pct'],
                y=sorted_df['cumulative_node_influence_pct'],
                mode='lines+markers',
                name='Cumulative %',
                line=dict(color='#FF5722', width=3),
                marker=dict(size=4),
                hovertemplate='<b>Top %{x:.1f}% features</b><br>Cumulative: %{y:.1f}%<extra></extra>'
            ),
            secondary_y=True
        )
        
        # Linee di riferimento Pareto (80%, 90%, 95%)
        for pct, label in [(80, '80%'), (90, '90%'), (95, '95%')]:
            fig_pareto.add_hline(
                y=pct, 
                line_dash="dash", 
                line_color="gray", 
                opacity=0.5,
                secondary_y=True
            )
            fig_pareto.add_annotation(
                x=100, 
                y=pct, 
                text=label, 
                showarrow=False, 
                xanchor='left',
                yref='y2'
            )
        
        # Trova il "knee" (punto dove la cumulativa raggiunge 80%)
        knee_idx = (sorted_df['cumulative_node_influence_pct'] >= 80).idxmax()
        knee_rank_pct = sorted_df.loc[knee_idx, 'rank_pct']
        knee_cumul = sorted_df.loc[knee_idx, 'cumulative_node_influence_pct']
        
        fig_pareto.add_trace(
            go.Scatter(
                x=[knee_rank_pct],
                y=[knee_cumul],
                mode='markers',
                name='Knee (80%)',
                marker=dict(size=15, color='#4CAF50', symbol='diamond', line=dict(width=2, color='white')),
                hovertemplate=f'<b>Knee Point</b><br>Top {knee_rank_pct:.1f}% features<br>Cumulativa: {knee_cumul:.1f}%<extra></extra>',
                showlegend=True
            ),
            secondary_y=True
        )
        
        # Layout
        fig_pareto.update_xaxes(title_text="Rank % Features (by descending node_influence)")
        fig_pareto.update_yaxes(title_text="Node Influence (individual)", secondary_y=False)
        fig_pareto.update_yaxes(title_text="Cumulative % Node Influence", secondary_y=True, range=[0, 105])
        
        fig_pareto.update_layout(
            height=500,
            showlegend=True,
            template='plotly_white',
            legend=dict(x=0.02, y=0.98, xanchor='left', yanchor='top'),
            title="Grafico Pareto: Node Influence delle Features"
        )
        
        st.plotly_chart(fig_pareto, use_container_width=True)
        
        # Statistiche chiave Pareto
        st.markdown("#### 📊 Statistiche Pareto (Node Influence)")
        
        col1, col2, col3, col4 = st.columns(4)
        
        # Trova percentili chiave
        top_10_idx = max(0, int(len(sorted_df) * 0.1))
        top_20_idx = max(0, int(len(sorted_df) * 0.2))
        top_50_idx = max(0, int(len(sorted_df) * 0.5))
        
        top_10_pct = sorted_df['cumulative_node_influence_pct'].iloc[top_10_idx] if top_10_idx < len(sorted_df) else 0
        top_20_pct = sorted_df['cumulative_node_influence_pct'].iloc[top_20_idx] if top_20_idx < len(sorted_df) else 0
        top_50_pct = sorted_df['cumulative_node_influence_pct'].iloc[top_50_idx] if top_50_idx < len(sorted_df) else 0
        
        with col1:
            st.metric("Top 10% features", f"{top_10_pct:.1f}% node_influence", 
                     help=f"Le prime {int(len(sorted_df)*0.1)} features più influenti coprono {top_10_pct:.1f}% dell'influenza totale")
        with col2:
            st.metric("Top 20% features", f"{top_20_pct:.1f}% node_influence",
                     help=f"Le prime {int(len(sorted_df)*0.2)} features più influenti coprono {top_20_pct:.1f}% dell'influenza totale")
        with col3:
            st.metric("Top 50% features", f"{top_50_pct:.1f}% node_influence",
                     help=f"Le prime {int(len(sorted_df)*0.5)} features più influenti coprono {top_50_pct:.1f}% dell'influenza totale")
        with col4:
            # Gini coefficient
            gini = 1 - 2 * np.trapz(sorted_df['cumulative_node_influence_pct'] / 100, sorted_df['rank_pct'] / 100)
            st.metric("Gini Coefficient", f"{gini:.3f}", help="0 = distribuzione uguale, 1 = molto concentrata")
        
        # Info sul knee point e suggerimento threshold
        # sorted_df[knee_idx] ci dà la riga del knee point
        knee_cumul_threshold = sorted_df.loc[knee_idx, 'influence'] if 'influence' in sorted_df.columns else scatter_df['influence'].max()
        
        st.success(f"""
        🎯 **Knee Point (80%)**: Le prime **{knee_rank_pct:.1f}%** delle features ({int(len(sorted_df) * knee_rank_pct / 100)} nodi) 
        coprono l'**80%** della node_influence totale.
        
        💡 **Suggerimento Threshold**: Per concentrarti sulle features fino al knee point (80%), 
        usa `cumulative_threshold ≈ {knee_cumul_threshold:.4f}` nello slider sopra.
        """)
        
        # Histogram distribuzione node_influence (opzionale, in expander)
        with st.expander("📊 Histogram Distribuzione Node Influence", expanded=False):
            fig_hist = px.histogram(
                sorted_df,
                x='node_influence',
                nbins=50,
                title='Distribuzione Node Influence (Features)',
                labels={'node_influence': 'Node Influence', 'count': 'Frequenza'},
                color_discrete_sequence=['#2196F3']
            )
            
            fig_hist.update_layout(
                height=350,
                template='plotly_white',
                showlegend=False
            )
            
            fig_hist.update_traces(marker=dict(opacity=0.7))
            
            st.plotly_chart(fig_hist, use_container_width=True)
            
            # Statistiche distribuzione
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Mean", f"{sorted_df['node_influence'].mean():.6f}")
            with col2:
                st.metric("Median", f"{sorted_df['node_influence'].median():.6f}")
            with col3:
                st.metric("Std Dev", f"{sorted_df['node_influence'].std():.6f}")
            with col4:
                st.metric("Max", f"{sorted_df['node_influence'].max():.6f}")
    
    except Exception as e:
        st.error(f"❌ Errore nella creazione del grafico di distribuzione: {str(e)}")
        import traceback
        st.code(traceback.format_exc())
    
    # Ritorna le feature filtrate (solo SAE features, no embeddings/logits/errors)
    # Utile per export
    sae_features_only = scatter_filtered[
        ~(is_embedding_filtered | is_logit_filtered | is_error_filtered)
    ].copy()
    
    return sae_features_only

