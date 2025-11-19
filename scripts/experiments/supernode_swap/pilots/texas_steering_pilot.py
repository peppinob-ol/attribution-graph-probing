#!/usr/bin/env python3
"""
Texas-only steering pilot.

This script:
  1. Extracts the "texas" supernode features from existing graph/grouping files.
  2. Generates prompts/features JSON files for batch_steering.py.
  3. Uses the remote steering helper to run the steering batch on the GPU node.
  4. Prints a short summary of the steered/default outputs.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

import importlib.util
import sys

import pandas as pd
import yaml

SCRIPTS_DIR = Path(__file__).resolve().parents[3]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from experiments.batch.pipeline.steering_remote import process_remote_steering_step


def _load_steering_module():
    module_path = SCRIPTS_DIR / "03_neuronpedia_steering.py"
    spec = importlib.util.spec_from_file_location("neuronpedia_steering", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module at {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("neuronpedia_steering", module)
    spec.loader.exec_module(module)
    return module


steering = _load_steering_module()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Texas steering pilot via remote GPU.")
    parser.add_argument(
        "--config",
        default="scripts/experiments/batch/configs/usa_states_full.yml",
        help="Batch config YAML (used to read model + remote settings).",
    )
    parser.add_argument("--slug", default="texas_Dallas", help="Seed slug")
    parser.add_argument(
        "--prompt",
        default="The capital of the state containing Dallas is",
        help="Prompt text",
    )
    parser.add_argument("--concept", default="texas", help="Supernode concept to steer")
    parser.add_argument(
        "--outputs-dir",
        default="output/steering_pilots/texas",
        help="Directory to store prompts/features/results",
    )
    parser.add_argument(
        "--M",
        type=float,
        default=-2.0,
        help="Multiplicative factor for compute_supernode_strengths",
    )
    parser.add_argument(
        "--target-token",
        default=" Austin",
        help="Token string whose logprob delta we want to inspect",
    )
    return parser.parse_args()


def load_config(path: str) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def derive_paths(slug: str) -> Dict[str, Path]:
    base = Path(f"output/usa_states_batch/{slug}")
    grouping = base / "02 Node Grouping" / "node_grouping.csv"
    metrics = base / "00 Graph Generation" / "graph_feature_static_metrics.csv"
    if not grouping.exists() or not metrics.exists():
        raise FileNotFoundError(
            f"Grouping or metrics not found for slug '{slug}'. "
            f"Expected {grouping} and {metrics}"
        )
    return {"grouping": grouping, "metrics": metrics}


def prepare_feature_json(
    grouping_path: Path,
    metrics_path: Path,
    concept: str,
    slug: str,
    source_set: str,
    M: float,
) -> Dict[str, Any]:
    grouping_df = pd.read_csv(grouping_path)
    metrics_df = pd.read_csv(metrics_path)
    supernode = steering.extract_concept_supernode(
        grouping_df=grouping_df, metrics_df=metrics_df, concept=concept, slug=slug
    )
    payload = steering.compute_supernode_strengths(
        supernode, M=M, source_set=source_set, ensure_non_empty=True
    )
    features = [
        {"source": item["layer"], "index": item["index"], "strength": float(item["strength"])}
        for item in payload
    ]
    return {"global": features}


def write_prompts_file(path: Path, slug: str, prompt: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump([{"id": slug, "text": prompt}], f, ensure_ascii=False, indent=2)


def write_features_file(path: Path, data: Dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def main() -> None:
    args = parse_args()
    config = load_config(args.config)
    model_cfg = config["model"]
    source_set = model_cfg["source_set"]

    # Ensure steering config exists and default to CPU-backed steering for pilots
    steering_cfg = config.setdefault("steering", {})
    steering_cfg.setdefault("device", "cpu")
    steering_cfg.setdefault("n_tokens", 4)

    slug_paths = derive_paths(args.slug)
    outputs_dir = Path(args.outputs_dir)
    prompts_path = outputs_dir / "prompts.json"
    features_path = outputs_dir / "features.json"
    result_path = outputs_dir / "steering_dump.json"

    feature_json = prepare_feature_json(
        slug_paths["grouping"],
        slug_paths["metrics"],
        args.concept,
        args.slug,
        source_set,
        args.M,
    )
    write_prompts_file(prompts_path, args.slug, args.prompt)
    write_features_file(features_path, feature_json)

    paths = {
        "prompts_json": prompts_path,
        "steering_features_json": features_path,
        "steering_dump_json": result_path,
        "base": outputs_dir,
    }
    seed = {"slug": args.slug}

    success, metadata = process_remote_steering_step(
        config, seed, paths, verbose=True
    )
    if not success:
        print("Steering run failed.")
        return

    print(f"Remote steering completed. Metadata: {metadata}")
    if not result_path.exists():
        print(f"Result file not found at {result_path}")
        return

    with open(result_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not data.get("results"):
        print("No results in steering_dump.json")
        return

    entry = data["results"][0]
    print(f"\nPrompt: {entry['prompt']}")
    print(f"STEERED:\n{entry.get('steered')}\n")
    print(f"DEFAULT:\n{entry.get('default')}\n")

    def find_token_logprob(logprobs, token):
        if not logprobs:
            return None
        for item in logprobs:
            if item.get("token") == token:
                return item.get("logprob")
        return None

    steered_lp = find_token_logprob(entry.get("steered_logprobs"), args.target_token)
    default_lp = find_token_logprob(entry.get("default_logprobs"), args.target_token)
    if steered_lp is not None and default_lp is not None:
        delta = steered_lp - default_lp
        print(
            f"Token '{args.target_token}': steered logprob={steered_lp:.4f}, "
            f"default logprob={default_lp:.4f}, delta={delta:.4f}"
        )
    else:
        print("Token logprobs not available for comparison.")


if __name__ == "__main__":
    main()


