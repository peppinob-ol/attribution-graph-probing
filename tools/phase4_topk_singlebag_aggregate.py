"""
Aggregate phase-4 fair top-K Dallas saturation re-run into per-cell and
per-condition CSVs.

Reads the per-pair JSON files written by ``run_batch_swaps.py`` for the
four single-bag conditions (``auto_top{10,21,100,200}_dallas``) under a
shared run id, and emits two CSVs in ``output/research/``:

* ``phase4_topk_singlebag_cells.csv`` -- one row per (condition, source,
  target) cell. Phase-4 uses single-bag interventions, so there is at
  most one cell per pair (no field-additivity variants).
* ``phase4_topk_singlebag_conditions.csv`` -- per-condition aggregate
  with the same column layout as ``phase3v3_conditions.csv`` so the
  figure script can stitch the two files together.

Run from the repo root::

    python tools/phase4_topk_singlebag_aggregate.py [run_id]

Defaults to the most recent ``phase4_topk_singlebag_*`` run id found
under any of the four condition dirs.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO = Path(__file__).resolve().parents[1]
SWAP_ROOT = REPO / "output" / "usa_states_fact_batch" / "_swap_conditions"
OUT_DIR = REPO / "output" / "research"

CONDITIONS = [
    "auto_top10_dallas",
    "auto_top21_dallas",
    "auto_top100_dallas",
    "auto_top200_dallas",
]

PAIRS_PER_CONDITION = 49


def _safe_load(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _detect_latest_run_id() -> str:
    candidates: List[Tuple[float, str]] = []
    for cond in CONDITIONS:
        runs_dir = SWAP_ROOT / cond / "_swaps" / "runs"
        if not runs_dir.exists():
            continue
        for child in runs_dir.iterdir():
            if not child.is_dir():
                continue
            if not child.name.startswith("phase4_topk_singlebag_"):
                continue
            candidates.append((child.stat().st_mtime, child.name))
    if not candidates:
        raise SystemExit(
            "No phase4_topk_singlebag_* run id found and none provided. "
            f"Looked under {SWAP_ROOT}/<cond>/_swaps/runs/."
        )
    candidates.sort(reverse=True)
    return candidates[0][1]


def _harvest_cell(
    cond: str,
    src: str,
    cell_path: Path,
) -> Optional[Dict[str, Any]]:
    """Load the default-M cell JSON + its m_tuned sibling (if any)."""
    name = cell_path.name
    if "__m_tuned" in name:
        return None
    data = _safe_load(cell_path)
    if data is None:
        return None

    pair_meta = data.get("pair", {}) or {}
    target_slug = pair_meta.get("to_slug") or "texas_dallas"

    em = data.get("evaluation", {}).get("exact_match", {})
    hit_default = bool(em.get("steered_has_to_answer"))
    suppressed = bool(em.get("from_suppressed"))

    intervention = (
        data.get("interventions", {}) or data.get("intervention", {}) or {}
    )
    ablate_count = int(intervention.get("ablate_count", 0) or 0)
    amplify_count = int(intervention.get("amplify_count", 0) or 0)

    timing_ms = data.get("duration_ms") or data.get("timing", {}).get("duration_ms")

    m_tuned: Optional[float] = None
    msearch_phase: Optional[str] = None
    msearch_steps: Optional[int] = None
    hit_via_msearch = False
    msearch_path = cell_path.with_name(name.removesuffix(".json") + "__m_tuned.json")
    msearch_data = _safe_load(msearch_path) if msearch_path.exists() else None
    if msearch_data is not None:
        ms = msearch_data.get("m_search", {}) or {}
        m_tuned = ms.get("m_tuned")
        msearch_phase = ms.get("phase")
        msearch_steps = ms.get("total_steps")
        hit_via_msearch = m_tuned is not None

    hit_any = hit_default or hit_via_msearch

    diagnostics = intervention.get("diagnostics", {}) or {}

    return {
        "condition": cond.removesuffix("_dallas"),
        "source": src,
        "target": target_slug,
        "variant": "single_bag",
        "hit_default": int(hit_default),
        "hit_msearch": int(hit_via_msearch),
        "hit_any": int(hit_any),
        "suppressed": int(suppressed),
        "n_ablate": ablate_count,
        "n_amplify": amplify_count,
        "n_total_features": ablate_count + amplify_count,
        "achieved_sum_src": diagnostics.get("achieved_sum_src", ""),
        "achieved_sum_tgt": diagnostics.get("achieved_sum_tgt", ""),
        "m_tuned": m_tuned if m_tuned is not None else "",
        "msearch_phase": msearch_phase or "",
        "msearch_steps": msearch_steps if msearch_steps is not None else "",
        "duration_ms": timing_ms or "",
    }


def aggregate(run_id: str) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
    cells: List[Dict[str, Any]] = []
    conditions_out: List[Dict[str, Any]] = []

    for cond in CONDITIONS:
        base = SWAP_ROOT / cond / "_swaps" / "runs" / run_id
        bs = base / "by_source"
        if not bs.exists():
            print(f"WARN: missing by_source dir for {cond}: {bs}")
            continue

        cond_cells: List[Dict[str, Any]] = []
        for src_dir in sorted(bs.iterdir()):
            if not src_dir.is_dir():
                continue
            src = src_dir.name
            for cell_path in sorted(src_dir.glob("to_*.json")):
                row = _harvest_cell(cond, src, cell_path)
                if row is not None:
                    cond_cells.append(row)

        cells.extend(cond_cells)

        sources_seen = {r["source"] for r in cond_cells}
        sources_hit = {r["source"] for r in cond_cells if r["hit_any"]}
        n_default_hits = sum(r["hit_default"] for r in cond_cells)
        n_msearch_hits = sum(r["hit_msearch"] for r in cond_cells)
        amp_counts = [r["n_amplify"] for r in cond_cells]
        abl_counts = [r["n_ablate"] for r in cond_cells]
        m_tuned_vals = [
            float(r["m_tuned"]) for r in cond_cells if r["m_tuned"] != ""
        ]

        conditions_out.append({
            "condition": cond.removesuffix("_dallas"),
            "n_sources_seen": len(sources_seen),
            "sources_hit": len(sources_hit),
            "source_coverage": round(
                len(sources_hit) / PAIRS_PER_CONDITION, 4
            ),
            "cells_run": len(cond_cells),
            "cells_max_no_earlystop": PAIRS_PER_CONDITION,
            "cells_skipped_by_earlystop": 0,
            "cell_hits_default": n_default_hits,
            "cell_hits_msearch": n_msearch_hits,
            "cell_hits_total": n_default_hits + n_msearch_hits,
            "cell_hit_rate": round(
                (n_default_hits + n_msearch_hits) / len(cond_cells)
                if cond_cells else 0.0,
                4,
            ),
            "mean_n_amplify": round(
                sum(amp_counts) / len(amp_counts), 2
            ) if amp_counts else 0,
            "mean_n_ablate": round(
                sum(abl_counts) / len(abl_counts), 2
            ) if abl_counts else 0,
            "n_msearch_hits_with_m": len(m_tuned_vals),
            "m_tuned_min": min(m_tuned_vals) if m_tuned_vals else "",
            "m_tuned_median": (
                sorted(m_tuned_vals)[len(m_tuned_vals) // 2]
                if m_tuned_vals else ""
            ),
            "m_tuned_mean": round(
                sum(m_tuned_vals) / len(m_tuned_vals), 3
            ) if m_tuned_vals else "",
            "m_tuned_max": max(m_tuned_vals) if m_tuned_vals else "",
        })

    return cells, conditions_out


def write_csv(rows: List[Dict[str, Any]], path: Path) -> None:
    if not rows:
        print(f"WARN: no rows to write at {path}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = list(rows[0].keys())
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
    print(f"  wrote {path}  ({len(rows)} rows)")


def main(argv: List[str]) -> int:
    if len(argv) > 1:
        run_id = argv[1]
    else:
        run_id = _detect_latest_run_id()
    print(f"Aggregating phase-4 single-bag results for run_id={run_id}")
    cells, conditions = aggregate(run_id)

    write_csv(cells, OUT_DIR / "phase4_topk_singlebag_cells.csv")
    write_csv(conditions, OUT_DIR / "phase4_topk_singlebag_conditions.csv")

    print("\n=== Per-condition summary ===")
    print(
        f"{'condition':18s} {'src_hit/49':>11} {'cells':>7} {'hits':>6} "
        f"{'cellHR':>7} {'mean_amp':>9} {'M_med':>7}"
    )
    print("-" * 74)
    for row in conditions:
        cm = row["m_tuned_median"]
        cm_str = f"{cm:.2f}" if isinstance(cm, (int, float)) else "  - "
        print(
            f"{row['condition']:18s} "
            f"{row['sources_hit']:>3d}/49      "
            f"{row['cells_run']:>7d} "
            f"{row['cell_hits_total']:>6d} "
            f"{row['cell_hit_rate'] * 100:>6.1f}% "
            f"{row['mean_n_amplify']:>9.2f} "
            f"{cm_str:>7}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
