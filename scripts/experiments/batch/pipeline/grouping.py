"""
Node grouping for batch experiments.
Converts activations_dump.json to CSV and runs 02_node_grouping.py.
"""
import json
import csv
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, List


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
                
                # Find peak
                peak_val = max(values)
                peak_idx = values.index(peak_val)
                peak_token = tokens[peak_idx] if peak_idx < len(tokens) else ""
                
                # Calculate sparsity ratio: (peak - mean) / peak
                mean_val = sum(values) / len(values)
                sparsity_ratio = (peak_val - mean_val) / peak_val if peak_val > 0 else 0.0
                
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


def process_grouping_step(config: Dict[str, Any], seed: Dict[str, Any], 
                         paths: Dict[str, Path], verbose: bool = True) -> bool:
    """
    Process node grouping step for a seed.
    
    Steps:
    1. Convert activations_dump.json to CSV
    2. Run scripts/02_node_grouping.py with thresholds from config
    3. Write outputs to 02 Node Grouping/
    
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
    blacklist = grouping_config.get('blacklist', '')
    
    # Path to 02_node_grouping.py
    parent_dir = Path(__file__).parent.parent.parent.parent
    grouping_script = parent_dir / 'scripts' / '02_node_grouping.py'
    
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
    if blacklist:
        cmd.extend(['--blacklist', blacklist])
    
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
        
        return True
    
    except subprocess.TimeoutExpired:
        print(f"ERROR: Node grouping timed out after 10 minutes")
        return False
    
    except Exception as e:
        print(f"ERROR: Failed to run node grouping: {e}")
        import traceback
        traceback.print_exc()
        return False

