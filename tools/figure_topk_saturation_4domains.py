"""
Paper figure (4-panel): per-pair, per-side influence-budget-matched top-K-by-
node-influence baseline vs labeled best-of-(field-add x {default, m_tuned})
across paintings, products, books, USA.

By construction, top-K consumes the *same* per-pair target-side influence as
the labeled winner (smallest prefix whose cumulative ``node_influence`` >=
labeled reference). The interesting axis is therefore feature count: at the
same influence budget, labeled uses many more features (because each
field-add variant pulls in supernode scaffolding that is light per-feature
but heavy in count), while top-K-by-influence uses far fewer. The y-axis
hit rate gap is the apples-to-apples gap.

Each panel:
  * x-axis: per-condition mean number of amplified features per call
            (target side, identity pairs excluded).
  * y-axis: Hit rate (% pairs whose steered output exact-matches the
            target answer; for top-K this is the max over default and
            m_tuned).
  * red diamond: labeled best-of-(field-add x {default, m_tuned}) winner.
  * green circle: top-K-by-influence with the per-pair budget match.
  * mean target-side influence is annotated under each marker so the
    reader can verify that both conditions sit at the same per-pair
    influence budget.
  * paired contingency (both / lbl-only / topk-only / none) under each
    panel for caption-ready stats.

Inputs: ``output/research/topk_im_pairs_<domain>.csv`` produced by
``tools/topk_influence_matched_aggregate.py``.

Outputs: ``paper/figures/fig_topk_im_4domains.{pdf,png}``.
"""
from __future__ import annotations

import csv
import statistics as st
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import matplotlib.pyplot as plt

REPO = Path(__file__).resolve().parent.parent
PAIRS_CSV_DIR = REPO / "output" / "research"
OUT_PDF = REPO / "paper" / "figures" / "fig_topk_im_4domains.pdf"
OUT_PNG = REPO / "paper" / "figures" / "fig_topk_im_4domains.png"

DOMAINS = [
    ("paintings", "Paintings"),
    ("products",  "Products"),
    ("books",     "Books"),
    ("usa",       "USA"),
]

LABELED_COLOR = "#d62728"
TOPK_COLOR    = "#2ca02c"


def _safe_float(x: object) -> Optional[float]:
    if x is None or x == "":
        return None
    try:
        return float(x)
    except (TypeError, ValueError):
        return None


def _safe_bool(x: object) -> Optional[bool]:
    if x is None or x == "":
        return None
    try:
        return bool(int(x))
    except (TypeError, ValueError):
        return None


def _load_pairs(csv_path: Path) -> List[Dict[str, object]]:
    if not csv_path.exists():
        return []
    with csv_path.open() as fh:
        return list(csv.DictReader(fh))


def _summarise(rows: List[Dict[str, object]]) -> Dict[str, float]:
    """Compute the per-domain markers shown in the figure."""
    paired = [
        r for r in rows
        if _safe_bool(r["labeled_hit"]) is not None
    ]
    nonid = [r for r in rows if _safe_bool(r["is_identity"]) is False]
    nonid_paired = [
        r for r in nonid
        if _safe_bool(r["labeled_hit"]) is not None
    ]

    def _mean(xs: List[Optional[float]]) -> float:
        xs = [x for x in xs if x is not None]
        return st.mean(xs) if xs else 0.0

    def _rate(rows_: List[Dict[str, object]], key: str) -> float:
        bools = [_safe_bool(r[key]) for r in rows_]
        bools = [b for b in bools if b is not None]
        return (sum(1 for b in bools if b) / len(bools)) if bools else 0.0

    # Mean target-side influence consumed (excluding identity, where K_tgt = 0).
    topk_x = _mean([_safe_float(r["achieved_sum_tgt"]) for r in nonid])
    topk_K = _mean([_safe_float(r["K_tgt"]) for r in nonid])
    topk_y = _rate(rows, "best_hit")  # use full matrix for hit rate (matches summary CSV)

    lbl_x = _mean([_safe_float(r["labeled_ref_sum_tgt"]) for r in nonid_paired])
    lbl_n = _mean([_safe_float(r["labeled_n_amplify"]) for r in nonid_paired])
    lbl_y = _rate(paired, "labeled_hit")

    # paired contingency on the matched subset, for caption-ready numbers
    both = lbl_only = topk_only = both_lose = 0
    for r in paired:
        lbl = bool(_safe_bool(r["labeled_hit"]))
        topk = bool(_safe_bool(r["best_hit"]))
        if lbl and topk:
            both += 1
        elif lbl:
            lbl_only += 1
        elif topk:
            topk_only += 1
        else:
            both_lose += 1

    return {
        "n_pairs": len(rows),
        "topk_x": topk_x,
        "topk_y": topk_y,
        "topk_K": topk_K,
        "lbl_x": lbl_x,
        "lbl_y": lbl_y,
        "lbl_n": lbl_n,
        "paired_both_win": both,
        "paired_labeled_only_win": lbl_only,
        "paired_topk_only_win": topk_only,
        "paired_both_lose": both_lose,
    }


def main() -> None:
    plt.rcParams.update({
        "font.family": "serif",
        "font.size": 9.5,
        "axes.titlesize": 10.5,
        "axes.labelsize": 9.5,
        "legend.fontsize": 8.5,
        "xtick.labelsize": 8.5,
        "ytick.labelsize": 8.5,
        "axes.spines.top": False,
        "axes.spines.right": False,
    })

    fig, axes = plt.subplots(1, 4, figsize=(12.0, 3.6), sharey=True)
    legend_handles = [
        plt.Line2D([0], [0], marker="D", color="w",
                   markerfacecolor=LABELED_COLOR, markeredgecolor="black",
                   markersize=9, label="labeled best-of (field-add x adaptive M)"),
        plt.Line2D([0], [0], marker="o", color="w",
                   markerfacecolor=TOPK_COLOR, markeredgecolor="black",
                   markersize=8, label="top-K by node-influence (per-pair budget-matched)"),
    ]

    summaries: List[Tuple[str, str, Optional[Dict[str, float]]]] = []
    for domain_key, domain_label in DOMAINS:
        rows = _load_pairs(PAIRS_CSV_DIR / f"topk_im_pairs_{domain_key}.csv")
        s = _summarise(rows) if rows else None
        summaries.append((domain_key, domain_label, s))

    # axes share y; pick a y-limit that covers every domain comfortably
    ymax = 0.0
    for _, _, s in summaries:
        if s is None:
            continue
        ymax = max(ymax, s["lbl_y"], s["topk_y"])
    y_top = max(0.7, ymax + 0.10)

    for ax, (domain_key, domain_label, s) in zip(axes, summaries):
        if s is None or s["n_pairs"] == 0:
            ax.set_title(f"{domain_label}\n(no data)", color="gray")
            ax.set_xticks([])
            ax.tick_params(axis="y", labelleft=False)
            continue

        x_lbl = s["lbl_n"]
        x_topk = s["topk_K"]
        y_lbl = s["lbl_y"] * 100
        y_topk = s["topk_y"] * 100

        ax.scatter(
            x_lbl, y_lbl,
            marker="D", s=200, facecolor=LABELED_COLOR, edgecolor="black",
            linewidth=0.9, zorder=4,
        )
        ax.scatter(
            x_topk, y_topk,
            marker="o", s=160, facecolor=TOPK_COLOR, edgecolor="black",
            linewidth=0.9, zorder=4,
        )

        # Connect the two with a downward arrow showing the Hit% gap.
        ax.annotate(
            "",
            xy=(x_topk, y_topk + 0.6),
            xytext=(x_topk, y_lbl - 0.6),
            arrowprops=dict(arrowstyle="->", color="black", lw=1.1, alpha=0.75),
        )
        delta_pp = y_lbl - y_topk
        ax.text(
            x_topk + (x_lbl - x_topk) * 0.08, (y_lbl + y_topk) / 2,
            f"{delta_pp:+.1f}\npp",
            ha="left", va="center", fontsize=8.6, color="black",
            fontweight="semibold", linespacing=1.0,
        )

        # Labels next to markers
        ax.annotate(
            f"labeled  n={s['lbl_n']:.0f}",
            xy=(x_lbl, y_lbl),
            xytext=(8, 6), textcoords="offset points",
            ha="left", va="bottom",
            fontsize=8.7, color=LABELED_COLOR, fontweight="semibold",
        )
        ax.annotate(
            f"top-K  K={s['topk_K']:.0f}",
            xy=(x_topk, y_topk),
            xytext=(8, -6), textcoords="offset points",
            ha="left", va="top",
            fontsize=8.7, color=TOPK_COLOR, fontweight="semibold",
        )

        # Footnote: per-pair influence budget consumed (must be ~equal between
        # the two markers, by construction). One number per panel, since the
        # match is per-pair on every pair.
        ax.text(
            0.02, 0.97,
            f"mean target-side influence:\n"
            f"  labeled = {s['lbl_x']:.4f}\n"
            f"  top-K  = {s['topk_x']:.4f}",
            transform=ax.transAxes,
            fontsize=7.7, ha="left", va="top",
            color="#444", linespacing=1.15,
            family="monospace",
        )
        # Bottom annotation: paired contingency
        ax.text(
            0.02, 0.04,
            f"both={s['paired_both_win']} | "
            f"lbl={s['paired_labeled_only_win']} | "
            f"topk={s['paired_topk_only_win']} | "
            f"none={s['paired_both_lose']}",
            transform=ax.transAxes,
            fontsize=7.5, ha="left", va="bottom",
            style="italic", color="#666",
        )

        ax.set_title(f"{domain_label}  (N={s['n_pairs']})", pad=8)
        ax.set_xlabel("mean amplified features per call")

        # X scale: zero -> 1.4x the larger of the two means, with a small
        # padding so the labels don't fall off the right edge.
        x_max = max(x_lbl, x_topk)
        ax.set_xlim(0, x_max * 1.55)
        ax.set_ylim(-3, y_top * 100 + 3)
        ax.grid(axis="y", linestyle=":", alpha=0.35)

    axes[0].set_ylabel("Hit rate  (%)")

    fig.suptitle(
        "Per-pair influence-matched top-K-by-influence vs labeled best-of (4 in-scope domains)",
        fontsize=11, y=1.02,
    )
    fig.legend(
        handles=legend_handles,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.07),
        ncol=2, frameon=False,
    )

    OUT_PDF.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout(rect=(0, 0.04, 1, 0.96))
    fig.savefig(OUT_PDF, bbox_inches="tight")
    fig.savefig(OUT_PNG, dpi=200, bbox_inches="tight")
    print(f"  wrote {OUT_PDF.relative_to(REPO)}")
    print(f"  wrote {OUT_PNG.relative_to(REPO)}")


if __name__ == "__main__":
    main()
