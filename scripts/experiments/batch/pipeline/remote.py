"""
Remote execution module for running activations on GPU nodes via SSH.
Handles rsync, GPU selection, locking, and remote command execution.
"""
import json
import os
import shutil
import subprocess
import tempfile
import time
import traceback
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List, Set


class RemoteExecutor:
    """Handles SSH/rsync operations for remote GPU node."""
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize remote executor from config.
        
        Args:
            config: Full experiment config with compute.remote section
        """
        self.remote_config = config.get('compute', {}).get('remote', {})
        
        if not self.remote_config.get('enabled'):
            raise ValueError("Remote execution not enabled in config")
        
        host_value = self.remote_config.get('host')
        host_env = self.remote_config.get('host_env')
        if host_env:
            env_value = os.environ.get(host_env)
            if not env_value:
                raise ValueError(f"Environment variable '{host_env}' not set for compute.remote.host_env")
            host_value = env_value
        if not host_value:
            raise ValueError("compute.remote requires host or host_env")
        self.host = host_value
        self.user = self.remote_config['user']
        self.base_dir = self.remote_config['base_dir']
        self.repo_dir = self.remote_config['repo_dir']
        self.logs_dir = self.remote_config['logs_dir']
        self.env_activate_cmd = self.remote_config['env_activate_cmd']
        self.use_gpu_count = self.remote_config.get('use_gpu_count', 1)
        self.gpu_selection = self.remote_config.get('gpu_selection', 'auto')
        self.persist_sae_cache = self.remote_config.get('persist_sae_cache', False)
        
        # Get password from env if specified
        password_env = self.remote_config.get('password_env')
        self.password = os.environ.get(password_env) if password_env else None
        
        self.ssh_target = f"{self.user}@{self.host}"
    
    def ssh_run(self, cmd: str, timeout: int = 3600, capture_output: bool = True) -> Tuple[int, str, str]:
        """
        Run command on remote host via SSH.
        
        Args:
            cmd: Command to run (will be executed via bash -c)
            timeout: Timeout in seconds
            capture_output: If True, capture stdout/stderr
        
        Returns:
            Tuple of (returncode, stdout, stderr)
        """
        # On Windows, use native ssh (no sshpass support)
        # Assumes SSH key-based auth is set up
        # Use shell=True on Windows for proper command handling
        import platform
        
        # Use list form (works on all platforms)
        # Pass command as single argument to SSH
        ssh_cmd = ['ssh', '-o', 'StrictHostKeyChecking=no', self.ssh_target, cmd]
        
        try:
            result = subprocess.run(
                ssh_cmd,
                stdin=subprocess.DEVNULL,  # Prevent hang
                capture_output=capture_output,
                text=True,
                encoding='utf-8',
                errors='replace',
                timeout=timeout
            )
            return result.returncode, result.stdout or "", result.stderr or ""
        
        except subprocess.TimeoutExpired:
            return -1, "", f"Command timed out after {timeout}s"
        
        except Exception as e:
            return -1, "", str(e)
    
    def rsync_up(self, local_path: str, remote_path: str, verbose: bool = False) -> bool:
        """
        Upload file/directory to remote host via rsync or scp.
        
        Args:
            local_path: Local file or directory path
            remote_path: Remote destination path
            verbose: Print rsync output
        
        Returns:
            True if successful, False otherwise
        """
        local_p = Path(local_path)
        if not local_p.exists():
            print(f"ERROR: Local path does not exist: {local_path}")
            return False
        
        # Try rsync first (faster), fall back to scp
        remote_target = f"{self.ssh_target}:{remote_path}"
        
        # Use scp (more widely available than rsync on Windows)
        # On Windows, assume SSH key-based auth (no sshpass)
        scp_cmd = ['scp', '-o', 'StrictHostKeyChecking=no', '-r', str(local_path), remote_target]
        
        try:
            result = subprocess.run(
                scp_cmd,
                capture_output=not verbose,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                print(f"ERROR: Upload failed: {result.stderr if not verbose else ''}")
                return False
            
            return True
        
        except Exception as e:
            print(f"ERROR: Upload exception: {e}")
            return False
    
    def rsync_down(self, remote_path: str, local_path: str, verbose: bool = False) -> bool:
        """
        Download file/directory from remote host via rsync or scp.
        
        Args:
            remote_path: Remote file or directory path
            local_path: Local destination path
            verbose: Print output
        
        Returns:
            True if successful, False otherwise
        """
        # Ensure local parent directory exists
        Path(local_path).parent.mkdir(parents=True, exist_ok=True)
        
        remote_target = f"{self.ssh_target}:{remote_path}"
        
        # On Windows, assume SSH key-based auth (no sshpass)
        scp_cmd = ['scp', '-o', 'StrictHostKeyChecking=no', '-r', remote_target, str(local_path)]
        
        try:
            result = subprocess.run(
                scp_cmd,
                capture_output=not verbose,
                text=True,
                timeout=300
            )
            
            if result.returncode != 0:
                print(f"ERROR: Download failed: {result.stderr if not verbose else ''}")
                return False
            
            return True
        
        except Exception as e:
            print(f"ERROR: Download exception: {e}")
            return False
    
    def _get_busy_gpu_uuids(self) -> Optional[Set[str]]:
        """
        Return set of GPU UUIDs that currently have compute processes.
        """
        cmd = "nvidia-smi --query-compute-apps=gpu_uuid --format=csv,noheader"
        rc, stdout, stderr = self.ssh_run(cmd, timeout=10)

        if rc != 0:
            # Some older drivers don't support this query; fall back to heuristics
            if stderr.strip():
                print(f"WARNING: Failed to query compute apps via nvidia-smi: {stderr.strip()}")
            return None

        busy: Set[str] = set()
        for line in stdout.strip().splitlines():
            entry = line.strip()
            if not entry or entry.lower().startswith("no running"):
                continue
            parts = [p.strip() for p in entry.split(",")]
            if not parts:
                continue
            uuid = parts[0]
            if uuid:
                busy.add(uuid)
        return busy

    def get_free_gpu(self) -> Optional[int]:
        """
        Find a free GPU on the remote node.
        
        Uses nvidia-smi to check memory usage and running processes.
        Returns GPU index if found, None otherwise.
        """
        # Query GPU status
        cmd = 'nvidia-smi --query-gpu=index,uuid,memory.used,utilization.gpu --format=csv,noheader,nounits'
        rc, stdout, stderr = self.ssh_run(cmd, timeout=10)
        
        if rc != 0:
            warning = stderr.strip() or "nvidia-smi unavailable"
            print(f"WARNING: Failed to query nvidia-smi: {warning}")
            return self._fallback_gpu_index()

        gpu_rows = []
        for line in stdout.strip().split('\n'):
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 4:
                try:
                    gpu_idx = int(parts[0])
                    uuid = parts[1]
                    mem_used = int(parts[2])
                    util = int(parts[3])
                except ValueError:
                    continue
                gpu_rows.append(
                    {
                        "index": gpu_idx,
                        "uuid": uuid,
                        "memory": mem_used,
                        "util": util,
                    }
                )

        if not gpu_rows:
            print("ERROR: Unable to parse nvidia-smi output for GPU selection")
            return None

        idle_mem_threshold = int(self.remote_config.get("gpu_idle_memory_mb", 2000))
        warn_mem_threshold = int(self.remote_config.get("gpu_warn_memory_mb", 4000))
        
        # Manual override: allow user to pin candidate GPUs via compute.remote.gpus
        # We only check VRAM here (ignoring utilization and compute-apps) because on
        # some shared nodes utilization and compute-apps can be misleading or stale.
        manual_gpus = self.remote_config.get("gpus")
        if isinstance(manual_gpus, list) and manual_gpus:
            try:
                manual_indices = {int(g) for g in manual_gpus}
            except Exception:
                manual_indices = set()
            if manual_indices:
                candidates = [
                    row
                    for row in gpu_rows
                    if row["index"] in manual_indices and row["memory"] < 4000
                ]
                if candidates:
                    candidates.sort(key=lambda row: (row["memory"], row["index"]))
                    chosen = candidates[0]["index"]
                    print(f"  [REMOTE] Using manually configured GPU {chosen}")
                    return chosen

        busy_uuids = self._get_busy_gpu_uuids()
        busy_uuids = busy_uuids if busy_uuids is not None else set()
        
        free_candidates: List[Dict[str, int]] = []
        ghost_candidates: List[Dict[str, int]] = []
        nonbusy_candidates: List[Dict[str, int]] = []
        
        for row in gpu_rows:
            is_busy = row["uuid"] in busy_uuids
            if not is_busy:
                nonbusy_candidates.append(row)
            if row["memory"] <= idle_mem_threshold:
                if not is_busy:
                    free_candidates.append(row)
                else:
                    ghost_candidates.append(row)
        
        def _choose(candidate_rows: List[Dict[str, int]], note: Optional[str] = None) -> int:
            candidate_rows.sort(key=lambda r: (r["memory"], r["index"]))
            chosen_row = candidate_rows[0]
            if note:
                print(note.format(idx=chosen_row["index"], mem=chosen_row["memory"]))
            return chosen_row["index"]
        
        if free_candidates:
            return _choose(free_candidates)
        
        if ghost_candidates:
            return _choose(
                ghost_candidates,
                note=(
                    "  [REMOTE] Treating GPU {idx} as free despite compute-app residue "
                    "(memory {mem} MB < idle threshold)"
                ),
            )
        
        if nonbusy_candidates:
            low_mem = [row for row in nonbusy_candidates if row["memory"] <= warn_mem_threshold]
            if low_mem:
                return _choose(
                    low_mem,
                    note=(
                        "  [REMOTE] No fully idle GPUs; using lowest-memory GPU {idx} "
                        "(memory {mem} MB)"
                    ),
                )
            return _choose(
                nonbusy_candidates,
                note=(
                    "  [REMOTE] All GPUs above warning threshold; falling back to GPU {idx} "
                    "(memory {mem} MB)"
                ),
            )
        
        # Last resort: pick the lowest-memory GPU overall, even if busy, but warn loudly.
        gpu_rows.sort(key=lambda r: (r["memory"], r["index"]))
        chosen_row = gpu_rows[0]
        print(
            "WARNING: All GPUs report active compute processes; falling back to GPU "
            f"{chosen_row['index']} (memory {chosen_row['memory']} MB)."
        )
        return chosen_row["index"]

    def _fallback_gpu_index(self) -> Optional[int]:
        """
        Return a best-effort GPU index when nvidia-smi is unavailable.
        Prefers user-specified compute.remote.gpus list, otherwise GPU 0.
        """
        manual_gpus = self.remote_config.get("gpus")
        if isinstance(manual_gpus, list) and manual_gpus:
            try:
                fallback = int(manual_gpus[0])
                print(f"  [REMOTE] Falling back to configured GPU {fallback}")
                return fallback
            except (ValueError, TypeError):
                pass
        print("  [REMOTE] Falling back to GPU 0 (nvidia-smi unavailable)")
        return 0
    
    def acquire_gpu_lock(self, gpu_id: int) -> bool:
        """
        Acquire lock for a GPU by creating a lock directory.
        
        Args:
            gpu_id: GPU index to lock
        
        Returns:
            True if lock acquired, False if already locked
        """
        lock_dir = f"{self.base_dir}/.locks/gpu{gpu_id}"
        cmd = f"mkdir {lock_dir} 2>/dev/null && echo 'locked' || echo 'failed'"
        
        rc, stdout, stderr = self.ssh_run(cmd, timeout=5)
        
        return 'locked' in stdout
    
    def release_gpu_lock(self, gpu_id: int) -> bool:
        """
        Release GPU lock by removing lock directory.
        
        Args:
            gpu_id: GPU index to unlock
        
        Returns:
            True if successful
        """
        lock_dir = f"{self.base_dir}/.locks/gpu{gpu_id}"
        cmd = f"rmdir {lock_dir} 2>/dev/null || true"
        
        self.ssh_run(cmd, timeout=5)
        return True
    
    def build_remote_env(self, config: Dict[str, Any], seed: Dict[str, Any], 
                        remote_paths: Dict[str, str]) -> Dict[str, str]:
        """
        Build environment variables dict for remote activation run.
        
        Args:
            config: Full experiment config
            seed: Seed config
            remote_paths: Dict with remote file paths
        
        Returns:
            Dict of env var name -> value
        """
        model_config = config['model']
        act_config = config['get_activations']['local']
        
        env = {
            'NP_WORKDIR': self.base_dir,
            'MODEL_ID': model_config['id'],
            'SOURCE_SET': model_config['source_set'],
            'PROMPTS_JSON_PATH': remote_paths['prompts_json'],
            'FEATURES_JSON_PATH': remote_paths['features_json'],
            'OUT_JSON_PATH': remote_paths['activations_dump_json'],
            'CHUNK_BY_LAYER': 'true' if act_config.get('chunk_by_layer', True) else 'false',
            'INCLUDE_ZERO_ACTIVATIONS': 'true' if act_config.get('include_zero', False) else 'false',
        }
        
        # Force CHUNK_BY_LAYER=true for clt-hp
        if model_config['source_set'] == 'clt-hp':
            env['CHUNK_BY_LAYER'] = 'true'
        
        return env

    def build_remote_steering_env(
        self,
        config: Dict[str, Any],
        seed: Dict[str, Any],
        remote_paths: Dict[str, str],
        steering_cfg: Dict[str, Any],
    ) -> Dict[str, str]:
        """
        Build environment variables dict for remote steering run.
        """
        model_config = config["model"]
        env = {
            "NP_WORKDIR": self.base_dir,
            "MODEL_ID": model_config["id"],
            "SOURCE_SET": model_config["source_set"],
            "PROMPTS_JSON_PATH": remote_paths["prompts_json"],
            "FEATURES_JSON_PATH": remote_paths["features_json"],
            "OUT_JSON_PATH": remote_paths["steering_dump_json"],
            "STEER_TEMPERATURE": str(steering_cfg.get("temperature", 0.5)),
            "STEER_N_TOKENS": str(steering_cfg.get("n_tokens", 16)),
            "STEER_FREQ_PENALTY": str(steering_cfg.get("freq_penalty", 2.0)),
            "STEER_SEED": str(steering_cfg.get("seed", 42)),
            "STEER_STRENGTH_MULTIPLIER": str(
                steering_cfg.get("strength_multiplier", 1.0)
            ),
            "STEER_METHOD": steering_cfg.get(
                "steer_method", "ORTHOGONAL_DECOMP"
            ),
            "STEER_N_LOGPROBS": str(steering_cfg.get("n_logprobs", 5)),
            "STEER_NORMALIZE": "true"
            if steering_cfg.get("normalize", False)
            else "false",
            "PYTHONIOENCODING": "utf-8",
        }
        steer_device = steering_cfg.get("device")
        if steer_device in ("cpu", "cuda"):
            env["STEER_DEVICE"] = steer_device
        env.setdefault(
            "PYTORCH_CUDA_ALLOC_CONF",
            steering_cfg.get("cuda_alloc_conf", "expandable_segments:True"),
        )
        return env
    
    def run_remote_activation(self, config: Dict[str, Any], seed: Dict[str, Any], 
                             local_paths: Dict[str, Path], verbose: bool = True) -> Tuple[bool, Optional[int], str]:
        """
        Run activation measurement on remote GPU node.
        
        Steps:
        1. Create remote directories
        2. Upload prompts.json and features.json
        3. Find free GPU and acquire lock
        4. Run batch_get_activations.py remotely
        5. Download activations_dump.json
        6. Release GPU lock
        
        Args:
            config: Full experiment config
            seed: Seed config
            local_paths: Dict with local Path objects
            verbose: Print progress
        
        Returns:
            Tuple of (success: bool, gpu_id: Optional[int], log_path: str)
        """
        slug = seed['slug']
        
        if verbose:
            print(f"  [REMOTE] Setting up remote execution for {slug}...")
        
        # Step 1: Create remote directories
        remote_exp_dir = f"{self.base_dir}/experiments/{slug}"
        remote_logs_dir = self.logs_dir
        
        cmd = f'mkdir -p "{remote_exp_dir}" "{remote_logs_dir}" "{self.base_dir}/.locks"'
        
        if verbose:
            print(f"  [DEBUG] SSH command: {cmd}")
        
        # Don't capture output for mkdir (causes hang on Windows)
        rc, stdout, stderr = self.ssh_run(cmd, timeout=10, capture_output=False)
        
        if rc != 0:
            print(f"ERROR: Failed to create remote directories")
            print(f"  Return code: {rc}")
            print(f"  Stderr: {stderr}")
            print(f"  Stdout: {stdout}")
            return False, None, ""
        
        # Step 2: Upload inputs
        if verbose:
            print(f"  [REMOTE] Uploading inputs...")
        
        remote_prompts = f"{remote_exp_dir}/prompts.json"
        remote_features = f"{remote_exp_dir}/features.json"
        
        if not self.rsync_up(str(local_paths['prompts_json']), remote_prompts, verbose=False):
            return False, None, ""
        
        if not self.rsync_up(str(local_paths['selected_features_json']), remote_features, verbose=False):
            return False, None, ""
        
        # Step 3: Find free GPU
        if verbose:
            print(f"  [REMOTE] Finding free GPU...")
        
        gpu_id = self.get_free_gpu()
        if gpu_id is None:
            print(f"ERROR: No free GPU found on remote node")
            return False, None, ""
        
        if verbose:
            print(f"  [REMOTE] Using GPU {gpu_id}")
        
        # Try to acquire lock (skip on Windows due to subprocess/SSH issues)
        import platform
        if platform.system() != 'Windows':
            if not self.acquire_gpu_lock(gpu_id):
                print(f"ERROR: Failed to acquire lock for GPU {gpu_id} (already in use)")
                return False, None, ""
        elif verbose:
            print(f"  [REMOTE] Skipping GPU lock on Windows (you're the only user)")
        
        # Step 4: Build environment and run
        remote_out = f"{remote_exp_dir}/activations_dump.json"
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        remote_log = f"{remote_logs_dir}/{slug}_{timestamp}.log"
        
        remote_paths_dict = {
            'prompts_json': remote_prompts,
            'features_json': remote_features,
            'activations_dump_json': remote_out,
        }
        
        env_vars = self.build_remote_env(config, seed, remote_paths_dict)
        
        # Create a shell script with Unix line endings
        script_lines = [
            '#!/bin/bash',
            'set -e',
            self.env_activate_cmd,
            f'cd {self.repo_dir}',
        ]
        
        # Add exports
        for k, v in env_vars.items():
            script_lines.append(f'export {k}={v}')
        
        # Add main command
        script_lines.append(
            f'CUDA_VISIBLE_DEVICES={gpu_id} python scripts/neuronpedia_activations/batch_get_activations.py 2>&1 | tee {remote_log}'
        )
        
        # Join with Unix newlines
        script_content = '\n'.join(script_lines) + '\n'
        
        # Write script to remote
        remote_script = f"{remote_exp_dir}/run_activation.sh"
        
        # Upload script content with Unix line endings
        import tempfile
        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False, encoding='utf-8', newline='\n') as tf:
            tf.write(script_content)
            temp_script_path = tf.name
        
        if not self.rsync_up(temp_script_path, remote_script, verbose=False):
            print(f"ERROR: Failed to upload run script")
            Path(temp_script_path).unlink()
            return False, None, ""
        
        Path(temp_script_path).unlink()
        
        # Make executable and run
        full_cmd = f'chmod +x {remote_script} && {remote_script}'
        
        if verbose:
            print(f"  [REMOTE] Running activations on GPU {gpu_id}...")
            print(f"    Model: {env_vars['MODEL_ID']}")
            print(f"    Source: {env_vars['SOURCE_SET']}")
            print(f"    Chunk by layer: {env_vars['CHUNK_BY_LAYER']}")
        
        # Run (with extended timeout for large runs)
        rc, stdout, stderr = self.ssh_run(full_cmd, timeout=7200, capture_output=True)
        
        # Release lock (skip on Windows)
        import platform
        if platform.system() != 'Windows':
            self.release_gpu_lock(gpu_id)
        
        if rc != 0:
            print(f"ERROR: Remote activation failed (exit code {rc})")
            if verbose:
                print(f"STDERR:\n{stderr}")
            return False, gpu_id, remote_log
        
        # Step 5: Download results
        if verbose:
            print(f"  [REMOTE] Downloading results...")
        
        if not self.rsync_down(remote_out, str(local_paths['activations_dump_json']), verbose=False):
            print(f"ERROR: Failed to download activations_dump.json")
            return False, gpu_id, remote_log
        
        # Also download log file
        local_log_path = local_paths['base'] / f"remote_{timestamp}.log"
        self.rsync_down(remote_log, str(local_log_path), verbose=False)
        
        if verbose:
            print(f"  [REMOTE] Completed successfully")
            print(f"    GPU: {gpu_id}")
            print(f"    Remote log: {remote_log}")
            print(f"    Local log: {local_log_path}")
        
        return True, gpu_id, remote_log

    def run_remote_steering(
        self,
        config: Dict[str, Any],
        seed: Dict[str, Any],
        local_paths: Dict[str, Path],
        verbose: bool = True,
    ) -> Tuple[bool, Optional[int], str]:
        """
        Run batch_steering.py on the remote node for a given seed.
        """
        steering_cfg = config.get("steering", {})
        slug = seed["slug"]

        if verbose:
            print(f"  [REMOTE] Setting up remote steering for {slug}...")

        remote_exp_dir = f"{self.base_dir}/steering/{slug}"
        remote_logs_dir = self.logs_dir
        cmd = f'mkdir -p "{remote_exp_dir}" "{remote_logs_dir}" "{self.base_dir}/.locks"'
        rc, _, stderr = self.ssh_run(cmd, timeout=10, capture_output=False)
        if rc != 0:
            print(f"ERROR: Failed to create remote directories for steering: {stderr}")
            return False, None, ""

        remote_prompts = f"{remote_exp_dir}/prompts.json"
        remote_features = f"{remote_exp_dir}/features.json"
        if not self.rsync_up(str(local_paths["prompts_json"]), remote_prompts, verbose=False):
            return False, None, ""
        if not self.rsync_up(str(local_paths["steering_features_json"]), remote_features, verbose=False):
            return False, None, ""

        if verbose:
            print("  [REMOTE] Finding free GPU for steering...")
        gpu_id = self.get_free_gpu()
        if gpu_id is None:
            print("ERROR: No free GPU available for steering")
            return False, None, ""
        if verbose:
            print(f"  [REMOTE] Using GPU {gpu_id}")

        import platform
        lock_acquired = False
        if platform.system() != "Windows":
            lock_acquired = self.acquire_gpu_lock(gpu_id)
            if not lock_acquired:
                print(f"ERROR: GPU {gpu_id} already locked")
                return False, None, ""
        elif verbose:
            print("  [REMOTE] Skipping GPU lock on Windows")

        remote_out = f"{remote_exp_dir}/steering_dump.json"
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        remote_log = f"{remote_logs_dir}/{slug}_{timestamp}_steer.log"

        remote_paths_dict = {
            "prompts_json": remote_prompts,
            "features_json": remote_features,
            "steering_dump_json": remote_out,
        }
        env_vars = self.build_remote_steering_env(
            config, seed, remote_paths_dict, steering_cfg
        )

        script_lines = [
            "#!/bin/bash",
            "set -e",
            self.env_activate_cmd,
            f"cd {self.repo_dir}",
        ]
        for k, v in env_vars.items():
            script_lines.append(f'export {k}="{v}"')
        script_lines.append(
            f"CUDA_VISIBLE_DEVICES={gpu_id} python scripts/neuronpedia_steering/batch_steering.py "
            f"2>&1 | tee {remote_log}"
        )
        script_content = "\n".join(script_lines) + "\n"
        remote_script = f"{remote_exp_dir}/run_steering.sh"

        import tempfile

        with tempfile.NamedTemporaryFile(
            mode="w", suffix=".sh", delete=False, encoding="utf-8", newline="\n"
        ) as tf:
            tf.write(script_content)
            temp_script_path = tf.name

        if not self.rsync_up(temp_script_path, remote_script, verbose=False):
            Path(temp_script_path).unlink(missing_ok=True)
            if lock_acquired:
                self.release_gpu_lock(gpu_id)
            return False, None, ""
        Path(temp_script_path).unlink(missing_ok=True)

        full_cmd = f"chmod +x {remote_script} && {remote_script}"
        if verbose:
            print(f"  [REMOTE] Running steering script on GPU {gpu_id}...")
        rc, stdout, stderr = self.ssh_run(full_cmd, timeout=7200, capture_output=True)

        if lock_acquired:
            self.release_gpu_lock(gpu_id)

        if rc != 0:
            print(f"ERROR: Remote steering failed (exit code {rc})")
            if verbose:
                print(f"STDERR:\n{stderr}")
            return False, gpu_id, remote_log

        if verbose:
            print("  [REMOTE] Downloading steering results...")
        if not self.rsync_down(
            remote_out, str(local_paths["steering_dump_json"]), verbose=False
        ):
            print("ERROR: Failed to download steering_dump.json")
            return False, gpu_id, remote_log

        local_log_path = local_paths["base"] / f"remote_steer_{timestamp}.log"
        self.rsync_down(remote_log, str(local_log_path), verbose=False)

        if verbose:
            print("  [REMOTE] Steering completed successfully")
            print(f"    GPU: {gpu_id}")
            print(f"    Remote log: {remote_log}")
            print(f"    Local log: {local_log_path}")

        return True, gpu_id, remote_log

    def run_remote_batch(self, config: Dict[str, Any], batch_states: List[Dict[str, Any]],
                         batch_id: str, verbose: bool = True) -> Tuple[bool, Dict[str, Any], Dict[str, Any]]:
        """
        Run a batch of seeds on the remote node using remote_batch_runner.py.
        Returns (success, metadata, per_seed_results).
        """
        if not batch_states:
            return True, {}, {}

        model_cfg = config['model']
        act_cfg = config['get_activations']['local']
        include_zero = act_cfg.get('include_zero', False)
        chunk_by_layer = act_cfg.get('chunk_by_layer', True)
        persist_cache = self.remote_config.get('persist_sae_cache', False)

        timestamp = time.strftime("%Y%m%d_%H%M%S")
        remote_batch_dir = f"{self.base_dir}/experiments/{batch_id}_{timestamp}"
        remote_manifest = f"{remote_batch_dir}/batch_manifest.json"
        remote_results = f"{remote_batch_dir}/batch_results.json"
        remote_log = f"{self.logs_dir}/{batch_id}_{timestamp}.log"

        if verbose:
            slugs = ", ".join(state['seed']['slug'] for state in batch_states)
            print(f"  [REMOTE] Preparing batch {batch_id} ({len(batch_states)} seeds: {slugs})")

        # Create directories
        cmd = f'mkdir -p "{remote_batch_dir}" "{self.logs_dir}" "{self.base_dir}/.locks"'
        rc, _, stderr = self.ssh_run(cmd, timeout=10, capture_output=False)
        if rc != 0:
            print(f"ERROR: Failed to create remote batch directory: {stderr}")
            return False, {}, {}

        seed_remote_info: Dict[str, Dict[str, Any]] = {}
        manifest = {
            "batch_id": batch_id,
            "timestamp": timestamp,
            "model": {
                "id": model_cfg['id'],
                "source_set": model_cfg['source_set'],
            },
            "activation": {
                "chunk_by_layer": True if model_cfg['source_set'] == 'clt-hp' else chunk_by_layer,
                "include_zero": include_zero,
                "persist_sae_cache": persist_cache,
            },
            "seeds": [],
        }

        # Upload inputs per seed
        for state in batch_states:
            slug = state['seed']['slug']
            paths = state['paths']
            remote_seed_dir = f"{remote_batch_dir}/{slug}"
            self.ssh_run(f'mkdir -p "{remote_seed_dir}"', timeout=5, capture_output=False)

            local_prompts = paths['prompts_json']
            local_features = paths['selected_features_json']

            if not local_prompts.exists() or not local_features.exists():
                error_msg = f"Missing prompts/features for seed {slug}"
                print(f"ERROR: {error_msg}")
                return False, {}, {}

            remote_prompts = f"{remote_seed_dir}/prompts.json"
            remote_features = f"{remote_seed_dir}/features.json"
            remote_out = f"{remote_seed_dir}/activations_dump.json"

            if not self.rsync_up(str(local_prompts), remote_prompts, verbose=False):
                return False, {}, {}
            if not self.rsync_up(str(local_features), remote_features, verbose=False):
                return False, {}, {}

            seed_remote_info[slug] = {
                "remote_prompts": remote_prompts,
                "remote_features": remote_features,
                "remote_out": remote_out,
                "local_out": paths['activations_dump_json'],
                "local_base": paths['base'],
            }

            manifest["seeds"].append({
                "slug": slug,
                "prompts_json": remote_prompts,
                "features_json": remote_features,
                "out_json": remote_out,
            })

        # Write manifest locally and upload
        with tempfile.NamedTemporaryFile(mode='w', delete=False, encoding='utf-8') as tf:
            json.dump(manifest, tf, indent=2)
            temp_manifest_path = tf.name
        upload_ok = self.rsync_up(temp_manifest_path, remote_manifest, verbose=False)
        Path(temp_manifest_path).unlink(missing_ok=True)
        if not upload_ok:
            return False, {}, {}

        # Select GPU
        gpu_id = self.get_free_gpu()
        if gpu_id is None:
            print("ERROR: No free GPU found for batch")
            return False, {}, {}
        if verbose:
            print(f"  [REMOTE] Batch {batch_id} assigned GPU {gpu_id}")

        import platform
        lock_acquired = False
        if platform.system() != 'Windows':
            lock_acquired = self.acquire_gpu_lock(gpu_id)
            if not lock_acquired:
                print(f"ERROR: Failed to acquire GPU lock for GPU {gpu_id}")
                return False, {}, {}

        env_vars = {
            'NP_WORKDIR': self.base_dir,
            'MODEL_ID': model_cfg['id'],
            'SOURCE_SET': model_cfg['source_set'],
            'CHUNK_BY_LAYER': 'true',
            'INCLUDE_ZERO_ACTIVATIONS': 'true' if include_zero else 'false',
            'PERSIST_SAE_CACHE': 'true' if persist_cache else 'false',
            'PYTHONIOENCODING': 'utf-8',
        }

        script_lines = [
            '#!/bin/bash',
            'set -e',
            self.env_activate_cmd,
            f'cd {self.repo_dir}',
        ]
        for k, v in env_vars.items():
            script_lines.append(f'export {k}={v}')
        script_lines.append(
            f'CUDA_VISIBLE_DEVICES={gpu_id} python scripts/experiments/batch/pipeline/remote_batch_runner.py '
            f'--manifest {remote_manifest} --results {remote_results} 2>&1 | tee {remote_log}'
        )
        script_content = '\n'.join(script_lines) + '\n'
        remote_script = f"{remote_batch_dir}/run_batch.sh"

        with tempfile.NamedTemporaryFile(mode='w', suffix='.sh', delete=False, encoding='utf-8', newline='\n') as tf:
            tf.write(script_content)
            temp_script_path = tf.name

        if not self.rsync_up(temp_script_path, remote_script, verbose=False):
            Path(temp_script_path).unlink(missing_ok=True)
            if lock_acquired:
                self.release_gpu_lock(gpu_id)
            return False, {}, {}
        Path(temp_script_path).unlink(missing_ok=True)

        self.ssh_run(f'chmod +x {remote_script}', timeout=5, capture_output=False)
        if verbose:
            print(f"  [REMOTE] Running batch script {remote_script}")

        rc, stdout, stderr = self.ssh_run(f'bash {remote_script}', timeout=7200, capture_output=True)

        if lock_acquired:
            self.release_gpu_lock(gpu_id)

        per_seed_results: Dict[str, Dict[str, Any]] = {
            state['seed']['slug']: {
                "success": False,
                "error": "Batch execution failed" if rc != 0 else "Unknown",
                "remote_log": remote_log,
                "local_log": None,
            }
            for state in batch_states
        }

        # Download log once and copy to each seed directory
        shared_log_name = Path(f"{batch_id}_{timestamp}.log")
        first_base = batch_states[0]['paths']['base']
        shared_log_local = first_base / shared_log_name
        shared_log_local.parent.mkdir(parents=True, exist_ok=True)
        if self.rsync_down(remote_log, str(shared_log_local), verbose=False):
            for state in batch_states:
                dest = state['paths']['base'] / shared_log_name
                if dest != shared_log_local:
                    dest.parent.mkdir(parents=True, exist_ok=True)
                    shutil.copy(shared_log_local, dest)
                per_seed_results[state['seed']['slug']]['local_log'] = str(dest)
        else:
            shared_log_local = None

        # Download results manifest (if present)
        fd, tmp_path = tempfile.mkstemp(prefix="batch_results_", suffix=".json")
        os.close(fd)
        tmp_results = Path(tmp_path)
        results_loaded = False
        if self.rsync_down(remote_results, str(tmp_results), verbose=False):
            try:
                summary = json.loads(tmp_results.read_text(encoding='utf-8'))
                results_loaded = True
            except Exception:
                traceback.print_exc()
            finally:
                tmp_results.unlink(missing_ok=True)
        else:
            tmp_results.unlink(missing_ok=True)

        if results_loaded:
            for entry in summary.get('seeds', []):
                slug = entry.get('slug')
                if slug not in per_seed_results:
                    continue
                per_seed_results[slug]['success'] = entry.get('success', False)
                per_seed_results[slug]['error'] = entry.get('error')

        # Download outputs for successful seeds
        for slug, info in per_seed_results.items():
            if not info.get('success'):
                continue
            remote_out = seed_remote_info[slug]['remote_out']
            local_out = seed_remote_info[slug]['local_out']
            if not self.rsync_down(remote_out, str(local_out), verbose=False):
                info['success'] = False
                info['error'] = "Failed to download activations_dump.json"

        if not results_loaded and rc != 0:
            if verbose:
                print(f"ERROR: Batch script failed rc={rc}")
                print(stderr)
            return False, {"gpu_id": gpu_id, "remote_log": remote_log, "batch_id": batch_id}, per_seed_results

        batch_success = all(result.get('success') for result in per_seed_results.values())
        metadata = {
            "gpu_id": gpu_id,
            "remote_log": remote_log,
            "batch_id": batch_id,
            "remote_dir": remote_batch_dir,
        }

        return batch_success, metadata, per_seed_results


def check_sshpass_available() -> bool:
    """Check if sshpass is available (needed for password auth)."""
    try:
        result = subprocess.run(['sshpass', '-V'], capture_output=True, timeout=5)
        return result.returncode == 0
    except:
        return False


def process_remote_activation_step(config: Dict[str, Any], seed: Dict[str, Any], 
                                   paths: Dict[str, Path], verbose: bool = True) -> Tuple[bool, Dict[str, Any]]:
    """
    Process activations step using remote GPU node.
    
    Args:
        config: Full experiment config
        seed: Seed config
        paths: Local paths dict
        verbose: Print progress
    
    Returns:
        Tuple of (success: bool, metadata: dict with gpu_id, log_path, etc.)
    """
    # Check if remote is enabled
    remote_config = config.get('compute', {}).get('remote', {})
    if not remote_config.get('enabled'):
        print(f"ERROR: Remote execution not enabled in config")
        return False, {}
    
    # Check for password auth requirements
    password_env = remote_config.get('password_env')
    if password_env and not os.environ.get(password_env):
        print(f"ERROR: Password env var {password_env} not set")
        return False, {}
    
    # Check sshpass if using password
    if password_env and not check_sshpass_available():
        print(f"WARNING: sshpass not available; password auth may fail")
        print(f"  Install with: sudo apt-get install sshpass (Linux) or brew install hudochenkov/sshpass/sshpass (Mac)")
    
    # Initialize executor
    try:
        executor = RemoteExecutor(config)
    except Exception as e:
        print(f"ERROR: Failed to initialize remote executor: {e}")
        return False, {}
    
    # Run remote activation
    success, gpu_id, log_path = executor.run_remote_activation(config, seed, paths, verbose=verbose)
    
    metadata = {
        'remote_host': f"{executor.user}@{executor.host}",
        'gpu_id': gpu_id,
        'remote_log': log_path,
        'base_dir': executor.base_dir,
    }
    
    return success, metadata


def process_remote_activation_batch(config: Dict[str, Any], batch_states: List[Dict[str, Any]],
                                    batch_id: str, verbose: bool = True) -> Tuple[bool, Dict[str, Any], Dict[str, Any]]:
    """
    Process a batch of seeds using the remote GPU node.
    Returns (success, metadata, per_seed_results).
    """
    remote_config = config.get('compute', {}).get('remote', {})
    if not remote_config.get('enabled'):
        print("ERROR: Remote execution not enabled in config")
        return False, {}, {}

    password_env = remote_config.get('password_env')
    if password_env and not os.environ.get(password_env):
        print(f"ERROR: Password env var {password_env} not set")
        return False, {}, {}

    if password_env and not check_sshpass_available():
        print("WARNING: sshpass not available; password auth may fail")

    executor = RemoteExecutor(config)
    success, metadata, per_seed = executor.run_remote_batch(config, batch_states, batch_id, verbose=verbose)
    metadata.update({'remote_host': f"{executor.user}@{executor.host}"})
    return success, metadata, per_seed


def verify_remote_connection(config: Dict[str, Any], verbose: bool = True) -> bool:
    """
    Run a quick SSH + directory check before kicking off remote work.
    """
    remote_config = config.get('compute', {}).get('remote', {})
    if not remote_config.get('enabled'):
        return True
    
    try:
        executor = RemoteExecutor(config)
    except Exception as exc:
        print(f"ERROR: Failed to initialize remote executor: {exc}")
        return False
    
    if verbose:
        print(f"  [REMOTE] Checking connectivity to {executor.ssh_target} ...")
    
    rc, stdout, stderr = executor.ssh_run('echo __REMOTE_OK__', timeout=10)
    if rc != 0 or '__REMOTE_OK__' not in stdout:
        print("ERROR: SSH connection failed")
        if stderr:
            print(f"  stderr: {stderr.strip()}")
        if stdout:
            print(f"  stdout: {stdout.strip()}")
        return False
    
    dir_cmd = f'mkdir -p "{executor.base_dir}" "{executor.logs_dir}" && echo __REMOTE_DIR_OK__'
    rc, stdout, stderr = executor.ssh_run(dir_cmd, timeout=10)
    if rc != 0 or '__REMOTE_DIR_OK__' not in stdout:
        print("ERROR: Unable to access remote base/log directories")
        if stderr:
            print(f"  stderr: {stderr.strip()}")
        if stdout:
            print(f"  stdout: {stdout.strip()}")
        return False
    
    if verbose:
        print("  [REMOTE] Connectivity OK")
    return True

