"""
Layout v2: prompt + before/after prediction strip on top, smaller graph in
the middle, and an intervention-strength sweep plot at the bottom.

Mirrors the published Anthropic layout that puts ``PROMPT |
ORIGINAL PREDICTION | AFTER INTERVENTION`` headers above the boxes-and-arrows
diagram and a probability-vs-M curve below it. Only static data already on
disk is required.

Reuses the graph-area layout from ``circuit_svg_compact`` (positions, label
wrapping, layered z-order) and adds:
- top header strip with three fields,
- compact ``GRAPH & INTERVENTIONS`` section title,
- sweep line chart with two probability curves and an intervention-strength
  highlight tick.
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
    _wrap_label,
)
from graph_visualization import InterventionGraph  # noqa: E402  (vendored)
from IPython.display import SVG  # noqa: E402
from sweep_loader import SweepData  # noqa: E402


# --------------------------------------------------------------------------- #
# Layout constants                                                            #
# --------------------------------------------------------------------------- #


CANVAS_W = 480
CANVAS_H = 820
PAD = 20

# Sweep plot widths (forward-declared so the y-axis title can be placed at PAD).
PLOT_LEFT_LABEL_W = 36   # room for "Next Token Probability" rotated + tick labels

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

# Sweep plot region
PLOT_TOP = GRAPH_TOP + GRAPH_H + 16
PLOT_H = 240
PLOT_LEFT = PAD + PLOT_LEFT_LABEL_W   # space for vertical y-title + % labels
PLOT_RIGHT = CANVAS_W - PAD - 14
PLOT_INNER_TOP = PLOT_TOP + 50  # leave space for end-of-curve labels at top
PLOT_INNER_BOTTOM = PLOT_TOP + PLOT_H - 40  # leave space for x-axis labels

LINE_DECAY = "#9a9a9a"   # grey -- "original prediction" curve
LINE_GROW = "#D2691E"    # orange -- "after intervention" curve
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
# Sweep plot                                                                  #
# --------------------------------------------------------------------------- #


def _plot_section_svg(sweep: SweepData) -> str:
    parts: list[str] = []

    # Region divider above the plot.
    parts.append(
        f'<line x1="{PAD}" y1="{PLOT_TOP - 6}" x2="{CANVAS_W - PAD}" y2="{PLOT_TOP - 6}" '
        f'stroke="#e0e0e0" stroke-width="1"/>'
    )

    n = len(sweep.points)
    if n == 0:
        parts.append(
            f'<text x="{PAD + 6}" y="{PLOT_TOP + 20}" fill="#aaa" '
            f'font-family="Arial, sans-serif" font-size="11">no sweep data available</text>'
        )
        return "\n".join(parts)

    # Y range: max non-null prob, padded to next 5%.
    all_probs = [
        p for p in (*sweep.auto_decay_curve, *sweep.auto_grow_curve) if p is not None
    ]
    y_max_data = max(all_probs) if all_probs else 0.5
    y_max = max(0.1, _ceil_to_step(y_max_data, 0.05))

    # X positions: equally spaced by index of M_amplify points.
    plot_w = PLOT_RIGHT - PLOT_LEFT
    if n > 1:
        x_positions = [PLOT_LEFT + i * plot_w / (n - 1) for i in range(n)]
    else:
        x_positions = [PLOT_LEFT + plot_w / 2]

    # Background grid + y-axis tick labels at 0/25/50/75/100% of y_max.
    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        gy = PLOT_INNER_BOTTOM - frac * (PLOT_INNER_BOTTOM - PLOT_INNER_TOP)
        if frac > 0:
            parts.append(
                f'<line x1="{PLOT_LEFT}" y1="{gy:.1f}" x2="{PLOT_RIGHT}" y2="{gy:.1f}" '
                f'stroke="#eee" stroke-width="1"/>'
            )
        pct_label = f"{round(frac * y_max * 100)}%"
        parts.append(
            f'<text x="{PLOT_LEFT - 4:.1f}" y="{gy + 3:.1f}" text-anchor="end" '
            f'fill="#888" font-family="Arial, sans-serif" font-size="9">{pct_label}</text>'
        )

    # Y-axis line.
    parts.append(
        f'<line x1="{PLOT_LEFT}" y1="{PLOT_INNER_TOP}" x2="{PLOT_LEFT}" y2="{PLOT_INNER_BOTTOM}" '
        f'stroke="#888" stroke-width="1"/>'
    )

    # Y-axis title, rotated -90 degrees and centred along the inner plot height.
    title_cy = (PLOT_INNER_TOP + PLOT_INNER_BOTTOM) / 2
    title_x = PAD + 8
    parts.append(
        f'<text x="{title_x}" y="{title_cy}" fill="#666" '
        f'font-family="Arial, sans-serif" font-size="10" text-anchor="middle" '
        f'transform="rotate(-90 {title_x} {title_cy})">Next Token Probability</text>'
    )

    # Curves: when AFTER == ORIGINAL (same token kept on top), draw a single
    # orange curve labeled with the unified "(original = after)" annotation.
    same_token = sweep.auto_grow_token is None and sweep.auto_decay_token is not None
    decay_color = LINE_GROW if same_token else LINE_DECAY
    parts.append(_curve_svg(x_positions, sweep.auto_decay_curve, y_max, color=decay_color))
    if not same_token:
        parts.append(_curve_svg(x_positions, sweep.auto_grow_curve, y_max, color=LINE_GROW))

    # End-point labels.
    if sweep.auto_decay_token:
        decay_label_color = LINE_GROW if same_token else "#666"
        annot = "(original = after)" if same_token else "(original)"
        parts.append(
            f'<text x="{PLOT_LEFT + 4}" y="{PLOT_TOP + 16}" fill="{decay_label_color}" '
            f'font-family="Menlo, Consolas, monospace" font-size="12" font-weight="bold">'
            f'{html.escape(sweep.auto_decay_token.strip())}</text>'
        )
        parts.append(
            f'<text x="{PLOT_LEFT + 4 + 8 * (len(sweep.auto_decay_token.strip()) + 1)}" '
            f'y="{PLOT_TOP + 16}" fill="#aaa" font-family="Arial, sans-serif" font-size="10">'
            f'{annot}</text>'
        )
    if sweep.auto_grow_token:
        parts.append(
            f'<text x="{PLOT_RIGHT - 4}" y="{PLOT_TOP + 16}" text-anchor="end" '
            f'fill="{LINE_GROW}" font-family="Menlo, Consolas, monospace" '
            f'font-size="12" font-weight="bold">'
            f'{html.escape(sweep.auto_grow_token.strip())}</text>'
        )
        parts.append(
            f'<text x="{PLOT_RIGHT - 4}" y="{PLOT_TOP + 30}" text-anchor="end" '
            f'fill="#aaa" font-family="Arial, sans-serif" font-size="10">(after intervention)</text>'
        )

    # X axis with tick labels = M values.
    parts.append(
        f'<line x1="{PLOT_LEFT}" y1="{PLOT_INNER_BOTTOM}" x2="{PLOT_RIGHT}" '
        f'y2="{PLOT_INNER_BOTTOM}" stroke="#888" stroke-width="1"/>'
    )
    primary_idx: int | None = None
    for i, p in enumerate(sweep.points):
        x = x_positions[i]
        parts.append(
            f'<line x1="{x:.1f}" y1="{PLOT_INNER_BOTTOM}" x2="{x:.1f}" '
            f'y2="{PLOT_INNER_BOTTOM + 4}" stroke="#888" stroke-width="1"/>'
        )
        is_primary = p.M_amplify == sweep.primary_M
        if is_primary:
            primary_idx = i
        label_color = ACCENT if is_primary else "#666"
        weight = "bold" if is_primary else "normal"
        parts.append(
            f'<text x="{x:.1f}" y="{PLOT_INNER_BOTTOM + 18}" text-anchor="middle" '
            f'fill="{label_color}" font-family="Arial, sans-serif" font-size="11" '
            f'font-weight="{weight}">{p.M_amplify}x</text>'
        )

    # X axis title.
    parts.append(
        f'<text x="{PLOT_LEFT}" y="{PLOT_INNER_BOTTOM + 34}" fill="#888" '
        f'font-family="Arial, sans-serif" font-size="10">Intervention Strength</text>'
    )

    # Highlight the primary M with a vertical dashed guide + filled badge.
    if primary_idx is not None:
        hx = x_positions[primary_idx]
        parts.append(
            f'<line x1="{hx:.1f}" y1="{PLOT_INNER_TOP - 4}" x2="{hx:.1f}" '
            f'y2="{PLOT_INNER_BOTTOM}" stroke="{ACCENT}" stroke-width="1" '
            f'stroke-dasharray="3 3" opacity="0.6"/>'
        )
        # Pill badge on the x-axis at primary M.
        badge_w = 36
        bx = hx - badge_w / 2
        by = PLOT_INNER_BOTTOM + 22
        parts.append(
            f'<rect x="{bx:.1f}" y="{by:.1f}" width="{badge_w}" height="14" '
            f'fill="{ACCENT}" rx="7"/>'
        )
        parts.append(
            f'<text x="{hx:.1f}" y="{by + 10:.1f}" text-anchor="middle" '
            f'fill="white" font-family="Arial, sans-serif" font-size="10" '
            f'font-weight="bold">{sweep.primary_M}x</text>'
        )

    return "\n".join(parts)


def _curve_svg(x_positions: list[float], curve: list[float | None], y_max: float, *,
               color: str) -> str:
    """Render a polyline curve. Missing points (None) -> dashed segments."""
    if not curve:
        return ""
    h = PLOT_INNER_BOTTOM - PLOT_INNER_TOP

    def _y_for(prob: float) -> float:
        return PLOT_INNER_BOTTOM - (prob / y_max) * h

    parts: list[str] = []
    # Build segments: solid where both endpoints are non-null, dashed where
    # at least one is null (linearly interpolated to 0).
    last_x: float | None = None
    last_y: float | None = None
    last_solid = False
    for x, prob in zip(x_positions, curve):
        if prob is None:
            cur_y = _y_for(0.0)
            cur_solid = False
        else:
            cur_y = _y_for(prob)
            cur_solid = True
        if last_x is not None and last_y is not None:
            seg_solid = last_solid and cur_solid
            dash = "" if seg_solid else 'stroke-dasharray="3 3" opacity="0.55"'
            parts.append(
                f'<line x1="{last_x:.1f}" y1="{last_y:.1f}" x2="{x:.1f}" y2="{cur_y:.1f}" '
                f'stroke="{color}" stroke-width="2" stroke-linecap="round" {dash}/>'
            )
        last_x, last_y, last_solid = x, cur_y, cur_solid
    # Dot markers on real points.
    for x, prob in zip(x_positions, curve):
        if prob is None:
            continue
        y = _y_for(prob)
        parts.append(
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="3" fill="{color}" '
            f'stroke="white" stroke-width="1"/>'
        )
    return "\n".join(parts)


def _ceil_to_step(value: float, step: float) -> float:
    """Round ``value`` up to the nearest multiple of ``step``."""
    if step <= 0:
        return value
    import math
    return math.ceil(value / step) * step


# --------------------------------------------------------------------------- #
# Public API                                                                  #
# --------------------------------------------------------------------------- #


def create_v2_visualization(
    intervention_graph: InterventionGraph,
    *,
    prompt: str,
    original_pred: tuple[str, float],
    after_pred: tuple[str, float],
    sweep: SweepData,
) -> SVG:
    top = _top_strip_svg(prompt, original_pred, after_pred)
    graph = _graph_section_svg(intervention_graph)
    plot = _plot_section_svg(sweep)

    svg = f"""<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" height="{CANVAS_H}" viewBox="0 0 {CANVAS_W} {CANVAS_H}">
  <rect width="{CANVAS_W}" height="{CANVAS_H}" fill="#f7f7f7"/>
  <rect x="{PAD - 5}" y="{PAD - 5}" width="{CANVAS_W - 2 * (PAD - 5)}" height="{CANVAS_H - 2 * (PAD - 5)}" fill="#ffffff" rx="14"/>

  {top}

  {graph}

  {plot}
</svg>"""
    return SVG(svg)
