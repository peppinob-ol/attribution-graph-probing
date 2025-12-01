# Batch Experiment Runner

Automated pipeline for running attribution graph experiments at scale from YAML configs.

This directory contains two runners:
1. **`run_batch_from_yaml.py`** - Graph generation, activations, and grouping
2. **`run_batch_swaps.py`** - CT steering swap experiments (requires graphs from step 1)

## Quick Start

### Graph Generation & Activations

```bash
# Validate config (dry run)
python run_batch_from_yaml.py --config configs/usa_states_full.yml --dry-run

# Run batch experiment
python run_batch_from_yaml.py --config configs/usa_states_full.yml

# Force overwrite existing outputs
python run_batch_from_yaml.py --config configs/usa_states_full.yml --force
```

### CT Steering Swaps (after graphs are generated)

```bash
# Validate swap config (dry run)
python run_batch_swaps.py --config configs/usa_states_swap.yml --dry-run

# Run single swap pair (test)
python run_batch_swaps.py --config configs/usa_states_swap.yml --pair texas_dallas:california_oakland

# Run full 50x50 matrix in PARALLEL (recommended for large runs)
python run_batch_swaps.py --config configs/usa_states_swap.yml --parallel

# Run full 50x50 matrix (sequential, slower)
python run_batch_swaps.py --config configs/usa_states_swap.yml

# Force re-run all (WARNING: overwrites existing results)
python run_batch_swaps.py --config configs/usa_states_swap.yml --force
```

### Swap Analysis (after swaps are completed)

```bash
# Analyze swap results with tiered classification
python analyze_swaps.py --output-dir _analysis_v3

# Browse individual results interactively
python browse_swaps.py --from california --to texas

# Generate visualizations
python ../../../visualization/swap_heatmap.py
python ../../../visualization/swap_factor_analysis.py
```

## Directory Structure

```
scripts/experiments/batch/
|-- configs/                          # YAML experiment configs
|   |-- usa_states_full.yml          # Graph generation config (50 states)
|   |-- usa_states_swap.yml          # CT steering swap config
|
|-- pipeline/                         # Pipeline modules
|   |-- loader.py                    # Config loading and validation
|   |-- graph.py                     # Graph generation and feature selection
|   |-- probes.py                    # Probe prompts handling
|   |-- activations_local.py         # Local activations processing
|   |-- manifest.py                  # Experiment manifest generation
|   |-- remote.py                    # Remote GPU execution (SSH/rsync)
|   |-- steering_remote_ct.py        # Remote CT steering execution
|   |-- graph_loader.py              # Shared graph data loading
|   |-- swap_loader.py               # Swap pair resolution
|   |-- swap_evaluator.py            # Swap result evaluation
|   |-- swap_classifier.py           # Tiered classification (0-5 tiers)
|
|-- run_batch_from_yaml.py           # Main CLI runner (graphs/activations)
|-- run_batch_swaps.py               # CT steering swap runner
|-- analyze_swaps.py                 # Post-hoc swap analysis & classification
|-- browse_swaps.py                  # Interactive result browser (colored)
|-- explore_swap_factors.py          # Factor correlation analysis
|-- army_parade.py                   # Pre-run state overview
|-- SWAP_STRATEGIES.md               # Strategies for improving swap success
|-- README.md                        # This file
|-- TESTING.md                       # Testing guide
```

## Per-Seed Output Structure

Each seed produces a standardized folder structure:

```
outputs_root/{slug}/
|-- manifest.json                    # Run metadata (timestamp, git commit, status)
|-- 00 Graph Generation/
|   |-- graph.json                   # Attribution graph from Neuronpedia
|   |-- graph_feature_static_metrics.csv
|   |-- selected_features_with_nodes.json
|-- 01 Prompt Probing/
|   |-- prompts.json                 # Probe prompts
|   |-- activations_dump.json        # Feature activations
|-- 02 Node Grouping/
    |-- node_grouping.csv            # Feature-to-supernode mapping
```

## Swap Experiment Output Structure

When running `run_batch_swaps.py`, results are stored in a `_swaps/` subdirectory:

```
outputs_root/
|-- _swaps/                          # All swap experiment results
|   |-- _summary.json                # Aggregate statistics
|   |-- _matrix.csv                  # 50x50 success rate matrix
|   |-- by_source/                   # Results organized by source prompt
|   |   |-- texas_dallas/
|   |   |   |-- to_california_oakland.json
|   |   |   |-- to_florida_miami.json
|   |   |   |-- to_texas_dallas.json  # Identity baseline
|   |   |-- california_oakland/
|   |       |-- to_texas_dallas.json
|   |-- _analysis_v3/                # Analysis output (from analyze_swaps.py)
|   |   |-- tier_summary.json        # Tiered success rates
|   |   |-- tier_matrix.csv          # 50x50 tier matrix
|   |   |-- detailed_results.csv     # Per-swap classification
|   |   |-- tier_heatmap.png         # Heatmap visualization
|   |   |-- swap_factor_analysis.png # Factor correlation plots
|   |   |-- swap_factor_summary.json # Correlation statistics
|   |-- work/                        # Temporary work files per swap
|
|-- texas_dallas/                    # Source graph data (unchanged)
|-- california_oakland/              # Source graph data (unchanged)
```

Each swap result file contains:
- Source/target entity info (state, capital, city)
- Intervention counts (ablate + amplify features)
- Evaluation metrics (exact match, suppression, topk probabilities)
- Raw outputs for post-hoc analysis

## Swap Analysis Tools

After running swaps, use these tools to analyze results:

### Tiered Classification System

The `analyze_swaps.py` script classifies each swap into a 0-5 tier:

| Tier | Name | Description |
|------|------|-------------|
| 5 | PERFECT | Target capital found in output |
| 4 | TARGET_STATE_CITY | Target state city found (not capital) |
| 3 | TARGET_STATE_ONLY | Target state reference found |
| 2 | SUPPRESSED_ONLY | Source suppressed, no target info |
| 1 | SOURCE_PERSISTS | Source capital still in output |
| 0 | WRONG_STATE | Wrong state entirely |

```bash
# Run classification analysis
python analyze_swaps.py --output-dir _analysis_v3

# Output files:
#   tier_summary.json    - Aggregate statistics by tier
#   tier_matrix.csv      - 50x50 tier matrix
#   detailed_results.csv - Per-swap classification
```

### Interactive Browser

Browse individual swap results with colored tier display:

```bash
# Browse all results
python browse_swaps.py

# Filter by source/target
python browse_swaps.py --from california --to texas

# Filter by tier
python browse_swaps.py --tier 5  # Only PERFECT swaps

# Commands in browser:
#   [number] - Show detailed result
#   n/p      - Next/previous page
#   m        - Add note to current result
#   notes    - Review all notes
#   save     - Export notes to JSON
#   q        - Quit
```

### Visualizations

```bash
# Generate heatmap from tier matrix
python ../../../visualization/swap_heatmap.py

# Generate factor analysis (native prob, supernodes, etc.)
python ../../../visualization/swap_factor_analysis.py
```

### Factor Analysis

The `explore_swap_factors.py` and `swap_factor_analysis.py` scripts analyze correlations between swap success and graph characteristics:

**Key findings from 50-state analysis:**

| Factor | vs Source Tier | vs Target Tier |
|--------|----------------|----------------|
| State supernode features | r = -0.92 | r = +0.06 |
| Native logit probability | r = -0.61 | r = +0.27 |
| Total supernode count | r = -0.75 | r = -0.09 |

**Interpretation:**
- **State features**: More features in state supernode = harder to steer FROM (strong defense)
- **Native probability**: Higher native prob = harder to escape, easier to land on
- **Supernodes**: More supernodes = harder to steer FROM

**State Archetypes:**
- **Exchangers** (CA, OH): Good bidirectional steering
- **Magnets** (CO): Easy to steer TO, hard to steer FROM
- **Escape Routes** (GA, OR): Easy to steer FROM, hard to steer TO
- **Traps** (NY): Hard to steer in either direction

## Config Overview

See `configs/usa_capitals_swap_full.yml` for a complete example with all options.

### Minimal Config

```yaml
version: 0.1
experiment_name: my_experiment

paths:
  outputs_root: output/my_experiment

model:
  id: gemma-2-2b
  source_set: clt-hp

features:
  selection: cumulative_influence
  threshold: 0.95

probes:
  mode: shared_file
  shared_file:
    prompts_json: examples_data/prompts.json

get_activations:
  backend: local
  local:
    chunk_by_layer: true
    include_zero: false
    gpus: [0]

steps:
  graph_generation: false    # Use precomputed graphs
  feature_export: true       # Extract features from graphs
  probe_prompts: true        # Setup probe prompts
  activations: true          # Run activation measurement
  grouping: false            # (not yet implemented)
  upload_subgraph: false     # (not yet implemented)
  dry_run: false
  force: false

# Precomputed seeds (when graph_generation=false)
precomputed_seeds:
  - slug: texas_dallas
    graph_json: output/graph_data/texas_dallas.json
  - slug: california_oakland
    graph_json: output/graph_data/california_oakland.json
```

### Seeds Modes

The runner supports three modes for seed specification:

#### 1. Precomputed (default)
Use pre-generated graphs from Streamlit or manual API calls:

```yaml
graph_generation:
  seeds_mode: precomputed

precomputed_seeds:
  - slug: texas_dallas
    graph_json: output/graph_data/texas_dallas.json
```

#### 2. Prompts List
Generate graphs from a list of prompts:

```yaml
graph_generation:
  enabled: true
  seeds_mode: prompts_list
  prompts_list:
    items:
      - "The capital of Texas is"
      - "The capital of California is"
    # Or load from file:
    # file: data/prompts_list.txt
```

#### 3. Templated (for entity swapping)
Generate graphs and probes from templates + entities:

```yaml
graph_generation:
  enabled: true
  seeds_mode: templated
  templated:
    seed_prompt: "The capital of state containing {city} is"
    slug_template: "{state}_{city}"
    entities:
      items:
        - { city: "Dallas", state: "Texas", capital: "Austin" }
        - { city: "Oakland", state: "California", capital: "Sacramento" }

probes:
  mode: templated
  templated:
    templates:
      - id: probe_city
        text: "entity: A city in {state}, USA is {city}"
      - id: probe_capital
        text: "entity: The capital city of {state} is {capital}"
```

### Swap Config (for run_batch_swaps.py)

The swap runner uses a separate config that references the source config:

```yaml
version: 0.1
experiment_name: usa_states_swap

inputs:
  # Reference the original config for entities (no duplication!)
  source_config: configs/usa_states_full.yml
  graphs_root: output/usa_states_batch

swap:
  mode: matrix              # Full NxN combinations (50x50 = 2500)
  include_identity: true    # Include Texas->Texas as baseline
  # Or use explicit pairs:
  # mode: defined_pairs
  # pairs:
  #   - [texas_dallas, california_oakland]
  #   - [new_york_new_york_city, florida_miami]

ct_steering:
  model_id: google/gemma-2-2b
  transcoder_set: mntss/clt-gemma-2-2b-2.5M
  M_ablate: 0.0             # Ablation multiplier (0 = full ablate)
  M_amplify: 2.0            # Amplification multiplier
  temperature: 0.3
  n_tokens: 6
  seed: 42

compute:
  inherit_from_source: true # Use same remote settings as source_config
```

Key features:
- **No entity duplication**: Imports entities from `source_config`
- **Concept extraction**: Uses `entity['state'].lower()` for concept matching
- **Flexible modes**: Full matrix or explicit pairs
- **Inherited compute**: Reuses remote execution settings from source

## Environment Variables

For local activation runs, the following env vars are set automatically:

- `MODEL_ID` - from config.model.id
- `SOURCE_SET` - from config.model.source_set
- `PROMPTS_JSON_PATH` - per-seed prompts file
- `FEATURES_JSON_PATH` - per-seed features file
- `OUT_JSON_PATH` - per-seed output path
- `CHUNK_BY_LAYER` - from config.get_activations.local.chunk_by_layer
- `INCLUDE_ZERO_ACTIVATIONS` - from config.get_activations.local.include_zero

For Neuronpedia API calls (graph generation):

- `NEURONPEDIA_API_KEY` - must be set in your environment

For gated models (e.g., Gemma):

- `HF_TOKEN` - Hugging Face token (optional, for local runs)

## Current Limitations

### Implemented
- Config loading and validation
- Seed resolution (all 3 modes)
- Graph generation via API (prompts_list, templated modes)
- Feature selection (cumulative_influence method)
- Probe prompts (shared_file, templated modes)
- Local activations (calls batch_get_activations.py)
- Manifest generation (git commit, timestamps, status)
- Dry-run mode
- Force overwrite mode

### Implemented (Remote Execution)
- SSH-based remote execution for activations on GPU nodes
- Automatic GPU selection (finds free GPU via nvidia-smi)
- GPU locking to avoid conflicts on shared nodes
- Rsync/SCP for file upload/download
- Remote log capture and local storage
- Multi-seed batching (download each SAE layer once per batch)
- Limited parallelism across GPUs via configurable max_gpus
- Node grouping step (classification + naming)
- Activations dump to CSV conversion

### CT Steering Swaps (Implemented)
- Full 50x50 swap matrix via `run_batch_swaps.py`
- Dual-graph steering: ablate source concept, amplify target concept
- Stored activations from graph.json (no redundant forward pass)
- Result evaluation with exact match + topk probability metrics
- Aggregation to summary statistics and success matrix
- **Parallel execution** with `--parallel` flag (uses multiple GPUs)
- **Resume capability**: Skips already-completed pairs automatically
- **Tiered classification** with 6-level success metrics
- **Analysis tools**: `analyze_swaps.py`, `browse_swaps.py`
- **Visualizations**: Heatmaps, factor analysis plots

### Not Yet Implemented
- Subgraph upload to Neuronpedia
- API backend for activations
- Per-seed probe prompts mode (per_seed_file)
- Local CT steering execution (remote only for now)

## Remote Execution (Implemented)

Enable remote GPU execution by setting `compute.remote.enabled: true` in your config:

```yaml
compute:
  remote:
    enabled: true
    host_env: "ELEUTHERAI_NODE_IP"  # defined in .env, e.g. ELEUTHERAI_NODE_IP=198.51.100.10
    user: "giuseppe"
    password_env: "ELEUTHERAI_NODE_PSW"  # Or use SSH keys
    base_dir: "/mnt/ssd-1/soar-automated_interpretability/graphs/giuseppe"
    repo_dir: "/mnt/ssd-1/soar-automated_interpretability/graphs/giuseppe/attribution-graph-probing"
    logs_dir: "/mnt/ssd-1/soar-automated_interpretability/graphs/giuseppe/logs"
    env_activate_cmd: "source /mnt/ssd-1/soar-automated_interpretability/graphs/giuseppe/env.sh"
    gpu_selection: auto          # Automatically finds free GPU
    max_gpus: 2                  # Upper bound on concurrent remote batches
    batch_size: 5                # Seeds per remote batch (share the same layer sweep)
    persist_sae_cache: true      # Keep downloaded SAE layers on disk between batches
```

**Features:**
- Automatic free GPU detection via nvidia-smi (mem < 500MB, util < 5%)
- GPU locking (mkdir-based) to avoid conflicts on shared nodes
- Upload inputs (prompts.json, features.json) via scp
- Run activations remotely with proper env setup
- Download results (activations_dump.json, logs) back to laptop
- Automatic GPU lock release on completion or failure
- Batch manifest + per-seed summaries (manifest.json records batch_id/gpu/log paths)
- Configurable SAE cache persistence (reuse clt-hp layers without re-downloading)

### RunPod-specific notes

For pods created on RunPod, use the dedicated config
`configs/usa_states_full_runpod.yml`. There are two ways to prepare pods:

1. **Custom image (preferred)** – build `docker/runpod/Dockerfile`, push it to
   a registry, and point your RunPod template at that image. The entrypoint
   handles sshd (with symmetric port mapping), repo cloning, venv creation, and
   installs `sae-lens`. Full instructions live in
   `docs/runpod_docker.md`.
2. **Manual bootstrap** – copy `scripts/runpod_bootstrap_template.sh` to the
   persistent volume and run it after each restart.

Either way, the config assumes the volume layout below:

- `compute.remote.base_dir: /workspace/graphs/giuseppe`
- `repo_dir: /workspace/graphs/giuseppe/attribution-graph-probing`
- `logs_dir: /workspace/graphs/giuseppe/logs`
- `env_activate_cmd: source /workspace/graphs/giuseppe/env.sh`

Operational checklist:

1. **SSH** – use the proxy command (`ssh <pod-id>@ssh.runpod.io …`) for quick interactive shells. For SCP/automation, copy the “SSH over exposed TCP” host + port from the RunPod UI and set `RUNPOD_HOST` and `RUNPOD_SSH_PORT` in your local shell before running the pipeline.
2. **Bootstrap** – either let the image entrypoint run automatically (option 1)
   or run the bootstrap script once per fresh pod (option 2).
3. **Verify** – SSH into the pod, run
   `source /workspace/graphs/giuseppe/env.sh` followed by
   `python -c "import sae_lens; print('remote env ok')"` to confirm the
   environment matches what `batch_steering.py` expects.

After these steps you can launch both batch runs and steering pilots from your
local machine without touching the pod configuration again.

## Parallel Execution & Resume

### Parallel Mode (Recommended for Large Runs)

```bash
# Run with 8 parallel workers (default)
python run_batch_swaps.py --config configs/usa_states_swap.yml --parallel

# Custom worker count
python run_batch_swaps.py --config configs/usa_states_swap.yml --parallel --max-workers 4
```

**Performance benchmarks (8x A40 GPUs):**
- Sequential: ~85s per swap
- Parallel: ~10-11 swaps/minute
- 50x50 matrix (2450 swaps): ~4 hours

### Resume Behavior

The swap runner **automatically skips completed pairs**:

```
[SKIP] 93 pairs already completed (use --force to re-run)
```

**If interrupted:**
1. Each swap saves results immediately to `by_source/{from}/to_{to}.json`
2. Completed swaps are preserved
3. Re-run the same command to auto-resume
4. Summary/matrix regenerated at end

**To force re-run:**
```bash
python run_batch_swaps.py --config configs/usa_states_swap.yml --force
```

**WARNING:** `--force` overwrites ALL existing results!

## Future Work

### Additional Improvements
Improve scheduler and resume capabilities:

- Smarter queueing/priorities beyond fixed batch_size
- Dynamic scaling when more GPUs become available mid-run

### Additional Features
- Resume from checkpoint (skip completed seeds)
- Progress bars and ETA
- Email/Slack notifications on completion
- Resource monitoring (GPU mem, disk usage)

## Troubleshooting

### Config validation errors
Run with `--dry-run` to validate config before execution:

```bash
python run_batch_from_yaml.py --config my_config.yml --dry-run
```

### Activations fail with OOM
For heavy SAE sets (e.g., clt-hp), ensure `chunk_by_layer: true`:

```yaml
get_activations:
  local:
    chunk_by_layer: true  # Process one layer at a time
```

### File not found errors
Check that:
- Precomputed graph_json paths exist
- Shared prompts_json path exists
- outputs_root directory is writable

### Import errors
Ensure you're running from the repo root or have the repo in PYTHONPATH:

```bash
cd /path/to/circuit_tracer-prompt_rover
python scripts/experiments/batch/run_batch_from_yaml.py --config ...
```

## Examples

### Graph Generation & Activations

```bash
# Dry run (validate only)
python run_batch_from_yaml.py \
  --config configs/usa_states_full.yml \
  --dry-run

# Run full pipeline (50 states)
python run_batch_from_yaml.py \
  --config configs/usa_states_full.yml

# Force rerun (overwrite existing)
python run_batch_from_yaml.py \
  --config configs/usa_states_full.yml \
  --force
```

### CT Steering Swaps

```bash
# Dry run (validate and show plan)
python run_batch_swaps.py \
  --config configs/usa_states_swap.yml \
  --dry-run

# Run single pair (for testing)
python run_batch_swaps.py \
  --config configs/usa_states_swap.yml \
  --pair texas_dallas:california_oakland

# Run full 50x50 matrix (2500 experiments)
python run_batch_swaps.py \
  --config configs/usa_states_swap.yml

# Force rerun all swaps
python run_batch_swaps.py \
  --config configs/usa_states_swap.yml \
  --force
```

### Two-Phase Workflow

The typical workflow is:

```bash
# Phase 1: Generate graphs (run once)
python run_batch_from_yaml.py --config configs/usa_states_full.yml

# Phase 2: Run swap experiments (can run multiple times with different params)
python run_batch_swaps.py --config configs/usa_states_swap.yml --parallel

# Re-run with different M values
# Edit usa_states_swap.yml: M_amplify: 5.0
python run_batch_swaps.py --config configs/usa_states_swap.yml --force
```

### Full 50x50 Run Checklist

Before running a large swap matrix:

```bash
# 1. Preview all states (army parade)
python army_parade.py

# 2. Dry run to validate config
python run_batch_swaps.py --config configs/usa_states_swap.yml --dry-run --parallel

# 3. Check how many pairs will be skipped (already done)
# Output will show: "[SKIP] N pairs already completed"

# 4. Run with parallel execution (NO --force to preserve existing!)
python run_batch_swaps.py --config configs/usa_states_swap.yml --parallel

# 5. After completion, run analysis
python analyze_swaps.py --output-dir _analysis_50x50
python ../../../visualization/swap_heatmap.py
python ../../../visualization/swap_factor_analysis.py
```

**Time estimate for 50x50:**
- ~2,450 swap pairs
- ~10 swaps/minute with 8 GPUs
- **~4 hours total**

## Contributing

When adding new features:

1. Add config schema to YAML (with defaults)
2. Update `pipeline/loader.py` validation
3. Implement in relevant pipeline module
4. Update this README
5. Add example to configs/

## License

GPL-3.0 - See LICENSE file for details

