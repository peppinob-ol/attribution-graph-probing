"""
Local activations processing for batch experiments.
Runs batch_get_activations.py with proper env configuration.
"""
import os
import subprocess
from pathlib import Path
from typing import Dict, Any


def process_activations_step(config: Dict[str, Any], seed: Dict[str, Any], paths: Dict[str, Path],
                             verbose: bool = True) -> bool:
    """
    Process activations step for a seed using local backend.
    
    Sets up environment and calls batch_get_activations.py.
    For now, runs locally. Future: SSH to remote node.
    
    Returns True if successful, False otherwise.
    """
    backend = config['get_activations']['backend']
    
    if backend != 'local':
        print(f"ERROR: Only 'local' backend supported for now (got: {backend})")
        return False
    
    local_config = config['get_activations']['local']
    
    # Prepare environment
    env = os.environ.copy()
    env['MODEL_ID'] = config['model']['id']
    env['SOURCE_SET'] = config['model']['source_set']
    env['PROMPTS_JSON_PATH'] = str(paths['prompts_json'])
    env['FEATURES_JSON_PATH'] = str(paths['selected_features_json'])
    env['OUT_JSON_PATH'] = str(paths['activations_dump_json'])
    env['CHUNK_BY_LAYER'] = 'true' if local_config.get('chunk_by_layer', True) else 'false'
    env['INCLUDE_ZERO_ACTIVATIONS'] = 'true' if local_config.get('include_zero', False) else 'false'
    
    # Optional: set NP_WORKDIR if running remotely
    # For now, use default (will clone to /content or current dir)
    
    if verbose:
        print(f"  Running local activations...")
        print(f"    Model: {env['MODEL_ID']}")
        print(f"    Source: {env['SOURCE_SET']}")
        print(f"    Prompts: {env['PROMPTS_JSON_PATH']}")
        print(f"    Features: {env['FEATURES_JSON_PATH']}")
        print(f"    Output: {env['OUT_JSON_PATH']}")
    
    # Path to batch_get_activations.py
    script_path = Path(__file__).parent.parent.parent.parent / 'neuronpedia activations' / 'batch_get_activations.py'
    
    if not script_path.exists():
        print(f"ERROR: batch_get_activations.py not found at: {script_path}")
        return False
    
    # Run the script
    try:
        result = subprocess.run(
            ['python3', str(script_path)],
            env=env,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )
        
        if result.returncode != 0:
            print(f"ERROR: batch_get_activations.py failed with code {result.returncode}")
            print(f"STDOUT:\n{result.stdout}")
            print(f"STDERR:\n{result.stderr}")
            return False
        
        if verbose:
            print(f"  Activations completed successfully")
            # Print last few lines of output
            lines = result.stdout.strip().split('\n')
            for line in lines[-5:]:
                print(f"    {line}")
        
        return True
    
    except subprocess.TimeoutExpired:
        print(f"ERROR: batch_get_activations.py timed out after 1 hour")
        return False
    
    except Exception as e:
        print(f"ERROR: Failed to run batch_get_activations.py: {e}")
        import traceback
        traceback.print_exc()
        return False

