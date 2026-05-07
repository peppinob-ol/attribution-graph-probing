"""
Layout v2: prompt + before/after prediction strip on top, smaller graph in
the middle, and a per-position trajectory plot at the bottom.

Mirrors the published Anthropic layout that puts ``PROMPT |
ORIGINAL PREDICTION | AFTER INTERVENTION`` headers above the boxes-and-arrows
diagram. The bottom plot reuses the position-axis trajectory panel from
``circuit_svg_strip`` so both layouts share the exact same curve renderer
(source/target probability per generated token, with an ``unsteered <-> steered``
divider) -- only the surrounding chrome differs.

Reuses the graph-area layout from ``circuit_svg_compact`` (positions, label
wrapping, layered z-order) and the trajectory plot from
``circuit_svg_strip``.
"""

from __future__ import annotations

import html
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from circuit_svg_compact import (  # noqa: E402  (sys.path manipulation above)
    NODE_H,
    NODE_W,
    REPL_DX,
    REPL_DY,
    _build_connections,
    _connection_svg,
    _node_box_svg_layered,
)
from circuit_svg_strip import (  # noqa: E402
    TrajectoryPlot,
    _plot_panel_svg,
)
from graph_visualization import InterventionGraph  # noqa: E402  (vendored)
from IPython.display import SVG  # noqa: E402


# --------------------------------------------------------------------------- #
# Layout constants                                                            #
# --------------------------------------------------------------------------- #


CANVAS_W = 480
CANVAS_H = 820
PAD = 20

# Top header strip (PROMPT | ORIGINAL PRED | AFTER INTERVENTION)
HEADER_TOP = 24
HEADER_H = 100
HEADER_PROMPT_W = 200
HEADER_PRED_W = 110

# Graph region: extra vertical room so the topmost replacement boxes don't
# bleed up into the "GRAPH & INTERVENTIONS" title text above them.
GRAPH_TOP = HEADER_TOP + HEADER_H + 8
GRAPH_H = 400
GRAPH_TOP_ROW_OFFSET = 96  # top_y = GRAPH_TOP + GRAPH_TOP_ROW_OFFSET

# Trajectory plot region (rendered via circuit_svg_strip._plot_panel_svg).
PLOT_TOP = GRAPH_TOP + GRAPH_H + 16
PLOT_H = 240

ACCENT = "#D2691E"


# --------------------------------------------------------------------------- #
# Top strip                                                                   #
# --------------------------------------------------------------------------- #


def _top_strip_svg(prompt: str, original_pred: tuple[str, float], after_pred: tuple[str, float]) -> str:
    """Three-cell strip: PROMPT, ORIGINAL PREDICTION, AFTER INTERVENTION."""
    parts: list[str] = []

    # Prompt cell (no border, monospace text wrapped to 2 lines).
    px = PAD + 8
    py = HEADER_TOP
    parts.append(
        f'<text x="{px}" y="{py + 12}" fill="#666" font-family="Arial, sans-serif" '
        f'font-size="11" font-weight="bold" letter-spacing="1.2px">PROMPT</text>'
    )
    lines = _wrap_prompt(prompt, max_chars=22)
    for i, line in enumerate(lines[:3]):
        parts.append(
            f'<text x="{px}" y="{py + 36 + i * 16}" fill="#222" '
            f'font-family="Menlo, Consolas, monospace" font-size="12">'
            f'{html.escape(line)}</text>'
        )

    # Original prediction cell (grey-ish box).
    ox = PAD + HEADER_PROMPT_W + 4
    oy = HEADER_TOP
    parts.append(
        f'<text x="{ox + 8}" y="{oy + 12}" fill="#666" font-family="Arial, sans-serif" '
        f'font-size="9.5" font-weight="bold" letter-spacing="1px">ORIGINAL</text>'
    )
    parts.append(
        f'<text x="{ox + 8}" y="{oy + 24}" fill="#666" font-family="Arial, sans-serif" '
        f'font-size="9.5" font-weight="bold" letter-spacing="1px">PREDICTION</text>'
    )
    parts.extend(
        _prediction_box(
            ox + 4, oy + 36, HEADER_PRED_W - 8, 50, original_pred,
            fill="#ececec", stroke="#a4a4a4", text_color="#2a2a2a",
        )
    )

    # After-intervention cell (orange-ringed box).
    ax = ox + HEADER_PRED_W + 4
    ay = HEADER_TOP
    parts.append(
        f'<text x="{ax + 8}" y="{ay + 12}" fill="#666" font-family="Arial, sans-serif" '
        f'font-size="9.5" font-weight="bold" letter-spacing="1px">AFTER</text>'
    )
    parts.append(
        f'<text x="{ax + 8}" y="{ay + 24}" fill="#666" font-family="Arial, sans-serif" '
        f'font-size="9.5" font-weight="bold" letter-spacing="1px">INTERVENTION</text>'
    )
    parts.extend(
        _prediction_box(
            ax + 4, ay + 36, HEADER_PRED_W - 8, 50, after_pred,
            fill="#FFF8DC", stroke=ACCENT, text_color="#3a2a18",
        )
    )

    # Divider below the header.
    div_y = HEADER_TOP + HEADER_H - 4
    parts.append(
        f'<line x1="{PAD}" y1="{div_y}" x2="{CANVAS_W - PAD}" y2="{div_y}" '
        f'stroke="#e0e0e0" stroke-width="1"/>'
    )
    return "\n".join(parts)


def _prediction_box(x: float, y: float, w: float, h: float, pred: tuple[str, float],
                    *, fill: str, stroke: str, text_color: str) -> list[str]:
    """Pill-shaped box with a token (monospace) and its probability percent."""
    token, prob = pred
    parts = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.5" rx="10"/>'
    ]
    display = token if token.strip() else "(empty)"
    parts.append(
        f'<text x="{x + w / 2:.1f}" y="{y + 22:.1f}" text-anchor="middle" '
        f'fill="{text_color}" font-family="Menlo, Consolas, monospace" '
        f'font-size="14" font-weight="bold">{html.escape(display.strip())}</text>'
    )
    pct = f"{prob * 100:.1f}%" if prob < 0.1 else f"{round(prob * 100)}%"
    parts.append(
        f'<text x="{x + w / 2:.1f}" y="{y + 40:.1f}" text-anchor="middle" '
        f'fill="#666" font-family="Arial, sans-serif" font-size="10">{pct}</text>'
    )
    return parts


def _wrap_prompt(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    words = text.split()
    lines: list[str] = []
    cur = ""
    for w in words:
        candidate = (cur + " " + w).strip() if cur else w
        if len(candidate) <= max_chars:
            cur = candidate
        else:
            if cur:
                lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


# --------------------------------------------------------------------------- #
# Graph (re-uses circuit_svg_compact helpers)                                 #
# --------------------------------------------------------------------------- #


def _graph_positions(intervention_graph: InterventionGraph) -> dict[str, dict]:
    """Same logic as circuit_svg_compact._calc_positions but with a custom y-band."""
    nodes = intervention_graph.ordered_nodes
    out: dict[str, dict] = {}
    if not nodes:
        return out
    bottom_y = GRAPH_TOP + GRAPH_H - NODE_H - 10
    top_y = GRAPH_TOP + GRAPH_TOP_ROW_OFFSET
    n_rows = len(nodes)
    step = (bottom_y - top_y) / (n_rows - 1) if n_rows > 1 else 0
    for row_idx, row in enumerate(nodes):
        row_y = bottom_y - row_idx * step
        row_w = len(row) * NODE_W + (len(row) - 1) * 22
        start_x = (CANVAS_W - row_w) / 2
        for col_idx, node in enumerate(row):
            node_x = start_x + col_idx * (NODE_W + 22)
            out[node.name] = {"x": node_x, "y": row_y, "node": node}
    all_nodes: list = []
    for row in nodes:
        for n in row:
            all_nodes.append(n)
            if n.replacement_node:
                all_nodes.append(n.replacement_node)
    for n in all_nodes:
        if n.replacement_node and n.replacement_node.name not in out:
            origin = out.get(n.name)
            if origin is None:
                continue
            out[n.replacement_node.name] = {
                "x": origin["x"] + REPL_DX,
                "y": origin["y"] - REPL_DY,
                "node": n.replacement_node,
            }
    return out


def _graph_section_svg(intervention_graph: InterventionGraph) -> str:
    title_y = GRAPH_TOP + 14
    title = (
        f'<text x="{PAD + 6}" y="{title_y}" fill="#666" font-family="Arial, sans-serif" '
        f'font-size="9" font-weight="bold" letter-spacing="1.1px">'
        f'GRAPH &amp; INTERVENTIONS</text>'
    )
    node_data = _graph_positions(intervention_graph)
    connections = _build_connections(intervention_graph.ordered_nodes)
    arrows = _connection_svg(node_data, connections)
    boxes_back, boxes_front = _node_box_svg_layered(node_data)
    return f"{title}\n{boxes_back}\n{arrows}\n{boxes_front}"


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #


def create_v2_visualization(
    intervention_graph: InterventionGraph,
    *,
    prompt: str,
    original_pred: tuple[str, float],
    after_pred: tuple[str, float],
    trajectory: TrajectoryPlot,
) -> SVG:
    top = _top_strip_svg(prompt, original_pred, after_pred)
    graph = _graph_section_svg(intervention_graph)
    plot = _plot_panel_svg(
        trajectory,
        x=PAD,
        y=PLOT_TOP,
        w=CANVAS_W - 2 * PAD,
        h=PLOT_H,
    )

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" viewBox="0 0 {CANVAS_W} {CANVAS_H}">
  <rect width="{CANVAS_W}" height="{CANVAS_H}" fill="#f7f7f7"/>
  <rect x="{PAD - 5}" y="{PAD - 5}" width="{CANVAS_W - 2 * (PAD - 5)}" height="{CANVAS_H - 2 * (PAD - 5)}" fill="#ffffff" rx="14"/>

  {top}

  {graph}

  {plot}
</svg>"""
    return SVG(svg)
