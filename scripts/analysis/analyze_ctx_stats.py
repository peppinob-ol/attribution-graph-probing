import json
from pathlib import Path
from typing import Dict, Any

import numpy as np
import pandas as pd


def load_graph(path: Path) -> Dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        return json.load(f)


def is_feature_node_id(node_id: str) -> bool:
    # Feature nodes look like: "1_12928_2" (layer_feature_ctx)
    return len(node_id) > 0 and node_id[0].isdigit() and ("_" in node_id)


def build_feature_frames(data: Dict[str, Any]) -> pd.DataFrame:
    nodes = pd.DataFrame(data["nodes"])  # columns include node_id, ctx_idx, influence, activation
    feature_mask = nodes["node_id"].astype(str).str[0].str.isdigit() & nodes["node_id"].astype(str).str.contains("_")
    feat_nodes = nodes.loc[feature_mask].copy()
    feat_nodes["feature_key"] = feat_nodes["node_id"].str.rsplit("_", n=1).str[0]
    return feat_nodes


def compute_cov(feat_nodes: pd.DataFrame) -> pd.DataFrame:
    cov = (
        feat_nodes.groupby("feature_key")["ctx_idx"].nunique().rename("n_ctx").reset_index()
    )
    return cov


def compute_feature_stats(feat_nodes: pd.DataFrame) -> pd.DataFrame:
    per_feat = (
        feat_nodes.groupby("feature_key").agg(
            mean_influence=("influence", "mean"),
            median_influence=("influence", "median"),
            mean_activation=("activation", "mean"),
            median_activation=("activation", "median"),
            n_nodes=("node_id", "count"),
        )
    ).reset_index()
    return per_feat


def compute_correlations(per_feat_with_cov: pd.DataFrame) -> Dict[str, float]:
    out: Dict[str, float] = {}
    df = per_feat_with_cov.dropna(subset=["n_ctx", "mean_influence", "mean_activation"]).copy()
    if len(df) == 0:
        return out
    out["pearson_nctx_mean_influence"] = float(df["n_ctx"].corr(df["mean_influence"], method="pearson"))
    out["spearman_nctx_mean_influence"] = float(df["n_ctx"].corr(df["mean_influence"], method="spearman"))
    out["pearson_nctx_mean_activation"] = float(df["n_ctx"].corr(df["mean_activation"], method="pearson"))
    out["spearman_nctx_mean_activation"] = float(df["n_ctx"].corr(df["mean_activation"], method="spearman"))
    out["pearson_mean_act_mean_infl"] = float(df["mean_activation"].corr(df["mean_influence"], method="pearson"))
    out["spearman_mean_act_mean_infl"] = float(df["mean_activation"].corr(df["mean_influence"], method="spearman"))
    return out


def per_ctx_stats(feat_nodes: pd.DataFrame) -> pd.DataFrame:
    by_ctx = (
        feat_nodes.groupby("ctx_idx").agg(
            mean_influence=("influence", "mean"),
            median_influence=("influence", "median"),
            mean_activation=("activation", "mean"),
            median_activation=("activation", "median"),
            n_nodes=("node_id", "count"),
        )
    ).reset_index().sort_values("ctx_idx")
    return by_ctx


def group_compare(feat_nodes: pd.DataFrame, cov: pd.DataFrame) -> Dict[str, Any]:
    merged = feat_nodes.merge(cov, on="feature_key", how="left")
    g1 = merged[merged["n_ctx"] == 1]
    g2 = merged[merged["n_ctx"] >= 5]
    def stats(x: pd.Series) -> Dict[str, float]:
        return {
            "mean": float(np.mean(x)) if len(x) else float("nan"),
            "median": float(np.median(x)) if len(x) else float("nan"),
            "std": float(np.std(x, ddof=1)) if len(x) > 1 else float("nan"),
            "n": int(len(x))
        }
    res = {
        "influence_nctx1": stats(g1["influence"]),
        "influence_nctx_ge5": stats(g2["influence"]),
        "activation_nctx1": stats(g1["activation"]),
        "activation_nctx_ge5": stats(g2["activation"]),
    }
    return res


def embedding_inflow_stats(data: Dict[str, Any], feat_nodes: pd.DataFrame) -> Dict[str, Any]:
    links = pd.DataFrame(data["links"])  # columns: source, target, weight
    links = links.dropna(subset=["source", "target"]).copy()
    # Consider target feature nodes only
    links["is_target_feature"] = links["target"].astype(str).str[0].str.isdigit()
    feat_links = links[links["is_target_feature"]].copy()
    feat_links["feature_key"] = feat_links["target"].str.rsplit("_", n=1).str[0]
    # Identify embedding sources
    feat_links["is_embedding_src"] = feat_links["source"].astype(str).str.startswith("E_")

    # Aggregate abs weight shares per feature
    feat_links["abs_w"] = feat_links["weight"].abs()
    by_feat_total = feat_links.groupby("feature_key")["abs_w"].sum().rename("total_abs_w")
    by_feat_embed = feat_links[feat_links["is_embedding_src"].fillna(False)].groupby("feature_key")["abs_w"].sum().rename("embed_abs_w")
    combined = pd.concat([by_feat_total, by_feat_embed], axis=1).fillna(0.0)
    combined["embed_share"] = np.where(combined["total_abs_w"] > 0, combined["embed_abs_w"] / combined["total_abs_w"], np.nan)

    # Focus on features with n_ctx >= 7 if available
    cov = compute_cov(feat_nodes)
    f7 = cov[cov["n_ctx"] >= 7]["feature_key"].tolist()
    f1 = cov[cov["n_ctx"] == 1]["feature_key"].tolist()

    def safe_mean(x: pd.Series) -> float:
        x = x.dropna()
        return float(x.mean()) if len(x) else float("nan")

    out = {
        "global_embed_share_mean": safe_mean(combined["embed_share"]),
        "embed_share_mean_nctx1": safe_mean(combined.loc[combined.index.intersection(f1), "embed_share"]),
        "embed_share_mean_nctx7": safe_mean(combined.loc[combined.index.intersection(f7), "embed_share"]),
        "top_features_nctx7": f7,
    }
    return out


def main() -> None:
    graph_path = Path("output/graph_data/clt-hp-the-capital-of-201020250035-20251020-003525.json")
    data = load_graph(graph_path)
    feat_nodes = build_feature_frames(data)

    cov = compute_cov(feat_nodes)
    per_feat = compute_feature_stats(feat_nodes)
    per_feat_with_cov = per_feat.merge(cov, on="feature_key", how="left")
    corr = compute_correlations(per_feat_with_cov)
    ctx_stats = per_ctx_stats(feat_nodes)
    grp = group_compare(feat_nodes, cov)
    inflow = embedding_inflow_stats(data, feat_nodes)

    # Console report
    print("=== Totale feature:", len(cov), "===")
    print("\nDistribuzione n_ctx (numero di contesti per feature):")
    dist = cov["n_ctx"].value_counts().sort_index()
    for k, v in dist.items():
        pct = v / len(cov) * 100.0
        print(f"  {k} ctx_idx: {v} feature ({pct:.1f}%)")

    print("\nCorrelazioni:")
    for k in sorted(corr.keys()):
        print(f"  {k}: {corr[k]:.3f}")

    print("\nStatistiche per ctx_idx (mean/median activation & influence):")
    for _, row in ctx_stats.iterrows():
        print(
            f"  ctx {int(row['ctx_idx'])}: n={int(row['n_nodes'])}  "
            f"mean_act={row['mean_activation']:.3f} median_act={row['median_activation']:.3f}  "
            f"mean_infl={row['mean_influence']:.3f} median_infl={row['median_influence']:.3f}"
        )

    print("\nConfronto gruppi (n_ctx=1 vs n_ctx>=5):")
    for k, stats in grp.items():
        print(f"  {k}: n={stats['n']} mean={stats['mean']:.3f} median={stats['median']:.3f} std={stats['std']}")

    print("\nEmbedding inflow share (abs weight):")
    for k, v in inflow.items():
        if isinstance(v, float):
            print(f"  {k}: {v:.3f}")
        else:
            print(f"  {k}: {v}")

    # Save machine-readable summary
    summary = {
        "n_features": int(len(cov)),
        "n_ctx_distribution": dist.to_dict(),
        "correlations": corr,
        "per_ctx_stats": ctx_stats.to_dict(orient="records"),
        "group_compare": grp,
        "embedding_inflow": inflow,
    }
    out_json = Path("output/ctx_analysis_summary.json")
    with out_json.open("w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)
    print(f"\nSalvato riassunto in: {out_json}")


if __name__ == "__main__":
    main()







