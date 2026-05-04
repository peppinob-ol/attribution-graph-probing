"""
Headline summary table -- per-subprocess view, all conditions.

For each condition averages across the 35 (5 sources x 7 variants) cells:
  type | n_amplify_per_subprocess | cum_influence_amplified_per_subprocess
       | n_hits | n_failures | mean_M

Definitions:
  * Per cell, read amplify features from
        <run>/work/<src>__to__<tgt>__<variant>/features.json
    keep entries with M > 0 (positive amplification; ablations have M < 0).
  * Look each (layer, index) up in the canonical Dallas circuit-tracer metrics
        output/usa_states_fact_batch/texas_dallas/00 Graph Generation/
            graph_feature_static_metrics.csv
    joined as features.index == metrics.id (the metrics CSV uses the column
    `feature` for a sequential node index and stores the raw transcoder id
    under `id`).
  * Sum node_influence to obtain cum_influence_amplified per cell.
  * Average n_amplify and cum_influence across the 35 cells per condition.
  * n_hits / n_failures pull from output/research/smoke_msearch_results.csv
    (combining canonical M=20 hits and M-search rescued hits).
  * mean_M averages the M_amplify that produced each hit (canonical -> 20,
    rescued -> the search-selected value).
"""
from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
COND_ROOT = REPO / "output" / "usa_states_fact_batch" / "_swap_conditions"
CANON_METRICS = (
    REPO
    / "output/usa_states_fact_batch/texas_dallas/00 Graph Generation"
    / "graph_feature_static_metrics.csv"
)
RESULTS_CSV = REPO / "output/research/smoke_msearch_results.csv"
OUT_CSV = REPO / "output/research/smoke_msearch_main_table_v2.csv"

CANONICAL_M = 20.0
CONDITIONS = [
    "human_dallas",
    "auto_dallas",
    "auto_top21_dallas",
    "auto_top100_dallas",
    "auto_top200_dallas",
    "shuffled_labels_dallas",
]
LABELS = {
    "human_dallas": "human",
    "auto_dallas": "auto",
    "auto_top21_dallas": "auto top-21",
    "auto_top100_dallas": "auto top-100",
    "auto_top200_dallas": "auto top-200",
    "shuffled_labels_dallas": "shuffled-labels",
}


def latest_run(cond: str) -> Path | None:
    runs = sorted((COND_ROOT / cond / "_swaps" / "runs").glob("2026*"))
    return runs[-1] if runs else None


def load_canonical_influence() -> dict:
    m = pd.read_csv(CANON_METRICS)
    m["layer"] = m["layer"].astype(int)
    m["id"] = m["id"].astype(int)
    inf = m.groupby(["layer", "id"], as_index=False)["node_influence"].max()
    return {(int(r.layer), int(r.id)): float(r.node_influence) for r in inf.itertuples()}


def cell_amplify_stats(features_path: Path, lookup: dict) -> tuple[int, float, int]:
    if not features_path.exists():
        return 0, 0.0, 0
    feats = json.loads(features_path.read_text())
    n = 0
    cum = 0.0
    missing = 0
    for f in feats:
        m = f.get("M", 0)
        is_ablation = f.get("ablate", False) or (isinstance(m, (int, float)) and m < 0)
        if is_ablation:
            continue
        layer = int(f["layer"])
        idx = int(f["index"])
        n += 1
        v = lookup.get((layer, idx))
        if v is None:
            missing += 1
            continue
        cum += v
    return n, cum, missing


def collect_cells(cond: str, lookup: dict) -> pd.DataFrame:
    run = latest_run(cond)
    if run is None:
        return pd.DataFrame()
    work = run / "work"
    rows = []
    if not work.exists():
        return pd.DataFrame(rows)
    for cell in sorted(work.iterdir()):
        if not cell.is_dir():
            continue
        name = cell.name
        if "__to__" not in name:
            continue
        src, rest = name.split("__to__", 1)
        if "__add_" in rest:
            tgt, variant = rest.split("__", 1)
        else:
            tgt, variant = rest, ""
        n, cum, miss = cell_amplify_stats(cell / "features.json", lookup)
        rows.append({
            "condition": cond,
            "from_slug": src,
            "to_slug": tgt,
            "variant": variant,
            "n_amplify": n,
            "cum_amplify_influence": cum,
            "n_missing_from_metrics": miss,
        })
    return pd.DataFrame(rows)


def hits_and_M(results: pd.DataFrame, cond: str) -> tuple[int, int, float, int]:
    sub = results[results["condition"] == cond]
    n_total = len(sub)
    can_hits = sub[sub["canonical_hit_fuzzy"] == 1]
    tuned_hits = sub[(sub["canonical_hit_fuzzy"] == 0) & (sub["tuned_hit_fuzzy"] == 1)]
    n_hits = len(can_hits) + len(tuned_hits)
    n_fail = n_total - n_hits
    m_values = [CANONICAL_M] * len(can_hits) + tuned_hits["m_tuned"].dropna().tolist()
    if not m_values:
        return n_hits, n_fail, float("nan"), n_total
    return n_hits, n_fail, sum(m_values) / len(m_values), n_total


def main() -> None:
    lookup = load_canonical_influence()
    results = pd.read_csv(RESULTS_CSV) if RESULTS_CSV.exists() else pd.DataFrame()

    rows = []
    for cond in CONDITIONS:
        cells = collect_cells(cond, lookup)
        if results.empty or cond not in set(results["condition"]):
            n_hits, n_fail, mean_m, n_total = (0, 0, float("nan"), 0)
        else:
            n_hits, n_fail, mean_m, n_total = hits_and_M(results, cond)
        if cells.empty:
            mean_n = float("nan")
            mean_inf = float("nan")
            total_amp = 0
            total_inf = 0.0
        else:
            mean_n = cells["n_amplify"].mean()
            mean_inf = cells["cum_amplify_influence"].mean()
            total_amp = int(cells["n_amplify"].sum())
            total_inf = float(cells["cum_amplify_influence"].sum())
        rows.append({
            "type": LABELS[cond],
            "n_amplify_per_subprocess": round(mean_n, 1) if mean_n == mean_n else None,
            "cum_influence_amplified_per_subprocess": round(mean_inf, 4) if mean_inf == mean_inf else None,
            "n_hits": n_hits,
            "n_failures": n_fail,
            "mean_M": round(mean_m, 2) if mean_m == mean_m else None,
            "total_amplify_across_cells": total_amp,
            "total_cum_influence_across_cells": round(total_inf, 4),
            "n_cells": n_total,
        })

    df = pd.DataFrame(rows)
    df.to_csv(OUT_CSV, index=False)
    print(f"  wrote {OUT_CSV}\n")

    cols_md = ["type", "n_amplify_per_subprocess", "cum_influence_amplified_per_subprocess",
               "n_hits", "n_failures", "mean_M"]
    print("Markdown table (means across the cells of each condition):\n")
    print("| " + " | ".join(cols_md) + " |")
    print("|" + "|".join("---" for _ in cols_md) + "|")
    for r in df[cols_md].itertuples(index=False):
        out = []
        for v in r:
            if v is None or (isinstance(v, float) and v != v):
                out.append("--")
            elif isinstance(v, float):
                out.append(f"{v:g}" if abs(v) < 1000 else f"{v:.3f}")
            else:
                out.append(str(v))
        print("| " + " | ".join(out) + " |")

    print("\nFull frame:\n")
    print(df.to_string(index=False))


if __name__ == "__main__":
    main()
