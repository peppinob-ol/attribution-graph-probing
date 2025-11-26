"""
Node grouping for batch experiments.
Converts activations_dump.json to CSV and runs 02_node_grouping.py.
"""
import json
import csv
import subprocess
import sys
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List

REPO_ROOT = Path(__file__).resolve().parents[4]
SCRIPTS_DIR = REPO_ROOT / 'scripts'


def activations_dump_to_csv(activations_json_path: Path, output_csv_path: Path, 
                            verbose: bool = True) -> bool:
    """
    Convert activations_dump.json to minimal CSV format expected by 02_node_grouping.py.
    
    Required CSV columns:
    - feature_key (layer_index format, e.g., "1_12928")
    - layer
    - feature (index)
    - prompt
    - peak_token
    - peak_token_idx
    - activation_max
    - sparsity_ratio
    
    Args:
        activations_json_path: Path to activations_dump.json
        output_csv_path: Path to write CSV
        verbose: Print progress
    
    Returns:
        True if successful, False otherwise
    """
    try:
        with open(activations_json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        rows = []
        
        for result in data.get('results', []):
            prompt = result.get('prompt', '')
            tokens = result.get('tokens', [])
            
            for act in result.get('activations', []):
                source = act['source']  # e.g., "20-clt-hp"
                layer = int(source.split('-')[0])
                index = int(act['index'])
                values = act.get('values', [])
                
                if not values:
                    continue
                
                # Find peak (exclude BOS at index 0, matching frontend behavior)
                if len(values) > 1:
                    values_no_bos = values[1:]
                    peak_val = max(values_no_bos)
                    peak_idx = values_no_bos.index(peak_val) + 1  # +1 to account for skipped BOS
                else:
                    peak_val = values[0] if values else 0
                    peak_idx = 0
                peak_token = tokens[peak_idx] if peak_idx < len(tokens) else ""
                
                # Calculate sparsity ratio: (peak - mean) / peak (using values_no_bos)
                if len(values) > 1:
                    mean_val = sum(values_no_bos) / len(values_no_bos)
                    sparsity_ratio = (peak_val - mean_val) / peak_val if peak_val > 0 else 0.0
                else:
                    sparsity_ratio = 0.0
                
                rows.append({
                    'feature_key': f"{layer}_{index}",
                    'layer': layer,
                    'feature': index,
                    'prompt': prompt,
                    'peak_token': peak_token,
                    'peak_token_idx': peak_idx,
                    'activation_max': peak_val,
                    'sparsity_ratio': sparsity_ratio,
                })
        
        if not rows:
            print(f"ERROR: No activation rows generated from {activations_json_path}")
            return False
        
        # Write CSV
        output_csv_path.parent.mkdir(parents=True, exist_ok=True)
        
        with open(output_csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            writer.writeheader()
            writer.writerows(rows)
        
        if verbose:
            print(f"    Converted {len(rows)} activation records to CSV")
            print(f"    Wrote: {output_csv_path}")
        
        return True
    
    except Exception as e:
        print(f"ERROR: Failed to convert activations to CSV: {e}")
        import traceback
        traceback.print_exc()
        return False


def upload_subgraph(config: Dict[str, Any], seed: Dict[str, Any], 
                   paths: Dict[str, Path], verbose: bool = True) -> bool:
    """
    Upload grouped subgraph to Neuronpedia.
    
    Args:
        config: Full experiment config
        seed: Seed config
        paths: Paths dict
        verbose: Print progress
    
    Returns:
        True if successful, False otherwise
    """
    grouping_config = config.get('grouping', {})
    upload_config = grouping_config.get('upload', {})
    
    if not upload_config.get('enabled'):
        if verbose:
            print(f"  [SKIP] Neuronpedia upload disabled")
        return True
    
    if verbose:
        print(f"  Uploading subgraph to Neuronpedia...")
    
    # Get API key
    api_key_env = upload_config.get('api_key_env', 'NEURONPEDIA_API_KEY')
    api_key = os.environ.get(api_key_env)
    
    if not api_key:
        print(f"ERROR: {api_key_env} not set in environment")
        return False
    
    # Load grouped CSV
    import pandas as pd
    try:
        df_grouped = pd.read_csv(paths['grouping_csv'], encoding='utf-8')
    except Exception as e:
        print(f"ERROR: Failed to load grouped CSV: {e}")
        return False
    
    # Get display name
    display_name_template = upload_config.get('display_name_template', '{slug} (auto-grouped)')
    display_name = display_name_template.format(slug=seed['slug'])
    
    # Import upload function from 02_node_grouping.py
    sys.path.insert(0, str(SCRIPTS_DIR))
    
    import importlib.util
    grouping_script = SCRIPTS_DIR / '02_node_grouping.py'
    spec = importlib.util.spec_from_file_location("grouping_module", str(grouping_script))
    grouping_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(grouping_module)
    
    upload_subgraph_to_neuronpedia = grouping_module.upload_subgraph_to_neuronpedia
    
    # Load selected nodes (features + node_ids) to mimic manual workflow
    selected_nodes_data = None
    selected_nodes_path = paths.get('selected_features_json')
    if selected_nodes_path and selected_nodes_path.exists():
        try:
            with open(selected_nodes_path, 'r', encoding='utf-8') as f:
                selected_nodes_data = json.load(f)
            if verbose:
                n_nodes = len(selected_nodes_data.get('node_ids', []))
                n_features = len(selected_nodes_data.get('features', []))
                print(f"    Loaded selected nodes: {n_features} features / {n_nodes} nodes")
        except Exception as e:
            print(f"WARNING: Failed to load selected nodes JSON ({selected_nodes_path}): {e}")
    else:
        if verbose:
            print(f"    WARNING: selected_features_with_nodes.json not found; embeddings/logits may be grouped")

    # Call upload
    try:
        result = upload_subgraph_to_neuronpedia(
            df_grouped=df_grouped,
            graph_json_path=str(paths['graph_json']),
            api_key=api_key,
            display_name=display_name,
            overwrite_id=upload_config.get('overwrite_id', ''),
            selected_nodes_data=selected_nodes_data,
            verbose=verbose
        )
        
        # Save upload response
        upload_response_path = paths['grouping_dir'] / 'upload_response.json'
        with open(upload_response_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)
        
        if verbose:
            print(f"    Upload successful!")
            print(f"    Response saved: {upload_response_path}")

        # Update manifest with Neuronpedia URL metadata
        metadata_url = None
        metadata = {}
        try:
            with open(paths['graph_json'], 'r', encoding='utf-8') as graph_file:
                graph_data = json.load(graph_file)
            metadata = graph_data.get('metadata', {})
        except Exception as exc:
            if verbose:
                print(f"    WARNING: unable to read graph metadata for manifest update: {exc}")

        if metadata:
            model_id = metadata.get('model_id') or metadata.get('scan') or config['model']['id']
            source_set = metadata.get('source_set_name') or metadata.get('source_set') or config['model']['source_set']
            slug = metadata.get('slug', seed['slug'])
            node_threshold = metadata.get('node_threshold') or metadata.get('pruning_settings', {}).get('node_threshold') or config.get('graph_generation', {}).get('api_params', {}).get('nodeThreshold', 0.8)
            density_threshold = metadata.get('desired_logit_prob') or metadata.get('density_threshold') or config.get('graph_generation', {}).get('api_params', {}).get('desiredLogitProb', 0.95)
            metadata_url = (
                f"https://www.neuronpedia.org/{model_id}/graph"
                f"?sourceSet={source_set}"
                f"&slug={slug}"
                f"&pruningThreshold={node_threshold}"
                f"&densityThreshold={density_threshold}"
            )

        manifest_path = paths['base'] / 'manifest.json'
        if manifest_path.exists():
            try:
                with open(manifest_path, 'r', encoding='utf-8') as mfile:
                    manifest_data = json.load(mfile)
            except Exception:
                manifest_data = {}
        else:
            manifest_data = {}

        neuronpedia_entry = {
            "display_name": display_name,
            "subgraph_id": result.get('subgraphId') or result.get('subgraph_id'),
            "uploaded_at": datetime.now().isoformat(),
            "supernodes": int(df_grouped['feature_key'].nunique()),
            "pinned_nodes": len(selected_nodes_data.get('node_ids', [])) if selected_nodes_data else None,
            "url": metadata_url,
        }

        manifest_data['neuronpedia'] = {k: v for k, v in neuronpedia_entry.items() if v is not None}

        try:
            with open(manifest_path, 'w', encoding='utf-8') as mfile:
                json.dump(manifest_data, mfile, indent=2, ensure_ascii=False)
            if verbose:
                print(f"    Manifest updated with Neuronpedia reference")
        except Exception as exc:
            print(f"WARNING: Failed to update manifest with Neuronpedia metadata: {exc}")

        return True
    
    except Exception as e:
        print(f"ERROR: Subgraph upload failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def process_grouping_step(config: Dict[str, Any], seed: Dict[str, Any], 
                         paths: Dict[str, Path], verbose: bool = True) -> bool:
    """
    Process node grouping step for a seed.
    
    Steps:
    1. Convert activations_dump.json to CSV
    2. Run scripts/02_node_grouping.py with thresholds from config
    3. Optionally upload subgraph to Neuronpedia
    4. Write outputs to 02 Node Grouping/
    
    Args:
        config: Full experiment config
        seed: Seed config
        paths: Paths dict
        verbose: Print progress
    
    Returns:
        True if successful, False otherwise
    """
    grouping_config = config.get('grouping', {})
    
    if not grouping_config.get('enabled'):
        if verbose:
            print(f"  [SKIP] Grouping disabled in config")
        return True
    
    grouping_dir = paths['grouping_dir']
    grouping_dir.mkdir(parents=True, exist_ok=True)
    
    if verbose:
        print(f"  Running node grouping...")
    
    # Step 1: Convert activations to CSV
    temp_csv = grouping_dir / 'activations_temp.csv'
    
    if not activations_dump_to_csv(paths['activations_dump_json'], temp_csv, verbose=verbose):
        return False
    
    # Step 2: Run 02_node_grouping.py
    # Build command with thresholds from config
    thresholds = grouping_config.get('thresholds', {})
    window = grouping_config.get('window', 7)

    # Build blacklist from legacy string + new token list
    blacklist_tokens: set[str] = set()
    legacy_blacklist = grouping_config.get('blacklist', '')
    if isinstance(legacy_blacklist, str) and legacy_blacklist.strip():
        for token in legacy_blacklist.split(','):
            token_clean = token.strip().lower()
            if token_clean:
                blacklist_tokens.add(token_clean)

    configured_tokens = grouping_config.get('blacklist_tokens', [])
    if isinstance(configured_tokens, str):
        configured_tokens = [configured_tokens]
    if isinstance(configured_tokens, list):
        for token in configured_tokens:
            if not token:
                continue
            token_clean = str(token).strip().lower()
            if token_clean:
                blacklist_tokens.add(token_clean)

    # Always include <bos> so BOS never forms a supernode
    blacklist_tokens.add('<bos>')
    blacklist_arg = ','.join(sorted(blacklist_tokens))
    
    # Path to 02_node_grouping.py
    grouping_script = SCRIPTS_DIR / '02_node_grouping.py'
    
    if not grouping_script.exists():
        print(f"ERROR: 02_node_grouping.py not found at: {grouping_script}")
        return False
    
    # Build command
    cmd = [
        sys.executable,
        str(grouping_script),
        '--input', str(temp_csv),
        '--output', str(paths['grouping_csv']),
        '--json', str(paths['activations_dump_json']),
        '--window', str(window),
    ]
    
    # Add graph if available
    if paths['graph_json'].exists():
        cmd.extend(['--graph', str(paths['graph_json'])])
    
    # Add blacklist if provided
    if blacklist_arg:
        cmd.extend(['--blacklist', blacklist_arg])
    
    # Add threshold overrides
    if 'dict_peak_consistency_min' in thresholds:
        cmd.extend(['--dict-consistency-min', str(thresholds['dict_peak_consistency_min'])])
    if 'sayx_func_vs_sem_min' in thresholds:
        cmd.extend(['--sayx-func-min', str(thresholds['sayx_func_vs_sem_min'])])
    if 'sayx_layer_min' in thresholds:
        cmd.extend(['--sayx-layer-min', str(thresholds['sayx_layer_min'])])
    if 'rel_sparsity_max' in thresholds:
        cmd.extend(['--rel-sparsity-max', str(thresholds['rel_sparsity_max'])])
    
    if verbose:
        cmd.append('--verbose')
    
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=600
        )
        
        if result.returncode != 0:
            print(f"ERROR: Node grouping failed (exit code {result.returncode})")
            print(f"STDOUT:\n{result.stdout}")
            print(f"STDERR:\n{result.stderr}")
            return False
        
        if verbose:
            print(f"  Grouping completed successfully")
            # Print last few lines
            lines = result.stdout.strip().split('\n')
            for line in lines[-5:]:
                print(f"    {line}")
        
        # Clean up temp CSV
        if temp_csv.exists():
            temp_csv.unlink()
        
        # Step 3: Upload to Neuronpedia (if enabled)
        if config.get('steps', {}).get('upload_subgraph', False):
            if not upload_subgraph(config, seed, paths, verbose=verbose):
                print(f"WARNING: Upload failed, but grouping succeeded")
                # Don't fail the whole step if upload fails
        
        return True
    
    except subprocess.TimeoutExpired:
        print(f"ERROR: Node grouping timed out after 10 minutes")
        return False
    
    except Exception as e:
        print(f"ERROR: Failed to run node grouping: {e}")
        import traceback
        traceback.print_exc()
        return False

