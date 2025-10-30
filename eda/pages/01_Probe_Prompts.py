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
import numpy as np
import re

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

# Load Neuronpedia API key
def load_neuronpedia_key():
    """Load Neuronpedia API key from .env or environment"""
    from dotenv import load_dotenv
    
    # Load .env if exists
    env_file = parent_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    
    return os.environ.get("NEURONPEDIA_API_KEY", "")

neuronpedia_key = load_neuronpedia_key()

if not neuronpedia_key:
    st.sidebar.warning("⚠️ Neuronpedia API Key not found")
    st.sidebar.info("""
    Add `NEURONPEDIA_API_KEY=your-key` to `.env` file 
    or set the environment variable.
    """)
    neuronpedia_key = st.sidebar.text_input("Or enter it here:", type="password", key="neuronpedia_key_input")
else:
    st.sidebar.success("✅ Neuronpedia API Key loaded")

st.sidebar.markdown("---")

# === API KEY OPENAI ===

st.sidebar.subheader("OpenAI (for concepts)")

# Load OpenAI API key
def load_openai_key():
    """Load OpenAI API key from .env or environment"""
    from dotenv import load_dotenv
    
    # Load .env if exists
    env_file = parent_dir / ".env"
    if env_file.exists():
        load_dotenv(env_file)
    
    return os.environ.get("OPENAI_API_KEY", "")

openai_key = load_openai_key()

if not openai_key:
    st.sidebar.warning("⚠️ OpenAI API Key not found")
    st.sidebar.info("""
    Add `OPENAI_API_KEY=your-key` to `.env` file 
    or set the environment variable.
    """)
    openai_key = st.sidebar.text_input("Or enter it here:", type="password", key="openai_key_input")

# Model selection
model_choice = st.sidebar.selectbox(
    "OpenAI Model",
    ["gpt-4o-mini", "gpt-4o", "gpt-3.5-turbo"],
    index=0,
    help="Model to use for concept generation"
)

st.sidebar.markdown("---")

# ===== HELPERS: concepts/prompt JSON normalization =====

def _is_concepts_list(obj):
    return (
        isinstance(obj, list)
        and all(
            isinstance(x, dict)
            and ("label" in x and "category" in x and "description" in x)
            for x in obj
        )
    )


def _is_prompts_list(obj):
    return (
        isinstance(obj, list)
        and all(isinstance(x, dict) and ("text" in x) for x in obj)
    )


def _parse_prompt_text_to_concept(text: str) -> dict:
    t = (text or "").strip()
    # Default fallbacks
    category = ""
    description = ""
    label = ""

    # Split category from the rest: "category: description is label"
    if ":" in t:
        left, _sep, rest = t.partition(":")
        category = left.strip()
    else:
        rest = t

    # Split description and label on last occurrence of " is "
    if " is " in rest:
        desc_part, _sep, label_part = rest.rpartition(" is ")
        description = desc_part.strip()
        label = label_part.strip()
    else:
        # If no " is ", try a simpler split: last token as label
        parts = rest.strip().split()
        if len(parts) >= 2:
            label = parts[-1]
            description = rest.strip()[: -len(label)].strip().rstrip(":")
        else:
            # Give up; put everything as description
            description = rest.strip()

    return {
        "label": label,
        "category": category or "",
        "description": description,
    }


def normalize_concepts_json(obj) -> list:
    """Accept either concepts JSON ([{label,category,description}, ...])
    or prompts JSON ([{id?, text}, ...]) and return a concepts list.
    """
    if _is_concepts_list(obj):
        return obj
    if _is_prompts_list(obj):
        concepts = []
        for item in obj:
            concepts.append(_parse_prompt_text_to_concept(item.get("text", "")))
        return concepts
    # Unsupported shape: try best-effort if it's a list of strings
    if isinstance(obj, list) and all(isinstance(x, str) for x in obj):
        return [_parse_prompt_text_to_concept(x) for x in obj]
    return []

# ===== STEP 1: LOAD GRAPH JSON =====

st.header("1️⃣ Load Graph JSON")

st.write("""
Load the JSON file of an attribution graph generated by Neuronpedia from a locally saved file (e.g.: `output/graph_data/my_graph.json`)
""")

graph_json = None
graph_source = None

# List available JSON files
output_dir = parent_dir / "output" / "graph_data"
json_files = []
if output_dir.exists():
    json_files = sorted(output_dir.glob("**/*.json"))

if json_files:
    # Convert to relative paths for display
    json_options = [str(f.relative_to(parent_dir)) for f in json_files]
    
    selected_json_path = st.selectbox(
        "Graph JSON file",
        json_options,
        index=0,
        help="Select the graph to analyze"
    )
    
    if st.button("Load from File", type="primary"):
        json_path_full = parent_dir / selected_json_path
        try:
            with open(json_path_full, 'r', encoding='utf-8') as f:
                graph_json = json.load(f)
            graph_source = selected_json_path
            st.session_state['graph_json'] = graph_json
            st.session_state['graph_source'] = graph_source
            st.success(f"✅ Graph loaded from: {selected_json_path}")
            st.rerun()
        except Exception as e:
            st.error(f"❌ Loading error: {e}")
else:
    st.warning("⚠️ No JSON files found in output/graph_data/")

# Manual upload
uploaded_file = st.file_uploader(
    "Or upload a JSON file",
    type=['json'],
    help="Upload a Neuronpedia graph JSON file"
)

if uploaded_file is not None:
    try:
        graph_json = json.load(uploaded_file)
        graph_source = uploaded_file.name
        st.session_state['graph_json'] = graph_json
        st.session_state['graph_source'] = graph_source
        st.success(f"✅ Graph loaded from upload: {uploaded_file.name}")
        st.rerun()
    except Exception as e:
        st.error(f"❌ Loading error: {e}")

# Retrieve graph from session state
if 'graph_json' in st.session_state:
    graph_json = st.session_state['graph_json']
    graph_source = st.session_state.get('graph_source', 'unknown')

# Show graph info if loaded
if graph_json:
    with st.expander("Graph Info", expanded=True):
        metadata = graph_json.get("metadata", {})
        nodes = graph_json.get("nodes", [])
        
        st.write(f"**Source:** {graph_source}")
        st.write(f"**Model ID:** {metadata.get('scan', 'N/A')}")
        
        # Show the source format that will be used
        model_id = metadata.get('scan', '')
        info = metadata.get('info', {})
        transcoder_set_raw = info.get('transcoder_set', '')
        source_urls = info.get('source_urls', [])
        
        # Determine set name (converts "gemma" → "gemmascope")
        if transcoder_set_raw and transcoder_set_raw.lower() == 'gemma':
            set_name = "gemmascope"
        elif transcoder_set_raw:
            set_name = transcoder_set_raw
        elif 'gemma' in model_id.lower():
            set_name = "gemmascope"
        else:
            set_name = "gemmascope"
        
        # Determine type (res vs transcoder) from URLs
        source_type = "res-16k"
        for url in source_urls:
            if "transcoder" in url.lower():
                source_type = "transcoder-16k"
                break
            elif "res" in url.lower():
                source_type = "res-16k"
                break
        
        source_preview = f"{set_name}-{source_type}"
        
        st.write(f"**Source Format:** `{source_preview}` (e.g.: `6-{source_preview}`)")
        st.write(f"**Prompt:** `{metadata.get('prompt', 'N/A')[:100]}...`")
        st.write(f"**Total Nodes:** {len(nodes)}")
        
        # Count features
        features = [n for n in nodes if n.get("feature_type") == "cross layer transcoder"]
        st.write(f"**Features (cross layer transcoder):** {len(features)}")
        
        # Influence statistics
        if features:
            influences = [abs(f.get("influence", 0)) for f in features]
            st.write(f"**Total Influence (abs):** {sum(influences):.4f}")
            st.write(f"**Max Influence:** {max(influences):.6f}")
            st.write(f"**Min Influence:** {min(influences):.6f}")

# ===== STEP 2: LOAD FEATURE SUBSET =====

if graph_json:
    st.header("2️⃣ Load Feature Subset")
    
    st.write("""
    Load a 'selected_features_with_nodes.json' file with the list of features to analyze, or use all features from the graph.
    """)
    
    # Tab for selection mode
    tab_load, tab_all, tab_export = st.tabs(["Load Subset", "Use All", "Export Subset"])
    
    with tab_load:
        st.subheader("Load Feature Subset from JSON")
        
        uploaded_features = st.file_uploader(
            "JSON file with features",
            type=['json'],
            help="Accepts: [{'layer': int, 'index': int}, ...] OR {'features': [...], 'node_ids': [...]}",
            key="features_uploader"
        )
        
        if uploaded_features is not None:
            try:
                raw_json = json.load(uploaded_features)
                
                # Support both formats:
                # 1. [{"layer": int, "index": int}, ...] (legacy)
                # 2. {"features": [...], "node_ids": [...], "metadata": {...}} (complete)
                if isinstance(raw_json, dict) and "features" in raw_json:
                    # Complete format with features + nodes - extract only features
                    features_json = raw_json["features"]
                    st.info("📦 Complete format detected (features + nodes). Using features only.")
                elif isinstance(raw_json, list):
                    # Legacy format (features only)
                    features_json = raw_json
                else:
                    st.error("❌ Unrecognized JSON format")
                    st.stop()
                
                # Convert features format to features_in_graph format
                features_in_graph = []
                nodes = graph_json.get("nodes", [])
                
                # Create lookup for features from graph
                graph_features_lookup = {}
                skipped_count = 0
                
                for node in nodes:
                    # Filter only SAE nodes (cross layer transcoder)
                    if node.get("feature_type") != "cross layer transcoder":
                        continue
                    
                    layer = node.get("layer")
                    node_id = node.get("node_id", "")
                    feature_idx = None
                    
                    # Extract feature_index from node_id (format: "layer_featureIndex_sequence")
                    # Example: "24_79427_7" → feature_idx = 79427
                    if node_id and '_' in node_id:
                        parts = node_id.split('_')
                        if len(parts) >= 2:
                            try:
                                feature_idx = int(parts[1])
                            except (ValueError, IndexError):
                                pass
                    
                    # SKIP malformed SAE nodes (no fake fallback!)
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
                    st.warning(f"⚠️ {skipped_count} feature nodes with malformed node_id were skipped")
                
                # Match with loaded features
                for feat_json in features_json:
                    layer = feat_json.get("layer")
                    index = feat_json.get("index")
                    
                    if layer is not None and index is not None:
                        key = (int(layer), int(index))
                        if key in graph_features_lookup:
                            features_in_graph.append(graph_features_lookup[key])
                        else:
                            st.warning(f"Feature not found in graph: layer={layer}, index={index}")
                
                st.session_state['filtered_features'] = features_in_graph
                st.success(f"✅ Loaded {len(features_in_graph)} features from subset")
                
                # Show statistics
                col1, col2 = st.columns(2)
                with col1:
                    st.metric("Features in JSON", len(features_json))
                with col2:
                    st.metric("Features found in graph", len(features_in_graph))
                
            except Exception as e:
                st.error(f"❌ Loading error: {e}")
    
    with tab_all:
        st.subheader("Use All Features from Graph")
        
        # Extract features from graph
        nodes = graph_json.get("nodes", [])
        all_features = []
        skipped_count = 0
        
        for node in nodes:
            if node.get("feature_type") != "cross layer transcoder":
                continue
            
            layer = node.get("layer")
            
            # Extract feature_index from node_id (format: "layer_featureIndex_sequence")
            # Example: "24_79427_7" → feature_index = 79427
            node_id = node.get("node_id", "")
            feature_idx = None
            
            if node_id and '_' in node_id:
                parts = node_id.split('_')
                if len(parts) >= 2:
                    try:
                        feature_idx = int(parts[1])
                    except (ValueError, IndexError):
                        pass
            
            # SKIP nodes without valid feature_idx (no fake fallback!)
            if layer is None or feature_idx is None:
                skipped_count += 1
                continue
            
            all_features.append({
                "layer": int(layer),
                "feature": int(feature_idx),  # Now contains the correct index!
                "original_activation": float(node.get("activation", 0)),
                "original_ctx_idx": int(node.get("ctx_idx", 0)),
                "influence": float(node.get("influence", 0)),
            })
        
        st.write(f"**Total features in graph:** {len(all_features)}")
        
        if st.button("Use All Features", type="primary"):
            st.session_state['filtered_features'] = all_features
            st.success(f"✅ Loaded {len(all_features)} features from graph")
            st.rerun()
    
    with tab_export:
        st.subheader("Export Current Feature Subset")
        
        if 'filtered_features' in st.session_state and st.session_state['filtered_features']:
            features_to_export = st.session_state['filtered_features']
            
            st.write(f"**Features to export:** {len(features_to_export)}")
            
            # Preview first features
            with st.expander("Preview features"):
                preview_list = [
                    {"layer": f["layer"], "index": f["feature"]}
                    for f in features_to_export[:10]
                ]
                st.json(preview_list)
                if len(features_to_export) > 10:
                    st.caption(f"... and {len(features_to_export) - 10} more features")
            
            export_filename = st.text_input(
                "File name",
                value="feature_subset.json",
                help="Name of JSON file to save"
            )
            
            if st.button("Export Feature Subset", type="primary"):
                output_path = parent_dir / "output" / export_filename
                
                try:
                    export_features_list(features_to_export, str(output_path), verbose=False)
                    st.success(f"✅ Feature subset exported: {output_path.relative_to(parent_dir)}")
                    
                    # Download button
                    with open(output_path, 'r', encoding='utf-8') as f:
                        features_json_str = f.read()
                    
                    st.download_button(
                        label="Download Feature Subset",
                        data=features_json_str,
                        file_name=export_filename,
                        mime="application/json"
                    )
                    
                except Exception as e:
                    st.error(f"❌ Export error: {e}")
        else:
            st.info("⚠️ No features selected. Load a subset or use all features first.")

# ===== STEP 3: DEFINE CONCEPTS =====

if graph_json:
    st.header("3️⃣ Define Concepts")
    
    # Tabs for automatic or manual generation
    tab_gen, tab_manual, tab_load = st.tabs(["Generate with OpenAI", "Manual Entry", "Load from File"])
    
    with tab_gen:
        st.subheader("Automatic Concept Generation")
        
        # Load prompt from graph
        prompt_text = graph_json.get("metadata", {}).get("prompt", "")
        
        prompt_for_concepts = st.text_area(
            "Original prompt",
            value=prompt_text,
            height=100,
            help="The prompt used to generate the graph"
        )
        
        output_for_concepts = st.text_area(
            "Model output (optional)",
            value="",
            height=100,
            help="The model output for the prompt (if available)"
        )
        
        num_concepts = st.slider(
            "Number of concepts to generate",
            min_value=1,
            max_value=20,
            value=5,
            help="How many concepts do you want to extract from the text"
        )
        
        if st.button("Generate Concepts with OpenAI", type="primary"):
            if not openai_key:
                st.error("⚠️ Enter a valid OpenAI API key")
            else:
                with st.spinner("Generating concepts..."):
                    try:
                        # Prepare text to analyze
                        text_to_analyze = f"PROMPT: {prompt_for_concepts}\n"
                        if output_for_concepts:
                            text_to_analyze += f"\nOUTPUT: {output_for_concepts}"
                        
                        # Call OpenAI
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
                        
                        # Parse response
                        content = response.choices[0].message.content.strip()
                        
                        # Remove markdown code blocks if present
                        if content.startswith("```"):
                            lines = content.split("\n")
                            content = "\n".join(lines[1:-1])
                        if content.startswith("json"):
                            content = content[4:].strip()
                        
                        concepts_generated = json.loads(content)
                        
                        # Save to session state
                        st.session_state['concepts'] = concepts_generated
                        
                        st.success(f"✅ Generated {len(concepts_generated)} concepts!")
                        st.rerun()
                        
                    except Exception as e:
                        st.error(f"❌ Generation error: {e}")
                        st.exception(e)
    
    with tab_manual:
        st.subheader("Manual Entry")
        
        st.write("Enter concepts in JSON format:")
        
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
            help="JSON array with format: [{label, category, description}, ...]"
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
        st.subheader("Load from JSON File")
        
        uploaded_file = st.file_uploader(
            "Upload JSON file with concepts",
            type=['json'],
            help="JSON file with array of concepts",
            key="concepts_uploader"
        )
        
        if uploaded_file is not None:
            try:
                raw = json.load(uploaded_file)
                concepts_uploaded = normalize_concepts_json(raw)
                if not concepts_uploaded:
                    st.error("❌ Unrecognized JSON format. Expected: concepts [{label,category,description}] or prompts [{id?, text}].")
                else:
                    st.session_state['concepts'] = concepts_uploaded
                    if _is_prompts_list(raw):
                        st.info("🔄 Recognized 'prompts' format. Automatically converted to 'concepts'.")
                    st.success(f"✅ Loaded {len(concepts_uploaded)} concepts from file!")
            except Exception as e:
                st.error(f"❌ Loading error: {e}")

# Edit concepts:

if 'concepts' in st.session_state and st.session_state['concepts']:
    
    
    concepts = st.session_state['concepts']
    
    # Show editable table
    df_concepts = pd.DataFrame(concepts)
    
    st.write(f"**{len(concepts)} concepts available:**")
    
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
    
    # Update session state
    st.session_state['concepts'] = edited_df.to_dict(orient='records')
    
    # Download button - prompts format
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
        label="📥 Download Prompts JSON",
        data=prompts_json,
        file_name=f"prompts_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
        mime="application/json",
        type="primary",
        help="Format compatible with batch_get_activations.py"
    )

# ===== STEP 4: GET FEATURE ACTIVATIONS =====

if 'concepts' in st.session_state and st.session_state['concepts']:
    st.header("4️⃣ Get Feature Activations")
    
    # Create tabs for different analysis methods
    tab1, tab2 = st.tabs(["Load from file", "Analysis via API"])
    
    with tab2:
        st.warning("⚠️ **Temporarily disabled** due to Neuronpedia API rate limits. Please use the 'Load from file' tab with pre-calculated activations from Colab.")
        st.write("Analysis parameters:")
        
        col1, col2, col3 = st.columns(3)
        
        with col1:
            activation_threshold = st.slider(
                "Activation percentile threshold",
                min_value=0.5,
                max_value=0.99,
                value=0.9,
                step=0.01,
                help="Percentile to calculate activation density threshold"
            )
        
        with col2:
            use_baseline = st.checkbox(
                "Calculate baseline",
                value=True,
                help="Calculate metrics vs original prompt (requires more API calls)"
            )
        
        with col3:
            output_filename = st.text_input(
                "Output CSV file name",
                value="acts_compared.csv",
                help="Name of CSV file to save in output/"
            )
        
        # === CHECKPOINT & RECOVERY ===
        st.subheader("Checkpoint & Recovery")
        
        col1_ckpt, col2_ckpt, col3_ckpt = st.columns(3)
        
        with col1_ckpt:
            checkpoint_every = st.number_input(
                "Save checkpoint every N features",
                min_value=5,
                max_value=100,
                value=10,
                help="Save partial data every N features processed"
            )
        
        with col2_ckpt:
            resume_from_checkpoint = st.checkbox(
                "Resume from checkpoint",
                value=True,
                help="If present, resume analysis from where it was interrupted"
            )
        
        with col3_ckpt:
            # Search for existing checkpoints
            checkpoint_dir = parent_dir / "output" / "checkpoints"
            checkpoint_files = []
            if checkpoint_dir.exists():
                checkpoint_files = sorted(checkpoint_dir.glob("probe_prompts_*.json"), reverse=True)
            
            if checkpoint_files and resume_from_checkpoint:
                selected_checkpoint = st.selectbox(
                    "Checkpoint to resume",
                    options=["New"] + [f.name for f in checkpoint_files[:5]],
                    help="Select an existing checkpoint or start new"
                )
            else:
                selected_checkpoint = "New"
        
        # Show info on selected checkpoint
        if selected_checkpoint != "New" and resume_from_checkpoint:
            checkpoint_path = checkpoint_dir / selected_checkpoint
            if checkpoint_path.exists():
                try:
                    with open(checkpoint_path, 'r', encoding='utf-8') as f:
                        ckpt_data = json.load(f)
                    num_records = ckpt_data.get('num_records', 0)
                    timestamp = ckpt_data.get('timestamp', 'unknown')
                    metadata = ckpt_data.get('metadata', {})
                    
                    st.info(f"""
                    **Checkpoint found:**
                    - Records: {num_records}
                    - Date: {timestamp}
                    - Status: {metadata.get('status', 'in progress')}
                    - Concepts: {metadata.get('current_concept', '?')}/{metadata.get('total_concepts', '?')}
                    """)
                except Exception as e:
                    st.warning(f"Checkpoint read error: {e}")
        
        # Estimate API calls
        if 'filtered_features' in st.session_state:
            num_features = len(st.session_state['filtered_features'])
            num_concepts = len(st.session_state['concepts'])
            
            total_calls = num_features * num_concepts
            if use_baseline:
                total_calls += num_features
            
            st.info(f"""
            **API calls estimate:**
            - Selected features: {num_features}
            - Concepts: {num_concepts}
            - Baseline: {'Yes' if use_baseline else 'No'} ({num_features if use_baseline else 0} calls)
            - **Total calls**: ~{total_calls}
            - **Estimated time**: ~{total_calls / 5 / 60:.1f} minutes (rate limit: 5 req/sec)
            """)
        
        if st.button("Run Analysis", type="primary", disabled=True):
            # Check prerequisites
            if not neuronpedia_key:
                st.error("❌ Neuronpedia API Key not configured")
                st.stop()
            
            if 'filtered_features' not in st.session_state:
                st.error("❌ Features not loaded. Complete Step 2 (Load Feature Subset).")
                st.stop()
            
            # Progress tracking
            progress_bar = st.progress(0)
            status_text = st.empty()
            log_area = st.empty()
            
            # Log buffer
            log_messages = []
            
            def progress_callback(current, total, phase):
                """Callback to update progress bar and log"""
                progress = current / total
                progress_bar.progress(progress)
                
                msg = f"{phase.capitalize()}: {current}/{total} ({progress*100:.1f}%)"
                status_text.text(msg)
                
                # Add to log (keep last 10 messages)
                log_messages.append(msg)
                if len(log_messages) > 10:
                    log_messages.pop(0)
                
                log_area.text("\n".join(log_messages))
            
            # Container for detailed log
            with st.expander("Detailed Log", expanded=True):
                detailed_log = st.empty()
            
            try:
                output_dir = parent_dir / "output"
                output_csv_path = output_dir / output_filename
                
                # Setup checkpoint path
                checkpoint_path_to_use = None
                if resume_from_checkpoint and selected_checkpoint != "New":
                    checkpoint_path_to_use = str(checkpoint_dir / selected_checkpoint)
                    status_text.info(f"📂 Resuming from checkpoint: {selected_checkpoint}")
                else:
                    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
                    checkpoint_path_to_use = str(parent_dir / "output" / "checkpoints" / f"probe_prompts_{timestamp}.json")
                    status_text.info("🆕 Starting new analysis...")
                
                log_messages.append(f"💾 Checkpoint: {Path(checkpoint_path_to_use).name}")
                log_messages.append(f"🔄 Resume: {resume_from_checkpoint}")
                log_messages.append("🚀 Initialization...")
                
                # Temporarily override filtering: use already loaded features
                # (analyze_concepts_from_graph_json extracts from graph, we pass the subset)
                
                # Prepare modified graph_json with only selected features
                filtered_graph = graph_json.copy()
                if 'filtered_features' in st.session_state:
                    # Filter nodes in graph to include only selected features
                    selected_keys = {(f['layer'], f['feature']) for f in st.session_state['filtered_features']}
                    filtered_nodes = []
                    skipped_nodes_filter = 0
                    
                    for node in graph_json.get('nodes', []):
                        if node.get('feature_type') == 'cross layer transcoder':
                            layer = node.get('layer')
                            
                            # Extract feature_index from node_id (format: "layer_featureIndex_sequence")
                            node_id = node.get("node_id", "")
                            feature = None
                            
                            if node_id and '_' in node_id:
                                parts = node_id.split('_')
                                if len(parts) >= 2:
                                    try:
                                        feature = int(parts[1])
                                    except (ValueError, IndexError):
                                        pass
                            
                            # SKIP nodes without valid feature (no fake fallback!)
                            if feature is None:
                                skipped_nodes_filter += 1
                                continue
                            
                            if (int(layer), int(feature)) in selected_keys:
                                filtered_nodes.append(node)
                        else:
                            # Keep non-feature nodes (logits, embeddings)
                            filtered_nodes.append(node)
                    
                    filtered_graph['nodes'] = filtered_nodes
                    
                    if skipped_nodes_filter > 0:
                        log_messages.append(f"⚠️ {skipped_nodes_filter} feature nodes with malformed node_id skipped")
                
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
                st.warning("⚠️ Analysis interrupted by user")
                st.info(f"""
                **Checkpoint saved automatically**
                
                To resume analysis:
                1. Select the checkpoint in "Checkpoint & Recovery" section
                2. Enable "Resume from checkpoint"
                3. Click "Run Analysis"
                
                Checkpoint: `{Path(checkpoint_path_to_use).name}`
                """)
                
            except Exception as e:
                st.error(f"❌ Error during analysis: {e}")
                st.exception(e)
                
                if 'checkpoint_path_to_use' in locals():
                    st.info(f"""
                    **Checkpoint saved before error**
                    
                    You can resume analysis by selecting the checkpoint:
                    `{Path(checkpoint_path_to_use).name}`
                    """)
        
        # ===== DISPLAY RESULTS (API tab) =====
        
        if 'analysis_results' in st.session_state:
            st.markdown("---")
            st.subheader("Results")
            
            df_results = st.session_state['analysis_results']
            
            if not df_results.empty:
                st.write(f"**{len(df_results)} result rows**")
                
                # Reset index for display
                df_display = df_results.reset_index()
                
                # Filters
                st.subheader("Filters")
                
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
                
                # Apply filters
                df_filtered = df_display[
                    (df_display['label'].isin(labels_filter)) &
                    (df_display['category'].isin(categories_filter)) &
                    (df_display['layer'].isin(layers_filter))
                ]
                
                # Show table
                st.dataframe(
                    df_filtered,
                    use_container_width=True,
                    height=400
                )
                
                # Download filtered results
                csv_filtered = df_filtered.to_csv(index=False, encoding='utf-8').encode('utf-8')
                st.download_button(
                    label="Download Filtered Results",
                    data=csv_filtered,
                    file_name=f"acts_compared_filtered_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
                    mime="text/csv"
                )
                
                # Quick statistics
                st.subheader("Quick Statistics")
                
                col1, col2, col3, col4 = st.columns(4)
                
                with col1:
                    st.metric("Total Features", len(df_filtered))
                
                with col2:
                    avg_z = df_filtered['z_score'].mean()
                    st.metric("Mean Z-score", f"{avg_z:.2f}")
                
                with col3:
                    picco_su_label = (df_filtered['picco_su_label'].sum() / len(df_filtered) * 100) if len(df_filtered) > 0 else 0
                    st.metric("Peak on Label (%)", f"{picco_su_label:.1f}%")
                
                with col4:
                    avg_cos_sim = df_filtered['cosine_similarity'].mean()
                    st.metric("Mean Cosine Sim.", f"{avg_cos_sim:.3f}")
                
            else:
                st.warning("⚠️ No results available")
    
    with tab1:
        st.info("""
        **📊 Use Colab for batch processing** — Process multiple prompts and features efficiently using GPU.
        
        **Colab Notebook:** [Open batch_get_activations.py](https://colab.research.google.com/drive/1YlZ9El6Cx2UnFqaQwBhLHsoernRTMxK4?usp=sharing)
        
        **Estimated time:** ~15 minutes for 5 prompts × 50 features with L4 GPU
        
        **How to use:**
        1. Open the Colab notebook (Runtime > Change runtime type > L4 GPU)
        2. Prepare your `prompts.json` and `features.json` files
        3. Run the cell to get `activations_dump.json`
        4. Upload the JSON file below for analysis
        """)
        
        st.markdown("""
        ### Load Activations from JSON File
        
        Load a JSON file with pre-calculated activations (e.g. generated with `batch_get_activations.py` on Colab).
        
        **Expected format:**
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
            "Select JSON file",
            type=['json'],
            help="JSON file with pre-calculated activations from batch_get_activations.py",
            key="activations_uploader"
        )
        
        # Persist upload in session_state to avoid losing it on reruns
        if uploaded_file is not None:
            try:
                raw_bytes = uploaded_file.getvalue()
                text = raw_bytes.decode('utf-8')
                activations_data = json.loads(text)
                st.session_state['activations_uploaded_data'] = activations_data
                st.session_state['activations_uploaded_name'] = uploaded_file.name
            except json.JSONDecodeError as e:
                st.error(f"❌ JSON parsing error: {e}")
            except Exception as e:
                st.error(f"❌ File loading error: {e}")
                st.exception(e)
        
        if 'activations_uploaded_data' in st.session_state:
            try:
                activations_data = st.session_state['activations_uploaded_data']
                
                # Show file info
                st.success("✅ File loaded successfully!")
                
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Model", activations_data.get('model', 'N/A'))
                with col2:
                    st.metric("SAE Set", activations_data.get('source_set', 'N/A'))
                with col3:
                    n_results = len(activations_data.get('results', []))
                    st.metric("Processed Prompts", n_results)
                
                # Show results preview
                if 'results' in activations_data and len(activations_data['results']) > 0:
                    st.markdown("---")
                    st.subheader("Data Preview")
                    
                    # Create summary DataFrame
                    summary_data = []
                    for result in activations_data['results']:
                        summary_data.append({
                            'Probe ID': result.get('probe_id', 'N/A'),
                            'Prompt': result.get('prompt', '')[:60] + '...' if len(result.get('prompt', '')) > 60 else result.get('prompt', ''),
                            'N. Tokens': len(result.get('tokens', [])),
                            'N. Activations': len(result.get('activations', []))
                        })
                    
                    import pandas as pd
                    df_summary = pd.DataFrame(summary_data)
                    st.dataframe(df_summary, use_container_width=True)
                    
                    # Show details of first prompt (example)
                    with st.expander("First prompt details", expanded=False):
                        first_result = activations_data['results'][0]
                        st.write(f"**Probe ID:** {first_result.get('probe_id', 'N/A')}")
                        st.write(f"**Prompt:** {first_result.get('prompt', 'N/A')}")
                        st.write(f"**Token:** `{first_result.get('tokens', [])[:10]}`{'...' if len(first_result.get('tokens', [])) > 10 else ''}")
                        st.write(f"**Activations found:** {len(first_result.get('activations', []))}")
                        
                        if first_result.get('activations'):
                            st.write("**First 3 activations:**")
                            for i, act in enumerate(first_result['activations'][:3], 1):
                                st.json({
                                    f"Activation {i}": {
                                        'source': act.get('source'),
                                        'index': act.get('index'),
                                        'max_value': act.get('max_value'),
                                        'max_value_index': act.get('max_value_index'),
                                        'n_values': len(act.get('values', []))
                                    }
                                })
                    
                    # ===== CHART: IMPORTANCE vs ACTIVATION =====
                    st.markdown("---")
                    st.subheader("📊 Main Chart: Importance vs Activation")
                    
                    st.caption("""
                    **Bar chart**: Features sorted by causal importance (node_influence).
                    Bar height = peak activation (max_value, **excluding BOS**). Color = prompt.
                    Red line = node_influence score.
                    """)
                    
                    # Config
                    col1, col2 = st.columns([2, 1])
                    with col1:
                        top_n = st.slider("Show top N features (by node_influence)", 10, 100, 30, 5)
                    with col2:
                        exclude_bos = st.checkbox("Exclude features with peak on <BOS>", value=False, 
                                                  help="Remove features whose peak is on BOS token")
                    
                    # Load node_influence from CSV
                    csv_path = parent_dir / "output" / "graph_feature_static_metrics.csv"
                    
                    if not csv_path.exists():
                        st.warning(f"⚠️ CSV with node_influence not found: `{csv_path.relative_to(parent_dir)}`")
                        st.info("First generate CSV using **00_Graph_Generation.py** > 'Generate CSV Metrics'")
                    else:
                        try:
                            feats_csv = pd.read_csv(csv_path, encoding='utf-8')
                            feats_csv['feature_key'] = feats_csv['layer'].astype(int).astype(str) + '_' + feats_csv['id'].astype(int).astype(str)
                            feats_csv = feats_csv[['feature_key', 'node_influence']]
                            
                            # Extract activations per prompt/feature from JSON
                            import re
                            rows = []
                            for res in activations_data.get('results', []):
                                prompt = res.get('prompt', '')
                                tokens = res.get('tokens', [])
                                T = len(tokens)
                                
                                for a in res.get('activations', []):
                                    src = str(a.get('source', ''))
                                    # Extract layer from numeric prefix (e.g. "10-clt-hp" -> 10)
                                    try:
                                        layer = int(src.split('-', 1)[0])
                                    except Exception:
                                        m = re.search(r'(\d+)', src)
                                        layer = int(m.group(1)) if m else None
                                    
                                    idx = int(a.get('index'))
                                    if layer is None:
                                        continue
                                    
                                    feature_key = f"{layer}_{idx}"
                                    
                                    # Extract values and calculate max EXCLUDING first element (BOS)
                                    values = a.get('values', [])
                                    if len(values) > 1:
                                        # Exclude index 0 (BOS), find max among others
                                        values_no_bos = values[1:]
                                        max_value = max(values_no_bos) if values_no_bos else None
                                        # Index relative to values_no_bos, add 1 for offset
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
                            
                            # Pre-filter info
                            n_before = len(act_df)
                            n_bos = len(act_df[act_df['peak_token'] == '<BOS>'])
                            
                            # BOS filter
                            if exclude_bos:
                                act_df = act_df[act_df['peak_token'] != '<BOS>']
                                if len(act_df) == 0 and n_bos > 0:
                                    st.warning(f"⚠️ All {n_before} activations were filtered because they have peak on <BOS>!")
                                    st.info("Disable BOS filter to visualize these features.")
                            
                            if act_df.empty:
                                st.info("No activations available for chart.")
                            else:
                                # Dataset info
                                n_unique_features = act_df['feature_key'].nunique()
                                n_prompts = act_df['prompt'].nunique()
                                if n_unique_features <= 5:
                                    st.info(f"Dataset contains only {n_unique_features} unique feature(s) on {n_prompts} prompt(s)")
                                
                                # Aggregate by feature/prompt: max activation
                                agg = act_df.groupby(['feature_key', 'prompt'], as_index=False)['activation'].max()
                                
                                # DATA VERIFICATION TABLE
                                with st.expander("Activation Analysis CSV", expanded=False):
                                    st.caption("""
                                    **Raw data used for chart**: each row = feature + prompt combination.
                                    
                                    **Activation metrics** (all exclude BOS):
                                    - `activation_max` → Maximum activation peak
                                    - `activation_sum` → Total sum of activations
                                    - `activation_mean` → Mean of activations (length-normalized)
                                    - `sparsity_ratio` → (max - mean) / max. Measures how concentrated activation is:
                                      - **~0**: uniform activation/distributed across all tokens
                                      - **~1**: very sparse activation (only few strong peaks)
                                    
                                    **Other columns**:
                                    - `peak_token_idx` → Peak position (1+ due to BOS exclusion)
                                    - `node_influence` → Maximum value from CSV for that feature_key 
                                      (a feature can appear multiple times in CSV with different ctx_idx)
                                    - `csv_ctx_idx` → Token context where node_influence is maximum
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
                                            
                                            # Extract values and calculate max EXCLUDING first element (BOS)
                                            values = a.get('values', [])
                                            if len(values) > 1:
                                                # Exclude index 0 (BOS), find max among others
                                                values_no_bos = values[1:]
                                                max_value = max(values_no_bos) if values_no_bos else None
                                                # Index relative to values_no_bos, add 1 for offset
                                                max_idx = values_no_bos.index(max_value) + 1 if max_value is not None else None
                                                # Calculate sum and mean excluding BOS
                                                sum_values = sum(values_no_bos) if values_no_bos else 0
                                                mean_value = sum_values / len(values_no_bos) if values_no_bos else 0
                                                # Calculate sparsity ratio: how concentrated activation is
                                                # 0 = uniform (all similar), 1 = very sparse (only peaks)
                                                sparsity = (max_value - mean_value) / max_value if max_value and max_value > 0 else 0
                                            else:
                                                max_value = None
                                                max_idx = None
                                                sum_values = 0
                                                mean_value = 0
                                                sparsity = 0
                                            peak_token = tokens[max_idx] if isinstance(max_idx, int) and 0 <= max_idx < T else None
                                            
                                            # Apply BOS filter if active
                                            if exclude_bos and peak_token == '<BOS>':
                                                continue
                                            
                                            verification_rows.append({
                                                'feature_key': feature_key,
                                                'layer': layer,
                                                'index': idx,
                                                'source': src,
                                                'prompt': prompt,
                                                'activation_max': max_value,
                                                'activation_sum': sum_values,
                                                'activation_mean': mean_value,
                                                'sparsity_ratio': sparsity,
                                                'peak_token': peak_token,
                                                'peak_token_idx': max_idx
                                            })
                                    
                                    verify_df = pd.DataFrame(verification_rows)
                                    
                                    # Load complete CSV to get ctx_idx
                                    csv_full = pd.read_csv(csv_path, encoding='utf-8')
                                    csv_full['feature_key'] = csv_full['layer'].astype(int).astype(str) + '_' + csv_full['id'].astype(int).astype(str)
                                    
                                    # For each feature_key, take max(node_influence) and corresponding ctx_idx
                                    # Sort by node_influence and take last (max)
                                    csv_max = csv_full.sort_values('node_influence').groupby('feature_key', as_index=False).last()
                                    csv_max = csv_max[['feature_key', 'node_influence', 'ctx_idx']]
                                    csv_max = csv_max.rename(columns={'ctx_idx': 'csv_ctx_idx'})
                                    
                                    # Merge with CSV (left join to see NaNs too)
                                    verify_full = verify_df.merge(
                                        csv_max, 
                                        on='feature_key', 
                                        how='left'
                                    )
                                    
                                    # Reorder columns
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
                                                st.caption("🎯 Very sparse features")
                                            elif avg_sparsity > 0.4:
                                                st.caption("⚖️ Moderate sparsity")
                                            else:
                                                st.caption("📊 Distributed features")
                                    
                                    # Download CSV - moved to bottom of page
                                
                                # ===== CHECK DI CORRETTEZZA DATI =====
                                
                                # CHECK 1: Verifica che verify_full abbia node_influence
                                n_with_ni = verify_full['node_influence'].notna().sum()
                                n_total_verify = len(verify_full)
                                
                                if n_with_ni == 0:
                                    st.error("❌ ERROR: No feature in JSON has node_influence from CSV!")
                                    st.info("Possible causes:\n- CSV not generated from the same graph\n- Column 'id' in CSV does not match 'index' in JSON")
                                    st.stop()
                                
                                if n_with_ni < n_total_verify:
                                    st.warning(f"⚠️ {n_total_verify - n_with_ni}/{n_total_verify} rows without node_influence")
                                
                                # CHECK 2: Verifica che activation_max sia sempre calcolata
                                n_null_act = verify_full['activation_max'].isna().sum()
                                if n_null_act > 0:
                                    st.warning(f"⚠️ WARNING: {n_null_act} rows with activation_max = null")
                                
                                # CHECK 3: Verifica che peak_token_idx non sia mai 0 (dovrebbe essere sempre >= 1, escludendo BOS)
                                n_bos_peak = (verify_full['peak_token_idx'] == 0).sum()
                                if n_bos_peak > 0:
                                    st.error(f"❌ ERROR: {n_bos_peak} rows have peak_token_idx=0 (BOS)! Max calculation did not exclude BOS correctly.")
                                
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
                                
                                # EXCLUDE RECONSTRUCTION ERROR NODES (where layer == index, e.g., 18_18)
                                n_before_error_filter = len(plot_data)
                                plot_data = plot_data[plot_data['layer'] != plot_data['index']].copy()
                                n_error_excluded = n_before_error_filter - len(plot_data)
                                
                                if n_error_excluded > 0:
                                    st.info(f"🔧 Excluded {n_error_excluded} reconstruction error node(s) from chart")
                                
                                if plot_data.empty:
                                    st.warning("❌ No feature with node_influence available for the chart.")
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
                                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                        margin=dict(t=150)
                                    )
                                    
                                    st.plotly_chart(fig, use_container_width=True)
                                    
                                    
                                    # ===== GRAFICO 2: COLORATO PER PEAK TOKEN =====
                                    
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
                                        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
                                        margin=dict(t=150)
                                    )
                                    
                                    st.plotly_chart(fig2, use_container_width=True)
                                    
                                    # Info sui token
                                    n_unique_tokens = pivot_by_token.columns.notna().sum()
                                    st.info(f"""
                                    **📊 Token Analysis**:
                                    - unique peak tokens: {n_unique_tokens}
                                    - Features displayed: {len(pivot_by_token)}
                                    """)
                                    
                                    # Dettagli token più frequenti
                                    with st.expander("🔍 Most frequent peak tokens"):
                                        token_freq = plot_data_top['peak_token'].value_counts()
                                        token_freq_df = pd.DataFrame({
                                            'peak_token': token_freq.index,
                                            'count': token_freq.values,
                                            'percentage': (token_freq.values / len(plot_data_top) * 100).round(1)
                                        })
                                        st.dataframe(token_freq_df.head(20), use_container_width=True)
                                    
                                    # ===== BARRE DI COPERTURA =====
                                    st.markdown("---")
                                    
                                    # EXCLUDE ERROR NODES for coverage analysis (same as chart filter)
                                    verify_full_no_error = verify_full[verify_full['layer'] != verify_full['index']].copy()
                                    
                                    # Feature attive = features con activation_max > 0 in verify_full (excluding error nodes)
                                    features_with_signal = verify_full_no_error[verify_full_no_error['activation_max'] > 0]['feature_key'].unique()
                                    n_features_active = len(features_with_signal)
                                    
                                    # Feature totali = feature_key uniche nel JSON caricato (verify_full, excluding error nodes)
                                    # NON dal CSV (che contiene tutte le features del grafo)
                                    n_features_total = verify_full_no_error['feature_key'].nunique()
                                    
                                    # Calcola node_influence per feature attive vs totale
                                    # Usa max(node_influence) per feature_key, MA SOLO per le features nel JSON (no error nodes)
                                    csv_max_ni_json = verify_full_no_error.groupby('feature_key', as_index=False)['node_influence'].max()
                                    active_features_influence = csv_max_ni_json[csv_max_ni_json['feature_key'].isin(features_with_signal)]['node_influence'].sum()
                                    total_influence = csv_max_ni_json['node_influence'].sum()
                                    
                                    # Percentuali
                                    pct_features = (n_features_active / n_features_total * 100) if n_features_total > 0 else 0
                                    pct_influence = (active_features_influence / total_influence * 100) if total_influence > 0 else 0
                                    
                                    # Progress bars
                                    st.markdown("**📊 Coverage Analysis (Active features on probe prompts)**")
                                    
                                    # Barra 1: Feature count
                                    st.markdown(f"**Features Coverage:** {n_features_active} / {n_features_total} features ({pct_features:.1f}%)")
                                    st.progress(pct_features / 100)
                                    
                                    # Barra 2: Node influence
                                    st.markdown(f"**Importance Coverage:** {active_features_influence:.4f} / {total_influence:.4f} node_influence ({pct_influence:.1f}%)")
                                    st.progress(pct_influence / 100)
                                    
                                    st.caption("""
                                    💡 **Interpretation**: 
                                    - Features Coverage = % of features (in loaded JSON) that activate (>0) on at least one probe prompt
                                    - Importance Coverage = % of causal importance (of features in JSON) covered by active features
                                    
                                    📌 Reference values are features present in loaded JSON, not the entire graph.
                                    🔧 Reconstruction error nodes (where layer == index) are excluded from these metrics.
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
                                    

                                    
                                    # ===== ACTIVATION HEATMAPS (Feature × Token for all probes) =====
                                    st.markdown("---")
                                    
                                    with st.expander("🔥 Activation Heatmaps: Feature × Token", expanded=False):
                                        st.caption("""
                                        **Feature × Token heatmaps** (one per probe) showing activation patterns.
                                        Each heatmap shows which tokens activate which features most strongly.
                                        Green intensity indicates activation strength (darker = stronger).
                                        **BOS token is excluded** from all heatmaps.
                                        """)
                                        
                                        try:
                                            import plotly.graph_objects as go
                                            
                                            # For each probe, create a heatmap
                                            for probe_idx, probe_result in enumerate(activations_data.get('results', [])):
                                                probe_id = probe_result.get('probe_id', f'probe_{probe_idx}')
                                                prompt = probe_result.get('prompt', '')
                                                tokens = probe_result.get('tokens', [])
                                                
                                                # Get activations for features present in plot_data_top
                                                activations = probe_result.get('activations', [])
                                                
                                                if not activations or not tokens:
                                                    continue
                                                
                                                # Filter to only features shown in the main chart (plot_data_top)
                                                selected_feature_keys = set(plot_data_top['feature_key'].unique())
                                                
                                                # EXCLUDE BOS: skip first token and first value in activation arrays
                                                tokens_no_bos = tokens[1:] if len(tokens) > 1 and tokens[0].upper() in ['<BOS>', '<S>'] else tokens
                                                bos_offset = 1 if len(tokens) > len(tokens_no_bos) else 0
                                                
                                                # Build heatmap matrix: rows = features, columns = tokens (no BOS)
                                                heatmap_data = []
                                                feature_labels = []
                                                
                                                for activation in activations:
                                                    source = str(activation.get('source', ''))
                                                    try:
                                                        layer = int(source.split('-', 1)[0])
                                                    except Exception:
                                                        import re
                                                        m = re.search(r'(\d+)', source)
                                                        layer = int(m.group(1)) if m else None
                                                    
                                                    if layer is None:
                                                        continue
                                                
                                                idx = int(activation.get('index'))
                                                feature_key = f"{layer}_{idx}"
                                                
                                                # Only include features from the main chart
                                                if feature_key not in selected_feature_keys:
                                                    continue
                                                
                                                values = activation.get('values', [])
                                                # Exclude BOS value (first element)
                                                values_no_bos = values[bos_offset:] if len(values) > bos_offset else values
                                                
                                                if len(values_no_bos) == len(tokens_no_bos):
                                                    heatmap_data.append(values_no_bos)
                                                    feature_labels.append(feature_key)
                                            
                                            # Check if we have data to plot (after processing all activations)
                                            if not heatmap_data:
                                                st.info(f"No activation data for probe {probe_idx + 1}")
                                            else:
                                                # Create heatmap
                                                heatmap_array = np.array(heatmap_data)
                                                
                                                # Create custom hover text with token and value (no BOS)
                                                hover_text = []
                                                for feat_idx, feature_key in enumerate(feature_labels):
                                                    row_hover = []
                                                    for tok_idx, token in enumerate(tokens_no_bos):
                                                        value = heatmap_array[feat_idx, tok_idx]
                                                        row_hover.append(
                                                            f"Feature: {feature_key}<br>"
                                                            f"Token: {token}<br>"
                                                            f"Activation: {value:.3f}"
                                                        )
                                                    hover_text.append(row_hover)
                                                
                                                fig_heatmap = go.Figure(data=go.Heatmap(
                                                    z=heatmap_array,
                                                    x=tokens_no_bos,
                                                    y=feature_labels,
                                                    colorscale='Greens',
                                                    hovertext=hover_text,
                                                    hoverinfo='text',
                                                    colorbar=dict(title="Activation")
                                                ))
                                                
                                                fig_heatmap.update_layout(
                                                    title=f"Probe {probe_idx + 1}: {prompt[:60]}{'...' if len(prompt) > 60 else ''} [BOS EXCLUDED]",
                                                    xaxis_title="Tokens (BOS excluded)",
                                                    yaxis_title="Features (layer_index)",
                                                    height=max(400, len(feature_labels) * 20),
                                                    xaxis=dict(tickangle=-45),
                                                    margin=dict(l=100, r=50, t=100, b=100)
                                                )
                                                
                                                st.plotly_chart(fig_heatmap, use_container_width=True)
                                                
                                                # Show peak analysis for this probe (BOS already excluded)
                                                with st.expander(f"📊 Peak Analysis for Probe {probe_idx + 1}"):
                                                    # Find peaks (max activation per feature, BOS already excluded)
                                                    peak_analysis = []
                                                    for feat_idx, feature_key in enumerate(feature_labels):
                                                        values = heatmap_array[feat_idx, :]
                                                        max_val = values.max()
                                                        max_idx = values.argmax()
                                                        peak_token = tokens_no_bos[max_idx]
                                                        
                                                        peak_analysis.append({
                                                            'feature_key': feature_key,
                                                            'peak_token': peak_token,
                                                            'peak_value': max_val,
                                                            'peak_position': max_idx + bos_offset  # Adjust position to account for BOS
                                                        })
                                                    
                                                    peak_df = pd.DataFrame(peak_analysis)
                                                    peak_df = peak_df.sort_values('peak_value', ascending=False)
                                                    
                                                    st.dataframe(peak_df, use_container_width=True, height=300)
                                                    
                                                    # Token frequency as peak
                                                    token_freq = peak_df['peak_token'].value_counts()
                                                    st.markdown(f"**Most frequent peak tokens:** {', '.join([f'{tok} ({cnt})' for tok, cnt in token_freq.head(5).items()])}")
                                        
                                        except Exception as e:
                                            st.error(f"❌ Error creating heatmaps: {e}")
                                            import traceback
                                            st.code(traceback.format_exc())
                        
                        except Exception as e:
                            st.error(f"❌ Error processing chart: {e}")
                            st.exception(e)
                
            except json.JSONDecodeError as e:
                st.error(f"❌ JSON parsing error: {e}")
            except Exception as e:
                st.error(f"❌ File loading error: {e}")
                st.exception(e)
            
            # ===== DOWNLOAD BUTTON AT BOTTOM =====
            if 'activations_uploaded_data' in st.session_state:
                activations_data_final = st.session_state['activations_uploaded_data']
                
                # Recreate verify_full DataFrame for download
                try:
                    verification_rows_final = []
                    for res in activations_data_final.get('results', []):
                        prompt = res.get('prompt', '')
                        tokens = res.get('tokens', [])
                        T = len(tokens)
                        
                        for a in res.get('activations', []):
                            import re
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
                            
                            # Extract values excluding BOS
                            values = a.get('values', [])
                            if len(values) > 1:
                                values_no_bos = values[1:]
                                max_value = max(values_no_bos) if values_no_bos else None
                                max_idx = values_no_bos.index(max_value) + 1 if max_value is not None else None
                                sum_values = sum(values_no_bos) if values_no_bos else 0
                                mean_value = sum_values / len(values_no_bos) if values_no_bos else 0
                                sparsity = (max_value - mean_value) / max_value if max_value and max_value > 0 else 0
                            else:
                                max_value = None
                                max_idx = None
                                sum_values = 0
                                mean_value = 0
                                sparsity = 0
                                
                            peak_token = tokens[max_idx] if isinstance(max_idx, int) and 0 <= max_idx < T else None
                            
                            verification_rows_final.append({
                                'feature_key': feature_key,
                                'layer': layer,
                                'index': idx,
                                'source': src,
                                'prompt': prompt,
                                'activation_max': max_value,
                                'activation_sum': sum_values,
                                'activation_mean': mean_value,
                                'sparsity_ratio': sparsity,
                                'peak_token': peak_token,
                                'peak_token_idx': max_idx
                            })
                    
                    verify_full_final = pd.DataFrame(verification_rows_final)
                    
                    if not verify_full_final.empty:
                        st.markdown("---")
                        csv_export_final = verify_full_final.to_csv(index=False).encode('utf-8')
                        st.download_button(
                            label="📥 Download Activation Analysis CSV",
                            data=csv_export_final,
                            file_name="probe_prompts_activation_analysis.csv",
                            mime="text/csv",
                            type="primary",
                            use_container_width=True,
                            help="Download complete activation analysis data with metrics (excluding BOS)"
                        )
                except Exception:
                    pass  # Silently fail if data unavailable
        else:
            st.info("Upload a JSON file to visualize data")

else:
    st.info("Load a graph JSON to start analysis")

# ===== SIDEBAR INFO =====

st.sidebar.markdown("---")
st.sidebar.header("Info")
st.sidebar.write("""
**Probe Prompts** analyzes how graph features 
activate on specific concepts using Neuronpedia APIs.

**Workflow:**
1. Load a graph JSON (from file or API)
2. Load feature subset or use all features
3. Generate concepts with OpenAI or enter manually
4. Edit/save concepts (prompts JSON format)
5. Run analysis (via Neuronpedia API)
6. Visualize and download results

**Calculated metrics:**
- Activations on label span and full sequence
- Z-scores (standard, robust, log)
- Density, cosine similarity, ratio vs original
- Original influence for each feature
""")

st.sidebar.caption("Version: 2.0.0 | Probe Prompts API")
