"""
Analyze contrast-group trial results.

Reads per-swap JSON files produced by runs using the trial_contrast_* configs
and compares the diagnostic value of different specificity metrics:

  - target - source  (existing core metric)
  - target - mean(other dataset answers)
  - target - max(other dataset answers)
  - target - top-k mean(other dataset answers)

Prints a comparative table and writes a JSON summary for follow-up.

Usage:
    python scripts/experiments/batch/analyze_contrast_trial.py \\
        --swaps-dir output/usa_states_batch/_swaps/runs/<run_id>

    python scripts/experiments/batch/analyze_contrast_trial.py \\
        --swaps-dir output/paintings_painters_batch/_swaps/runs/<run_id>
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_trial_results(swaps_dir: Path) -> List[Dict[str, Any]]:
    if (swaps_dir / "by_source").exists():
        by_source = swaps_dir / "by_source"
    elif swaps_dir.name == "by_source":
        by_source = swaps_dir
    else:
        raise FileNotFoundError(f"by_source not found in {swaps_dir}")

    results = []
    for src in sorted(by_source.iterdir()):
        if not src.is_dir():
            continue
        for f in sorted(src.glob("to_*.json")):
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                data["_file"] = str(f)
                results.append(data)
            except (json.JSONDecodeError, IOError) as e:
                print(f"  Warning: {f}: {e}")
    return results


def extract_contrast_metrics(result: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    ev = result.get("evaluation", {})
    traj = ev.get("logit_trajectory")
    if not traj:
        return None

    summary = traj.get("summary", {})
    gap_traj = summary.get("gap_trajectory", [])
    cg = traj.get("contrast_groups", {}).get("same_dataset")

    swap_id = result.get("swap_id", "?")
    from_slug = result.get("source", {}).get("slug", "?")
    to_slug = result.get("target", {}).get("slug", "?")

    tier = ev.get("tier")
    exact_match = ev.get("exact_match", {}).get("steered_has_to_answer", False)

    row: Dict[str, Any] = {
        "swap_id": swap_id,
        "from_slug": from_slug,
        "to_slug": to_slug,
        "tier": tier,
        "exact_match": exact_match,
        "flip_position": summary.get("flip_position"),
        "gap_closure": summary.get("gap_closure"),
        "initial_gap": summary.get("initial_gap"),
        "best_gap": summary.get("best_gap"),
    }

    if cg:
        agg = cg.get("aggregate", {})
        row.update({
            "n_contrast_members": cg.get("n_members"),
            "topk_k": cg.get("topk_k"),
            "initial_target_minus_mean": agg.get("initial_target_minus_mean"),
            "best_target_minus_mean": agg.get("best_target_minus_mean"),
            "initial_target_minus_max": agg.get("initial_target_minus_max"),
            "best_target_minus_max": agg.get("best_target_minus_max"),
            "initial_target_minus_topk": agg.get("initial_target_minus_topk"),
            "best_target_minus_topk": agg.get("best_target_minus_topk"),
            "best_rank_within": agg.get("best_rank_within"),
            "initial_rank_within": agg.get("initial_rank_within"),
        })
    else:
        row["n_contrast_members"] = None

    return row


def _fmt(val, fmt=".2f"):
    if val is None:
        return "N/A"
    return f"{val:{fmt}}"


def analyze_trial(swaps_dir: Path, output_path: Optional[Path] = None):
    results = load_trial_results(swaps_dir)
    print(f"Loaded {len(results)} swap results from {swaps_dir}")

    rows = []
    for r in results:
        m = extract_contrast_metrics(r)
        if m:
            rows.append(m)

    if not rows:
        print("No results with trajectory data found.")
        return

    has_contrast = [r for r in rows if r.get("n_contrast_members") is not None]
    no_contrast = [r for r in rows if r.get("n_contrast_members") is None]

    print(f"\nResults with contrast groups: {len(has_contrast)}")
    if no_contrast:
        print(f"Results without contrast groups (legacy): {len(no_contrast)}")

    # Header
    print(f"\n{'='*120}")
    print(f"{'swap':<40} {'tier':>4} {'exact':>5} {'gap_cl':>7} "
          f"{'t-mean0':>8} {'t-mean*':>8} {'t-max0':>7} {'t-max*':>7} "
          f"{'t-topk0':>8} {'t-topk*':>8} {'rank0':>5} {'rank*':>5} {'#cg':>3}")
    print(f"{'-'*120}")

    for r in has_contrast:
        label = f"{r['from_slug']} -> {r['to_slug']}"
        if len(label) > 38:
            label = label[:35] + "..."
        print(
            f"{label:<40} "
            f"{_fmt(r['tier'], 'd') if r['tier'] is not None else 'N/A':>4} "
            f"{'Y' if r['exact_match'] else 'N':>5} "
            f"{_fmt(r['gap_closure']):>7} "
            f"{_fmt(r['initial_target_minus_mean']):>8} "
            f"{_fmt(r['best_target_minus_mean']):>8} "
            f"{_fmt(r['initial_target_minus_max']):>7} "
            f"{_fmt(r['best_target_minus_max']):>7} "
            f"{_fmt(r['initial_target_minus_topk']):>8} "
            f"{_fmt(r['best_target_minus_topk']):>8} "
            f"{_fmt(r['initial_rank_within'], 'd') if r.get('initial_rank_within') is not None else 'N/A':>5} "
            f"{_fmt(r['best_rank_within'], 'd') if r.get('best_rank_within') is not None else 'N/A':>5} "
            f"{r['n_contrast_members'] or 0:>3}"
        )

    # Aggregate comparison
    def _safe_mean(vals):
        valid = [v for v in vals if v is not None]
        return sum(valid) / len(valid) if valid else None

    print(f"\n{'='*80}")
    print("AGGREGATE COMPARISON")
    print(f"{'='*80}")

    metrics_to_compare = [
        ("gap_closure (target-source)", "gap_closure"),
        ("initial target-mean", "initial_target_minus_mean"),
        ("best target-mean", "best_target_minus_mean"),
        ("initial target-max", "initial_target_minus_max"),
        ("best target-max", "best_target_minus_max"),
        ("initial target-topk", "initial_target_minus_topk"),
        ("best target-topk", "best_target_minus_topk"),
    ]

    for label, key in metrics_to_compare:
        vals = [r.get(key) for r in has_contrast]
        mean_val = _safe_mean(vals)
        valid = [v for v in vals if v is not None]
        positive_rate = sum(1 for v in valid if v > 0) / len(valid) if valid else 0
        print(f"  {label:<30}: mean={_fmt(mean_val):>8}, "
              f"positive_rate={positive_rate:.0%}")

    rank_metrics = [
        ("initial rank within group", "initial_rank_within"),
        ("best rank within group", "best_rank_within"),
    ]
    for label, key in rank_metrics:
        vals = [r.get(key) for r in has_contrast]
        mean_val = _safe_mean(vals)
        valid = [v for v in vals if v is not None]
        top1_rate = sum(1 for v in valid if v == 1) / len(valid) if valid else 0
        print(f"  {label:<30}: mean={_fmt(mean_val):>8}, "
              f"top1_rate={top1_rate:.0%}")

    if has_contrast:
        n_members = has_contrast[0].get("n_contrast_members", 0)
        topk_k = has_contrast[0].get("topk_k", 3)
        print(f"\n  Dataset size: {n_members + 2} entities "
              f"({n_members} contrast members, topk_k={topk_k})")

    # Save JSON summary
    if output_path is None:
        output_path = swaps_dir / "_contrast_trial_summary.json"
    summary = {
        "swaps_dir": str(swaps_dir),
        "n_results": len(rows),
        "n_with_contrast": len(has_contrast),
        "per_swap": has_contrast,
        "aggregate": {
            label: {
                "mean": _safe_mean([r.get(key) for r in has_contrast]),
                "positive_rate": (
                    sum(1 for v in [r.get(key) for r in has_contrast]
                        if v is not None and v > 0)
                    / max(1, len(has_contrast))
                ),
            }
            for label, key in metrics_to_compare
        },
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2, ensure_ascii=False)
    print(f"\nSummary written to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze contrast-group trial results"
    )
    parser.add_argument(
        "--swaps-dir", type=str, required=True,
        help="Path to swap run directory (containing by_source/)",
    )
    parser.add_argument(
        "--output", type=str, default=None,
        help="Output JSON path (default: <swaps-dir>/_contrast_trial_summary.json)",
    )
    args = parser.parse_args()

    swaps_dir = Path(args.swaps_dir)
    output_path = Path(args.output) if args.output else None
    analyze_trial(swaps_dir, output_path)


if __name__ == "__main__":
    main()
