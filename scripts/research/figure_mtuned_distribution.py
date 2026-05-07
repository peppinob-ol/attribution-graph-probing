"""
Distribution of M_tuned per condition on the full 50-state Phase B v3 run.

For every cell that hit (either at default M=2 or via M-search), we have an
amplification factor M at which the steered output flipped to the target
answer. Lower M means a smaller perturbation was sufficient. We use M as a
proxy for how "naturally" the chosen feature bag aligns with the target
concept: the smaller the M, the closer the bag is to the model's own
representation of the target.

Reads ``output/research/phase3v3_cells.csv`` and writes
``paper/figures/fig_mtuned_distribution.{pdf,png}``.
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


REPO = Path(__file__).resolve().parents[2]
CSV_PATH = REPO / "output" / "research" / "phase3v3_cells.csv"
OUT_PDF = REPO / "paper" / "figures" / "fig_mtuned_distribution.pdf"
OUT_PNG = REPO / "paper" / "figures" / "fig_mtuned_distribution.png"


CONDITION_ORDER = [
    ("auto",            "probe-prompting"),
    ("auto_top200",     "top-200"),
    ("human",           "human"),
    ("auto_top100",     "top-100"),
    ("auto_top21",      "top-21"),
]

CONDITION_COLORS = {
    "auto":         "#1f77b4",
    "auto_top200":  "#2ca02c",
    "human":        "#d62728",
    "auto_top100":  "#9467bd",
    "auto_top21":   "#ff7f0e",
}


def load_cells():
    rows = []
    with CSV_PATH.open() as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def m_per_hit(rows):
    """Return list of M values, one per (cell that hit) per condition."""
    by_cond = {c: [] for c, _ in CONDITION_ORDER}
    for r in rows:
        if r["condition"] not in by_cond:
            continue
        if int(r["hit_default"]):
            by_cond[r["condition"]].append(2.0)
        elif int(r["hit_msearch"]) and r["m_tuned"]:
            try:
                by_cond[r["condition"]].append(float(r["m_tuned"]))
            except ValueError:
                pass
    return by_cond


def main() -> None:
    rows = load_cells()
    data = m_per_hit(rows)

    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 9.5,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })

    fig, ax = plt.subplots(figsize=(7.0, 4.2))

    positions = list(range(len(CONDITION_ORDER)))
    labels = []
    medians = []

    for pos, (cond_key, cond_label) in enumerate(CONDITION_ORDER):
        vals = data.get(cond_key, [])
        labels.append(f"{cond_label}\n(n={len(vals)})")
        if not vals:
            continue
        arr = np.array(vals)
        med = float(np.median(arr))
        medians.append((cond_label, med, len(vals)))

        # log-scale jitter strip
        x = pos + np.random.uniform(-0.12, 0.12, size=len(arr))
        ax.scatter(x, arr,
                   color=CONDITION_COLORS[cond_key], alpha=0.55, s=18,
                   edgecolor="none", zorder=2)

        # Boxplot box (manual for log-scale safety)
        q25, q75 = np.percentile(arr, [25, 75])
        ax.add_patch(plt.Rectangle(
            (pos - 0.3, q25), 0.6, q75 - q25,
            facecolor="white",
            edgecolor=CONDITION_COLORS[cond_key], linewidth=1.4, zorder=3,
        ))
        ax.hlines(med, pos - 0.32, pos + 0.32,
                  colors=CONDITION_COLORS[cond_key], linewidth=2.2, zorder=4)

        # Median annotation
        ax.text(pos, max(arr) * 1.18, f"med={med:.1f}",
                ha="center", va="bottom", fontsize=8.5,
                color=CONDITION_COLORS[cond_key], fontweight="semibold")

    # Reference lines
    ax.axhline(2.0, linestyle=":", color="gray", alpha=0.45, linewidth=1.0)
    ax.text(len(CONDITION_ORDER) - 0.5, 2.05, "default M = 2",
            ha="right", va="bottom", fontsize=8.0, color="gray", style="italic")
    ax.axhline(20.0, linestyle=":", color="gray", alpha=0.4, linewidth=1.0)
    ax.text(len(CONDITION_ORDER) - 0.5, 20.5, "M-search ceiling = 20",
            ha="right", va="bottom", fontsize=8.0, color="gray", style="italic")

    ax.set_yscale("log")
    ax.set_ylim(0.08, 30)
    ax.set_xticks(positions)
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("M used at hit (log scale)\nlower = smaller perturbation suffices")
    ax.set_title(
        "How big does the perturbation have to be to flip the output?",
        pad=10, fontsize=11,
    )
    ax.grid(axis="y", which="major", alpha=0.20, linestyle=":")
    ax.grid(axis="y", which="minor", alpha=0.10, linestyle=":")

    plt.tight_layout()
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PDF, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=200, bbox_inches="tight")
    print(f"  wrote {OUT_PDF}")
    print(f"  wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
