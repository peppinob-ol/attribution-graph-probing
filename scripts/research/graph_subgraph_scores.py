"""Compute Replacement and Completeness scores for full graphs and concept-aligned
subgraphs across all entities in the five probe-prompting datasets.

Formulas follow `circuit_tracer.graph.compute_graph_scores` (Hanna & Piotrowski,
safety-research/circuit-tracer), operating on the pruned Neuronpedia graph JSON
rather than the dense pre-prune adjacency tensor:

  Replacement = I_embed / (I_embed + I_error)
  Completeness = sum_i (1 - error_frac_in(i)) * W(i) / sum_i W(i)

where all influences are computed via power iteration on the row-normalised
|adjacency| with logit-probability weights on the target-logit outputs.

Subgraph variant: unpinned CLT feature nodes are re-labeled as error
(their incoming and outgoing mass now counts toward `error_influence` and
toward `error_frac_in`). Pinned features come from `node_grouping.csv` rows
whose `supernode_name` is non-empty.

Usage:
    python -m scripts.research.graph_subgraph_scores \
        --datasets usa_states_batch book_characters_authors_batch \
                   products_founders_batch paintings_painters_batch \
        --out output/research/graph_subgraph_scores.csv
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.sparse import csr_matrix, eye as sp_eye


FEATURE_TYPE_CLT = "cross layer transcoder"
FEATURE_TYPE_ERROR = "mlp reconstruction error"
FEATURE_TYPE_EMBED = "embedding"
FEATURE_TYPE_LOGIT = "logit"


def build_adjacency(graph_json: dict) -> tuple[csr_matrix, list[str], list[str], np.ndarray]:
    """Return (A, node_ids, types, logit_probs) where A[i, j] = |weight| of edge j -> i."""

    nodes = graph_json["nodes"]
    links = graph_json["links"]

    node_ids: list[str] = [n["node_id"] for n in nodes]
    types: list[str] = [n["feature_type"] for n in nodes]
    id_to_idx = {nid: i for i, nid in enumerate(node_ids)}

    logit_probs = np.zeros(len(nodes), dtype=np.float64)
    for i, n in enumerate(nodes):
        if n["feature_type"] == FEATURE_TYPE_LOGIT:
            logit_probs[i] = float(n.get("token_prob") or 0.0)

    rows, cols, data = [], [], []
    for lk in links:
        src = id_to_idx.get(lk["source"])
        dst = id_to_idx.get(lk["target"])
        if src is None or dst is None:
            continue
        w = abs(float(lk["weight"]))
        if w == 0.0:
            continue
        rows.append(dst)
        cols.append(src)
        data.append(w)

    N = len(nodes)
    A = csr_matrix((data, (rows, cols)), shape=(N, N), dtype=np.float64)
    return A, node_ids, types, logit_probs


def normalise_rows(A: csr_matrix) -> csr_matrix:
    """Row-normalise so each row sums to 1 (rows with no incoming mass stay zero)."""

    row_sums = np.asarray(A.sum(axis=1)).flatten()
    inv = np.zeros_like(row_sums)
    mask = row_sums > 0
    inv[mask] = 1.0 / row_sums[mask]
    D = csr_matrix((inv, (np.arange(len(inv)), np.arange(len(inv)))), shape=A.shape)
    return D @ A


def compute_influence(A_norm: csr_matrix, logit_weights: np.ndarray, max_iter: int = 1000, tol: float = 1e-12) -> np.ndarray:
    """Sum over k>=1 of (logit_weights @ A^k). Matches circuit_tracer.compute_influence."""

    current = logit_weights @ A_norm
    total = current.copy()
    for _ in range(max_iter):
        if not np.any(np.abs(current) > tol):
            break
        current = current @ A_norm
        total = total + current
    else:
        raise RuntimeError("Influence computation did not converge")
    return np.asarray(total).flatten()


def compute_scores(
    A_norm: csr_matrix,
    logit_weights: np.ndarray,
    types: np.ndarray,
    embed_mask: np.ndarray,
    error_mask: np.ndarray,
) -> tuple[float, float]:
    """Replacement and Completeness given a partition of nodes into embed/error."""

    node_influence = compute_influence(A_norm, logit_weights)

    embed_influence = float(node_influence[embed_mask].sum())
    error_influence = float(node_influence[error_mask].sum())
    denom = embed_influence + error_influence
    replacement = float("nan") if denom == 0 else embed_influence / denom

    error_frac_in = np.asarray(A_norm[:, error_mask].sum(axis=1)).flatten()
    non_error_fraction = 1.0 - error_frac_in
    output_influence = node_influence + logit_weights
    total_out = float(output_influence.sum())
    completeness = float("nan") if total_out == 0 else float((non_error_fraction * output_influence).sum()) / total_out

    return replacement, completeness


def subgraph_scores_for_graph(graph_path: Path, pinned_feature_keys: set[str]) -> dict:
    """Full-graph and subgraph Replacement/Completeness for one Neuronpedia graph JSON."""

    graph_json = json.loads(graph_path.read_text())

    A, node_ids, type_list, logit_probs = build_adjacency(graph_json)
    types = np.asarray(type_list)
    N = len(node_ids)

    A_norm = normalise_rows(A)

    embed_mask = types == FEATURE_TYPE_EMBED
    error_mask_full = types == FEATURE_TYPE_ERROR
    feature_mask = types == FEATURE_TYPE_CLT

    full_repl, full_comp = compute_scores(A_norm, logit_probs, types, embed_mask, error_mask_full)

    feature_key_by_idx = {
        i: graph_json["nodes"][i]["node_id"].rsplit("_", 1)[0]
        for i in range(N)
        if feature_mask[i]
    }
    unpinned_feature_mask = np.zeros(N, dtype=bool)
    n_feat_total = 0
    n_feat_pinned = 0
    for i, key in feature_key_by_idx.items():
        n_feat_total += 1
        if key in pinned_feature_keys:
            n_feat_pinned += 1
        else:
            unpinned_feature_mask[i] = True

    sub_error_mask = error_mask_full | unpinned_feature_mask
    sub_repl, sub_comp = compute_scores(A_norm, logit_probs, types, embed_mask, sub_error_mask)

    return {
        "n_nodes": N,
        "n_features": int(feature_mask.sum()),
        "n_error_nodes": int(error_mask_full.sum()),
        "n_embed_nodes": int(embed_mask.sum()),
        "n_logit_nodes": int((types == FEATURE_TYPE_LOGIT).sum()),
        "n_features_pinned": n_feat_pinned,
        "n_features_total": n_feat_total,
        "pinned_fraction": n_feat_pinned / n_feat_total if n_feat_total else 0.0,
        "G_Repl": full_repl,
        "G_Comp": full_comp,
        "S_Repl": sub_repl,
        "S_Comp": sub_comp,
    }


def load_pinned_feature_keys(
    node_grouping_csv: Path,
    selected_features_json: Path | None = None,
    exclude_review: bool = True,
) -> set[str]:
    """Return feature_keys pinned in the concept-aligned subgraph.

    A feature is pinned iff:
      * it appears in `selected_features_with_nodes.json` (cumulative-influence
        selection, tau applied at graph generation time), AND
      * its row in `node_grouping.csv` has a non-empty `supernode_name`, AND
      * (when `exclude_review`) its `review` flag is not True.

    Falls back to just the CSV rule if the JSON is missing.
    """

    feature_keys: set[str] = set()
    if not node_grouping_csv.exists():
        return feature_keys

    cols = ["feature_key", "supernode_name"]
    df = pd.read_csv(node_grouping_csv)
    mask = df["supernode_name"].notna() & (df["supernode_name"].astype(str).str.len() > 0)
    if exclude_review and "review" in df.columns:
        mask &= df["review"].fillna(False).astype(bool) == False
    feature_keys = set(df.loc[mask, "feature_key"].astype(str).unique())

    if selected_features_json is not None and selected_features_json.exists():
        sel = json.loads(selected_features_json.read_text())
        selected_keys = {f"{f['layer']}_{f['index']}" for f in sel.get("features", [])}
        if selected_keys:
            feature_keys &= selected_keys

    return feature_keys


def run_dataset(dataset_dir: Path) -> list[dict]:
    rows: list[dict] = []
    entities = sorted(p for p in dataset_dir.iterdir() if p.is_dir() and not p.name.startswith("_"))
    for entity_dir in entities:
        graph_path = entity_dir / "00 Graph Generation" / "graph.json"
        grouping_csv = entity_dir / "02 Node Grouping" / "node_grouping.csv"
        selected_json = entity_dir / "00 Graph Generation" / "selected_features_with_nodes.json"
        if not graph_path.exists() or not grouping_csv.exists():
            continue
        pinned = load_pinned_feature_keys(grouping_csv, selected_json)
        if not pinned:
            print(f"[skip] {entity_dir.name}: no pinned features", file=sys.stderr)
            continue
        try:
            res = subgraph_scores_for_graph(graph_path, pinned)
        except Exception as exc:
            print(f"[warn] {entity_dir.name}: {exc}", file=sys.stderr)
            continue
        res["dataset"] = dataset_dir.name
        res["entity"] = entity_dir.name
        rows.append(res)
    return rows


def aggregate(rows: Iterable[dict]) -> pd.DataFrame:
    df = pd.DataFrame(list(rows))
    if df.empty:
        return df
    agg = (
        df.groupby("dataset")
          .agg(n_entities=("entity", "count"),
               G_Repl=("G_Repl", "mean"),
               S_Repl=("S_Repl", "mean"),
               G_Comp=("G_Comp", "mean"),
               S_Comp=("S_Comp", "mean"),
               mean_pinned_fraction=("pinned_fraction", "mean"),
               mean_n_features=("n_features", "mean"))
          .reset_index()
    )
    return agg


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--datasets", nargs="+", required=True,
                    help="Dataset directory names under output/, e.g. usa_states_batch")
    ap.add_argument("--output_root", type=Path, default=Path("output"),
                    help="Root containing each <dataset> directory (default: output)")
    ap.add_argument("--out", type=Path, default=Path("output/research/graph_subgraph_scores.csv"),
                    help="Per-entity CSV output path")
    ap.add_argument("--summary_out", type=Path,
                    default=Path("output/research/graph_subgraph_scores_summary.csv"),
                    help="Per-dataset aggregate CSV output path")
    args = ap.parse_args()

    all_rows: list[dict] = []
    for ds in args.datasets:
        ds_dir = args.output_root / ds
        if not ds_dir.exists():
            print(f"[warn] dataset dir missing: {ds_dir}", file=sys.stderr)
            continue
        ds_rows = run_dataset(ds_dir)
        print(f"{ds}: scored {len(ds_rows)} entities")
        all_rows.extend(ds_rows)

    if not all_rows:
        print("no rows produced", file=sys.stderr)
        sys.exit(1)

    df = pd.DataFrame(all_rows)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    col_order = [
        "dataset", "entity",
        "G_Repl", "S_Repl", "G_Comp", "S_Comp",
        "n_nodes", "n_features", "n_error_nodes", "n_embed_nodes", "n_logit_nodes",
        "n_features_pinned", "n_features_total", "pinned_fraction",
    ]
    df = df[col_order]
    df.to_csv(args.out, index=False)
    print(f"wrote {args.out}")

    summary = aggregate(all_rows)
    summary.to_csv(args.summary_out, index=False)
    print(f"wrote {args.summary_out}")
    print("\nPer-dataset summary:")
    with pd.option_context("display.float_format", "{:.3f}".format):
        print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
