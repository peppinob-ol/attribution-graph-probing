"""
Local activations processing for batch experiments.
Supports single-seed, multi-seed (model loaded once), and multi-GPU modes.
"""
import json
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Dict, Any, List, Tuple

from pipeline.loader import plan_batches


def _get_script_path() -> Path:
    return Path(__file__).parent.parent.parent.parent / 'neuronpedia_activations' / 'batch_get_activations.py'


def _base_env(config: Dict[str, Any]) -> dict:
    """Build environment dict shared by single and batch modes."""
    local_config = config['get_activations']['local']
    env = os.environ.copy()
    env['MODEL_ID'] = config['model']['id']
    env['SOURCE_SET'] = config['model']['source_set']
    env['CHUNK_BY_LAYER'] = 'true' if local_config.get('chunk_by_layer', True) else 'false'
    env['INCLUDE_ZERO_ACTIVATIONS'] = 'true' if local_config.get('include_zero', False) else 'false'
    env.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')
    return env


def process_activations_step(config: Dict[str, Any], seed: Dict[str, Any], paths: Dict[str, Path],
                             verbose: bool = True) -> bool:
    """
    Process activations for a single seed (original behavior).
    Spawns batch_get_activations.py as a subprocess.
    Returns True if successful, False otherwise.
    """
    backend = config['get_activations']['backend']
    if backend != 'local':
        print(f"ERROR: Only 'local' backend supported for now (got: {backend})")
        return False

    env = _base_env(config)
    env['PROMPTS_JSON_PATH'] = str(paths['prompts_json'])
    env['FEATURES_JSON_PATH'] = str(paths['selected_features_json'])
    env['OUT_JSON_PATH'] = str(paths['activations_dump_json'])

    if verbose:
        print(f"  Running local activations...")
        print(f"    Model: {env['MODEL_ID']}")
        print(f"    Source: {env['SOURCE_SET']}")
        print(f"    Prompts: {env['PROMPTS_JSON_PATH']}")
        print(f"    Features: {env['FEATURES_JSON_PATH']}")
        print(f"    Output: {env['OUT_JSON_PATH']}")

    script_path = _get_script_path()
    if not script_path.exists():
        print(f"ERROR: batch_get_activations.py not found at: {script_path}")
        return False

    try:
        result = subprocess.run(
            ['python3', str(script_path)],
            env=env, capture_output=True, text=True, timeout=3600,
        )
        if result.returncode != 0:
            print(f"ERROR: batch_get_activations.py failed with code {result.returncode}")
            print(f"STDOUT:\n{result.stdout}")
            print(f"STDERR:\n{result.stderr}")
            return False
        if verbose:
            print(f"  Activations completed successfully")
            for line in result.stdout.strip().split('\n')[-5:]:
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


def _run_one_batch(
    config: Dict[str, Any],
    batch_states: List[Dict[str, Any]],
    gpu_id: int,
    manifest_path: Path,
    script_path: Path,
    verbose: bool,
) -> Dict[str, bool]:
    """
    Run batch_get_activations.py for one batch of seeds on a single GPU.
    Writes a per-batch manifest and sets CUDA_VISIBLE_DEVICES.
    Returns dict slug -> success for this batch.
    """
    manifest = []
    for state in batch_states:
        paths = state['paths']
        manifest.append({
            'slug': state['seed']['slug'],
            'prompts_json': str(paths['prompts_json']),
            'features_json': str(paths['selected_features_json']),
            'output_json': str(paths['activations_dump_json']),
        })
    with open(manifest_path, 'w', encoding='utf-8') as f:
        json.dump(manifest, f, indent=2)

    env = _base_env(config)
    env['SEEDS_MANIFEST_PATH'] = str(manifest_path)
    env['PERSIST_SAE_CACHE'] = 'true'
    env['CUDA_VISIBLE_DEVICES'] = str(gpu_id)

    timeout = 3600 * len(batch_states)
    try:
        result = subprocess.run(
            ['python3', str(script_path)],
            env=env, capture_output=False, text=True, timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        if verbose:
            print(f"  [GPU {gpu_id}] Batch timed out")
        return {s['seed']['slug']: False for s in batch_states}
    except Exception as e:
        if verbose:
            print(f"  [GPU {gpu_id}] Batch failed: {e}")
        return {s['seed']['slug']: False for s in batch_states}

    status_path = str(manifest_path).replace('.json', '_status.json')
    if os.path.exists(status_path):
        with open(status_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    success = result.returncode == 0
    return {s['seed']['slug']: success for s in batch_states}


def process_activations_batch_local(
    config: Dict[str, Any],
    seed_states: List[Dict[str, Any]],
    verbose: bool = True,
) -> Dict[str, bool]:
    """
    Process activations for multiple seeds. Uses a single subprocess when
    only one GPU is configured; otherwise shards seeds across GPU-pinned
    subprocesses (one batch per worker, round-robin GPU assignment).
    SAE cache is persisted on disk to avoid re-downloading transcoders.

    Args:
        config: Full experiment config
        seed_states: List of state dicts (must have 'seed' and 'paths' keys)
        verbose: Print progress

    Returns:
        Dict mapping slug -> success bool
    """
    backend = config['get_activations']['backend']
    if backend != 'local':
        print(f"ERROR: Only 'local' backend supported (got: {backend})")
        return {s['seed']['slug']: False for s in seed_states}

    script_path = _get_script_path()
    if not script_path.exists():
        print(f"ERROR: batch_get_activations.py not found at: {script_path}")
        return {s['seed']['slug']: False for s in seed_states}

    local_cfg = config['get_activations'].get('local', {})
    gpus = local_cfg.get('gpus')
    if gpus is None:
        gpus = [0]
    if not isinstance(gpus, list):
        gpus = [0]
    gpus = [int(g) for g in gpus if isinstance(g, (int, str)) and str(g).isdigit()]
    if not gpus:
        gpus = [0]

    batch_size = local_cfg.get('batch_size')
    if batch_size is None or not isinstance(batch_size, int) or batch_size <= 0:
        batch_size = max(1, (len(seed_states) + len(gpus) - 1) // len(gpus))

    outputs_root = Path(config['paths']['outputs_root'])
    outputs_root.mkdir(parents=True, exist_ok=True)

    # Single GPU or single batch: one subprocess, no executor
    if len(gpus) <= 1 or len(seed_states) <= 1:
        manifest_path = outputs_root / '_activations_manifest.json'
        env = _base_env(config)
        env['SEEDS_MANIFEST_PATH'] = str(manifest_path)
        env['PERSIST_SAE_CACHE'] = 'true'
        if gpus:
            env['CUDA_VISIBLE_DEVICES'] = str(gpus[0])
        manifest = []
        for state in seed_states:
            paths = state['paths']
            manifest.append({
                'slug': state['seed']['slug'],
                'prompts_json': str(paths['prompts_json']),
                'features_json': str(paths['selected_features_json']),
                'output_json': str(paths['activations_dump_json']),
            })
        with open(manifest_path, 'w', encoding='utf-8') as f:
            json.dump(manifest, f, indent=2)
        if verbose:
            print(f"  Manifest: {manifest_path} ({len(manifest)} seed(s))")
        timeout = 3600 * len(seed_states)
        try:
            result = subprocess.run(
                ['python3', str(script_path)],
                env=env, capture_output=False, text=True, timeout=timeout,
            )
        except subprocess.TimeoutExpired:
            print(f"ERROR: Batch activations timed out after {timeout}s")
            return {s['seed']['slug']: False for s in seed_states}
        except Exception as e:
            print(f"ERROR: Batch activations failed: {e}")
            return {s['seed']['slug']: False for s in seed_states}
        status_path = str(manifest_path).replace('.json', '_status.json')
        if os.path.exists(status_path):
            with open(status_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        success = result.returncode == 0
        return {s['seed']['slug']: success for s in seed_states}

    # Multi-GPU: split into batches, run one subprocess per batch pinned to a GPU
    batches = plan_batches(seed_states, batch_size)
    if verbose:
        print(f"  Local multi-GPU: {len(batches)} batch(es), GPUs {gpus} (batch_size={batch_size})")

    merged: Dict[str, bool] = {}
    with ThreadPoolExecutor(max_workers=len(gpus)) as executor:
        futures = {}
        for batch_index, batch_states in enumerate(batches):
            gpu_id = gpus[batch_index % len(gpus)]
            manifest_path = outputs_root / f'_activations_manifest_gpu{gpu_id}_{batch_index}.json'
            future = executor.submit(
                _run_one_batch,
                config,
                batch_states,
                gpu_id,
                manifest_path,
                script_path,
                verbose,
            )
            futures[future] = (gpu_id, batch_index)
        for future in as_completed(futures):
            gpu_id, batch_index = futures[future]
            try:
                batch_result = future.result()
                merged.update(batch_result)
            except Exception as e:
                if verbose:
                    print(f"  [GPU {gpu_id}] batch {batch_index} raised: {e}")
                for state in batches[batch_index]:
                    merged[state['seed']['slug']] = False
    return merged
