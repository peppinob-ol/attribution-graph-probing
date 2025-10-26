"""Page 1 - Probe Prompts: Analyze activations on specific concepts via Neuronpedia API"""
import sys
from pathlib import Path

# Add parent directory to path
parent_dir = Path(__file__).parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

import streamlit as st
import json
import os
from datetime import datetime
import pandas as pd

# Import probe functions
import importlib.util
script_path = parent_dir / "scripts" / "01_probe_prompts.py"
if script_path.exists():
    spec = importlib.util.spec_from_file_location("probe_prompts", script_path)
    probe_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(probe_module)
    analyze_concepts_from_graph_json = probe_module.analyze_concepts_from_graph_json
    filter_features_by_influence = probe_module.filter_features_by_influence
    export_concepts_to_prompts = probe_module.export_concepts_to_prompts
else:
    st.error("Script 01_probe_prompts.py not found!")
    st.stop()

# Import graph generation functions for feature export
script_path_graph = parent_dir / "scripts" / "00_neuronpedia_graph_generation.py"
if script_path_graph.exists():
    spec_graph = importlib.util.spec_from_file_location("graph_gen", script_path_graph)
    graph_module = importlib.util.module_from_spec(spec_graph)
    spec_graph.loader.exec_module(graph_module)
    export_features_list = graph_module.export_features_list
else:
    st.error("Script 00_neuronpedia_graph_generation.py not found!")
    st.stop()

st.set_page_config(page_title="Probe Prompts", page_icon="🔍", layout="wide")

st.title("🔍 Probe Prompts - Concept Analysis via API")

st.info("""
**Analyze feature activations on specific concepts using Neuronpedia APIs.**
Load a graph JSON from Neuronpedia, generate concepts via OpenAI, and analyze how features activate.
""")

# ===== SIDEBAR: CONFIGURATION =====

st.sidebar.header("⚙️ Configuration")

# === API KEY NEURONPEDIA ===

st.sidebar.subheader("Neuronpedia API")

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
    st.sidebar.warning("⚠️ Neuronpedia API Key not found")
    st.sidebar.info("""
    Aggiungi `NEURONPEDIA_API_KEY=your-key` nel file `.env` 
    oppure imposta la variabile d'ambiente.
    """)
    neuronpedia_key = st.sidebar.text_input("Oppure inseriscila qui:", type="password", key="neuronpedia_key_input")
else:
    st.sidebar.success("✅ Neuronpedia API Key loaded")

st.sidebar.markdown("---")

# === API KEY OPENAI ===

st.sidebar.subheader("OpenAI (for concepts)")

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
    st.sidebar.warning("⚠️ OpenAI API Key not found")
    st.sidebar.info("""
    Aggiungi `OPENAI_API_KEY=your-key` nel file `.env` 
    oppure imposta la variabile d'ambiente.
    """)
    openai_key = st.sidebar.text_input("Oppure inseriscila qui:", type="password", key="openai_key_input")

# Model selection
model_choice = st.sidebar.selectbox(
    "OpenAI Model",
    ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
    index=0,
    help="Model to use for concept generation"
)

st.sidebar.markdown("---")

# ===== STEP 1: CARICAMENTO GRAPH JSON =====

st.header("1️⃣ Load Graph JSON")

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

# ===== STEP 2: CARICA FEATURE SUBSET =====

if graph_json:
    st.header("2️⃣ Load Feature Subset")
    
    st.write("""
    Carica un file JSON con la lista di features da analizzare, oppure usa tutte le features del grafo.
    """)
    
    # Tab per scelta modalità
    tab_load, tab_all, tab_export = st.tabs(["📂 Carica Subset", "📋 Usa Tutte", "💾 Esporta Subset"])
    
    with tab_load:
        st.subheader("Carica Feature Subset da JSON")
        
        uploaded_features = st.file_uploader(
            "File JSON con features",
            type=['json'],
            help="Formato: [{\"layer\": int, \"index\": int}, ...]",
            key="features_uploader"
        )
        
        if uploaded_features is not None:
            try:
                features_json = json.load(uploaded_features)
                
                # Converti formato features in features_in_graph format
                features_in_graph = []
                nodes = graph_json.get("nodes", [])
                
                # Crea lookup per features dal graph
                graph_features_lookup = {}
                skipped_count = 0
                
                for node in nodes:
                    # Filtra solo nodi SAE (cross layer transcoder)
                    if node.get("feature_type") != "cross layer transcoder":
                        continue
                    
                    layer = node.get("layer")
                    node_id = node.get("node_id", "")
                    feature_idx = None
                    
                    # Estrai feature_index dal node_id (formato: "layer_featureIndex_sequence")
                    # Esempio: "24_79427_7" → feature_idx = 79427
                    if node_id and '_' in node_id:
                        parts = node_id.split('_')
                        if len(parts) >= 2:
                            try:
                                feature_idx = int(parts[1])
                            except (ValueError, IndexError):
                                pass
                    
                    # SKIP nodi SAE malformati (no fallback fasullo!)
                    if layer is None or feature_idx is None:
                        skipped_count += 1
                        continue
                    
                    graph_features_lookup[(int(layer), int(feature_idx))] = {
                        "layer": int(layer),
                        "feature": int(feature_idx),
                        "original_activation": float(node.get("activation", 0)),
                        "original_ctx_idx": int(node.get("ctx_idx", 0)),
                        "influence": float(node.get("influence", 0)),
                    }
                
                if skipped_count > 0:
                    st.warning(f"⚠️ {skipped_count} nodi feature con node_id malformato sono stati skippati")
                
                # Match con features caricate
                for feat_json in features_json:
                    layer = feat_json.get("layer")
                    index = feat_json.get("index")
                    
                    if layer is not None and index is not None:
                        key = (int(layer), int(index))
                        if key in graph_features_lookup:
                            features_in_graph.append(graph_features_lookup[key])
                        else:
                            st.warning(f"Feature non trovata nel grafo: layer={layer}, index={index}")
                
                st.session_state['filtered_features'] = features_in_graph
                st.success(f"✅ Caricate {len(features_in_graph)} features dal subset")
                
                # Mostra statistiche
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Features nel JSON", len(features_json))
                with col2:
                    st.metric("Features trovate nel grafo", len(features_in_graph))
                
            except Exception as e:
                st.error(f"❌ Errore nel caricamento: {e}")
    
    with tab_all:
        st.subheader("Usa Tutte le Features del Grafo")
        
        # Estrai features dal graph
        nodes = graph_json.get("nodes", [])
        all_features = []
        skipped_count = 0
        
        for node in nodes:
            if node.get("feature_type") != "cross layer transcoder":
                continue
            
            layer = node.get("layer")
            
            # Estrai feature_index dal node_id (formato: "layer_featureIndex_sequence")
            # Esempio: "24_79427_7" → feature_index = 79427
            node_id = node.get("node_id", "")
            feature_idx = None
            
            if node_id and '_' in node_id:
                parts = node_id.split('_')
                if len(parts) >= 2:
                    try:
                        feature_idx = int(parts[1])
                    except (ValueError, IndexError):
                        pass
            
            # SKIP nodi senza feature_idx valido (no fallback fasullo!)
            if layer is None or feature_idx is None:
                skipped_count += 1
                continue
            
            all_features.append({
                "layer": int(layer),
                "feature": int(feature_idx),  # Ora contiene l'indice corretto!
                "original_activation": float(node.get("activation", 0)),
                "original_ctx_idx": int(node.get("ctx_idx", 0)),
                "influence": float(node.get("influence", 0)),
            })
        
        st.write(f"**Features totali nel grafo:** {len(all_features)}")
        
        if st.button("📋 Usa Tutte le Features", type="primary"):
            st.session_state['filtered_features'] = all_features
            st.success(f"✅ Caricate {len(all_features)} features dal grafo")
            st.rerun()
    
    with tab_export:
        st.subheader("Esporta Feature Subset Corrente")
        
        if 'filtered_features' in st.session_state and st.session_state['filtered_features']:
            features_to_export = st.session_state['filtered_features']
            
            st.write(f"**Features da esportare:** {len(features_to_export)}")
            
            # Preview prime features
            with st.expander("Preview features"):
                preview_list = [
                    {"layer": f["layer"], "index": f["feature"]}
                    for f in features_to_export[:10]
                ]
                st.json(preview_list)
                if len(features_to_export) > 10:
                    st.caption(f"... e altre {len(features_to_export) - 10} features")
            
            export_filename = st.text_input(
                "Nome file",
                value="feature_subset.json",
                help="Nome del file JSON da salvare"
            )
            
            if st.button("💾 Esporta Feature Subset", type="primary"):
                output_path = parent_dir / "output" / export_filename
                
                try:
                    export_features_list(features_to_export, str(output_path), verbose=False)
                    st.success(f"✅ Feature subset esportato: {output_path.relative_to(parent_dir)}")
                    
                    # Download button
                    with open(output_path, 'r', encoding='utf-8') as f:
                        features_json_str = f.read()
                    
                    st.download_button(
                        label="⬇️ Scarica Feature Subset",
                        data=features_json_str,
                        file_name=export_filename,
                        mime="application/json"
                    )
                    
                except Exception as e:
                    st.error(f"❌ Errore nell'export: {e}")
        else:
            st.info("⚠️ Nessuna feature selezionata. Carica un subset o usa tutte le features prima.")

# ===== STEP 3: DEFINISCI CONCEPTS =====

if graph_json:
    st.header("3️⃣ Define Concepts")
    
    # Tab per generazione automatica o manuale
    tab_gen, tab_manual, tab_load = st.tabs(["🤖 Genera con OpenAI", "✏️ Inserimento Manuale", "📂 Carica da File"])
    
    with tab_gen:
        st.subheader("Automatic Concept Generation")
        
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
                        
                        st.success(f"✅ Generated {len(concepts_generated)} concepts!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Generation error: {e}")
                        st.exception(e)
    
    with tab_manual:
        st.subheader("Manual Entry")
        
        st.write("Inserisci i concepts in formato JSON:")
        
        default_concepts = [  {
                "label": "Dallas",
                "category": "entity",
                "description": "A city in Texas, USA"
            },
            {
                "label": "Austin",
                "category": "entity",
                "description": "The capital city of Texas"
            },
            {
                "label": "Texas",
                "category": "entity",
                "description": "A state in the United States"
            },
            {
                "label": "the capital city",
                "category": "attribute",
                "description": "The primary city serving as the seat of government for a state"
            },
            {
                "label": "the state containing",
                "category": "relationship",
                "description": "the state in which a city is located"
            }
            ]
        
        manual_json = st.text_area(
            "JSON Concepts",
            value=json.dumps(default_concepts, indent=2),
            height=300,
            help="Array JSON con format: [{label, category, description}, ...]"
        )
        
        if st.button("Load Concepts Manually"):
            try:
                concepts_manual = json.loads(manual_json)
                st.session_state['concepts'] = concepts_manual
                st.success(f"✅ Loaded {len(concepts_manual)} concepts!")
                st.rerun()
            except json.JSONDecodeError as e:
                st.error(f"❌ JSON parsing error: {e}")
    
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

# modifica concepts:

if 'concepts' in st.session_state and st.session_state['concepts']:
    
    
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
        if st.button("💾 Save Concepts as Prompts JSON"):
            output_dir = parent_dir / "output"
            output_prompts_path = output_dir / f"prompts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
            output_prompts_path.parent.mkdir(parents=True, exist_ok=True)
            
            # Usa la funzione export_concepts_to_prompts
            export_concepts_to_prompts(st.session_state['concepts'], str(output_prompts_path), verbose=False)
            st.success(f"✅ Prompts salvati in: {output_prompts_path.relative_to(parent_dir)}")
            st.info("Formato: `[{\"id\": \"probe_X\", \"text\": \"categoria: descrizione is label\"}, ...]`")
    
    with col2:
        # Download button - formato prompts
        prompts_list = []
        for i, concept in enumerate(st.session_state['concepts']):
            label = concept.get("label", "").strip()
            category = concept.get("category", "").strip()
            description = concept.get("description", "").strip()
            if label and category and description:
                prompt_text = f"{category}: {description} is {label}"
                probe_id = f"probe_{i}_{label.replace(' ', '_')}"
                prompts_list.append({"id": probe_id, "text": prompt_text})
        
        prompts_json = json.dumps(prompts_list, indent=2, ensure_ascii=False)
        st.download_button(
            label="⬇️ Scarica Prompts JSON",
            data=prompts_json,
            file_name=f"prompts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
            mime="application/json",
            help="Formato compatibile con batch_get_activations.py"
        )

# ===== STEP 4: RUN ANALYSIS =====

if 'concepts' in st.session_state and st.session_state['concepts']:
    st.header("4️⃣ Run Analysis")
    
    # Crea tabs per metodi di analisi diversi
    tab1, tab2 = st.tabs(["🌐 Analisi tramite API", "📁 Carica da file"])
    
    with tab1:
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
                st.error("❌ Neuronpedia API Key not configured")
                st.stop()
            
            if 'filtered_features' not in st.session_state:
                st.error("❌ Features non caricate. Completa lo Step 2 (Carica Feature Subset).")
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
                
                # Sovrascrive temporaneamente il filtraggio: usa features già caricate
                # (analyze_concepts_from_graph_json estrae dal graph, noi passiamo già il subset)
                
                # Prepara graph_json modificato con solo le features selezionate
                filtered_graph = graph_json.copy()
                if 'filtered_features' in st.session_state:
                    # Filtra nodes nel graph per includere solo le features selezionate
                    selected_keys = {(f['layer'], f['feature']) for f in st.session_state['filtered_features']}
                    filtered_nodes = []
                    skipped_nodes_filter = 0
                    
                    for node in graph_json.get('nodes', []):
                        if node.get('feature_type') == 'cross layer transcoder':
                            layer = node.get('layer')
                            
                            # Estrai feature_index dal node_id (formato: "layer_featureIndex_sequence")
                            node_id = node.get("node_id", "")
                            feature = None
                            
                            if node_id and '_' in node_id:
                                parts = node_id.split('_')
                                if len(parts) >= 2:
                                    try:
                                        feature = int(parts[1])
                                    except (ValueError, IndexError):
                                        pass
                            
                            # SKIP nodi senza feature valido (no fallback fasullo!)
                            if feature is None:
                                skipped_nodes_filter += 1
                                continue
                            
                            if (int(layer), int(feature)) in selected_keys:
                                filtered_nodes.append(node)
                        else:
                            # Mantieni nodi non-feature (logits, embeddings)
                            filtered_nodes.append(node)
                    
                    filtered_graph['nodes'] = filtered_nodes
                    
                    if skipped_nodes_filter > 0:
                        log_messages.append(f"⚠️ {skipped_nodes_filter} nodi feature con node_id malformato skippati")
                
                df_results = analyze_concepts_from_graph_json(
                    graph_json=filtered_graph,
                    concepts=st.session_state['concepts'],
                    api_key=neuronpedia_key,
                    activation_threshold_quantile=activation_threshold,
                    use_baseline=use_baseline,
                    cumulative_contribution=1.0,  # Usa tutte le features (già filtrate)
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
                3. Click "Run Analysis"
                
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
        
        # ===== VISUALIZZA RISULTATI (tab API) =====
        
        if 'analysis_results' in st.session_state:
            st.markdown("---")
            st.subheader("📊 Results")
            
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
                st.subheader("Quick Statistics")
                
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
    
    with tab2:
        st.markdown("""
        ### 📁 Carica Attivazioni da File JSON
        
        Carica un file JSON con attivazioni pre-calcolate (es. generato con `batch_get_activations.py` su Colab).
        
        **Formato atteso:**
        ```json
        {
          "model": "gemma-2-2b",
          "source_set": "clt-hp",
          "results": [
            {
              "probe_id": "p1",
              "prompt": "...",
              "tokens": [...],
              "counts": [[...]],
              "activations": [{"source": "10-clt-hp", "index": 123, "values": [...], ...}]
            }
          ]
        }
        ```
        """)
        
        uploaded_file = st.file_uploader(
            "Seleziona file JSON",
            type=['json'],
            help="File JSON con attivazioni pre-calcolate da batch_get_activations.py"
        )
        
        if uploaded_file is not None:
            try:
                # Carica il JSON
                activations_data = json.load(uploaded_file)
                
                # Mostra info sul file caricato
                st.success("✅ File caricato con successo!")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Modello", activations_data.get('model', 'N/A'))
                with col2:
                    st.metric("SAE Set", activations_data.get('source_set', 'N/A'))
                with col3:
                    n_results = len(activations_data.get('results', []))
                    st.metric("Prompt Processati", n_results)
                
                # Mostra anteprima risultati
                if 'results' in activations_data and len(activations_data['results']) > 0:
                    st.markdown("---")
                    st.subheader("📊 Anteprima Dati")
                    
                    # Crea DataFrame di riepilogo
                    summary_data = []
                    for result in activations_data['results']:
                        summary_data.append({
                            'Probe ID': result.get('probe_id', 'N/A'),
                            'Prompt': result.get('prompt', '')[:60] + '...' if len(result.get('prompt', '')) > 60 else result.get('prompt', ''),
                            'N. Token': len(result.get('tokens', [])),
                            'N. Attivazioni': len(result.get('activations', []))
                        })
                    
                    import pandas as pd
                    df_summary = pd.DataFrame(summary_data)
                    st.dataframe(df_summary, use_container_width=True)
                    
                    # Mostra dettagli primo prompt (esempio)
                    with st.expander("🔍 Dettagli primo prompt", expanded=False):
                        first_result = activations_data['results'][0]
                        st.write(f"**Probe ID:** {first_result.get('probe_id', 'N/A')}")
                        st.write(f"**Prompt:** {first_result.get('prompt', 'N/A')}")
                        st.write(f"**Token:** `{first_result.get('tokens', [])[:10]}`{'...' if len(first_result.get('tokens', [])) > 10 else ''}")
                        st.write(f"**Attivazioni trovate:** {len(first_result.get('activations', []))}")
                        
                        if first_result.get('activations'):
                            st.write("**Prime 3 attivazioni:**")
                            for i, act in enumerate(first_result['activations'][:3], 1):
                                st.json({
                                    f"Attivazione {i}": {
                                        'source': act.get('source'),
                                        'index': act.get('index'),
                                        'max_value': act.get('max_value'),
                                        'max_value_index': act.get('max_value_index'),
                                        'n_values': len(act.get('values', []))
                                    }
                                })
                    
                    # ===== GRAFICO: IMPORTANCE vs ACTIVATION =====
                    st.markdown("---")
                    st.subheader("📈 Main Chart: Importance vs Activation")
                    
                    st.caption("""
                    **Grafico a barre**: Features ordinate per importanza causale (node_influence).
                    Altezza barra = peak activation (max_value, **escludendo BOS**). Colore = prompt.
                    Linea rossa = node_influence score.
                    """)
                    
                    # Config
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        top_n = st.slider("Mostra top N features (per node_influence)", 10, 100, 30, 5)
                    with col2:
                        exclude_bos = st.checkbox("Escludi features con peak su <BOS>", value=False, 
                                                  help="Rimuove features il cui picco è sul token BOS")
                    
                    # Carica node_influence dal CSV
                    csv_path = parent_dir / "output" / "graph_feature_static_metrics.csv"
                    
                    if not csv_path.exists():
                        st.warning(f"⚠️ CSV con node_influence non trovato: `{csv_path.relative_to(parent_dir)}`")
                        st.info("Genera prima il CSV usando **00_Graph_Generation.py** > 'Genera CSV Metriche'")
                    else:
                        try:
                            feats_csv = pd.read_csv(csv_path, encoding='utf-8')
                            feats_csv['feature_key'] = feats_csv['layer'].astype(int).astype(str) + '_' + feats_csv['id'].astype(int).astype(str)
                            feats_csv = feats_csv[['feature_key', 'node_influence']]
                            
                            # Estrai attivazioni per prompt/feature dal JSON
                            import re
                            rows = []
                            for res in activations_data.get('results', []):
                                prompt = res.get('prompt', '')
                                tokens = res.get('tokens', [])
                                T = len(tokens)
                                
                                for a in res.get('activations', []):
                                    src = str(a.get('source', ''))
                                    # Estrai layer dal prefisso numerico (es. "10-clt-hp" -> 10)
                                    try:
                                        layer = int(src.split('-', 1)[0])
                                    except Exception:
                                        m = re.search(r'(\d+)', src)
                                        layer = int(m.group(1)) if m else None
                                    
                                    idx = int(a.get('index'))
                                    if layer is None:
                                        continue
                                    
                                    feature_key = f"{layer}_{idx}"
                                    
                                    # Estrai values e calcola max ESCLUDENDO il primo elemento (BOS)
                                    values = a.get('values', [])
                                    if len(values) > 1:
                                        # Escludi indice 0 (BOS), trova max tra gli altri
                                        values_no_bos = values[1:]
                                        max_value = max(values_no_bos) if values_no_bos else None
                                        # Indice relativo a values_no_bos, aggiungi 1 per l'offset
                                        max_idx = values_no_bos.index(max_value) + 1 if max_value is not None else None
                                    else:
                                        max_value = None
                                        max_idx = None
                                    
                                    peak_token = tokens[max_idx] if isinstance(max_idx, int) and 0 <= max_idx < T else None
                                    
                                    rows.append({
                                        'feature_key': feature_key,
                                        'prompt': prompt,
                                        'activation': max_value,
                                        'peak_token': peak_token
                                    })
                            
                            act_df = pd.DataFrame(rows)
                            
                            # Info pre-filtro
                            n_before = len(act_df)
                            n_bos = len(act_df[act_df['peak_token'] == '<BOS>'])
                            
                            # Filtro BOS
                            if exclude_bos:
                                act_df = act_df[act_df['peak_token'] != '<BOS>']
                                if len(act_df) == 0 and n_bos > 0:
                                    st.warning(f"⚠️ Tutte le {n_before} attivazioni sono state filtrate perché hanno peak su <BOS>!")
                                    st.info("💡 Disabilita il filtro BOS per visualizzare queste features.")
                            
                            if act_df.empty:
                                st.info("Nessuna attivazione disponibile per il grafico.")
                            else:
                                # Info dataset
                                n_unique_features = act_df['feature_key'].nunique()
                                n_prompts = act_df['prompt'].nunique()
                                if n_unique_features <= 5:
                                    st.info(f"📊 Dataset contiene solo {n_unique_features} feature(s) uniche su {n_prompts} prompt(s)")
                                
                                # Aggrega per feature/prompt: max activation
                                agg = act_df.groupby(['feature_key', 'prompt'], as_index=False)['activation'].max()
                                
                                # TABELLA DI VERIFICA DATI
                                with st.expander("🔍 Tabella di Verifica Dati (JSON + CSV)", expanded=False):
                                    st.caption("""
                                    **Dati grezzi usati per il grafico**: ogni riga = combinazione feature + prompt.
                                    
                                    **Metriche di attivazione** (tutte escludono BOS):
                                    - `activation_max` → Picco massimo di attivazione
                                    - `activation_sum` → Somma totale delle attivazioni
                                    - `activation_mean` → Media delle attivazioni (normalizzata per lunghezza)
                                    - `sparsity_ratio` → (max - mean) / max. Misura quanto è concentrata l'attivazione:
                                      - **~0**: attivazione uniforme/distribuita su tutti i token
                                      - **~1**: attivazione molto sparsa (solo pochi picchi forti)
                                    
                                    **Altre colonne**:
                                    - `peak_token_idx` → Posizione del picco (1+ per esclusione BOS)
                                    - `node_influence` → Valore massimo dal CSV per quella feature_key 
                                      (una feature può apparire più volte nel CSV con diversi ctx_idx)
                                    - `csv_ctx_idx` → Contesto del token dove node_influence è massima
                                    """)
                                    
                                    # Prepara dati dal JSON con più dettagli
                                    verification_rows = []
                                    for res in activations_data.get('results', []):
                                        prompt = res.get('prompt', '')
                                        tokens = res.get('tokens', [])
                                        T = len(tokens)
                                        
                                        for a in res.get('activations', []):
                                            src = str(a.get('source', ''))
                                            try:
                                                layer = int(src.split('-', 1)[0])
                                            except Exception:
                                                m = re.search(r'(\d+)', src)
                                                layer = int(m.group(1)) if m else None
                                            
                                            idx = int(a.get('index'))
                                            if layer is None:
                                                continue
                                            
                                            feature_key = f"{layer}_{idx}"
                                            
                                            # Estrai values e calcola max ESCLUDENDO il primo elemento (BOS)
                                            values = a.get('values', [])
                                            if len(values) > 1:
                                                # Escludi indice 0 (BOS), trova max tra gli altri
                                                values_no_bos = values[1:]
                                                max_value = max(values_no_bos) if values_no_bos else None
                                                # Indice relativo a values_no_bos, aggiungi 1 per l'offset
                                                max_idx = values_no_bos.index(max_value) + 1 if max_value is not None else None
                                                # Calcola somma e media escludendo BOS
                                                sum_values = sum(values_no_bos) if values_no_bos else 0
                                                mean_value = sum_values / len(values_no_bos) if values_no_bos else 0
                                                # Calcola sparsity ratio: quanto è concentrata l'attivazione
                                                # 0 = uniforme (tutte simili), 1 = molto sparsa (solo picchi)
                                                sparsity = (max_value - mean_value) / max_value if max_value and max_value > 0 else 0
                                            else:
                                                max_value = None
                                                max_idx = None
                                                sum_values = 0
                                                mean_value = 0
                                                sparsity = 0
                                            peak_token = tokens[max_idx] if isinstance(max_idx, int) and 0 <= max_idx < T else None
                                            
                                            # Applica filtro BOS se attivo
                                            if exclude_bos and peak_token == '<BOS>':
                                                continue
                                            
                                            verification_rows.append({
                                                'feature_key': feature_key,
                                                'layer': layer,
                                                'index': idx,
                                                'source': src,
                                                'prompt': prompt[:50] + '...' if len(prompt) > 50 else prompt,
                                                'activation_max': max_value,
                                                'activation_sum': sum_values,
                                                'activation_mean': mean_value,
                                                'sparsity_ratio': sparsity,
                                                'peak_token': peak_token,
                                                'peak_token_idx': max_idx
                                            })
                                    
                                    verify_df = pd.DataFrame(verification_rows)
                                    
                                    # Carica CSV completo per avere ctx_idx
                                    csv_full = pd.read_csv(csv_path, encoding='utf-8')
                                    csv_full['feature_key'] = csv_full['layer'].astype(int).astype(str) + '_' + csv_full['id'].astype(int).astype(str)
                                    
                                    # Per ogni feature_key, prendi max(node_influence) e il ctx_idx corrispondente
                                    # Ordina per node_influence e prendi l'ultimo (max)
                                    csv_max = csv_full.sort_values('node_influence').groupby('feature_key', as_index=False).last()
                                    csv_max = csv_max[['feature_key', 'node_influence', 'ctx_idx']]
                                    csv_max = csv_max.rename(columns={'ctx_idx': 'csv_ctx_idx'})
                                    
                                    # Merge con CSV (left join per vedere anche i NaN)
                                    verify_full = verify_df.merge(
                                        csv_max, 
                                        on='feature_key', 
                                        how='left'
                                    )
                                    
                                    # Riordina colonne
                                    cols_order = ['feature_key', 'layer', 'index', 'source', 'prompt', 
                                                  'activation_max', 'activation_sum', 'activation_mean', 'sparsity_ratio',
                                                  'peak_token', 'peak_token_idx',
                                                  'node_influence', 'csv_ctx_idx']
                                    verify_full = verify_full[cols_order]
                                    
                                    # Ordina per node_influence (nulls last) e poi per feature_key
                                    verify_full = verify_full.sort_values(
                                        ['node_influence', 'feature_key'], 
                                        ascending=[False, True],
                                        na_position='last'
                                    )
                                    
                                    # Info
                                    n_total_rows = len(verify_full)
                                    n_features = verify_full['feature_key'].nunique()
                                    n_prompts_verify = verify_full['prompt'].nunique()
                                    n_missing_influence = verify_full['node_influence'].isna().sum()
                                    
                                    st.info(f"""
                                    **📊 Dataset verificato**:
                                    - Righe totali: {n_total_rows} (combinazioni feature × prompt)
                                    - Features uniche: {n_features}
                                    - Prompts unici: {n_prompts_verify}
                                    - Righe senza node_influence: {n_missing_influence}
                                    - **node_influence**: max per ogni feature_key (una feature può avere più valori nel CSV per diversi ctx_idx)
                                    - **csv_ctx_idx**: contesto del token dove node_influence è massima
                                    {' - ⚠️ Filtro BOS attivo: righe con peak su <BOS> escluse' if exclude_bos else ''}
                                    """)
                                    
                                    # Mostra tabella
                                    st.dataframe(
                                        verify_full,
                                        use_container_width=True,
                                        height=400
                                    )
                                    
                                    # Statistiche metriche di attivazione
                                    with st.expander("📊 Statistiche Metriche di Attivazione"):
                                        stats_cols = st.columns(4)
                                        
                                        with stats_cols[0]:
                                            st.metric("Max (media)", f"{verify_full['activation_max'].mean():.2f}")
                                            st.caption(f"Range: {verify_full['activation_max'].min():.2f} - {verify_full['activation_max'].max():.2f}")
                                        
                                        with stats_cols[1]:
                                            st.metric("Sum (media)", f"{verify_full['activation_sum'].mean():.2f}")
                                            st.caption(f"Range: {verify_full['activation_sum'].min():.2f} - {verify_full['activation_sum'].max():.2f}")
                                        
                                        with stats_cols[2]:
                                            st.metric("Mean (media)", f"{verify_full['activation_mean'].mean():.2f}")
                                            st.caption(f"Range: {verify_full['activation_mean'].min():.2f} - {verify_full['activation_mean'].max():.2f}")
                                        
                                        with stats_cols[3]:
                                            avg_sparsity = verify_full['sparsity_ratio'].mean()
                                            st.metric("Sparsity (media)", f"{avg_sparsity:.3f}")
                                            st.caption(f"Range: {verify_full['sparsity_ratio'].min():.3f} - {verify_full['sparsity_ratio'].max():.3f}")
                                            if avg_sparsity > 0.7:
                                                st.caption("🎯 Features molto sparse")
                                            elif avg_sparsity > 0.4:
                                                st.caption("⚖️ Sparsity moderata")
                                            else:
                                                st.caption("📊 Features distribuite")
                                    
                                    # Download CSV
                                    csv_export = verify_full.to_csv(index=False).encode('utf-8')
                                    st.download_button(
                                        label="💾 Scarica tabella verifica (CSV)",
                                        data=csv_export,
                                        file_name="probe_prompts_verification_data.csv",
                                        mime="text/csv"
                                    )
                                
                                # ===== CHECK DI CORRETTEZZA DATI =====
                                
                                # CHECK 1: Verifica che verify_full abbia node_influence
                                n_with_ni = verify_full['node_influence'].notna().sum()
                                n_total_verify = len(verify_full)
                                
                                if n_with_ni == 0:
                                    st.error("❌ ERRORE: Nessuna feature nel JSON ha node_influence dal CSV!")
                                    st.info("Possibili cause:\n- CSV non generato dallo stesso grafo\n- Colonna 'id' nel CSV non corrisponde a 'index' nel JSON")
                                    st.stop()
                                
                                if n_with_ni < n_total_verify:
                                    st.warning(f"⚠️ WARNING: {n_total_verify - n_with_ni}/{n_total_verify} righe senza node_influence")
                                
                                # CHECK 2: Verifica che activation_max sia sempre calcolata
                                n_null_act = verify_full['activation_max'].isna().sum()
                                if n_null_act > 0:
                                    st.warning(f"⚠️ WARNING: {n_null_act} righe con activation_max = null")
                                
                                # CHECK 3: Verifica che peak_token_idx non sia mai 0 (dovrebbe essere sempre >= 1, escludendo BOS)
                                n_bos_peak = (verify_full['peak_token_idx'] == 0).sum()
                                if n_bos_peak > 0:
                                    st.error(f"❌ ERRORE: {n_bos_peak} righe hanno peak_token_idx=0 (BOS)! Il calcolo del max non ha escluso BOS correttamente.")
                                
                                # CHECK 4: Verifica coerenza dati tra verify_full e agg
                                verify_check = verify_full.groupby(['feature_key', 'prompt'], as_index=False)['activation_max'].max()
                                verify_check = verify_check.rename(columns={'activation_max': 'activation'})
                                
                                # Merge per confronto
                                comparison = agg.merge(
                                    verify_check, 
                                    on=['feature_key', 'prompt'], 
                                    how='outer',
                                    suffixes=('_agg', '_verify')
                                )
                                
                                n_mismatch = 0
                                if 'activation_agg' in comparison.columns and 'activation_verify' in comparison.columns:
                                    # Conta le differenze significative (> 0.001)
                                    comparison['diff'] = abs(comparison['activation_agg'].fillna(0) - comparison['activation_verify'].fillna(0))
                                    n_mismatch = (comparison['diff'] > 0.001).sum()
                                    
                                    if n_mismatch > 0:
                                        st.warning(f"⚠️ WARNING: {n_mismatch} righe con differenze tra dati aggregati e tabella verifica")
                                        with st.expander("Mostra differenze"):
                                            st.dataframe(comparison[comparison['diff'] > 0.001])
                                
                                # ===== PREPARAZIONE DATI PER GRAFICO =====
                                # Usa DIRETTAMENTE verify_full (già filtrato per BOS se richiesto)
                                
                                # Filtra solo righe con node_influence valida
                                plot_data = verify_full[verify_full['node_influence'].notna()].copy()
                                
                                if plot_data.empty:
                                    st.warning("❌ Nessuna feature con node_influence disponibile per il grafico.")
                                else:
                                    # Seleziona top N features per node_influence
                                    # Per ogni feature_key, prendiamo il max node_influence (già fatto nella tabella)
                                    top_features_ni = plot_data.groupby('feature_key', as_index=False)['node_influence'].max()
                                    top_features_ni = top_features_ni.sort_values('node_influence', ascending=False).head(top_n)
                                    top_feats = top_features_ni['feature_key'].tolist()
                                    
                                    # Filtra plot_data per le top features
                                    plot_data_top = plot_data[plot_data['feature_key'].isin(top_feats)].copy()
                                    
                                    # Pivot: righe=feature, colonne=prompt, valori=activation_max
                                    pivot_data = plot_data_top.pivot_table(
                                        index='feature_key', 
                                        columns='prompt', 
                                        values='activation_max', 
                                        aggfunc='max', 
                                        fill_value=0
                                    )
                                    
                                    # Crea mappatura node_influence per ordinamento
                                    ni_map = top_features_ni.set_index('feature_key')['node_influence'].to_dict()
                                    
                                    # Ordina pivot_data per node_influence (decrescente)
                                    pivot_data = pivot_data.loc[[f for f in top_feats if f in pivot_data.index]]
                                    
                                    # CHECK 5: Verifica che tutte le top features siano nel pivot
                                    missing_in_pivot = set(top_feats) - set(pivot_data.index)
                                    if missing_in_pivot:
                                        st.warning(f"⚠️ WARNING: {len(missing_in_pivot)} features tra le top {top_n} non hanno dati nel pivot: {missing_in_pivot}")
                                    
                                    # Costruisci grafico
                                    import plotly.graph_objects as go
                                    fig = go.Figure()
                                    
                                    # Barre per prompt
                                    for prompt in pivot_data.columns:
                                        fig.add_trace(go.Bar(
                                            name=prompt[:30] + '...' if len(prompt) > 30 else prompt,
                                            x=pivot_data.index,
                                            y=pivot_data[prompt],
                                            hovertemplate=f'<b>{prompt}</b><br>Feature: %{{x}}<br>Activation (max_value): %{{y:.3f}}<extra></extra>'
                                        ))
                                    
                                    # Linea node_influence (asse destro)
                                    importance_line = [ni_map.get(f, 0) for f in pivot_data.index]
                                    
                                    # Se ci sono poche features, usa markers più grandi
                                    marker_size = 12 if len(pivot_data) <= 5 else 8
                                    
                                    fig.add_trace(go.Scatter(
                                        name='Importance (node_influence)',
                                        x=pivot_data.index,
                                        y=importance_line,
                                        mode='lines+markers',
                                        line=dict(color='red', width=3),
                                        marker=dict(size=marker_size, color='red'),
                                        yaxis='y2',
                                        hovertemplate='<b>node_influence</b><br>Feature: %{x}<br>Score: %{y:.4f}<extra></extra>'
                                    ))
                                    
                                    title_suffix = " [BOS EXCLUDED]" if exclude_bos else ""
                                    fig.update_layout(
                                        title=f"Top {len(pivot_data)} Features: Activation by Prompt + Importance{title_suffix}",
                                        xaxis_title="Feature (ordered by node_influence)",
                                        yaxis_title="Activation (max_value)",
                                        yaxis2=dict(
                                            title='node_influence',
                                            overlaying='y',
                                            side='right'
                                        ),
                                        barmode='stack',
                                        height=600,
                                        hovermode='x unified',
                                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                                    )
                                    
                                    st.plotly_chart(fig, use_container_width=True)
                                    
                                    # ===== CHECK POST-GRAFICO =====
                                    # Verifica coerenza dati nel grafico
                                    with st.expander("✅ Check Correttezza Grafico"):
                                        st.markdown("**Verifiche effettuate:**")
                                        
                                        check_results = []
                                        
                                        # Check 1: Tutti i dati dal verify_full
                                        check_results.append(f"✅ Grafico usa direttamente `verify_full` (tabella di verifica)")
                                        
                                        # Check 2: Activation esclude BOS
                                        n_bos_in_plot = (plot_data_top['peak_token_idx'] == 0).sum()
                                        if n_bos_in_plot == 0:
                                            check_results.append(f"✅ Nessuna activation con peak su BOS (indice 0)")
                                        else:
                                            check_results.append(f"❌ {n_bos_in_plot} activation con peak su BOS!")
                                        
                                        # Check 3: node_influence presente per tutte le features visualizzate
                                        n_ni_in_plot = plot_data_top['node_influence'].notna().sum()
                                        n_total_plot = len(plot_data_top)
                                        if n_ni_in_plot == n_total_plot:
                                            check_results.append(f"✅ Tutte le {n_total_plot} righe del grafico hanno node_influence")
                                        else:
                                            check_results.append(f"⚠️ Solo {n_ni_in_plot}/{n_total_plot} righe hanno node_influence")
                                        
                                        # Check 4: Ordinamento corretto
                                        actual_order = list(pivot_data.index)
                                        expected_order = top_feats[:len(actual_order)]
                                        if actual_order == expected_order:
                                            check_results.append(f"✅ Ordinamento features corretto per node_influence decrescente")
                                        else:
                                            check_results.append(f"⚠️ Ordinamento features non corrisponde")
                                        
                                        # Check 5: Range valori sensati
                                        max_act = plot_data_top['activation_max'].max()
                                        min_act = plot_data_top[plot_data_top['activation_max'] > 0]['activation_max'].min()
                                        max_ni = plot_data_top['node_influence'].max()
                                        min_ni = plot_data_top['node_influence'].min()
                                        
                                        check_results.append(f"ℹ️ Activation range: [{min_act:.2f}, {max_act:.2f}]")
                                        check_results.append(f"ℹ️ node_influence range: [{min_ni:.6f}, {max_ni:.6f}]")
                                        
                                        for result in check_results:
                                            st.markdown(f"- {result}")
                                    
                                    # ===== GRAFICO 2: COLORATO PER PEAK TOKEN =====
                                    st.markdown("---")
                                    st.subheader("🎨 Alternative View: Colored by Peak Token")
                                    
                                    st.caption("""
                                    **Stesso grafico ma colorato diversamente**: Ogni colore rappresenta un **token di picco** diverso.
                                    Utile per vedere quali token attivano maggiormente le features.
                                    """)
                                    
                                    # Pivot per peak_token invece che per prompt
                                    # Dobbiamo aggregare: per ogni feature + peak_token, prendiamo max activation
                                    pivot_by_token = plot_data_top.pivot_table(
                                        index='feature_key',
                                        columns='peak_token',
                                        values='activation_max',
                                        aggfunc='max',
                                        fill_value=0
                                    )
                                    
                                    # Ordina pivot per mantenere stesso ordine del primo grafico (per node_influence)
                                    pivot_by_token = pivot_by_token.loc[[f for f in top_feats if f in pivot_by_token.index]]
                                    
                                    # Costruisci secondo grafico
                                    fig2 = go.Figure()
                                    
                                    # Genera palette di colori distintivi
                                    import plotly.express as px
                                    colors = px.colors.qualitative.Set3
                                    if len(pivot_by_token.columns) > len(colors):
                                        colors = colors * (len(pivot_by_token.columns) // len(colors) + 1)
                                    
                                    # Barre per peak_token
                                    for i, token in enumerate(pivot_by_token.columns):
                                        if token is None or pd.isna(token):
                                            token_label = "[NULL]"
                                        else:
                                            token_label = str(token)
                                        
                                        fig2.add_trace(go.Bar(
                                            name=token_label,
                                            x=pivot_by_token.index,
                                            y=pivot_by_token[token],
                                            marker_color=colors[i % len(colors)],
                                            hovertemplate=f'<b>Peak Token: {token_label}</b><br>Feature: %{{x}}<br>Activation (max_value): %{{y:.3f}}<extra></extra>'
                                        ))
                                    
                                    # Linea node_influence (asse destro) - stessa del primo grafico
                                    importance_line_2 = [ni_map.get(f, 0) for f in pivot_by_token.index]
                                    marker_size_2 = 12 if len(pivot_by_token) <= 5 else 8
                                    
                                    fig2.add_trace(go.Scatter(
                                        name='Importance (node_influence)',
                                        x=pivot_by_token.index,
                                        y=importance_line_2,
                                        mode='lines+markers',
                                        line=dict(color='red', width=3),
                                        marker=dict(size=marker_size_2, color='red'),
                                        yaxis='y2',
                                        hovertemplate='<b>node_influence</b><br>Feature: %{x}<br>Score: %{y:.4f}<extra></extra>'
                                    ))
                                    
                                    fig2.update_layout(
                                        title=f"Top {len(pivot_by_token)} Features: Activation by Peak Token + Importance{title_suffix}",
                                        xaxis_title="Feature (ordered by node_influence)",
                                        yaxis_title="Activation (max_value)",
                                        yaxis2=dict(
                                            title='node_influence',
                                            overlaying='y',
                                            side='right'
                                        ),
                                        barmode='stack',
                                        height=600,
                                        hovermode='x unified',
                                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
                                    )
                                    
                                    st.plotly_chart(fig2, use_container_width=True)
                                    
                                    # Info sui token
                                    n_unique_tokens = pivot_by_token.columns.notna().sum()
                                    st.info(f"""
                                    **📊 Token Analysis**:
                                    - Tokens unici con picco: {n_unique_tokens}
                                    - Features visualizzate: {len(pivot_by_token)}
                                    - Ogni colore = diverso token dove la feature raggiunge il picco
                                    """)
                                    
                                    # Dettagli token più frequenti
                                    with st.expander("🔍 Token più frequenti come picco"):
                                        token_freq = plot_data_top['peak_token'].value_counts()
                                        token_freq_df = pd.DataFrame({
                                            'peak_token': token_freq.index,
                                            'count': token_freq.values,
                                            'percentage': (token_freq.values / len(plot_data_top) * 100).round(1)
                                        })
                                        st.dataframe(token_freq_df.head(20), use_container_width=True)
                                    
                                    # ===== BARRE DI COPERTURA =====
                                    st.markdown("---")
                                    
                                    # Feature attive = features con activation_max > 0 in verify_full
                                    features_with_signal = verify_full[verify_full['activation_max'] > 0]['feature_key'].unique()
                                    n_features_active = len(features_with_signal)
                                    
                                    # Feature totali = feature_key uniche nel JSON caricato (verify_full)
                                    # NON dal CSV (che contiene tutte le features del grafo)
                                    n_features_total = verify_full['feature_key'].nunique()
                                    
                                    # Calcola node_influence per feature attive vs totale
                                    # Usa max(node_influence) per feature_key, MA SOLO per le features nel JSON
                                    csv_max_ni_json = verify_full.groupby('feature_key', as_index=False)['node_influence'].max()
                                    active_features_influence = csv_max_ni_json[csv_max_ni_json['feature_key'].isin(features_with_signal)]['node_influence'].sum()
                                    total_influence = csv_max_ni_json['node_influence'].sum()
                                    
                                    # Percentuali
                                    pct_features = (n_features_active / n_features_total * 100) if n_features_total > 0 else 0
                                    pct_influence = (active_features_influence / total_influence * 100) if total_influence > 0 else 0
                                    
                                    # Progress bars
                                    st.markdown("**📊 Coverage Analysis (Features attive sui probe prompts)**")
                                    
                                    # Barra 1: Feature count
                                    st.markdown(f"**Features Coverage:** {n_features_active} / {n_features_total} features ({pct_features:.1f}%)")
                                    st.progress(pct_features / 100)
                                    
                                    # Barra 2: Node influence
                                    st.markdown(f"**Importance Coverage:** {active_features_influence:.4f} / {total_influence:.4f} node_influence ({pct_influence:.1f}%)")
                                    st.progress(pct_influence / 100)
                                    
                                    st.caption("""
                                    💡 **Interpretazione**: 
                                    - Features Coverage = % di features (nel JSON caricato) che si attivano (>0) su almeno uno dei probe prompts
                                    - Importance Coverage = % dell'importanza causale (delle features nel JSON) coperta dalle features attive
                                    
                                    📌 I valori di riferimento sono le features presenti nel JSON caricato, non l'intero grafo.
                                    """)
                                    
                                    # Dettagli features visualizzate
                                    with st.expander("🔍 Dettagli features visualizzate"):
                                        details_df = pd.DataFrame({
                                            'feature_key': pivot_data.index,
                                            'node_influence': importance_line
                                        })
                                        # Aggiungi anche le attivazioni per prompt
                                        for col in pivot_data.columns:
                                            details_df[f"act_{col[:20]}"] = pivot_data[col].values
                                        
                                        st.dataframe(details_df, use_container_width=True)
                                    
                                    # Metriche riepilogative
                                    st.markdown("---")
                                    col1, col2, col3, col4 = st.columns(4)
                                    with col1:
                                        st.metric("Features visualizzate", len(pivot_data))
                                    with col2:
                                        st.metric("Prompt analizzati", len(pivot_data.columns))
                                    with col3:
                                        avg_importance = sum(importance_line) / len(importance_line) if importance_line else 0
                                        st.metric("Avg node_influence", f"{avg_importance:.4f}")
                                    with col4:
                                        avg_activation = pivot_data.values.mean()
                                        st.metric("Avg activation", f"{avg_activation:.3f}")
                                    
                                    # Download dati
                                    st.download_button(
                                        label="📥 Download chart data CSV",
                                        data=pivot_data.to_csv(),
                                        file_name=f'importance_vs_activation_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv',
                                        mime='text/csv'
                                    )
                        
                        except Exception as e:
                            st.error(f"❌ Errore nell'elaborazione del grafico: {e}")
                            st.exception(e)
                
            except json.JSONDecodeError as e:
                st.error(f"❌ Errore nel parsing del JSON: {e}")
            except Exception as e:
                st.error(f"❌ Errore nel caricamento del file: {e}")
                st.exception(e)
        else:
            st.info("👆 Carica un file JSON per visualizzare i dati")

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
2. Carica feature subset o usa tutte le features
3. Genera concepts con OpenAI o inseriscili manualmente
4. Modifica/salva concepts (formato prompts JSON)
5. Esegui l'analisi (tramite API Neuronpedia)
6. Visualizza e scarica i risultati

**Metriche calcolate:**
- Attivazioni su label span e sequenza completa
- Z-scores (standard, robust, log)
- Densità, cosine similarity, ratio vs original
- Influence originale per ogni feature
""")

st.sidebar.caption("Version: 2.0.0 | Probe Prompts API")
