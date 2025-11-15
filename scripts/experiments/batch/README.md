# Batch Experiment Runner

Automated pipeline for running attribution graph experiments at scale from YAML configs.

## Quick Start

```bash
# Validate config (dry run)
python run_batch_from_yaml.py --config configs/usa_capitals_swap_full.yml --dry-run

# Run batch experiment
python run_batch_from_yaml.py --config configs/usa_capitals_swap_full.yml

# Force overwrite existing outputs
python run_batch_from_yaml.py --config configs/usa_capitals_swap_full.yml --force
```

## Directory Structure

```
scripts/experiments/batch/
├── configs/                          # YAML experiment configs
│   └── usa_capitals_swap_full.yml   # Example config
├── pipeline/                         # Pipeline modules
│   ├── loader.py                    # Config loading and validation
│   ├── graph.py                     # Graph generation and feature selection
│   ├── probes.py                    # Probe prompts handling
│   ├── activations_local.py         # Local activations processing
│   └── manifest.py                  # Experiment manifest generation
├── run_batch_from_yaml.py           # Main CLI runner
└── README.md                        # This file
```

## Per-Seed Output Structure

Each seed produces a standardized folder structure:

```
outputs_root/{slug}/
├── manifest.json                    # Run metadata (timestamp, git commit, status)
├── 00 Graph Generation/
│   ├── graph.json                   # Attribution graph from Neuronpedia
│   ├── graph_feature_static_metrics.csv
│   └── selected_features_with_nodes.json
├── 01 Prompt Probing/
│   ├── prompts.json                 # Probe prompts
│   └── activations_dump.json        # Feature activations
└── 02 Node Grouping/                # (future)
    └── node_grouping.csv
```

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
- Node grouping step (classification + naming)
- Activations dump to CSV conversion

### Not Yet Implemented
- Parallel seed processing (currently sequential)
- Subgraph upload to Neuronpedia
- API backend for activations
- Per-seed probe prompts mode (per_seed_file)

## Remote Execution (Implemented)

Enable remote GPU execution by setting `compute.remote.enabled: true` in your config:

```yaml
compute:
  remote:
    enabled: true
    host: "207.53.234.140"
    user: "giuseppe"
    password_env: "ELEUTHERAI_NODE_PSW"  # Or use SSH keys
    base_dir: "/mnt/ssd-1/soar-automated_interpretability/graphs/giuseppe"
    repo_dir: "/mnt/ssd-1/soar-automated_interpretability/graphs/giuseppe/attribution-graph-probing"
    logs_dir: "/mnt/ssd-1/soar-automated_interpretability/graphs/giuseppe/logs"
    env_activate_cmd: "source /mnt/ssd-1/soar-automated_interpretability/graphs/giuseppe/env.sh"
    use_gpu_count: 1
    gpu_selection: auto  # Automatically finds free GPU
```

**Features:**
- Automatic free GPU detection via nvidia-smi (mem < 500MB, util < 5%)
- GPU locking (mkdir-based) to avoid conflicts on shared nodes
- Upload inputs (prompts.json, features.json) via scp
- Run activations remotely with proper env setup
- Download results (activations_dump.json, logs) back to laptop
- Automatic GPU lock release on completion or failure

## Future Work

### Parallel Seed Processing
Run multiple seeds concurrently (one per GPU):

- Distribute seeds across available GPUs
- Monitor GPU availability in real-time
- Queue seeds when all GPUs busy

### Additional Features
- Resume from checkpoint (skip completed seeds)
- Parallel seed processing
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

### Dry Run (Validate Only)
```bash
python run_batch_from_yaml.py \
  --config configs/usa_capitals_swap_full.yml \
  --dry-run
```

### Run with Precomputed Graphs
```bash
# 1. Generate graphs via Streamlit (00 Graph Generation page)
# 2. Update config with graph_json paths
# 3. Run batch
python run_batch_from_yaml.py \
  --config configs/usa_capitals_swap_full.yml
```

### Entity Swap Experiment
```bash
# Config with templated seeds and probes
python run_batch_from_yaml.py \
  --config configs/entity_swap_states.yml
```

### Force Rerun
```bash
# Overwrite existing outputs
python run_batch_from_yaml.py \
  --config configs/usa_capitals_swap_full.yml \
  --force
```

## Contributing

When adding new features:

1. Add config schema to YAML (with defaults)
2. Update `pipeline/loader.py` validation
3. Implement in relevant pipeline module
4. Update this README
5. Add example to configs/

## License

GPL-3.0 - See LICENSE file for details

