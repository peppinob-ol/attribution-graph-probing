"""Regenerate paper/figures/fig_circuit_texas.{svg,png}.

Renders the concept-aligned subgraph for the seed
"<bos>Fact: The capital of the state containing Dallas is" using the eight
supernodes referenced in sections/results.tex (capital, state, Texas, Dallas,
Austin, Say (capital), Say (Texas), Say (Austin)).

Reads the auto-pipeline grouping in
``output/usa_states_fact_batch/texas_dallas/``, resolves each supernode's
(layer, pos, feature_idx) triples from ``02 Node Grouping/node_grouping.csv``
joined with ``00 Graph Generation/graph.json``, and writes both SVG and PNG.

Usage:
    python -m scripts.research.figure_circuit_texas
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.render_circuit_svg import (  # noqa: E402
    SupernodeSpec,
    features_for_supernode,
    render_offline,
)


ENTITY_DIR = REPO_ROOT / "output" / "usa_states_fact_batch" / "texas_dallas"
GRAPH_JSON = ENTITY_DIR / "00 Graph Generation" / "graph.json"
OUT_SVG = REPO_ROOT / "paper" / "figures" / "fig_circuit_texas.svg"
OUT_PNG = REPO_ROOT / "paper" / "figures" / "fig_circuit_texas.png"


SEMANTIC_NAMES = ["capital", "state", "Texas", "Dallas", "Austin"]
SAY_NAMES = ["Say (capital)", "Say (Texas)", "Say (Austin)"]


def _build_specs() -> list[SupernodeSpec]:
    """Build SupernodeSpec list for the eight concept-aligned supernodes plus
    three token-embedding anchors (Dallas, capital, state)."""
    specs: list[SupernodeSpec] = []

    feats: dict[str, list] = {
        name: features_for_supernode(ENTITY_DIR, name)
        for name in SEMANTIC_NAMES + SAY_NAMES
    }
    for name, triples in feats.items():
        if not triples:
            raise RuntimeError(f"no features resolved for supernode {name!r}")

    specs.append(SupernodeSpec(name="Emb: Dallas", features=None, children=["Dallas"]))
    specs.append(SupernodeSpec(name="Emb: state", features=None, children=["state"]))
    specs.append(SupernodeSpec(name="Emb: capital", features=None, children=["capital"]))

    specs.append(
        SupernodeSpec(
            name="Dallas",
            features=feats["Dallas"],
            children=["Texas"],
        )
    )
    specs.append(
        SupernodeSpec(
            name="state",
            features=feats["state"],
            children=["Texas"],
        )
    )
    specs.append(
        SupernodeSpec(
            name="capital",
            features=feats["capital"],
            children=["Say (capital)", "Austin"],
        )
    )

    specs.append(
        SupernodeSpec(
            name="Texas",
            features=feats["Texas"],
            children=["Austin", "Say (Texas)"],
        )
    )

    specs.append(
        SupernodeSpec(
            name="Austin",
            features=feats["Austin"],
            children=["Say (Austin)"],
        )
    )

    specs.append(SupernodeSpec(name="Say (capital)", features=feats["Say (capital)"]))
    specs.append(SupernodeSpec(name="Say (Texas)", features=feats["Say (Texas)"]))
    specs.append(SupernodeSpec(name="Say (Austin)", features=feats["Say (Austin)"]))

    return specs


def _rows() -> list[list[str]]:
    """Bottom-to-top row layout for the compact renderer."""
    return [
        ["Emb: Dallas", "Emb: state", "Emb: capital"],
        ["Dallas", "state", "capital"],
        ["Texas"],
        ["Austin"],
        ["Say (Texas)", "Say (Austin)", "Say (capital)"],
    ]


def _convert_to_png(svg_path: Path, png_path: Path, scale: float = 2.0) -> None:
    import cairosvg

    cairosvg.svg2png(
        url=str(svg_path),
        write_to=str(png_path),
        scale=scale,
    )


def main() -> None:
    if not GRAPH_JSON.exists():
        raise FileNotFoundError(f"graph.json missing: {GRAPH_JSON}")

    specs = _build_specs()
    rows = _rows()

    OUT_SVG.parent.mkdir(parents=True, exist_ok=True)
    render_offline(
        graph_path=GRAPH_JSON,
        supernodes=specs,
        rows=rows,
        output_svg_path=OUT_SVG,
        compact=True,
        top_k=6,
    )
    print(f"wrote {OUT_SVG.relative_to(REPO_ROOT)}")

    _convert_to_png(OUT_SVG, OUT_PNG, scale=2.0)
    print(f"wrote {OUT_PNG.relative_to(REPO_ROOT)}")


if __name__ == "__main__":
    main()
