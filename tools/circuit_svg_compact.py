"""
Compact, portrait-oriented variant of the upstream circuit-tracer SVG renderer.

The upstream ``demos/graph_visualization.py`` produces a 700x400 landscape
canvas with single-line, 100x35 boxes and a single-row top-outputs strip.
This module renders the same logical InterventionGraph in a tighter layout
that mirrors Anthropic's published Dallas->Austin diagram:

- ~480x600 portrait canvas
- 80x46 boxes with two-line wrapped text
- 3-column grid for top outputs
- activation % drawn above-left of each box (no rounded badge)

It only uses the data on ``Supernode`` / ``InterventionGraph`` (name, features,
children, activation, intervention, replacement_node) -- nothing else from
the upstream renderer is required.
"""

from __future__ import annotations

import html
import math
import sys
from pathlib import Path

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from graph_visualization import InterventionGraph, Supernode  # noqa: E402  (vendored)
from IPython.display import SVG  # noqa: E402


# Layout constants, tuned to match the reference image.
CANVAS_W = 480
CANVAS_H = 640
PAD = 20
# GRAPH_TOP leaves ~30px below the card edge so the topmost row's replacement
# badges (which sit ~12px above their box) stay safely inside the white card.
GRAPH_TOP = 50
GRAPH_H = 370  # tall enough that replacements above row N don't crowd row N+1
PROMPT_TOP = GRAPH_TOP + GRAPH_H + 24
TOP_OUTPUTS_TOP = PROMPT_TOP + 90
NODE_W = 80
NODE_H = 46
H_GAP = 22
REPL_DX = 22  # how far right the replacement box sits relative to its original
REPL_DY = 64  # how far above the replacement box sits relative to its original
LINE_COLOR = "#8B4513"
LINE_COLOR_REPL = "#D2691E"
LINE_WIDTH = "2"
LINE_WIDTH_REPL = "3"


# --------------------------------------------------------------------------- #
# Layout                                                                      #
# --------------------------------------------------------------------------- #


def _wrap_label(text: str, max_chars: int = 11) -> list[str]:
    """Wrap a supernode label into at most 2 lines, biased toward natural breaks."""
    if len(text) <= max_chars:
        return [text]

    # Prefer splitting before "(" so "Say (Sacramento)" -> ["Say", "(Sacramento)"]
    if "(" in text:
        head, _, tail = text.partition("(")
        head = head.strip()
        if head and len(head) <= max_chars and len(f"({tail}") <= max_chars + 2:
            return [head, f"({tail}".strip()]

    # Otherwise split on the first space that yields the most balanced lines.
    if " " in text:
        words = text.split(" ")
        # try every break point and pick the one with smallest max(line)
        best, best_score = None, math.inf
        for i in range(1, len(words)):
            a = " ".join(words[:i])
            b = " ".join(words[i:])
            score = max(len(a), len(b))
            if score < best_score:
                best_score = score
                best = (a, b)
        if best:
            return list(best)

    # Last resort: break in the middle.
    mid = len(text) // 2
    return [text[:mid], text[mid:]]


def _calc_positions(nodes: list[list[Supernode]]) -> dict[str, dict]:
    """Return ``{name: {"x": float, "y": float, "node": Supernode}}`` for layout."""
    n_rows = len(nodes)
    if n_rows == 0:
        return {}

    # Distribute rows vertically inside the graph area, bottom -> top.
    out: dict[str, dict] = {}
    bottom_y = GRAPH_TOP + GRAPH_H - NODE_H - 10
    top_y = GRAPH_TOP + 60  # leave room for replacement nodes above the topmost row
    if n_rows > 1:
        step = (bottom_y - top_y) / (n_rows - 1)
    else:
        step = 0

    for row_idx, row in enumerate(nodes):
        row_y = bottom_y - row_idx * step
        row_w = len(row) * NODE_W + (len(row) - 1) * H_GAP
        start_x = (CANVAS_W - row_w) / 2
        for col_idx, node in enumerate(row):
            node_x = start_x + col_idx * (NODE_W + H_GAP)
            out[node.name] = {"x": node_x, "y": row_y, "node": node}

    # Place replacements directly above their original node (offset right and up).
    all_nodes: list[Supernode] = []
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


def _build_connections(nodes: list[list[Supernode]]) -> list[dict]:
    """Mirror upstream build_connections_data: respects replacement_node semantics."""
    all_nodes: set[Supernode] = set()

    def _add(node: Supernode) -> None:
        all_nodes.add(node)
        if node.replacement_node:
            _add(node.replacement_node)
        for child in node.children:
            _add(child)

    for row in nodes:
        for node in row:
            _add(node)

    replacement_names: set[str] = {n.replacement_node.name for n in all_nodes if n.replacement_node}

    connections: list[dict] = []
    for node in all_nodes:
        if node.replacement_node:
            # Original is greyed out; drop its outgoing edges (replacement carries them).
            continue
        is_repl = node.name in replacement_names
        for child in node.children:
            conn = {"from": node.name, "to": child.name}
            if is_repl:
                conn["replacement"] = True
            connections.append(conn)
    return connections


# --------------------------------------------------------------------------- #
# SVG generation                                                              #
# --------------------------------------------------------------------------- #


def _arrow_svg(x1: float, y1: float, x2: float, y2: float, color: str, width: str) -> list[str]:
    parts = [
        f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" '
        f'stroke="{color}" stroke-width="{width}" stroke-linecap="round"/>'
    ]
    dx, dy = x2 - x1, y2 - y1
    length = math.hypot(dx, dy)
    if length <= 0:
        return parts
    ux, uy = dx / length, dy / length
    asize = 7.0
    base_x = x2 - asize * ux
    base_y = y2 - asize * uy
    perp_x, perp_y = -uy * (asize / 2), ux * (asize / 2)
    left = (base_x + perp_x, base_y + perp_y)
    right = (base_x - perp_x, base_y - perp_y)
    parts.append(
        f'<polygon points="{x2:.1f},{y2:.1f} {left[0]:.1f},{left[1]:.1f} {right[0]:.1f},{right[1]:.1f}" '
        f'fill="{color}"/>'
    )
    return parts


def _connection_svg(node_data: dict[str, dict], connections: list[dict]) -> str:
    parts: list[str] = []
    for conn in connections:
        src = node_data.get(conn["from"])
        dst = node_data.get(conn["to"])
        if not src or not dst:
            continue
        # Anchor points: top-center of source, bottom-center of dest box (so arrows point upward).
        x1 = src["x"] + NODE_W / 2
        y1 = src["y"]  # top of source box (since dest is above)
        x2 = dst["x"] + NODE_W / 2
        y2 = dst["y"] + NODE_H  # bottom of dest box
        # If source is actually below dest (normal), arrow goes from top of src to bottom of dst.
        if src["y"] > dst["y"]:
            x1, y1 = src["x"] + NODE_W / 2, src["y"]
            x2, y2 = dst["x"] + NODE_W / 2, dst["y"] + NODE_H
        else:
            # rare: dest below source -> draw downward
            x1, y1 = src["x"] + NODE_W / 2, src["y"] + NODE_H
            x2, y2 = dst["x"] + NODE_W / 2, dst["y"]

        is_repl = bool(conn.get("replacement"))
        color = LINE_COLOR_REPL if is_repl else LINE_COLOR
        width = LINE_WIDTH_REPL if is_repl else LINE_WIDTH
        parts.extend(_arrow_svg(x1, y1, x2, y2, color, width))
    return "\n".join(parts)


def _node_box_chunks(name: str, data: dict, replacement_names: set[str]) -> list[str]:
    """Render a single supernode (box + label + activation % + intervention badge)."""
    node: Supernode = data["node"]
    x, y = data["x"], data["y"]

    is_low = node.activation is not None and node.activation <= 0.25
    is_negative_intervention = node.intervention and "-" in node.intervention
    is_replacement = name in replacement_names

    if is_low or is_negative_intervention:
        fill, stroke, text_color = "#f0f0f0", "#d8d8d8", "#aaa"
    elif is_replacement:
        fill, stroke, text_color = "#FFF8DC", "#D2691E", "#3a2a18"
    else:
        fill, stroke, text_color = "#ececec", "#a4a4a4", "#2a2a2a"

    parts = [
        f'<rect x="{x:.1f}" y="{y:.1f}" width="{NODE_W}" height="{NODE_H}" '
        f'fill="{fill}" stroke="{stroke}" stroke-width="1.5" rx="8"/>'
    ]

    lines = _wrap_label(name, max_chars=11)
    line_height = 14
    first_y = y + (NODE_H - (len(lines) - 1) * line_height) / 2 + 4
    cx = x + NODE_W / 2
    for i, line in enumerate(lines):
        parts.append(
            f'<text x="{cx:.1f}" y="{first_y + i * line_height:.1f}" text-anchor="middle" '
            f'fill="{text_color}" font-family="Arial, sans-serif" font-size="11" '
            f'font-weight="bold">{html.escape(line)}</text>'
        )

    if node.activation is not None:
        pct = round(max(0.0, min(1.0, node.activation)) * 100)
        parts.append(
            f'<text x="{x - 2:.1f}" y="{y - 4:.1f}" text-anchor="start" '
            f'fill="#888" font-family="Arial, sans-serif" font-size="10" '
            f'font-weight="600">{pct}%</text>'
        )

    if node.intervention:
        badge_w = max(28, 7 * len(node.intervention) + 10)
        bx = x + NODE_W - badge_w + 4
        by = y - 12
        parts.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{badge_w}" height="14" '
            f'fill="#D2691E" stroke="none" rx="7"/>'
        )
        parts.append(
            f'<text x="{bx + badge_w / 2:.1f}" y="{by + 10:.1f}" text-anchor="middle" '
            f'fill="white" font-family="Arial, sans-serif" font-size="9" font-weight="bold">'
            f'{html.escape(node.intervention)}</text>'
        )
    return parts


def _node_box_svg_layered(node_data: dict[str, dict]) -> tuple[str, str]:
    """Split boxes into background (greyed-out originals) and foreground (everything else).

    Arrows are drawn between these two layers so vertical arrows that pass
    behind a greyed original remain visible, while replacement boxes always
    sit on top.
    """
    replacement_names = {
        d["node"].replacement_node.name for d in node_data.values() if d["node"].replacement_node
    }
    back: list[str] = []
    front: list[str] = []
    for name, data in node_data.items():
        node: Supernode = data["node"]
        is_low = node.activation is not None and node.activation <= 0.25
        is_neg = bool(node.intervention and "-" in node.intervention)
        is_back = (is_low or is_neg) and name not in replacement_names
        target = back if is_back else front
        target.extend(_node_box_chunks(name, data, replacement_names))
    return "\n".join(back), "\n".join(front)


def _top_outputs_grid_svg(
    top_outputs: list[tuple[str, float]],
    *,
    cols: int = 3,
    rows: int = 2,
    cell_w: float = 130,
    cell_h: float = 28,
    gap_x: float = 12,
    gap_y: float = 8,
    origin_x: float = PAD + 10,
    origin_y: float = TOP_OUTPUTS_TOP + 18,
) -> str:
    parts: list[str] = []
    for idx, (token, prob) in enumerate(top_outputs[: cols * rows]):
        r, c = divmod(idx, cols)
        x = origin_x + c * (cell_w + gap_x)
        y = origin_y + r * (cell_h + gap_y)
        display = html.escape(token if token else "(empty)")
        pct = f"{prob * 100:.1f}%" if prob < 0.1 else f"{round(prob * 100)}%"
        # cell background
        parts.append(
            f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell_w}" height="{cell_h}" '
            f'fill="#ececec" stroke="none" rx="6"/>'
        )
        # token text + percentage tspan
        parts.append(
            f'<text x="{x + 8:.1f}" y="{y + 18:.1f}" '
            f'fill="#222" font-family="Menlo, Consolas, monospace" font-size="12" '
            f'font-weight="bold">{display}'
            f'<tspan fill="#777" font-family="Arial, sans-serif" font-size="10" '
            f'font-weight="normal" dx="6">{pct}</tspan></text>'
        )
    return "\n".join(parts)


def _wrap_prompt(text: str, max_chars: int = 36) -> list[str]:
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


def create_compact_visualization(
    intervention_graph: InterventionGraph,
    top_outputs: list[tuple[str, float]],
) -> SVG:
    """Compact replacement for upstream create_graph_visualization."""
    node_data = _calc_positions(intervention_graph.ordered_nodes)
    connections = _build_connections(intervention_graph.ordered_nodes)

    # Split boxes into "originals (greyed)" and "replacements / regular".
    # Arrows go between the two layers so replacements stay clearly on top
    # while arrows are not occluded by any greyed-out original.
    arrows = _connection_svg(node_data, connections)
    boxes_back, boxes_front = _node_box_svg_layered(node_data)
    outputs = _top_outputs_grid_svg(top_outputs)

    prompt_lines = _wrap_prompt(intervention_graph.prompt, max_chars=36)
    prompt_text_svg: list[str] = []
    for i, line in enumerate(prompt_lines):
        prompt_text_svg.append(
            f'<text x="{PAD + 10}" y="{PROMPT_TOP + 36 + i * 18}" '
            f'fill="#222" font-family="Menlo, Consolas, monospace" font-size="13">'
            f'{html.escape(line)}</text>'
        )
    prompt_block = "\n".join(prompt_text_svg)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" viewBox="0 0 {CANVAS_W} {CANVAS_H}">
  <rect width="{CANVAS_W}" height="{CANVAS_H}" fill="#f7f7f7"/>
  <rect x="{PAD - 5}" y="{PAD - 5}" width="{CANVAS_W - 2 * (PAD - 5)}" height="{CANVAS_H - 2 * (PAD - 5)}" fill="#ffffff" rx="14"/>

  <text x="{PAD + 6}" y="{PAD + 18}" fill="#666" font-family="Arial, sans-serif"
        font-size="11" font-weight="bold" letter-spacing="1.2px">GRAPH &amp;</text>
  <text x="{PAD + 6}" y="{PAD + 32}" fill="#666" font-family="Arial, sans-serif"
        font-size="11" font-weight="bold" letter-spacing="1.2px">INTERVENTIONS</text>

  <g>
    {boxes_back}
    {arrows}
    {boxes_front}
  </g>

  <line x1="{PAD}" y1="{PROMPT_TOP}" x2="{CANVAS_W - PAD}" y2="{PROMPT_TOP}" stroke="#e0e0e0" stroke-width="1"/>
  <text x="{PAD + 6}" y="{PROMPT_TOP + 18}" fill="#666" font-family="Arial, sans-serif"
        font-size="11" font-weight="bold" letter-spacing="1px">PROMPT</text>
  {prompt_block}

  <text x="{PAD + 6}" y="{TOP_OUTPUTS_TOP + 8}" fill="#666" font-family="Arial, sans-serif"
        font-size="11" font-weight="bold" letter-spacing="1px">TOP OUTPUTS</text>
  {outputs}
</svg>"""
    return SVG(svg)
