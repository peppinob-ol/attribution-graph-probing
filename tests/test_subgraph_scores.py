"""
Tests for ``tools.subgraph_scores``.

Locks in the circuit-tracer formulas on small handcrafted graphs:

- An all-token graph (no errors, no features) must give R = 1, C = 1.
- An all-error graph (no token paths) must give R = 0.
- Pinning all CLT features in compute_subgraph_scores must reproduce
  compute_graph_scores exactly.
- Pinning none must collapse to the "all errors" case (R = 0).
- The Dallas-Austin reference graph exercise the full pipeline on real data.
"""
from __future__ import annotations

import json
import math
from pathlib import Path

import pytest

from tools.subgraph_scores import (
    GraphScores,
    SubgraphScores,
    compute_graph_scores,
    compute_subgraph_scores,
    load_graph,
)


REPO_ROOT = Path(__file__).resolve().parents[1]
DALLAS_GRAPH = REPO_ROOT / "output" / "research" / "dallas_austin_reference" / "gemma-fact-dallas-austin.json"
HUMAN_ANNOT = REPO_ROOT / "output" / "research" / "dallas_austin_reference" / "human_annotated_subgraph.json"


def _toy_graph(nodes, links):
    """Build a minimal valid Neuronpedia-style graph dict."""
    return {"nodes": list(nodes), "links": list(links)}


def _logit(node_id, prob, ctx_idx=1):
    return {
        "node_id": node_id,
        "feature_type": "logit",
        "layer": "27",
        "ctx_idx": ctx_idx,
        "token_prob": prob,
    }


def _embed(node_id, ctx_idx):
    return {
        "node_id": node_id,
        "feature_type": "embedding",
        "layer": "E",
        "ctx_idx": ctx_idx,
    }


def _err(node_id, layer, ctx_idx):
    return {
        "node_id": node_id,
        "feature_type": "mlp reconstruction error",
        "layer": str(layer),
        "ctx_idx": ctx_idx,
        "feature": -1,
    }


def _clt(node_id, layer, ctx_idx):
    return {
        "node_id": node_id,
        "feature_type": "cross layer transcoder",
        "layer": str(layer),
        "ctx_idx": ctx_idx,
        "influence": 0.5,
        "activation": 1.0,
    }


def _link(src, tgt, w):
    return {"source": src, "target": tgt, "weight": w}


# ---------------------------------------------------------------------------
# Trivial-graph identities
# ---------------------------------------------------------------------------

def test_pure_token_to_logit_gives_replacement_one():
    """Single embedding directly feeding a single logit -> R=1, C=1."""
    g = _toy_graph(
        nodes=[_embed("E_1_0", 0), _logit("L_0", 1.0, ctx_idx=0)],
        links=[_link("E_1_0", "L_0", 1.0)],
    )
    out = compute_graph_scores(g)
    assert math.isclose(out.replacement, 1.0, abs_tol=1e-9)
    assert math.isclose(out.completeness, 1.0, abs_tol=1e-9)


def test_pure_error_to_logit_gives_replacement_zero():
    """Single error directly feeding a single logit -> R = 0; C < 1 (the logit
    has 100% error inputs, dragging the completeness average down)."""
    g = _toy_graph(
        nodes=[_err("err_0_0", 0, 0), _logit("L_0", 1.0, ctx_idx=0)],
        links=[_link("err_0_0", "L_0", 1.0)],
    )
    out = compute_graph_scores(g)
    assert math.isclose(out.replacement, 0.0, abs_tol=1e-9)
    assert out.completeness < 1.0 - 1e-9


def test_balanced_token_and_error_gives_half_replacement():
    """Equal-weight token vs error edges into a logit -> R = 0.5."""
    g = _toy_graph(
        nodes=[
            _embed("E_1_0", 0),
            _err("err_0_0", 0, 0),
            _logit("L_0", 1.0, ctx_idx=0),
        ],
        links=[
            _link("E_1_0", "L_0", 1.0),
            _link("err_0_0", "L_0", 1.0),
        ],
    )
    out = compute_graph_scores(g)
    assert math.isclose(out.replacement, 0.5, abs_tol=1e-9)
    # Completeness averages over the three nodes weighted by out_inf;
    # adding an error path can only drag it below the all-token (1.0) case.
    assert out.completeness < 1.0 - 1e-9


def test_feature_chain_propagates_full_replacement():
    """Token -> feature -> logit: replacement should still be 1."""
    g = _toy_graph(
        nodes=[
            _embed("E_1_0", 0),
            _clt("0_42_0", 0, 0),
            _logit("L_0", 1.0, ctx_idx=0),
        ],
        links=[
            _link("E_1_0", "0_42_0", 1.0),
            _link("0_42_0", "L_0", 1.0),
        ],
    )
    out = compute_graph_scores(g)
    assert math.isclose(out.replacement, 1.0, abs_tol=1e-9)
    assert math.isclose(out.completeness, 1.0, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# Subgraph identities
# ---------------------------------------------------------------------------

def test_pinning_all_features_matches_full_graph_scores():
    g = _toy_graph(
        nodes=[
            _embed("E_1_0", 0),
            _clt("0_42_0", 0, 0),
            _err("err_0_0", 0, 0),
            _logit("L_0", 1.0, ctx_idx=0),
        ],
        links=[
            _link("E_1_0", "0_42_0", 1.0),
            _link("0_42_0", "L_0", 1.0),
            _link("err_0_0", "L_0", 0.3),
        ],
    )
    full = compute_graph_scores(g)
    pinned_all = compute_subgraph_scores(g, ["0_42_0"])
    assert math.isclose(full.replacement, pinned_all.replacement, abs_tol=1e-9)
    assert math.isclose(full.completeness, pinned_all.completeness, abs_tol=1e-9)


def test_pinning_none_collapses_features_into_errors():
    """With no features pinned, all CLT influence is folded into errors -> R=0."""
    g = _toy_graph(
        nodes=[
            _embed("E_1_0", 0),
            _clt("0_42_0", 0, 0),
            _err("err_0_0", 0, 0),
            _logit("L_0", 1.0, ctx_idx=0),
        ],
        links=[
            _link("E_1_0", "0_42_0", 1.0),
            _link("0_42_0", "L_0", 1.0),
        ],
    )
    pinned_none = compute_subgraph_scores(g, pinned_node_ids=[])
    assert math.isclose(pinned_none.replacement, 0.0, abs_tol=1e-9)
    assert pinned_none.completeness < 1.0 - 1e-9


def test_subgraph_creates_virtual_error_when_missing():
    """If unpinned feature's (layer, ctx_idx) error node is absent, a virtual one is added."""
    g = _toy_graph(
        nodes=[
            _embed("E_1_0", 0),
            _clt("0_42_0", 0, 0),
            _logit("L_0", 1.0, ctx_idx=0),
        ],
        links=[
            _link("E_1_0", "0_42_0", 1.0),
            _link("0_42_0", "L_0", 1.0),
        ],
    )
    out = compute_subgraph_scores(g, pinned_node_ids=[])
    assert out.n_virtual_errors_added == 1
    assert out.n_pinned_clt == 0
    assert out.n_clt_total == 1
    assert math.isclose(out.replacement, 0.0, abs_tol=1e-9)


# ---------------------------------------------------------------------------
# Real graph: Dallas-Austin
# ---------------------------------------------------------------------------

@pytest.mark.skipif(
    not DALLAS_GRAPH.exists(),
    reason="dallas-austin reference graph not downloaded",
)
def test_dallas_austin_full_graph_scores_in_plausible_range():
    out = compute_graph_scores(load_graph(DALLAS_GRAPH))
    assert 0.0 <= out.replacement <= 1.0
    assert 0.0 <= out.completeness <= 1.0
    assert out.n_features > 0 and out.n_logits > 0


@pytest.mark.skipif(
    not (DALLAS_GRAPH.exists() and HUMAN_ANNOT.exists()),
    reason="dallas-austin reference data not downloaded",
)
def test_dallas_austin_human_subgraph_lower_replacement_than_full():
    """Pinning only the 21 human-curated CLT features must give R <= R_full."""
    graph = load_graph(DALLAS_GRAPH)
    annot = json.loads(HUMAN_ANNOT.read_text())

    pinned = []
    for sn in annot["supernodes"]:
        for m in sn["members"]:
            if m.get("feature_type") == "cross layer transcoder":
                pinned.append(m["node_id"])
    for n in annot["pinned_nodes"]:
        if n.get("feature_type") == "cross layer transcoder":
            pinned.append(n["node_id"])

    full = compute_graph_scores(graph)
    sub = compute_subgraph_scores(graph, pinned)

    assert sub.n_pinned_clt > 0
    assert sub.replacement <= full.replacement + 1e-9
    assert 0.0 <= sub.replacement <= 1.0
    assert 0.0 <= sub.completeness <= 1.0
