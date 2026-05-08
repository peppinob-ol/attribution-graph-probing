"""
Paper figure (full-50-state version): source-level top-K saturation.

Single-panel scatter of mean amplified-feature cumulative influence per
steering call (x) vs source hit-rate (y, % of 49 non-Dallas USA sources
where the target answer appears at least once across that source's
variants).

Reference markers (``human``, ``ours``, label-shuffled random control) come from
the labeled best-of field-additivity-with-adaptive-M reference
(``full_50states_phase3v3_20260505_0251``). The top-K family is the
fair single-bag re-run from phase-4 (``phase4_topk_singlebag_*``):
target = top-K Dallas features by node_influence, source = canonical
auto's full grouping, no field-additivity, adaptive M-search only.

Reads:
  - ``output/research/phase3v3_conditions.csv``                (human/ours/shuffled-labels)
  - ``output/research/phase4_topk_singlebag_conditions.csv``   (top-21/100/200; top-10 omitted from figure)

Writes ``paper/figures/fig_topk_saturation_full50.{pdf,png}``.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path
from typing import Optional

import matplotlib.pyplot as plt
import numpy as np


REPO = Path(__file__).resolve().parents[2]
PHASE3V3_CSV = REPO / "output" / "research" / "phase3v3_conditions.csv"
PHASE4_CSV = REPO / "output" / "research" / "phase4_topk_singlebag_conditions.csv"
SWAP_ROOT = REPO / "output" / "usa_states_fact_batch" / "_swap_conditions"
PHASE3V3_RUN = "full_50states_phase3v3_20260505_0251"
TARGET_METRICS = (
    REPO / "output" / "usa_states_fact_batch" / "texas_dallas"
    / "00 Graph Generation" / "graph_feature_static_metrics.csv"
)
OUT_PDF = REPO / "paper" / "figures" / "fig_topk_saturation_full50.pdf"
OUT_PNG = REPO / "paper" / "figures" / "fig_topk_saturation_full50.png"


FAMILY_STYLE = {
    "human":  dict(marker="s", color="#d62728", size=130, edge="black"),
    "probe":  dict(marker="D", color="#1f77b4", size=130, edge="black"),
    "topk":   dict(marker="o", color="#2ca02c", size=130, edge="black"),
    "shuf":   dict(marker="X", color="#888888", size=130, edge="black"),
}


# (label, family, source_csv_key) per condition. ``source_csv_key`` selects
# either the phase3v3 reference (labeled best-of) or the phase-4 fair
# single-bag re-run for the top-K family.
PRETTY = {
    "human":           ("human",           "human", "phase3v3"),
    "auto":            ("ours",            "probe", "phase3v3"),
    "shuffled_labels": ("random", "shuf",  "phase3v3"),
    "auto_top21":      ("top-21",          "topk",  "phase4"),
    "auto_top100":     ("top-100",         "topk",  "phase4"),
    "auto_top200":     ("top-200",         "topk",  "phase4"),
}


# Map from condition key (in either CSV) to the swap-condition directory
# name (which has a ``_dallas`` suffix).
COND_DIR = {
    "human":           "human_dallas",
    "auto":            "auto_dallas",
    "shuffled_labels": "shuffled_labels_dallas",
    "auto_top21":      "auto_top21_dallas",
    "auto_top100":     "auto_top100_dallas",
    "auto_top200":     "auto_top200_dallas",
}


def detect_phase4_run_id() -> Optional[str]:
    """Latest ``phase4_topk_singlebag_*`` run id under any phase-4 condition dir."""
    candidates: list[tuple[float, str]] = []
    for cond in ("auto_top21_dallas", "auto_top100_dallas", "auto_top200_dallas"):
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
        return None
    candidates.sort(reverse=True)
    return candidates[0][1]


def load_target_influence(metrics_csv: Path) -> dict[tuple[int, int], float]:
    """Return ``(layer, feature_index) -> sum of node_influence`` over all ctx for the
    target graph (texas_dallas). Embed and logit rows are skipped."""
    infl: dict[tuple[int, int], float] = defaultdict(float)
    with metrics_csv.open() as f:
        for r in csv.DictReader(f):
            try:
                L = int(r["layer"])
            except (TypeError, ValueError):
                continue
            if L < 0 or L >= 26:
                continue
            if not r["node_influence"]:
                continue
            F = int(r["id"])
            infl[(L, F)] += float(r["node_influence"])
    return infl


def mean_cum_influence(
    condition: str,
    run_id: str,
    infl: dict[tuple[int, int], float],
) -> float:
    """Mean per-cell sum of amplified-feature node_influence across ``run_id``."""
    work_dir = SWAP_ROOT / COND_DIR[condition] / "_swaps" / "runs" / run_id / "work"
    if not work_dir.exists():
        return float("nan")
    totals: list[float] = []
    for cell_dir in sorted(work_dir.iterdir()):
        feats_path = cell_dir / "features.json"
        if not feats_path.exists():
            continue
        feats = json.loads(feats_path.read_text())
        s = 0.0
        for e in feats:
            if float(e.get("M", 0)) <= 0:
                continue
            key = (int(e["layer"]), int(e["index"]))
            s += infl.get(key, 0.0)
        totals.append(s)
    if not totals:
        return float("nan")
    return sum(totals) / len(totals)


def load_conditions(phase4_run_id: Optional[str]):
    """Return one row per marker, joining phase3v3 and phase4 CSVs.

    Phase3v3 supplies ``human / auto / shuffled_labels`` markers; phase4
    supplies ``auto_top10/21/100/200``. Both CSVs share the same column
    names so we just tag each row with its source run id.
    """
    rows: list[dict] = []

    keep_phase3v3 = {"human", "auto", "shuffled_labels"}
    if PHASE3V3_CSV.exists():
        with PHASE3V3_CSV.open() as f:
            for r in csv.DictReader(f):
                if r["condition"] not in keep_phase3v3:
                    continue
                r["sources_hit"] = int(r["sources_hit"])
                r["n_sources_seen"] = int(r["n_sources_seen"])
                r["cells_run"] = int(r["cells_run"])
                r["__run_id"] = PHASE3V3_RUN
                rows.append(r)

    if phase4_run_id and PHASE4_CSV.exists():
        keep_phase4 = {"auto_top21", "auto_top100", "auto_top200"}
        with PHASE4_CSV.open() as f:
            for r in csv.DictReader(f):
                if r["condition"] not in keep_phase4:
                    continue
                r["sources_hit"] = int(r["sources_hit"])
                r["n_sources_seen"] = int(r["n_sources_seen"])
                r["cells_run"] = int(r["cells_run"])
                r["__run_id"] = phase4_run_id
                rows.append(r)

    return rows


def panel_source_rate(ax, rows, infl_by_key):
    """Source hit-rate (sources_hit / n_sources_seen) vs cumulative-influence budget."""
    pts = []
    for r in rows:
        label, fam, _ = PRETTY[r["condition"]]
        pts.append({
            "label": label,
            "family": fam,
            "x": mean_cum_influence(r["condition"], r["__run_id"], infl_by_key),
            "y": 100.0 * r["sources_hit"] / r["n_sources_seen"],
            "sources_hit": r["sources_hit"],
            "n_sources": r["n_sources_seen"],
        })

    topk = sorted([p for p in pts if p["family"] == "topk"], key=lambda d: d["x"])
    ax.plot([p["x"] for p in topk], [p["y"] for p in topk],
            linestyle="--", color="#2ca02c", alpha=0.6, linewidth=1.5, zorder=1)

    for p in pts:
        s = FAMILY_STYLE[p["family"]]
        ax.scatter(p["x"], p["y"],
                   marker=s["marker"], s=s["size"],
                   facecolor=s["color"], edgecolor=s["edge"],
                   linewidth=0.9, zorder=3)

    annot = {
        "human":           dict(xytext=( 10,  -2), ha="left",   va="center"),
        "ours":            dict(xytext=(  0,  14), ha="center", va="bottom"),
        "random":          dict(xytext=( 10,   0), ha="left",   va="center"),
        "top-21":          dict(xytext=(  0,  14), ha="center", va="bottom"),
        "top-100":         dict(xytext=(  0,  14), ha="center", va="bottom"),
        "top-200":         dict(xytext=(  0,  14), ha="center", va="bottom"),
    }
    for p in pts:
        meta = annot[p["label"]]
        ax.annotate(p["label"], (p["x"], p["y"]),
                    xytext=meta["xytext"], textcoords="offset points",
                    ha=meta["ha"], va=meta["va"], fontsize=9)

    ax.axhline(100.0, color="gray", linewidth=0.7, alpha=0.5, linestyle=":")

    xs = [p["x"] for p in pts]
    xmax = max(xs)
    ax.set_xlim(0, xmax * 1.18)
    ax.set_xlabel("mean cumulative influence per swap")
    ax.set_ylabel("successful swaps (%)")
    ax.set_ylim(-5, 108)
    ax.grid(axis="y", alpha=0.18, linestyle=":")


def main() -> None:
    phase4_run_id = detect_phase4_run_id()
    if phase4_run_id is None:
        print(
            "WARN: no phase4_topk_singlebag_* run id found; figure will only "
            "include human/ours/random markers."
        )
    else:
        print(f"Using phase4 run id: {phase4_run_id}")
    rows = load_conditions(phase4_run_id)
    infl_by_key = load_target_influence(TARGET_METRICS)
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 9.5,
        "axes.labelsize": 10,
        "axes.titlesize": 11,
        "legend.fontsize": 8.5,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })

    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    panel_source_rate(ax, rows, infl_by_key)

    legend_handles = [
        plt.Line2D([0], [0], marker="s", color="w", markerfacecolor="#d62728",
                   markeredgecolor="black", markersize=8, label="human"),
        plt.Line2D([0], [0], marker="D", color="w", markerfacecolor="#1f77b4",
                   markeredgecolor="black", markersize=8, label="ours"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#2ca02c",
                   markeredgecolor="black", markersize=8,
                   label="top-K by node influence"),
        plt.Line2D([0], [0], marker="X", color="w", markerfacecolor="#888888",
                   markeredgecolor="black", markersize=8,
                   label="random"),
    ]
    fig.legend(handles=legend_handles, loc="lower center",
               bbox_to_anchor=(0.5, -0.04), ncol=2, frameon=False)

    plt.tight_layout(rect=[0, 0.05, 1, 1.0])
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PDF, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=200, bbox_inches="tight")
    print(f"  wrote {OUT_PDF}")
    print(f"  wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
