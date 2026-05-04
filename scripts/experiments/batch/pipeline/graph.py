"""
Graph generation and feature selection for batch experiments.
"""
import json
import math
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add parent to path for imports
# From scripts/experiments/batch/pipeline/graph.py:
#   parent = pipeline/
#   parent.parent = batch/
#   parent.parent.parent = experiments/
#   parent.parent.parent.parent = scripts/
#   parent.parent.parent.parent.parent = repo_root
repo_root = Path(__file__).parent.parent.parent.parent.parent
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

# Import functions by loading the script module directly
import importlib.util

graph_gen_script = repo_root / "scripts" / "00_neuronpedia_graph_generation.py"

if not graph_gen_script.exists():
    raise FileNotFoundError(f"Graph generation script not found at: {graph_gen_script}")

spec = importlib.util.spec_from_file_location("graph_gen_module", str(graph_gen_script))
graph_gen_module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(graph_gen_module)

generate_attribution_graph = graph_gen_module.generate_attribution_graph
extract_static_metrics_from_json = graph_gen_module.extract_static_metrics_from_json
compute_error_node_influence = graph_gen_module.compute_error_node_influence


def process_graph_step(config: Dict[str, Any], seed: Dict[str, Any], paths: Dict[str, Path], 
                       verbose: bool = True) -> bool:
    """
    Process graph generation step for a seed.
    
    If seed has graph_json (precomputed), verify it exists.
    Otherwise, generate via Neuronpedia API (unless graph already exists and graph_generation is disabled).
    
    Then compute metrics and select features.
    
    Returns True if successful, False otherwise.
    """
    graph_dir = paths['graph_dir']
    graph_dir.mkdir(parents=True, exist_ok=True)
    
    graph_json_path = paths['graph_json']
    
    # Check if graph_generation step is enabled
    steps = config.get('steps', {})
    graph_generation_enabled = steps.get('graph_generation', False)
    
    # Step 1: Get or verify graph.json
    if 'graph_json' in seed:
        # Precomputed mode: verify file exists
        source_graph = Path(seed['graph_json'])
        if not source_graph.exists():
            print(f"ERROR: Precomputed graph not found: {source_graph}")
            return False
        
        # Copy to output location if different
        if source_graph.resolve() != graph_json_path.resolve():
            if verbose:
                print(f"  Copying graph: {source_graph} -> {graph_json_path}")
            import shutil
            shutil.copy2(source_graph, graph_json_path)
    
    elif graph_json_path.exists() and not graph_generation_enabled:
        # Graph already exists and graph_generation is disabled - reuse existing
        if verbose:
            print(f"  [REUSE] Using existing graph: {graph_json_path}")
    
    elif 'prompt' in seed:
        # Generate via API
        if verbose:
            print(f"  Generating graph via Neuronpedia API...")
            print(f"    Prompt: {seed['prompt'][:60]}...")
        
        # Get API key
        import os
        api_key = os.environ.get('NEURONPEDIA_API_KEY')
        if not api_key:
            print("ERROR: NEURONPEDIA_API_KEY not set in environment")
            return False
        
        # Get graph generation params from config
        graph_gen = config.get('graph_generation', {})
        api_params = graph_gen.get('api_params', {}) or {}
        model_id = config['model']['id']
        # Precedence (most specific first):
        #   1. graph_generation.api_params.sourceSetName  (Neuronpedia API param name)
        #   2. graph_generation.source_set_name           (legacy snake_case key)
        #   3. model.source_set                           (UI/source-set alias, may differ from
        #                                                  the actual transcoder used to build the graph)
        source_set_name = (
            api_params.get('sourceSetName')
            or graph_gen.get('source_set_name')
            or config['model']['source_set']
        )
        
        # Call generation function
        try:
            result = generate_attribution_graph(
                prompt=seed['prompt'],
                api_key=api_key,
                model_id=model_id,
                source_set_name=source_set_name,
                slug=seed['slug'],
                save_locally=True,
                output_dir=str(graph_dir),
                verbose=verbose
            )
            
            if not result.get('success'):
                print(f"ERROR: Graph generation failed: {result.get('error')}")
                return False
            
            # Move generated file to standard name
            if result.get('local_path'):
                generated_path = Path(result['local_path'])
                if generated_path != graph_json_path:
                    # Use replace() to overwrite if exists (Windows-safe)
                    generated_path.replace(graph_json_path)
        
        except Exception as e:
            print(f"ERROR: Graph generation exception: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    else:
        print(f"ERROR: Seed has neither graph_json nor prompt: {seed}")
        return False
    
    # Step 2: Compute static metrics
    if verbose:
        print(f"  Computing graph metrics...")
    
    try:
        with open(graph_json_path, 'r', encoding='utf-8') as f:
            graph_data = json.load(f)
        
        metrics_csv_path = paths['graph_metrics_csv']
        df = extract_static_metrics_from_json(
            graph_data,
            output_path=str(metrics_csv_path),
            verbose=verbose
        )
        
        if df is None or df.empty:
            print(f"ERROR: Failed to extract metrics from graph")
            return False

        # Persist error-node influence into manifest.json
        error_info = compute_error_node_influence(df)
        manifest_path = paths['base'] / 'manifest.json'
        try:
            manifest_data = {}
            if manifest_path.exists():
                with open(manifest_path, 'r', encoding='utf-8') as mf:
                    manifest_data = json.load(mf)
            manifest_data['graph_quality'] = error_info
            with open(manifest_path, 'w', encoding='utf-8') as mf:
                json.dump(manifest_data, mf, indent=2, ensure_ascii=False)
            if verbose:
                pct = error_info.get('error_node_influence_pct')
                print(f"  Error-node influence: {pct}%")
        except Exception as exc:
            if verbose:
                print(f"  WARNING: Could not write graph_quality to manifest: {exc}")

    except Exception as e:
        print(f"ERROR: Metrics computation failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    # Step 3: Select features
    if verbose:
        print(f"  Selecting features...")
    
    try:
        features_config = config['features']
        selection = features_config['selection']
        
        post_filter_cfg = features_config.get('post_filter', {})
        node_threshold_config = post_filter_cfg.get('node_threshold')
        node_threshold_value = None
        if node_threshold_config is not None:
            node_threshold_value = float(node_threshold_config)
            if node_threshold_value > 1:
                node_threshold_value = node_threshold_value / 100.0

        if selection == 'cumulative_influence':
            threshold = features_config['threshold']
            
            # Filter by cumulative_influence <= threshold
            selected = df[df['cumulative_influence'] <= threshold]
            
            # Extract unique (layer, feature) pairs
            features_list = []
            for _, row in selected.iterrows():
                if row['layer'] >= 0:  # Exclude embeddings (layer -1) for now
                    idx_value = row.get('id')
                    if idx_value is None or (isinstance(idx_value, float) and math.isnan(idx_value)):
                        idx_value = row['feature']
                    features_list.append({
                        'layer': int(row['layer']),
                        'index': int(idx_value)
                    })
            
            # Remove duplicates
            seen = set()
            unique_features = []
            for feat in features_list:
                key = (feat['layer'], feat['index'])
                if key not in seen:
                    seen.add(key)
                    unique_features.append(feat)

            if node_threshold_value is not None and graph_data:
                allowed_pairs = set()
                for node in graph_data.get('nodes', []):
                    node_id = node.get('node_id') or node.get('nodeId')
                    if not node_id:
                        continue
                    feature_type = node.get('feature_type', '')
                    if feature_type != 'cross layer transcoder':
                        continue
                    parts = str(node_id).split('_')
                    if len(parts) < 2 or not parts[0].isdigit():
                        continue
                    try:
                        layer_val = int(parts[0])
                        feature_val = int(parts[1])
                    except ValueError:
                        continue
                    influence_val = node.get('influence')
                    if influence_val is None:
                        continue
                    # Keep features with low cumulative influence (high priority)
                    # Lower influence = selected earlier = more important
                    if influence_val <= node_threshold_value:
                        allowed_pairs.add((layer_val, feature_val))

                before_filter = len(unique_features)
                unique_features = [
                    feat for feat in unique_features
                    if (feat['layer'], feat['index']) in allowed_pairs
                ]
                if verbose:
                    print(f"    Applied node_threshold <= {node_threshold_value:.3f}: kept {len(unique_features)} of {before_filter}")
            
            if verbose:
                print(f"    Selected {len(unique_features)} features at threshold {threshold}")
        
        else:
            print(f"ERROR: Unsupported selection method: {selection}")
            return False
        
        # Collect node_ids for selected features to keep uploads scoped to these nodes
        selected_pairs = {(feat['layer'], feat['index']) for feat in unique_features}
        selected_node_ids: List[str] = []
        if graph_data and selected_pairs:
            for node in graph_data.get('nodes', []):
                node_id = node.get('node_id') or node.get('nodeId')
                if not node_id:
                    continue
                feature_type = node.get('feature_type', '')
                if feature_type != 'cross layer transcoder':
                    # Skip embeddings, logits, reconstruction error nodes
                    continue
                parts = str(node_id).split('_')
                if len(parts) < 2:
                    continue
                layer_token = parts[0]
                if not layer_token.isdigit():
                    # Skip embeddings/logits (e.g., 'E')
                    continue
                try:
                    layer_val = int(layer_token)
                    feature_val = int(parts[1])
                except ValueError:
                    continue
                if (layer_val, feature_val) in selected_pairs:
                    selected_node_ids.append(node_id)

        # Write selected_features_with_nodes.json
        output_data = {
            'features': unique_features,
            'metadata': {
                'n_features': len(unique_features),
                'selection': selection,
                'threshold': threshold if selection == 'cumulative_influence' else None,
                'n_nodes': len(selected_node_ids),
            }
        }
        if node_threshold_value is not None:
            output_data['metadata'].setdefault('post_filter', {})
            output_data['metadata']['post_filter']['node_threshold'] = node_threshold_config
        if selected_node_ids:
            output_data['node_ids'] = selected_node_ids
        
        selected_features_path = paths['selected_features_json']
        with open(selected_features_path, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2, ensure_ascii=False)
        
        if verbose:
            print(f"    Wrote: {selected_features_path}")
    
    except Exception as e:
        print(f"ERROR: Feature selection failed: {e}")
        import traceback
        traceback.print_exc()
        return False
    
    return True

