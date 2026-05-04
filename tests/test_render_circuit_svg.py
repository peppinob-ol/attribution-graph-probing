"""Smoke tests for tools/render_circuit_svg.py.

These tests exercise the offline circuit-SVG renderer end-to-end without
needing a GPU, transcoder weights, or a live ReplacementModel: they construct
a minimal InterventionGraph and an `output/.../graph.json`-backed example,
then verify the SVG contains the expected structural markers.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.render_circuit_svg import (  # noqa: E402  (path setup above)
    SupernodeSpec,
    features_for_supernode,
    render_offline,
)


CALIFORNIA_DIR = REPO_ROOT / "output" / "usa_states_batch" / "california_Oakland"
CALIFORNIA_GRAPH = CALIFORNIA_DIR / "00 Graph Generation" / "graph.json"


@pytest.fixture
def synthetic_graph_json(tmp_path: Path) -> Path:
    """Minimal graph.json mimicking the schema produced by circuit-tracer."""
    data = {
        "metadata": {
            "slug": "synthetic_demo",
            "scan": "fake-scan",
            "transcoder_list": [],
            "prompt_tokens": ["<bos>", "Hello", " world"],
            "prompt": "<bos>Hello world",
            "node_threshold": 0.8,
        },
        "qParams": {
            "pinnedIds": [],
            "supernodes": [],
            "linkType": "both",
            "clickedId": "",
            "sg_pos": "",
        },
        "nodes": [
            {
                "node_id": "5_42_2",
                "feature": 1,
                "layer": "5",
                "ctx_idx": 2,
                "feature_type": "cross layer transcoder",
                "activation": 1.5,
                "clerp": "",
            },
            {
                "node_id": "28_999_2",
                "feature": 999,
                "layer": "28",
                "ctx_idx": 2,
                "feature_type": "logit",
                "token_prob": 0.42,
                "is_target_logit": True,
                "clerp": 'Output " world" (p=0.420)',
            },
            {
                "node_id": "28_111_2",
                "feature": 111,
                "layer": "28",
                "ctx_idx": 2,
                "feature_type": "logit",
                "token_prob": 0.10,
                "is_target_logit": False,
                "clerp": 'Output " other" (p=0.100)',
            },
        ],
        "links": [],
    }
    p = tmp_path / "graph.json"
    p.write_text(json.dumps(data), encoding="utf-8")
    return p


def test_renders_minimal_svg_from_synthetic_graph(synthetic_graph_json, tmp_path):
    """Builds a 3-node circuit (Emb -> Mid -> Out) and writes an SVG."""
    svg = render_offline(
        graph_path=synthetic_graph_json,
        supernodes=[
            SupernodeSpec(name="Emb", features=None, children=["Mid"]),
            SupernodeSpec(
                name="Mid",
                features=[(5, 2, 42)],
                children=["Out"],
                activation=0.85,
            ),
            SupernodeSpec(name="Out", features=[(28, 2, 999)]),
        ],
        rows=[["Emb"], ["Mid"], ["Out"]],
        output_svg_path=tmp_path / "circuit.svg",
    )

    assert svg.startswith("<svg "), "SVG must open with <svg> root tag"
    assert "</svg>" in svg, "SVG must close with </svg>"
    assert "Emb" in svg
    assert "Mid" in svg
    assert "Out" in svg
    # 85% override should appear as a label on Mid
    assert "85%" in svg
    # Default 100% baseline should appear on Out
    assert "100%" in svg
    # Top output read from logit nodes
    assert "world" in svg
    assert (tmp_path / "circuit.svg").is_file()


def test_top_outputs_read_from_graph_json(synthetic_graph_json):
    svg = render_offline(
        graph_path=synthetic_graph_json,
        supernodes=[SupernodeSpec(name="A", features=[(5, 2, 42)])],
        rows=[["A"]],
        top_k=5,
    )
    # token text (with leading space, like the tutorial does it)
    assert "world" in svg and "42%" in svg
    assert "other" in svg and "10%" in svg


def test_top_outputs_override(synthetic_graph_json):
    svg = render_offline(
        graph_path=synthetic_graph_json,
        supernodes=[SupernodeSpec(name="A", features=[(5, 2, 42)])],
        rows=[["A"]],
        top_outputs=[("token_x", 0.9), ("token_y", 0.05)],
    )
    assert "token_x" in svg
    assert "90%" in svg
    assert "token_y" in svg


def test_intervention_and_replacement_render(synthetic_graph_json):
    svg = render_offline(
        graph_path=synthetic_graph_json,
        supernodes=[
            SupernodeSpec(name="orig", features=[(5, 2, 42)], intervention="-2x", replacement="repl"),
            SupernodeSpec(name="repl", features=[(5, 2, 42)], children=["target"]),
            SupernodeSpec(name="target", features=[(28, 2, 999)]),
        ],
        rows=[["orig"], ["target"]],
    )
    # Intervention badge text and replacement node name both end up in the SVG
    assert "-2x" in svg
    assert "repl" in svg


def test_unknown_row_name_raises(synthetic_graph_json):
    with pytest.raises(ValueError, match="unknown supernode names"):
        render_offline(
            graph_path=synthetic_graph_json,
            supernodes=[SupernodeSpec(name="known", features=[(5, 2, 42)])],
            rows=[["known"], ["typo"]],
        )


@pytest.mark.skipif(
    not CALIFORNIA_GRAPH.exists(),
    reason="California graph.json not present; skipping integration smoke",
)
def test_renders_from_california_graph(tmp_path):
    """End-to-end on a real graph.json from this repo's output/."""
    california_features = features_for_supernode(CALIFORNIA_DIR, "California")
    sacramento_features = features_for_supernode(CALIFORNIA_DIR, "Sacramento")

    # Both should be non-empty for the California entry; if the project's
    # node_grouping.csv ever changes labels, fall back to a known feature so
    # the smoke test still demonstrates rendering.
    if not california_features:
        california_features = [(0, 7, 32742)]  # row 6 of the CSV inspected by hand
    if not sacramento_features:
        sacramento_features = california_features

    svg = render_offline(
        graph_path=CALIFORNIA_GRAPH,
        supernodes=[
            SupernodeSpec(name="Emb: Oakland", features=None, children=["California"]),
            SupernodeSpec(
                name="California",
                features=california_features,
                children=["Say Sacramento"],
            ),
            SupernodeSpec(
                name="Say Sacramento",
                features=sacramento_features,
            ),
        ],
        rows=[["Emb: Oakland"], ["California"], ["Say Sacramento"]],
        output_svg_path=tmp_path / "california_circuit.svg",
        top_k=5,
    )

    assert "California" in svg
    assert "Sacramento" in svg
    # Prompt from graph.json should be visible
    assert "Oakland" in svg
    assert (tmp_path / "california_circuit.svg").is_file()
