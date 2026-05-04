"""
Paper figure: probe-prompting beats both human curation and influence-only
top-K baselines.

Plots n_hits as a function of per-subprocess cumulative amplified influence
across all six Dallas-as-target conditions from the M-search smoke. Two
ceilings are highlighted as horizontal reference lines:
  * human ceiling at 5/35 hits (curated 22-feature baseline)
  * top-K-by-influence ceiling at ~10/35 hits (matched-budget sweep that
    saturates regardless of how much influence we pump in)
Probe-prompting (the auto pipeline with label-driven supernode composition)
sits at 14/35, clearing both ceilings simultaneously: +9 vs human, +4 vs
top-K saturation.

Outputs: paper/figures/fig_topk_saturation.pdf (and matching .png preview).
"""
from __future__ import annotations

from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np

REPO = Path(__file__).resolve().parent.parent
OUT_PDF = REPO / "paper" / "figures" / "fig_topk_saturation.pdf"
OUT_PNG = REPO / "paper" / "figures" / "fig_topk_saturation.png"


# Headline numbers from output/research/smoke_msearch_main_table_v2.csv.
# Each entry: (display_label, family, cum_inf_per_subprocess,
#              n_amplify_per_subprocess, n_hits, mean_M).
DATA = [
    ("human",            "human",   0.0144,   3.4,  5, 12.96),
    ("probe-prompting",  "probe",   0.0671, 120.6, 14,  7.74),
    ("top-21",           "topk",    0.0306,   8.0, 10,  5.20),
    ("top-100",          "topk",    0.0432,  21.1,  9,  6.11),
    ("top-200",          "topk",    0.0502,  34.9, 10,  3.64),
    ("shuffled-labels",  "shuf",    0.0043,   3.4,  0, float("nan")),
]


FAMILY_STYLE = {
    "human":  dict(marker="s", color="#d62728", size=120, edge="black"),
    "probe":  dict(marker="D", color="#1f77b4", size=240, edge="black"),
    "topk":   dict(marker="o", color="#2ca02c", size=120, edge="black"),
    "shuf":   dict(marker="X", color="#888888", size=110, edge="black"),
}


def main() -> None:
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 10,
        "axes.titlesize": 11,
        "axes.labelsize": 10.5,
        "legend.fontsize": 8.5,
        "xtick.labelsize": 9,
        "ytick.labelsize": 9,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })

    fig, ax = plt.subplots(figsize=(6.8, 4.0))

    x_left, x_right = -0.004, 0.094

    # 1a) Human ceiling: faint red horizontal reference line all the way
    #     across, marking the score that human curation achieves.
    ax.axhline(5, linestyle="--", color="#d62728", alpha=0.35, linewidth=1.3, zorder=1)
    ax.text(
        x_right - 0.001, 5.0 + 0.25,
        "human ceiling",
        ha="right", va="bottom", fontsize=8.5, color="#d62728",
        style="italic",
    )

    # 1b) Top-K saturation curve through the top-K family + dotted extension.
    topk_pts = sorted(
        [(x[2], x[4], x[0]) for x in DATA if x[1] == "topk"],
        key=lambda t: t[0],
    )
    xs = [p[0] for p in topk_pts]
    ys = [p[1] for p in topk_pts]
    ax.plot(xs, ys, linestyle="--", color="#2ca02c", alpha=0.7, linewidth=1.6, zorder=1)
    ax.hlines(10, xs[-1], x_right, linestyles=":", colors="#2ca02c", alpha=0.55, linewidth=1.3, zorder=1)
    ax.hlines(10, x_left, xs[0], linestyles=":", colors="#2ca02c", alpha=0.35, linewidth=1.0, zorder=1)
    ax.text(
        x_right - 0.001, 10.0 + 0.25,
        "top-K (influence-only) ceiling",
        ha="right", va="bottom", fontsize=8.5, color="#2ca02c",
        style="italic",
    )

    # 1c) Highlight ring around probe-prompting (the winner).
    probe = next(d for d in DATA if d[1] == "probe")
    ax.scatter(probe[2], probe[4],
               marker="D", s=440, facecolor="none",
               edgecolor="#1f77b4", linewidth=1.6, alpha=0.55, zorder=2)

    # 2) Plot every condition as a marker.
    for label, family, cum_inf, n_amp, n_hits, mean_m in DATA:
        s = FAMILY_STYLE[family]
        ax.scatter(cum_inf, n_hits,
                   marker=s["marker"], s=s["size"],
                   facecolor=s["color"], edgecolor=s["edge"],
                   linewidth=0.9, zorder=3)

    # 3) Annotate each point with its name + feature count subscript.
    annotate = {
        "human":           dict(xytext=( 8,   2), ha="left",   va="center"),
        "probe-prompting": dict(xytext=( 0,  16), ha="center", va="bottom"),
        "top-21":          dict(xytext=(-4,  12), ha="right",  va="bottom"),
        "top-100":         dict(xytext=( 0, -16), ha="center", va="top"),
        "top-200":         dict(xytext=( 4,  12), ha="left",   va="bottom"),
        "shuffled-labels": dict(xytext=( 9,   1), ha="left",   va="center"),
    }
    for label, family, cum_inf, n_amp, n_hits, mean_m in DATA:
        meta = annotate[label]
        text = f"{label}\n({n_amp:g} features)" if family != "human" or label == "human" else label
        # Override: shuffled-labels only shows label (n=3.4 same as human, less
        # informative on its own).
        if label == "shuffled-labels":
            text = f"{label}\n({n_amp:g} features)"
        ax.annotate(
            text,
            (cum_inf, n_hits),
            xytext=meta["xytext"],
            textcoords="offset points",
            ha=meta["ha"], va=meta["va"],
            fontsize=9.5, color="black",
            linespacing=1.05,
        )

    # 4) The two delta annotations that anchor the headline message:
    #      probe-prompting clears BOTH the human ceiling AND the top-K ceiling.
    #    Both arrows live to the right of probe-prompting in the empty corner.
    saturation_y = 10
    human_y = 5
    delta_x_topk = probe[2] + 0.0055
    delta_x_human = probe[2] + 0.0155

    # +4 vs top-K (short arrow, close to the marker)
    ax.annotate(
        "",
        xy=(delta_x_topk, probe[4]),
        xytext=(delta_x_topk, saturation_y),
        arrowprops=dict(arrowstyle="<->", color="#2ca02c", lw=1.6, alpha=0.9),
    )
    ax.text(
        delta_x_topk + 0.0011, (probe[4] + saturation_y) / 2,
        "+4\nvs top-K",
        ha="left", va="center", fontsize=8.8, color="#2ca02c",
        fontweight="semibold", linespacing=1.0,
    )

    # +9 vs human (taller arrow, further out so it doesn't crowd the +4)
    ax.annotate(
        "",
        xy=(delta_x_human, probe[4]),
        xytext=(delta_x_human, human_y),
        arrowprops=dict(arrowstyle="<->", color="#d62728", lw=1.6, alpha=0.9),
    )
    ax.text(
        delta_x_human + 0.0011, (probe[4] + human_y) / 2,
        "+9\nvs human",
        ha="left", va="center", fontsize=8.8, color="#d62728",
        fontweight="semibold", linespacing=1.0,
    )


    # 6) Axis cosmetics.
    ax.set_xlabel(r"cumulative node influence amplified per steering call")
    ax.set_ylabel("Austin hits  (out of 35 cells)")
    ax.set_xlim(x_left, x_right)
    ax.set_ylim(-1.4, 17)
    ax.set_yticks([0, 5, 10, 14])
    ax.grid(axis="y", alpha=0.18, linestyle=":")
    ax.set_title(
        "probe-prompting beats both human curation and influence-only top-K",
        fontsize=10.5, pad=8,
    )

    # 7) Single-line legend.
    legend_handles = [
        plt.Line2D([0], [0], marker="s", color="w", markerfacecolor="#d62728",
                   markeredgecolor="black", markersize=8, label="human (curated)"),
        plt.Line2D([0], [0], marker="D", color="w", markerfacecolor="#1f77b4",
                   markeredgecolor="black", markersize=8, label="probe-prompting (auto pipeline)"),
        plt.Line2D([0], [0], marker="o", color="w", markerfacecolor="#2ca02c",
                   markeredgecolor="black", markersize=8, label="top-K by node-influence"),
        plt.Line2D([0], [0], marker="X", color="w", markerfacecolor="#888888",
                   markeredgecolor="black", markersize=8, label="shuffled-labels (control)"),
    ]
    ax.legend(handles=legend_handles, loc="upper left", frameon=False,
              handletextpad=0.4, borderaxespad=0.3)

    plt.tight_layout()
    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT_PDF, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=200, bbox_inches="tight")
    print(f"  wrote {OUT_PDF}")
    print(f"  wrote {OUT_PNG}")


if __name__ == "__main__":
    main()
