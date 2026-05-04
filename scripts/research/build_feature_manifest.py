"""Build a cross-dataset manifest of feature-classification metrics.

This script rebuilds the per-feature metrics used by the node-grouping
decision tree from existing node_grouping.csv files. It does not rerun probing
or mutate the upstream pipeline outputs.
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from pathlib import Path


DATASETS = (
    "usa_states_batch",
    "book_characters_authors_batch",
    "products_founders_batch",
    "paintings_painters_batch",
    "sounds_colors_batch",
)

ORDERED_COLUMNS = [
    "dataset",
    "entity",
    "feature_key",
    "layer",
    "feature",
    "peak_consistency_main",
    "n_distinct_peaks",
    "main_peak_token",
    "func_vs_sem_pct",
    "conf_F",
    "conf_S",
    "share_F",
    "sparsity_median",
    "K_sem_distinct",
    "n_active_prompts",
    "n_prompts",
    "pred_label",
    "subtype",
    "review",
]


def iter_node_grouping_csvs(output_root: Path):
    for dataset in DATASETS:
        dataset_root = output_root / dataset
        if not dataset_root.exists():
            raise FileNotFoundError(f"Missing dataset directory: {dataset_root}")

        for csv_path in sorted(dataset_root.glob("*/02 Node Grouping/node_grouping.csv")):
            entity = csv_path.parents[1].name
            yield dataset, entity, csv_path


def read_rows(csv_path: Path) -> list[dict[str, str]]:
    with csv_path.open(newline="", encoding="utf-8") as handle:
        return list(csv.DictReader(handle))


def tokenize_prompt(row: dict[str, str]) -> list[str]:
    if row.get("tokens"):
        try:
            tokens = json.loads(row["tokens"])
            return [str(token).strip().lower() for token in tokens]
        except json.JSONDecodeError:
            pass

    prompt = row.get("prompt", "")
    return (
        prompt.lower()
        .replace(",", " , ")
        .replace(".", " . ")
        .split()
    )


def calculate_peak_consistency(rows: list[dict[str, str]]) -> dict[str, object]:
    token_stats: dict[str, dict[str, int]] = {}

    for row in rows:
        peak_token = str(row.get("peak_token", "")).strip().lower()
        stats = token_stats.setdefault(peak_token, {"as_peak": 0, "in_prompt": 0})
        stats["as_peak"] += 1

        tokens_lower = tokenize_prompt(row)
        for token in set(tokens_lower):
            token_stats.setdefault(token, {"as_peak": 0, "in_prompt": 0})
            token_stats[token]["in_prompt"] += tokens_lower.count(token)

    token_consistencies = {}
    for token, stats in token_stats.items():
        if stats["in_prompt"] > 0:
            token_consistencies[token] = {
                "consistency": stats["as_peak"] / stats["in_prompt"],
                "as_peak": stats["as_peak"],
                "in_prompt": stats["in_prompt"],
            }

    if token_consistencies:
        main_peak_token, main_stats = max(
            token_consistencies.items(),
            key=lambda item: item[1]["as_peak"],
        )
        peak_consistency_main = main_stats["consistency"]
    else:
        main_peak_token = ""
        peak_consistency_main = 0.0

    n_distinct_peaks = sum(
        1 for stats in token_consistencies.values() if stats["as_peak"] > 0
    )
    return {
        "peak_consistency_main": peak_consistency_main,
        "n_distinct_peaks": n_distinct_peaks,
        "main_peak_token": main_peak_token,
    }


def as_float(value: str, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def aggregate_feature_metrics(rows: list[dict[str, str]]) -> list[dict[str, object]]:
    grouped: dict[str, list[dict[str, str]]] = {}
    for row in rows:
        grouped.setdefault(row["feature_key"], []).append(row)

    feature_stats = []
    for feature_key, group in grouped.items():
        layer = int(as_float(group[0].get("layer", "0")))
        consistency_metrics = calculate_peak_consistency(group)

        active = [row for row in group if as_float(row.get("activation_max", "0")) > 0]
        functional = [
            row for row in active if row.get("peak_token_type") == "functional"
        ]
        semantic = [row for row in active if row.get("peak_token_type") == "semantic"]
        n_total_peaks = len(active)

        share_F = len(functional) / n_total_peaks if n_total_peaks else 0.0
        conf_F = share_F
        conf_S = 1.0 - share_F

        if functional and semantic:
            max_act_func = max(as_float(row.get("activation_max", "0")) for row in functional)
            max_act_sem = max(as_float(row.get("activation_max", "0")) for row in semantic)
            max_val = max(max_act_func, max_act_sem)
            func_vs_sem_pct = (
                100.0 * (max_act_func - max_act_sem) / max_val if max_val > 0 else 0.0
            )
        elif functional:
            func_vs_sem_pct = 100.0
        elif semantic:
            func_vs_sem_pct = -100.0
        else:
            func_vs_sem_pct = 0.0

        sparsities = [as_float(row.get("sparsity_ratio", "0")) for row in active]
        sparsity_median = statistics.median(sparsities) if sparsities else 0.0

        sem_tokens = [
            str(row.get("peak_token", "")).strip().lower()
            for row in group
            if row.get("peak_token_type") == "semantic"
        ]
        K_sem_distinct = len(set(sem_tokens))

        feature_stats.append(
            {
                "feature_key": feature_key,
                "layer": layer,
                "feature": group[0].get("feature", ""),
                "peak_consistency_main": consistency_metrics["peak_consistency_main"],
                "n_distinct_peaks": consistency_metrics["n_distinct_peaks"],
                "main_peak_token": consistency_metrics["main_peak_token"],
                "func_vs_sem_pct": func_vs_sem_pct,
                "conf_F": conf_F,
                "conf_S": conf_S,
                "share_F": share_F,
                "sparsity_median": sparsity_median,
                "K_sem_distinct": K_sem_distinct,
                "n_active_prompts": len(active),
                "n_prompts": len(group),
                "pred_label": group[0].get("pred_label", ""),
                "subtype": group[0].get("subtype", ""),
                "review": group[0].get("review", ""),
            }
        )

    return feature_stats


def build_manifest(repo_root: Path) -> list[dict[str, object]]:
    output_root = repo_root / "output"
    rows = []

    for dataset, entity, csv_path in iter_node_grouping_csvs(output_root):
        entity_rows = read_rows(csv_path)
        metrics = aggregate_feature_metrics(entity_rows)
        for row in metrics:
            row["dataset"] = dataset
            row["entity"] = entity
            rows.append(row)

    if not rows:
        raise RuntimeError(f"No node_grouping.csv files found under {output_root}")

    return rows


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path(__file__).resolve().parents[2],
        help="Repository root. Defaults to the root inferred from this script path.",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("output/research/feature_manifest.csv"),
        help="Output CSV path, relative to repo root unless absolute.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    repo_root = args.repo_root.resolve()
    output_path = args.output
    if not output_path.is_absolute():
        output_path = repo_root / output_path

    manifest = build_manifest(repo_root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=ORDERED_COLUMNS)
        writer.writeheader()
        writer.writerows(
            {column: row.get(column, "") for column in ORDERED_COLUMNS}
            for row in manifest
        )

    counts = {dataset: 0 for dataset in DATASETS}
    for row in manifest:
        counts[str(row["dataset"])] += 1
    print(f"Wrote {len(manifest):,} feature rows to {output_path}")
    for dataset, count in counts.items():
        print(f"  {dataset}: {count:,}")


if __name__ == "__main__":
    main()
