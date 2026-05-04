"""
Replacement and completeness scores for Neuronpedia attribution graphs.

Pure-numpy port of ``circuit_tracer.graph.compute_graph_scores`` and
``compute_subgraph_scores`` (PR safety-research/circuit-tracer#42) that
operates directly on a Neuronpedia graph JSON ``{"nodes": [...], "links": [...]}``.
No torch / no Graph .pt file required.

Formulas (verbatim from the upstream library):

    A         = adjacency matrix where A[target, source] = edge_weight
    A_norm    = |A| with each row L1-normalized (clamped at 1e-10)
    inf       = logit_weights @ (A_norm + A_norm^2 + A_norm^3 + ...)
    R         = sum(inf[tokens]) / (sum(inf[tokens]) + sum(inf[errors]))
    out_inf   = inf + logit_weights
    C         = sum_node((1 - frac_error_inputs(node)) * out_inf(node)) / sum(out_inf)

Subgraph variant: every CLT feature whose ``node_id`` is NOT in
``pinned_node_ids`` is folded into the error node at ``(layer, ctx_idx)``
by adding its outgoing edges (column) to the error column and zeroing
its row/column. Missing error nodes (also pruned away) are added as
virtual error rows/columns at the end of the matrix.

Public API
----------

``compute_graph_scores(graph_json) -> GraphScores``
    Replacement and completeness for the graph as stored.

``compute_subgraph_scores(graph_json, pinned_node_ids) -> SubgraphScores``
    Same metrics treating unpinned CLT features as errors.

``load_graph(path)`` / ``compute_graph_scores_from_path(path)`` /
``compute_subgraph_scores_from_path(path, pinned)`` are convenience
helpers that read JSON from disk.

Reference: https://github.com/safety-research/circuit-tracer/pull/42
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Sequence, Tuple

import numpy as np

CLT_TYPE = "cross layer transcoder"
ERROR_TYPE = "mlp reconstruction error"
EMBED_TYPE = "embedding"
LOGIT_TYPE = "logit"

_INFLUENCE_MAX_ITER = 1000
_NORM_CLAMP = 1e-10


@dataclass(frozen=True)
class GraphScores:
    replacement: float
    completeness: float
    n_features: int
    n_errors: int
    n_tokens: int
    n_logits: int
    n_links: int


@dataclass(frozen=True)
class SubgraphScores:
    replacement: float
    completeness: float
    n_pinned_clt: int
    n_clt_total: int
    n_virtual_errors_added: int


# ---------------------------------------------------------------------------
# Adjacency assembly
# ---------------------------------------------------------------------------

def _classify_nodes(graph: Mapping) -> Tuple[List[dict], List[dict], List[dict], List[dict]]:
    """Bucket nodes into [features, errors, embeddings, logits] preserving JSON order."""
    nodes = graph["nodes"]
    features = [n for n in nodes if n.get("feature_type") == CLT_TYPE]
    errors = [n for n in nodes if n.get("feature_type") == ERROR_TYPE]
    embeds = [n for n in nodes if n.get("feature_type") == EMBED_TYPE]
    logits = [n for n in nodes if n.get("feature_type") == LOGIT_TYPE]
    return features, errors, embeds, logits


def _build_adjacency(
    graph: Mapping,
) -> Tuple[np.ndarray, np.ndarray, Dict[str, int], List[dict], Dict[str, int]]:
    """
    Build the adjacency matrix and logit-weight vector from a Neuronpedia
    graph JSON.

    Returns
    -------
    A : (n, n) float64
        ``A[target_idx, source_idx] = edge_weight``.
    logit_weights : (n,) float64
        Probability of each logit token at its index, zero elsewhere.
    node_id_to_idx : dict
        Maps Neuronpedia ``node_id`` strings to row/column indices.
    ordered_nodes : list[dict]
        Nodes in the index order ``[features | errors | embeddings | logits]``.
    slices : dict
        Section sizes/start indices for the four node groups.
    """
    features, errors, embeds, logits = _classify_nodes(graph)
    ordered = features + errors + embeds + logits
    n = len(ordered)

    node_id_to_idx = {node["node_id"]: i for i, node in enumerate(ordered)}

    A = np.zeros((n, n), dtype=np.float64)
    for link in graph.get("links", []):
        si = node_id_to_idx.get(link.get("source"))
        ti = node_id_to_idx.get(link.get("target"))
        if si is None or ti is None:
            continue
        A[ti, si] = float(link.get("weight", 0.0))

    slices = {
        "n_features": len(features),
        "n_errors": len(errors),
        "n_tokens": len(embeds),
        "n_logits": len(logits),
        "feature_start": 0,
        "error_start": len(features),
        "token_start": len(features) + len(errors),
        "logit_start": len(features) + len(errors) + len(embeds),
    }

    logit_weights = np.zeros(n, dtype=np.float64)
    for j, ln in enumerate(logits):
        logit_weights[slices["logit_start"] + j] = float(ln.get("token_prob", 0.0))

    return A, logit_weights, node_id_to_idx, ordered, slices


# ---------------------------------------------------------------------------
# Numerics (mirror of circuit_tracer.graph)
# ---------------------------------------------------------------------------

def _normalize_matrix(A: np.ndarray) -> np.ndarray:
    abs_a = np.abs(A)
    row_sums = abs_a.sum(axis=1, keepdims=True)
    row_sums = np.maximum(row_sums, _NORM_CLAMP)
    return abs_a / row_sums


def _compute_influence(
    A_norm: np.ndarray,
    logit_weights: np.ndarray,
    max_iter: int = _INFLUENCE_MAX_ITER,
) -> np.ndarray:
    current = logit_weights @ A_norm
    influence = current.copy()
    for _ in range(max_iter):
        if not np.any(current):
            return influence
        current = current @ A_norm
        influence = influence + current
    raise RuntimeError(
        f"Influence computation did not converge in {max_iter} iterations"
    )


def _scores_from_arrays(
    A_norm: np.ndarray,
    influence: np.ndarray,
    logit_weights: np.ndarray,
    error_idx_mask: np.ndarray,
    token_start: int,
    logit_start: int,
) -> Tuple[float, float]:
    token_inf = float(influence[token_start:logit_start].sum())
    error_inf = float(influence[error_idx_mask].sum())
    if (token_inf + error_inf) > 0:
        replacement = token_inf / (token_inf + error_inf)
    else:
        replacement = 0.0

    non_error_in_frac = 1.0 - A_norm[:, error_idx_mask].sum(axis=1)
    out_inf = influence + logit_weights
    total_out = float(out_inf.sum())
    if total_out > 0:
        completeness = float((non_error_in_frac * out_inf).sum()) / total_out
    else:
        completeness = 0.0
    return replacement, completeness


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def compute_graph_scores(graph: Mapping) -> GraphScores:
    A, lw, _, _, sl = _build_adjacency(graph)
    A_norm = _normalize_matrix(A)
    influence = _compute_influence(A_norm, lw)

    n = A.shape[0]
    error_mask = np.zeros(n, dtype=bool)
    error_mask[sl["error_start"] : sl["token_start"]] = True

    replacement, completeness = _scores_from_arrays(
        A_norm, influence, lw, error_mask, sl["token_start"], sl["logit_start"]
    )
    return GraphScores(
        replacement=replacement,
        completeness=completeness,
        n_features=sl["n_features"],
        n_errors=sl["n_errors"],
        n_tokens=sl["n_tokens"],
        n_logits=sl["n_logits"],
        n_links=len(graph.get("links", [])),
    )


def compute_subgraph_scores(
    graph: Mapping,
    pinned_node_ids: Iterable[str],
) -> SubgraphScores:
    pinned = set(pinned_node_ids)
    A, lw, _, ordered, sl = _build_adjacency(graph)
    n = A.shape[0]

    err_lookup: Dict[Tuple[int, int], int] = {}
    for i, node in enumerate(ordered):
        if node.get("feature_type") != ERROR_TYPE:
            continue
        try:
            err_lookup[(int(node["layer"]), int(node["ctx_idx"]))] = i
        except (ValueError, TypeError, KeyError):
            continue

    missing_error_keys: List[Tuple[int, int]] = []
    n_clt_total = sl["n_features"]
    n_pinned_clt = 0
    for i, node in enumerate(ordered):
        if node.get("feature_type") != CLT_TYPE:
            continue
        if node["node_id"] in pinned:
            n_pinned_clt += 1
            continue
        try:
            key = (int(node["layer"]), int(node["ctx_idx"]))
        except (ValueError, TypeError, KeyError):
            continue
        if key not in err_lookup and key not in missing_error_keys:
            missing_error_keys.append(key)

    n_virtual = len(missing_error_keys)
    if n_virtual > 0:
        new_n = n + n_virtual
        new_A = np.zeros((new_n, new_n), dtype=np.float64)
        new_A[:n, :n] = A
        new_lw = np.zeros(new_n, dtype=np.float64)
        new_lw[:n] = lw
        for k, key in enumerate(missing_error_keys):
            err_lookup[key] = n + k
        A = new_A
        lw = new_lw
        n = new_n

    extra_error_indices = {err_lookup[k] for k in missing_error_keys}

    for i, node in enumerate(ordered):
        if node.get("feature_type") != CLT_TYPE:
            continue
        if node["node_id"] in pinned:
            continue
        try:
            key = (int(node["layer"]), int(node["ctx_idx"]))
        except (ValueError, TypeError, KeyError):
            continue
        err_idx = err_lookup[key]
        A[:, err_idx] += A[:, i]
        A[i, :] = 0.0
        A[:, i] = 0.0

    A_norm = _normalize_matrix(A)
    influence = _compute_influence(A_norm, lw)

    error_mask = np.zeros(n, dtype=bool)
    error_mask[sl["error_start"] : sl["token_start"]] = True
    for ix in extra_error_indices:
        error_mask[ix] = True

    replacement, completeness = _scores_from_arrays(
        A_norm,
        influence,
        lw,
        error_mask,
        sl["token_start"],
        sl["logit_start"],
    )
    return SubgraphScores(
        replacement=replacement,
        completeness=completeness,
        n_pinned_clt=n_pinned_clt,
        n_clt_total=n_clt_total,
        n_virtual_errors_added=n_virtual,
    )


# ---------------------------------------------------------------------------
# Convenience IO helpers
# ---------------------------------------------------------------------------

def load_graph(path: str | Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def compute_graph_scores_from_path(path: str | Path) -> GraphScores:
    return compute_graph_scores(load_graph(path))


def compute_subgraph_scores_from_path(
    path: str | Path,
    pinned_node_ids: Iterable[str],
) -> SubgraphScores:
    return compute_subgraph_scores(load_graph(path), pinned_node_ids)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _format(scores) -> str:
    if isinstance(scores, GraphScores):
        return (
            f"GraphScores(replacement={scores.replacement:.4f}, "
            f"completeness={scores.completeness:.4f}, "
            f"n_features={scores.n_features}, n_errors={scores.n_errors}, "
            f"n_tokens={scores.n_tokens}, n_logits={scores.n_logits}, "
            f"n_links={scores.n_links})"
        )
    if isinstance(scores, SubgraphScores):
        return (
            f"SubgraphScores(replacement={scores.replacement:.4f}, "
            f"completeness={scores.completeness:.4f}, "
            f"n_pinned_clt={scores.n_pinned_clt}/{scores.n_clt_total}, "
            f"n_virtual_errors_added={scores.n_virtual_errors_added})"
        )
    return repr(scores)


def main(argv: Sequence[str] | None = None) -> int:
    import argparse

    parser = argparse.ArgumentParser(
        description="Compute replacement and completeness scores for a "
        "Neuronpedia attribution-graph JSON."
    )
    parser.add_argument("graph_json", type=Path)
    parser.add_argument(
        "--pinned",
        type=str,
        default=None,
        help="Comma-separated list of pinned node_ids for the subgraph variant. "
        "If omitted, prints scores for the full graph as stored.",
    )
    args = parser.parse_args(argv)

    graph = load_graph(args.graph_json)
    if args.pinned:
        ids = [s.strip() for s in args.pinned.split(",") if s.strip()]
        print(_format(compute_subgraph_scores(graph, ids)))
    else:
        print(_format(compute_graph_scores(graph)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
