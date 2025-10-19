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
    # Fallback se il modulo non è importabile
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

st.sidebar.header("⚙️ Configurazione")

# Carica API key
api_key = load_api_key()

if not api_key:
    st.sidebar.error("❌ API Key non trovata!")
    st.error("""
    **API Key Neuronpedia richiesta!**
    
    Per utilizzare questa funzionalità, devi configurare la tua API key:
    
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

st.sidebar.success(f"✅ API Key caricata ({len(api_key)} caratteri)")

# ===== SEZIONE: GENERA NUOVO GRAFO =====

st.header("🌐 Genera Nuovo Attribution Graph")

# INPUT PROMPT
st.subheader("📝 Prompt Configuration")

prompt = st.text_area(
    "Prompt da analizzare",
    value="The capital of state containing Dallas is",
    height=100,
    help="Inserisci il prompt da analizzare. Il modello cercherà di predire il prossimo token."
)

# PARAMETRI GRAFO
st.subheader("🔧 Graph Parameters")

with st.expander("📊 Configurazione avanzata", expanded=False):
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
            help="Probabilità cumulativa desiderata per i logit"
        )

slug = st.text_input(
    "Slug personalizzato (opzionale)",
    value="",
    help="Se vuoto, verrà generato automaticamente"
)

# GENERAZIONE
st.subheader("🚀 Generazione")

col1, col2 = st.columns([1, 2])

with col1:
    generate_button = st.button("🌐 Genera Graph", type="primary", use_container_width=True)
with col2:
    save_locally = st.checkbox("💾 Salva localmente", value=True)

# Stato
if 'generation_result' not in st.session_state:
    st.session_state.generation_result = None
if 'static_metrics_df' not in st.session_state:
    st.session_state.static_metrics_df = None

if generate_button:
    if not prompt.strip():
        st.error("❌ Inserisci un prompt valido!")
        st.stop()
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.text("📋 Preparazione...")
        progress_bar.progress(10)
        
        status_text.text("🔄 Invio richiesta a Neuronpedia...")
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
            st.success("✅ Graph generato con successo!")
        else:
            st.error(f"❌ Errore: {result.get('error', 'Sconosciuto')}")
    
    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"❌ Errore inaspettato: {str(e)}")
        with st.expander("🐛 Dettagli"):
            import traceback
            st.code(traceback.format_exc())

st.markdown("---")

# ===== SEZIONE: ESTRAI CSV DA JSON ESISTENTE =====

with st.expander("📂 **Estrai CSV da JSON Esistente**", expanded=False):
    st.write("""
    Se hai già un file JSON del grafo, puoi estrarre le metriche statiche (`logit_influence`, `frac_external_raw`)
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
                help="File JSON ordinati per data (più recenti prima)"
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
            if st.button("📋 Estrai CSV", key="extract_existing"):
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
                    
                    st.success(f"✅ CSV generato: `{csv_output_path}`")
                    
                    col1, col2, col3, col4 = st.columns(4)
                    with col1:
                        st.metric("Features", len(df))
                    with col2:
                        st.metric("Σ Influence", f"{df['logit_influence'].sum():.2f}")
                    with col3:
                        st.metric("μ Influence", f"{df['logit_influence'].mean():.4f}")
                    with col4:
                        st.metric("μ Frac Ext", f"{df['frac_external_raw'].mean():.3f}")
                    
                    with st.expander("Preview CSV"):
                        st.dataframe(df.head(10), use_container_width=True)
                    
                except Exception as e:
                    st.error(f"❌ Errore: {str(e)}")
        else:
            st.warning("Nessun file JSON trovato in `output/graph_data/`")
    else:
        st.warning("Directory `output/graph_data/` non trovata")

st.markdown("---")

# ===== VISUALIZZAZIONE RISULTATI =====

if st.session_state.generation_result is not None:
    result = st.session_state.generation_result
    
    if result['success']:
        st.header("📊 Risultati")
        
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
        st.subheader("📈 Statistiche Grafo")
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
        st.subheader("📊 Metriche Statiche")
        
        st.info("""
        **Richiesto per la pipeline:** Genera il CSV con `logit_influence` e `frac_external_raw` 
        per usare questo grafo negli step successivi (compute thresholds, supernodes, etc.)
        """)
        
        if st.button("📋 Genera CSV Metriche", key="extract_new"):
            try:
                with st.spinner("Estrazione..."):
                    csv_output_path = str(parent_dir / "output" / "graph_feature_static_metrics.csv")
                    df = extract_static_metrics_from_json(
                        result['graph_data'],
                        output_path=csv_output_path,
                        verbose=False
                    )
                    st.session_state.static_metrics_df = df
                
                st.success(f"✅ CSV generato: `{csv_output_path}`")
            except Exception as e:
                st.error(f"❌ Errore: {str(e)}")
        
        # Mostra CSV se disponibile
        if st.session_state.static_metrics_df is not None:
            df = st.session_state.static_metrics_df
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Features", len(df))
            with col2:
                st.metric("Σ Influence", f"{df['logit_influence'].sum():.2f}")
            with col3:
                st.metric("μ Influence", f"{df['logit_influence'].mean():.4f}")
            with col4:
                st.metric("μ Frac Ext", f"{df['frac_external_raw'].mean():.3f}")
            
            with st.expander("Preview CSV"):
                st.dataframe(df.head(20), use_container_width=True)
            
            with st.expander("📈 Distribuzione"):
                try:
                    import plotly.express as px
                    
                    col1, col2 = st.columns(2)
                    with col1:
                        fig = px.histogram(df, x='logit_influence', nbins=50, 
                                         title='logit_influence')
                        st.plotly_chart(fig, use_container_width=True)
                    with col2:
                        fig = px.histogram(df, x='frac_external_raw', nbins=50,
                                         title='frac_external_raw')
                        st.plotly_chart(fig, use_container_width=True)
                except:
                    pass
            
            csv_str = df.to_csv(index=False)
            st.download_button(
                "📥 Download CSV",
                csv_str,
                "graph_feature_static_metrics.csv",
                "text/csv"
            )
        
        st.markdown("---")
        
        # Download JSON
        if result.get('local_path'):
            st.subheader("💾 File Salvato")
            st.code(result['local_path'])
            file_size = os.path.getsize(result['local_path']) / 1024 / 1024
            st.caption(f"Dimensione: {file_size:.2f} MB")
        
        json_str = json.dumps(result['graph_data'], ensure_ascii=False, indent=2)
        st.download_button(
            "📥 Download JSON",
            json_str,
            f"{result['slug']}.json",
            "application/json"
        )

# ===== FOOTER =====

st.sidebar.markdown("---")
st.sidebar.subheader("📚 Info")
st.sidebar.markdown("""
**Attribution Graph**: visualizza come le SAE features contribuiscono alla predizione.

**Elementi**:
- Embedding nodes: token input
- Feature nodes: SAE latents
- Logit nodes: token predetti
""")

st.sidebar.caption("🌐 Powered by Neuronpedia API")

