"""
Remote steering helper.

Mirrors remote activation execution but runs scripts/neuronpedia_steering/batch_steering.py
on the GPU node via SSH.
"""
from pathlib import Path
from typing import Any, Dict, Tuple

from .remote import RemoteExecutor


def process_remote_steering_step(
    config: Dict[str, Any],
    seed: Dict[str, Any],
    paths: Dict[str, Path],
    verbose: bool = True,
) -> Tuple[bool, Dict[str, Any]]:
    """
    Execute the steering batch for a single seed on the remote GPU node.

    Args:
        config: Full experiment config (must have compute.remote + steering sections).
        seed: Seed config dict (needs slug, etc.).
        paths: Dict of local Path objects with keys:
               - 'prompts_json'
               - 'steering_features_json'
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
    success, gpu_id, remote_log = executor.run_remote_steering(
        config, seed, paths, verbose=verbose
    )

    metadata = {
        "remote_host": f"{executor.user}@{executor.host}",
        "gpu_id": gpu_id,
        "remote_log": remote_log,
        "base_dir": executor.base_dir,
    }
    return success, metadata


