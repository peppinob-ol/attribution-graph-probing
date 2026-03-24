#!/usr/bin/env python3
"""
Backfill per-swap features.json files for existing batch runs.

The GPU-batched pipeline writes features into shared _work/_gpu_batch_N/
files but not per-swap files.  The demo's detail panel needs per-swap
features at {run_dir}/work/{swap_id}/features.json to show expandable
feature links and source/target groupings.

This script re-computes features (CPU only, no GPU) and writes them,
using all available CPU cores via multiprocessing.

Usage:
    # Backfill a single config / run
    python backfill_swap_features.py --config configs/fullscale_usa_labeled.yml

    # Backfill with explicit run_id
    python backfill_swap_features.py --config configs/fullscale_usa_labeled.yml \
        --run-id fullscale_usa_labeled

    # Backfill all fullscale configs for a domain
    python backfill_swap_features.py \
        --config configs/fullscale_usa_labeled.yml \
        --config configs/fullscale_usa_random.yml \
        --config configs/fullscale_usa_field_add.yml

    # Control parallelism (default: all CPUs)
    python backfill_swap_features.py --config configs/fullscale_usa_labeled.yml --workers 16

    # Dry run to see what would be written
    python backfill_swap_features.py --config configs/fullscale_usa_labeled.yml --dry-run
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os
import sys
import time
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent.parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from pipeline.swap_loader import (
    SwapPair,
    load_swap_config,
    resolve_swap_pairs,
    get_swap_paths,
)
from pipeline.graph_loader import load_graph_data
from pipeline.controls import create_intervention_builder


def _load_ct_steering_module():
    steering_path = SCRIPTS_DIR / "03_ct_steering.py"
    spec = importlib.util.spec_from_file_location("ct_steering", steering_path)
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load module from {steering_path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["ct_steering"] = module
    spec.loader.exec_module(module)
    return module


def _expand_control_variants(config: Dict[str, Any]) -> List[Tuple[Dict[str, Any], str]]:
    """Same expansion as run_batch_swaps._expand_control_variants."""
    control_cfg = config.get("control", {})
    mode = control_cfg.get("mode", "labeled") if control_cfg else "labeled"
    replicates = control_cfg.get("replicates", 1)

    if mode == "additivity" and "runs" in control_cfg:
        variants = []
        for i, run_spec in enumerate(control_cfg["runs"]):
            cfg = copy.deepcopy(config)
            fields = run_spec.get("fields")
            roles = run_spec.get("concept_subset", run_spec.get("roles"))
            if fields is not None:
                cfg["control"]["concept_subset"] = {"fields": fields}
                suffix = "_".join(fields)
            elif roles is not None and isinstance(roles, list):
                cfg["control"]["concept_subset"] = {"roles": roles}
                suffix = "_".join(roles)
            else:
                cfg["control"]["concept_subset"] = run_spec
                suffix = f"v{i}"
            variants.append((cfg, f"add_{suffix}"))
        return variants

    if replicates <= 1:
        return [(config, "")]

    variants = []
    for r in range(replicates):
        cfg = copy.deepcopy(config)
        cfg["control"]["_current_replicate"] = r
        variants.append((cfg, f"r{r}"))
    return variants


# -- Worker function for multiprocessing --

def _process_chunk(
    chunk_pairs_serialized: List[Dict],
    config: Dict[str, Any],
    variants: List[Tuple[Dict[str, Any], str]],
    force: bool,
) -> Dict[str, int]:
    """Process a chunk of pairs in a worker process."""
    ct_steering = _load_ct_steering_module()

    written = 0
    skipped = 0
    errors = 0

    for pair_data in chunk_pairs_serialized:
        pair = SwapPair(**pair_data)
        paths = get_swap_paths(config, pair)
        try:
            data_from = load_graph_data(paths['from_graph_dir'], verbose=False)
            data_to = (
                load_graph_data(paths['to_graph_dir'], verbose=False)
                if pair.from_slug != pair.to_slug
                else data_from
            )
        except FileNotFoundError:
            errors += len(variants)
            continue

        for variant_config, variant_suffix in variants:
            swap_paths = get_swap_paths(config, pair, variant_suffix)
            features_path = swap_paths['work_dir'] / "features.json"

            if features_path.exists() and not force:
                skipped += 1
                continue

            try:
                variant_builder = create_intervention_builder(variant_config)
                result = variant_builder.build_for_pair(
                    ct_steering=ct_steering,
                    config=variant_config,
                    pair=pair,
                    data_from=data_from,
                    data_to=data_to,
                )
                features_path.parent.mkdir(parents=True, exist_ok=True)
                with open(features_path, "w", encoding="utf-8") as f:
                    json.dump(result.features, f, indent=2)
                written += 1
            except Exception:
                errors += 1

    return {"written": written, "skipped": skipped, "errors": errors}


def _serialize_pair(pair: SwapPair) -> Dict:
    """Convert SwapPair to a plain dict for pickling across processes."""
    return {
        "from_slug": pair.from_slug,
        "to_slug": pair.to_slug,
        "from_entity": pair.from_entity,
        "to_entity": pair.to_entity,
        "from_concept_str": pair.from_concept_str,
        "to_concept_str": pair.to_concept_str,
    }


def backfill_features(
    config_path: str,
    *,
    run_id: Optional[str] = None,
    dry_run: bool = False,
    force: bool = False,
    workers: int = 0,
) -> Dict[str, int]:
    """
    Backfill per-swap features.json for one config.

    Returns dict with counts: written, skipped, errors.
    """
    print(f"\n{'='*60}")
    print(f"  Config: {config_path}")
    print(f"{'='*60}")

    config = load_swap_config(config_path)

    graphs_root = Path(config["inputs"]["graphs_root"])
    swaps_base = graphs_root / "_swaps"

    effective_run_id = run_id or config.get("experiment_name", "")
    run_dir = swaps_base / "runs" / effective_run_id
    if not run_dir.exists():
        print(f"  Run directory not found: {run_dir}")
        return {"written": 0, "skipped": 0, "errors": 0}

    config["_swaps_dir"] = str(run_dir)
    print(f"  Run dir: {run_dir}")

    pairs = resolve_swap_pairs(config)
    variants = _expand_control_variants(config)
    total_items = len(pairs) * len(variants)

    print(f"  Pairs: {len(pairs)}, Variants: {len(variants)}, "
          f"Total items: {total_items}")

    if dry_run:
        print(f"  [DRY RUN] Would write up to {total_items} features.json files")
        return {"written": total_items, "skipped": 0, "errors": 0}

    n_workers = workers or min(os.cpu_count() or 4, len(pairs))
    n_workers = max(1, min(n_workers, len(pairs)))
    print(f"  Workers: {n_workers}")

    chunk_size = max(1, len(pairs) // n_workers)
    chunks = []
    for i in range(0, len(pairs), chunk_size):
        chunk = [_serialize_pair(p) for p in pairs[i:i + chunk_size]]
        chunks.append(chunk)

    start = time.time()
    totals: Dict[str, int] = {"written": 0, "skipped": 0, "errors": 0}

    with ProcessPoolExecutor(max_workers=n_workers) as executor:
        futures = {
            executor.submit(_process_chunk, chunk, config, variants, force): idx
            for idx, chunk in enumerate(chunks)
        }
        done_items = 0
        for future in as_completed(futures):
            result = future.result()
            for k in totals:
                totals[k] += result[k]
            done_items += result["written"] + result["skipped"] + result["errors"]
            elapsed = time.time() - start
            rate = done_items / elapsed if elapsed > 0 else 0
            remaining = (total_items - done_items) / rate if rate > 0 else 0
            print(f"  Progress: {done_items}/{total_items} "
                  f"({elapsed:.0f}s elapsed, ~{remaining:.0f}s remaining)")

    elapsed = time.time() - start
    print(f"  Done in {elapsed:.1f}s -- Written: {totals['written']}, "
          f"Skipped: {totals['skipped']}, Errors: {totals['errors']}")
    return totals


def main():
    parser = argparse.ArgumentParser(
        description="Backfill per-swap features.json for existing batch runs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--config", action="append", required=True, dest="configs",
        help="Swap config YAML (can specify multiple times)",
    )
    parser.add_argument(
        "--run-id", default=None,
        help="Override run_id (default: experiment_name from config)",
    )
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument(
        "--force", action="store_true",
        help="Overwrite existing features.json files",
    )
    parser.add_argument(
        "--workers", type=int, default=0,
        help="Number of parallel workers (default: all CPUs)",
    )
    args = parser.parse_args()

    totals = {"written": 0, "skipped": 0, "errors": 0}
    for config_path in args.configs:
        counts = backfill_features(
            config_path, run_id=args.run_id,
            dry_run=args.dry_run, force=args.force,
            workers=args.workers,
        )
        for k in totals:
            totals[k] += counts[k]

    print(f"\n{'='*60}")
    print(f"  TOTAL: {totals['written']} written, "
          f"{totals['skipped']} skipped, {totals['errors']} errors")
    print(f"{'='*60}")


if __name__ == "__main__":
    main()
