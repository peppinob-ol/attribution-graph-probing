"""
Aggregate Phase B v3 results (full 50-state Dallas-target swap) into a tidy
CSV.

Reads the per-cell JSON files written by ``run_batch_swaps.py`` under each
condition's run directory and emits two CSVs in ``output/research/``:

* ``phase3v3_cells.csv`` -- one row per cell-attempt (source, target, variant,
  condition, hit_at_default_M, hit_via_msearch, m_tuned, suppressed,
  n_amplify, n_ablate, kl_drop, ...).
* ``phase3v3_conditions.csv`` -- per-condition aggregate: cells run, cell
  hits, source coverage (fraction of 49 sources where any variant hits),
  feature counts, M_tuned distribution.

Run from the repo root:

    python scripts/research/phase3v3_aggregate.py [run_id]

Defaults to the run id stored in ``/tmp/phase3v3_run_id.txt``.
"""
from __future__ import annotations

import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


REPO = Path(__file__).resolve().parents[2]
SWAP_ROOT = REPO / "output" / "usa_states_fact_batch" / "_swap_conditions"
OUT_DIR = REPO / "output" / "research"

CONDITIONS = [
    "human_dallas",
    "auto_dallas",
    "auto_top21_dallas",
    "auto_top100_dallas",
    "auto_top200_dallas",
    "shuffled_labels_dallas",
]


def _load_run_id(arg: Optional[str]) -> str:
    if arg:
        return arg
    rid_path = Path("/tmp/phase3v3_run_id.txt")
    if rid_path.exists():
        return rid_path.read_text().strip()
    raise SystemExit("No run id provided and /tmp/phase3v3_run_id.txt missing")


def _safe_load(path: Path) -> Optional[Dict[str, Any]]:
    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _variant_from_name(name: str) -> str:
    """Extract variant suffix from result filename like ``to_<target>__<variant>.json``."""
    stem = name.removesuffix(".json")
    parts = stem.split("__")
    if len(parts) >= 2:
        return parts[1]
    return ""


def _harvest_cell(
    base: Path,
    cond: str,
    src: str,
    cell_path: Path,
) -> Optional[Dict[str, Any]]:
    """Load one default-M cell + its m_tuned sibling (if any) and return a row."""
    name = cell_path.name
    if "__m_tuned" in name:
        return None  # handled via the default-M sibling
    data = _safe_load(cell_path)
    if data is None:
        return None

    pair_meta = data.get("pair", {}) or {}
    target_slug = pair_meta.get("to_slug") or "texas_dallas"
    variant = _variant_from_name(name).removeprefix(f"to_{target_slug}_")
    if variant.startswith("_"):
        variant = variant[1:]

    em = data.get("evaluation", {}).get("exact_match", {})
    hit_default = bool(em.get("steered_has_to_answer"))
    suppressed = bool(em.get("from_suppressed"))

    intervention = data.get("interventions", {}) or data.get("intervention", {}) or {}
    ablate_count = int(intervention.get("ablate_count", 0) or 0)
    amplify_count = int(intervention.get("amplify_count", 0) or 0)

    timing_ms = data.get("duration_ms") or data.get("timing", {}).get("duration_ms")

    # Sibling m_tuned (if any) -- written as a peer file with __m_tuned suffix.
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
        # if m_tuned file was written, that's a hit (per run_single_swap)
        hit_via_msearch = m_tuned is not None

    hit_any = hit_default or hit_via_msearch

    return {
        "condition": cond.removesuffix("_dallas"),
        "source": src,
        "target": target_slug,
        "variant": variant,
        "hit_default": int(hit_default),
        "hit_msearch": int(hit_via_msearch),
        "hit_any": int(hit_any),
        "suppressed": int(suppressed),
        "n_ablate": ablate_count,
        "n_amplify": amplify_count,
        "n_total_features": ablate_count + amplify_count,
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
                row = _harvest_cell(base, cond, src, cell_path)
                if row is not None:
                    cond_cells.append(row)

        cells.extend(cond_cells)

        # Per-condition aggregate
        sources_seen = {r["source"] for r in cond_cells}
        sources_hit = {r["source"] for r in cond_cells if r["hit_any"]}
        n_default_hits = sum(r["hit_default"] for r in cond_cells)
        n_msearch_hits = sum(r["hit_msearch"] for r in cond_cells)
        amp_counts = [r["n_amplify"] for r in cond_cells]
        abl_counts = [r["n_ablate"] for r in cond_cells]
        m_tuned_vals = [float(r["m_tuned"]) for r in cond_cells if r["m_tuned"] != ""]

        conditions_out.append({
            "condition": cond.removesuffix("_dallas"),
            "n_sources_seen": len(sources_seen),
            "sources_hit": len(sources_hit),
            "source_coverage": round(len(sources_hit) / 49, 4),
            "cells_run": len(cond_cells),
            "cells_max_no_earlystop": 49 * 7,
            "cells_skipped_by_earlystop": 49 * 7 - len(cond_cells),
            "cell_hits_default": n_default_hits,
            "cell_hits_msearch": n_msearch_hits,
            "cell_hits_total": n_default_hits + n_msearch_hits,
            "cell_hit_rate": round(
                (n_default_hits + n_msearch_hits) / len(cond_cells) if cond_cells else 0.0,
                4,
            ),
            "mean_n_amplify": round(sum(amp_counts) / len(amp_counts), 2) if amp_counts else 0,
            "mean_n_ablate": round(sum(abl_counts) / len(abl_counts), 2) if abl_counts else 0,
            "n_msearch_hits_with_m": len(m_tuned_vals),
            "m_tuned_min": min(m_tuned_vals) if m_tuned_vals else "",
            "m_tuned_median": sorted(m_tuned_vals)[len(m_tuned_vals)//2] if m_tuned_vals else "",
            "m_tuned_mean": round(sum(m_tuned_vals)/len(m_tuned_vals), 3) if m_tuned_vals else "",
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
    run_id = _load_run_id(argv[1] if len(argv) > 1 else None)
    print(f"Aggregating Phase B v3 results for run_id={run_id}")
    cells, conditions = aggregate(run_id)

    write_csv(cells, OUT_DIR / "phase3v3_cells.csv")
    write_csv(conditions, OUT_DIR / "phase3v3_conditions.csv")

    print("\n=== Per-condition summary ===")
    print(f"{'condition':22s} {'src_hit/49':>11} {'cells':>7} {'hits':>6} "
          f"{'cellHR':>7} {'mean_amp':>9} {'M_med':>7}")
    print("-" * 78)
    for row in conditions:
        cm = row['m_tuned_median']
        cm_str = f"{cm:.2f}" if isinstance(cm, (int, float)) else "  - "
        print(
            f"{row['condition']:22s} "
            f"{row['sources_hit']:>3d}/49      "
            f"{row['cells_run']:>7d} "
            f"{row['cell_hits_total']:>6d} "
            f"{row['cell_hit_rate']*100:>6.1f}% "
            f"{row['mean_n_amplify']:>9.1f} "
            f"{cm_str:>7}"
        )

    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
