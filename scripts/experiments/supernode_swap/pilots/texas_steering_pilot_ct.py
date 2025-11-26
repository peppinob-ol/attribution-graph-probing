#!/usr/bin/env python3
"""
Texas Supernode Steering Pilot - Circuit Tracer Version

This pilot script orchestrates steering experiments using Circuit Tracer's
ReplacementModel.feature_intervention_generate() instead of SAE-based steering.

Key differences from texas_steering_pilot.py:
1. Uses batch_steering_ct.py instead of batch_steering.py
2. Features format: {layer, index, position, delta, ablate} instead of {source, index, strength}
3. Directly accesses CLT decoder vectors that write to ALL subsequent layers
4. Supports freeze_attention for constrained patching (mechanistic faithfulness)

This script can run:
- Locally (with GPU and circuit_tracer installed)
- Remotely via ELEUTHERAI_NODE (using steering_remote_ct.py)
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import yaml

# -------------------------------------------------------------------
# Path setup
# -------------------------------------------------------------------
SCRIPTS_DIR = Path(__file__).resolve().parent.parent.parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

# Config paths
EXPERIMENT_DIR = Path(__file__).resolve().parent.parent
GRAPHS_DIR = SCRIPTS_DIR.parent / "graphs"
OUTPUT_DIR = EXPERIMENT_DIR / "output" / "ct_results"

# Remote execution support
from experiments.batch.pipeline.steering_remote_ct import process_remote_ct_steering_step


def _load_ct_steering_module():
    """Load 03_ct_steering.py module dynamically."""
    steering_path = SCRIPTS_DIR / "03_ct_steering.py"
    spec = importlib.util.spec_from_file_location("ct_steering", steering_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {steering_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ct_steering"] = module
    spec.loader.exec_module(module)
    return module


# -------------------------------------------------------------------
# Configuration
# -------------------------------------------------------------------

DEFAULT_CONFIG = {
    "model_id": "google/gemma-2-2b",
    "transcoder_set": "mntss/clt-gemma-2-2b-2.5M",  # 2.5M features CLT (matches Neuronpedia graphs)
    "concepts": {
        "from": "texas",      # Concept to ablate (from graph_dir)
        "to": "california",   # Concept to amplify (from graph_dir_to)
    },
    "steering": {
        "M_ablate": -2,      # Multiplier for 'from' (0=ablate, -1=reverse, etc.)
        "M_amplify": 20,     # Multiplier for 'to' (2=double)
        "temperature": 0.3,
        "n_tokens": 3,
        "freq_penalty": 2.0,
        "seed": 42,
        "freeze_attention": False,
        "top_k": 5,
        "steer_generated_tokens": True,
    },
    "slug": "texas_to_california",
    "graph_dir": "output/usa_states_batch/texas_Dallas",           # Graph for ablation (texas)
    "graph_dir_to": "output/usa_states_batch/california_Oakland",  # Graph for amplification (california)
}


# -------------------------------------------------------------------
# Data loading helpers
# -------------------------------------------------------------------


def load_graph_data(graph_dir: Path) -> Dict[str, Any]:
    """Load all data from a graph directory.
    
    Supports two directory structures:
    1. Batch pipeline structure:
       - {graph_dir}/02 Node Grouping/node_grouping.csv
       - {graph_dir}/00 Graph Generation/graph_feature_static_metrics.csv
       - {graph_dir}/00 Graph Generation/graph.json
    2. Flat structure:
       - {graph_dir}/node_grouping.csv
       - {graph_dir}/graph_feature_static_metrics.csv
       - {graph_dir}/graph.json
    
    Returns:
        Dict with 'grouping', 'metrics' DataFrames and 'prompt' string from graph.json
    """
    # Try batch pipeline structure first
    grouping_path = graph_dir / "02 Node Grouping" / "node_grouping.csv"
    metrics_path = graph_dir / "00 Graph Generation" / "graph_feature_static_metrics.csv"
    graph_json_path = graph_dir / "00 Graph Generation" / "graph.json"
    
    # Fall back to flat structure
    if not grouping_path.exists():
        grouping_path = graph_dir / "node_grouping.csv"
    if not metrics_path.exists():
        metrics_path = graph_dir / "graph_feature_static_metrics.csv"
    if not graph_json_path.exists():
        graph_json_path = graph_dir / "graph.json"
    
    if not grouping_path.exists():
        raise FileNotFoundError(f"Node grouping not found: {grouping_path}")
    if not metrics_path.exists():
        raise FileNotFoundError(f"Feature metrics not found: {metrics_path}")
    
    # Load prompt and activations from graph.json
    prompt = None
    activations_map = {}  # {(layer, feature, position): activation_value}
    
    if graph_json_path.exists():
        with open(graph_json_path, "r", encoding="utf-8") as f:
            graph_data = json.load(f)
        
        # Extract prompt
        prompt = graph_data.get("metadata", {}).get("prompt")
        if prompt:
            print(f"  [PROMPT] Loaded from graph.json: {prompt[:60]}...")
        
        # Extract activations from nodes by parsing node_id
        # node_id format: "{layer}_{feature}_{position}" e.g., "0_1861_7"
        nodes = graph_data.get("nodes", [])
        for node in nodes:
            node_id = node.get("node_id", "")
            activation = node.get("activation")
            if node_id and activation is not None:
                parts = node_id.split("_")
                if len(parts) >= 3:
                    try:
                        layer = int(parts[0])
                        feature = int(parts[1])
                        position = int(parts[2])
                        activations_map[(layer, feature, position)] = float(activation)
                    except (ValueError, IndexError):
                        pass  # Skip malformed node_ids
        
        if activations_map:
            print(f"  [ACTIVATIONS] Loaded {len(activations_map)} stored activations from graph.json")
    
    return {
        "grouping": pd.read_csv(grouping_path),
        "metrics": pd.read_csv(metrics_path),
        "prompt": prompt,
        "activations_map": activations_map,  # Stored activations from graph
        "graph_dir": graph_dir,
    }


def load_prompts(prompt_file: Path) -> List[Dict[str, str]]:
    """Load prompts from JSON file (legacy, for probe prompts)."""
    if not prompt_file.exists():
        raise FileNotFoundError(f"Prompt file not found: {prompt_file}")
    with open(prompt_file, "r", encoding="utf-8") as f:
        data = json.load(f)
    # Normalize to list of {id, text}
    if isinstance(data, list):
        if data and isinstance(data[0], str):
            return [{"id": str(i), "text": text} for i, text in enumerate(data)]
        return data
    raise ValueError("Invalid prompt file format")


# -------------------------------------------------------------------
# Feature preparation for CT
# -------------------------------------------------------------------


def prepare_ct_features_json(
    ct_steering,
    data_from: Dict[str, Any],
    data_to: Optional[Dict[str, Any]],
    concept_from: str,
    concept_to: Optional[str],
    slug: str,
    M_ablate: float,
    M_amplify: float,
    steer_generated_tokens: bool,
) -> List[Dict[str, Any]]:
    """
    Prepare CT intervention features for batch_steering_ct.py.
    
    Supports dual-graph loading:
    - data_from: Graph data for the 'from' concept (to ablate)
    - data_to: Graph data for the 'to' concept (to amplify) - can be same or different graph

    Returns feature list in CT format:
    [
        {"layer": 7, "index": 123, "position": -1, "M": 0.0, "stored_activation": 1.84},
        ...
    ]
    
    Note: M can be negative (e.g., -2.0 to reverse direction), zero (ablate), or positive (amplify).
    When stored_activation is present, batch_steering_ct.py can skip get_activations().
    """
    features = []

    # Extract 'from' supernode for ablation (from graph_from)
    if concept_from:
        try:
            supernode_from = ct_steering.extract_ct_supernode(
                grouping_df=data_from["grouping"],
                metrics_df=data_from["metrics"],
                concept=concept_from,
                slug=slug,
            )
            # Pass activations_map from graph.json if available
            activations_map_from = data_from.get("activations_map", {})
            from_interventions = ct_steering.compute_ct_interventions(
                supernode_from, 
                M_ablate, 
                steer_generated_tokens=steer_generated_tokens,
                activations_map=activations_map_from if activations_map_from else None,
            )
            features.extend(from_interventions)
            n_with_stored = sum(1 for f in from_interventions if "stored_activation" in f)
            print(f"  [ABLATE] '{concept_from}' from {data_from.get('graph_dir', 'graph_from')}: "
                  f"{len(from_interventions)} features (M={M_ablate}, {n_with_stored} with stored activation)")
        except ValueError as e:
            print(f"  Warning: Could not extract '{concept_from}' supernode: {e}")

    # Extract 'to' supernode for amplification (from graph_to, which may be different!)
    if concept_to and data_to:
        try:
            supernode_to = ct_steering.extract_ct_supernode(
                grouping_df=data_to["grouping"],
                metrics_df=data_to["metrics"],
                concept=concept_to,
                slug=slug,
            )
            # Pass activations_map from graph.json if available
            activations_map_to = data_to.get("activations_map", {})
            to_interventions = ct_steering.compute_ct_interventions(
                supernode_to, 
                M_amplify, 
                steer_generated_tokens=steer_generated_tokens,
                activations_map=activations_map_to if activations_map_to else None,
            )
            features.extend(to_interventions)
            n_with_stored = sum(1 for f in to_interventions if "stored_activation" in f)
            print(f"  [AMPLIFY] '{concept_to}' from {data_to.get('graph_dir', 'graph_to')}: "
                  f"{len(to_interventions)} features (M={M_amplify}, {n_with_stored} with stored activation)")
        except ValueError as e:
            print(f"  Warning: Could not extract '{concept_to}' supernode: {e}")

    return features


# -------------------------------------------------------------------
# Local execution (requires circuit_tracer)
# -------------------------------------------------------------------


def run_local_ct_steering(
    prompts: List[Dict[str, str]],
    features: List[Dict[str, Any]],
    config: Dict[str, Any],
) -> Dict[str, Any]:
    """Run CT steering locally using batch_steering_ct.py logic."""
    try:
        from circuit_tracer.replacement_model import ReplacementModel
    except ImportError:
        raise ImportError(
            "circuit_tracer not installed. Install via: "
            "pip install git+https://github.com/anthropics/circuit-tracer.git"
        )
    
    import torch
    
    # Load model
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.bfloat16 if device.type == "cuda" else torch.float32
    
    print(f"Loading ReplacementModel: {config['model_id']}")
    model = ReplacementModel.from_pretrained(
        config["model_id"],
        config["transcoder_set"],
        device=device,
        dtype=dtype,
    )
    
    # Import batch steering utilities
    steering_utils_path = SCRIPTS_DIR / "neuronpedia_steering" / "batch_steering_ct.py"
    spec = importlib.util.spec_from_file_location("batch_steering_ct", steering_utils_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load {steering_utils_path}")
    batch_ct = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(batch_ct)
    
    # Parse features
    ct_features = batch_ct._normalize_ct_feature_list(features)
    
    results = []
    steer_cfg = config["steering"]
    
    for prompt_item in prompts:
        prompt_id = prompt_item["id"]
        text = prompt_item["text"]
        
        print(f"Processing: {prompt_id}")
        
        raw = batch_ct.run_ct_generation(
            text,
            ct_features,
            model,
            seed=steer_cfg["seed"],
            temperature=steer_cfg["temperature"],
            freq_penalty=steer_cfg["freq_penalty"],
            max_new_tokens=steer_cfg["n_tokens"],
            freeze_attention=steer_cfg["freeze_attention"],
            top_k=steer_cfg["top_k"],
        )
        
        results.append({
            "probe_id": prompt_id,
            "prompt": text,
            "steered": raw["steered"],
            "default": raw["default"],
            "steered_topk": raw.get("steered_topk", []),
            "default_topk": raw.get("default_topk", []),
            "intervention_count": raw["intervention_count"],
        })
    
    return {
        "model": config["model_id"],
        "transcoder_set": config["transcoder_set"],
        "n_prompts": len(results),
        "results": results,
        "config": steer_cfg,
    }


# -------------------------------------------------------------------
# Remote execution (via ELEUTHERAI_NODE)
# -------------------------------------------------------------------


def load_remote_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """
    Load remote execution config from YAML.
    
    Looks for config in order:
    1. Provided config_path
    2. scripts/experiments/batch/configs/usa_capitals_swap_full.yml
    3. scripts/experiments/batch/configs/test_dallas_single.yml
    """
    search_paths = [
        config_path,
        SCRIPTS_DIR / "experiments" / "batch" / "configs" / "usa_capitals_swap_full.yml",
        SCRIPTS_DIR / "experiments" / "batch" / "configs" / "test_dallas_single.yml",
    ]
    
    for path in search_paths:
        if path and path.exists():
            with open(path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f)
    
    raise FileNotFoundError("No remote config file found. Provide --remote-config")


def execute_remote_ct_steering(
    work_dir: Path,
    config: Dict[str, Any],
    remote_config_path: Optional[Path] = None,
) -> Optional[Dict[str, Any]]:
    """
    Execute CT steering on ELEUTHERAI_NODE via SSH.
    
    Args:
        work_dir: Directory with prepared prompts.json and features.json
        config: Experiment config (model, steering params)
        remote_config_path: Path to YAML with compute.remote section
    
    Returns:
        Results dict or None if remote execution failed
    """
    # Load remote config
    remote_cfg = load_remote_config(remote_config_path)
    
    # Ensure remote is enabled
    if not remote_cfg.get("compute", {}).get("remote", {}).get("enabled"):
        # Enable it for this run
        remote_cfg.setdefault("compute", {}).setdefault("remote", {})["enabled"] = True
    
    # Merge CT steering config into remote config
    remote_cfg["ct_steering"] = {
        "transcoder_set": config.get("transcoder_set", "gemma"),
        "temperature": config["steering"]["temperature"],
        "n_tokens": config["steering"]["n_tokens"],
        "freq_penalty": config["steering"]["freq_penalty"],
        "seed": config["steering"]["seed"],
        "top_k": config["steering"]["top_k"],
        "freeze_attention": config["steering"].get("freeze_attention", False),
    }
    
    # Merge model config
    remote_cfg.setdefault("model", {})["id"] = config.get("model_id", "google/gemma-2-2b")
    
    # Prepare paths for remote executor
    prompts_path = work_dir / "prompts.json"
    features_path = work_dir / "features.json"
    output_path = work_dir / "steering_dump.json"
    
    if not prompts_path.exists() or not features_path.exists():
        raise FileNotFoundError("Input files not prepared. Run prepare step first.")
    
    paths = {
        "prompts_json": prompts_path,
        "steering_features_json": features_path,
        "steering_dump_json": output_path,
        "base": work_dir,
    }
    
    seed = {"slug": config.get("slug", "ct_pilot")}
    
    print(f"[REMOTE-CT] Executing on ELEUTHERAI_NODE...")
    print(f"  Model: {remote_cfg['model']['id']}")
    print(f"  Transcoder: {remote_cfg['ct_steering']['transcoder_set']}")
    
    success, metadata = process_remote_ct_steering_step(
        remote_cfg, seed, paths, verbose=True
    )
    
    if not success:
        print("ERROR: Remote CT steering failed")
        return None
    
    # Load results
    if output_path.exists():
        with open(output_path, "r", encoding="utf-8") as f:
            results = json.load(f)
        results["_metadata"] = metadata
        return results
    
    print("ERROR: Results file not found after remote execution")
    return None


# -------------------------------------------------------------------
# Main experiment flow
# -------------------------------------------------------------------


def run_experiment(
    config: Dict[str, Any],
    *,
    local: bool = True,
    dry_run: bool = False,
    remote_config_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """
    Run the full CT steering experiment.
    
    Args:
        config: Experiment configuration
        local: If True, run locally. If False, attempt remote execution via ELEUTHERAI_NODE.
        dry_run: If True, only prepare files without executing.
        remote_config_path: Path to YAML config with compute.remote section
    
    Returns:
        Experiment results
    """
    ct_steering = _load_ct_steering_module()
    
    # Setup output directory
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    work_dir = OUTPUT_DIR / f"run_{timestamp}"
    work_dir.mkdir(parents=True, exist_ok=True)
    
    print(f"Experiment work directory: {work_dir}")
    
    # -------------------------------------------------------------------------
    # DUAL-GRAPH LOADING
    # -------------------------------------------------------------------------
    # graph_dir: Source graph for ABLATION (concept_from)
    # graph_dir_to: Target graph for AMPLIFICATION (concept_to) - optional, different graph
    
    graph_dir_from = Path(config["graph_dir"])
    graph_dir_to_str = config.get("graph_dir_to")
    graph_dir_to = Path(graph_dir_to_str) if graph_dir_to_str else None
    
    print(f"\n[GRAPH FROM] Loading ablation graph: {graph_dir_from}")
    data_from = load_graph_data(graph_dir_from)
    
    data_to = None
    if graph_dir_to and graph_dir_to != graph_dir_from:
        print(f"[GRAPH TO] Loading amplification graph: {graph_dir_to}")
        data_to = load_graph_data(graph_dir_to)
    elif config["concepts"].get("to"):
        # Same graph for both concepts
        print(f"[GRAPH TO] Using same graph for amplification")
        data_to = data_from
    
    # -------------------------------------------------------------------------
    # PROMPT: Use the original attribution prompt from graph.json
    # -------------------------------------------------------------------------
    prompt_text = data_from.get("prompt")
    if not prompt_text:
        # Fallback: try to load from prompts.json (legacy)
        prompts_file = graph_dir_from / "01 Prompt Probing" / "prompts.json"
        if not prompts_file.exists():
            prompts_file = graph_dir_from / "prompts.json"
        if prompts_file.exists():
            legacy_prompts = load_prompts(prompts_file)
            prompt_text = legacy_prompts[0]["text"] if legacy_prompts else None
            print(f"  [PROMPT] Fallback to prompts.json: {prompt_text[:60] if prompt_text else 'None'}...")
    
    if not prompt_text:
        prompt_text = f"The capital of the state containing Dallas is"
        print(f"  [PROMPT] Using hardcoded default: {prompt_text}")
    
    # Create single prompt for the experiment (using graph.json prompt)
    prompts = [{"id": "graph_prompt", "text": prompt_text}]
    print(f"\n[EXPERIMENT PROMPT] {prompt_text}")
    
    # -------------------------------------------------------------------------
    # PREPARE CT FEATURES (dual-graph aware)
    # -------------------------------------------------------------------------
    print("\nPreparing CT intervention features...")
    features = prepare_ct_features_json(
        ct_steering=ct_steering,
        data_from=data_from,
        data_to=data_to,
        concept_from=config["concepts"]["from"],
        concept_to=config["concepts"].get("to"),
        slug=config["slug"],
        M_ablate=config["steering"]["M_ablate"],
        M_amplify=config["steering"]["M_amplify"],
        steer_generated_tokens=config["steering"]["steer_generated_tokens"],
    )
    
    print(f"Total CT interventions: {len(features)}")
    
    # Save prepared files
    prompts_path = work_dir / "prompts.json"
    features_path = work_dir / "features.json"
    config_path = work_dir / "config.json"
    
    with open(prompts_path, "w", encoding="utf-8") as f:
        json.dump(prompts, f, indent=2)
    with open(features_path, "w", encoding="utf-8") as f:
        json.dump(features, f, indent=2)
    with open(config_path, "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    
    print(f"\nPrepared files:")
    print(f"  - {prompts_path}")
    print(f"  - {features_path}")
    print(f"  - {config_path}")
    
    if dry_run:
        print("\n[DRY RUN] Skipping execution.")
        return {"status": "dry_run", "work_dir": str(work_dir)}
    
    # Execute steering
    print("\n" + "=" * 60)
    print("EXECUTING CT STEERING")
    print("=" * 60)
    
    if local:
        results = run_local_ct_steering(prompts, features, config)
    else:
        # Remote execution via ELEUTHERAI_NODE
        results = execute_remote_ct_steering(work_dir, config, remote_config_path)
        if results is None:
            print("Remote execution failed. Falling back to local.")
            results = run_local_ct_steering(prompts, features, config)
    
    # Save results (may overwrite if remote already saved)
    output_path = work_dir / "steering_dump.json"
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    
    print(f"\n[OK] Results saved to: {output_path}")
    
    # Print summary
    print("\n" + "=" * 60)
    print("RESULTS SUMMARY")
    print("=" * 60)
    for r in results.get("results", []):
        print(f"\n--- {r['probe_id']} ---")
        print(f"Prompt: {r['prompt'][:50]}...")
        print(f"Default: {r['default'][:100]}...")
        print(f"Steered: {r['steered'][:100]}...")
        print(f"Interventions: {r['intervention_count']}")
    
    return results


def main():
    parser = argparse.ArgumentParser(
        description="Texas CT Steering Pilot - Circuit Tracer based steering"
    )
    parser.add_argument(
        "--config",
        type=Path,
        help="Path to JSON config file (overrides defaults)",
    )
    parser.add_argument(
        "--remote-config",
        type=Path,
        help="Path to YAML config with compute.remote section (for ELEUTHERAI_NODE)",
    )
    parser.add_argument(
        "--graph-dir",
        type=Path,
        help="Path to graph directory for ablation (concept-from)",
    )
    parser.add_argument(
        "--graph-dir-to",
        type=Path,
        help="Path to DIFFERENT graph for amplification (concept-to). If not provided, uses --graph-dir.",
    )
    parser.add_argument(
        "--concept-from",
        type=str,
        help="Concept to ablate (from --graph-dir)",
    )
    parser.add_argument(
        "--concept-to",
        type=str,
        help="Concept to amplify (from --graph-dir-to or --graph-dir)",
    )
    parser.add_argument(
        "--M-ablate",
        type=float,
        help="Ablation multiplier (0=full ablate)",
    )
    parser.add_argument(
        "--M-amplify",
        type=float,
        help="Amplification multiplier (2=double)",
    )
    parser.add_argument(
        "--freeze-attention",
        action="store_true",
        help="Freeze attention patterns during intervention",
    )
    parser.add_argument(
        "--local",
        action="store_true",
        default=True,
        help="Run locally (default)",
    )
    parser.add_argument(
        "--remote",
        action="store_true",
        help="Run on remote GPU via ELEUTHERAI_NODE",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Prepare files only, don't execute",
    )
    
    args = parser.parse_args()
    
    # Load config
    config = dict(DEFAULT_CONFIG)
    if args.config and args.config.exists():
        with open(args.config, "r", encoding="utf-8") as f:
            user_config = json.load(f)
        # Merge
        for key, val in user_config.items():
            if isinstance(val, dict) and key in config:
                config[key].update(val)
            else:
                config[key] = val
    
    # Apply CLI overrides
    if args.graph_dir:
        config["graph_dir"] = str(args.graph_dir)
    if args.graph_dir_to:
        config["graph_dir_to"] = str(args.graph_dir_to)
    if args.concept_from:
        config["concepts"]["from"] = args.concept_from
    if args.concept_to:
        config["concepts"]["to"] = args.concept_to
    if args.M_ablate is not None:
        config["steering"]["M_ablate"] = args.M_ablate
    if args.M_amplify is not None:
        config["steering"]["M_amplify"] = args.M_amplify
    if args.freeze_attention:
        config["steering"]["freeze_attention"] = True
    
    # Run
    local = not args.remote
    run_experiment(
        config,
        local=local,
        dry_run=args.dry_run,
        remote_config_path=args.remote_config,
    )


if __name__ == "__main__":
    main()

