"""Export paper-ready clustering figures, excluding the sounds dataset.

Run from the repo root or from `paper/`:

    .venv/bin/python paper/scripts_figures/make_clustering_figures.py

Outputs three PDFs into ``paper/figures/``:

- ``fig_pca_per_dataset.pdf``: 2x2 facet of PCA(2) over deduped features,
  coloured by rule class, one panel per non-sounds dataset.
- ``fig_tsne_per_dataset.pdf``: 2x2 facet of per-dataset t-SNE.
- ``fig_gmm_bic.pdf``: BIC-preferred GMM (full covariance) on the
  deduped non-sounds frame -- contingency heatmap + UMAP scatter.

The script reads ``output/research/feature_manifest.csv`` (built by
``scripts/research/build_feature_manifest.py``) and is fully
deterministic (``random_state=0``).
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import umap
from sklearn.decomposition import PCA
from sklearn.manifold import TSNE
from sklearn.metrics import adjusted_rand_score
from sklearn.mixture import GaussianMixture
from sklearn.preprocessing import StandardScaler


REPO_ROOT = Path(__file__).resolve().parent.parent.parent
MANIFEST = REPO_ROOT / "output" / "research" / "feature_manifest.csv"
FIGDIR = REPO_ROOT / "paper" / "figures"
FIGDIR.mkdir(parents=True, exist_ok=True)


METRIC_COLUMNS = [
    "peak_consistency_main",
    "n_distinct_peaks_log1p",
    "func_vs_sem_pct",
    "conf_F",
    "sparsity_median",
    "layer",
]

CLASS_ORDER = [
    "Semantic (Dictionary)",
    "Semantic (Dictionary fallback)",
    "Semantic (Concept)",
    "Relationship",
    'Say "X"',
    "Ambiguous/Review",
]

CLASS_PALETTE = dict(
    zip(CLASS_ORDER, sns.color_palette("tab10", n_colors=len(CLASS_ORDER)))
)

DATASET_ORDER = [
    "usa_states_batch",
    "book_characters_authors_batch",
    "products_founders_batch",
    "paintings_painters_batch",
]

DATASET_LABELS = {
    "usa_states_batch": "USA states",
    "book_characters_authors_batch": "Books",
    "products_founders_batch": "Products",
    "paintings_painters_batch": "Paintings",
}

SOUNDS_KEY = "sounds_colors_batch"


PAPER_RC = {
    "font.family": "serif",
    "font.size": 9,
    "axes.titlesize": 9.5,
    "axes.labelsize": 9,
    "legend.fontsize": 8,
    "xtick.labelsize": 8,
    "ytick.labelsize": 8,
    "axes.linewidth": 0.6,
    "axes.spines.top": False,
    "axes.spines.right": False,
    "savefig.bbox": "tight",
    "savefig.pad_inches": 0.02,
    "pdf.fonttype": 42,
    "ps.fonttype": 42,
}


def info(msg: str) -> None:
    elapsed = time.perf_counter() - _T0
    print(f"[{elapsed:6.1f}s] {msg}", flush=True)


def save_fig(fig: plt.Figure, pdf_path: Path) -> None:
    """Save the figure as PDF (paper artefact) and PNG (preview), then close."""
    fig.savefig(pdf_path)
    png_path = pdf_path.with_suffix(".png")
    fig.savefig(png_path, dpi=200)
    plt.close(fig)
    info(f"wrote {pdf_path.relative_to(REPO_ROOT)} (+ .png)")


def class_label(row: pd.Series) -> str:
    if bool(row.get("review", False)):
        return "Ambiguous/Review"
    if row["pred_label"] == 'Say "X"':
        return 'Say "X"'
    if row["pred_label"] == "Relationship":
        return "Relationship"
    if row["subtype"] == "Dictionary":
        return "Semantic (Dictionary)"
    if row["subtype"] == "Dictionary (fallback)":
        return "Semantic (Dictionary fallback)"
    return "Semantic (Concept)"


def build_frames() -> tuple[pd.DataFrame, pd.DataFrame]:
    manifest = pd.read_csv(MANIFEST)
    manifest = manifest[manifest["dataset"] != SOUNDS_KEY].copy()
    manifest["n_distinct_peaks_log1p"] = np.log1p(manifest["n_distinct_peaks"])
    manifest["class"] = manifest.apply(class_label, axis=1)

    dedup = (
        manifest.groupby(["layer", "feature"], as_index=False)
        .agg(
            {
                "dataset": lambda s: s.mode().iat[0],
                "class": lambda s: s.mode().iat[0],
                "peak_consistency_main": "median",
                "n_distinct_peaks": "median",
                "func_vs_sem_pct": "median",
                "conf_F": "median",
                "sparsity_median": "median",
            }
        )
    )
    dedup["n_distinct_peaks_log1p"] = np.log1p(dedup["n_distinct_peaks"])

    info(f"manifest rows (no sounds): {len(manifest):,}")
    info(f"deduped global features (no sounds): {len(dedup):,}")
    return manifest, dedup


def style_panel_axes(ax: plt.Axes, title: str) -> None:
    ax.set_title(title, fontsize=9.0, pad=3)
    ax.set_xlabel("")
    ax.set_ylabel("")
    ax.tick_params(axis="both", which="both", labelsize=7.0)
    ax.grid(True, linewidth=0.4, alpha=0.6)
    for spine in ("top", "right"):
        ax.spines[spine].set_visible(False)


def add_class_legend(fig: plt.Figure, present: list[str], ncol: int) -> None:
    handles = [
        plt.Line2D(
            [0],
            [0],
            marker="o",
            linestyle="",
            color=CLASS_PALETTE[cls],
            markersize=5.5,
            label=cls,
        )
        for cls in CLASS_ORDER
        if cls in present
    ]
    fig.legend(
        handles=handles,
        loc="lower center",
        bbox_to_anchor=(0.5, -0.02),
        ncol=ncol,
        frameon=False,
        handletextpad=0.4,
        columnspacing=1.2,
        fontsize=8,
    )


def fig_pca_per_dataset(dedup: pd.DataFrame) -> Path:
    info("PCA: fitting on deduped non-sounds frame")
    X = StandardScaler().fit_transform(dedup[METRIC_COLUMNS])
    pca = PCA(n_components=2, random_state=0)
    pcs = pca.fit_transform(X)

    plot_df = dedup.copy()
    plot_df["PC1"] = pcs[:, 0]
    plot_df["PC2"] = pcs[:, 1]

    panels = [
        (key, plot_df[plot_df["dataset"] == key])
        for key in DATASET_ORDER
        if (plot_df["dataset"] == key).any()
    ]

    n = len(panels)
    fig, axes = plt.subplots(
        1, n, figsize=(9.0, 2.7), sharex=True, sharey=True
    )
    if n == 1:
        axes = np.array([axes])
    for ax, (key, sub) in zip(axes, panels):
        sns.scatterplot(
            data=sub,
            x="PC1",
            y="PC2",
            hue="class",
            hue_order=CLASS_ORDER,
            palette=CLASS_PALETTE,
            s=7,
            alpha=0.7,
            linewidth=0,
            ax=ax,
            legend=False,
        )
        title = f"{DATASET_LABELS[key]}  (N={len(sub):,})"
        style_panel_axes(ax, title)
        ax.set_xlabel("PC1", fontsize=8)
    axes[0].set_ylabel("PC2", fontsize=8)

    ev = pca.explained_variance_ratio_
    fig.suptitle(
        f"PCA(2) of feature metric space  -  explained variance "
        f"PC1 {ev[0]:.0%}, PC2 {ev[1]:.0%}",
        fontsize=9.5,
        y=1.0,
    )
    add_class_legend(fig, plot_df["class"].unique().tolist(), ncol=6)
    fig.tight_layout(rect=(0, 0.12, 1, 0.95))

    out = FIGDIR / "fig_pca_per_dataset.pdf"
    save_fig(fig, out)
    return out


def fig_tsne_per_dataset(
    manifest: pd.DataFrame,
    sample_n: int = 2500,
    cache_dir: Path | None = None,
) -> Path:
    if cache_dir is None:
        cache_dir = REPO_ROOT / "output" / "research" / "_cache_paper"
    cache_dir.mkdir(parents=True, exist_ok=True)

    panels = []
    for key in DATASET_ORDER:
        sub_full = manifest[manifest["dataset"] == key]
        if sub_full.empty:
            continue
        sample_size = min(len(sub_full), sample_n)
        sub = sub_full.sample(n=sample_size, random_state=0).copy().reset_index(drop=True)
        cache_path = cache_dir / f"tsne_{key}_n{sample_size}.npy"
        if cache_path.exists():
            info(f"t-SNE: cached {key} (N={sample_size:,}) -> {cache_path.name}")
            coords = np.load(cache_path)
        else:
            Xd = StandardScaler().fit_transform(sub[METRIC_COLUMNS])
            info(f"t-SNE: fitting {key} (N={sample_size:,})")
            coords = TSNE(
                n_components=2,
                init="pca",
                learning_rate="auto",
                perplexity=min(30, max(5, sample_size // 5)),
                random_state=0,
            ).fit_transform(Xd)
            np.save(cache_path, coords)
        sub["TSNE1"] = coords[:, 0]
        sub["TSNE2"] = coords[:, 1]
        panels.append((key, sub, len(sub_full), sample_size))

    n = len(panels)
    fig, axes = plt.subplots(1, n, figsize=(9.0, 2.9))
    if n == 1:
        axes = np.array([axes])
    sample_sizes = sorted({s for _, _, _, s in panels})
    for ax, (key, sub, total_n, _) in zip(axes, panels):
        sns.scatterplot(
            data=sub,
            x="TSNE1",
            y="TSNE2",
            hue="class",
            hue_order=CLASS_ORDER,
            palette=CLASS_PALETTE,
            s=7,
            alpha=0.7,
            linewidth=0,
            ax=ax,
            legend=False,
        )
        title = f"{DATASET_LABELS[key]} (N={total_n:,})"
        style_panel_axes(ax, title)
        ax.set_xlabel("t-SNE-1", fontsize=8)
    axes[0].set_ylabel("t-SNE-2", fontsize=8)

    sample_note = (
        f"sample = {sample_sizes[0]:,} per panel"
        if len(sample_sizes) == 1
        else f"sample up to {max(sample_sizes):,} per panel"
    )
    fig.suptitle(
        f"Per-dataset t-SNE of feature metric space  ({sample_note})",
        fontsize=9.5,
        y=1.0,
    )
    present = sorted({c for _, sub, _, _ in panels for c in sub["class"].unique()})
    add_class_legend(fig, present, ncol=6)
    fig.tight_layout(rect=(0, 0.12, 1, 0.95), w_pad=1.2)

    out = FIGDIR / "fig_tsne_per_dataset.pdf"
    save_fig(fig, out)
    return out


def select_bic_k(
    X: np.ndarray, k_grid: list[int], covariance_type: str
) -> tuple[int, float]:
    best_k, best_bic = k_grid[0], np.inf
    for k in k_grid:
        gmm = GaussianMixture(
            n_components=k,
            covariance_type=covariance_type,
            random_state=0,
            n_init=3,
            max_iter=300,
        ).fit(X)
        bic = gmm.bic(X)
        info(f"  GMM k={k:>2d} ({covariance_type}): BIC={bic:.0f}")
        if bic < best_bic:
            best_bic, best_k = bic, k
    return best_k, best_bic


def fig_gmm_bic(dedup: pd.DataFrame) -> Path:
    info("GMM-BIC: standardizing dedup frame")
    X = StandardScaler().fit_transform(dedup[METRIC_COLUMNS])

    info("GMM-BIC: sweeping full-covariance k=2..14")
    k_star, _ = select_bic_k(X, list(range(2, 15)), "full")
    info(f"GMM-BIC: selected k*={k_star} (full covariance)")

    gmm_star = GaussianMixture(
        n_components=k_star,
        covariance_type="full",
        random_state=0,
        n_init=5,
        max_iter=400,
    ).fit(X)
    components = gmm_star.predict(X)
    ari = adjusted_rand_score(dedup["class"], components)

    info("UMAP: 2-D embedding of standardized dedup")
    umap_xy = umap.UMAP(
        n_components=2,
        n_neighbors=30,
        min_dist=0.1,
        metric="euclidean",
        random_state=0,
    ).fit_transform(X)

    present_classes = [c for c in CLASS_ORDER if c in dedup["class"].unique()]
    contingency = pd.crosstab(
        pd.Series(components, name=f"gmm_k{k_star}"),
        dedup["class"].astype(str),
    ).reindex(columns=present_classes, fill_value=0)
    contingency = contingency.sort_values(
        by=present_classes, ascending=False, kind="mergesort"
    )
    contingency_norm = contingency.div(contingency.sum(axis=1), axis=0)

    fig, axes = plt.subplots(
        1, 2, figsize=(11.0, 3.2),
        gridspec_kw={"width_ratios": [1.35, 1.0], "wspace": 0.28},
    )

    sns.heatmap(
        contingency_norm,
        annot=contingency.values,
        fmt="d",
        cmap="Greens",
        cbar_kws={"shrink": 0.82, "pad": 0.015, "aspect": 18},
        ax=axes[0],
        annot_kws={"size": 6.0},
        linewidths=0.25,
        linecolor="white",
    )
    axes[0].set_xlabel("rule label", fontsize=8.5)
    axes[0].set_ylabel(f"GMM component (k*={k_star})", fontsize=8.5)
    axes[0].set_title(
        f"GMM components vs rule labels  (ARI={ari:.3f})",
        fontsize=9.0,
        pad=4,
    )
    axes[0].set_xticklabels(
        axes[0].get_xticklabels(), rotation=30, ha="right", fontsize=7.0
    )
    axes[0].set_yticklabels(
        axes[0].get_yticklabels(), rotation=0, fontsize=6.5
    )
    cbar = axes[0].collections[0].colorbar
    if cbar is not None:
        cbar.ax.tick_params(labelsize=6.5)
        cbar.set_label("row-normalized share", fontsize=7.5)

    palette_components = sns.color_palette("tab20", n_colors=k_star)
    scatter_df = dedup.copy()
    scatter_df["UMAP1"] = umap_xy[:, 0]
    scatter_df["UMAP2"] = umap_xy[:, 1]
    scatter_df["component"] = components

    for comp_idx in range(k_star):
        sub = scatter_df[scatter_df["component"] == comp_idx]
        if sub.empty:
            continue
        axes[1].scatter(
            sub["UMAP1"],
            sub["UMAP2"],
            s=10,
            alpha=0.65,
            linewidth=0,
            color=palette_components[comp_idx],
            label=f"c{comp_idx}",
        )
    axes[1].set_xlabel("UMAP-1", fontsize=8.5)
    axes[1].set_ylabel("UMAP-2", fontsize=8.5)
    axes[1].set_title(
        f"GMM components (k*={k_star}) on UMAP", fontsize=9.0, pad=4
    )
    axes[1].tick_params(axis="both", which="both", labelsize=7.0)
    axes[1].grid(True, linewidth=0.4, alpha=0.6)
    for spine in ("top", "right"):
        axes[1].spines[spine].set_visible(False)
    axes[1].margins(x=0.02, y=0.02)

    fig.suptitle(
        "BIC-preferred Gaussian mixture",
        fontsize=9.5,
        y=1.0,
    )
    fig.tight_layout(rect=(0, 0, 1, 0.94))

    out = FIGDIR / "fig_gmm_bic.pdf"
    save_fig(fig, out)
    return out


def main(argv: list[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--only",
        choices=["pca", "tsne", "gmm", "all"],
        default="all",
        help="Render only the named figure (default: all).",
    )
    args = parser.parse_args(argv)

    if not MANIFEST.exists():
        print(f"ERROR: manifest not found at {MANIFEST}", file=sys.stderr)
        return 1

    plt.rcParams.update(PAPER_RC)
    sns.set_theme(style="whitegrid", rc=PAPER_RC)

    manifest, dedup = build_frames()

    if args.only in ("pca", "all"):
        fig_pca_per_dataset(dedup)
    if args.only in ("tsne", "all"):
        fig_tsne_per_dataset(manifest)
    if args.only in ("gmm", "all"):
        fig_gmm_bic(dedup)

    info("done")
    return 0


_T0 = time.perf_counter()


if __name__ == "__main__":
    raise SystemExit(main())
