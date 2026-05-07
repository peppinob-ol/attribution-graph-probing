"""Horizontal-strip layout for swap interventions.

A landscape variant inspired by the demo's detail panel, with four columns:

    SOURCE / TARGET cards | DEFAULT / STEERED text | ABLATED / AMPLIFIED list | position-axis plot

Same grey-orange palette as ``circuit_svg_v2`` and the swap matrix. The
right-most plot replaces the ``M``-sweep curve with a per-token-position
trajectory: how does the probability of the source / target token evolve
across the steered model's generated tokens?

Public entry point: :func:`create_strip_visualization`.
"""
from __future__ import annotations

import html
import math
from dataclasses import dataclass
from typing import Sequence

# --------------------------------------------------------------------------- #
# Layout constants                                                            #
# --------------------------------------------------------------------------- #

CANVAS_W = 1000
CANVAS_H = 220
PAD = 8

# Column widths (the four panels fit horizontally with 8px gutters).
COL_ENTITY_W = 110
COL_OUTPUT_W = 340
COL_FEATURES_W = 184
COL_PLOT_W = (
    CANVAS_W - 4 * PAD - COL_ENTITY_W - COL_OUTPUT_W - COL_FEATURES_W
)
ROW_H = (CANVAS_H - 3 * PAD) // 2  # two stacked rows

CARD_FILL = "#f6f6f6"
CARD_STROKE = "#d8d8d8"
CARD_RADIUS = 6
LABEL_COLOR = "#777"
TEXT_COLOR = "#1f1f1f"
MUTED_TEXT = "#555"

SOURCE_ACCENT = "#6e6e6e"   # grey -- "source" highlight
TARGET_ACCENT = "#D2691E"   # chocolate orange -- "target" highlight
ABLATE_BADGE_FILL = "#ececec"
ABLATE_BADGE_TEXT = "#555"
AMPLIFY_BADGE_FILL = "#D2691E"
AMPLIFY_BADGE_TEXT = "#ffffff"

PLOT_GRID = "#eeeeee"
PLOT_AXIS = "#888888"
PLOT_DECAY = "#9a9a9a"
PLOT_GROW = "#D2691E"


# --------------------------------------------------------------------------- #
# Public dataclasses                                                          #
# --------------------------------------------------------------------------- #


@dataclass
class EntityCard:
    role: str           # "Source" or "Target"
    headline: str       # the answer token, e.g. "Indianapolis"
    fields: list[tuple[str, str]]  # [(field_name, value), ...]


@dataclass
class SupernodeRow:
    name: str
    feature_count: int   # number of (layer, pos, feature_idx) features in the supernode


@dataclass
class TrajectoryPlot:
    """Per-position trajectory data for the right-hand plot.

    *positions*, *probs_source*, *probs_target*, *generated_tokens* must all
    have the same length. ``primary_position`` is highlighted with a vertical
    orange line (default 0 = the position used to score "tier 5" hits).
    """
    positions: list[int]
    generated_tokens: list[str]
    source_token: str
    target_token: str
    probs_source: list[float | None]
    probs_target: list[float | None]
    primary_position: int = 0


# --------------------------------------------------------------------------- #
# Helpers                                                                     #
# --------------------------------------------------------------------------- #


def _wrap_text(text: str, max_chars: int) -> list[str]:
    """Word-wrap *text* into lines no longer than *max_chars* (best-effort)."""
    if not text:
        return []
    words = text.split(" ")
    lines: list[str] = []
    cur = ""
    for w in words:
        candidate = f"{cur} {w}".strip()
        if len(candidate) <= max_chars or not cur:
            cur = candidate
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _highlight_substring(
    text: str,
    needles_with_color: Sequence[tuple[str, str]],
) -> list[tuple[str, str | None]]:
    """Split *text* into (segment, color) pairs.

    Each (needle, color) pair will be coloured wherever it appears as a
    case-insensitive substring; the rest of the text gets ``color = None``.
    Earlier needles take precedence over later ones.
    """
    if not text:
        return []
    spans: list[tuple[int, int, str]] = []
    occupied = [False] * len(text)
    for needle, color in needles_with_color:
        if not needle:
            continue
        i = 0
        low = text.lower()
        nlow = needle.lower()
        while True:
            j = low.find(nlow, i)
            if j == -1:
                break
            if not any(occupied[j : j + len(needle)]):
                spans.append((j, j + len(needle), color))
                for k in range(j, j + len(needle)):
                    occupied[k] = True
            i = j + len(needle)
    spans.sort()
    out: list[tuple[str, str | None]] = []
    cursor = 0
    for s, e, color in spans:
        if cursor < s:
            out.append((text[cursor:s], None))
        out.append((text[s:e], color))
        cursor = e
    if cursor < len(text):
        out.append((text[cursor:], None))
    return out


def _ceil_to_step(x: float, step: float) -> float:
    if x <= 0:
        return step
    n = int(x / step)
    if n * step >= x - 1e-9:
        return n * step
    return (n + 1) * step


_ENTITY_HEADLINE_FONT_SIZE = 12
_ENTITY_HEADLINE_LINE_H = 12  # tight stacking when the answer wraps
_ENTITY_VALUE_FONT_SIZE = 9
_ENTITY_LABEL_FONT_SIZE = 9
_ENTITY_LINE_H = 10

# Approximate per-character width (px) at the corresponding font sizes. Used
# only for soft word-wrapping inside the narrow entity cards: cairosvg renders
# the actual glyph widths in the output, but we still need a budget to avoid
# the text being clipped by the card border (the issue the user flagged
# happens when long values like "The Catcher in the Rye" silently overflow).
_HEADLINE_CHAR_W = 6.8   # Menlo bold @ 12
_VALUE_CHAR_W = 5.5      # Menlo regular @ 9
_LABEL_CHAR_W = 4.6      # Arial regular @ 9


def _wrap_to_width(text: str, max_chars: int) -> list[str]:
    """Greedy word-wrap; falls back to character-chunking for tokens longer
    than ``max_chars`` so the panel never lets a single long word escape its
    border."""
    if not text:
        return []
    words = text.split(" ")
    lines: list[str] = []
    cur = ""
    for w in words:
        if len(w) > max_chars:
            if cur:
                lines.append(cur)
                cur = ""
            for j in range(0, len(w), max_chars):
                lines.append(w[j : j + max_chars])
            continue
        candidate = f"{cur} {w}".strip()
        if len(candidate) <= max_chars or not cur:
            cur = candidate
        else:
            lines.append(cur)
            cur = w
    if cur:
        lines.append(cur)
    return lines


def _entity_card_svg(card: EntityCard, x: int, y: int, w: int, h: int) -> str:
    """Render one source / target entity card.

    Field values longer than the card width are word-wrapped onto continuation
    lines (with a hanging indent) so domains like Books -- where ``book``
    holds a full title -- don't silently clip text against the card border.
    """
    accent = TARGET_ACCENT if card.role.lower() == "target" else SOURCE_ACCENT
    parts: list[str] = []
    parts.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{CARD_RADIUS}" '
        f'ry="{CARD_RADIUS}" fill="{CARD_FILL}" stroke="{CARD_STROKE}"/>'
    )
    parts.append(
        f'<text x="{x + 10}" y="{y + 14}" fill="{LABEL_COLOR}" '
        f'font-family="Arial, sans-serif" font-size="9" font-weight="bold" '
        f'letter-spacing="1.1px">{card.role.upper()}</text>'
    )

    inner_w = w - 20  # 10 px padding on each side
    headline_max_chars = max(4, int(inner_w / _HEADLINE_CHAR_W))
    headline_lines = _wrap_to_width(card.headline, headline_max_chars)[:2]
    if not headline_lines:
        headline_lines = [card.headline]
    headline_y = y + 30
    for line in headline_lines:
        parts.append(
            f'<text x="{x + 10}" y="{headline_y}" fill="{accent}" '
            f'font-family="Menlo, Consolas, monospace" '
            f'font-size="{_ENTITY_HEADLINE_FONT_SIZE}" '
            f'font-weight="bold">{html.escape(line)}</text>'
        )
        headline_y += _ENTITY_HEADLINE_LINE_H
    yy = headline_y + 2
    bottom_limit = y + h - 4
    for field_name, value in card.fields[:3]:
        # Budget for first line: deduct width of "<field_name>: " (Arial 9)
        # so the value can start inline next to the label without spilling.
        prefix_chars = len(field_name) + 2
        prefix_w = prefix_chars * _LABEL_CHAR_W
        first_line_max = max(2, int((inner_w - prefix_w) / _VALUE_CHAR_W))
        cont_max = max(2, int(inner_w / _VALUE_CHAR_W))

        # If even a single word can't fit on the inline first line next to
        # the field label (e.g. "character: Huckleberry" only has room for
        # ~7 chars after the label, but "Huckleberry" is 11), push the value
        # to its own continuation line with the full inner width. This avoids
        # the ugly mid-word break "Huckleb / erry" the user saw.
        words = (value or "").split(" ")
        first_word_len = len(words[0]) if words else 0
        if first_word_len > first_line_max and first_word_len <= cont_max:
            lines: list[str] = [""]
            budget = cont_max
        else:
            lines = []
            budget = first_line_max
        cur = ""
        for w_token in words:
            if len(w_token) > budget and cur:
                lines.append(cur)
                cur = ""
                budget = cont_max
            if len(w_token) > budget:
                # value still longer than even a fresh continuation line
                for j in range(0, len(w_token), budget):
                    lines.append(w_token[j : j + budget])
                continue
            candidate = f"{cur} {w_token}".strip() if cur else w_token
            if len(candidate) <= budget:
                cur = candidate
            else:
                lines.append(cur)
                cur = w_token
                budget = cont_max
        if cur:
            lines.append(cur)
        if not lines:
            lines = [""]

        # Line 1: "<field_name>: <value>" inline, sharing one <text>.
        if yy > bottom_limit:
            break
        parts.append(
            f'<text x="{x + 10}" y="{yy}" fill="{LABEL_COLOR}" '
            f'font-family="Arial, sans-serif" font-size="{_ENTITY_LABEL_FONT_SIZE}">'
            f'{html.escape(field_name)}: '
            f'<tspan fill="{TEXT_COLOR}" font-family="Menlo, Consolas, monospace" '
            f'font-size="{_ENTITY_VALUE_FONT_SIZE}">{html.escape(lines[0])}</tspan>'
            f'</text>'
        )
        yy += _ENTITY_LINE_H
        for cont in lines[1:]:
            if yy > bottom_limit:
                break
            parts.append(
                f'<text x="{x + 10}" y="{yy}" fill="{TEXT_COLOR}" '
                f'font-family="Menlo, Consolas, monospace" '
                f'font-size="{_ENTITY_VALUE_FONT_SIZE}">'
                f'{html.escape(cont)}</text>'
            )
            yy += _ENTITY_LINE_H
    return "\n".join(parts)


def _split_line_into_spans(
    line: str,
    line_start_global: int,
    spans: list[tuple[str, str | None]],
) -> list[tuple[str, str | None]]:
    """Project the global ``spans`` partition onto a single wrapped line.

    Returns ``[(chunk, color_or_None), ...]`` in line order so the caller
    can emit one ``<tspan>`` per chunk inside a single ``<text>`` element
    -- letting the SVG renderer flow them inline with their actual glyph
    widths instead of relying on a (lossy) per-character estimate.
    """
    out: list[tuple[str, str | None]] = []
    if not line:
        return out
    line_end_global = line_start_global + len(line)
    running = 0
    for seg, color in spans:
        seg_start = running
        seg_end = running + len(seg)
        running = seg_end
        if seg_end <= line_start_global or seg_start >= line_end_global:
            continue
        clip_start = max(seg_start, line_start_global)
        clip_end = min(seg_end, line_end_global)
        out.append((seg[clip_start - seg_start : clip_end - seg_start], color))
    return out


def _output_panel_svg(
    title: str,
    text: str,
    source_word: str,
    target_word: str,
    x: int,
    y: int,
    w: int,
    h: int,
) -> str:
    """Render one of the DEFAULT / STEERED OUTPUT panels.

    Each wrapped line lives in a single ``<text>`` element with one
    ``<tspan>`` per highlighted segment; this lets the SVG renderer flow
    bold-coloured chunks (the source / target tokens) at their true glyph
    widths instead of needing manual ``x`` placement, which was producing
    the small leftward gap and trailing overlap that the user reported.
    """
    parts: list[str] = []
    parts.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{CARD_RADIUS}" '
        f'ry="{CARD_RADIUS}" fill="{CARD_FILL}" stroke="{CARD_STROKE}"/>'
    )
    parts.append(
        f'<text x="{x + 10}" y="{y + 14}" fill="{LABEL_COLOR}" '
        f'font-family="Arial, sans-serif" font-size="9" font-weight="bold" '
        f'letter-spacing="1.1px">{html.escape(title.upper())}</text>'
    )

    text = text.replace("<bos>", "")
    spans = _highlight_substring(
        text,
        [
            (target_word, TARGET_ACCENT),
            (source_word, SOURCE_ACCENT),
        ],
    )
    plain = "".join(s[0] for s in spans)
    lines_plain = _wrap_text(plain, max_chars=44)

    line_h = 15
    yy = y + 34
    rendered_lines = lines_plain[:4]
    cursor = 0
    text_x = x + 10
    for line in rendered_lines:
        line_start = plain.find(line, cursor)
        if line_start < 0:
            line_start = cursor
        line_chunks = _split_line_into_spans(line, line_start, spans)
        if not line_chunks:
            cursor = line_start + len(line)
            yy += line_h
            continue
        tspans: list[str] = []
        for chunk, color in line_chunks:
            tspan_color = color or TEXT_COLOR
            weight = "bold" if color else "normal"
            # ``xml:space="preserve"`` keeps interior whitespace intact so the
            # word-spacing around bold-coloured chunks matches the surrounding
            # plain text (otherwise the SVG renderer collapses leading /
            # trailing spaces inside a tspan and the highlight visually drifts).
            tspans.append(
                f'<tspan fill="{tspan_color}" font-weight="{weight}" '
                f'xml:space="preserve">{html.escape(chunk)}</tspan>'
            )
        parts.append(
            f'<text x="{text_x}" y="{yy}" fill="{TEXT_COLOR}" '
            f'font-family="Menlo, Consolas, monospace" font-size="12">'
            + "".join(tspans)
            + "</text>"
        )
        cursor = line_start + len(line)
        yy += line_h
    return "\n".join(parts)


def _features_panel_svg(
    title: str,
    badge_text: str,
    badge_fill: str,
    badge_text_color: str,
    rows: list[SupernodeRow],
    total_features: int,
    x: int,
    y: int,
    w: int,
    h: int,
) -> str:
    parts: list[str] = []
    parts.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{CARD_RADIUS}" '
        f'ry="{CARD_RADIUS}" fill="{CARD_FILL}" stroke="{CARD_STROKE}"/>'
    )
    parts.append(
        f'<text x="{x + 10}" y="{y + 14}" fill="{LABEL_COLOR}" '
        f'font-family="Arial, sans-serif" font-size="9" font-weight="bold" '
        f'letter-spacing="1.1px">{html.escape(title.upper())} '
        f'({total_features})</text>'
    )

    badge_w = 36
    badge_h = 14
    bx = x + w - badge_w - 8
    by = y + 6
    parts.append(
        f'<rect x="{bx}" y="{by}" width="{badge_w}" height="{badge_h}" rx="7" '
        f'ry="7" fill="{badge_fill}"/>'
        f'<text x="{bx + badge_w / 2:.1f}" y="{by + 10}" fill="{badge_text_color}" '
        f'font-family="Arial, sans-serif" font-size="9" font-weight="bold" '
        f'text-anchor="middle">{html.escape(badge_text)}</text>'
    )

    yy = y + 32
    for row in rows[:5]:
        label = row.name
        if len(label) > 22:
            label = label[:21] + "…"
        parts.append(
            f'<text x="{x + 10}" y="{yy}" fill="{TEXT_COLOR}" '
            f'font-family="Menlo, Consolas, monospace" font-size="10">'
            f'{html.escape(label)}'
            f'<tspan fill="{LABEL_COLOR}" font-size="9"> '
            f'({row.feature_count} feats.)</tspan></text>'
        )
        yy += 13
    return "\n".join(parts)


def _plot_panel_svg(
    plot: TrajectoryPlot,
    x: int,
    y: int,
    w: int,
    h: int,
) -> str:
    parts: list[str] = []
    parts.append(
        f'<rect x="{x}" y="{y}" width="{w}" height="{h}" rx="{CARD_RADIUS}" '
        f'ry="{CARD_RADIUS}" fill="#ffffff" stroke="{CARD_STROKE}"/>'
    )

    n = len(plot.positions)
    if n == 0:
        parts.append(
            f'<text x="{x + 10}" y="{y + 20}" fill="{LABEL_COLOR}" '
            f'font-family="Arial, sans-serif" font-size="10">no trajectory data</text>'
        )
        return "\n".join(parts)

    inner_left = x + 38   # tight left padding: rotated y-title + % labels
    inner_right = x + w - 12
    inner_top = y + 36    # extra breathing room for the title + annotation
    inner_bottom = y + h - 28

    src_max = max((p for p in plot.probs_source if p is not None), default=0.0)
    tgt_max = max((p for p in plot.probs_target if p is not None), default=0.0)
    y_max = _ceil_to_step(max(src_max, tgt_max, 0.05), 0.05)

    plot_w = inner_right - inner_left
    plot_h = inner_bottom - inner_top
    if n > 1:
        x_positions = [inner_left + i * plot_w / (n - 1) for i in range(n)]
    else:
        x_positions = [inner_left + plot_w / 2]

    for frac in (0.0, 0.25, 0.5, 0.75, 1.0):
        gy = inner_bottom - frac * plot_h
        parts.append(
            f'<line x1="{inner_left}" y1="{gy:.1f}" x2="{inner_right}" '
            f'y2="{gy:.1f}" stroke="{PLOT_GRID}" stroke-width="1"/>'
        )
        parts.append(
            f'<text x="{inner_left - 4}" y="{gy + 3:.1f}" fill="{LABEL_COLOR}" '
            f'font-family="Arial, sans-serif" font-size="8" '
            f'text-anchor="end">{int(round(frac * y_max * 100))}%</text>'
        )

    parts.append(
        f'<line x1="{inner_left}" y1="{inner_top}" x2="{inner_left}" '
        f'y2="{inner_bottom}" stroke="{PLOT_AXIS}" stroke-width="1"/>'
    )
    parts.append(
        f'<line x1="{inner_left}" y1="{inner_bottom}" x2="{inner_right}" '
        f'y2="{inner_bottom}" stroke="{PLOT_AXIS}" stroke-width="1"/>'
    )

    # Y-axis title: rotated -90 degrees, centred along the inner plot height.
    # Same font as the x-axis caption ("Generated token position"), placed
    # just outside the % tick labels.
    title_cy = (inner_top + inner_bottom) / 2.0
    title_x = x + 10
    parts.append(
        f'<text x="{title_x}" y="{title_cy:.1f}" fill="{LABEL_COLOR}" '
        f'font-family="Arial, sans-serif" font-size="8" text-anchor="middle" '
        f'transform="rotate(-90 {title_x} {title_cy:.1f})">'
        f'Next Token Probability</text>'
    )

    if 0 <= plot.primary_position < n:
        hx = x_positions[plot.primary_position]
        parts.append(
            f'<line x1="{hx:.1f}" y1="{inner_top}" x2="{hx:.1f}" '
            f'y2="{inner_bottom}" stroke="{PLOT_GROW}" stroke-width="1" '
            f'stroke-dasharray="2 2"/>'
        )

    def _curve(probs: list[float | None], color: str) -> None:
        pts: list[tuple[float, float]] = []
        for i, p in enumerate(probs):
            if p is None:
                if pts:
                    parts.append(_polyline(pts, color))
                pts = []
                continue
            py = inner_bottom - (p / y_max) * plot_h if y_max > 0 else inner_bottom
            pts.append((x_positions[i], py))
        if pts:
            parts.append(_polyline(pts, color))
        for i, p in enumerate(probs):
            if p is None:
                continue
            py = inner_bottom - (p / y_max) * plot_h if y_max > 0 else inner_bottom
            parts.append(
                f'<circle cx="{x_positions[i]:.1f}" cy="{py:.1f}" r="2.2" '
                f'fill="{color}"/>'
            )

    _curve(plot.probs_source, PLOT_DECAY)
    _curve(plot.probs_target, PLOT_GROW)

    src_label = (plot.source_token.strip() or "src")[:11]
    tgt_label = (plot.target_token.strip() or "tgt")[:11]
    parts.append(
        f'<text x="{x + 10}" y="{y + 14}" fill="{LABEL_COLOR}" '
        f'font-family="Arial, sans-serif" font-size="9" font-weight="bold" '
        f'letter-spacing="1.0px">TARGET TRAJECTORY</text>'
    )
    legend_y = y + 14
    legend_x = x + w - 10
    tgt_label_w = max(28, int(len(tgt_label) * 6.0))
    legend_x -= tgt_label_w
    parts.append(
        f'<text x="{legend_x}" y="{legend_y}" fill="{PLOT_GROW}" '
        f'font-family="Menlo, Consolas, monospace" font-size="9" '
        f'font-weight="bold">{html.escape(tgt_label)}</text>'
    )
    parts.append(
        f'<line x1="{legend_x - 14}" y1="{legend_y - 3}" '
        f'x2="{legend_x - 4}" y2="{legend_y - 3}" '
        f'stroke="{PLOT_GROW}" stroke-width="2"/>'
    )
    legend_x -= 18
    src_label_w = max(28, int(len(src_label) * 6.0))
    legend_x -= src_label_w
    parts.append(
        f'<text x="{legend_x}" y="{legend_y}" fill="{PLOT_DECAY}" '
        f'font-family="Menlo, Consolas, monospace" font-size="9" '
        f'font-weight="bold">{html.escape(src_label)}</text>'
    )
    parts.append(
        f'<line x1="{legend_x - 14}" y1="{legend_y - 3}" '
        f'x2="{legend_x - 4}" y2="{legend_y - 3}" '
        f'stroke="{PLOT_DECAY}" stroke-width="2"/>'
    )

    # Tick density: pick a step that guarantees a minimum horizontal gap
    # between adjacent rendered labels so they never visually collide. We
    # estimate label width from the truncation cap (8 chars + ellipsis) and
    # the per-character width of font-size 8 monospace (~5 px).
    label_y = inner_bottom + 10
    n_labels = len(plot.generated_tokens)
    max_label_chars = 7
    label_char_w = 5.0
    min_label_gap = 6.0
    label_width_px = max_label_chars * label_char_w + min_label_gap
    if n_labels > 1:
        spacing_per_pos = plot_w / (n_labels - 1)
        step = max(1, math.ceil(label_width_px / max(spacing_per_pos, 1.0)))
    else:
        step = 1
    last_label_x: float | None = None
    for i, tok in enumerate(plot.generated_tokens):
        is_unsteered = tok.strip().startswith("[")
        if is_unsteered:
            continue  # the unsteered column is annotated above the plot instead
        is_primary = i == plot.primary_position
        if not is_primary and i % step != 0 and i != n_labels - 1:
            continue
        cx = x_positions[i] if i < len(x_positions) else inner_right
        # Belt-and-braces: even after the step filter, drop a label if the
        # primary tick has already pushed it too close to its neighbour
        # (keeps "Suzanne" / "Collins" from sitting on top of each other).
        if (
            not is_primary
            and last_label_x is not None
            and cx - last_label_x < label_width_px
        ):
            continue
        color = PLOT_GROW if is_primary else MUTED_TEXT
        weight = "bold" if is_primary else "normal"
        label = tok.strip() or "·"
        if len(label) > max_label_chars + 1:
            label = label[:max_label_chars] + "…"
        parts.append(
            f'<text x="{cx:.1f}" y="{label_y}" fill="{color}" '
            f'font-family="Menlo, Consolas, monospace" font-size="8" '
            f'font-weight="{weight}" text-anchor="middle">'
            f'{html.escape(label)}</text>'
        )
        last_label_x = cx

    # Separator between [unsteered] (index 0) and the steered run (index >= 1)
    # plus a "unsteered <-> steered" annotation above the plot. The arrow is
    # centred on the first steered tick (the orange-highlighted point) so the
    # bidirectional <-> sits visually between the two regions.
    if n >= 2 and plot.generated_tokens and plot.generated_tokens[0].strip().startswith("["):
        sep_x = (x_positions[0] + x_positions[1]) / 2.0
        parts.append(
            f'<line x1="{sep_x:.1f}" y1="{inner_top}" x2="{sep_x:.1f}" '
            f'y2="{inner_bottom + 4}" stroke="#cccccc" stroke-width="1" '
            f'stroke-dasharray="1 3"/>'
        )
        annot_x = x_positions[1]
        parts.append(
            f'<text x="{annot_x:.1f}" y="{inner_top - 8}" fill="{LABEL_COLOR}" '
            f'font-family="Arial, sans-serif" font-size="7" '
            f'font-style="italic" text-anchor="middle">'
            f'unsteered &#8596; steered</text>'
        )

    parts.append(
        f'<text x="{(inner_left + inner_right) / 2:.1f}" y="{y + h - 4}" '
        f'fill="{LABEL_COLOR}" font-family="Arial, sans-serif" font-size="8" '
        f'text-anchor="middle">Generated token position</text>'
    )

    return "\n".join(parts)


def _polyline(points: list[tuple[float, float]], color: str) -> str:
    """Render a polyline that hits every data point but with slightly rounded
    corners, giving a hand-drawn feel without aggressive smoothing.

    Each interior vertex is replaced with a small quadratic-Bezier corner
    (radius clamped to half of the shorter adjacent segment, capped at 4 px),
    so the curve still passes through every data point with good fidelity.
    """
    if not points:
        return ""
    if len(points) == 1:
        x, y = points[0]
        return (
            f'<circle cx="{x:.1f}" cy="{y:.1f}" r="1.6" fill="{color}"/>'
        )
    if len(points) == 2:
        pts = " ".join(f"{x:.1f},{y:.1f}" for x, y in points)
        return (
            f'<polyline points="{pts}" fill="none" stroke="{color}" '
            f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
        )

    radius = 4.0
    cmds: list[str] = [f"M{points[0][0]:.1f},{points[0][1]:.1f}"]
    for i in range(1, len(points) - 1):
        prev = points[i - 1]
        cur = points[i]
        nxt = points[i + 1]
        dx_in, dy_in = prev[0] - cur[0], prev[1] - cur[1]
        dx_out, dy_out = nxt[0] - cur[0], nxt[1] - cur[1]
        len_in = math.hypot(dx_in, dy_in)
        len_out = math.hypot(dx_out, dy_out)
        r = min(radius, len_in / 2.0, len_out / 2.0)
        if r <= 0.5 or len_in == 0 or len_out == 0:
            cmds.append(f"L{cur[0]:.1f},{cur[1]:.1f}")
            continue
        in_x = cur[0] + dx_in * r / len_in
        in_y = cur[1] + dy_in * r / len_in
        out_x = cur[0] + dx_out * r / len_out
        out_y = cur[1] + dy_out * r / len_out
        cmds.append(f"L{in_x:.1f},{in_y:.1f}")
        cmds.append(f"Q{cur[0]:.1f},{cur[1]:.1f} {out_x:.1f},{out_y:.1f}")
    cmds.append(f"L{points[-1][0]:.1f},{points[-1][1]:.1f}")
    d = " ".join(cmds)
    return (
        f'<path d="{d}" fill="none" stroke="{color}" '
        f'stroke-width="1.6" stroke-linecap="round" stroke-linejoin="round"/>'
    )


# --------------------------------------------------------------------------- #
# Public entry point                                                          #
# --------------------------------------------------------------------------- #


def create_strip_visualization(
    *,
    source_card: EntityCard,
    target_card: EntityCard,
    default_output: str,
    steered_output: str,
    source_word: str,
    target_word: str,
    ablated: list[SupernodeRow],
    amplified: list[SupernodeRow],
    ablate_total_features: int,
    amplify_total_features: int,
    ablate_badge: str,
    amplify_badge: str,
    trajectory: TrajectoryPlot,
    ablate_title: str = "Source / Ablated",
    amplify_title: str = "Target / Amplified",
) -> str:
    """Render a single horizontal strip SVG and return its markup."""
    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{CANVAS_W}" '
        f'height="{CANVAS_H}" viewBox="0 0 {CANVAS_W} {CANVAS_H}">'
    )
    parts.append(f'<rect width="{CANVAS_W}" height="{CANVAS_H}" fill="#ffffff"/>')

    x_entity = PAD
    x_output = x_entity + COL_ENTITY_W + PAD
    x_features = x_output + COL_OUTPUT_W + PAD
    x_plot = x_features + COL_FEATURES_W + PAD

    y_top = PAD
    y_bot = y_top + ROW_H + PAD
    y_plot = PAD

    parts.append(_entity_card_svg(source_card, x_entity, y_top, COL_ENTITY_W, ROW_H))
    parts.append(_entity_card_svg(target_card, x_entity, y_bot, COL_ENTITY_W, ROW_H))

    parts.append(
        _output_panel_svg(
            "Default Output",
            default_output,
            source_word,
            target_word,
            x_output,
            y_top,
            COL_OUTPUT_W,
            ROW_H,
        )
    )
    parts.append(
        _output_panel_svg(
            "Steered Output",
            steered_output,
            source_word,
            target_word,
            x_output,
            y_bot,
            COL_OUTPUT_W,
            ROW_H,
        )
    )

    parts.append(
        _features_panel_svg(
            ablate_title,
            ablate_badge,
            ABLATE_BADGE_FILL,
            ABLATE_BADGE_TEXT,
            ablated,
            ablate_total_features,
            x_features,
            y_top,
            COL_FEATURES_W,
            ROW_H,
        )
    )
    parts.append(
        _features_panel_svg(
            amplify_title,
            amplify_badge,
            AMPLIFY_BADGE_FILL,
            AMPLIFY_BADGE_TEXT,
            amplified,
            amplify_total_features,
            x_features,
            y_bot,
            COL_FEATURES_W,
            ROW_H,
        )
    )

    parts.append(
        _plot_panel_svg(
            trajectory,
            x_plot,
            y_plot,
            COL_PLOT_W,
            CANVAS_H - 2 * PAD,
        )
    )

    parts.append("</svg>")
    return "\n".join(parts)
