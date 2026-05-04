"""Phase 3 full-scale run prep.

What this does (no GPU work, pure orchestration):
  1) Reads scripts/experiments/batch/configs/usa_states_fact_full.yml
     (the canonical 50-USA list).
  2) Detects which states already have a canonical graph under
     output/usa_states_fact_batch/ and which ones are missing.
  3) Splits the missing states into N graph-generation shards (default 8),
     writes one YAML per shard under
     scripts/experiments/batch/configs/_phase3_shards/.
  4) Extends every existing swap-condition directory under
     output/usa_states_fact_batch/_swap_conditions/<cond>/ to add a symlink
     for each new source state, mirroring the smoke layout.
  5) Writes 6 full-scale swap-condition YAMLs
     (full_swap_<cond>_dallas.yml) that target texas_dallas from all 49
     non-Texas sources.
  6) Emits two launch scripts:
       tools/launch_phase3_graphs.sh   (8-way parallel graph gen)
       tools/launch_phase3_swaps.sh    (6-way parallel swap+M-search)

Run it once; it is idempotent (skips existing shards/configs/symlinks).
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
from typing import List

import yaml

REPO = Path(__file__).resolve().parent.parent
CONFIG_DIR = REPO / "scripts" / "experiments" / "batch" / "configs"
SHARD_DIR = CONFIG_DIR / "_phase3_shards"
FACT_BATCH = REPO / "output" / "usa_states_fact_batch"
COND_ROOT = FACT_BATCH / "_swap_conditions"

MASTER_GRAPH_CONFIG = CONFIG_DIR / "usa_states_fact_full.yml"
TARGET_SLUG = "texas_dallas"

CONDITIONS = [
    "human_dallas",
    "auto_dallas",
    "auto_top21_dallas",
    "auto_top100_dallas",
    "auto_top200_dallas",
    "shuffled_labels_dallas",
]
SMOKE_TEMPLATES = {c: CONFIG_DIR / f"smoke_swap_{c}.yml" for c in CONDITIONS}


def load_master_entities() -> List[dict]:
    with open(MASTER_GRAPH_CONFIG) as fh:
        cfg = yaml.safe_load(fh)
    return cfg["graph_generation"]["templated"]["entities"]["items"]


def detect_done_slugs() -> List[str]:
    if not FACT_BATCH.exists():
        return []
    done = []
    for child in FACT_BATCH.iterdir():
        if not child.is_dir():
            continue
        if child.name.startswith("_"):
            continue
        if "wrong_transcoder" in child.name:
            continue
        # Require both graph json and grouping csv to count as "done".
        graph_ok = (child / "00 Graph Generation" / "graph.json").exists()
        group_ok = (child / "02 Node Grouping" / "node_grouping.csv").exists()
        if graph_ok and group_ok:
            done.append(child.name)
    return sorted(done)


def build_shard_yamls(missing: List[dict], n_shards: int) -> List[Path]:
    SHARD_DIR.mkdir(parents=True, exist_ok=True)
    with open(MASTER_GRAPH_CONFIG) as fh:
        master = yaml.safe_load(fh)

    # Round-robin so each shard gets a balanced mix.
    shards: List[List[dict]] = [[] for _ in range(n_shards)]
    for i, item in enumerate(missing):
        shards[i % n_shards].append(item)

    written: List[Path] = []
    for i, items in enumerate(shards):
        if not items:
            continue
        cfg = yaml.safe_load(yaml.safe_dump(master))  # deep copy
        cfg["experiment_name"] = f"phase3_graphs_shard{i}"
        cfg["graph_generation"]["templated"]["entities"]["items"] = items
        cfg.setdefault("get_activations", {}).setdefault("local", {})["gpus"] = [0]  # rebound at launch via CUDA_VISIBLE_DEVICES
        out = SHARD_DIR / f"phase3_graphs_shard{i}.yml"
        with open(out, "w") as fh:
            yaml.safe_dump(cfg, fh, sort_keys=False)
        written.append(out)
        print(f"  shard {i}: {len(items)} states  ->  {out}")
    return written


def extend_swap_condition_symlinks(new_sources: List[str]) -> None:
    if not COND_ROOT.exists():
        print(f"  [skip] {COND_ROOT} does not exist (smoke run never created it)")
        return
    for cond in CONDITIONS:
        cond_dir = COND_ROOT / cond
        if not cond_dir.exists():
            print(f"  [warn] missing condition dir: {cond_dir}")
            continue
        added = 0
        for src in new_sources:
            link = cond_dir / src
            target = (FACT_BATCH / src).resolve()
            if link.exists() or link.is_symlink():
                continue
            try:
                link.symlink_to(target)
                added += 1
            except FileExistsError:
                pass
        print(f"  {cond}: +{added} symlinks (target dir: {cond_dir})")


def write_full_swap_yamls(all_sources: List[str]) -> List[Path]:
    written: List[Path] = []
    pairs_block = "\n".join(f"    - [{src}, {TARGET_SLUG}]" for src in all_sources)

    for cond in CONDITIONS:
        template_path = SMOKE_TEMPLATES[cond]
        if not template_path.exists():
            print(f"  [warn] missing smoke template: {template_path}")
            continue
        text = template_path.read_text()

        # Rewrite experiment_name (smoke_* -> full_*).
        text = text.replace(
            f"experiment_name: smoke_swap_{cond.replace('_dallas', '_target_dallas')}",
            f"experiment_name: full_swap_{cond.replace('_dallas', '_target_dallas')}",
        )

        # Repoint source_config from the 6-state smoke list to the 50-state
        # canonical fact list. Using the bare filename (no `configs/` prefix)
        # so it resolves against the swap config's own directory regardless
        # of the launcher's cwd.
        text = text.replace(
            "source_config: configs/smoke_fact_6states.yml",
            "source_config: usa_states_fact_full.yml",
        )

        # Replace the (5-pair) block with the (49-pair) block. We anchor on
        # the literal 5-source block from the smoke template; if anchors
        # change, the helper bails out so we do not silently mis-edit.
        smoke_block = (
            "  pairs:\n"
            "    - [california_oakland, texas_dallas]\n"
            "    - [new_york_new_york_city, texas_dallas]\n"
            "    - [florida_miami, texas_dallas]\n"
            "    - [illinois_chicago, texas_dallas]\n"
            "    - [washington_seattle, texas_dallas]\n"
        )
        if smoke_block not in text:
            raise SystemExit(
                f"  [error] smoke pair block not found verbatim in {template_path}; "
                f"template format changed, cannot generate full-swap YAML safely."
            )
        text = text.replace(smoke_block, "  pairs:\n" + pairs_block + "\n")

        out = CONFIG_DIR / f"full_swap_{cond}.yml"
        out.write_text(text)
        written.append(out)
        print(f"  {cond}: full-scale config -> {out}  ({len(all_sources)} pairs)")
    return written


def write_launch_scripts(shard_paths: List[Path]) -> None:
    """Two parallel launch scripts; conservative (& wait on each pool)."""
    graphs_lines = [
        "#!/usr/bin/env bash",
        "# Auto-generated by tools/phase3_full_prepare.py.",
        "# Launches 8-way parallel graph generation, one shard per GPU.",
        "set -u",
        "REPO=$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\"/.. && pwd)",
        "cd \"$REPO\"",
        "source .venv/bin/activate",
        "mkdir -p logs/phase3",
        "echo \"[phase3-graphs] launching ${#}-shard parallel graph generation\"",
    ]
    pids: List[str] = []
    for i, path in enumerate(shard_paths):
        log = f"logs/phase3/graphs_shard{i}.log"
        graphs_lines.append(
            f'CUDA_VISIBLE_DEVICES={i} nohup python scripts/experiments/batch/run_batch_from_yaml.py '
            f'--config {path.relative_to(REPO)} > {log} 2>&1 &'
        )
        graphs_lines.append(f'PID{i}=$!')
        graphs_lines.append(f'echo "[phase3-graphs] shard {i} -> GPU {i}, pid $PID{i}, log {log}"')
        pids.append(f"$PID{i}")
    graphs_lines += [
        "echo \"[phase3-graphs] all shards launched, waiting...\"",
        f"wait {' '.join(pids)}",
        "echo \"[phase3-graphs] all shards finished\"",
    ]
    out = REPO / "tools" / "launch_phase3_graphs.sh"
    out.write_text("\n".join(graphs_lines) + "\n")
    out.chmod(0o755)
    print(f"  wrote {out}")

    # Swap side: run_batch_swaps.py has built-in --parallel --workers --gpus.
    # We run the 6 conditions SEQUENTIALLY but each one fans out across all
    # 8 GPUs (49 source pairs / 8 workers ~= 6 pairs/GPU, ~36 min/condition,
    # ~3.6 h total wall-clock instead of 4.8 h with one-condition-per-GPU).
    swap_lines = [
        "#!/usr/bin/env bash",
        "# Auto-generated by tools/phase3_full_prepare.py.",
        "# Runs 6 swap conditions sequentially; each one uses all 8 GPUs",
        "# (--parallel --workers 8) to distribute 49 source pairs.",
        "set -e",
        "set -u",
        "REPO=$(cd \"$(dirname \"${BASH_SOURCE[0]}\")\"/.. && pwd)",
        "cd \"$REPO\"",
        "source .venv/bin/activate",
        "mkdir -p logs/phase3",
        "RUN_ID=${RUN_ID:-full_50states_phase3_$(date +%Y%m%d_%H%M)}",
        'echo "[phase3-swaps] run_id=$RUN_ID, 6 conditions sequential, 8-GPU per condition"',
    ]
    for cond in CONDITIONS:
        cfg = f"scripts/experiments/batch/configs/full_swap_{cond}.yml"
        log = f"logs/phase3/swap_{cond}.log"
        swap_lines += [
            f'echo "[phase3-swaps] === starting condition: {cond} ==="',
            f'python scripts/experiments/batch/run_batch_swaps.py \\',
            f'    --config {cfg} \\',
            f'    --parallel --workers 8 --gpus 0,1,2,3,4,5,6,7 \\',
            f'    --run-id "$RUN_ID" \\',
            f'    > {log} 2>&1',
            f'echo "[phase3-swaps] === finished condition: {cond} ==="',
        ]
    swap_lines.append('echo "[phase3-swaps] all conditions finished"')
    out = REPO / "tools" / "launch_phase3_swaps.sh"
    out.write_text("\n".join(swap_lines) + "\n")
    out.chmod(0o755)
    print(f"  wrote {out}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--n-shards", type=int, default=8,
                        help="Number of parallel graph-generation shards (default: 8)")
    parser.add_argument("--no-symlinks", action="store_true",
                        help="Skip extending swap-condition symlinks")
    args = parser.parse_args()

    print("== Phase 3 full-scale prep ==")
    entities = load_master_entities()
    done = detect_done_slugs()
    missing = [e for e in entities if e["slug"] not in set(done)]

    print(f"  master entities: {len(entities)}")
    print(f"  already done:    {len(done)}  (e.g. {', '.join(done[:3])})")
    print(f"  missing:         {len(missing)}")

    print("\n[1/4] Writing graph-generation shard YAMLs...")
    shard_paths = build_shard_yamls(missing, n_shards=args.n_shards)

    if not args.no_symlinks:
        print("\n[2/4] Extending swap-condition symlinks for new sources...")
        new_sources = [e["slug"] for e in missing if e["slug"] != TARGET_SLUG]
        extend_swap_condition_symlinks(new_sources)

    print("\n[3/4] Writing full-scale swap config YAMLs...")
    all_sources = [e["slug"] for e in entities if e["slug"] != TARGET_SLUG]
    write_full_swap_yamls(all_sources)

    print("\n[4/4] Writing launch scripts...")
    write_launch_scripts(shard_paths)

    print("\nDone. Next steps:")
    print("  1) bash tools/launch_phase3_graphs.sh   # ~1.7h wall-clock (8 GPUs in parallel)")
    print("  2) bash tools/launch_phase3_swaps.sh    # ~3.6h wall-clock (6 conds sequential x 8 GPUs each)")
    print("  Total expected: ~5.3h end-to-end.")
    print("\nMonitor with:")
    print("  tail -f logs/phase3/graphs_shard0.log")
    print("  tail -f logs/phase3/swap_human_dallas.log")


if __name__ == "__main__":
    main()
