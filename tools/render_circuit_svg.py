"""
Offline renderer for tutorial-style circuit SVGs (boxes-and-arrows + activation %).

Produces the same kind of diagram shown in
https://github.com/decoderesearch/circuit-tracer/blob/main/demos/circuit_tracing_tutorial.ipynb
but reads everything from an already-generated ``graph.json`` file under
``output/.../00 Graph Generation/`` -- no GPU, no transcoder load, no live
``ReplacementModel``. The trade-off is that activation percentages are taken
from the JSON's per-node ``activation`` field (the baseline activation under
the original prompt); intervention scenarios must be expressed by overriding
``SupernodeSpec.activation`` / ``intervention``.

Usage (programmatic):

    from tools.render_circuit_svg import SupernodeSpec, render_offline
    svg = render_offline(
        graph_path="output/usa_states_batch/california_Oakland/00 Graph Generation/graph.json",
        supernodes=[
            SupernodeSpec(name="Emb: Oakland",  features=None, children=["California"]),
            SupernodeSpec(name="California",    features=[(0, 7, 32742)], children=["Say Sacramento"]),
            SupernodeSpec(name="Say Sacramento", features=[(20, 8, 12345)]),
        ],
        rows=[["Emb: Oakland"], ["California"], ["Say Sacramento"]],
        output_svg_path="output/usa_states_batch/california_Oakland/circuit.svg",
    )
"""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable

# Make the vendored upstream module importable regardless of how this file is
# invoked (CLI, pytest, or "python -m tools.render_circuit_svg").
_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from graph_visualization import (  # noqa: E402  (sys.path manipulation above)
    InterventionGraph,
    Supernode,
    create_graph_visualization,
)


FeatureTriple = tuple[int, int, int]  # (layer, pos, feature_idx)


@dataclass
class SupernodeSpec:
    """User-facing description of one supernode in the circuit diagram.

    Attributes:
        name: Display label inside the box.
        features: List of (layer, pos, feature_idx). ``None`` marks an
            embedding/abstract node with no underlying features (no % label).
        children: Names of supernodes this one points to (causal arrow target).
        activation: Optional override (0.0 - 1.0). If ``None`` and ``features``
            is non-empty, defaults to 1.0 (= 100 %, baseline).
        intervention: Optional badge text such as ``"-2x"``, ``"+3x"``.
        replacement: Optional name of the supernode that replaces this one in
            an intervention scenario (rendered as the orange/cream box).
    """

    name: str
    features: list[FeatureTriple] | None = None
    children: list[str] = field(default_factory=list)
    activation: float | None = None
    intervention: str | None = None
    replacement: str | None = None


def _logit_text_from_clerp(clerp: str) -> str:
    """Parse the token from a logit node's clerp field.

    ``graph.json`` logit nodes store ``clerp`` as e.g. ``'Output " Sacramento" (p=0.277)'``.
    Returns ``" Sacramento"`` (preserving the leading space, like the tutorial).
    """
    m = re.match(r'Output\s+"(.*)"\s+\(p=', clerp or "")
    return m.group(1) if m else (clerp or "")


def _top_outputs_from_graph(graph: dict, k: int = 5) -> list[tuple[str, float]]:
    """Read top-k logit nodes from a graph.json dict, sorted by token_prob desc."""
    logits = [n for n in graph.get("nodes", []) if n.get("feature_type") == "logit"]
    logits.sort(key=lambda n: n.get("token_prob", 0.0), reverse=True)
    return [
        (_logit_text_from_clerp(n.get("clerp", "")), float(n.get("token_prob", 0.0)))
        for n in logits[:k]
    ]


def _build_supernode_objects(
    specs: list[SupernodeSpec],
) -> dict[str, Supernode]:
    """Materialise Supernode objects with cross-references resolved by name."""
    by_name: dict[str, Supernode] = {}
    for spec in specs:
        node = Supernode(
            name=spec.name,
            features=spec.features,  # type: ignore[arg-type]  (renderer only checks truthiness)
            children=[],  # filled below
            intervention=spec.intervention,
            replacement_node=None,  # filled below
        )
        if spec.activation is not None:
            node.activation = float(spec.activation)
        elif spec.features:
            # Baseline: feature-bearing node defaults to 100% (unperturbed).
            node.activation = 1.0
        else:
            node.activation = None
        by_name[spec.name] = node

    for spec in specs:
        node = by_name[spec.name]
        node.children = [by_name[c] for c in spec.children if c in by_name]
        if spec.replacement and spec.replacement in by_name:
            node.replacement_node = by_name[spec.replacement]
    return by_name


def render_offline(
    graph_path: str | Path,
    supernodes: list[SupernodeSpec],
    rows: list[list[str]],
    *,
    output_svg_path: str | Path | None = None,
    top_outputs: list[tuple[str, float]] | None = None,
    top_k: int = 5,
    prompt_override: str | None = None,
    compact: bool = False,
) -> str:
    """Render a circuit SVG offline from an existing graph.json.

    Args:
        graph_path: Path to ``00 Graph Generation/graph.json``.
        supernodes: Supernode specs (display name + feature triples + edges).
        rows: Layout from bottom to top, e.g. ``[["Emb: X"], ["mid"], ["top"]]``.
            Each entry is a supernode name; row 0 is drawn at the bottom.
        output_svg_path: If provided, the SVG string is written to this path.
        top_outputs: Override list of ``(token, probability)`` to display.
            If ``None``, the top-``top_k`` logits from the graph are used.
        top_k: How many logit boxes to show when reading from the graph.
        prompt_override: Override the prompt text shown at the bottom.
        compact: If ``True``, render the diagram with the portrait-oriented,
            horizontally compact layout that mirrors Anthropic's published
            Dallas->Austin figure (multi-line boxes, 3x2 top-outputs grid).
            If ``False`` (default), use the upstream landscape layout.

    Returns:
        The raw SVG string.
    """
    graph_path = Path(graph_path)
    with graph_path.open("r", encoding="utf-8") as f:
        graph = json.load(f)

    nodes_by_name = _build_supernode_objects(supernodes)
    missing = [name for row in rows for name in row if name not in nodes_by_name]
    if missing:
        raise ValueError(f"rows references unknown supernode names: {missing}")

    ordered_nodes = [[nodes_by_name[name] for name in row] for row in rows]

    prompt = prompt_override or graph.get("metadata", {}).get("prompt", "")
    intervention_graph = InterventionGraph(ordered_nodes=ordered_nodes, prompt=prompt)
    # Register all nodes (renderer iterates `ordered_nodes`, but we keep the
    # `nodes` dict populated for parity with the upstream tutorial flow).
    for node in nodes_by_name.values():
        intervention_graph.nodes[node.name] = node

    if top_outputs is None:
        top_outputs = _top_outputs_from_graph(graph, k=top_k)

    if compact:
        from circuit_svg_compact import create_compact_visualization
        svg_obj = create_compact_visualization(intervention_graph, top_outputs)
    else:
        svg_obj = create_graph_visualization(intervention_graph, top_outputs)
    svg_str = svg_obj.data  # IPython.display.SVG holds the raw markup on .data

    if output_svg_path is not None:
        out = Path(output_svg_path)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(svg_str, encoding="utf-8")

    return svg_str


# -------------------------------------------------------------------------
# Helpers for working with the existing repo's graph.json + node_grouping.csv
# -------------------------------------------------------------------------


def features_for_supernode(
    state_dir: str | Path,
    supernode_name: str,
    *,
    grouping_csv: str | Path | None = None,
    graph_json: str | Path | None = None,
) -> list[FeatureTriple]:
    """Resolve all (layer, pos, feature_idx) triples for one supernode label.

    Reads ``02 Node Grouping/node_grouping.csv`` for the (layer, feature) ->
    supernode_name mapping, then joins with ``00 Graph Generation/graph.json``
    to recover the position (ctx_idx) of each feature node.
    """
    state_dir = Path(state_dir)
    grouping_csv = Path(grouping_csv) if grouping_csv else state_dir / "02 Node Grouping" / "node_grouping.csv"
    graph_json = Path(graph_json) if graph_json else state_dir / "00 Graph Generation" / "graph.json"

    import csv

    layer_feat_pairs: set[tuple[int, int]] = set()
    with grouping_csv.open("r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("supernode_name", "").strip() == supernode_name:
                try:
                    layer_feat_pairs.add((int(row["layer"]), int(row["feature"])))
                except (KeyError, ValueError):
                    continue
    if not layer_feat_pairs:
        return []

    triples: list[FeatureTriple] = []
    with graph_json.open("r", encoding="utf-8") as f:
        graph = json.load(f)
    for n in graph.get("nodes", []):
        if n.get("feature_type") != "cross layer transcoder":
            continue
        nid = n.get("node_id", "")
        parts = nid.split("_")
        if len(parts) != 3:
            continue
        try:
            layer, feat_idx, pos = int(parts[0]), int(parts[1]), int(parts[2])
        except ValueError:
            continue
        if (layer, feat_idx) in layer_feat_pairs:
            triples.append((layer, pos, feat_idx))
    return triples


def _coerce_iterable_features(value: Iterable[FeatureTriple] | None) -> list[FeatureTriple] | None:
    if value is None:
        return None
    return [tuple(map(int, t)) for t in value]  # type: ignore[return-value]
