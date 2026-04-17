"""
Run scalable cross-prompt robustness analysis across all domains.

Computes pairwise feature overlap for all entity pairs in each domain,
then produces aggregate statistics, cross-domain comparisons, and
correlations with swap performance.

Usage::

    python scripts/experiments/run_scalable_cross_prompt.py

Outputs go to output/research/cross_prompt_scalable/.
"""

from __future__ import annotations

import csv
import json
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.experiments.cross_prompt_robustness_scalable import (
    CrossPromptComparator,
    PairResult,
)

OUTPUT_DIR = Path(__file__).resolve().parents[2] / "output" / "research" / "cross_prompt_scalable"

DATASETS = [
    "usa_states_batch",
    "book_characters_authors_batch",
    "products_founders_batch",
    "paintings_painters_batch",
    "sounds_colors_batch",
]

DOMAIN_LABELS = {
    "usa_states_batch": "USA",
    "book_characters_authors_batch": "Books",
    "products_founders_batch": "Products",
    "paintings_painters_batch": "Paintings",
    "sounds_colors_batch": "Sounds",
}


def _bootstrap_ci(values: List[float], n_boot: int = 5000,
                   ci: float = 0.95, seed: int = 42) -> Tuple[float, float, float]:
    """Return (mean, ci_low, ci_high) via bootstrap."""
    rng = np.random.RandomState(seed)
    arr = np.array(values)
    means = np.array([
        np.mean(rng.choice(arr, size=len(arr), replace=True))
        for _ in range(n_boot)
    ])
    alpha = (1 - ci) / 2
    return float(np.mean(arr)), float(np.percentile(means, alpha * 100)), float(np.percentile(means, (1 - alpha) * 100))


def _cohens_d(a: List[float], b: List[float]) -> float:
    """Cohen's d effect size."""
    na, nb = np.array(a), np.array(b)
    if len(na) < 2 or len(nb) < 2:
        return 0.0
    pooled_std = np.sqrt(
        ((len(na) - 1) * np.var(na, ddof=1) + (len(nb) - 1) * np.var(nb, ddof=1))
        / (len(na) + len(nb) - 2)
    )
    if pooled_std < 1e-12:
        return 0.0
    return float((np.mean(na) - np.mean(nb)) / pooled_std)


def _permutation_test(observed: float, pool_size: int,
                      sample_size_a: int, sample_size_b: int,
                      n_features_list: List[int],
                      n_perm: int = 1000, seed: int = 42) -> float:
    """Test if observed Jaccard overlap is above chance.

    Simulates random feature selection from a pool and computes
    expected Jaccard under independence.
    """
    rng = np.random.RandomState(seed)
    count_ge = 0
    for _ in range(n_perm):
        sa = rng.randint(0, pool_size, size=sample_size_a)
        sb = rng.randint(0, pool_size, size=sample_size_b)
        intersection = len(set(sa) & set(sb))
        union = len(set(sa) | set(sb))
        j = intersection / union if union > 0 else 0.0
        if j >= observed:
            count_ge += 1
    return count_ge / n_perm


def run_all_pairs(comp: CrossPromptComparator) -> Dict[str, List[PairResult]]:
    """Run pairwise comparison for all domains."""
    all_results: Dict[str, List[PairResult]] = {}
    for ds in DATASETS:
        t0 = time.time()
        results = comp.compare_all(ds, progress=True)
        elapsed = time.time() - t0
        all_results[ds] = results
        print(f"  [{DOMAIN_LABELS[ds]}] {len(results)} pairs in {elapsed:.1f}s")
    return all_results


def compute_domain_aggregates(all_results: Dict[str, List[PairResult]]) -> Dict[str, Dict[str, Any]]:
    """Compute per-domain aggregate statistics with bootstrap CIs."""
    aggregates: Dict[str, Dict[str, Any]] = {}
    for ds, results in all_results.items():
        if not results:
            continue
        label = DOMAIN_LABELS[ds]
        n = len(results)

        jaccards = [r.jaccard_overlap for r in results]
        dir_a = [r.directional_overlap_a for r in results]
        stabilities = [r.activation_stability for r in results]
        peak_tok = [r.peak_token_agreement for r in results]
        peak_type = [r.peak_type_agreement for r in results]
        same_sn = [r.same_supernode_rate for r in results]
        regrouped = [r.entity_regrouped_rate for r in results]
        inconsistent = [r.inconsistent_rate for r in results]
        inf_jaccards = [r.influence_weighted_jaccard for r in results]

        early = [r.bucket_overlap.get("early", 0) for r in results]
        mid = [r.bucket_overlap.get("mid", 0) for r in results]
        late = [r.bucket_overlap.get("late", 0) for r in results]

        def stats(vals: List[float], name: str) -> Dict[str, Any]:
            mean, ci_lo, ci_hi = _bootstrap_ci(vals)
            return {
                "mean": mean,
                "median": float(np.median(vals)),
                "std": float(np.std(vals)),
                "ci_95_lo": ci_lo,
                "ci_95_hi": ci_hi,
                "min": float(np.min(vals)),
                "max": float(np.max(vals)),
            }

        agg = {
            "domain": label,
            "dataset": ds,
            "n_pairs": n,
            "n_entities": len(set(r.slug_a for r in results) | set(r.slug_b for r in results)),
            "jaccard": stats(jaccards, "jaccard"),
            "directional_overlap": stats(dir_a, "directional_a"),
            "activation_stability": stats(stabilities, "stability"),
            "peak_token_agreement": stats(peak_tok, "peak_token"),
            "peak_type_agreement": stats(peak_type, "peak_type"),
            "same_supernode_rate": stats(same_sn, "same_sn"),
            "entity_regrouped_rate": stats(regrouped, "regrouped"),
            "inconsistent_rate": stats(inconsistent, "inconsistent"),
            "influence_weighted_jaccard": stats(inf_jaccards, "inf_jaccard"),
            "overlap_early": stats(early, "early"),
            "overlap_mid": stats(mid, "mid"),
            "overlap_late": stats(late, "late"),
        }
        aggregates[ds] = agg
    return aggregates


def compute_per_layer_curves(all_results: Dict[str, List[PairResult]]) -> Dict[str, Dict[int, Dict[str, float]]]:
    """Compute mean overlap per individual layer, per domain."""
    curves: Dict[str, Dict[int, Dict[str, float]]] = {}
    for ds, results in all_results.items():
        if not results:
            continue
        layer_vals: Dict[int, List[float]] = defaultdict(list)
        for r in results:
            for layer, val in r.per_layer_overlap.items():
                layer_vals[layer].append(val)
        layer_stats: Dict[int, Dict[str, float]] = {}
        for layer in sorted(layer_vals.keys()):
            vals = layer_vals[layer]
            layer_stats[layer] = {
                "mean": float(np.mean(vals)),
                "std": float(np.std(vals)),
                "n_pairs": len(vals),
            }
        curves[ds] = layer_stats
    return curves


def compute_permutation_baselines(all_results: Dict[str, List[PairResult]]) -> Dict[str, Dict[str, float]]:
    """Test if observed overlap is above chance via permutation.

    Uses a conservative pool size estimate: total unique features seen
    across all entities in the domain.
    """
    baselines: Dict[str, Dict[str, float]] = {}
    for ds, results in all_results.items():
        if not results:
            continue
        all_features: set = set()
        feature_counts: List[int] = []
        entities_seen: set = set()
        for r in results:
            if r.slug_a not in entities_seen:
                entities_seen.add(r.slug_a)
                feature_counts.append(r.n_features_a)
            if r.slug_b not in entities_seen:
                entities_seen.add(r.slug_b)
                feature_counts.append(r.n_features_b)

        mean_jaccard = float(np.mean([r.jaccard_overlap for r in results]))
        mean_n_a = int(np.mean([r.n_features_a for r in results]))
        mean_n_b = int(np.mean([r.n_features_b for r in results]))

        pool_sizes = [1000, 5000, 10000, 50000]
        pvals = {}
        for pool in pool_sizes:
            p = _permutation_test(
                mean_jaccard, pool, mean_n_a, mean_n_b,
                feature_counts, n_perm=2000,
            )
            pvals[f"pool_{pool}"] = p

        baselines[ds] = {
            "mean_jaccard": mean_jaccard,
            "mean_n_features": float(np.mean(feature_counts)),
            **pvals,
        }
    return baselines


def correlate_with_swaps(
    all_results: Dict[str, List[PairResult]],
) -> Dict[str, Dict[str, Any]]:
    """Correlate pairwise overlap with swap performance metrics."""
    try:
        from scripts.utils.swap_query import SwapQuery
    except ImportError:
        print("  WARNING: SwapQuery not available, skipping swap correlation")
        return {}

    q = SwapQuery()
    correlations: Dict[str, Dict[str, Any]] = {}

    run_map = {
        "usa_states_batch": "fullscale_usa_labeled",
        "book_characters_authors_batch": "fullscale_books_labeled",
        "products_founders_batch": "fullscale_products_labeled",
        "paintings_painters_batch": "fullscale_paintings_labeled",
        "sounds_colors_batch": "fullscale_sounds_labeled",
    }

    for ds, results in all_results.items():
        run_id = run_map.get(ds)
        if not run_id:
            continue
        available_runs = q.list_runs(ds)
        if run_id not in available_runs:
            print(f"  WARNING: run {run_id} not found in {ds}, skipping correlation")
            continue

        print(f"  [{DOMAIN_LABELS[ds]}] Loading swap data for correlation...")
        swaps = q.search(
            dataset=ds, run=run_id, variant="",
            top_n=999999, sort_by="vs_max", skip_identity=True,
        )
        swap_by_pair: Dict[Tuple[str, str], Any] = {}
        for s in swaps:
            key = (s.from_slug, s.to_slug)
            swap_by_pair[key] = s

        jaccards = []
        vs_maxes = []
        gap_closures = []
        hits = []

        for r in results:
            for slug_from, slug_to in [(r.slug_a, r.slug_b), (r.slug_b, r.slug_a)]:
                key = (slug_from.lower().replace(" ", "_"),
                       slug_to.lower().replace(" ", "_"))
                sw = swap_by_pair.get(key)
                if sw and sw.vs_max is not None:
                    jaccards.append(r.jaccard_overlap)
                    vs_maxes.append(sw.vs_max)
                    gap_closures.append(sw.gap_closure if sw.gap_closure is not None else 0.0)
                    hits.append(1.0 if sw.steered_has_to_answer else 0.0)

        if len(jaccards) < 10:
            print(f"  [{DOMAIN_LABELS[ds]}] Only {len(jaccards)} matched pairs, skipping")
            continue

        j_arr = np.array(jaccards)
        vs_arr = np.array(vs_maxes)
        gc_arr = np.array(gap_closures)
        h_arr = np.array(hits)

        r_vs = float(np.corrcoef(j_arr, vs_arr)[0, 1]) if np.std(vs_arr) > 0 else 0.0
        r_gc = float(np.corrcoef(j_arr, gc_arr)[0, 1]) if np.std(gc_arr) > 0 else 0.0
        r_hit = float(np.corrcoef(j_arr, h_arr)[0, 1]) if np.std(h_arr) > 0 else 0.0

        correlations[ds] = {
            "n_matched_pairs": len(jaccards),
            "r_jaccard_vs_max": r_vs,
            "r_jaccard_gap_closure": r_gc,
            "r_jaccard_hit": r_hit,
            "mean_vs_max": float(np.mean(vs_arr)),
            "mean_gap_closure": float(np.mean(gc_arr)),
            "hit_rate": float(np.mean(h_arr)),
        }
        print(f"  [{DOMAIN_LABELS[ds]}] N={len(jaccards)}, "
              f"r(jaccard,vsMax)={r_vs:.3f}, r(jaccard,gc)={r_gc:.3f}")

    return correlations


def write_summary_csv(aggregates: Dict[str, Dict[str, Any]], path: Path) -> None:
    """Write a cross-domain summary CSV."""
    path.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "domain", "n_pairs", "n_entities",
        "jaccard_mean", "jaccard_ci95",
        "directional_mean", "directional_ci95",
        "stability_mean", "stability_ci95",
        "peak_token_mean", "peak_type_mean",
        "same_sn_mean", "regrouped_mean", "inconsistent_mean",
        "overlap_early_mean", "overlap_mid_mean", "overlap_late_mean",
        "inf_jaccard_mean",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields)
        writer.writeheader()
        for ds in DATASETS:
            agg = aggregates.get(ds)
            if not agg:
                continue
            writer.writerow({
                "domain": agg["domain"],
                "n_pairs": agg["n_pairs"],
                "n_entities": agg["n_entities"],
                "jaccard_mean": f"{agg['jaccard']['mean']:.4f}",
                "jaccard_ci95": f"[{agg['jaccard']['ci_95_lo']:.4f}, {agg['jaccard']['ci_95_hi']:.4f}]",
                "directional_mean": f"{agg['directional_overlap']['mean']:.4f}",
                "directional_ci95": f"[{agg['directional_overlap']['ci_95_lo']:.4f}, {agg['directional_overlap']['ci_95_hi']:.4f}]",
                "stability_mean": f"{agg['activation_stability']['mean']:.4f}",
                "stability_ci95": f"[{agg['activation_stability']['ci_95_lo']:.4f}, {agg['activation_stability']['ci_95_hi']:.4f}]",
                "peak_token_mean": f"{agg['peak_token_agreement']['mean']:.4f}",
                "peak_type_mean": f"{agg['peak_type_agreement']['mean']:.4f}",
                "same_sn_mean": f"{agg['same_supernode_rate']['mean']:.4f}",
                "regrouped_mean": f"{agg['entity_regrouped_rate']['mean']:.4f}",
                "inconsistent_mean": f"{agg['inconsistent_rate']['mean']:.4f}",
                "overlap_early_mean": f"{agg['overlap_early']['mean']:.4f}",
                "overlap_mid_mean": f"{agg['overlap_mid']['mean']:.4f}",
                "overlap_late_mean": f"{agg['overlap_late']['mean']:.4f}",
                "inf_jaccard_mean": f"{agg['influence_weighted_jaccard']['mean']:.4f}",
            })


def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    comp = CrossPromptComparator()
    t_start = time.time()

    # Phase 1: Run all pairs
    print("=" * 70)
    print("PHASE 1: Pairwise Comparison Across All Domains")
    print("=" * 70)
    all_results = run_all_pairs(comp)

    total_pairs = sum(len(r) for r in all_results.values())
    print(f"\nTotal pairs computed: {total_pairs}")

    # Save per-pair CSVs
    for ds, results in all_results.items():
        label = DOMAIN_LABELS[ds]
        csv_path = OUTPUT_DIR / f"pairs_{label.lower()}.csv"
        comp.save_results(results, csv_path)
        print(f"  Saved: {csv_path}")

    # Phase 2: Aggregate statistics
    print("\n" + "=" * 70)
    print("PHASE 2: Aggregate Statistics with Bootstrap CIs")
    print("=" * 70)
    aggregates = compute_domain_aggregates(all_results)
    write_summary_csv(aggregates, OUTPUT_DIR / "cross_domain_summary.csv")
    with open(OUTPUT_DIR / "aggregates.json", "w", encoding="utf-8") as f:
        json.dump(aggregates, f, indent=2)
    print(f"  Saved: {OUTPUT_DIR / 'aggregates.json'}")

    for ds in DATASETS:
        agg = aggregates.get(ds)
        if not agg:
            continue
        j = agg["jaccard"]
        s = agg["activation_stability"]
        print(f"\n  {agg['domain']:>10s}: N={agg['n_pairs']:>5d} pairs, "
              f"Jaccard={j['mean']:.3f} [{j['ci_95_lo']:.3f},{j['ci_95_hi']:.3f}], "
              f"Stability={s['mean']:.3f} [{s['ci_95_lo']:.3f},{s['ci_95_hi']:.3f}]")

    # Phase 3: Per-layer curves
    print("\n" + "=" * 70)
    print("PHASE 3: Per-Layer Overlap Curves")
    print("=" * 70)
    curves = compute_per_layer_curves(all_results)
    with open(OUTPUT_DIR / "per_layer_curves.json", "w", encoding="utf-8") as f:
        json.dump(curves, f, indent=2, default=str)
    print(f"  Saved: {OUTPUT_DIR / 'per_layer_curves.json'}")

    for ds in DATASETS:
        if ds not in curves:
            continue
        label = DOMAIN_LABELS[ds]
        layers = curves[ds]
        early_layers = [v["mean"] for k, v in layers.items() if int(k) <= 5]
        late_layers = [v["mean"] for k, v in layers.items() if int(k) >= 15]
        early_mean = np.mean(early_layers) if early_layers else 0
        late_mean = np.mean(late_layers) if late_layers else 0
        print(f"  {label:>10s}: Early(0-5)={early_mean:.3f}, Late(15+)={late_mean:.3f}, "
              f"ratio={early_mean/late_mean:.2f}x" if late_mean > 0 else
              f"  {label:>10s}: Early(0-5)={early_mean:.3f}, Late(15+)={late_mean:.3f}")

    # Phase 4: Permutation test
    print("\n" + "=" * 70)
    print("PHASE 4: Permutation Test (Chance Baseline)")
    print("=" * 70)
    baselines = compute_permutation_baselines(all_results)
    with open(OUTPUT_DIR / "permutation_baselines.json", "w", encoding="utf-8") as f:
        json.dump(baselines, f, indent=2)
    print(f"  Saved: {OUTPUT_DIR / 'permutation_baselines.json'}")

    for ds, bl in baselines.items():
        label = DOMAIN_LABELS[ds]
        print(f"  {label:>10s}: mean_jaccard={bl['mean_jaccard']:.3f}, "
              f"p(pool=1k)={bl['pool_1000']:.3f}, "
              f"p(pool=5k)={bl['pool_5000']:.3f}, "
              f"p(pool=10k)={bl['pool_10000']:.3f}")

    # Phase 5: Swap correlation
    print("\n" + "=" * 70)
    print("PHASE 5: Correlation with Swap Performance")
    print("=" * 70)
    correlations = correlate_with_swaps(all_results)
    if correlations:
        with open(OUTPUT_DIR / "swap_correlations.json", "w", encoding="utf-8") as f:
            json.dump(correlations, f, indent=2)
        print(f"  Saved: {OUTPUT_DIR / 'swap_correlations.json'}")

    elapsed = time.time() - t_start
    print(f"\n{'=' * 70}")
    print(f"COMPLETE: {total_pairs} pairs in {elapsed:.1f}s")
    print(f"Results in: {OUTPUT_DIR}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
