"""Pagina 0 - Graph Generation: Genera Attribution Graphs su Neuronpedia"""
import sys
from pathlib import Path

# Aggiungi parent directory al path
parent_dir = Path(__file__).parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import streamlit as st
import json
import os
from datetime import datetime

# Import funzioni generazione grafo
try:
    from scripts.neuronpedia_graph_generation import (
        generate_attribution_graph,
        get_graph_stats,
        load_api_key,
        extract_static_metrics_from_json
    )
except ImportError:
    # Fallback se il modulo non Ã¨ importabile
    import importlib.util
    script_path = parent_dir / "scripts" / "00_neuronpedia_graph_generation.py"
    spec = importlib.util.spec_from_file_location("neuronpedia_graph_generation", script_path)
    graph_gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(graph_gen)
    generate_attribution_graph = graph_gen.generate_attribution_graph
    get_graph_stats = graph_gen.get_graph_stats
    load_api_key = graph_gen.load_api_key
    extract_static_metrics_from_json = graph_gen.extract_static_metrics_from_json

st.set_page_config(page_title="Graph Generation", page_icon="🌐", layout="wide")

st.title("🌐 Attribution Graph Generation")

st.info("""
**Genera un nuovo attribution graph su Neuronpedia** per analizzare come il modello predice il prossimo token.
Il grafo mostra le features (SAE latents) che contribuiscono maggiormente alla predizione.
""")

# ===== SIDEBAR: CONFIGURAZIONE =====

st.sidebar.header("Configurazione")

# Carica API key
api_key = load_api_key()

if not api_key:
    st.sidebar.error("API Key non trovata!")
    st.error("""
    **API Key Neuronpedia richiesta!**
    
    Per utilizzare questa funzionalitÃ , devi configurare la tua API key:
    
    1. Ottieni una API key da [Neuronpedia](https://www.neuronpedia.org/)
    2. Aggiungi al file `.env` nella root del progetto:
       ```
       NEURONPEDIA_API_KEY='your-key-here'
       ```
    3. Oppure imposta la variabile d'ambiente:
       ```
       export NEURONPEDIA_API_KEY='your-key-here'
       ```
    """)
    st.stop()

st.sidebar.success(f"API Key caricata ({len(api_key)} caratteri)")

# ===== SEZIONE: GENERA NUOVO GRAFO =====

st.header("🌐 Genera Nuovo Attribution Graph")

# INPUT PROMPT
st.subheader(" Prompt Configuration")

prompt = st.text_area(
    "Prompt da analizzare",
    value="The capital of state containing Dallas is",
    height=100,
    help="Inserisci il prompt da analizzare. Il modello cercherÃ  di predire il prossimo token."
)

# PARAMETRI GRAFO
st.subheader("Graph Parameters")

with st.expander("Configurazione avanzata", expanded=False):
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Model & Source Set**")
        
        model_id = st.selectbox(
            "Model ID",
            ["gemma-2-2b", "gpt2-small", "gemma-2-9b"],
            help="Modello da analizzare"
        )
        
        source_set_name = st.text_input(
            "Source Set Name",
            value="gemmascope-transcoder-16k",
            help="Nome del source set SAE da utilizzare"
        )
        
        max_feature_nodes = st.number_input(
            "Max Feature Nodes",
            min_value=100,
            max_value=10000,
            value=5000,
            step=100,
            help="Numero massimo di feature nodes da includere"
        )
    
    with col2:
        st.write("**Thresholds**")
        
        node_threshold = st.slider(
            "Node Threshold",
            min_value=0.0,
            max_value=1.0,
            value=0.8,
            step=0.05,
            help="Soglia minima di importanza per includere un nodo"
        )
        
        edge_threshold = st.slider(
            "Edge Threshold",
            min_value=0.0,
            max_value=1.0,
            value=0.85,
            step=0.05,
            help="Soglia minima di importanza per includere un edge"
        )
        
        max_n_logits = st.number_input(
            "Max N Logits",
            min_value=1,
            max_value=50,
            value=10,
            step=1,
            help="Numero massimo di logit da considerare"
        )
        
        desired_logit_prob = st.slider(
            "Desired Logit Probability",
            min_value=0.5,
            max_value=0.99,
            value=0.95,
            step=0.01,
            help="ProbabilitÃ  cumulativa desiderata per i logit"
        )

slug = st.text_input(
    "Slug personalizzato (opzionale)",
    value="",
    help="Se vuoto, verrÃ  generato automaticamente"
)

# GENERAZIONE
st.subheader(" Generazione")

col1, col2 = st.columns([1, 2])

with col1:
    generate_button = st.button("🌐 Genera Graph", type="primary", use_container_width=True)
with col2:
    save_locally = st.checkbox("Salva localmente", value=True)

# Stato
if 'generation_result' not in st.session_state:
    st.session_state.generation_result = None
if 'static_metrics_df' not in st.session_state:
    st.session_state.static_metrics_df = None
if 'extracted_graph_data' not in st.session_state:
    st.session_state.extracted_graph_data = None
if 'extracted_csv_df' not in st.session_state:
    st.session_state.extracted_csv_df = None

if generate_button:
    if not prompt.strip():
        st.error("Inserisci un prompt valido!")
        st.stop()
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.text(" Preparazione...")
        progress_bar.progress(10)
        
        status_text.text("Invio richiesta a Neuronpedia...")
        progress_bar.progress(30)
        
        result = generate_attribution_graph(
            prompt=prompt,
            api_key=api_key,
            model_id=model_id,
            source_set_name=source_set_name,
            slug=slug if slug.strip() else None,
            max_n_logits=max_n_logits,
            desired_logit_prob=desired_logit_prob,
            node_threshold=node_threshold,
            edge_threshold=edge_threshold,
            max_feature_nodes=max_feature_nodes,
            save_locally=save_locally,
            verbose=False
        )
        
        progress_bar.progress(100)
        status_text.empty()
        progress_bar.empty()
        
        st.session_state.generation_result = result
        
        if result['success']:
            st.success("Graph generato con successo!")
        else:
            st.error(f"Errore: {result.get('error', 'Sconosciuto')}")
    
    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"Errore inaspettato: {str(e)}")
        with st.expander("Dettagli"):
            import traceback
            st.code(traceback.format_exc())

st.markdown("---")

# ===== SEZIONE: ANALIZZA JSON ESISTENTE -> CSV =====

with st.expander("**Analizza JSON Esistente -> CSV**", expanded=False):
    st.write("""
    Se hai già un file JSON del grafo, puoi estrarre le metriche statiche (`node_influence`, `cumulative_influence`, `frac_external_raw`)
    senza rigenerare il grafo.
    """)
    
    # Lista file JSON disponibili
    json_dir = parent_dir / "output" / "graph_data"
    if json_dir.exists():
        json_files = sorted(json_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        
        if json_files:
            # Usa path relativi alla parent dir del progetto per visualizzazione
            json_options = [str(f.relative_to(parent_dir)) for f in json_files]
            selected_json = st.selectbox(
                "Seleziona file JSON",
                options=json_options,
                help="File JSON ordinati per data (piÃ¹ recenti prima)"
            )
            
            # Mostra info file
            if selected_json:
                file_path = parent_dir / selected_json
                file_size = file_path.stat().st_size / 1024 / 1024
                file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Dimensione", f"{file_size:.2f} MB")
                with col2:
                    st.metric("Data", file_time.strftime("%Y-%m-%d %H:%M"))
                with col3:
                    st.metric("Nome", file_path.name[:20] + "...")
            
            # Bottone estrazione
            if st.button("Estrai CSV", key="extract_existing"):
                try:
                    with st.spinner("Estrazione metriche in corso..."):
                        json_full_path = str(parent_dir / selected_json)
                        with open(json_full_path, 'r', encoding='utf-8') as f:
                            graph_data = json.load(f)
                        
                        csv_output_path = str(parent_dir / "output" / "graph_feature_static_metrics.csv")
                        df = extract_static_metrics_from_json(
                            graph_data,
                            output_path=csv_output_path,
                            verbose=False
                        )
                        
                        # Salva in session_state per mantenere tra i re-run
                        st.session_state.extracted_graph_data = graph_data
                        st.session_state.extracted_csv_df = df
                    
                    st.success(f"CSV generato: `{csv_output_path}`")
                    st.info("Scorri in basso per vedere le visualizzazioni interattive")
                    
                except Exception as e:
                    st.error(f"Errore: {str(e)}")
        else:
            st.warning("Nessun file JSON trovato in `output/graph_data/`")
    else:
        st.warning("Directory `output/graph_data/` non trovata")

# ===== VISUALIZZAZIONE DATI ESTRATTI (persiste tra re-run) =====

if st.session_state.extracted_graph_data is not None and st.session_state.extracted_csv_df is not None:
    graph_data = st.session_state.extracted_graph_data
    df = st.session_state.extracted_csv_df
    
    st.markdown("---")
    st.header("Analisi Dati Estratti")
    
    # Metriche CSV
    col1, col2, col3, col4, col5 = st.columns(5)
    with col1:
        st.metric("Features", len(df))
    with col2:
        st.metric("Token Unici", df['ctx_idx'].nunique())
    with col3:
        st.metric("μ Activation", f"{df['activation'].mean():.3f}")
    with col4:
        # Usa node_influence (influenza marginale) per somma totale
        st.metric("Σ Node Infl", f"{df['node_influence'].sum():.2f}")
    with col5:
        st.metric("μ Frac Ext", f"{df['frac_external_raw'].mean():.3f}")
    
    with st.expander("Visualizza Dataframe Completo", expanded=False):
        st.dataframe(df, use_container_width=True, height=600)
    
    # Scatter plot: Layer vs Context Position con Influence
    st.subheader("Distribuzione Features per Layer e Posizione")
    
    # Prepara i dati dal JSON per lo scatter plot
    if 'nodes' in graph_data:
        import pandas as pd
        import plotly.express as px
        
        # Estrai prompt_tokens dalla metadata per mappare ctx_idx -> token
        prompt_tokens = graph_data.get('metadata', {}).get('prompt_tokens', [])
        
        # Visualizzazione scatter plot con filtro
        from eda.utils.graph_visualization import create_scatter_plot_with_filter
        filtered_features = create_scatter_plot_with_filter(graph_data)
        
        # Export feature selezionate
        if filtered_features is not None and len(filtered_features) > 0:
            st.markdown("---")
            st.subheader("📥 Esporta Feature Selezionate")
            
            # Converti dataframe in formato [{"layer": X, "index": Y}, ...]
            # Rimuovi duplicati usando set di tuple (layer, feature)
            unique_features = {
                (int(row['layer']), int(row['feature']))
                for _, row in filtered_features.iterrows()
            }
            
            # Converti in lista ordinata di dict
            features_export = [
                {"layer": layer, "index": feature}
                for layer, feature in sorted(unique_features)
            ]
            
            # Estrai anche i node_ids selezionati (per upload subgraph)
            node_ids_export = sorted(filtered_features['id'].unique().tolist())
            
            # Crea export completo con features E node_ids
            export_data = {
                "features": features_export,
                "node_ids": node_ids_export,
                "metadata": {
                    "n_features": len(features_export),
                    "n_nodes": len(node_ids_export),
                    "cumulative_threshold": cumulative_threshold_summary if 'cumulative_threshold_summary' in locals() else None,
                    "exported_at": datetime.now().isoformat()
                }
            }
            
            # Statistiche
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Features Uniche", len(features_export))
            with col2:
                st.metric("Nodi Selezionati", len(node_ids_export))
            with col3:
                st.metric("Layer Unici", len({f['layer'] for f in features_export}))
            
            # Download JSON (formato completo)
            col_full, col_legacy = st.columns(2)
            
            with col_full:
                st.download_button(
                    label="⬇️ Download Features + Nodes JSON",
                    data=json.dumps(export_data, indent=2, ensure_ascii=False),
                    file_name="selected_features_with_nodes.json",
                    mime="application/json",
                    help="Formato completo con features e node_ids (per Node Grouping + Upload)"
                )
            
            with col_legacy:
                st.download_button(
                    label="⬇️ Download Features JSON (legacy)",
                    data=json.dumps(features_export, indent=2, ensure_ascii=False),
                    file_name="selected_features.json",
                    mime="application/json",
                    help="Formato legacy (solo features, compatibile con batch_get_activations.py)"
                )
            
            # Preview
            with st.expander("🔍 Preview Export Completo", expanded=False):
                st.json({
                    "features": features_export[:5],
                    "node_ids": node_ids_export[:10],
                    "metadata": export_data["metadata"]
                })
        
st.markdown("---")

# ===== VISUALIZZAZIONE RISULTATI =====

if st.session_state.generation_result is not None:
    result = st.session_state.generation_result
    
    if result['success']:
        st.header("Risultati")
        
        # Metriche
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Nodi", result['num_nodes'])
        with col2:
            st.metric("Links", result['num_links'])
        with col3:
            st.metric("Model", result['model_id'])
        with col4:
            slug_short = result['slug'][:15] + "..." if len(result['slug']) > 15 else result['slug']
            st.metric("Slug", slug_short)
        
        # Link Neuronpedia
        st.subheader("🌐 Visualizza su Neuronpedia")
        neuronpedia_url = f"https://www.neuronpedia.org/graph/{result['model_id']}/{result['slug']}"
        st.markdown(f"[**Apri Graph**]({neuronpedia_url})")
        
        # Statistiche
        st.subheader("Statistiche Grafo")
        stats = get_graph_stats(result['graph_data'])
        
        col1, col2 = st.columns(2)
        with col1:
            st.write("**Composizione:**")
            st.write(f"- Embeddings: {stats['embedding_nodes']}")
            st.write(f"- Features: {stats['feature_nodes']}")
            st.write(f"- Logits: {stats['logit_nodes']}")
        
        with col2:
            st.write("**Layers:**")
            for layer in stats['layers'][:8]:
                st.write(f"- Layer {layer}: {stats['nodes_by_layer'][layer]}")
            if len(stats['layers']) > 8:
                st.caption(f"... e altri {len(stats['layers']) - 8} layer")
        
        # ESTRAI CSV DAL GRAFO APPENA GENERATO
        st.subheader("Metriche Statiche")
        
        st.info("""
        **Richiesto per la pipeline:** Genera il CSV con `node_influence`, `cumulative_influence` e `frac_external_raw` 
        per usare questo grafo negli step successivi (compute thresholds, supernodes, etc.)
        """)
        
        if st.button("Genera CSV Metriche", key="extract_new"):
            try:
                with st.spinner("Estrazione..."):
                    csv_output_path = str(parent_dir / "output" / "graph_feature_static_metrics.csv")
                    df = extract_static_metrics_from_json(
                        result['graph_data'],
                        output_path=csv_output_path,
                        verbose=False
                    )
                    st.session_state.static_metrics_df = df
                
                st.success(f"CSV generato: `{csv_output_path}`")
            except Exception as e:
                st.error(f"Errore: {str(e)}")
        
        # Mostra CSV se disponibile
        if st.session_state.static_metrics_df is not None:
            df = st.session_state.static_metrics_df
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Features", len(df))
            with col2:
                st.metric("Σ Node Infl", f"{df['node_influence'].sum():.2f}")
            with col3:
                st.metric("Max Cumul", f"{df['cumulative_influence'].max():.4f}")
            with col4:
                st.metric("μ Frac Ext", f"{df['frac_external_raw'].mean():.3f}")
            
            with st.expander("Preview CSV"):
                st.dataframe(df.head(20), use_container_width=True)
            
            with st.expander("Distribuzione"):
                try:
                    import plotly.express as px
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        fig = px.histogram(df, x='node_influence', nbins=50, 
                                         title='node_influence (marginal)')
                        st.plotly_chart(fig, use_container_width=True)
                    with col2:
                        fig = px.histogram(df, x='cumulative_influence', nbins=50,
                                         title='cumulative_influence')
                        st.plotly_chart(fig, use_container_width=True)
                except:
                    pass
            
            csv_str = df.to_csv(index=False)
            st.download_button(
                "Download CSV",
                csv_str,
                "graph_feature_static_metrics.csv",
                "text/csv"
            )
        
        st.markdown("---")
        
        # Download JSON
        if result.get('local_path'):
            st.subheader("File Salvato")
            st.code(result['local_path'])
            file_size = os.path.getsize(result['local_path']) / 1024 / 1024
            st.caption(f"Dimensione: {file_size:.2f} MB")
        
        json_str = json.dumps(result['graph_data'], ensure_ascii=False, indent=2)
        st.download_button(
            "Download JSON",
            json_str,
            f"{result['slug']}.json",
            "application/json"
        )

st.markdown("---")

# ===== GRAFICI RIASSUNTIVI: COVERAGE E STRENGTH =====

st.header("📊 Grafici Riassuntivi: Coverage e Strength")

# Sorgente dati: preferisci dati estratti, altrimenti ultimo grafo generato
graph_data_for_plots = None
if st.session_state.get('extracted_graph_data') is not None:
    graph_data_for_plots = st.session_state.extracted_graph_data
elif st.session_state.get('generation_result') is not None and st.session_state.generation_result.get('success'):
    graph_data_for_plots = st.session_state.generation_result.get('graph_data')

if graph_data_for_plots is None or 'nodes' not in graph_data_for_plots:
    st.info("Nessun dato grafico disponibile: estrai o genera un grafo per vedere i riassunti.")
else:
    import pandas as pd
    import plotly.express as px
    import numpy as np

    nodes_df = pd.DataFrame(graph_data_for_plots['nodes'])
    is_feature = nodes_df['node_id'].astype(str).str[0].str.isdigit() & nodes_df['node_id'].astype(str).str.contains('_')
    feat_nodes = nodes_df.loc[is_feature].copy()
    
    if len(feat_nodes) == 0:
        st.warning("Nessuna feature trovata nei dati correnti.")
    else:
        # Aggiungi slider per filtrare (riusa la stessa logica di create_scatter_plot_with_filter)
        max_influence = feat_nodes['influence'].max()
        
        st.markdown("### 🎚️ Filtra Features per Cumulative Influence")
        st.info(f"""
        **Usa lo slider per filtrare i grafici sottostanti** in base alla copertura cumulativa di influence (0-{max_influence:.2f}).
        I grafici riassuntivi mostreranno solo le feature con `influence ≤ threshold`.
        """)
        
        # Controlla se esiste già lo slider principale (da create_scatter_plot_with_filter)
        # Se esiste, usa quello, altrimenti crea uno nuovo
        slider_key = "cumulative_slider_summary"
        if "cumulative_slider_main" in st.session_state:
            # Riusa il valore dello slider principale
            cumulative_threshold_summary = st.session_state.cumulative_slider_main
            st.info(f"📌 Sincronizzato con lo slider principale: threshold = {cumulative_threshold_summary:.4f}")
        else:
            # Crea slider separato
            cumulative_threshold_summary = st.slider(
                "Cumulative Influence Threshold (grafici riassuntivi)",
                min_value=0.0,
                max_value=float(max_influence),
                value=float(max_influence),
                step=0.01,
                key=slider_key,
                help=f"Mantieni solo feature con influence ≤ threshold. Range: 0.0 - {max_influence:.2f}"
            )
        
        # Applica filtro
        feat_nodes_filtered = feat_nodes[feat_nodes['influence'] <= cumulative_threshold_summary].copy()
        
        if len(feat_nodes_filtered) == 0:
            st.warning("⚠️ Nessuna feature soddisfa il filtro corrente. Aumenta la soglia.")
        else:
            # Mostra statistiche filtro
            col1, col2, col3 = st.columns(3)
            with col1:
                st.metric("Feature Totali", len(feat_nodes))
            with col2:
                st.metric("Feature Filtrate", len(feat_nodes_filtered))
            with col3:
                pct = (len(feat_nodes_filtered) / len(feat_nodes) * 100) if len(feat_nodes) > 0 else 0
                st.metric("% Mantenute", f"{pct:.1f}%")
            
            st.markdown("---")
            
            # Calcola n_ctx e statistiche per feature
            feat_nodes_filtered['feature_key'] = feat_nodes_filtered['node_id'].str.rsplit('_', n=1).str[0]
            cov = (
                feat_nodes_filtered.groupby('feature_key')['ctx_idx'].nunique()
                .rename('n_ctx').reset_index()
            )
            per_feat = (
                feat_nodes_filtered.groupby('feature_key')
                .agg(mean_influence=('influence','mean'),
                     mean_activation=('activation','mean'))
                .reset_index()
            )
            per_feat_cov = per_feat.merge(cov, on='feature_key', how='left')
            nodes_with_cov = feat_nodes_filtered.merge(cov, on='feature_key', how='left')

            # Grafico 1: Copertura (Istogramma + ECDF)
            st.subheader("🔢 Copertura delle feature (n_ctx)")
            c1, c2 = st.columns(2)
            with c1:
                fig_hist = px.histogram(cov, x='n_ctx', color_discrete_sequence=['#4C78A8'])
                fig_hist.update_layout(title='Distribuzione n_ctx per feature',
                                       xaxis_title='Numero di ctx_idx unici',
                                       yaxis_title='Numero di feature')
                st.plotly_chart(fig_hist, use_container_width=True)
            with c2:
                fig_ecdf = px.ecdf(cov, x='n_ctx', color_discrete_sequence=['#F58518'])
                fig_ecdf.update_layout(title='ECDF di n_ctx',
                                       xaxis_title='Numero di ctx_idx unici',
                                       yaxis_title='Frazione cumulativa')
                st.plotly_chart(fig_ecdf, use_container_width=True)

            # Grafico 2: Strength vs Coverage (Activation vs n_ctx e Scatter mean)
            st.subheader("⚡ Strength vs Coverage")
            c3, c4 = st.columns(2)
            with c3:
                fig_violin = px.violin(nodes_with_cov, x='n_ctx', y='activation', box=True, points=False)
                fig_violin.update_layout(title='Activation per n_ctx',
                                         xaxis_title='n_ctx (feature)',
                                         yaxis_title='Activation (nodo)')
                st.plotly_chart(fig_violin, use_container_width=True)
            with c4:
                fig_scatter = px.scatter(per_feat_cov, x='mean_activation', y='mean_influence',
                                         color='n_ctx', size='n_ctx', hover_data=['feature_key'],
                                         color_continuous_scale='Viridis')
                # Correlazioni per il sottotitolo
                if len(per_feat_cov) >= 2:
                    pearson = float(per_feat_cov['mean_activation'].corr(per_feat_cov['mean_influence'], method='pearson'))
                    spearman = float(per_feat_cov['mean_activation'].corr(per_feat_cov['mean_influence'], method='spearman'))
                    fig_scatter.update_layout(title=f'Mean activation vs mean influence<br>(r={pearson:.2f}, ρ={spearman:.2f})')
                else:
                    fig_scatter.update_layout(title='Mean activation vs mean influence')
                fig_scatter.update_layout(xaxis_title='Mean activation (per feature)',
                                          yaxis_title='Mean influence (per feature)')
                st.plotly_chart(fig_scatter, use_container_width=True)
            
            # Insight rapidi
            with st.expander("💡 Insight dai grafici", expanded=False):
                # Calcola statistiche chiave
                top_n_ctx = cov['n_ctx'].max()
                n_top = len(cov[cov['n_ctx'] == top_n_ctx])
                top_features = cov[cov['n_ctx'] == top_n_ctx]['feature_key'].tolist()
                
                st.markdown(f"""
                **Copertura (n_ctx)**:
                - {len(cov)} feature uniche nel dataset filtrato
                - {n_top} feature presenti in tutti i {top_n_ctx} contesti
                - Feature multi-contesto ({top_n_ctx}): {', '.join([f'`{f}`' for f in top_features[:5]])}
                
                **Strength vs Coverage**:
                - Correlazione activation-influence: **r={pearson:.2f}** (Pearson), **ρ={spearman:.2f}** (Spearman)
                - {"Correlazione negativa: feature con activation alta tendono ad avere influence bassa" if pearson < -0.2 else "Correlazione debole o positiva tra activation e influence"}
                """)
                
                # Statistiche gruppi
                if len(nodes_with_cov) > 0:
                    g1 = nodes_with_cov[nodes_with_cov['n_ctx'] == 1]
                    g_multi = nodes_with_cov[nodes_with_cov['n_ctx'] >= 5]
                    
                    if len(g1) > 0 and len(g_multi) > 0:
                        st.markdown(f"""
                        **Confronto gruppi**:
                        - n_ctx=1: {len(g1)} nodi, mean_activation={g1['activation'].mean():.2f}, mean_influence={g1['influence'].mean():.3f}
                        - n_ctx≥5: {len(g_multi)} nodi, mean_activation={g_multi['activation'].mean():.2f}, mean_influence={g_multi['influence'].mean():.3f}
                        """)


# ===== FOOTER =====

st.sidebar.markdown("---")
st.sidebar.subheader("Info")
st.sidebar.markdown("""
**Attribution Graph**: visualizza come le SAE features contribuiscono alla predizione.

**Elementi**:
- Embedding nodes: token input
- Feature nodes: SAE latents
- Logit nodes: token predetti
""")

st.sidebar.caption("🌐 Powered by Neuronpedia API")

