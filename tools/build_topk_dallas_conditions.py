"""
Build matched-budget top-K Dallas swap conditions.

For each requested K we create a new condition directory at
    output/usa_states_fact_batch/_swap_conditions/auto_top<K>_dallas/
mirroring the layout of the existing auto_top21_dallas condition:
    auto_top<K>_dallas/
        <source_state>           -> symlink to canonical source dir
        texas_dallas/
            00 Graph Generation  -> symlink to canonical Dallas graph dir
            02 Node Grouping/
                node_grouping.csv  (filtered to top-K features by
                                    node_influence; original labels
                                    inherited from auto)
            manifest.json

We also write a per-K swap config YAML by cloning
    scripts/experiments/batch/configs/smoke_swap_auto_top21_dallas.yml
and substituting the experiment_name and graphs_root.

CLI:
    python tools/build_topk_dallas_conditions.py [Ks...]               # smoke (5 sources)
    python tools/build_topk_dallas_conditions.py --full [Ks...]        # phase-4 (49 sources)

The ``--full`` flag pulls the 49-source list from
``scripts/experiments/batch/configs/full_swap_auto_top21_dallas.yml``
so it stays in sync with the rest of the all-49-source pipeline.
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
FACT_BATCH = REPO / "output" / "usa_states_fact_batch"
COND_ROOT = FACT_BATCH / "_swap_conditions"
CONFIG_DIR = REPO / "scripts" / "experiments" / "batch" / "configs"
TEMPLATE_CONFIG = CONFIG_DIR / "smoke_swap_auto_top21_dallas.yml"
FULL49_CONFIG = CONFIG_DIR / "full_swap_auto_top21_dallas.yml"

CANONICAL_DALLAS = FACT_BATCH / "texas_dallas"
CANONICAL_GRP_CSV = CANONICAL_DALLAS / "02 Node Grouping" / "node_grouping.csv"
CANONICAL_METRICS_CSV = CANONICAL_DALLAS / "00 Graph Generation" / "graph_feature_static_metrics.csv"

SMOKE_SOURCE_STATES = [
    "california_oakland",
    "florida_miami",
    "illinois_chicago",
    "new_york_new_york_city",
    "washington_seattle",
]


def load_full49_sources() -> list[str]:
    """Return the 49 source state slugs from the full_swap_auto_top21_dallas config."""
    text = FULL49_CONFIG.read_text()
    matches = re.findall(r"-\s*\[([a-z_]+),\s*texas_dallas\]", text)
    if len(matches) != 49:
        raise RuntimeError(
            f"Expected 49 source states in {FULL49_CONFIG.name}, got {len(matches)}."
        )
    return matches


def topk_features(K: int) -> pd.DataFrame:
    metrics = pd.read_csv(CANONICAL_METRICS_CSV)
    metrics["layer"] = metrics["layer"].astype(int)
    metrics["id"] = metrics["id"].astype(int)
    inf = (
        metrics.groupby(["layer", "id"], as_index=False)["node_influence"]
        .max()
        .rename(columns={"id": "feature"})
    )

    grp = pd.read_csv(CANONICAL_GRP_CSV)
    grp["layer"] = grp["layer"].astype(int)
    grp["feature"] = grp["feature"].astype(int)
    bag = grp[["layer", "feature"]].drop_duplicates().reset_index(drop=True)

    merged = bag.merge(inf, how="left", on=["layer", "feature"]).fillna(0.0)
    top = merged.sort_values("node_influence", ascending=False).head(K)
    return top[["layer", "feature"]].reset_index(drop=True)


def build_condition(K: int, source_states: list[str]) -> Path:
    cond_name = f"auto_top{K}_dallas"
    cond_dir = COND_ROOT / cond_name
    if cond_dir.exists():
        added = 0
        for src in source_states:
            link = cond_dir / src
            if link.exists() or link.is_symlink():
                continue
            link.symlink_to((FACT_BATCH / src).resolve())
            added += 1
        if added:
            print(f"  [exists] {cond_dir}: +{added} source symlinks")
        else:
            print(f"  [skip] {cond_dir} already exists")
        return cond_dir

    cond_dir.mkdir(parents=True)

    for src in source_states:
        link = cond_dir / src
        target = (FACT_BATCH / src).resolve()
        link.symlink_to(target)

    dallas_dir = cond_dir / "texas_dallas"
    dallas_dir.mkdir()
    (dallas_dir / "00 Graph Generation").symlink_to(
        (CANONICAL_DALLAS / "00 Graph Generation").resolve()
    )

    grouping_dir = dallas_dir / "02 Node Grouping"
    grouping_dir.mkdir()

    top = topk_features(K)
    keep_keys = set(zip(top["layer"], top["feature"]))

    full_grp = pd.read_csv(CANONICAL_GRP_CSV)
    full_grp["layer"] = full_grp["layer"].astype(int)
    full_grp["feature"] = full_grp["feature"].astype(int)
    mask = [(int(l), int(f)) in keep_keys for l, f in zip(full_grp["layer"], full_grp["feature"])]
    sub = full_grp[mask].reset_index(drop=True)
    sub.to_csv(grouping_dir / "node_grouping.csv", index=False)

    manifest = {
        "condition": cond_name,
        "K": K,
        "n_features_in_grouping": len(top),
        "n_rows": len(sub),
        "supernodes": sorted(sub["supernode_name"].dropna().unique().tolist()),
        "source": "top-K features by node_influence in canonical auto Dallas grouping",
    }
    with open(dallas_dir / "manifest.json", "w") as f:
        json.dump(manifest, f, indent=2)

    print(f"  built {cond_dir}: {len(top)} features, {len(sub)} grouping rows, {len(manifest['supernodes'])} supernodes")
    return cond_dir


def write_yaml(K: int) -> Path:
    cond_name = f"auto_top{K}_dallas"
    yaml_path = CONFIG_DIR / f"smoke_swap_{cond_name}.yml"
    if yaml_path.exists():
        print(f"  [skip] {yaml_path} already exists")
        return yaml_path
    template = TEMPLATE_CONFIG.read_text()
    new = template.replace(
        "experiment_name: smoke_swap_auto_top21_target_dallas",
        f"experiment_name: smoke_swap_auto_top{K}_target_dallas",
    ).replace(
        "auto_top21_dallas",
        cond_name,
    ).replace(
        "top 21 features from auto-dallas",
        f"top {K} features from auto-dallas",
    ).replace(
        "matching the human's 21 unique features",
        f"matched-budget control (K={K})",
    )
    yaml_path.write_text(new)
    print(f"  wrote {yaml_path}")
    return yaml_path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("CLI:")[0].strip())
    parser.add_argument("Ks", nargs="*", type=int, default=[100, 200],
                        help="K values to build (default: 100 200)")
    parser.add_argument("--full", action="store_true",
                        help="Use the 49-source phase-4 list "
                             "(default: 5-source smoke list)")
    parser.add_argument("--no-yaml", action="store_true",
                        help="Skip writing the smoke YAML clone "
                             "(useful when phase-4 has its own configs)")
    args = parser.parse_args()

    if args.full:
        sources = load_full49_sources()
        print(f"Using {len(sources)} source states from {FULL49_CONFIG.name}")
    else:
        sources = SMOKE_SOURCE_STATES
        print(f"Using {len(sources)} smoke source states")

    for K in args.Ks:
        print(f"=== K={K} ===")
        build_condition(K, sources)
        if not args.no_yaml:
            write_yaml(K)


if __name__ == "__main__":
    main()
