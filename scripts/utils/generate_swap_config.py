"""
Generate YAML configs for the swap pipeline from a validated dataset.

Produces two files matching the existing pipeline format:
  - {name}_full.yml   (graph generation + probes + entities)
  - {name}_swap.yml   (references full config, matrix swap mode)

Usage:
    python -m scripts.utils.generate_swap_config scripts/utils/datasets/songs_lead_singers_validated.json
    python -m scripts.utils.generate_swap_config scripts/utils/datasets/*_validated.json
    python -m scripts.utils.generate_swap_config scripts/utils/datasets
    python -m scripts.utils.generate_swap_config songs_validated.json --output-dir scripts/experiments/batch/configs
"""

import argparse
import glob
import json
from pathlib import Path

import yaml


DEFAULT_OUTPUT_DIR = "scripts/experiments/batch/configs"


def generate_configs(dataset_path: str, output_dir: str | None = None):
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    name = dataset["name"]
    n_entities = len(dataset["entities"])

    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    full_config = _build_full_config(dataset)
    swap_config = _build_swap_config(name)

    full_path = out / f"{name}_full.yml"
    swap_path = out / f"{name}_swap.yml"

    _write_yaml(full_path, full_config)
    _write_yaml(swap_path, swap_config)

    print(f"Generated : {full_path}")
    print(f"Generated : {swap_path}")
    print(f"Entities  : {n_entities}")
    print(f"Matrix    : {n_entities}x{n_entities} = {n_entities**2} swap pairs")


def resolve_dataset_paths(dataset_inputs: list[str]) -> list[Path]:
    paths: list[Path] = []

    for dataset_input in dataset_inputs:
        input_path = Path(dataset_input)

        if input_path.is_dir():
            matches = sorted(input_path.glob("*_validated.json"))
        else:
            matches = [Path(match) for match in sorted(glob.glob(dataset_input))]

        if matches:
            paths.extend(match for match in matches if match.is_file())
            continue

        if input_path.is_file():
            paths.append(input_path)
            continue

        raise FileNotFoundError(
            f"No dataset files found for input: {dataset_input}"
        )

    unique_paths: list[Path] = []
    seen: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique_paths.append(path)

    if not unique_paths:
        raise FileNotFoundError("No dataset files found.")

    return unique_paths


def _build_full_config(dataset: dict) -> dict:
    name = dataset["name"]
    return {
        "version": 0.1,
        "experiment_name": f"{name}_batch",
        "paths": {"outputs_root": f"output/{name}_batch"},
        "model": {"id": "gemma-2-2b", "source_set": "clt-hp"},
        "features": {
            "selection": "cumulative_influence",
            "threshold": 0.95,
            "post_filter": {"node_threshold": 95},
        },
        "probes": {
            "mode": "templated",
            "templated": {"templates": dataset.get("probe_templates", [])},
        },
        "graph_generation": {
            "enabled": True,
            "seeds_mode": "templated",
            "templated": {
                "seed_prompt": dataset["seed_prompt_template"],
                "slug_template": "{slug}",
                "entities": {"items": dataset["entities"]},
            },
        },
    }


def _build_swap_config(name: str) -> dict:
    return {
        "version": 0.1,
        "experiment_name": f"{name}_swap",
        "inputs": {
            "source_config": f"configs/{name}_full.yml",
            "graphs_root": f"output/{name}_batch",
        },
        "swap": {"mode": "matrix", "include_identity": True},
        "ct_steering": {
            "model_id": "google/gemma-2-2b",
            "transcoder_set": "mntss/clt-gemma-2-2b-2.5M",
            "M_ablate": -2,
            "M_amplify": 20,
            "temperature": 0.3,
            "n_tokens": 10,
            "freq_penalty": 2.0,
            "seed": 42,
            "top_k": 5,
            "freeze_attention": False,
            "steer_generated_tokens": False,
        },
        "compute": {
            "inherit_from_source": True,
            "remote": {"enabled": True, "batch_size": 4, "max_gpus": 8},
        },
        "steps": {
            "validate_inputs": True,
            "prepare_features": True,
            "run_steering": True,
            "aggregate_results": True,
        },
    }


def _write_yaml(path: Path, data: dict):
    with open(path, "w", encoding="utf-8") as f:
        yaml.dump(data, f, default_flow_style=False, sort_keys=False, allow_unicode=True)


def main():
    parser = argparse.ArgumentParser(
        description="Generate swap pipeline YAML configs from validated dataset files"
    )
    parser.add_argument(
        "datasets",
        nargs="+",
        help="Validated dataset path(s), glob(s), or directories",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help=f"Output directory for YAML configs (default: {DEFAULT_OUTPUT_DIR})",
    )
    args = parser.parse_args()
    dataset_paths = resolve_dataset_paths(args.datasets)
    for dataset_path in dataset_paths:
        generate_configs(str(dataset_path), args.output_dir)


if __name__ == "__main__":
    main()
