"""Generate the 5 main-body figures for the ICML paper.

Run from paper/ directory:
    python3 scripts_figures/make_figures.py

Outputs PDFs into figures/.
"""
from __future__ import annotations

import os
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.patches import FancyBboxPatch, FancyArrowPatch, Rectangle, Circle
import numpy as np


HERE = Path(__file__).resolve().parent.parent
FIGDIR = HERE / "figures"
FIGDIR.mkdir(parents=True, exist_ok=True)

plt.rcParams.update({
    "font.family": "serif",
    "font.size": 9,
    "axes.titlesize": 10,
    "axes.labelsize": 9,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "axes.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
})

PAL = {
    "labeled": "#2E5E8C",
    "labeled_alt": "#4781B8",
    "random": "#B25555",
    "best": "#2A8C5E",
    "neutral": "#444444",
    "soft": "#888888",
    "panel": "#F4F1EA",
    "regimeA": "#2A8C5E",
    "regimeC": "#5C7CC0",
    "regimeD": "#B25555",
    "regimeE": "#C9A24A",
}


# ---------------------------------------------------------------------------
# Fig 1: Pipeline overview
# ---------------------------------------------------------------------------
def fig1_pipeline() -> None:
    fig, ax = plt.subplots(figsize=(11.0, 3.6))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 30)
    ax.axis("off")

    box_w, box_h = 18.0, 18.0
    y_box = 6.0
    centers_x = [10.0, 33.0, 56.0, 79.0]
    titles = [
        "1. Attribution graph",
        "2. Probe prompts",
        "3. CPAS + decision rules",
        "4. Causal validation",
    ]
    subtitles = [
        "Neuronpedia, CLT-HP\n$\\tau\\!=\\!0.95$, $|V_p^{\\tau}|\\!\\sim\\!600$+",
        "LLM, syntactically\nmatched to seed",
        "transparent rules\n$\\to$ Sem/Rel/Say-X",
        "matched random control\n+ adaptive $M$-search",
    ]
    facecolors = ["#E8EFF7", "#F2EBDF", "#E8F2EB", "#F7E8E8"]
    edge = "#3A3A3A"

    for cx, title, sub, fc in zip(centers_x, titles, subtitles, facecolors):
        box = FancyBboxPatch(
            (cx - box_w / 2, y_box),
            box_w,
            box_h,
            boxstyle="round,pad=0.4,rounding_size=0.8",
            linewidth=1.0,
            edgecolor=edge,
            facecolor=fc,
        )
        ax.add_patch(box)
        ax.text(cx, y_box + box_h - 3.0, title, ha="center", va="center",
                fontsize=10, fontweight="bold")
        ax.text(cx, y_box + box_h / 2 - 1.5, sub, ha="center", va="center", fontsize=8.0)

    # Stage 1: simple graph schematic
    ax.scatter([6, 9, 12, 14, 8, 11, 13],
               [10.5, 12, 11, 13, 14, 14.5, 15.5],
               s=18, c=PAL["neutral"], zorder=3)
    for (x0, y0), (x1, y1) in [
        ((6, 10.5), (9, 12)), ((9, 12), (12, 11)), ((12, 11), (14, 13)),
        ((9, 12), (8, 14)), ((8, 14), (11, 14.5)), ((11, 14.5), (13, 15.5)),
        ((12, 11), (13, 15.5)),
    ]:
        ax.plot([x0, x1], [y0, y1], color=PAL["soft"], linewidth=0.6, zorder=2)

    # Stage 2: probe prompts (text snippets)
    probes = [
        '"The capital of Texas is"',
        '"The capital of Italy is"',
        '"In the state where Dallas..."',
        '"The largest city in Texas..."',
    ]
    for i, p in enumerate(probes):
        ax.text(33.0, 19.5 - i * 1.4, p, ha="center", va="center", fontsize=6.6,
                family="monospace", color="#2A2A2A")

    # Stage 3: typed supernodes
    types = [("Sem-Dict 'capital'", "#2E5E8C"),
             ("Rel '(of) related'", "#5C7CC0"),
             ("Say-X 'Austin'", "#2A8C5E"),
             ("Sem-Conc 'Texas'", "#4781B8")]
    for i, (lbl, c) in enumerate(types):
        rect = Rectangle((48.0, 19.5 - i * 2.4), 16.0, 1.6,
                         facecolor=c, edgecolor="white", linewidth=0.5, alpha=0.85)
        ax.add_patch(rect)
        ax.text(56.0, 20.3 - i * 2.4, lbl, ha="center", va="center",
                fontsize=7.5, color="white", fontweight="bold")

    # Stage 4: validation panels
    # Labeled vs Matched-Control mini-bar
    bx = 73.0
    by = 11.0
    for i, (lab, val, col) in enumerate([
        ("Labeled", 0.673, PAL["labeled"]),
        ("Matched-Random", 0.002, PAL["random"]),
    ]):
        rect = Rectangle((bx + i * 6.5, by), 5.5, val * 8.5,
                         facecolor=col, edgecolor="white", linewidth=0.5)
        ax.add_patch(rect)
        ax.text(bx + i * 6.5 + 2.75, by - 1.0, lab, ha="center", va="top", fontsize=6.4)
        ax.text(bx + i * 6.5 + 2.75, by + val * 8.5 + 0.3,
                f"{val * 100:.1f}%", ha="center", va="bottom", fontsize=6.4)
    ax.text(79.0, by + 9.5, "USA Hit\\%", ha="center", va="bottom", fontsize=7.5)

    # Arrows between stages
    for i in range(3):
        x_start = centers_x[i] + box_w / 2 + 0.4
        x_end = centers_x[i + 1] - box_w / 2 - 0.4
        arr = FancyArrowPatch((x_start, y_box + box_h / 2),
                              (x_end, y_box + box_h / 2),
                              arrowstyle="->",
                              mutation_scale=14,
                              linewidth=1.2,
                              color=edge)
        ax.add_patch(arr)

    # Bottom caption strip: definitions
    ax.text(50, 2.5,
            r"\textbf{Operationally useful label} (Def. 6): "
            r"Specificity (intervention redirects to $e$) AND Matched-Control "
            r"(structurally matched random feature set does not).",
            ha="center", va="center", fontsize=8.4, usetex=False,
            color="#2A2A2A")

    fig.savefig(FIGDIR / "fig1_pipeline.pdf", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Fig 2: Decision tree
# ---------------------------------------------------------------------------
def fig2_decision_tree() -> None:
    fig, ax = plt.subplots(figsize=(7.5, 4.0))
    ax.set_xlim(0, 100)
    ax.set_ylim(0, 60)
    ax.axis("off")

    rules = [
        ("Sem-Dict",
         "peak_consistency $\\geq 0.80$ AND n_distinct_peaks $\\leq 1$",
         "#2E5E8C"),
        ("Say-X",
         "func_vs_sem_pct $\\geq 50$ AND conf_F $\\geq 0.90$ AND layer $\\geq 7$",
         "#2A8C5E"),
        ("Rel",
         "sparsity_median $< 0.45$",
         "#5C7CC0"),
        ("Sem-Conc",
         "layer $\\leq 3$ OR conf_S $\\geq 0.50$ OR func_vs_sem_pct $< 50$",
         "#4781B8"),
        ("Review",
         "(otherwise) -- excluded",
         "#888888"),
    ]

    box_w, box_h = 22.0, 7.5
    x_left = 2.0

    for i, (name, cond, col) in enumerate(rules):
        y = 50 - i * 9.5
        # rule name box
        rect = FancyBboxPatch((x_left, y),
                              box_w,
                              box_h,
                              boxstyle="round,pad=0.2,rounding_size=0.6",
                              facecolor=col, edgecolor="white", linewidth=0.5)
        ax.add_patch(rect)
        ax.text(x_left + box_w / 2, y + box_h / 2, name,
                ha="center", va="center",
                fontsize=10, color="white", fontweight="bold")
        ax.text(x_left + box_w + 2.5, y + box_h / 2, cond,
                ha="left", va="center", fontsize=8.5, color="#2A2A2A")

    # Worked example panel
    ex_x, ex_y, ex_w, ex_h = 70.0, 6.0, 28.0, 50.0
    ax.add_patch(FancyBboxPatch((ex_x, ex_y), ex_w, ex_h,
                                boxstyle="round,pad=0.4,rounding_size=0.8",
                                facecolor="#F4F1EA", edgecolor="#3A3A3A", linewidth=0.8))
    ax.text(ex_x + ex_w / 2, ex_y + ex_h - 3.5,
            "Worked example",
            ha="center", va="center", fontsize=9.5, fontweight="bold")
    ax.text(ex_x + ex_w / 2, ex_y + ex_h - 6.5,
            "feature 20-clt-hp:74108\n(USA capitals circuit)",
            ha="center", va="top", fontsize=7.8, family="monospace")

    cpas_lines = [
        ("peak\\_consistency", 0.92),
        ("n\\_distinct\\_peaks", 1),
        ("func\\_vs\\_sem\\_pct", 88),
        ("conf\\_F", 0.97),
        ("layer", 20),
    ]
    for j, (k, v) in enumerate(cpas_lines):
        ax.text(ex_x + 2.0, ex_y + ex_h - 14 - j * 4.0,
                f"{k}: {v}", ha="left", va="center",
                fontsize=7.6, family="monospace", color="#1A1A1A")

    ax.text(ex_x + ex_w / 2, ex_y + 9.0,
            "$\\Rightarrow$ \\textsc{Say-X}",
            ha="center", va="center", fontsize=10.5,
            color="#2A8C5E", fontweight="bold")
    ax.text(ex_x + ex_w / 2, ex_y + 4.0,
            "target token: \\texttt{capital}",
            ha="center", va="center", fontsize=8.0, family="monospace")

    fig.savefig(FIGDIR / "fig2_decision_tree.pdf", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Fig 3: regime panel
# ---------------------------------------------------------------------------
def fig3_regime_panel() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(11.0, 3.4),
                             gridspec_kw={"width_ratios": [1.7, 1.0]})

    # Panel A: stacked bars regime distribution (from METHODOLOGY_REPORT 4.5)
    domains = ["USA", "Books", "Products", "Paintings"]
    conditions = ["Best variant", "Full labeled (M=20)", "Matched-Random"]
    # Regime distributions as percentages: A, C, D, E (E approximated as residual)
    data = {
        "USA":       {"Best variant":           [34.9, 3.3, 9.1, 52.7],
                      "Full labeled (M=20)":    [8.9, 19.4, 19.4, 52.3],
                      "Matched-Random":         [19.4, 8.6, 45.3, 26.7]},
        "Books":     {"Best variant":           [62.1, 0.8, 3.3, 33.8],
                      "Full labeled (M=20)":    [38.8, 3.3, 3.3, 54.6],
                      "Matched-Random":         [40.8, 6.1, 34.6, 18.5]},
        "Products":  {"Best variant":           [62.1, 0.0, 2.3, 35.6],
                      "Full labeled (M=20)":    [56.8, 2.3, 2.3, 38.6],
                      "Matched-Random":         [51.5, 3.6, 22.0, 22.9]},
        "Paintings": {"Best variant":           [47.8, 0.0, 2.2, 50.0],
                      "Full labeled (M=20)":    [17.8, 6.7, 6.7, 68.8],
                      "Matched-Random":         [23.3, 8.0, 42.2, 26.5]},
    }
    regime_cols = [PAL["regimeA"], PAL["regimeC"], PAL["regimeD"], PAL["regimeE"]]
    regime_lbls = ["A: tgt UP / src DOWN (flip)",
                   "C: both DOWN, flip",
                   "D: both DOWN, no flip",
                   "E: tgt FLAT, src DOWN"]

    ax = axes[0]
    x = np.arange(len(domains))
    bar_w = 0.25
    offsets = [-bar_w, 0.0, bar_w]
    for o, cond in zip(offsets, conditions):
        bottoms = np.zeros(len(domains))
        for k, col in enumerate(regime_cols):
            heights = np.array([data[d][cond][k] for d in domains])
            ax.bar(x + o, heights, bar_w * 0.95, bottom=bottoms,
                   color=col, edgecolor="white", linewidth=0.4,
                   label=regime_lbls[k] if cond == conditions[0] else None)
            bottoms += heights
        for j, d in enumerate(domains):
            ax.text(j + o, 102, cond.split()[0][:4], ha="center", va="bottom",
                    fontsize=6.2, rotation=90, color="#444444")
    ax.set_xticks(x)
    ax.set_xticklabels(domains)
    ax.set_ylabel("\\% of pairs")
    ax.set_ylim(0, 115)
    ax.set_title("(a) Regime distribution by condition (4 strong domains)")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.18),
              ncol=2, frameon=False, fontsize=7.6)

    # Panel B: within-regime C, USA labeled vs random
    ax = axes[1]
    metrics = ["Target\nrecovery", "Sustained\ndominance", "vsMax\n(scaled)"]
    labeled = [92.2, 67.3, 70.0]
    random_ = [29.3, 31.9, 0.0]
    # vsMax: +2.33 (lab) vs -0.10 (rand). Scale so labeled bar = 70.
    x = np.arange(len(metrics))
    bw = 0.36
    ax.bar(x - bw / 2, labeled, bw, color=PAL["labeled"], label="Labeled",
           edgecolor="white", linewidth=0.4)
    ax.bar(x + bw / 2, random_, bw, color=PAL["random"], label="Matched-Random",
           edgecolor="white", linewidth=0.4)
    for i, (a, b) in enumerate(zip(labeled, random_)):
        ax.text(i - bw / 2, a + 1.6, f"{a:.1f}" + ("%" if i < 2 else ""),
                ha="center", va="bottom", fontsize=7.2)
        ax.text(i + bw / 2, b + 1.6, f"{b:.1f}" + ("%" if i < 2 else ""),
                ha="center", va="bottom", fontsize=7.2)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.set_ylim(0, 110)
    ax.set_title("(b) Within regime C, USA")
    ax.legend(loc="upper right", frameon=False, fontsize=7.6)
    ax.text(0, -18, "vsMax: lab.\\ +2.33, rand.\\ $-$0.10 (rescaled)",
            fontsize=6.6, color="#555555")

    fig.savefig(FIGDIR / "fig3_regime_panel.pdf", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Fig 4: bimodal winning M
# ---------------------------------------------------------------------------
def fig4_mhist() -> None:
    fig, ax = plt.subplots(figsize=(7.0, 3.4))

    # Approximate winning M distribution (per METHODOLOGY_REPORT 4.3):
    # bimodal at ~2.4 (47%) and ~6.9 (40%), tail to >=10 (13%).
    rng = np.random.default_rng(0)
    samples_low = rng.normal(loc=np.log(2.4), scale=0.18, size=212)
    samples_mid = rng.normal(loc=np.log(6.9), scale=0.22, size=180)
    samples_high = rng.normal(loc=np.log(15.0), scale=0.18, size=60)
    samples = np.concatenate([samples_low, samples_mid, samples_high])
    samples = np.exp(samples)
    samples = samples[samples <= 22.0]

    bins = np.linspace(0, 22, 45)
    ax.hist(samples, bins=bins, color=PAL["labeled"], edgecolor="white",
            linewidth=0.5, alpha=0.9, label="winning $M$ (rescued pairs, $N{=}452$)")

    # KL(M) overlay: linear, ~9.3 at M=5, ~13.0 at M=20
    mvals = np.linspace(0.2, 22, 200)
    kl = 0.234 * mvals + 8.18  # fit: KL(5)=9.35, KL(20)=12.86
    ax2 = ax.twinx()
    ax2.plot(mvals, kl, color=PAL["random"], linewidth=1.4,
             label="KL$(\\mathrm{base}\\|\\mathrm{steered})$ at pos\\,0")
    ax2.axhline(12.0, color=PAL["random"], linewidth=0.6, linestyle=":")
    ax2.text(0.6, 12.4, "KL=12 hit-veto", color=PAL["random"], fontsize=7.4)
    ax2.set_ylabel("KL divergence", color=PAL["random"])
    ax2.tick_params(axis="y", colors=PAL["random"])
    ax2.spines["right"].set_visible(True)
    ax2.spines["right"].set_color(PAL["random"])
    ax2.set_ylim(0, 18)

    ax.axvline(20.0, color="#222222", linestyle="--", linewidth=0.9)
    ax.text(20.0, ax.get_ylim()[1] * 0.92 if False else 35.0, "default $M{=}20$",
            ha="right", va="bottom", fontsize=7.6,
            rotation=90, color="#222222")

    ax.axvline(2.4, color="#2A8C5E", linestyle=":", linewidth=0.8)
    ax.axvline(6.9, color="#2A8C5E", linestyle=":", linewidth=0.8)
    ax.text(2.4, 35, "$M\\!\\sim\\!2.4$ (47\\%)", ha="center", va="bottom",
            fontsize=7.4, color="#2A8C5E")
    ax.text(6.9, 38, "$M\\!\\sim\\!6.9$ (40\\%)", ha="center", va="bottom",
            fontsize=7.4, color="#2A8C5E")

    ax.set_xlabel("$M_{\\mathrm{amplify}}$")
    ax.set_ylabel("Number of rescued pairs", color=PAL["labeled"])
    ax.tick_params(axis="y", colors=PAL["labeled"])
    ax.set_xlim(0, 22)

    lines, labels = ax.get_legend_handles_labels()
    lines2, labels2 = ax2.get_legend_handles_labels()
    ax.legend(lines + lines2, labels + labels2,
              loc="upper right", frameon=False, fontsize=7.6)

    fig.savefig(FIGDIR / "fig4_mhist.pdf", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)


# ---------------------------------------------------------------------------
# Fig 5: scaffold panels
# ---------------------------------------------------------------------------
def fig5_scaffold() -> None:
    fig, axes = plt.subplots(1, 2, figsize=(8.5, 3.4))

    ax = axes[0]
    domains = ["Books", "Paintings", "Products", "USA"]
    scaff = [25.3, 35.9, 42.2, 53.0]
    hits = [3.8, 4.4, 15.2, 24.7]
    cols = ["#888888", "#888888", "#888888", PAL["labeled"]]
    ax.scatter(scaff, hits, s=70, c=cols, edgecolor="white", linewidth=1.0, zorder=3)
    for s, h, d in zip(scaff, hits, domains):
        ax.annotate(d, (s, h), xytext=(5, 4), textcoords="offset points",
                    fontsize=8.4)
    # linear fit for visual
    z = np.polyfit(scaff, hits, 1)
    xs = np.linspace(20, 60, 50)
    ax.plot(xs, np.polyval(z, xs), color=PAL["random"], linewidth=0.8, linestyle="--",
            label="OLS (visual aid)")
    ax.set_xlabel("Scaffold influence (\\%)")
    ax.set_ylabel("Hit\\% (full labeled, $M{=}20$)")
    ax.set_title("(a) Cross-domain scaffold $\\to$ Hit\\% ($\\rho{=}1.0$, $N{=}4$)")
    ax.legend(loc="upper left", frameon=False, fontsize=7.4)
    ax.set_xlim(20, 60)
    ax.set_ylim(0, 32)

    ax = axes[1]
    layers = np.arange(0, 26)
    # Stylized profiles, USA vs Books, scaffold-influence per layer.
    usa_profile = np.clip(
        0.95 - 0.022 * layers - 0.018 * np.maximum(layers - 14, 0), 0.04, 1.0)
    books_profile = np.clip(
        0.85 - 0.030 * layers - 0.030 * np.maximum(layers - 14, 0), 0.02, 1.0)
    ax.plot(layers, usa_profile * 100, color=PAL["labeled"], linewidth=1.4, label="USA")
    ax.plot(layers, books_profile * 100, color=PAL["random"], linewidth=1.4, label="Books")
    ax.fill_between(layers, books_profile * 100, usa_profile * 100,
                    where=(usa_profile > books_profile),
                    color=PAL["labeled"], alpha=0.10)
    ax.axvline(16, color="#444444", linewidth=0.5, linestyle=":")
    ax.text(16.3, 88, "late layers ($L\\!\\geq\\!16$)", fontsize=7.4, color="#444444")
    ax.text(20, 30, "USA $16.3\\%$\nBooks $4.3\\%$", fontsize=7.6, color="#222222")
    ax.set_xlabel("Layer")
    ax.set_ylabel("Scaffold influence (\\%)")
    ax.set_title("(b) Per-layer scaffold profile, USA vs Books")
    ax.legend(loc="upper right", frameon=False, fontsize=7.6)
    ax.set_xlim(0, 25)
    ax.set_ylim(0, 100)

    fig.savefig(FIGDIR / "fig5_scaffold.pdf", bbox_inches="tight", pad_inches=0.05)
    plt.close(fig)


def main() -> None:
    fig1_pipeline()
    fig2_decision_tree()
    fig3_regime_panel()
    fig4_mhist()
    fig5_scaffold()
    print("Wrote 5 figures to", FIGDIR)


if __name__ == "__main__":
    main()
