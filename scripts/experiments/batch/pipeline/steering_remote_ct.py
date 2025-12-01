"""
Remote Circuit Tracer steering helper.

Runs scripts/neuronpedia_steering/batch_steering_ct.py on the GPU node via SSH.
Uses circuit_tracer's ReplacementModel.feature_intervention_generate().
"""
from pathlib import Path
from typing import Any, Dict, Tuple
import time

from .remote import RemoteExecutor


def build_remote_ct_steering_env(
    remote_executor: RemoteExecutor,
    config: Dict[str, Any],
    remote_paths: Dict[str, str],
    steering_cfg: Dict[str, Any],
) -> Dict[str, str]:
    """
    Build environment variables dict for remote CT steering run.
    
    CT steering uses different env vars than SAE-based steering:
    - MODEL_ID: HuggingFace model ID
    - TRANSCODER_SET: CLT transcoder set name
    - Temperature, tokens, freq_penalty as before
    - FREEZE_ATTENTION: for constrained patching
    """
    model_config = config.get("model", {})
    
    env = {
        "NP_WORKDIR": remote_executor.base_dir,
        "MODEL_ID": model_config.get("id", "google/gemma-2-2b"),
        # For CT we use transcoder_set not SOURCE_SET
        "TRANSCODER_SET": steering_cfg.get("transcoder_set", "gemma"),
        "PROMPTS_JSON_PATH": remote_paths["prompts_json"],
        "FEATURES_JSON_PATH": remote_paths["features_json"],
        "OUT_JSON_PATH": remote_paths["steering_dump_json"],
        "STEER_TEMPERATURE": str(steering_cfg.get("temperature", 0.5)),
        "STEER_N_TOKENS": str(steering_cfg.get("n_tokens", 16)),
        "STEER_FREQ_PENALTY": str(steering_cfg.get("freq_penalty", 2.0)),
        "STEER_SEED": str(steering_cfg.get("seed", 42)),
        "TOP_K": str(steering_cfg.get("top_k", 5)),
        "FREEZE_ATTENTION": "true" if steering_cfg.get("freeze_attention", False) else "false",
        "PYTHONIOENCODING": "utf-8",
    }
    
    # CUDA memory config
    env.setdefault(
        "PYTORCH_CUDA_ALLOC_CONF",
        steering_cfg.get("cuda_alloc_conf", "expandable_segments:True"),
    )
    
    return env


def run_remote_ct_steering(
    executor: RemoteExecutor,
    config: Dict[str, Any],
    seed: Dict[str, Any],
    local_paths: Dict[str, Path],
    verbose: bool = True,
) -> Tuple[bool, int, str]:
    """
    Run batch_steering_ct.py on the remote node for a given seed.
    
    Args:
        executor: RemoteExecutor instance
        config: Full experiment config
        seed: Seed config dict (needs slug)
        local_paths: Dict with keys:
            - 'prompts_json'
            - 'steering_features_json' (CT format features)
            - 'steering_dump_json' (output destination)
            - 'base' (output directory base)
        verbose: Print progress
    
    Returns:
        Tuple of (success, gpu_id, remote_log_path)
    """
    steering_cfg = config.get("ct_steering", config.get("steering", {}))
    slug = seed.get("slug", "ct_steer")
    
    if verbose:
        print(f"  [REMOTE-CT] Setting up remote CT steering for {slug}...")
    
    # Create remote directories
    remote_exp_dir = f"{executor.base_dir}/ct_steering/{slug}"
    remote_logs_dir = executor.logs_dir
    cmd = f'mkdir -p "{remote_exp_dir}" "{remote_logs_dir}" "{executor.base_dir}/.locks"'
    rc, _, stderr = executor.ssh_run(cmd, timeout=10, capture_output=False)
    if rc != 0:
        print(f"ERROR: Failed to create remote directories for CT steering: {stderr}")
        return False, -1, ""
    
    # Upload input files
    remote_prompts = f"{remote_exp_dir}/prompts.json"
    remote_features = f"{remote_exp_dir}/features.json"
    
    if not executor.rsync_up(str(local_paths["prompts_json"]), remote_prompts, verbose=False):
        print("ERROR: Failed to upload prompts.json")
        return False, -1, ""
    if not executor.rsync_up(str(local_paths["steering_features_json"]), remote_features, verbose=False):
        print("ERROR: Failed to upload features.json")
        return False, -1, ""
    
    # Find and lock a free GPU with retry logic for parallel execution
    # With 8 GPUs and many parallel workers, need enough retries to wait for a free GPU
    max_gpu_retries = 30  # ~2 minutes of retries at worst case
    gpu_id = None
    lock_acquired = False
    
    for retry in range(max_gpu_retries):
        if verbose and retry > 0 and retry % 5 == 0:
            print(f"  [REMOTE-CT] Retry {retry}/{max_gpu_retries} - waiting for GPU...")
        
        gpu_id = executor.get_free_gpu()
        if gpu_id is None:
            # No GPU appears free, wait and retry
            time.sleep(3 + (retry % 5))  # 3-7 second waits
            continue
        
        # Try to acquire lock
        lock_acquired = executor.acquire_gpu_lock(gpu_id)
        if lock_acquired:
            if verbose:
                print(f"  [REMOTE-CT] Using GPU {gpu_id} (locked)")
            break
        else:
            # Another worker got this GPU first, short wait then retry
            time.sleep(1 + (retry % 3))  # 1-3 second waits
    
    if not lock_acquired or gpu_id is None:
        print(f"ERROR: Could not acquire any GPU after {max_gpu_retries} retries (~2 min)")
        return False, -1, ""
    
    # Build paths and environment
    remote_out = f"{remote_exp_dir}/steering_dump.json"
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    remote_log = f"{remote_logs_dir}/{slug}_{timestamp}_ct_steer.log"
    
    remote_paths_dict = {
        "prompts_json": remote_prompts,
        "features_json": remote_features,
        "steering_dump_json": remote_out,
    }
    env_vars = build_remote_ct_steering_env(
        executor, config, remote_paths_dict, steering_cfg
    )
    
    # Build and upload script
    script_lines = [
        "#!/bin/bash",
        "set -e",
        executor.env_activate_cmd,
        f"cd {executor.repo_dir}",
    ]
    for k, v in env_vars.items():
        script_lines.append(f'export {k}="{v}"')
    
    # CT steering uses batch_steering_ct.py
    script_lines.append(
        f"CUDA_VISIBLE_DEVICES={gpu_id} python scripts/neuronpedia_steering/batch_steering_ct.py "
        f"2>&1 | tee {remote_log}"
    )
    script_content = "\n".join(script_lines) + "\n"
    remote_script = f"{remote_exp_dir}/run_ct_steering.sh"
    
    import tempfile
    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".sh", delete=False, encoding="utf-8", newline="\n"
    ) as tf:
        tf.write(script_content)
        temp_script_path = tf.name
    
    if not executor.rsync_up(temp_script_path, remote_script, verbose=False):
        Path(temp_script_path).unlink(missing_ok=True)
        if lock_acquired:
            executor.release_gpu_lock(gpu_id)
        return False, -1, ""
    Path(temp_script_path).unlink(missing_ok=True)
    
    # Execute
    full_cmd = f"chmod +x {remote_script} && {remote_script}"
    if verbose:
        print(f"  [REMOTE-CT] Running CT steering script on GPU {gpu_id}...")
        print(f"    Model: {env_vars['MODEL_ID']}")
        print(f"    Transcoder: {env_vars['TRANSCODER_SET']}")
        print(f"    Freeze attention: {env_vars['FREEZE_ATTENTION']}")
    
    rc, stdout, stderr = executor.ssh_run(full_cmd, timeout=7200, capture_output=True)
    
    # Release lock
    if lock_acquired:
        executor.release_gpu_lock(gpu_id)
    
    if rc != 0:
        print(f"ERROR: Remote CT steering failed (exit code {rc})")
        if verbose:
            print(f"STDERR:\n{stderr}")
        return False, gpu_id, remote_log
    
    # Download results
    if verbose:
        print("  [REMOTE-CT] Downloading CT steering results...")
    if not executor.rsync_down(remote_out, str(local_paths["steering_dump_json"]), verbose=False):
        print("ERROR: Failed to download steering_dump.json")
        return False, gpu_id, remote_log
    
    # Download log
    local_log_path = local_paths["base"] / f"remote_ct_steer_{timestamp}.log"
    executor.rsync_down(remote_log, str(local_log_path), verbose=False)
    
    if verbose:
        print("  [REMOTE-CT] CT Steering completed successfully")
        print(f"    GPU: {gpu_id}")
        print(f"    Remote log: {remote_log}")
        print(f"    Local log: {local_log_path}")
    
    return True, gpu_id, remote_log


def process_remote_ct_steering_step(
    config: Dict[str, Any],
    seed: Dict[str, Any],
    paths: Dict[str, Path],
    verbose: bool = True,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Execute Circuit Tracer steering for a single seed on the remote GPU node.
    
    Args:
        config: Full experiment config (must have compute.remote + ct_steering sections).
        seed: Seed config dict (needs slug).
        paths: Dict of local Path objects with keys:
            - 'prompts_json'
            - 'steering_features_json' (CT format)
            - 'steering_dump_json'
            - 'base' (output directory base)
        verbose: Print progress.
    
    Returns:
        (success, metadata) tuple.
    """
    remote_cfg = config.get("compute", {}).get("remote", {})
    if not remote_cfg.get("enabled"):
        print("ERROR: Remote execution not enabled in config")
        return False, {}
    
    executor = RemoteExecutor(config)
    success, gpu_id, remote_log = run_remote_ct_steering(
        executor, config, seed, paths, verbose=verbose
    )
    
    metadata = {
        "remote_host": f"{executor.user}@{executor.host}",
        "gpu_id": gpu_id,
        "remote_log": remote_log,
        "base_dir": executor.base_dir,
        "steering_type": "circuit_tracer",
    }
    return success, metadata

