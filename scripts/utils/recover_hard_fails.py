#!/usr/bin/env python3
"""
Recovery probe for hard-fail swap pairs.

A "hard-fail" pair is one that produced no hit in any field-add variant or
the labeled run at the default M_amplify=20 (see /tmp/hard_fail_pairs.json
or output/research/_pos0_manual_rescore_summary.json for definitions).

This script runs the existing two-phase adaptive M-search
(scripts/experiments/batch/pipeline/m_search.py) on each hard-fail pair,
but applies it to the top-K variants (ranked by vsmax) instead of just
the single picker-best variant. The motivation is empirical: m-tuned hits
on already-recovered pairs almost always succeed at M < 20 (typically
M in [4, 12]), and the variant that wins at low M is often NOT the one
with the best vsmax at M=20 (the default M disrupts the logits enough
that the "best" variant choice itself is biased).

For every probe that produces a hit, a ``__m_tuned.json`` file is written
next to the original variant result file.

Typical invocation::

    .venv/bin/python scripts/utils/recover_hard_fails.py \
        --dataset usa_states_batch \
        --gpu-ids 0 1 2 3 4 5 6 7 \
        --top-k-variants 3
"""
from __future__ import annotations

import argparse
import json
import logging
import math
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
BATCH_DIR = REPO_ROOT / "scripts" / "experiments" / "batch"
PIPELINE_DIR = BATCH_DIR / "pipeline"
for p in (BATCH_DIR, PIPELINE_DIR.parent):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

from pipeline.swap_loader import SwapPair  # type: ignore
from pipeline.swap_evaluator import evaluate_swap  # type: ignore
from pipeline.m_search import search_optimal_m, build_steer_fn  # type: ignore
from run_batch_swaps import _run_local_ct_steering  # type: ignore

logger = logging.getLogger(__name__)


DATASET_RUNS: Dict[str, Tuple[str, str]] = {
    "usa_states_batch":              ("fullscale_usa_labeled", "fullscale_usa_field_add"),
    "book_characters_authors_batch": ("fullscale_books_labeled", "fullscale_books_field_add"),
    "products_founders_batch":       ("fullscale_products_labeled", "fullscale_products_field_add"),
    "paintings_painters_batch":      ("fullscale_paintings_labeled", "fullscale_paintings_field_add"),
}

# Variants we always probe regardless of vsmax ordering, when present.
PRIORITY_VARIANTS = ["add_state_capital", "add_capital"]


def _vsmax(data: Dict[str, Any]) -> float:
    traj = (
        data.get("evaluation", {})
        .get("logit_trajectory", {})
        .get("contrast_groups", {})
        .get("same_dataset", {})
        .get("aggregate", {})
        .get("best_target_minus_max")
    )
    return float(traj) if traj is not None else float("-inf")


def _has_hit(data: Dict[str, Any]) -> bool:
    return bool(
        data.get("evaluation", {}).get("exact_match", {}).get("steered_has_to_answer")
    )


def _collect_pair_variants(
    run_dir: Path, from_slug: str, to_slug: str
) -> List[Dict[str, Any]]:
    """Return list of variant entries (sorted by score descending)."""
    src_dir = run_dir / "by_source" / from_slug
    if not src_dir.is_dir():
        return []
    variants: List[Dict[str, Any]] = []
    for fp in src_dir.glob(f"to_{to_slug}__add_*.json"):
        if "__m_tuned" in fp.stem:
            continue
        try:
            data = json.loads(fp.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            continue
        suffix = fp.stem.split("__", 1)[1]
        variants.append({
            "result_file": fp,
            "data": data,
            "variant_suffix": suffix,
            "vsmax": _vsmax(data),
            "is_priority": suffix in PRIORITY_VARIANTS,
        })

    variants.sort(
        key=lambda v: (v["is_priority"], v["vsmax"]),
        reverse=True,
    )
    return variants


def _select_variants_for_probe(
    variants: List[Dict[str, Any]], top_k: int
) -> List[Dict[str, Any]]:
    """Pick variants to m-search.

    Always include priority variants (add_state_capital, add_capital) when
    available, plus the top_k by vsmax. Capped to avoid duplicates.
    """
    if not variants:
        return []
    chosen: List[Dict[str, Any]] = []
    seen: set = set()

    # Priority first
    for v in variants:
        if v["is_priority"] and v["variant_suffix"] not in seen:
            chosen.append(v)
            seen.add(v["variant_suffix"])

    # Top-k by vsmax
    for v in sorted(variants, key=lambda x: x["vsmax"], reverse=True):
        if v["variant_suffix"] in seen:
            continue
        if len(chosen) >= top_k + len(PRIORITY_VARIANTS):
            break
        chosen.append(v)
        seen.add(v["variant_suffix"])

    return chosen[: top_k + len(PRIORITY_VARIANTS)]


def _process_pair(
    item: Dict[str, Any],
    config: Dict[str, Any],
    run_dir: Path,
    m_original: float,
    m_min: float,
    n_coarse_probes: int,
    n_fine_steps: int,
    log_tolerance: float,
    min_kl_drop: float,
    gpu_id: int,
    verbose: bool,
) -> Tuple[bool, int, str]:
    """Run m-search on one (pair, variant) item.

    Returns (hit, n_steps, info_string).
    """
    from_slug = item["from_slug"]
    to_slug = item["to_slug"]
    suffix = item["variant_suffix"]

    work_name = f"{from_slug}__to__{to_slug}__{suffix}"
    work_dir = run_dir / "work" / work_name
    features_file = work_dir / "features.json"
    if not features_file.exists():
        return False, 0, "no_features"

    with open(features_file, "r", encoding="utf-8") as f:
        features = json.load(f)

    prompt_text = item["data"].get("source", {}).get("prompt", "")
    if not prompt_text:
        return False, 0, "no_prompt"

    pair = SwapPair(
        from_slug=from_slug,
        to_slug=to_slug,
        from_entity=item["data"].get("source", {}),
        to_entity=item["data"].get("target", {}),
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

    # Cleanup tmp
    m_search_tmp = work_dir / "_m_search"
    if m_search_tmp.exists():
        import shutil
        shutil.rmtree(m_search_tmp, ignore_errors=True)

    if not tuned:
        return False, n_coarse_probes + n_fine_steps, f"no_hit_{suffix}"

    m_info = tuned.get("m_search", {})
    tuned_path = item["result_file"].with_name(
        f"{item['result_file'].stem}__m_tuned.json"
    )
    tuned_path.parent.mkdir(parents=True, exist_ok=True)
    with open(tuned_path, "w", encoding="utf-8") as f:
        json.dump(tuned, f, indent=2, ensure_ascii=False)
    m_val = m_info.get("m_tuned")
    return True, m_info.get("total_steps", 0), f"hit_M={m_val:.3f}_{suffix}"


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
    stop_on_first_variant_hit: bool,
) -> Dict[str, Any]:
    pairs_done: set = set()
    n_hits = 0
    n_jobs_run = 0
    total_steps = 0
    start = time.time()
    pair_outcomes: List[Dict[str, Any]] = []

    # Items in chunk are (pair, variant) jobs; group consecutively by pair
    for i, item in enumerate(chunk, 1):
        pair_key = (item["from_slug"], item["to_slug"])
        if stop_on_first_variant_hit and pair_key in pairs_done:
            continue

        suffix = item["variant_suffix"]
        logger.info(
            "[GPU %d] [%d/%d] %s -> %s [%s]",
            gpu_id, i, len(chunk), item["from_slug"], item["to_slug"], suffix,
        )
        hit, steps, info = _process_pair(
            item, config, run_dir, m_original,
            m_min=m_min, n_coarse_probes=n_coarse_probes,
            n_fine_steps=n_fine_steps, log_tolerance=log_tolerance,
            min_kl_drop=min_kl_drop, gpu_id=gpu_id, verbose=verbose,
        )
        n_jobs_run += 1
        total_steps += steps
        pair_outcomes.append({
            "from_slug": item["from_slug"],
            "to_slug": item["to_slug"],
            "variant": suffix,
            "hit": hit,
            "info": info,
        })
        if hit:
            n_hits += 1
            pairs_done.add(pair_key)
            logger.info("  HIT: %s", info)
        else:
            logger.info("  miss: %s", info)

    return {
        "gpu_id": gpu_id,
        "n_jobs": n_jobs_run,
        "n_hits": n_hits,
        "total_steps": total_steps,
        "elapsed_s": time.time() - start,
        "outcomes": pair_outcomes,
    }


def _build_pair_jobs(
    dataset: str, hard_fail_pairs: List[Tuple[str, str]],
    top_k_variants: int,
) -> Tuple[Path, Dict[str, Any], List[Dict[str, Any]]]:
    """For each hard-fail pair, build a list of (pair, variant) jobs ordered
    so that priority variants come first.
    """
    labeled_run, field_run = DATASET_RUNS[dataset]
    dataset_root = REPO_ROOT / "output" / dataset
    field_run_dir = dataset_root / "_swaps" / "runs" / field_run
    config_path = field_run_dir / "config_resolved.json"
    if not config_path.exists():
        raise FileNotFoundError(f"Missing config: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
    config["_swaps_dir"] = str(field_run_dir)

    jobs: List[Dict[str, Any]] = []
    for from_slug, to_slug in hard_fail_pairs:
        variants = _collect_pair_variants(field_run_dir, from_slug, to_slug)
        if not variants:
            continue
        # Skip pairs that already have a hit in any variant (defensive)
        if any(_has_hit(v["data"]) for v in variants):
            continue
        # Skip if any __m_tuned exists already
        src_dir = field_run_dir / "by_source" / from_slug
        if any(src_dir.glob(f"to_{to_slug}__*m_tuned*.json")):
            continue

        chosen = _select_variants_for_probe(variants, top_k_variants)
        for v in chosen:
            jobs.append({
                "from_slug": from_slug,
                "to_slug": to_slug,
                "variant_suffix": v["variant_suffix"],
                "result_file": v["result_file"],
                "data": v["data"],
            })

    return field_run_dir, config, jobs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", required=True, choices=sorted(DATASET_RUNS))
    parser.add_argument(
        "--hard-fail-json", default="/tmp/hard_fail_pairs.json",
        help="Path to hard-fail pair list (per-dataset)",
    )
    parser.add_argument("--top-k-variants", type=int, default=2,
                        help="Beyond priority variants, also probe top-K by vsmax")
    parser.add_argument("--gpu-ids", nargs="*", type=int, default=[0])
    parser.add_argument("--m-min", type=float, default=0.5)
    parser.add_argument("--n-coarse-probes", type=int, default=6)
    parser.add_argument("--n-fine-steps", type=int, default=4)
    parser.add_argument("--log-tolerance", type=float, default=0.1)
    parser.add_argument("--min-kl-drop", type=float, default=1.0)
    parser.add_argument("--limit", type=int, default=None,
                        help="Limit number of pairs (for testing)")
    parser.add_argument("--no-stop-on-first-variant-hit", action="store_true",
                        help="Probe ALL chosen variants per pair (default: stop after first hit)")
    parser.add_argument("--summary-out", default=None,
                        help="Write a JSON summary of outcomes here")
    parser.add_argument("-v", "--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    hard_fail_data = json.loads(Path(args.hard_fail_json).read_text())
    raw_pairs = hard_fail_data.get(args.dataset, [])
    pairs: List[Tuple[str, str]] = [tuple(p) for p in raw_pairs]
    if args.limit is not None:
        pairs = pairs[: args.limit]

    print(f"[recover_hard_fails] dataset={args.dataset} hard_fail_pairs={len(pairs)}")
    field_run_dir, config, jobs = _build_pair_jobs(
        args.dataset, pairs, args.top_k_variants,
    )
    print(f"[recover_hard_fails] eligible (pair, variant) jobs={len(jobs)}")
    if not jobs:
        print("Nothing to do.")
        return

    m_original = config.get("ct_steering", {}).get("M_amplify", 20.0)
    print(f"[recover_hard_fails] m_original={m_original} m_min={args.m_min}")

    gpu_ids = args.gpu_ids
    n_gpus = len(gpu_ids)
    stop_on_first = not args.no_stop_on_first_variant_hit

    # Distribute jobs round-robin by *pair* so all variants of a pair stay together
    pair_groups: Dict[Tuple[str, str], List[Dict[str, Any]]] = {}
    for j in jobs:
        pair_groups.setdefault((j["from_slug"], j["to_slug"]), []).append(j)
    pair_keys = list(pair_groups)
    chunks: List[List[Dict[str, Any]]] = [[] for _ in range(n_gpus)]
    for i, pk in enumerate(pair_keys):
        chunks[i % n_gpus].extend(pair_groups[pk])

    print(f"[recover_hard_fails] dispatching {len(pair_keys)} pairs across {n_gpus} GPUs")
    t0 = time.time()
    results: List[Dict[str, Any]] = []
    if n_gpus == 1:
        results.append(_run_gpu_chunk(
            gpu_ids[0], chunks[0], config, field_run_dir, m_original,
            m_min=args.m_min, n_coarse_probes=args.n_coarse_probes,
            n_fine_steps=args.n_fine_steps, log_tolerance=args.log_tolerance,
            min_kl_drop=args.min_kl_drop, verbose=args.verbose,
            stop_on_first_variant_hit=stop_on_first,
        ))
    else:
        with ThreadPoolExecutor(max_workers=n_gpus) as ex:
            futs = {}
            for gid, chunk in zip(gpu_ids, chunks):
                if not chunk:
                    continue
                fut = ex.submit(
                    _run_gpu_chunk, gid, chunk, config, field_run_dir, m_original,
                    args.m_min, args.n_coarse_probes, args.n_fine_steps,
                    args.log_tolerance, args.min_kl_drop, args.verbose,
                    stop_on_first,
                )
                futs[fut] = gid
            for fut in as_completed(futs):
                try:
                    results.append(fut.result())
                except Exception as exc:
                    print(f"  GPU {futs[fut]} FAILED: {exc}")

    elapsed = time.time() - t0

    # Aggregate
    total_jobs = sum(r["n_jobs"] for r in results)
    total_hits = sum(r["n_hits"] for r in results)
    all_outcomes: List[Dict[str, Any]] = []
    pairs_with_hit: set = set()
    for r in results:
        all_outcomes.extend(r["outcomes"])
        for o in r["outcomes"]:
            if o["hit"]:
                pairs_with_hit.add((o["from_slug"], o["to_slug"]))

    print()
    print("=" * 60)
    print(f"Total jobs run:        {total_jobs}")
    print(f"Total hits:            {total_hits}")
    print(f"Unique pairs with hit: {len(pairs_with_hit)} / {len(pair_keys)}  "
          f"({100*len(pairs_with_hit)/max(1,len(pair_keys)):.1f}%)")
    print(f"Wall time:             {elapsed:.1f}s")
    print("=" * 60)

    if args.summary_out:
        Path(args.summary_out).write_text(json.dumps({
            "dataset": args.dataset,
            "n_pairs_attempted": len(pair_keys),
            "n_jobs_run": total_jobs,
            "n_jobs_hit": total_hits,
            "n_pairs_recovered": len(pairs_with_hit),
            "pairs_recovered": sorted(list(pairs_with_hit)),
            "elapsed_s": elapsed,
            "outcomes": all_outcomes,
        }, indent=2))
        print(f"Wrote summary to {args.summary_out}")


if __name__ == "__main__":
    main()
