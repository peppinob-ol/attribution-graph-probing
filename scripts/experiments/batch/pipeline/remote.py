"""
Remote execution module for running activations on GPU nodes via SSH.
Handles rsync, GPU selection, locking, and remote command execution.
"""
import os
import subprocess
import time
from pathlib import Path
from typing import Dict, Any, Optional, Tuple, List


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
        
        self.host = self.remote_config['host']
        self.user = self.remote_config['user']
        self.base_dir = self.remote_config['base_dir']
        self.repo_dir = self.remote_config['repo_dir']
        self.logs_dir = self.remote_config['logs_dir']
        self.env_activate_cmd = self.remote_config['env_activate_cmd']
        self.use_gpu_count = self.remote_config.get('use_gpu_count', 1)
        self.gpu_selection = self.remote_config.get('gpu_selection', 'auto')
        
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
        
        if platform.system() == 'Windows':
            # On Windows, build as string and use shell=True
            ssh_cmd_str = f'ssh -o StrictHostKeyChecking=no {self.ssh_target} "{cmd}"'
            
            try:
                result = subprocess.run(
                    ssh_cmd_str,
                    capture_output=capture_output,
                    text=True,
                    timeout=timeout,
                    shell=True
                )
                return result.returncode, result.stdout, result.stderr
            except subprocess.TimeoutExpired:
                return -1, "", f"Command timed out after {timeout}s"
            except Exception as e:
                return -1, "", str(e)
        else:
            # On Linux/Mac, use list form
            ssh_cmd = ['ssh', '-o', 'StrictHostKeyChecking=no', self.ssh_target, cmd]
        
        try:
            result = subprocess.run(
                ssh_cmd,
                capture_output=capture_output,
                text=True,
                timeout=timeout
            )
            return result.returncode, result.stdout, result.stderr
        
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
    
    def get_free_gpu(self) -> Optional[int]:
        """
        Find a free GPU on the remote node.
        
        Uses nvidia-smi to check memory usage and running processes.
        Returns GPU index if found, None otherwise.
        """
        # Query GPU status
        cmd = 'nvidia-smi --query-gpu=index,memory.used,utilization.gpu --format=csv,noheader,nounits'
        rc, stdout, stderr = self.ssh_run(cmd, timeout=10)
        
        if rc != 0:
            print(f"ERROR: Failed to query nvidia-smi: {stderr}")
            return None
        
        # Parse output: "0, 0, 0" means GPU 0 with 0 MB used, 0% util
        for line in stdout.strip().split('\n'):
            parts = [p.strip() for p in line.split(',')]
            if len(parts) >= 3:
                try:
                    gpu_idx = int(parts[0])
                    mem_used = int(parts[1])
                    util = int(parts[2])
                    
                    # Consider free if memory < 500 MB and util < 5%
                    if mem_used < 500 and util < 5:
                        return gpu_idx
                
                except ValueError:
                    continue
        
        return None
    
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
        
        rc, stdout, stderr = self.ssh_run(cmd, timeout=10)
        
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
        
        # Try to acquire lock
        if not self.acquire_gpu_lock(gpu_id):
            print(f"ERROR: Failed to acquire lock for GPU {gpu_id} (already in use)")
            return False, None, ""
        
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
        
        # Build export commands
        exports = ' && '.join([f'export {k}="{v}"' for k, v in env_vars.items()])
        
        # Build full command
        full_cmd = (
            f'{self.env_activate_cmd} && '
            f'{exports} && '
            f'cd {self.repo_dir} && '
            f'CUDA_VISIBLE_DEVICES={gpu_id} python scripts/neuronpedia_activations/batch_get_activations.py 2>&1 | tee {remote_log}'
        )
        
        if verbose:
            print(f"  [REMOTE] Running activations on GPU {gpu_id}...")
            print(f"    Model: {env_vars['MODEL_ID']}")
            print(f"    Source: {env_vars['SOURCE_SET']}")
            print(f"    Chunk by layer: {env_vars['CHUNK_BY_LAYER']}")
        
        # Run (with extended timeout for large runs)
        rc, stdout, stderr = self.ssh_run(full_cmd, timeout=7200, capture_output=True)
        
        # Release lock
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

