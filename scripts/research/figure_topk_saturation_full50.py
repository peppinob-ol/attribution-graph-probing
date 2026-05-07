"""
Paper figure (full-50-state version): source-level top-K saturation.

Single-panel scatter of mean amplified-feature cumulative influence per
steering call (x, log) vs source hit-rate (y, % of 49 non-Dallas USA
sources where the target answer appears at least once across that
source's variants). The top-K family saturates well below probe-prompting
on a per-cell basis but catches up at the source level once enough
variants are tried; the human-curated supernodes sit between top-21 and
top-100; the shuffled-labels control sits at zero.

Reads ``output/research/phase3v3_conditions.csv`` for source hit-rates
and walks the per-cell ``features.json`` files of the phase3v3 swap run
to recover the mean cumulative node-influence carried by amplified
features per call. Writes
``paper/figures/fig_topk_saturation_full50.{pdf,png}``.
"""
from __future__ import annotations

import csv
import json
from collections import defaultdict
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


REPO = Path(__file__).resolve().parents[2]
CSV_PATH = REPO / "output" / "research" / "phase3v3_conditions.csv"
SWAP_ROOT = REPO / "output" / "usa_states_fact_batch" / "_swap_conditions"
PHASE3V3_RUN = "full_50states_phase3v3_20260505_0251"
TARGET_METRICS = (
    REPO / "output" / "usa_states_fact_batch" / "texas_dallas"
    / "00 Graph Generation" / "graph_feature_static_metrics.csv"
)
OUT_PDF = REPO / "paper" / "figures" / "fig_topk_saturation_full50.pdf"
OUT_PNG = REPO / "paper" / "figures" / "fig_topk_saturation_full50.png"


# Colours that match the existing figure family.
FAMILY_STYLE = {
    "human":  dict(marker="s", color="#d62728", size=130, edge="black"),
    "probe":  dict(marker="D", color="#1f77b4", size=130, edge="black"),
    "topk":   dict(marker="o", color="#2ca02c", size=130, edge="black"),
    "shuf":   dict(marker="X", color="#888888", size=130, edge="black"),
}


PRETTY = {
    "human":           ("human",           "human"),
    "auto":            ("ours",            "probe"),
    "auto_top21":      ("top-21",          "topk"),
    "auto_top100":     ("top-100",         "topk"),
    "auto_top200":     ("top-200",         "topk"),
    "shuffled_labels": ("shuffled-labels", "shuf"),
}


# Map from condition (as in phase3v3_conditions.csv) to the swap-condition
# directory name (which has a ``_dallas`` suffix).
COND_DIR = {
    "human":           "human_dallas",
    "auto":            "auto_dallas",
    "auto_top21":      "auto_top21_dallas",
    "auto_top100":     "auto_top100_dallas",
    "auto_top200":     "auto_top200_dallas",
    "shuffled_labels": "shuffled_labels_dallas",
}


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


def mean_cum_influence(condition: str, infl: dict[tuple[int, int], float]) -> float:
    """Mean per-cell sum of amplified-feature node_influence across the phase3v3 run."""
    work_dir = SWAP_ROOT / COND_DIR[condition] / "_swaps" / "runs" / PHASE3V3_RUN / "work"
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


def load_conditions():
    rows = []
    with CSV_PATH.open() as f:
        for r in csv.DictReader(f):
            r["sources_hit"] = int(r["sources_hit"])
            r["n_sources_seen"] = int(r["n_sources_seen"])
            r["cells_run"] = int(r["cells_run"])
            rows.append(r)
    return rows


def panel_source_rate(ax, rows, infl_by_key):
    """Source hit-rate (sources_hit / n_sources_seen) vs cumulative-influence budget."""
    pts = []
    for r in rows:
        label, fam = PRETTY[r["condition"]]
        pts.append({
            "label": label,
            "family": fam,
            "x": mean_cum_influence(r["condition"], infl_by_key),
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
        "human":           dict(xytext=( 10,   0), ha="left",   va="center"),
        "ours":            dict(xytext=(  0,  14), ha="center", va="bottom"),
        "top-21":          dict(xytext=(  0, -16), ha="center", va="top"),
        "top-100":         dict(xytext=(-10,  12), ha="right",  va="bottom"),
        "top-200":         dict(xytext=(  0, -16), ha="center", va="top"),
        "shuffled-labels": dict(xytext=( 10,   0), ha="left",   va="center"),
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
    ax.set_xlabel("mean cumulative influence per call")
    ax.set_ylabel("source hit-rate (%)")
    ax.set_ylim(-5, 108)
    ax.grid(axis="y", alpha=0.18, linestyle=":")


def main() -> None:
    rows = load_conditions()
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
                   label="shuffled-labels (control)"),
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
