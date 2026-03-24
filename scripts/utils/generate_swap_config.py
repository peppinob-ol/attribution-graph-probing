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
REPO_ROOT = Path(__file__).resolve().parents[2]


def _check_entity_outputs(name: str, entities: list[dict]) -> dict:
    """Check which entities already have batch pipeline outputs."""
    outputs_root = REPO_ROOT / "output" / f"{name}_batch"
    if not outputs_root.exists():
        return {"root_exists": False, "with_graphs": 0, "with_grouping": 0,
                "total": len(entities)}

    with_graphs = 0
    with_grouping = 0
    for entity in entities:
        slug = entity["slug"]
        entity_dir = outputs_root / slug
        if not entity_dir.exists():
            slug_lower = slug.lower()
            for entry in outputs_root.iterdir():
                if entry.is_dir() and entry.name.lower() == slug_lower:
                    entity_dir = entry
                    break
        batch_graph = entity_dir / "00 Graph Generation" / "graph.json"
        flat_graph = entity_dir / "graph.json"
        if batch_graph.exists() or flat_graph.exists():
            with_graphs += 1
        batch_grouping = entity_dir / "02 Node Grouping" / "node_grouping.csv"
        flat_grouping = entity_dir / "node_grouping.csv"
        if batch_grouping.exists() or flat_grouping.exists():
            with_grouping += 1

    return {"root_exists": True, "with_graphs": with_graphs,
            "with_grouping": with_grouping, "total": len(entities)}


def generate_configs(dataset_path: str, output_dir: str | None = None):
    with open(dataset_path, "r", encoding="utf-8") as f:
        dataset = json.load(f)

    name = dataset["name"]
    n_entities = len(dataset["entities"])

    if output_dir is None:
        output_dir = DEFAULT_OUTPUT_DIR
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    concept_fields = [dataset["swap_concept_field"], dataset["expected_field"]]

    state = _check_entity_outputs(name, dataset["entities"])
    all_graphs = state["with_graphs"] == state["total"]
    all_grouping = state["with_grouping"] == state["total"]
    needs_full_pipeline = not all_graphs or not all_grouping

    full_config = _build_full_config(dataset, skip_graph_generation=all_graphs)
    swap_config = _build_swap_config(name, concept_fields)

    full_path = out / f"{name}_full.yml"
    swap_path = out / f"{name}_swap.yml"

    _write_yaml(full_path, full_config)
    _write_yaml(swap_path, swap_config)

    print(f"Generated : {full_path}")
    print(f"Generated : {swap_path}")
    print(f"Entities  : {n_entities}")
    print(f"Matrix    : {n_entities}x{n_entities} = {n_entities**2} swap pairs")

    if not state["root_exists"]:
        print(f"\nOutputs   : output/{name}_batch/ does not exist")
        print(f"            Run the full pipeline first:")
        print(f"            python run_batch_from_yaml.py --config configs/{name}_full.yml")
    else:
        print(f"\nOutputs   : {state['with_graphs']}/{state['total']} entities have graphs, "
              f"{state['with_grouping']}/{state['total']} have grouping")
        if needs_full_pipeline:
            missing = state["total"] - state["with_graphs"]
            print(f"            {missing} entities still need the full pipeline")
        else:
            print(f"            All entities processed -- full pipeline can be skipped")
    print(f"Features  : prepare_features=true (per-pair features.json generated at swap time)")


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


def _extract_blacklist_tokens(probe_templates: list[dict]) -> list[str]:
    """Derive blacklist tokens from probe template prefixes (text before ':')."""
    tokens = {"<bos>"}
    for tpl in probe_templates:
        text = tpl.get("text", "")
        if ":" in text:
            tokens.add(text.split(":")[0].strip())
    return sorted(tokens)


def _build_full_config(dataset: dict, *, skip_graph_generation: bool = False) -> dict:
    name = dataset["name"]
    blacklist_tokens = _extract_blacklist_tokens(dataset.get("probe_templates", []))
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
        "get_activations": {
            "backend": "local",
            "local": {
                "chunk_by_layer": True,
                "include_zero": False,
                "gpus": [0, 1, 2, 3, 4, 5, 6, 7],
                "batch_size": 2,
            },
        },
        "grouping": {
            "enabled": True,
            "window": 7,
            "blacklist_tokens": blacklist_tokens,
            "thresholds": {
                "dict_peak_consistency_min": 0.8,
                "dict_n_distinct_peaks_max": 1,
                "sayx_func_vs_sem_min": 50.0,
                "sayx_layer_min": 7,
                "rel_sparsity_max": 0.45,
                "sem_layer_max": 3,
                "sem_conf_s_min": 0.50,
                "sem_func_vs_sem_max": 50.0,
            },
            "upload": {
                "enabled": True,
                "api_key_env": "NEURONPEDIA_API_KEY",
                "display_name_template": "{slug} (auto-grouped)",
                "overwrite_id": "",
            },
        },
        "steps": {
            "graph_generation": not skip_graph_generation,
            "feature_export": True,
            "prepare_features": True,
            "probe_prompts": True,
            "activations": True,
            "grouping": True,
            "upload_subgraph": True,
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


def _build_swap_config(name: str, concept_fields: list[str]) -> dict:
    answer_field = concept_fields[-1] if concept_fields else "capital"
    return {
        "version": 0.1,
        "display_demo": True,
        "experiment_name": f"{name}_swap",
        "inputs": {
            "source_config": f"configs/{name}_full.yml",
            "graphs_root": f"output/{name}_batch",
        },
        "swap": {
            "mode": "matrix",
            "include_identity": True,
            "concept_fields": concept_fields,
            "answer_field": answer_field,
        },
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
            "track_trajectory": True,
        },
        "compute": {
            "inherit_from_source": False,
            "remote": {"enabled": False},
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
