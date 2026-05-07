"""
Per-source x condition heatmap on the full 50-state Dallas-target Phase B v3
data.

Rows are the 49 non-Dallas source states (sorted alphabetically).
Columns are the 6 conditions (probe-prompting first since it ties for the
best, then the rest in decreasing source-coverage order).

Cell values:
  * white   -- no variant hit for that (source, condition)
  * filled  -- shaded by the M value at which the hit was found
              (low M = easier transfer; the cell also reports that M)
  * a default-M hit is labelled with a black dot to distinguish it from an
    M-search-rescued hit.

Reads ``output/research/phase3v3_cells.csv`` and writes
``paper/figures/fig_per_source_heatmap.{pdf,png}``.
"""
from __future__ import annotations

import csv
from pathlib import Path

import matplotlib.colors as mcolors
import matplotlib.pyplot as plt
import numpy as np


REPO = Path(__file__).resolve().parents[2]
CSV_PATH = REPO / "output" / "research" / "phase3v3_cells.csv"
OUT_PDF = REPO / "paper" / "figures" / "fig_per_source_heatmap.pdf"
OUT_PNG = REPO / "paper" / "figures" / "fig_per_source_heatmap.png"


CONDITION_ORDER = [
    ("auto",            "probe-prompting"),
    ("auto_top200",     "top-200"),
    ("human",           "human"),
    ("auto_top100",     "top-100"),
    ("auto_top21",      "top-21"),
    ("shuffled_labels", "shuffled-labels"),
]


def load_cells():
    rows = []
    with CSV_PATH.open() as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows


def main() -> None:
    rows = load_cells()

    # Per-source-x-condition aggregate: was there ANY hit, and what was the
    # smallest M that worked (or default M if hit_default).
    sources = sorted({r["source"] for r in rows})
    conds = [c for c, _ in CONDITION_ORDER]

    hit_grid = np.full((len(sources), len(conds)), False)
    m_grid = np.full((len(sources), len(conds)), np.nan)
    default_grid = np.full((len(sources), len(conds)), False)

    src_idx = {s: i for i, s in enumerate(sources)}
    cond_idx = {c: i for i, c in enumerate(conds)}

    for r in rows:
        ci = cond_idx.get(r["condition"])
        si = src_idx.get(r["source"])
        if ci is None or si is None:
            continue
        hit_default = int(r["hit_default"])
        hit_msearch = int(r["hit_msearch"])
        if hit_default:
            hit_grid[si, ci] = True
            default_grid[si, ci] = True
            # Default M=2 amplifier for the human/auto/topK runs
            m_val = 2.0
            cur = m_grid[si, ci]
            m_grid[si, ci] = m_val if (np.isnan(cur) or m_val < cur) else cur
        if hit_msearch and r["m_tuned"]:
            try:
                mt = float(r["m_tuned"])
            except ValueError:
                continue
            hit_grid[si, ci] = True
            cur = m_grid[si, ci]
            m_grid[si, ci] = mt if (np.isnan(cur) or mt < cur) else cur

    # --- Plot ---
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 8.5,
        "axes.titlesize": 11,
        "axes.labelsize": 10,
    })

    fig_h = max(8.0, 0.18 * len(sources))
    fig, ax = plt.subplots(figsize=(7.0, fig_h))

    cmap = plt.cm.viridis_r  # low M = bright (easy transfer)
    norm = mcolors.LogNorm(vmin=0.1, vmax=20.0)

    # Background: white where no hit, coloured by M elsewhere.
    for i in range(len(sources)):
        for j in range(len(conds)):
            if hit_grid[i, j]:
                m_val = m_grid[i, j]
                color = cmap(norm(m_val))
                ax.add_patch(plt.Rectangle((j, i), 1, 1, facecolor=color,
                                           edgecolor="white", linewidth=0.5))
                # Default-M hits get a small black dot in the corner
                if default_grid[i, j]:
                    ax.plot(j + 0.85, i + 0.15, marker="o", color="black",
                            markersize=2.5)
                # Annotate M value (small)
                txt = f"{m_val:.1f}" if m_val < 10 else f"{m_val:.0f}"
                lum = 0.2126 * color[0] + 0.7152 * color[1] + 0.0722 * color[2]
                tcol = "white" if lum < 0.55 else "black"
                ax.text(j + 0.5, i + 0.5, txt, ha="center", va="center",
                        fontsize=6.5, color=tcol)
            else:
                ax.add_patch(plt.Rectangle((j, i), 1, 1, facecolor="#f4f4f4",
                                           edgecolor="white", linewidth=0.5))

    # Axes / ticks
    ax.set_xlim(0, len(conds))
    ax.set_ylim(0, len(sources))
    ax.invert_yaxis()
    ax.set_xticks([j + 0.5 for j in range(len(conds))])
    ax.set_xticklabels([label for _, label in CONDITION_ORDER],
                       rotation=30, ha="right")
    ax.set_yticks([i + 0.5 for i in range(len(sources))])
    ax.set_yticklabels([s.replace("_", " ") for s in sources], fontsize=7)
    for spine in ax.spines.values():
        spine.set_visible(False)
    ax.tick_params(axis="both", which="both", length=0)

    # Coverage row at the top: print counts
    coverage = hit_grid.sum(axis=0)
    for j, n in enumerate(coverage):
        ax.text(j + 0.5, -0.6, f"{n}/49", ha="center", va="bottom",
                fontsize=9, fontweight="bold")

    ax.set_title("Per-source steering hits, full 50 USA states (Dallas target)",
                 pad=22, fontsize=11)

    # Colourbar
    sm = plt.cm.ScalarMappable(norm=norm, cmap=cmap)
    sm.set_array([])
    cbar = fig.colorbar(sm, ax=ax, fraction=0.025, pad=0.02)
    cbar.set_label("M used at hit (lower = easier transfer)", fontsize=9)
    cbar.ax.tick_params(labelsize=7.5)

    # Legend for default-M dot, anchored well below the rotated x-tick labels.
    ax.plot([], [], marker="o", color="black", linestyle="", markersize=4,
            label="black dot = default-M hit (no M-search needed)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10),
              frameon=False, fontsize=8.5)

    plt.tight_layout()
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PDF, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=180, bbox_inches="tight")
    print(f"  wrote {OUT_PDF}")
    print(f"  wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
