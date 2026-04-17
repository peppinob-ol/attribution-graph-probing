#!/usr/bin/env python3
"""
Systematic M-search configuration testing across all datasets.

Tests different m_min, n_coarse_probes, and m_search strategies
on selected representative pairs from each dataset.

Results are collected into a consolidated JSON report.
"""
from __future__ import annotations

import json
import logging
import sys
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

SCRIPT_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = SCRIPT_DIR.parent.parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from pipeline.swap_loader import SwapPair
from pipeline.swap_evaluator import evaluate_swap
from pipeline.m_search import (
    search_optimal_m, build_steer_fn, _patch_features_m,
    coarse_probe, fine_search_at_kl_transition, _geomspace,
)
from run_batch_swaps import _run_local_ct_steering

logger = logging.getLogger(__name__)

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_ROOT = REPO_ROOT / "output"


@dataclass
class TestConfig:
    name: str
    m_min: float = 0.1
    m_max_mult: float = 1.0  # multiplier on original M (1.0 = use original)
    n_coarse_probes: int = 6
    n_fine_steps: int = 6
    log_tolerance: float = 0.1
    min_kl_drop: float = 1.0


@dataclass
class TestResult:
    dataset: str
    run: str
    from_slug: str
    to_slug: str
    config_name: str
    hit: bool
    winning_m: Optional[float] = None
    phase: Optional[int] = None
    total_steps: int = 0
    kl_profile: List[Dict[str, Any]] = field(default_factory=list)
    phase2_steps: List[Dict[str, Any]] = field(default_factory=list)
    kl_transition: Optional[Dict[str, Any]] = None
    elapsed_s: float = 0.0
    error: Optional[str] = None


CONFIGS = [
    TestConfig("standard", m_min=0.1, n_coarse_probes=6, n_fine_steps=6),
    TestConfig("wide_range", m_min=0.01, n_coarse_probes=8, n_fine_steps=6),
    TestConfig("dense_coarse", m_min=0.1, n_coarse_probes=10, n_fine_steps=4),
    TestConfig("narrow_m5", m_min=0.5, m_max_mult=0.5, n_coarse_probes=6, n_fine_steps=6),
    TestConfig("tight_fine", m_min=0.1, n_coarse_probes=6, n_fine_steps=8,
               log_tolerance=0.05, min_kl_drop=0.5),
    TestConfig("ultrawide", m_min=0.01, m_max_mult=2.0, n_coarse_probes=8, n_fine_steps=6),
]

TEST_PAIRS = {
    "usa_states_batch": {
        "run": "fullscale_usa_labeled",
        "pairs": [
            ("south_carolina_charleston", "oregon_portland"),
            ("north_carolina_charlotte", "oregon_portland"),
            ("virginia_virginia_beach", "north_dakota_fargo"),
            ("kansas_wichita", "oklahoma_tulsa"),
            ("maryland_baltimore", "north_dakota_fargo"),
            ("idaho_idaho_falls", "arkansas_fayetteville"),
        ],
    },
    "products_founders_batch": {
        "run": "fullscale_products_labeled",
        "pairs": [
            ("windows", "facebook"),
            ("dell_xps", "facebook"),
            ("nike_shoes", "facebook"),
            ("dyson", "facebook"),
            ("oculus", "ford_cars"),
        ],
    },
    "paintings_painters_batch": {
        "run": "fullscale_paintings_labeled",
        "pairs": [
            ("starry_night", "the_scream"),
            ("persistence_of_memory", "blue_boy"),
            ("girl_pearl_earring", "the_scream"),
            ("blue_boy", "persistence_of_memory"),
            ("nighthawks", "the_scream"),
        ],
    },
    "sounds_colors_batch": {
        "run": "fullscale_sounds_labeled",
        "pairs": [
            ("whinny", "hiss"),
            ("bark", "hiss"),
            ("meow", "hiss"),
            ("meow", "whinny"),
            ("buzz", "hiss"),
        ],
    },
    "book_characters_authors_batch": {
        "run": "fullscale_books_labeled",
        "pairs": [
            ("frodo_baggins", "jay_gatsby"),
            ("katniss_everdeen", "jay_gatsby"),
            ("katniss_everdeen", "edmond_dantes"),
            ("elizabeth_bennet", "raskolnikov"),
            ("gregor_samsa", "dracula"),
        ],
    },
}


def _load_pair_data(
    dataset: str, run: str, from_slug: str, to_slug: str
) -> Optional[Tuple[Dict, List[Dict], str, SwapPair]]:
    """Load baseline result, features, prompt, and SwapPair for a test pair."""
    run_dir = OUTPUT_ROOT / dataset / "_swaps" / "runs" / run
    by_source = run_dir / "by_source" / from_slug
    result_file = by_source / f"to_{to_slug}.json"

    if not result_file.exists():
        return None

    data = json.loads(result_file.read_text())

    work_dir = run_dir / "work" / f"{from_slug}__to__{to_slug}"
    features_file = work_dir / "features.json"
    if not features_file.exists():
        return None

    features = json.loads(features_file.read_text())
    prompt = data.get("source", {}).get("prompt", "")
    if not prompt:
        return None

    pair = SwapPair(
        from_slug=from_slug,
        to_slug=to_slug,
        from_entity=data.get("source", {}),
        to_entity=data.get("target", {}),
    )
    return data, features, prompt, pair


def run_single_test(
    dataset: str, run: str, from_slug: str, to_slug: str,
    cfg: TestConfig, gpu_id: int, verbose: bool = False,
) -> TestResult:
    """Run a single m_search test with given config on a single pair."""
    start = time.time()

    loaded = _load_pair_data(dataset, run, from_slug, to_slug)
    if loaded is None:
        return TestResult(
            dataset=dataset, run=run, from_slug=from_slug, to_slug=to_slug,
            config_name=cfg.name, hit=False, error="missing data/features",
        )

    data, features, prompt, pair = loaded

    run_dir = OUTPUT_ROOT / dataset / "_swaps" / "runs" / run
    config_path = run_dir / "config_resolved.json"
    config = json.loads(config_path.read_text())
    config["_swaps_dir"] = str(run_dir)

    m_original = config.get("ct_steering", {}).get("M_amplify", 20.0)
    m_max = m_original * cfg.m_max_mult
    if m_max != m_original:
        config.setdefault("ct_steering", {})["M_amplify"] = m_max

    work_dir = run_dir / "work" / f"{from_slug}__to__{to_slug}"

    def _factory():
        return build_steer_fn(
            features=features, prompt=prompt, pair=pair, config=config,
            work_dir=work_dir, evaluate_swap_fn=evaluate_swap,
            run_steering_fn=_run_local_ct_steering,
            gpu_id=gpu_id, verbose=verbose,
        )

    tuned = search_optimal_m(
        _factory, data, m_max,
        m_min=cfg.m_min,
        n_coarse_probes=cfg.n_coarse_probes,
        n_fine_steps=cfg.n_fine_steps,
        log_tolerance=cfg.log_tolerance,
        min_kl_drop=cfg.min_kl_drop,
    )

    elapsed = time.time() - start

    if tuned is not None:
        m_info = tuned.get("m_search", {})
        return TestResult(
            dataset=dataset, run=run, from_slug=from_slug, to_slug=to_slug,
            config_name=cfg.name, hit=True,
            winning_m=m_info.get("m_tuned"),
            phase=m_info.get("phase"),
            total_steps=m_info.get("total_steps", 0),
            kl_profile=m_info.get("phase1_probes", []),
            phase2_steps=m_info.get("phase2_steps", []),
            kl_transition=m_info.get("kl_transition"),
            elapsed_s=round(elapsed, 1),
        )

    return TestResult(
        dataset=dataset, run=run, from_slug=from_slug, to_slug=to_slug,
        config_name=cfg.name, hit=False,
        total_steps=cfg.n_coarse_probes + cfg.n_fine_steps,
        elapsed_s=round(elapsed, 1),
    )


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Systematic M-search config testing")
    parser.add_argument("--gpu-id", type=int, default=1)
    parser.add_argument("--datasets", nargs="*", default=None,
                        help="Limit to specific datasets")
    parser.add_argument("--configs", nargs="*", default=None,
                        help="Limit to specific config names")
    parser.add_argument("--pairs-per-dataset", type=int, default=None,
                        help="Limit pairs per dataset")
    parser.add_argument("-v", "--verbose", action="store_true")
    parser.add_argument("--output", type=str,
                        default=str(REPO_ROOT / "output" / "research" / "m_search_test_results.json"))
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(message)s",
    )

    configs_to_test = CONFIGS
    if args.configs:
        configs_to_test = [c for c in CONFIGS if c.name in args.configs]

    datasets_to_test = TEST_PAIRS
    if args.datasets:
        datasets_to_test = {k: v for k, v in TEST_PAIRS.items() if k in args.datasets}

    total_tests = sum(
        min(len(v["pairs"]), args.pairs_per_dataset or 999) * len(configs_to_test)
        for v in datasets_to_test.values()
    )

    print(f"M-Search Configuration Testing")
    print(f"GPU: {args.gpu_id}")
    print(f"Datasets: {list(datasets_to_test.keys())}")
    print(f"Configs: {[c.name for c in configs_to_test]}")
    print(f"Total test runs: {total_tests}")
    print()

    results: List[TestResult] = []
    test_num = 0
    global_start = time.time()

    for ds, ds_info in datasets_to_test.items():
        run = ds_info["run"]
        pairs = ds_info["pairs"]
        if args.pairs_per_dataset:
            pairs = pairs[:args.pairs_per_dataset]

        print(f"=== {ds} ({run}) ===")

        for from_slug, to_slug in pairs:
            for cfg in configs_to_test:
                test_num += 1
                pair_label = f"{from_slug}->{to_slug}"
                print(f"  [{test_num}/{total_tests}] {pair_label} [{cfg.name}] ... ",
                      end="", flush=True)

                result = run_single_test(
                    ds, run, from_slug, to_slug, cfg,
                    gpu_id=args.gpu_id, verbose=args.verbose,
                )
                results.append(result)

                if result.error:
                    print(f"ERROR: {result.error}")
                elif result.hit:
                    print(f"HIT M={result.winning_m:.4f} "
                          f"(phase {result.phase}, {result.total_steps} steps, "
                          f"{result.elapsed_s:.0f}s)")
                else:
                    print(f"miss ({result.total_steps} steps, {result.elapsed_s:.0f}s)")

            # Clean up _m_search temp files between pairs
            work_dir = (OUTPUT_ROOT / ds / "_swaps" / "runs" / run / "work"
                        / f"{from_slug}__to__{to_slug}" / "_m_search")
            if work_dir.exists():
                import shutil
                shutil.rmtree(work_dir)
        print()

    elapsed = time.time() - global_start

    print(f"\n{'='*60}")
    print(f"RESULTS SUMMARY")
    print(f"{'='*60}")

    hits = [r for r in results if r.hit]
    misses = [r for r in results if not r.hit and not r.error]
    errors = [r for r in results if r.error]
    print(f"Total: {len(results)}, Hits: {len(hits)}, Misses: {len(misses)}, Errors: {len(errors)}")
    print(f"Time: {elapsed:.0f}s")

    print(f"\nBy config:")
    for cfg in configs_to_test:
        cfg_results = [r for r in results if r.config_name == cfg.name]
        cfg_hits = [r for r in cfg_results if r.hit]
        cfg_valid = [r for r in cfg_results if not r.error]
        if cfg_valid:
            pct = 100 * len(cfg_hits) / len(cfg_valid)
            avg_steps = sum(r.total_steps for r in cfg_valid) / len(cfg_valid)
            winning_ms = [r.winning_m for r in cfg_hits if r.winning_m]
            m_range = (f", M=[{min(winning_ms):.3f},{max(winning_ms):.3f}]"
                       if winning_ms else "")
            print(f"  {cfg.name}: {len(cfg_hits)}/{len(cfg_valid)} "
                  f"({pct:.0f}%), avg_steps={avg_steps:.1f}{m_range}")

    print(f"\nBy dataset:")
    for ds in datasets_to_test:
        ds_results = [r for r in results if r.dataset == ds]
        ds_hits = [r for r in ds_results if r.hit]
        ds_valid = [r for r in ds_results if not r.error]
        if ds_valid:
            pct = 100 * len(ds_hits) / len(ds_valid)
            print(f"  {ds}: {len(ds_hits)}/{len(ds_valid)} ({pct:.0f}%)")
            for cfg in configs_to_test:
                cfg_hits = [r for r in ds_results
                            if r.config_name == cfg.name and r.hit]
                cfg_valid = [r for r in ds_results
                             if r.config_name == cfg.name and not r.error]
                if cfg_valid:
                    cp = 100 * len(cfg_hits) / len(cfg_valid)
                    print(f"    {cfg.name}: {len(cfg_hits)}/{len(cfg_valid)} ({cp:.0f}%)")

    print(f"\nHit details:")
    for r in hits:
        print(f"  {r.dataset}: {r.from_slug}->{r.to_slug} [{r.config_name}] "
              f"M={r.winning_m:.4f} phase={r.phase} steps={r.total_steps}")

    report = {
        "test_configs": {c.name: asdict(c) for c in configs_to_test},
        "results": [asdict(r) for r in results],
        "summary": {
            "total": len(results),
            "hits": len(hits),
            "misses": len(misses),
            "errors": len(errors),
            "elapsed_s": round(elapsed, 1),
        },
    }
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"\nFull report saved to {args.output}")


if __name__ == "__main__":
    main()
