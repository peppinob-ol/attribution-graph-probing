"""Export the cross-run-best matrix and per-cell winners as static files.

Wraps ``demo.app.data.cross_run_best.CrossRunBestAggregator`` so the matrix
CSV (binary 1.0/0.0) and a winners JSON (with the winning field subset for
every hit cell) can be regenerated outside the demo.

Usage:
    python -m tools.export_swap_winners \
        --output-dir output \
        --dataset usa_states_batch \
        --csv-out output/usa_states_batch/_swaps/runs/full_50states_v1/_matrix_best_across.csv \
        --winners-out output/usa_states_batch/_swaps/runs/full_50states_v1/_winners_best_across.json
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path


def _ensure_demo_on_path() -> None:
    repo_root = Path(__file__).resolve().parent.parent
    demo_dir = repo_root / "demo"
    if not demo_dir.exists():
        raise SystemExit(f"demo/ not found at {demo_dir}")
    if str(demo_dir) not in sys.path:
        sys.path.insert(0, str(demo_dir))


def _build_aggregator(output_dir: Path):
    _ensure_demo_on_path()
    from app.data.cross_run_best import CrossRunBestAggregator
    from app.data.loader import DemoRegistry

    registry = DemoRegistry(output_dir)
    return CrossRunBestAggregator(registry)


def export(
    *,
    output_dir: Path,
    dataset: str,
    csv_out: Path,
    winners_out: Path,
    hit_tier: float = 5.0,
) -> tuple[int, int]:
    """Run the aggregator and write CSV + winners JSON to disk.

    Returns ``(n_hits, n_total)`` over the populated cells (excluding the
    diagonal and never-run pairs).
    """
    agg = _build_aggregator(output_dir)
    result = agg.get_best_matrix(dataset)
    matrix = result.get("matrix", {})
    winners = result.get("winners", {})

    slugs = sorted({s for src in matrix for s in [src, *matrix[src].keys()]})

    csv_out.parent.mkdir(parents=True, exist_ok=True)
    n_hits = 0
    n_total = 0
    with csv_out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow(["from_slug", *slugs])
        for src in slugs:
            row: list[str] = [src]
            for tgt in slugs:
                if src == tgt:
                    row.append("")
                    continue
                tier = matrix.get(src, {}).get(tgt)
                if tier is None:
                    row.append("")
                    continue
                n_total += 1
                if tier >= hit_tier:
                    n_hits += 1
                    row.append("1.0")
                else:
                    row.append("0.0")
            w.writerow(row)

    winners_out.parent.mkdir(parents=True, exist_ok=True)
    with winners_out.open("w", encoding="utf-8") as fh:
        json.dump(
            {
                "dataset": dataset,
                "considered_runs": result.get("considered_runs", []),
                "winners": winners,
            },
            fh,
            indent=2,
        )

    return n_hits, n_total


def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Output root passed to DemoRegistry (default: output).",
    )
    p.add_argument(
        "--dataset",
        type=str,
        default="usa_states_batch",
        help="Dataset id (folder name under output/).",
    )
    p.add_argument(
        "--csv-out",
        type=str,
        required=True,
        help="Where to write the binary 1.0/0.0 best-across-runs matrix CSV.",
    )
    p.add_argument(
        "--winners-out",
        type=str,
        required=True,
        help="Where to write the winners JSON (with fields_used per cell).",
    )
    p.add_argument(
        "--hit-tier",
        type=float,
        default=5.0,
        help="Tier threshold for a hit (default 5.0 = strict capital match).",
    )
    args = p.parse_args()

    n_hits, n_total = export(
        output_dir=Path(args.output_dir).resolve(),
        dataset=args.dataset,
        csv_out=Path(args.csv_out).resolve(),
        winners_out=Path(args.winners_out).resolve(),
        hit_tier=args.hit_tier,
    )
    pct = n_hits / max(1, n_total)
    print(f"hits {n_hits}/{n_total} ({pct:.1%})")
    print(f"wrote {args.csv_out}")
    print(f"wrote {args.winners_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
