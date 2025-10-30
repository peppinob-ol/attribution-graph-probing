"""Page 0 - Graph Generation: Generate Attribution Graphs on Neuronpedia"""
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

# Try to import PipelineState (optional - won't break if missing)
try:
    from eda.utils.pipeline_state import PipelineState
    PIPELINE_STATE_AVAILABLE = True
except ImportError:
    PIPELINE_STATE_AVAILABLE = False

# Import graph generation functions
try:
    from scripts.neuronpedia_graph_generation import (
        generate_attribution_graph,
        get_graph_stats,
        load_api_key,
        extract_static_metrics_from_json
    )
except ImportError:
    # Fallback if module is not directly importable
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
1. **Generate a new attribution graph on Neuronpedia** to analyze how the model predicts the next token. \n
2. **Analyze the graph** to understand the contribution of each feature.\n
3. **Filter Features by Cumulative Influence Coverage** for downstream analysis.
""")

# ===== SIDEBAR: CONFIGURATION =====

st.sidebar.header("Configuration")

# Load API key
api_key = load_api_key()

if not api_key:
    st.sidebar.error("API Key not found!")
    st.error("""
    **Neuronpedia API Key Required!**
       
    1. Obtain an API key from [Neuronpedia](https://www.neuronpedia.org/)
    2. Add to `.env` file in project root:
       ```
       NEURONPEDIA_API_KEY='your-key-here'
       ```
    3. Or set the environment variable:
       ```
       export NEURONPEDIA_API_KEY='your-key-here'
       ```
    """)
    st.stop()

st.sidebar.success(f"API Key loaded ({len(api_key)} characters)")

# ===== SECTION: GENERATE NEW GRAPH =====

st.header("🌐 Generate New Attribution Graph")

# INPUT PROMPT
st.subheader("1️⃣ Prompt Configuration")

prompt = st.text_area(
    "Prompt to analyze",
    value="The capital of state containing Dallas is",
    height=100,
    help="Enter the prompt to analyze. The model will try to predict the next token."
)

# GRAPH PARAMETERS
st.subheader("Graph Parameters")

with st.expander("Advanced configuration", expanded=False):
    col1, col2 = st.columns(2)
    
    with col1:
        st.write("**Model & Source Set**")
        
        model_id = st.selectbox(
            "Model ID",
            ["gemma-2-2b", "gpt2-small", "gemma-2-9b"],
            help="Model to analyze"
        )
        
        source_set_name = st.text_input(
            "Source Set Name",
            value="clt-hp", #"gemmascope-transcoder-16k",
            help="Name of the SAE source set to use"
        )
        
        max_feature_nodes = st.number_input(
            "Max Feature Nodes",
            min_value=100,
            max_value=10000,
            value=5000,
            step=100,
            help="Maximum number of feature nodes to include"
        )
    
    with col2:
        st.write("**Thresholds**")
        
        node_threshold = st.slider(
            "Node Threshold",
            min_value=0.0,
            max_value=1.0,
            value=0.8,
            step=0.05,
            help="Minimum importance threshold to include a node"
        )
        
        edge_threshold = st.slider(
            "Edge Threshold",
            min_value=0.0,
            max_value=1.0,
            value=0.85,
            step=0.05,
            help="Minimum importance threshold to include an edge"
        )
        
        max_n_logits = st.number_input(
            "Max N Logits",
            min_value=1,
            max_value=50,
            value=10,
            step=1,
            help="Maximum number of logits to consider"
        )
        
        desired_logit_prob = st.slider(
            "Desired Logit Probability",
            min_value=0.5,
            max_value=0.99,
            value=0.95,
            step=0.01,
            help="Desired cumulative probability for logits"
        )

slug = st.text_input(
    "Custom slug (optional)",
    value="",
    help="If empty, will be generated automatically"
)

# GENERATION
st.subheader("Generation")

col1, col2 = st.columns([1, 2])

with col1:
    generate_button = st.button("🌐 Generate Graph", type="primary", use_container_width=True)
with col2:
    save_locally = st.checkbox("Save locally", value=True)

# State
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
        st.error("Enter a valid prompt!")
        st.stop()
    
    progress_bar = st.progress(0)
    status_text = st.empty()
    
    try:
        status_text.text("Preparing...")
        progress_bar.progress(10)
        
        status_text.text("Sending request to Neuronpedia...")
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
        
        # Add generation parameters to result for later use
        if result['success']:
            result['source_set_name'] = source_set_name
            result['node_threshold'] = node_threshold
            result['desired_logit_prob'] = desired_logit_prob
        
        # Rename file to new format if saved locally (BEFORE saving to session_state)
        if result['success'] and result.get('local_path') and save_locally and PIPELINE_STATE_AVAILABLE:
            old_path = Path(result['local_path'])
            if old_path.exists():
                # Generate new filename with st1_ prefix
                new_filename = PipelineState.generate_filename(
                    step=1,
                    file_type='graph',
                    prompt=prompt
                )
                new_path = old_path.parent / new_filename
                
                # Rename file
                old_path.rename(new_path)
                
                # Update result with absolute path (AFTER rename)
                result['local_path'] = str(new_path.resolve())
                result['renamed_to_new_format'] = True
        
        # Save result to session_state (with updated path)
        st.session_state.generation_result = result
        
        # Build Neuronpedia URL
        if result['success']:
            neuronpedia_url = (
                f"https://www.neuronpedia.org/{result.get('model_id', 'gemma-2-2b')}/graph"
                f"?sourceSet={result.get('source_set_name', 'clt-hp')}"
                f"&slug={result.get('slug', '')}"
                f"&pruningThreshold={result.get('node_threshold', 0.8)}"
                f"&densityThreshold={result.get('desired_logit_prob', 0.95)}"
            )
            
            # Get the filename for display
            if result.get('local_path'):
                filename = Path(result['local_path']).name
                st.success(f"✅ Graph generated successfully: `{filename}`\n\n" f"[**Open Graph on Neuronpedia**]({neuronpedia_url})")
    
    
    except Exception as e:
        progress_bar.empty()
        status_text.empty()
        st.error(f"Unexpected error: {str(e)}")
        with st.expander("Details"):
            import traceback
            st.code(traceback.format_exc())

st.markdown("---")

# ===== SECTION: ANALYZE GRAPH =====

st.subheader("2️⃣ Analyze Graph")

# Check if we just generated a graph
just_generated = st.session_state.get('generation_result') and st.session_state.generation_result.get('success')
generated_path = st.session_state.generation_result.get('local_path') if just_generated else None

if just_generated and generated_path:
    # Auto-select the just-generated graph
    from pathlib import Path as PathLib
    
    # Convert to Path and handle both absolute and relative paths
    gen_path = PathLib(generated_path)
    if gen_path.is_absolute():
        # Absolute path - make it relative to parent_dir
        selected_json = str(gen_path.relative_to(parent_dir))
    else:
        # Already relative - use as is
        selected_json = str(gen_path).replace('\\', '/')
    
    st.info(f"📊 **Ready to analyze**: `{gen_path.name}` (just generated)")
    
    # Option to select a different file
    with st.expander("📁 Select a different graph file", expanded=False):
        json_dir = parent_dir / "output" / "graph_data"
        if json_dir.exists():
            json_files = sorted(json_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
            if json_files:
                json_options = [str(f.relative_to(parent_dir)) for f in json_files]
                # Find index of generated file
                default_idx = 0
                try:
                    default_idx = json_options.index(selected_json)
                except ValueError:
                    pass
                
                selected_json_alt = st.selectbox(
                    "Select JSON file",
                    options=json_options,
                    index=default_idx,
                    key="alt_json_select",
                    help="JSON files sorted by date (most recent first)"
                )
                if st.button("Use this file instead"):
                    selected_json = selected_json_alt
                    st.rerun()
else:
    # Normal file selection (no graph just generated)
    st.write("""
    Extract static metrics (`node_influence`, `cumulative_influence`, `frac_external_raw`) from an existing graph.
    """)
    
    json_dir = parent_dir / "output" / "graph_data"
    if json_dir.exists():
        json_files = sorted(json_dir.glob("*.json"), key=lambda x: x.stat().st_mtime, reverse=True)
        
        if json_files:
            # Use relative paths for display
            json_options = [str(f.relative_to(parent_dir)) for f in json_files]
            selected_json = st.selectbox(
                "Select JSON file",
                options=json_options,
                help="JSON files sorted by date (most recent first)"
            )
        else:
            st.warning("No JSON files found in `output/graph_data/`")
            selected_json = None
    else:
        st.warning("Directory `output/graph_data/` not found")
        selected_json = None

# Show file info and analysis button if we have a selected file
if selected_json:
    file_path = parent_dir / selected_json
    
    # Check if file exists before accessing stats
    if not file_path.exists():
        st.error(f"❌ File not found: `{file_path.name}`")
        st.warning("The file may have been moved or renamed. Please refresh the page or select another file.")
        st.stop()
    
    file_size = file_path.stat().st_size / 1024 / 1024
    file_time = datetime.fromtimestamp(file_path.stat().st_mtime)
    
    col1, col2, col3 = st.columns(3)
    with col1:
        st.metric("Size", f"{file_size:.2f} MB")
    with col2:
        st.metric("Date", file_time.strftime("%Y-%m-%d %H:%M"))
    with col3:
        st.metric("Name", file_path.name[:20] + "...")
    
    # Extract button
    button_label = "📊 Analyze This Graph" if just_generated else "📊 Analyze Graph"
    if st.button(button_label, key="extract_existing", type="primary"):
        try:
            with st.spinner("Extracting metrics..."):
                json_full_path = str(parent_dir / selected_json)
                with open(json_full_path, 'r', encoding='utf-8') as f:
                    graph_data = json.load(f)
                
                csv_output_path = str(parent_dir / "output" / "graph_feature_static_metrics.csv")
                df = extract_static_metrics_from_json(
                    graph_data,
                    output_path=csv_output_path,
                    verbose=False
                )
                
                # Save in session_state to persist across reruns
                st.session_state.extracted_graph_data = graph_data
                st.session_state.extracted_csv_df = df
                st.session_state.analysis_performed = True
            
            st.success(f"✅ CSV generated: `{csv_output_path}`")
            st.info("📊 Scroll down to see interactive visualizations")
            
        except Exception as e:
            st.error(f"❌ Error: {str(e)}")

st.markdown("---")

# ===== EXTRACTED DATA VISUALIZATION (persists across reruns) =====

if st.session_state.extracted_graph_data is not None and st.session_state.extracted_csv_df is not None:
    graph_data = st.session_state.extracted_graph_data
    df = st.session_state.extracted_csv_df
    
    # Only show if analysis was performed
    if st.session_state.get('analysis_performed', False):
        st.header("Extracted Data Analysis")
        
        # CSV Metrics
        col1, col2, col3, col4, col5 = st.columns(5)
        with col1:
            st.metric("Features", len(df))
        with col2:
            st.metric("Unique Tokens", df['ctx_idx'].nunique())
        with col3:
            st.metric("Mean Activation", f"{df['activation'].mean():.3f}")
        with col4:
            # Use node_influence (marginal influence) for total sum
            st.metric("Sum Node Infl", f"{df['node_influence'].sum():.2f}")
        with col5:
            st.metric("Mean Frac Ext", f"{df['frac_external_raw'].mean():.3f}")
        
        with st.expander("View Complete Dataframe", expanded=False):
            st.dataframe(df, use_container_width=True, height=600)
        
        # Scatter plot: Layer vs Context Position with Influence

        # Prepare data from JSON for scatter plot
        if 'nodes' in graph_data:
            import pandas as pd
            import plotly.express as px
            
            # Extract prompt_tokens from metadata to map ctx_idx -> token
            prompt_tokens = graph_data.get('metadata', {}).get('prompt_tokens', [])
            
            # Scatter plot visualization with filter
            from eda.utils.graph_visualization import create_scatter_plot_with_filter
            filtered_features = create_scatter_plot_with_filter(graph_data)
            
            # Save filtered_features for export section
            if filtered_features is not None and len(filtered_features) > 0:
                st.session_state.filtered_features_export = filtered_features

# ===== RESULTS VISUALIZATION =====

if st.session_state.generation_result is not None:
    result = st.session_state.generation_result
    
    if result['success']:
        st.header("Results")
        
        # Metrics
        col1, col2, col3, col4 = st.columns(4)
        with col1:
            st.metric("Nodes", result['num_nodes'])
        with col2:
            st.metric("Links", result['num_links'])
        with col3:
            st.metric("Model", result['model_id'])
        with col4:
            slug_short = result['slug'][:15] + "..." if len(result['slug']) > 15 else result['slug']
            st.metric("Slug", slug_short)
                
        # Show CSV if available
        if st.session_state.static_metrics_df is not None:
            df = st.session_state.static_metrics_df
            
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Features", len(df))
            with col2:
                st.metric("Sum Node Infl", f"{df['node_influence'].sum():.2f}")
            with col3:
                st.metric("Max Cumul", f"{df['cumulative_influence'].max():.4f}")
            with col4:
                st.metric("Mean Frac Ext", f"{df['frac_external_raw'].mean():.3f}")
            
            with st.expander("Preview CSV"):
                st.dataframe(df.head(20), use_container_width=True)
            
            with st.expander("Distribution"):
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
        


# ===== SUMMARY CHARTS: COVERAGE AND STRENGTH =====
# Only show if analysis was performed
if st.session_state.get('analysis_performed', False):
    # Data source: prefer extracted data, otherwise last generated graph
    graph_data_for_plots = None
    if st.session_state.get('extracted_graph_data') is not None:
        graph_data_for_plots = st.session_state.extracted_graph_data
    elif st.session_state.get('generation_result') is not None and st.session_state.generation_result.get('success'):
        graph_data_for_plots = st.session_state.generation_result.get('graph_data')

    if graph_data_for_plots is not None and 'nodes' in graph_data_for_plots:
        with st.expander("Summary Charts: Coverage and Strength", expanded=False):
            import pandas as pd
            import plotly.express as px
            import numpy as np

            nodes_df = pd.DataFrame(graph_data_for_plots['nodes'])
            is_feature = nodes_df['node_id'].astype(str).str[0].str.isdigit() & nodes_df['node_id'].astype(str).str.contains('_')
            feat_nodes = nodes_df.loc[is_feature].copy()
            
            if len(feat_nodes) == 0:
                st.warning("No features found in current data.")
            else:
                # Add slider to filter (reuse same logic as create_scatter_plot_with_filter)
                max_influence = feat_nodes['influence'].max()
                
                st.markdown("### Filter Features by Cumulative Influence")
                st.info(f"""
                **Use the slider to filter the charts below** based on cumulative influence coverage (0-{max_influence:.2f}).
                Summary charts will show only features with `influence <= threshold`.
                """)
                
                # Check if main slider already exists (from create_scatter_plot_with_filter)
                # If it exists, use it, otherwise create a new one
                slider_key = "cumulative_slider_summary"
                if "cumulative_slider_main" in st.session_state:
                    # Reuse main slider value
                    cumulative_threshold_summary = st.session_state.cumulative_slider_main
                    st.info(f"Synchronized with main slider: threshold = {cumulative_threshold_summary:.4f}")
                else:
                    # Create separate slider
                    cumulative_threshold_summary = st.slider(
                        "Cumulative Influence Threshold (summary charts)",
                        min_value=0.0,
                        max_value=float(max_influence),
                        value=float(max_influence),
                        step=0.01,
                        key=slider_key,
                        help=f"Keep only features with influence <= threshold. Range: 0.0 - {max_influence:.2f}"
                    )
                
                # Apply filter
                feat_nodes_filtered = feat_nodes[feat_nodes['influence'] <= cumulative_threshold_summary].copy()
                
                if len(feat_nodes_filtered) == 0:
                    st.warning("No features match the current filter. Increase the threshold.")
                else:
                    # Show filter statistics
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        st.metric("Total Features", len(feat_nodes))
                    with col2:
                        st.metric("Filtered Features", len(feat_nodes_filtered))
                    with col3:
                        pct = (len(feat_nodes_filtered) / len(feat_nodes) * 100) if len(feat_nodes) > 0 else 0
                        st.metric("% Kept", f"{pct:.1f}%")
                    
                    st.markdown("---")
                    
                    # Calculate n_ctx and statistics per feature
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

                    # Chart 1: Coverage (Histogram + ECDF)
                    st.subheader("Feature Coverage (n_ctx)")
                    c1, c2 = st.columns(2)
                    with c1:
                        fig_hist = px.histogram(cov, x='n_ctx', color_discrete_sequence=['#4C78A8'])
                        fig_hist.update_layout(title='n_ctx distribution per feature',
                                               xaxis_title='Number of unique ctx_idx',
                                               yaxis_title='Number of features')
                        st.plotly_chart(fig_hist, use_container_width=True)
                    with c2:
                        fig_ecdf = px.ecdf(cov, x='n_ctx', color_discrete_sequence=['#F58518'])
                        fig_ecdf.update_layout(title='n_ctx ECDF',
                                               xaxis_title='Number of unique ctx_idx',
                                               yaxis_title='Cumulative fraction')
                        st.plotly_chart(fig_ecdf, use_container_width=True)

                    # Chart 2: Strength vs Coverage (Activation vs n_ctx and Scatter mean)
                    st.subheader("Strength vs Coverage")
                    c3, c4 = st.columns(2)
                    with c3:
                        fig_violin = px.violin(nodes_with_cov, x='n_ctx', y='activation', box=True, points=False)
                        fig_violin.update_layout(title='Activation per n_ctx',
                                                 xaxis_title='n_ctx (feature)',
                                                 yaxis_title='Activation (node)')
                        st.plotly_chart(fig_violin, use_container_width=True)
                    with c4:
                        fig_scatter = px.scatter(per_feat_cov, x='mean_activation', y='mean_influence',
                                                 color='n_ctx', size='n_ctx', hover_data=['feature_key'],
                                                 color_continuous_scale='Viridis')
                        # Correlations for subtitle
                        if len(per_feat_cov) >= 2:
                            pearson = float(per_feat_cov['mean_activation'].corr(per_feat_cov['mean_influence'], method='pearson'))
                            spearman = float(per_feat_cov['mean_activation'].corr(per_feat_cov['mean_influence'], method='spearman'))
                            fig_scatter.update_layout(title=f'Mean activation vs mean influence<br>(r={pearson:.2f}, rho={spearman:.2f})')
                        else:
                            fig_scatter.update_layout(title='Mean activation vs mean influence')
                        fig_scatter.update_layout(xaxis_title='Mean activation (per feature)',
                                                  yaxis_title='Mean influence (per feature)')
                        st.plotly_chart(fig_scatter, use_container_width=True)
                    
                    # Quick insights
                    with st.expander("Insights from charts", expanded=False):
                        # Calculate key statistics
                        top_n_ctx = cov['n_ctx'].max()
                        n_top = len(cov[cov['n_ctx'] == top_n_ctx])
                        top_features = cov[cov['n_ctx'] == top_n_ctx]['feature_key'].tolist()
                        
                        st.markdown(f"""
                        **Coverage (n_ctx)**:
                        - {len(cov)} unique features in filtered dataset
                        - {n_top} features present in all {top_n_ctx} contexts
                        - Multi-context features ({top_n_ctx}): {', '.join([f'`{f}`' for f in top_features[:5]])}
                        
                        **Strength vs Coverage**:
                        - Activation-influence correlation: **r={pearson:.2f}** (Pearson), **rho={spearman:.2f}** (Spearman)
                        - {"Negative correlation: features with high activation tend to have low influence" if pearson < -0.2 else "Weak or positive correlation between activation and influence"}
                        """)
                        
                        # Group statistics
                        if len(nodes_with_cov) > 0:
                            g1 = nodes_with_cov[nodes_with_cov['n_ctx'] == 1]
                            g_multi = nodes_with_cov[nodes_with_cov['n_ctx'] >= 5]
                            
                            if len(g1) > 0 and len(g_multi) > 0:
                                st.markdown(f"""
                                **Group comparison**:
                                - n_ctx=1: {len(g1)} nodes, mean_activation={g1['activation'].mean():.2f}, mean_influence={g1['influence'].mean():.3f}
                                - n_ctx>=5: {len(g_multi)} nodes, mean_activation={g_multi['activation'].mean():.2f}, mean_influence={g_multi['influence'].mean():.3f}
                                """)

# ===== EXPORT SELECTED FEATURES =====

if st.session_state.get('analysis_performed', False) and st.session_state.get('filtered_features_export') is not None:
    filtered_features = st.session_state.filtered_features_export
    
    if len(filtered_features) > 0:
        st.markdown("---")
        st.subheader("Export Selected Features")
        
        # Convert dataframe to format [{"layer": X, "index": Y}, ...]
        # Remove duplicates using set of tuples (layer, feature)
        unique_features = {
            (int(row['layer']), int(row['feature']))
            for _, row in filtered_features.iterrows()
        }
        
        # Convert to sorted list of dicts
        features_export = [
            {"layer": layer, "index": feature}
            for layer, feature in sorted(unique_features)
        ]
        
        # Also extract selected node_ids (for subgraph upload)
        node_ids_export = sorted(filtered_features['id'].unique().tolist())
        
        # Create complete export with features AND node_ids
        export_data = {
            "features": features_export,
            "node_ids": node_ids_export,
            "metadata": {
                "n_features": len(features_export),
                "n_nodes": len(node_ids_export),
                "cumulative_threshold": st.session_state.get('cumulative_slider_main', None),
                "exported_at": datetime.now().isoformat()
            }
        }
        
        # Statistics
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Unique Features", len(features_export))
        with col2:
            st.metric("Selected Nodes", len(node_ids_export))
        with col3:
            st.metric("Unique Layers", len({f['layer'] for f in features_export}))
        
        # Download JSON (complete format)
        st.download_button(
            label="📥 Download Features+Nodes Subset",
            data=json.dumps(export_data, indent=2, ensure_ascii=False),
            file_name="selected_features_with_nodes.json",
            mime="application/json",
            help="Complete format with features and node_ids (for Node Grouping + Probe Prompts + batch_get_activations.py)",
            use_container_width=True,
            type="primary"
        )
        
        # LEGACY BUTTON (hidden - all tools now support complete format)
        # with col_legacy:
        #     st.download_button(
        #         label="Download Features JSON (legacy)",
        #         data=json.dumps(features_export, indent=2, ensure_ascii=False),
        #         file_name="selected_features.json",
        #         mime="application/json",
        #         help="Legacy format (features only, compatible with batch_get_activations.py)"
        #     )
        
        # Preview
        with st.expander("Preview Complete Export", expanded=False):
            st.json({
                "features": features_export[:5],
                "node_ids": node_ids_export[:10],
                "metadata": export_data["metadata"]
            })

# ===== FOOTER =====

st.sidebar.markdown("---")
st.sidebar.subheader("Info")
st.sidebar.markdown("""
**Attribution Graph**: visualizes how SAE features contribute to predictions.

**Elements**:
- Embedding nodes: input tokens
- Feature nodes: SAE latents
- Logit nodes: predicted tokens
""")

st.sidebar.caption("Powered by Neuronpedia API")

