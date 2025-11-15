# End-to-End Testing Guide

## Prerequisites

1. **Local (laptop):**
   - Python 3.10+ with dependencies installed
   - NEURONPEDIA_API_KEY set in environment (for graph generation)
   - ELEUTHERAI_NODE_PSW set in environment (for remote execution)

2. **Remote (GPU node):**
   - SSH access to giuseppe@207.53.234.140
   - Python venv set up at /mnt/ssd-1/.../giuseppe/venv
   - env.sh configured with HF_HOME, HF_TOKEN, venv activation
   - Repo cloned at /mnt/ssd-1/.../giuseppe/attribution-graph-probing

## Test 1: Single Seed (Dallas) - Local Execution

Tests the complete pipeline locally without remote execution.

```bash
# From repo root
cd scripts/experiments/batch

# Dry run first (validates config)
python run_batch_from_yaml.py \
  --config configs/test_dallas_single.yml \
  --dry-run

# Execute
python run_batch_from_yaml.py \
  --config configs/test_dallas_single.yml

# Verify outputs
ls -R ../../../output/test_batch_dallas/dallas_test/
```

**Expected outputs:**
```
output/test_batch_dallas/dallas_test/
├── manifest.json
├── 00 Graph Generation/
│   ├── graph.json (copied from examples)
│   ├── graph_feature_static_metrics.csv
│   └── selected_features_with_nodes.json
└── 01 Prompt Probing/
    ├── prompts.json (copied from examples)
    └── activations_dump.json
```

**Expected manifest.json fields:**
- status: "completed"
- timestamp_started, timestamp_completed
- git.commit, git.branch
- compute.backend: "local"
- compute.remote_enabled: false

## Test 2: Single Seed - Remote Execution

Tests remote GPU execution with SSH, rsync, GPU locking.

```bash
# Update config to enable remote
# Edit configs/test_dallas_single.yml:
#   compute.remote.enabled: true

# Ensure password env is set
export ELEUTHERAI_NODE_PSW="your_password"

# Dry run
python run_batch_from_yaml.py \
  --config configs/test_dallas_single.yml \
  --dry-run

# Execute
python run_batch_from_yaml.py \
  --config configs/test_dallas_single.yml
```

**Expected behavior:**
1. Uploads prompts.json and features.json to node
2. Finds free GPU (should pick GPU 0)
3. Acquires lock at /mnt/.../giuseppe/.locks/gpu0
4. Runs batch_get_activations.py remotely
5. Downloads activations_dump.json back
6. Downloads remote log
7. Releases GPU lock

**Verify on node:**
```bash
ssh giuseppe@207.53.234.140
ls /mnt/ssd-1/.../giuseppe/experiments/dallas_test/
ls /mnt/ssd-1/.../giuseppe/logs/
# Should see activations_dump.json and log file
```

**Expected manifest additions:**
- remote_host: "giuseppe@207.53.234.140"
- gpu_id: 0
- remote_log: "/mnt/.../logs/dallas_test_TIMESTAMP.log"
- base_dir: "/mnt/.../giuseppe"

## Test 3: Two Seeds Sequential

Tests multiple seeds running one after another on the same GPU.

Create config `configs/test_two_seeds.yml`:

```yaml
version: 0.1
experiment_name: test_two_seeds

paths:
  outputs_root: output/test_batch_two_seeds

model:
  id: gemma-2-2b
  source_set: gemmascope-res-16k

features:
  selection: cumulative_influence
  threshold: 0.95

probes:
  mode: shared_file
  shared_file:
    prompts_json: output/examples/Dallas/prompts.json

get_activations:
  backend: local
  local:
    chunk_by_layer: false
    include_zero: false

compute:
  remote:
    enabled: true
    host: "207.53.234.140"
    user: "giuseppe"
    password_env: "ELEUTHERAI_NODE_PSW"
    base_dir: "/mnt/ssd-1/soar-automated_interpretability/graphs/giuseppe"
    repo_dir: "/mnt/ssd-1/soar-automated_interpretability/graphs/giuseppe/attribution-graph-probing"
    logs_dir: "/mnt/ssd-1/soar-automated_interpretability/graphs/giuseppe/logs"
    env_activate_cmd: "source /mnt/ssd-1/soar-automated_interpretability/graphs/giuseppe/env.sh"
    use_gpu_count: 1

steps:
  graph_generation: false
  feature_export: true
  probe_prompts: true
  activations: true
  grouping: false

graph_generation:
  seeds_mode: precomputed

precomputed_seeds:
  - slug: dallas_test
    graph_json: output/examples/Dallas/00 Graph Generation/graph.json
  
  - slug: oakland_test
    graph_json: output/examples/capital oakland/graph.json
```

Run:
```bash
python run_batch_from_yaml.py --config configs/test_two_seeds.yml
```

**Expected behavior:**
- Processes dallas_test first (GPU 0)
- Releases GPU lock
- Processes oakland_test second (GPU 0 again, since it's free)
- Both complete successfully

**Verify:**
```bash
ls output/test_batch_two_seeds/
# Should see: dallas_test/ and oakland_test/
cat output/test_batch_two_seeds/dallas_test/manifest.json
cat output/test_batch_two_seeds/oakland_test/manifest.json
```

## Test 4: Grouping Step

Enable grouping in test config and verify classification/naming works.

```bash
# Edit configs/test_dallas_single.yml:
#   grouping.enabled: true
#   steps.grouping: true

# Run (force to regenerate)
python run_batch_from_yaml.py \
  --config configs/test_dallas_single.yml \
  --force
```

**Expected outputs:**
```
output/test_batch_dallas/dallas_test/02 Node Grouping/
├── node_grouping.csv
```

**Verify CSV has columns:**
- feature_key, layer, feature, prompt, peak_token, peak_token_type
- pred_label, subtype, confidence, supernode_name
- target_tokens, etc.

## Test 5: Force Rerun

Verify --force overwrites existing outputs.

```bash
# First run
python run_batch_from_yaml.py --config configs/test_dallas_single.yml

# Note timestamp in manifest
cat output/test_batch_dallas/dallas_test/manifest.json | grep timestamp

# Force rerun
python run_batch_from_yaml.py --config configs/test_dallas_single.yml --force

# Verify new timestamp
cat output/test_batch_dallas/dallas_test/manifest.json | grep timestamp
```

## Troubleshooting

### sshpass not found
If you see "sshpass not available" warning:

**Linux:**
```bash
sudo apt-get install sshpass
```

**Mac:**
```bash
brew install hudochenkov/sshpass/sshpass
```

**Windows:**
Use WSL or set up SSH key-based auth instead of password.

### SSH key-based auth (alternative to password)
If you prefer not to use passwords:

1. Generate SSH key (if not exists):
   ```bash
   ssh-keygen -t ed25519 -C "your_email@example.com"
   ```

2. Copy to remote:
   ```bash
   ssh-copy-id giuseppe@207.53.234.140
   ```

3. Update YAML:
   ```yaml
   compute.remote.password_env: ""  # Leave empty for key-based auth
   ```

### GPU already locked
If you see "Failed to acquire lock for GPU X":

```bash
# Check locks on remote
ssh giuseppe@207.53.234.140 'ls /mnt/ssd-1/.../giuseppe/.locks/'

# Remove stale lock if needed
ssh giuseppe@207.53.234.140 'rmdir /mnt/ssd-1/.../giuseppe/.locks/gpu0'
```

### Import errors
Ensure you're running from repo root:

```bash
cd /path/to/circuit_tracer-prompt_rover
python scripts/experiments/batch/run_batch_from_yaml.py --config ...
```

### Remote activation timeout
Default timeout is 2 hours (7200s). For very large runs, increase in `remote.py`:

```python
rc, stdout, stderr = self.ssh_run(full_cmd, timeout=14400, ...)  # 4 hours
```

## Success Criteria

Test passes if:
- Dry run validates config without errors
- All steps execute without exceptions
- manifest.json shows status="completed"
- activations_dump.json exists and has valid JSON
- (If grouping enabled) node_grouping.csv exists with expected columns
- Remote logs are downloaded to local outputs_root/{slug}/

## Next Steps After Tests Pass

1. Create real USA capitals config with all state pairs
2. Enable remote execution with compute.remote.enabled=true
3. Run batch with multiple seeds
4. Enable grouping step
5. Analyze transfer rates across entity swaps

