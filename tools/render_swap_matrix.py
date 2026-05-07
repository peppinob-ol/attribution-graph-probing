"""Render a 50x50 swap success matrix as an SVG.

The colours match ``circuit_svg_v2`` (grey ``#ececec``/``#9a9a9a`` for misses
and warm tones for hits), so the matrix sits naturally next to the v2 circuit
diagrams in a paper figure.

Two rendering modes:

1. **Binary**: ``_matrix.csv`` only -- single orange shade for every hit.

2. **Variant-coloured** (``--winners winners.json``): each hit cell is
   coloured by the *field subset* of the winning steering combination.
   Default 3-field (state+capital+city) cells stay chocolate orange; smaller
   subsets get distinct warm hues. The winners JSON is the output of
   ``tools/export_swap_winners.py`` (or the demo's
   ``CrossRunBestAggregator.get_best_matrix``).

CLI:
    # binary
    python -m tools.render_swap_matrix \
        output/.../_matrix.csv --output paper/figures/swap_matrix.svg

    # variant-coloured
    python -m tools.render_swap_matrix \
        output/.../_matrix_best_across.csv \
        --winners output/.../winners_best_across.json \
        --output paper/figures/swap_matrix.svg
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

# Palette mirrors tools/circuit_svg_v2.py
COLOR_BG = "#ffffff"
COLOR_BORDER = "#d4d4d4"
COLOR_LABEL = "#555"

CELL_FAIL = "#ececec"     # light grey -- miss
CELL_SUCCESS = "#D2691E"  # chocolate orange -- generic hit (binary mode)
CELL_DIAG = "#2a2a2a"     # dark grey -- diagonal / NaN

# Variant-mode palette: Okabe-Ito colorblind-safe categorical palette
# (Wong, Nature Methods 2011), widely used in scientific publications and
# robust under deuteranopia, protanopia and tritanopia. The 3-field default
# uses the strongest warm hue (vermillion) so it still reads as the canonical
# "active" colour next to the v2 chocolate-orange diagrams; remaining hues
# fan out across warm/cool space for unambiguous separation.
FIELD_PALETTE: list[tuple[tuple[str, ...], str, str]] = [
    (("capital", "city", "state"), "#D55E00", "state+capital+city"),  # vermillion
    (("capital", "state"),         "#E69F00", "state+capital"),       # orange
    (("city", "state"),            "#CC79A7", "state+city"),          # reddish purple
    (("capital", "city"),          "#009E73", "capital+city"),        # bluish green
    (("state",),                   "#56B4E9", "state only"),          # sky blue
    (("capital",),                 "#0072B2", "capital only"),        # blue
    (("city",),                    "#F0E442", "city only"),           # yellow
]
FIELD_OTHER_COLOR = "#888888"  # winners with no recorded fields (e.g. m-tuned only)


def _field_key(fields: object) -> tuple[str, ...] | None:
    """Normalise a ``fields_used`` value to a sorted tuple key.

    Returns ``None`` when no field information is available.
    """
    if fields is None:
        return None
    if isinstance(fields, list):
        if not fields:
            return None
        return tuple(sorted(str(f) for f in fields))
    if isinstance(fields, str):
        return (fields,)
    return None


def _field_color(fields: object) -> tuple[str, str]:
    """Return (fill, label) for a winner's ``fields_used`` payload."""
    key = _field_key(fields)
    if key is None:
        return FIELD_OTHER_COLOR, "other"
    for combo, color, label in FIELD_PALETTE:
        if key == combo:
            return color, label
    return FIELD_OTHER_COLOR, "other"


def _load_winners(path: Path) -> dict[str, dict[str, dict]]:
    with path.open(encoding="utf-8") as fh:
        data = json.load(fh)
    winners = data.get("winners") if isinstance(data, dict) and "winners" in data else data
    if not isinstance(winners, dict):
        raise ValueError(f"unexpected winners JSON shape in {path}")
    return winners

STATE_ABBREV = {
    "alabama": "AL", "alaska": "AK", "arizona": "AZ", "arkansas": "AR",
    "california": "CA", "colorado": "CO", "connecticut": "CT", "delaware": "DE",
    "florida": "FL", "georgia": "GA", "hawaii": "HI", "idaho": "ID",
    "illinois": "IL", "indiana": "IN", "iowa": "IA", "kansas": "KS",
    "kentucky": "KY", "louisiana": "LA", "maine": "ME", "maryland": "MD",
    "massachusetts": "MA", "michigan": "MI", "minnesota": "MN",
    "mississippi": "MS", "missouri": "MO", "montana": "MT", "nebraska": "NE",
    "nevada": "NV", "new_hampshire": "NH", "new_jersey": "NJ",
    "new_mexico": "NM", "new_york": "NY", "north_carolina": "NC",
    "north_dakota": "ND", "ohio": "OH", "oklahoma": "OK", "oregon": "OR",
    "pennsylvania": "PA", "rhode_island": "RI", "south_carolina": "SC",
    "south_dakota": "SD", "tennessee": "TN", "texas": "TX", "utah": "UT",
    "vermont": "VT", "virginia": "VA", "washington": "WA",
    "west_virginia": "WV", "wisconsin": "WI", "wyoming": "WY",
}


def _slug_to_state(slug: str) -> str:
    parts = slug.split("_")
    if parts[0] in {"new", "north", "south", "west", "rhode"}:
        key = "_".join(parts[:2])
    else:
        key = parts[0]
    return STATE_ABBREV.get(key, key[:2].upper())


def _load_matrix(csv_path: Path) -> tuple[list[str], list[str], list[list[float | None]]]:
    """Return (row_slugs, col_slugs, matrix) from a swap matrix CSV.

    Matrix cells: ``1.0``/``0.0`` for hit/miss, ``None`` for NaN/empty
    (diagonal or not-run).
    """
    with csv_path.open(newline="") as fh:
        reader = csv.reader(fh)
        header = next(reader)
        col_slugs = header[1:]
        row_slugs: list[str] = []
        rows: list[list[float | None]] = []
        for line in reader:
            row_slugs.append(line[0])
            cells: list[float | None] = []
            for v in line[1:]:
                v = v.strip()
                if v == "" or v.lower() == "nan":
                    cells.append(None)
                else:
                    try:
                        cells.append(float(v))
                    except ValueError:
                        cells.append(None)
            rows.append(cells)
    return row_slugs, col_slugs, rows


def render_matrix_svg(
    csv_path: Path,
    *,
    cell_size: int = 12,
    pad: int = 8,
    label_w: int = 42,
    label_h: int = 52,
    legend_h: int = 36,
    winners: dict[str, dict[str, dict]] | None = None,
) -> str:
    """Render the matrix SVG.

    When *winners* is provided, hit cells are coloured by the ``fields_used``
    of the winning configuration (variant mode), and the legend lists every
    observed field combination with its count. Otherwise hits use a single
    chocolate orange (binary mode).
    """
    row_slugs, col_slugs, matrix = _load_matrix(csv_path)
    n_rows = len(row_slugs)
    n_cols = len(col_slugs)

    grid_x = pad + label_w
    grid_y = pad + label_h
    grid_w = n_cols * cell_size
    grid_h = n_rows * cell_size

    canvas_w = grid_x + grid_w + pad
    if winners is not None:
        # 3 columns x 3 rows -> 9 slots, ~22px row pitch + 22px headroom.
        legend_h = max(legend_h, 22 * 3 + 24)
    canvas_h = grid_y + grid_h + pad + legend_h

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_w}" '
        f'height="{canvas_h}" viewBox="0 0 {canvas_w} {canvas_h}">'
    )
    parts.append(
        f'<rect x="0" y="0" width="{canvas_w}" height="{canvas_h}" '
        f'fill="{COLOR_BG}"/>'
    )
    parts.append(
        f'<rect x="0.5" y="0.5" width="{canvas_w - 1}" '
        f'height="{canvas_h - 1}" fill="none" stroke="{COLOR_BORDER}" rx="6" ry="6"/>'
    )

    label_font_size = 13
    # -70deg rotation (vs -60deg) opens the perpendicular gap between adjacent
    # column labels to cell_size*sin(70deg) ~= 11.3 user-units, which clears
    # the ~9.1 user-unit cap-height of 13pt Menlo without overlap.
    col_rotation = -70

    for j, slug in enumerate(col_slugs):
        cx = grid_x + j * cell_size + cell_size / 2
        cy = grid_y - 6
        abbrev = _slug_to_state(slug)
        parts.append(
            f'<text x="{cx:.1f}" y="{cy:.1f}" fill="{COLOR_LABEL}" '
            f'font-family="Menlo, Consolas, monospace" font-size="{label_font_size}" '
            f'text-anchor="start" '
            f'transform="rotate({col_rotation} {cx:.1f} {cy:.1f})">{abbrev}</text>'
        )

    for i, slug in enumerate(row_slugs):
        cx = grid_x - 6
        cy = grid_y + i * cell_size + cell_size / 2 + 4.5
        abbrev = _slug_to_state(slug)
        parts.append(
            f'<text x="{cx:.1f}" y="{cy:.1f}" fill="{COLOR_LABEL}" '
            f'font-family="Menlo, Consolas, monospace" font-size="{label_font_size}" '
            f'text-anchor="end">{abbrev}</text>'
        )

    field_counts: dict[str, int] = {}
    for i, row in enumerate(matrix):
        src_slug = row_slugs[i]
        for j, val in enumerate(row):
            x = grid_x + j * cell_size
            y = grid_y + i * cell_size
            if val is None:
                fill = CELL_DIAG
            elif val >= 0.5:
                if winners is not None:
                    meta = (winners.get(src_slug) or {}).get(col_slugs[j]) or {}
                    fill, label = _field_color(meta.get("fields_used"))
                    field_counts[label] = field_counts.get(label, 0) + 1
                else:
                    fill = CELL_SUCCESS
            else:
                fill = CELL_FAIL
            parts.append(
                f'<rect x="{x}" y="{y}" width="{cell_size - 1}" '
                f'height="{cell_size - 1}" fill="{fill}"/>'
            )

    parts.append(
        f'<rect x="{grid_x - 0.5}" y="{grid_y - 0.5}" width="{grid_w + 1}" '
        f'height="{grid_h + 1}" fill="none" stroke="{COLOR_BORDER}" '
        f'stroke-width="1"/>'
    )

    legend_font_size = 13
    box = 14
    legend_top = grid_y + grid_h + 22
    # Align legend's first column with the matrix grid (so the swatches sit
    # under the matrix's first column).
    legend_left = grid_x

    if winners is None:
        legend_y = legend_top
        legend_x = legend_left
        text_y = legend_y + 1
        parts.append(
            f'<rect x="{legend_x}" y="{legend_y - box + 2}" width="{box}" '
            f'height="{box}" fill="{CELL_SUCCESS}"/>'
            f'<text x="{legend_x + box + 6}" y="{text_y}" '
            f'fill="{COLOR_LABEL}" font-family="Arial, sans-serif" '
            f'font-size="{legend_font_size}">'
            f'capital redirect (top-1 = target)</text>'
        )
        legend_x2 = legend_x + 250
        parts.append(
            f'<rect x="{legend_x2}" y="{legend_y - box + 2}" width="{box}" '
            f'height="{box}" fill="{CELL_FAIL}" stroke="{COLOR_BORDER}"/>'
            f'<text x="{legend_x2 + box + 6}" y="{text_y}" '
            f'fill="{COLOR_LABEL}" font-family="Arial, sans-serif" '
            f'font-size="{legend_font_size}">miss</text>'
        )
        legend_x3 = legend_x2 + 75
        parts.append(
            f'<rect x="{legend_x3}" y="{legend_y - box + 2}" width="{box}" '
            f'height="{box}" fill="{CELL_DIAG}"/>'
            f'<text x="{legend_x3 + box + 6}" y="{text_y}" '
            f'fill="{COLOR_LABEL}" font-family="Arial, sans-serif" '
            f'font-size="{legend_font_size}">'
            f'diagonal / not run</text>'
        )
    else:
        # Variant legend: 7 field combinations (+ optional "other") plus miss
        # and diagonal markers. Laid out as 3 columns x 3 rows so labels never
        # collide.
        legend_entries: list[tuple[str, str]] = [
            (color, f"{label}  ({field_counts.get(label, 0)})")
            for _combo, color, label in FIELD_PALETTE
        ]
        if field_counts.get("other"):
            legend_entries.append(
                (FIELD_OTHER_COLOR, f"other ({field_counts['other']})")
            )
        legend_entries.append((CELL_FAIL, "miss"))
        legend_entries.append((CELL_DIAG, "diagonal / not run"))

        n_cols_legend = 3
        col_w = (canvas_w - legend_left - pad) / n_cols_legend
        for idx, (color, label) in enumerate(legend_entries):
            r, c = idx // n_cols_legend, idx % n_cols_legend
            x = legend_left + c * col_w
            y = legend_top + r * (box + 8)
            text_y = y + 1
            stroke = f' stroke="{COLOR_BORDER}"' if color == CELL_FAIL else ""
            parts.append(
                f'<rect x="{x:.1f}" y="{y - box + 2:.1f}" width="{box}" '
                f'height="{box}" fill="{color}"{stroke}/>'
                f'<text x="{x + box + 6:.1f}" y="{text_y:.1f}" '
                f'fill="{COLOR_LABEL}" font-family="Arial, sans-serif" '
                f'font-size="{legend_font_size}">{label}</text>'
            )

    parts.append("</svg>")
    return "\n".join(parts)


def _cli() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("matrix_csv", type=str, help="Path to swap matrix CSV.")
    p.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output SVG path (default: alongside CSV as swap_matrix.svg).",
    )
    p.add_argument(
        "--winners",
        type=str,
        default=None,
        help=(
            "Path to a winners JSON ({src: {tgt: {fields_used: ...}}}). When "
            "provided, hit cells are coloured by the winning field subset."
        ),
    )
    p.add_argument(
        "--cell-size", type=int, default=12, help="Cell size in pixels (default 12)."
    )
    args = p.parse_args()

    csv_path = Path(args.matrix_csv).resolve()
    if not csv_path.exists():
        raise SystemExit(f"matrix CSV not found: {csv_path}")
    winners = None
    if args.winners:
        winners_path = Path(args.winners).resolve()
        if not winners_path.exists():
            raise SystemExit(f"winners JSON not found: {winners_path}")
        winners = _load_winners(winners_path)

    out_path = (
        Path(args.output).resolve()
        if args.output
        else csv_path.with_name("swap_matrix.svg")
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    svg = render_matrix_svg(
        csv_path, cell_size=args.cell_size, winners=winners
    )
    out_path.write_text(svg, encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
