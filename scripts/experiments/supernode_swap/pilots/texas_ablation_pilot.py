#!/usr/bin/env python3
"""
Per-supernode ablation pilot for the Texas (Dallas -> Austin) prompt.

This script ranks supernodes by their static influence, selects a small subset
(including the primary state concept), and evaluates how ablating each affects
the logprob of the target capital token under various steering factors.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

import pandas as pd


def _load_steering_module():
    scripts_dir = Path(__file__).resolve().parents[3]
    module_path = scripts_dir / "03_neuronpedia_steering.py"
    spec = importlib.util.spec_from_file_location("neuronpedia_steering", module_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Unable to load module at {module_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules.setdefault("neuronpedia_steering", module)
    spec.loader.exec_module(module)
    return module


steering = _load_steering_module()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run a Texas-only supernode ablation pilot.")
    parser.add_argument(
        "--grouping-path",
        default="output/usa_states_batch/texas_Dallas/02 Node Grouping/node_grouping.csv",
        help="Path to node_grouping.csv for the Texas seed.",
    )
    parser.add_argument(
        "--metrics-path",
        default="output/usa_states_batch/texas_Dallas/00 Graph Generation/graph_feature_static_metrics.csv",
        help="Path to graph_feature_static_metrics.csv for the Texas seed.",
    )
    parser.add_argument(
        "--slug",
        default="texas_Dallas",
        help="Slug/identifier for this seed (used in outputs).",
    )
    parser.add_argument(
        "--prompt",
        default="The capital of the state containing Dallas is",
        help="Prompt text to steer.",
    )
    parser.add_argument(
        "--state-concept",
        default="texas",
        help="Name of the state supernode to ensure is included.",
    )
    parser.add_argument(
        "--target-token",
        default=" Austin",
        help="Capital token whose logprob delta should be tracked.",
    )
    parser.add_argument(
        "--M",
        nargs="+",
        type=float,
        default=[-1.0, 0.0, 1.0, 2.0, 4.0],
        help="List of steering factors to evaluate.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=5,
        help="Number of non-state supernodes to include (ranked by static influence).",
    )
    parser.add_argument(
        "--output-dir",
        default=str(Path(__file__).resolve().parent / "results"),
        help="Directory to store JSON/CSV summaries.",
    )
    parser.add_argument(
        "--api-key",
        default=None,
        help="Optional Neuronpedia API key (defaults to NEURONPEDIA_API_KEY env).",
    )
    parser.add_argument("--model-id", default="gemma-2-2b")
    parser.add_argument("--source-set", default="clt-hp")
    parser.add_argument("--steer-method", default="ORTHOGONAL_DECOMP")
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--n-tokens", type=int, default=16)
    parser.add_argument("--freq-penalty", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--strength-multiplier", type=float, default=1.0)
    return parser.parse_args()


def build_supernode_tables(
    grouping_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
    slug: str,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """Return dicts mapping supernode_name -> (SupernodeSpec, static_stats)."""
    names = (
        grouping_df["supernode_name"]
        .fillna("")
        .astype(str)
        .str.strip()
        .replace("", pd.NA)
        .dropna()
        .unique()
    )
    specs: Dict[str, Any] = {}
    stats: Dict[str, Any] = {}
    for name in names:
        subset = grouping_df[grouping_df["supernode_name"].astype(str) == name]
        try:
            spec = steering.extract_concept_supernode(
                grouping_df=subset,
                metrics_df=metrics_df,
                concept=name,
                slug=slug,
            )
        except ValueError:
            continue
        specs[name] = spec
        stats[name] = steering.compute_supernode_static_stats(spec, metrics_df)
    return specs, stats


def select_supernodes(
    specs: Dict[str, Any],
    stats: Dict[str, Any],
    state_concept: str,
    top_n: int,
) -> List[str]:
    if state_concept not in specs:
        raise KeyError(f"State concept '{state_concept}' not found among supernodes.")

    ranked = sorted(
        (
            name,
            stats[name]["node_influence_sum"],
        )
        for name in specs
        if name != state_concept
    )
    ranked.sort(key=lambda x: x[1], reverse=True)
    chosen = [state_concept]
    chosen += [name for name, _ in ranked[:top_n]]
    return chosen


def run_ablation_for_supernodes(
    names: List[str],
    specs: Dict[str, Any],
    stats: Dict[str, Any],
    args: argparse.Namespace,
) -> List[Dict[str, Any]]:
    cfg = steering.SteeringConfig(
        model_id=args.model_id,
        source_set=args.source_set,
        steer_method=args.steer_method,
        temperature=args.temperature,
        n_tokens=args.n_tokens,
        freq_penalty=args.freq_penalty,
        seed=args.seed,
        strength_multiplier=args.strength_multiplier,
    )
    api_key = args.api_key or os.environ.get("NEURONPEDIA_API_KEY")

    records: List[Dict[str, Any]] = []
    for name in names:
        sweep = steering.run_ablation_experiment(
            prompt=args.prompt,
            supernode=specs[name],
            Ms=args.M,
            cfg=cfg,
            target_tokens=[args.target_token],
            api_key=api_key,
        )
        entries = []
        for item in sweep["results"]:
            token_metrics = item.get("token_metrics") or {}
            delta = None
            token_entry = token_metrics.get(args.target_token)
            if token_entry:
                delta = token_entry.get("delta")
            entries.append(
                {
                    "M": item["M"],
                    "feature_count": item["feature_count"],
                    "delta_logprob": delta,
                }
            )
        records.append(
            {
                "supernode": name,
                "static_stats": stats[name],
                "results": entries,
            }
        )
    return records


def persist_outputs(
    records: List[Dict[str, Any]],
    args: argparse.Namespace,
) -> None:
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    json_path = output_dir / f"{args.slug}_ablation_pilot.json"
    csv_path = output_dir / f"{args.slug}_ablation_pilot.csv"

    payload = {
        "slug": args.slug,
        "prompt": args.prompt,
        "target_token": args.target_token,
        "M_values": args.M,
        "records": records,
    }
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2)

    csv_rows = []
    for record in records:
        static_stats = record["static_stats"]
        for entry in record["results"]:
            csv_rows.append(
                {
                    "supernode": record["supernode"],
                    "node_influence_sum": static_stats["node_influence_sum"],
                    "cumulative_influence_sum": static_stats["cumulative_influence_sum"],
                    "M": entry["M"],
                    "feature_count": entry["feature_count"],
                    "delta_logprob": entry["delta_logprob"],
                }
            )
    if csv_rows:
        pd.DataFrame(csv_rows).to_csv(csv_path, index=False)

    print(f"Results saved to:\n  JSON: {json_path}\n  CSV:  {csv_path}")


def main() -> None:
    args = parse_args()
    grouping_df = pd.read_csv(args.grouping_path)
    metrics_df = pd.read_csv(args.metrics_path)

    specs, stats = build_supernode_tables(grouping_df, metrics_df, args.slug)
    chosen = select_supernodes(specs, stats, args.state_concept, args.top_n)
    print(f"Evaluating supernodes: {chosen}")

    records = run_ablation_for_supernodes(chosen, specs, stats, args)
    persist_outputs(records, args)

    for record in records:
        print(f"\nSupernode: {record['supernode']}")
        print(f"  Static node influence sum: {record['static_stats']['node_influence_sum']:.4f}")
        for entry in record["results"]:
            print(
                f"    M={entry['M']:>4}: delta_logprob={entry['delta_logprob']}"
            )


if __name__ == "__main__":
    main()

