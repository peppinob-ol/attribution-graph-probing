"""
Graph generation and feature selection for batch experiments.
"""
import json
import sys
from pathlib import Path
from typing import Dict, Any, List

# Add parent to path for imports
parent_dir = Path(__file__).parent.parent.parent.parent
if str(parent_dir) not in sys.path:
    sys.path.insert(0, str(parent_dir))

from scripts import generate_attribution_graph, extract_static_metrics_from_json


def process_graph_step(config: Dict[str, Any], seed: Dict[str, Any], paths: Dict[str, Path], 
                       verbose: bool = True) -> bool:
    """
    Process graph generation step for a seed.
    
    If seed has graph_json (precomputed), verify it exists.
    Otherwise, generate via Neuronpedia API.
    
    Then compute metrics and select features.
    
    Returns True if successful, False otherwise.
    """
    graph_dir = paths['graph_dir']
    graph_dir.mkdir(parents=True, exist_ok=True)
    
    graph_json_path = paths['graph_json']
    
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
        model_id = config['model']['id']
        source_set_name = graph_gen.get('source_set_name', config['model']['source_set'])
        
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
                    generated_path.rename(graph_json_path)
        
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
        
        if selection == 'cumulative_influence':
            threshold = features_config['threshold']
            
            # Filter by cumulative_influence <= threshold
            selected = df[df['cumulative_influence'] <= threshold]
            
            # Extract unique (layer, feature) pairs
            features_list = []
            for _, row in selected.iterrows():
                if row['layer'] >= 0:  # Exclude embeddings (layer -1) for now
                    features_list.append({
                        'layer': int(row['layer']),
                        'index': int(row['feature'])
                    })
            
            # Remove duplicates
            seen = set()
            unique_features = []
            for feat in features_list:
                key = (feat['layer'], feat['index'])
                if key not in seen:
                    seen.add(key)
                    unique_features.append(feat)
            
            if verbose:
                print(f"    Selected {len(unique_features)} features at threshold {threshold}")
        
        else:
            print(f"ERROR: Unsupported selection method: {selection}")
            return False
        
        # Write selected_features_with_nodes.json
        output_data = {
            'features': unique_features,
            'metadata': {
                'n_features': len(unique_features),
                'selection': selection,
                'threshold': threshold if selection == 'cumulative_influence' else None,
            }
        }
        
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

