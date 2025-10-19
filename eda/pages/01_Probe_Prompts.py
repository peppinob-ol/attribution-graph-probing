"""Pagina 1 - Probe Prompts: Analizza attivazioni su concepts specifici tramite API Neuronpedia"""
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
import pandas as pd

# Import funzioni probe
import importlib.util
script_path = parent_dir / "scripts" / "01_probe_prompts.py"
if script_path.exists():
    spec = importlib.util.spec_from_file_location("probe_prompts", script_path)
    probe_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe_module)
    analyze_concepts_from_graph_json = probe_module.analyze_concepts_from_graph_json
    filter_features_by_influence = probe_module.filter_features_by_influence
else:
    st.error("Script 01_probe_prompts.py non trovato!")
    st.stop()

st.set_page_config(page_title="Probe Prompts", page_icon="🔍", layout="wide")

st.title("🔍 Probe Prompts - Analisi Concepts via API")

st.info("""
**Analizza le attivazioni delle features del grafo su concepts specifici usando le API di Neuronpedia.**
Carica un graph JSON da Neuronpedia, genera concepts tramite OpenAI, e analizza come le features si attivano.
""")

# ===== SIDEBAR: CONFIGURAZIONE =====

st.sidebar.header("⚙️ Configurazione")

# === API KEY NEURONPEDIA ===

st.sidebar.subheader("API Neuronpedia")

# Carica API key Neuronpedia
def load_neuronpedia_key():
    """Carica API key Neuronpedia da .env o environment"""
    from dotenv import load_dotenv
    
    # Carica .env se esiste
    env_file = parent_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    
    return os.environ.get("NEURONPEDIA_API_KEY", "")

neuronpedia_key = load_neuronpedia_key()

if not neuronpedia_key:
    st.sidebar.warning("⚠️ API Key Neuronpedia non trovata")
    st.sidebar.info("""
    Aggiungi `NEURONPEDIA_API_KEY=your-key` nel file `.env` 
    oppure imposta la variabile d'ambiente.
    """)
    neuronpedia_key = st.sidebar.text_input("Oppure inseriscila qui:", type="password", key="neuronpedia_key_input")
else:
    st.sidebar.success("✅ API Key Neuronpedia caricata")

st.sidebar.markdown("---")

# === API KEY OPENAI ===

st.sidebar.subheader("OpenAI (per concepts)")

# Carica API key OpenAI
def load_openai_key():
    """Carica API key OpenAI da .env o environment"""
    from dotenv import load_dotenv
    
    # Carica .env se esiste
    env_file = parent_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    
    return os.environ.get("OPENAI_API_KEY", "")

openai_key = load_openai_key()

if not openai_key:
    st.sidebar.warning("⚠️ API Key OpenAI non trovata")
    st.sidebar.info("""
    Aggiungi `OPENAI_API_KEY=your-key` nel file `.env` 
    oppure imposta la variabile d'ambiente.
    """)
    openai_key = st.sidebar.text_input("Oppure inseriscila qui:", type="password", key="openai_key_input")

# Model selection
model_choice = st.sidebar.selectbox(
    "Modello OpenAI",
    ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
    index=0,
    help="Modello da usare per generare i concepts"
)

st.sidebar.markdown("---")

# ===== STEP 1: CARICAMENTO GRAPH JSON =====

st.header("1️⃣ Carica Graph JSON")

st.write("""
Carica il file JSON di un attribution graph generato da Neuronpedia.
Puoi ottenerlo da:
- File salvato localmente (es: `output/graph_data/anthropological-circuit.json`)
- API di Neuronpedia: `https://www.neuronpedia.org/api/graph/{modelId}/{slug}`
""")

# Tab per caricamento
tab_file, tab_url = st.tabs(["📂 Da File", "🌐 Da URL/API"])

graph_json = None
graph_source = None

with tab_file:
    # Lista file JSON disponibili
    output_dir = parent_dir / "output" / "graph_data"
    json_files = []
    if output_dir.exists():
        json_files = sorted(output_dir.glob("**/*.json"))
    
    if json_files:
        # Converti in path relativi per display
        json_options = [str(f.relative_to(parent_dir)) for f in json_files]
        
        selected_json_path = st.selectbox(
            "File JSON del grafo",
            json_options,
            index=0,
            help="Seleziona il grafo da analizzare"
        )
        
        if st.button("📂 Carica da File", type="primary"):
            json_path_full = parent_dir / selected_json_path
            try:
                with open(json_path_full, 'r', encoding='utf-8') as f:
                    graph_json = json.load(f)
                graph_source = selected_json_path
                st.session_state['graph_json'] = graph_json
                st.session_state['graph_source'] = graph_source
                st.success(f"✅ Graph caricato da: {selected_json_path}")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Errore nel caricamento: {e}")
    else:
        st.warning("⚠️ Nessun file JSON trovato in output/graph_data/")
    
    # Upload manuale
    uploaded_file = st.file_uploader(
        "Oppure carica un file JSON",
        type=['json'],
        help="Carica un file JSON di un graph di Neuronpedia"
    )
    
    if uploaded_file is not None:
        try:
            graph_json = json.load(uploaded_file)
            graph_source = uploaded_file.name
            st.session_state['graph_json'] = graph_json
            st.session_state['graph_source'] = graph_source
            st.success(f"✅ Graph caricato da upload: {uploaded_file.name}")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Errore nel caricamento: {e}")

with tab_url:
    st.write("Carica un graph direttamente dall'API di Neuronpedia")
    
    col1, col2 = st.columns(2)
    with col1:
        api_model_id = st.text_input(
            "Model ID",
            value="gemma-2-2b",
            help="Es: gemma-2-2b, gpt2-small"
        )
    with col2:
        api_slug = st.text_input(
            "Graph Slug",
            value="",
            help="Lo slug del graph (dall'URL di Neuronpedia)"
        )
    
    if st.button("🌐 Carica da API", type="primary"):
        if not api_slug:
            st.error("⚠️ Inserisci uno slug valido")
        else:
            try:
                import requests
                url = f"https://www.neuronpedia.org/api/graph/{api_model_id}/{api_slug}"
                st.info(f"Fetching: {url}")
                
                response = requests.get(url)
                response.raise_for_status()
                graph_json = response.json()
                graph_source = f"API: {api_model_id}/{api_slug}"
                
                st.session_state['graph_json'] = graph_json
                st.session_state['graph_source'] = graph_source
                st.success(f"✅ Graph caricato da API: {api_model_id}/{api_slug}")
                st.rerun()
                
            except Exception as e:
                st.error(f"❌ Errore nel fetch: {e}")

# Recupera graph da session state
if 'graph_json' in st.session_state:
    graph_json = st.session_state['graph_json']
    graph_source = st.session_state.get('graph_source', 'unknown')

# Mostra info grafo se caricato
if graph_json:
    with st.expander("📊 Info Graph", expanded=True):
        metadata = graph_json.get("metadata", {})
        nodes = graph_json.get("nodes", [])
        
        st.write(f"**Source:** {graph_source}")
        st.write(f"**Model ID:** {metadata.get('scan', 'N/A')}")
        
        # Mostra il source format che verrà usato
        model_id = metadata.get('scan', '')
        info = metadata.get('info', {})
        transcoder_set_raw = info.get('transcoder_set', '')
        source_urls = info.get('source_urls', [])
        
        # Determina set name (converte "gemma" → "gemmascope")
        if transcoder_set_raw and transcoder_set_raw.lower() == 'gemma':
            set_name = "gemmascope"
        elif transcoder_set_raw:
            set_name = transcoder_set_raw
        elif 'gemma' in model_id.lower():
            set_name = "gemmascope"
        else:
            set_name = "gemmascope"
        
        # Determina tipo (res vs transcoder) dagli URL
        source_type = "res-16k"
        for url in source_urls:
            if "transcoder" in url.lower():
                source_type = "transcoder-16k"
                break
            elif "res" in url.lower():
                source_type = "res-16k"
                break
        
        source_preview = f"{set_name}-{source_type}"
        
        st.write(f"**Source Format:** `{source_preview}` (es: `6-{source_preview}`)")
        st.write(f"**Prompt:** `{metadata.get('prompt', 'N/A')[:100]}...`")
        st.write(f"**Total Nodes:** {len(nodes)}")
        
        # Conta features
        features = [n for n in nodes if n.get("feature_type") == "cross layer transcoder"]
        st.write(f"**Features (cross layer transcoder):** {len(features)}")
        
        # Statistiche influence
        if features:
            influences = [abs(f.get("influence", 0)) for f in features]
            st.write(f"**Total Influence (abs):** {sum(influences):.4f}")
            st.write(f"**Max Influence:** {max(influences):.6f}")
            st.write(f"**Min Influence:** {min(influences):.6f}")

# ===== STEP 2: FILTRAGGIO FEATURES PER INFLUENCE =====

if graph_json:
    st.header("2️⃣ Filtra Features per Influence")
    
    st.write("""
    Seleziona la percentuale di **cumulative influence contribution** per cui vuoi filtrare le features.
    Le features sono ordinate per influence (valore assoluto) decrescente.
    """)
    
    # Estrai features dal graph
    nodes = graph_json.get("nodes", [])
    features_in_graph = []
    
    for node in nodes:
        if node.get("feature_type") != "cross layer transcoder":
            continue
        
        layer = node.get("layer")
        feature_idx = node.get("feature")
        
        if layer is None or feature_idx is None:
            continue
        
        features_in_graph.append({
            "layer": int(layer),
            "feature": int(feature_idx),
            "original_activation": float(node.get("activation", 0)),
            "original_ctx_idx": int(node.get("ctx_idx", 0)),
            "influence": float(node.get("influence", 0)),
        })
    
    # Slider per cumulative contribution
    cumulative_contribution = st.slider(
        "Cumulative Influence Contribution (%)",
        min_value=1,
        max_value=100,
        value=95,
        step=1,
        help="Percentuale di contributo cumulativo di influence da mantenere"
    ) / 100.0
    
    # Calcola features selezionate
    (filtered_features, 
     threshold_influence, 
     num_selected, 
     num_total) = filter_features_by_influence(features_in_graph, cumulative_contribution)
    
    # Mostra statistiche
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
    
    # Salva in session state
    st.session_state['filtered_features'] = filtered_features
    st.session_state['cumulative_contribution'] = cumulative_contribution

# ===== STEP 3: DEFINISCI CONCEPTS =====

if graph_json:
    st.header("3️⃣ Definisci Concepts")
    
    # Tab per generazione automatica o manuale
    tab_gen, tab_manual, tab_load = st.tabs(["🤖 Genera con OpenAI", "✏️ Inserimento Manuale", "📂 Carica da File"])
    
    with tab_gen:
        st.subheader("Generazione Automatica Concepts")
        
        # Load del prompt dal graph
        prompt_text = graph_json.get("metadata", {}).get("prompt", "")
        
        prompt_for_concepts = st.text_area(
            "Prompt originale",
            value=prompt_text,
            height=100,
            help="Il prompt usato per generare il grafo"
        )
        
        output_for_concepts = st.text_area(
            "Output del modello (opzionale)",
            value="",
            height=100,
            help="L'output del modello per il prompt (se disponibile)"
        )
        
        num_concepts = st.slider(
            "Numero di concepts da generare",
            min_value=1,
            max_value=20,
            value=5,
            help="Quanti concepts vuoi estrarre dal testo"
        )
        
        if st.button("🤖 Genera Concepts con OpenAI", type="primary"):
            if not openai_key:
                st.error("⚠️ Inserisci una API key OpenAI valida")
            else:
                with st.spinner("Generazione concepts in corso..."):
                    try:
                        # Prepara il testo da analizzare
                        text_to_analyze = f"PROMPT: {prompt_for_concepts}\n"
                        if output_for_concepts:
                            text_to_analyze += f"\nOUTPUT: {output_for_concepts}"
                        
                        # Chiama OpenAI
                        import openai
                        openai.api_key = openai_key
                        
                        system_prompt = f"""Analyze the following text and extract the key concepts.

INSTRUCTIONS:
1. Identify the {num_concepts} most significant concepts in the text
2. For each concept, provide:
   - A brief and precise label (maximum 5 words)
   - A category (entity, process, relationship, attribute, etc.)
   - A brief description of the concept in context

Return ONLY a JSON array in the following format, without additional explanations:
[
    {{
        "label": "concept label",
        "category": "category",
        "description": "brief description"
    }},
    ...
]

TEXT:
{text_to_analyze}"""
                        
                        response = openai.chat.completions.create(
                            model=model_choice,
                            messages=[
                                {"role": "system", "content": "You are a helpful assistant that extracts key concepts from text."},
                                {"role": "user", "content": system_prompt}
                            ],
                            temperature=0.3,
                        )
                        
                        # Parse risposta
                        content = response.choices[0].message.content.strip()
                        
                        # Rimuovi markdown code blocks se presenti
                        if content.startswith("```"):
                            lines = content.split("\n")
                            content = "\n".join(lines[1:-1])
                        if content.startswith("json"):
                            content = content[4:].strip()
                        
                        concepts_generated = json.loads(content)
                        
                        # Salva in session state
                        st.session_state['concepts'] = concepts_generated
                        
                        st.success(f"✅ Generati {len(concepts_generated)} concepts!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Errore nella generazione: {e}")
                        st.exception(e)
    
    with tab_manual:
        st.subheader("Inserimento Manuale")
        
        st.write("Inserisci i concepts in formato JSON:")
        
        default_concepts = [
            {"label": "Dallas", "category": "entity", "description": "a major city located in the state of Texas"},
            {"label": "Texas", "category": "entity", "description": "the U.S. state in which Dallas is located"},
        ]
        
        manual_json = st.text_area(
            "JSON Concepts",
            value=json.dumps(default_concepts, indent=2),
            height=300,
            help="Array JSON con format: [{label, category, description}, ...]"
        )
        
        if st.button("Carica Concepts Manualmente"):
            try:
                concepts_manual = json.loads(manual_json)
                st.session_state['concepts'] = concepts_manual
                st.success(f"✅ Caricati {len(concepts_manual)} concepts!")
                st.rerun()
            except json.JSONDecodeError as e:
                st.error(f"❌ Errore nel parsing JSON: {e}")
    
    with tab_load:
        st.subheader("Carica da File JSON")
        
        uploaded_file = st.file_uploader(
            "Carica file JSON con concepts",
            type=['json'],
            help="File JSON con array di concepts",
            key="concepts_uploader"
        )
        
        if uploaded_file is not None:
            try:
                concepts_uploaded = json.load(uploaded_file)
                st.session_state['concepts'] = concepts_uploaded
                st.success(f"✅ Caricati {len(concepts_uploaded)} concepts da file!")
                st.rerun()
            except Exception as e:
                st.error(f"❌ Errore nel caricamento: {e}")

# ===== STEP 4: MODIFICA CONCEPTS =====

if 'concepts' in st.session_state and st.session_state['concepts']:
    st.header("4️⃣ Modifica Concepts")
    
    concepts = st.session_state['concepts']
    
    # Mostra tabella editabile
    df_concepts = pd.DataFrame(concepts)
    
    st.write(f"**{len(concepts)} concepts disponibili:**")
    
    edited_df = st.data_editor(
        df_concepts,
        num_rows="dynamic",
        use_container_width=True,
        column_config={
            "label": st.column_config.TextColumn("Label", width="medium", required=True),
            "category": st.column_config.TextColumn("Category", width="small", required=True),
            "description": st.column_config.TextColumn("Description", width="large", required=True),
        },
        hide_index=True,
    )
    
    # Aggiorna session state
    st.session_state['concepts'] = edited_df.to_dict(orient='records')
    
    # Bottoni per salvare/scaricare
    col1, col2 = st.columns(2)
    
    with col1:
        if st.button("💾 Salva Concepts come JSON"):
            output_dir = parent_dir / "output"
            output_concepts_path = output_dir / "concepts_edited.json"
            output_concepts_path.parent.mkdir(parents=True, exist_ok=True)
            with open(output_concepts_path, 'w', encoding='utf-8') as f:
                json.dump(st.session_state['concepts'], f, indent=2, ensure_ascii=False)
            st.success(f"✅ Salvati in: {output_concepts_path.relative_to(parent_dir)}")
    
    with col2:
        # Download button
        concepts_json = json.dumps(st.session_state['concepts'], indent=2, ensure_ascii=False)
        st.download_button(
            label="⬇️ Scarica Concepts",
            data=concepts_json,
            file_name=f"concepts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json"
        )
    
    # ===== STEP 5: ESEGUI ANALISI =====
    
    st.header("5️⃣ Esegui Analisi")
    
    st.write("Parametri analisi:")
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        activation_threshold = st.slider(
            "Soglia percentile attivazione",
            min_value=0.5,
            max_value=0.99,
            value=0.9,
            step=0.01,
            help="Percentile per calcolare la soglia di densità attivazioni"
        )
    
    with col2:
        use_baseline = st.checkbox(
            "Calcola baseline",
            value=True,
            help="Calcola metriche vs prompt originale (richiede più chiamate API)"
        )
    
    with col3:
        output_filename = st.text_input(
            "Nome file output CSV",
            value="acts_compared.csv",
            help="Nome del file CSV da salvare in output/"
        )
    
    # === CHECKPOINT & RECOVERY ===
    st.subheader("💾 Checkpoint & Recovery")
    
    col1_ckpt, col2_ckpt, col3_ckpt = st.columns(3)
    
    with col1_ckpt:
        checkpoint_every = st.number_input(
            "Salva checkpoint ogni N features",
            min_value=5,
            max_value=100,
            value=10,
            help="Salva i dati parziali ogni N features processate"
        )
    
    with col2_ckpt:
        resume_from_checkpoint = st.checkbox(
            "Riprendi da checkpoint",
            value=True,
            help="Se presente, riprende l'analisi da dove era stata interrotta"
        )
    
    with col3_ckpt:
        # Cerca checkpoint esistenti
        checkpoint_dir = parent_dir / "output" / "checkpoints"
        checkpoint_files = []
        if checkpoint_dir.exists():
            checkpoint_files = sorted(checkpoint_dir.glob("probe_prompts_*.json"), reverse=True)
        
        if checkpoint_files and resume_from_checkpoint:
            selected_checkpoint = st.selectbox(
                "Checkpoint da riprendere",
                options=["Nuovo"] + [f.name for f in checkpoint_files[:5]],
                help="Seleziona un checkpoint esistente o inizia nuovo"
            )
        else:
            selected_checkpoint = "Nuovo"
    
    # Mostra info su checkpoint selezionato
    if selected_checkpoint != "Nuovo" and resume_from_checkpoint:
        checkpoint_path = checkpoint_dir / selected_checkpoint
        if checkpoint_path.exists():
            try:
                with open(checkpoint_path, 'r', encoding='utf-8') as f:
                    ckpt_data = json.load(f)
                num_records = ckpt_data.get('num_records', 0)
                timestamp = ckpt_data.get('timestamp', 'unknown')
                metadata = ckpt_data.get('metadata', {})
                
                st.info(f"""
                **Checkpoint trovato:**
                - Records: {num_records}
                - Data: {timestamp}
                - Status: {metadata.get('status', 'in progress')}
                - Concepts: {metadata.get('current_concept', '?')}/{metadata.get('total_concepts', '?')}
                """)
            except Exception as e:
                st.warning(f"Errore lettura checkpoint: {e}")
    
    # Stima chiamate API
    if 'filtered_features' in st.session_state:
        num_features = len(st.session_state['filtered_features'])
        num_concepts = len(st.session_state['concepts'])
        
        total_calls = num_features * num_concepts
        if use_baseline:
            total_calls += num_features
        
        st.info(f"""
        **Stima chiamate API:**
        - Features selezionate: {num_features}
        - Concepts: {num_concepts}
        - Baseline: {'Sì' if use_baseline else 'No'} ({num_features if use_baseline else 0} chiamate)
        - **Totale chiamate**: ~{total_calls}
        - **Tempo stimato**: ~{total_calls / 5 / 60:.1f} minuti (rate limit: 5 req/sec)
        """)
    
    if st.button("▶️ Esegui Analisi", type="primary"):
        # Verifica prerequisiti
        if not neuronpedia_key:
            st.error("❌ API Key Neuronpedia non configurata")
            st.stop()
        
        if 'filtered_features' not in st.session_state:
            st.error("❌ Features non filtrate. Completa lo Step 2.")
            st.stop()
        
        # Progress tracking
        progress_bar = st.progress(0)
        status_text = st.empty()
        log_area = st.empty()
        
        # Log buffer
        log_messages = []
        
        def progress_callback(current, total, phase):
            """Callback per aggiornare progress bar e log"""
            progress = current / total
            progress_bar.progress(progress)
            
            msg = f"{phase.capitalize()}: {current}/{total} ({progress*100:.1f}%)"
            status_text.text(msg)
            
            # Aggiungi al log (mantieni ultimi 10 messaggi)
            log_messages.append(msg)
            if len(log_messages) > 10:
                log_messages.pop(0)
            
            log_area.text("\n".join(log_messages))
        
        # Container per log dettagliato
        with st.expander("📋 Log Dettagliato", expanded=True):
            detailed_log = st.empty()
        
        try:
            output_dir = parent_dir / "output"
            output_csv_path = output_dir / output_filename
            
            # Setup checkpoint path
            checkpoint_path_to_use = None
            if resume_from_checkpoint and selected_checkpoint != "Nuovo":
                checkpoint_path_to_use = str(checkpoint_dir / selected_checkpoint)
                status_text.info(f"📂 Riprendendo da checkpoint: {selected_checkpoint}")
            else:
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                checkpoint_path_to_use = str(parent_dir / "output" / "checkpoints" / f"probe_prompts_{timestamp}.json")
                status_text.info("🆕 Iniziando nuova analisi...")
            
            log_messages.append(f"💾 Checkpoint: {Path(checkpoint_path_to_use).name}")
            log_messages.append(f"🔄 Resume: {resume_from_checkpoint}")
            log_messages.append("🚀 Inizializzazione...")
            
            df_results = analyze_concepts_from_graph_json(
                graph_json=graph_json,
                concepts=st.session_state['concepts'],
                api_key=neuronpedia_key,
                activation_threshold_quantile=activation_threshold,
                use_baseline=use_baseline,
                cumulative_contribution=st.session_state.get('cumulative_contribution', 0.95),
                verbose=True,
                output_csv=str(output_csv_path),
                progress_callback=progress_callback,
                checkpoint_every=checkpoint_every,
                checkpoint_path=checkpoint_path_to_use,
                resume_from_checkpoint=resume_from_checkpoint
            )
            
            st.session_state['analysis_results'] = df_results
            st.session_state['output_csv_path'] = output_csv_path
            st.session_state['last_checkpoint_path'] = checkpoint_path_to_use
            
            progress_bar.progress(1.0)
            status_text.success("✅ Completato!")
            
            st.success(f"""
            ✅ **Analisi completata!**
            - Risultati: {output_csv_path.relative_to(parent_dir)}
            - Checkpoint: {Path(checkpoint_path_to_use).name}
            - Records: {len(df_results)}
            """)
            
        except KeyboardInterrupt:
            st.warning("⚠️ Analisi interrotta dall'utente")
            st.info(f"""
            💾 **Checkpoint salvato automaticamente**
            
            Per riprendere l'analisi:
            1. Seleziona il checkpoint nella sezione "Checkpoint & Recovery"
            2. Abilita "Riprendi da checkpoint"
            3. Clicca "Esegui Analisi"
            
            Checkpoint: `{Path(checkpoint_path_to_use).name}`
            """)
            
        except Exception as e:
            st.error(f"❌ Errore durante l'analisi: {e}")
            st.exception(e)
            
            if 'checkpoint_path_to_use' in locals():
                st.info(f"""
                💾 **Checkpoint salvato prima dell'errore**
                
                Puoi riprendere l'analisi selezionando il checkpoint:
                `{Path(checkpoint_path_to_use).name}`
                """)
    
    # ===== STEP 6: VISUALIZZA RISULTATI =====
    
    if 'analysis_results' in st.session_state:
        st.header("6️⃣ Risultati")
        
        df_results = st.session_state['analysis_results']
        
        if not df_results.empty:
            st.write(f"**{len(df_results)} righe di risultati**")
            
            # Reset index per visualizzazione
            df_display = df_results.reset_index()
            
            # Filtri
            st.subheader("Filtri")
            
            col1, col2, col3 = st.columns(3)
            
            with col1:
                labels_filter = st.multiselect(
                    "Label",
                    options=df_display['label'].unique().tolist(),
                    default=df_display['label'].unique().tolist()
                )
            
            with col2:
                categories_filter = st.multiselect(
                    "Category",
                    options=df_display['category'].unique().tolist(),
                    default=df_display['category'].unique().tolist()
                )
            
            with col3:
                layers_filter = st.multiselect(
                    "Layer",
                    options=sorted(df_display['layer'].unique().tolist()),
                    default=sorted(df_display['layer'].unique().tolist())
                )
            
            # Applica filtri
            df_filtered = df_display[
                (df_display['label'].isin(labels_filter)) &
                (df_display['category'].isin(categories_filter)) &
                (df_display['layer'].isin(layers_filter))
            ]
            
            # Mostra tabella
            st.dataframe(
                df_filtered,
                use_container_width=True,
                height=400
            )
            
            # Download risultati filtrati
            csv_filtered = df_filtered.to_csv(index=False, encoding='utf-8').encode('utf-8')
            st.download_button(
                label="⬇️ Scarica Risultati Filtrati",
                data=csv_filtered,
                file_name=f"acts_compared_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                mime="text/csv"
            )
            
            # Statistiche rapide
            st.subheader("Statistiche Rapide")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Features Totali", len(df_filtered))
            
            with col2:
                avg_z = df_filtered['z_score'].mean()
                st.metric("Z-score Medio", f"{avg_z:.2f}")
            
            with col3:
                picco_su_label = (df_filtered['picco_su_label'].sum() / len(df_filtered) * 100) if len(df_filtered) > 0 else 0
                st.metric("Picco su Label (%)", f"{picco_su_label:.1f}%")
            
            with col4:
                avg_cos_sim = df_filtered['cosine_similarity'].mean()
                st.metric("Cosine Sim. Media", f"{avg_cos_sim:.3f}")
            
        else:
            st.warning("⚠️ Nessun risultato disponibile")

else:
    st.info("👆 Carica un graph JSON per iniziare l'analisi")

# ===== SIDEBAR INFO =====

st.sidebar.markdown("---")
st.sidebar.header("ℹ️ Info")
st.sidebar.write("""
**Probe Prompts** analizza come le features del grafo 
si attivano su concepts specifici usando le API di Neuronpedia.

**Workflow:**
1. Carica un graph JSON (da file o API)
2. Filtra features per cumulative influence
3. Genera concepts con OpenAI o inseriscili manualmente
4. Modifica/aggiungi/elimina concepts
5. Esegui l'analisi (tramite API Neuronpedia)
6. Visualizza e scarica i risultati

**Metriche calcolate:**
- Attivazioni su label span e sequenza completa
- Z-scores (standard, robust, log)
- Densità, cosine similarity, ratio vs original
- Influence originale per ogni feature
""")

st.sidebar.caption("Version: 2.0.0 | Probe Prompts API")
