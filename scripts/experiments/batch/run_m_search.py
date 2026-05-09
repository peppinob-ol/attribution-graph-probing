#!/usr/bin/env python3
"""
Post-hoc adaptive M_amplify search on existing baseline runs.

Reads all swap results from a baseline run, identifies misses, and
runs the two-phase M search on each. Results are saved as ``__m_tuned``
variant files alongside the original results.

Supports cross-run filtering (``--all-runs``) to skip pairs that already
have a hit in any fullscale run/variant, and multi-GPU parallelism
(``--gpu-ids``).

Usage::

    # Single GPU, single run filter
    python run_m_search.py \\
        --dataset usa_states_batch \\
        --baseline-run fullscale_usa_labeled

    # All GPUs, cross-run filter
    python run_m_search.py \\
        --dataset usa_states_batch \\
        --baseline-run fullscale_usa_labeled \\
        --all-runs --gpu-ids 0 1 2 3 4 5 6 7

"""
from __future__ import annotations

import argparse
import json
import logging
import math
import os
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from pipeline.swap_loader import SwapPair
from pipeline.swap_evaluator import evaluate_swap
from pipeline.m_search import search_optimal_m, build_steer_fn
from run_batch_swaps import (
    _run_local_ct_steering,
    _enable_inprocess_ct_steering,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Cross-run hit collection
# ---------------------------------------------------------------------------

def _collect_cross_run_hits(
    dataset_root: Path,
    run_ids: List[str],
) -> Set[Tuple[str, str]]:
    """Scan multiple runs and return pairs that have at least one hit.

    Checks ALL files (including ``__add_*``, ``__r*`` variants) in each
    run's ``by_source/`` directory.

    Returns a set of ``(from_slug, to_slug)`` tuples.
    """
    hit_pairs: Set[Tuple[str, str]] = set()
    runs_dir = dataset_root / "_swaps" / "runs"

    for run_id in run_ids:
        by_source = runs_dir / run_id / "by_source"
        if not by_source.is_dir():
            continue
        for source_dir in by_source.iterdir():
            if not source_dir.is_dir():
                continue
            from_slug = source_dir.name
            for fpath in source_dir.glob("to_*.json"):
                stem = fpath.stem.replace("to_", "", 1)
                to_slug = stem.split("__", 1)[0]
                if from_slug == to_slug:
                    continue
                pair = (from_slug, to_slug)
                if pair in hit_pairs:
                    continue
                try:
                    data = json.loads(fpath.read_text(encoding="utf-8"))
                except (json.JSONDecodeError, OSError):
                    continue
                if data.get("evaluation", {}).get("exact_match", {}).get(
                    "steered_has_to_answer", False
                ):
                    hit_pairs.add(pair)

    return hit_pairs


def _discover_fullscale_runs(dataset_root: Path) -> List[str]:
    """Return names of all ``fullscale_*`` run directories."""
    runs_dir = dataset_root / "_swaps" / "runs"
    if not runs_dir.is_dir():
        return []
    return sorted(
        d.name for d in runs_dir.iterdir()
        if d.is_dir() and d.name.startswith("fullscale_")
    )


# ---------------------------------------------------------------------------
# Pair collection (enhanced)
# ---------------------------------------------------------------------------

def _collect_missed_pairs(
    run_dir: Path,
    cross_run_hits: Optional[Set[Tuple[str, str]]] = None,
) -> List[Dict[str, Any]]:
    """Scan by_source/ for non-identity misses without ``__m_tuned``.

    If *cross_run_hits* is provided, also skip pairs present in that set
    (they already have a hit in another run/variant).
    """
    by_source = run_dir / "by_source"
    if not by_source.exists():
        return []

    missed: List[Dict[str, Any]] = []
    for source_dir in sorted(by_source.iterdir()):
        if not source_dir.is_dir():
            continue
        for result_file in sorted(source_dir.glob("to_*.json")):
            if "__" in result_file.stem.split("to_", 1)[-1]:
                continue

            tuned_file = result_file.with_name(
                f"{result_file.stem}__m_tuned.json"
            )
            if tuned_file.exists():
                continue

            try:
                with open(result_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            ev = data.get("evaluation", {}).get("exact_match", {})
            if ev.get("steered_has_to_answer"):
                continue

            src = data.get("source", {})
            tgt = data.get("target", {})
            from_slug = src.get("slug", "")
            to_slug = tgt.get("slug", "")
            if from_slug == to_slug:
                continue

            if cross_run_hits and (from_slug, to_slug) in cross_run_hits:
                continue

            missed.append({
                "result_file": result_file,
                "data": data,
                "from_slug": from_slug,
                "to_slug": to_slug,
                "source_entity": src,
                "target_entity": tgt,
            })

    return missed


def _collect_missed_pairs_random(
    run_dir: Path,
    cross_run_hits: Optional[Set[Tuple[str, str]]] = None,
) -> List[Dict[str, Any]]:
    """Scan a matched-random run for missed replicate files.

    Random runs emit one file per replicate per pair, with stem
    ``to_<tgt>__r{N}``.  Each replicate is its own M-search target: the
    output ``to_<tgt>__r{N}__m_tuned.json`` lives alongside the source
    file and reuses ``work/<from>__to__<tgt>__r{N}/features.json``.

    The cross-run-hit filter is intentionally NOT applied here: we want
    the random null distribution at adaptive M for every pair, even when
    the labeled side already hits.
    """
    by_source = run_dir / "by_source"
    if not by_source.exists():
        return []

    missed: List[Dict[str, Any]] = []
    for source_dir in sorted(by_source.iterdir()):
        if not source_dir.is_dir():
            continue
        from_slug = source_dir.name
        for result_file in sorted(source_dir.glob("to_*__r*.json")):
            if "__m_tuned" in result_file.stem:
                continue
            stem = result_file.stem.replace("to_", "", 1)
            parts = stem.split("__", 1)
            if len(parts) != 2:
                continue
            to_slug, variant_suffix = parts[0], parts[1]
            if not variant_suffix.startswith("r"):
                continue
            if from_slug == to_slug:
                continue

            tuned_file = result_file.with_name(
                f"{result_file.stem}__m_tuned.json"
            )
            if tuned_file.exists():
                continue

            try:
                with open(result_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            ev = data.get("evaluation", {}).get("exact_match", {})
            if ev.get("steered_has_to_answer"):
                continue

            if cross_run_hits and (from_slug, to_slug) in cross_run_hits:
                continue

            missed.append({
                "result_file": result_file,
                "data": data,
                "variant_suffix": variant_suffix,
                "from_slug": from_slug,
                "to_slug": to_slug,
                "source_entity": data.get("source", {}),
                "target_entity": data.get("target", {}),
            })

    return missed


def _collect_missed_pairs_additivity(
    run_dir: Path,
    cross_run_hits: Optional[Set[Tuple[str, str]]] = None,
) -> List[Dict[str, Any]]:
    """Scan an additivity run for missed pairs, picking the best variant.

    Groups all ``__add_*`` files by ``(from_slug, to_slug)``.  Skips pairs
    that already have a hit in any variant (or in *cross_run_hits*).  For
    each fully-missed pair, selects the single best variant by a
    lexicographic score (tier, exact_match flags, -target_rank, vsmax) and
    returns one item per pair with a ``variant_suffix`` field so the worker
    can resolve the correct work directory and output filename.
    """
    by_source = run_dir / "by_source"
    if not by_source.exists():
        return []

    # Group variants by canonical pair
    PairKey = Tuple[str, str]
    pair_variants: Dict[PairKey, List[Dict[str, Any]]] = {}

    for source_dir in sorted(by_source.iterdir()):
        if not source_dir.is_dir():
            continue
        from_slug = source_dir.name
        for result_file in sorted(source_dir.glob("to_*__add_*.json")):
            if "__m_tuned" in result_file.stem:
                continue
            stem = result_file.stem.replace("to_", "", 1)
            to_slug = stem.split("__", 1)[0]
            variant_suffix = stem.split("__", 1)[1] if "__" in stem else ""
            if from_slug == to_slug:
                continue
            pk: PairKey = (from_slug, to_slug)
            pair_variants.setdefault(pk, []).append({
                "result_file": result_file,
                "variant_suffix": variant_suffix,
            })

    missed: List[Dict[str, Any]] = []

    for (from_slug, to_slug), variants in sorted(pair_variants.items()):
        if cross_run_hits and (from_slug, to_slug) in cross_run_hits:
            continue

        # Check if ANY variant hit; also find best non-hit variant
        any_hit = False
        best_score: Optional[Tuple] = None
        best_rec: Optional[Dict[str, Any]] = None

        for rec in variants:
            tuned_path = rec["result_file"].with_name(
                f"{rec['result_file'].stem}__m_tuned.json"
            )
            if tuned_path.exists():
                any_hit = True
                break

            try:
                with open(rec["result_file"], "r", encoding="utf-8") as f:
                    data = json.load(f)
            except (json.JSONDecodeError, OSError):
                continue

            ev = data.get("evaluation", {}).get("exact_match", {})
            if ev.get("steered_has_to_answer"):
                any_hit = True
                break

            tier = data.get("classification", {}).get("tier") or 0
            has_answer = bool(ev.get("steered_has_to_answer"))
            has_capital = bool(ev.get("steered_has_to_capital"))
            bl = data.get("evaluation", {}).get("baseline_logits", {})
            rank = bl.get("target", {}).get("rank")
            neg_rank = -rank if rank is not None else float("-inf")
            traj = data.get("evaluation", {}).get(
                "logit_trajectory", {}
            ).get("contrast_groups", {}).get(
                "same_dataset", {}
            ).get("aggregate", {}).get("best_target_minus_max")
            vsmax = traj if traj is not None else float("-inf")
            score = (tier, has_answer, has_capital, neg_rank, vsmax)

            if best_score is None or score > best_score:
                best_score = score
                best_rec = {
                    "result_file": rec["result_file"],
                    "data": data,
                    "variant_suffix": rec["variant_suffix"],
                    "from_slug": from_slug,
                    "to_slug": to_slug,
                    "source_entity": data.get("source", {}),
                    "target_entity": data.get("target", {}),
                }

        if any_hit or best_rec is None:
            continue

        missed.append(best_rec)

    return missed


# ---------------------------------------------------------------------------
# Per-GPU worker
# ---------------------------------------------------------------------------

def _run_gpu_chunk(
    gpu_id: int,
    chunk: List[Dict[str, Any]],
    config: Dict[str, Any],
    run_dir: Path,
    m_original: float,
    m_min: float,
    n_coarse_probes: int,
    n_fine_steps: int,
    log_tolerance: float,
    min_kl_drop: float,
    verbose: bool,
) -> Tuple[int, int, int, float]:
    """Process a chunk of missed pairs on a single GPU.

    Returns ``(n_processed, n_hits, total_steps, elapsed_s)``.
    """
    hits = 0
    total_steps = 0
    n_processed = 0
    start = time.time()

    for i, item in enumerate(chunk, 1):
        from_slug = item["from_slug"]
        to_slug = item["to_slug"]
        variant_label = f" [{item.get('variant_suffix', '')}]" if item.get("variant_suffix") else ""
        logger.info("[GPU %d] [%d/%d] %s -> %s%s",
                     gpu_id, i, len(chunk), from_slug, to_slug, variant_label)

        variant_suffix = item.get("variant_suffix", "")
        work_name = f"{from_slug}__to__{to_slug}__{variant_suffix}" if variant_suffix else f"{from_slug}__to__{to_slug}"
        work_dir = run_dir / "work" / work_name
        features_file = work_dir / "features.json"
        if not features_file.exists():
            logger.info("  SKIP: no features.json")
            continue

        with open(features_file, "r", encoding="utf-8") as f:
            features = json.load(f)

        prompt_text = item["data"].get("source", {}).get("prompt", "")
        if not prompt_text:
            logger.info("  SKIP: no prompt in result")
            continue

        pair = SwapPair(
            from_slug=from_slug,
            to_slug=to_slug,
            from_entity=item["source_entity"],
            to_entity=item["target_entity"],
        )

        def _factory(
            _features=features, _prompt=prompt_text,
            _pair=pair, _work_dir=work_dir, _gpu_id=gpu_id,
        ):
            return build_steer_fn(
                features=_features,
                prompt=_prompt,
                pair=_pair,
                config=config,
                work_dir=_work_dir,
                evaluate_swap_fn=evaluate_swap,
                run_steering_fn=_run_local_ct_steering,
                gpu_id=_gpu_id,
                verbose=verbose,
            )

        tuned = search_optimal_m(
            _factory, item["data"], m_original,
            m_min=m_min,
            n_coarse_probes=n_coarse_probes,
            n_fine_steps=n_fine_steps,
            log_tolerance=log_tolerance,
            min_kl_drop=min_kl_drop,
        )

        n_processed += 1

        if tuned:
            m_info = tuned.get("m_search", {})
            tuned_path = item["result_file"].with_name(
                f"{item['result_file'].stem}__m_tuned.json"
            )
            tuned_path.parent.mkdir(parents=True, exist_ok=True)
            with open(tuned_path, "w", encoding="utf-8") as f:
                json.dump(tuned, f, indent=2, ensure_ascii=False)
            hits += 1
            steps = m_info.get("total_steps", 0)
            total_steps += steps
            m_val = m_info.get("m_tuned")
            m_str = (f"{m_val:.4f}" if isinstance(m_val, (int, float))
                     else str(m_val))
            logger.info("  HIT at M=%s (phase %s, %d steps)",
                        m_str, m_info.get("phase"), steps)
        else:
            total_steps += n_coarse_probes + n_fine_steps
            logger.info("  no hit at any M")

        # Clean up _m_search temp files after each pair
        m_search_tmp = work_dir / "_m_search"
        if m_search_tmp.exists():
            import shutil
            shutil.rmtree(m_search_tmp, ignore_errors=True)

    elapsed = time.time() - start
    return n_processed, hits, total_steps, elapsed


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Post-hoc adaptive M search on existing runs",
    )
    parser.add_argument(
        "--dataset", required=True,
        help="Dataset dir name under output/ (e.g. usa_states_batch)",
    )
    parser.add_argument(
        "--baseline-run", required=True,
        help="Run ID (directory name under _swaps/runs/)",
    )
    # Cross-run filtering
    parser.add_argument(
        "--all-runs", action="store_true",
        help="Check ALL fullscale runs for existing hits (not just baseline)",
    )
    parser.add_argument(
        "--runs-to-check", nargs="*", default=None,
        help="Explicit run IDs to check for hits (overrides --all-runs)",
    )
    # Multi-GPU
    parser.add_argument(
        "--gpu-ids", nargs="*", type=int, default=None,
        help="GPU IDs for parallel execution (e.g. 0 1 2 3 4 5 6 7)",
    )
    # M-search params
    parser.add_argument("--m-min", type=float, default=0.1)
    parser.add_argument("--n-coarse-probes", type=int, default=6)
    parser.add_argument("--n-fine-steps", type=int, default=6)
    parser.add_argument("--log-tolerance", type=float, default=0.1)
    parser.add_argument("--min-kl-drop", type=float, default=1.0)
    # Filtering
    parser.add_argument(
        "--limit", type=int, default=None,
        help="Max pairs to process (for testing)",
    )
    parser.add_argument(
        "--pair", type=str, default=None,
        help="Single pair to process (from_slug:to_slug)",
    )
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument(
        "--mode", choices=["auto", "labeled", "additivity", "random"],
        default="auto",
        help=(
            "Which collector to use. 'auto' (default) infers from "
            "config.control.mode (additivity/random_feature_matched). "
            "Use 'random' to scan __r{N} replicate files; the cross-run "
            "hit filter is ignored in this mode."
        ),
    )
    parser.add_argument(
        "--in-process", action="store_true",
        help=(
            "Keep one ReplacementModel resident in this process (single "
            "GPU only; ~10x faster than the default per-probe subprocess "
            "fallback). When combined with multiple --gpu-ids, the parent "
            "spawns one --in-process child subprocess per GPU."
        ),
    )
    parser.add_argument(
        "--shard-of", type=int, default=None,
        help="Shard total (used internally when parent spawns per-GPU children).",
    )
    parser.add_argument(
        "--shard-idx", type=int, default=None,
        help="Shard index in [0, --shard-of) (used internally).",
    )
    parser.add_argument(
        "--restrict-slugs", type=str, default=None,
        help=(
            "Optional path to a JSON file containing a list of allowed "
            "entity slugs; pairs whose source or target is not in the "
            "list are skipped. Used to scope random M-search to the demo "
            "intersection."
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    repo_root = Path(__file__).resolve().parents[3]
    dataset_root = repo_root / "output" / args.dataset
    run_dir = dataset_root / "_swaps" / "runs" / args.baseline_run

    if not run_dir.exists():
        print(f"ERROR: Run directory not found: {run_dir}")
        sys.exit(1)

    config_path = run_dir / "config_resolved.json"
    if not config_path.exists():
        print(f"ERROR: config_resolved.json not found in {run_dir}")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    config["_swaps_dir"] = str(run_dir)
    m_original = config.get("ct_steering", {}).get("M_amplify", 20.0)

    gpu_ids = args.gpu_ids or [0]
    n_gpus = len(gpu_ids)

    # ---- Cross-run hit filter ----
    cross_run_hits: Optional[Set[Tuple[str, str]]] = None
    if args.runs_to_check:
        check_runs = args.runs_to_check
    elif args.all_runs:
        check_runs = _discover_fullscale_runs(dataset_root)
    else:
        check_runs = None

    if check_runs:
        print(f"Scanning {len(check_runs)} runs for existing hits: "
              f"{check_runs}")
        t0 = time.time()
        cross_run_hits = _collect_cross_run_hits(dataset_root, check_runs)
        print(f"  Found {len(cross_run_hits)} pairs with hits "
              f"({time.time() - t0:.1f}s)")

    # ---- Resolve effective mode ----
    control_mode = config.get("control", {}).get("mode", "")
    if args.mode == "auto":
        if control_mode == "additivity":
            effective_mode = "additivity"
        elif control_mode == "random_feature_matched":
            effective_mode = "random"
        else:
            effective_mode = "labeled"
    else:
        effective_mode = args.mode

    if effective_mode == "additivity":
        print(f"Additivity run detected -- scanning __add_* variants")
    elif effective_mode == "random":
        print(f"Random run detected -- scanning __r* replicate files; "
              f"cross-run hit filter is disabled in random mode.")

    # ---- Collect eligible pairs ----
    if effective_mode == "additivity":
        missed = _collect_missed_pairs_additivity(run_dir, cross_run_hits)
    elif effective_mode == "random":
        # Random: cross-run hits from labeled runs are irrelevant; we want
        # the random null distribution at adaptive M for every pair.
        missed = _collect_missed_pairs_random(run_dir, cross_run_hits=None)
    else:
        missed = _collect_missed_pairs(run_dir, cross_run_hits)
    if args.pair:
        from_slug, to_slug = args.pair.split(":")
        missed = [m for m in missed
                  if m["from_slug"] == from_slug and m["to_slug"] == to_slug]

    if args.restrict_slugs:
        with open(args.restrict_slugs, "r", encoding="utf-8") as f:
            allowed = set(json.load(f))
        before = len(missed)
        missed = [m for m in missed
                  if m["from_slug"] in allowed and m["to_slug"] in allowed]
        print(f"Restricted to {len(allowed)} slugs from "
              f"{args.restrict_slugs}: {before} -> {len(missed)} pairs")

    if args.limit is not None:
        missed = missed[:args.limit]

    # ---- Shard for per-GPU subprocess workers ----
    if args.shard_of is not None and args.shard_idx is not None:
        if not (0 <= args.shard_idx < args.shard_of):
            print(f"ERROR: --shard-idx must be in [0, --shard-of)")
            sys.exit(2)
        before = len(missed)
        missed = [m for i, m in enumerate(missed)
                  if i % args.shard_of == args.shard_idx]
        print(f"Shard {args.shard_idx}/{args.shard_of}: "
              f"{before} -> {len(missed)} pairs")

    print(f"\nDataset: {args.dataset}")
    print(f"Baseline run: {args.baseline_run}")
    print(f"M range: [{args.m_min}, {m_original}]")
    print(f"Budget: {args.n_coarse_probes} coarse + {args.n_fine_steps} fine "
          f"= {args.n_coarse_probes + args.n_fine_steps} max/pair")
    print(f"GPUs: {gpu_ids}")
    print(f"In-process: {args.in_process}")
    print(f"Eligible pairs: {len(missed)}")

    if not missed:
        print("Nothing to do.")
        return

    # ---- Parent dispatch: in-process + multi-GPU spawns child subprocesses ----
    if args.in_process and n_gpus > 1 and args.shard_of is None:
        return _spawn_per_gpu_children(args, gpu_ids, len(missed))

    # ---- Single-process execution ----
    if args.in_process:
        # When the parent dispatched us as a shard child, CUDA_VISIBLE_DEVICES
        # is already pinned to the assigned physical GPU; do NOT clobber it.
        # When invoked directly (no shard), pin to --gpu-ids[0] so the lone
        # process sees only that physical GPU.
        if args.shard_of is None:
            target_gpu = gpu_ids[0]
            os.environ["CUDA_VISIBLE_DEVICES"] = str(target_gpu)
        os.environ.setdefault(
            "PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True"
        )
        _enable_inprocess_ct_steering(True)
        # Inside the child's CUDA-visible space the device is index 0.
        gpu_ids = [0]
        n_gpus = 1

    # ---- Distribute across GPUs ----
    if n_gpus == 1:
        n_proc, n_hits, tot_steps, elapsed = _run_gpu_chunk(
            gpu_ids[0], missed, config, run_dir, m_original,
            m_min=args.m_min,
            n_coarse_probes=args.n_coarse_probes,
            n_fine_steps=args.n_fine_steps,
            log_tolerance=args.log_tolerance,
            min_kl_drop=args.min_kl_drop,
            verbose=args.verbose,
        )
        _print_summary(len(missed), n_hits, tot_steps, elapsed)
        return

    actual_n = min(n_gpus, len(missed))
    batch_size = math.ceil(len(missed) / actual_n)
    chunks = [
        missed[i : i + batch_size]
        for i in range(0, len(missed), batch_size)
    ]

    print(f"Distributing {len(missed)} pairs across {len(chunks)} GPUs "
          f"(~{batch_size} pairs/GPU)")

    total_hits = 0
    total_steps = 0
    total_processed = 0
    global_start = time.time()

    with ThreadPoolExecutor(max_workers=len(chunks)) as executor:
        futures = {}
        for idx, chunk in enumerate(chunks):
            gid = gpu_ids[idx]
            fut = executor.submit(
                _run_gpu_chunk,
                gid, chunk, config, run_dir, m_original,
                m_min=args.m_min,
                n_coarse_probes=args.n_coarse_probes,
                n_fine_steps=args.n_fine_steps,
                log_tolerance=args.log_tolerance,
                min_kl_drop=args.min_kl_drop,
                verbose=args.verbose,
            )
            futures[fut] = gid

        for fut in as_completed(futures):
            gid = futures[fut]
            try:
                n_proc, n_hits, steps, elapsed = fut.result()
                total_processed += n_proc
                total_hits += n_hits
                total_steps += steps
                print(f"  GPU {gid} done: {n_proc} pairs, "
                      f"{n_hits} hits, {elapsed:.0f}s")
            except Exception as exc:
                print(f"  GPU {gid} FAILED: {exc}")

    global_elapsed = time.time() - global_start
    _print_summary(len(missed), total_hits, total_steps, global_elapsed)


def _spawn_per_gpu_children(
    args: argparse.Namespace,
    gpu_ids: List[int],
    n_pairs_total: int,
) -> None:
    """Launch one --in-process child subprocess per GPU.

    Each child re-executes ``run_m_search.py`` with ``--gpu-ids <single>
    --in-process --shard-of N --shard-idx K``. The child's
    ``CUDA_VISIBLE_DEVICES`` is set explicitly so the resident
    ReplacementModel only sees its assigned GPU.
    """
    n = len(gpu_ids)
    print(f"\nSpawning {n} per-GPU child subprocesses (in-process mode)\n")

    base_cmd = [
        sys.executable, "-u", str(SCRIPT_DIR / "run_m_search.py"),
        "--dataset", args.dataset,
        "--baseline-run", args.baseline_run,
        "--mode", args.mode,
        "--in-process",
        "--m-min", str(args.m_min),
        "--n-coarse-probes", str(args.n_coarse_probes),
        "--n-fine-steps", str(args.n_fine_steps),
        "--log-tolerance", str(args.log_tolerance),
        "--min-kl-drop", str(args.min_kl_drop),
    ]
    if args.all_runs:
        base_cmd.append("--all-runs")
    if args.runs_to_check:
        base_cmd.extend(["--runs-to-check", *args.runs_to_check])
    if args.restrict_slugs:
        base_cmd.extend(["--restrict-slugs", args.restrict_slugs])
    if args.verbose:
        base_cmd.append("-v")

    procs = []
    log_dir = SCRIPT_DIR.parent.parent.parent / "logs" / "msearch_workers"
    log_dir.mkdir(parents=True, exist_ok=True)
    stamp = time.strftime("%Y%m%d_%H%M%S")
    for k, gpu_id in enumerate(gpu_ids):
        env = os.environ.copy()
        env["CUDA_VISIBLE_DEVICES"] = str(gpu_id)
        env.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
        cmd = base_cmd + [
            "--gpu-ids", "0",
            "--shard-of", str(n),
            "--shard-idx", str(k),
        ]
        log_path = log_dir / f"{args.baseline_run}_gpu{gpu_id}_shard{k}_{stamp}.log"
        log_f = open(log_path, "w", encoding="utf-8")
        print(f"  GPU {gpu_id}: shard {k}/{n} -> {log_path}")
        p = subprocess.Popen(cmd, env=env, stdout=log_f, stderr=subprocess.STDOUT)
        procs.append((gpu_id, k, p, log_f, log_path))

    print(f"\nLaunched {len(procs)} workers; waiting...\n")
    start = time.time()
    failures = []
    for gpu_id, k, p, log_f, log_path in procs:
        rc = p.wait()
        log_f.close()
        elapsed = time.time() - start
        status = "OK" if rc == 0 else f"FAIL rc={rc}"
        print(f"  GPU {gpu_id} shard {k}: {status} "
              f"({elapsed:.0f}s wall, log={log_path.name})")
        if rc != 0:
            failures.append((gpu_id, k, log_path))

    if failures:
        print(f"\n{len(failures)} workers failed:")
        for gpu_id, k, lp in failures:
            print(f"  GPU {gpu_id} shard {k}: {lp}")
            # Print last 20 lines of failed log for context.
            try:
                tail = lp.read_text().splitlines()[-20:]
                for line in tail:
                    print(f"    {line}")
            except OSError:
                pass


def _print_summary(n_pairs: int, n_hits: int, total_steps: int,
                   elapsed: float) -> None:
    print(f"\n--- Summary ---")
    print(f"Pairs searched: {n_pairs}")
    print(f"New hits: {n_hits} "
          f"({100 * n_hits / n_pairs:.1f}%)" if n_pairs else "")
    print(f"Total GPU calls: ~{total_steps}")
    print(f"Time: {elapsed:.0f}s")
    if n_pairs:
        print(f"  ({elapsed / n_pairs:.1f}s/pair)")


if __name__ == "__main__":
    main()
