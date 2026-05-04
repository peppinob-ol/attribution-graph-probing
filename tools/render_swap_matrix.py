"""Render a 50x50 swap success matrix as an SVG with a grey-orange palette.

The colours match ``circuit_svg_v2`` (grey ``#ececec``/``#9a9a9a`` for failure
and chocolate ``#D2691E`` for success), so the matrix sits naturally next to
the v2 circuit diagrams in a paper figure.

Input is a ``_matrix.csv`` produced by the swap pipeline: a square table with
state slugs as both rows and columns, ``1.0`` for a successful swap, ``0.0``
for a miss, blank for the diagonal / not-run.

CLI:
    python -m tools.render_swap_matrix \
        output/usa_states_batch/_swaps/runs/full_50states_v1/_matrix.csv \
        --output paper/figures/swap_matrix.svg
"""
from __future__ import annotations

import argparse
import csv
from pathlib import Path

# Palette mirrors tools/circuit_svg_v2.py
COLOR_BG = "#ffffff"
COLOR_CARD = "#ffffff"
COLOR_BORDER = "#d4d4d4"
COLOR_LABEL = "#555"
COLOR_TITLE = "#333"
COLOR_GRID = "#f0f0f0"

CELL_FAIL = "#ececec"     # light grey -- "0" cells
CELL_SUCCESS = "#D2691E"  # chocolate orange -- "1" cells
CELL_DIAG = "#2a2a2a"     # dark grey -- diagonal / NaN
CELL_DIAG_DOT = "#555"

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
    title: str = "Source -> Target swap outcomes",
    cell_size: int = 12,
    pad: int = 8,
    label_w: int = 28,
    label_h: int = 36,
    title_h: int = 22,
    legend_h: int = 22,
) -> str:
    row_slugs, col_slugs, matrix = _load_matrix(csv_path)
    n_rows = len(row_slugs)
    n_cols = len(col_slugs)

    grid_x = pad + label_w
    grid_y = pad + title_h + label_h
    grid_w = n_cols * cell_size
    grid_h = n_rows * cell_size

    canvas_w = grid_x + grid_w + pad
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

    parts.append(
        f'<text x="{grid_x}" y="{pad + 14}" fill="{COLOR_TITLE}" '
        f'font-family="Arial, sans-serif" font-size="11" font-weight="bold" '
        f'letter-spacing="1.0px">{title.upper()}</text>'
    )

    for j, slug in enumerate(col_slugs):
        cx = grid_x + j * cell_size + cell_size / 2
        cy = grid_y - 4
        abbrev = _slug_to_state(slug)
        parts.append(
            f'<text x="{cx:.1f}" y="{cy:.1f}" fill="{COLOR_LABEL}" '
            f'font-family="Menlo, Consolas, monospace" font-size="7" '
            f'text-anchor="start" '
            f'transform="rotate(-60 {cx:.1f} {cy:.1f})">{abbrev}</text>'
        )

    for i, slug in enumerate(row_slugs):
        cx = grid_x - 4
        cy = grid_y + i * cell_size + cell_size / 2 + 2.5
        abbrev = _slug_to_state(slug)
        parts.append(
            f'<text x="{cx:.1f}" y="{cy:.1f}" fill="{COLOR_LABEL}" '
            f'font-family="Menlo, Consolas, monospace" font-size="7" '
            f'text-anchor="end">{abbrev}</text>'
        )

    for i, row in enumerate(matrix):
        for j, val in enumerate(row):
            x = grid_x + j * cell_size
            y = grid_y + i * cell_size
            if val is None:
                fill = CELL_DIAG
            elif val >= 0.5:
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

    legend_y = grid_y + grid_h + 14
    legend_x = grid_x
    box = 10
    parts.append(
        f'<rect x="{legend_x}" y="{legend_y - box + 2}" width="{box}" '
        f'height="{box}" fill="{CELL_SUCCESS}"/>'
        f'<text x="{legend_x + box + 4}" y="{legend_y + 4}" '
        f'fill="{COLOR_LABEL}" font-family="Arial, sans-serif" font-size="8">'
        f'capital redirect (top-1 = target)</text>'
    )
    legend_x2 = legend_x + 158
    parts.append(
        f'<rect x="{legend_x2}" y="{legend_y - box + 2}" width="{box}" '
        f'height="{box}" fill="{CELL_FAIL}" stroke="{COLOR_BORDER}"/>'
        f'<text x="{legend_x2 + box + 4}" y="{legend_y + 4}" '
        f'fill="{COLOR_LABEL}" font-family="Arial, sans-serif" font-size="8">miss</text>'
    )
    legend_x3 = legend_x2 + 60
    parts.append(
        f'<rect x="{legend_x3}" y="{legend_y - box + 2}" width="{box}" '
        f'height="{box}" fill="{CELL_DIAG}"/>'
        f'<text x="{legend_x3 + box + 4}" y="{legend_y + 4}" '
        f'fill="{COLOR_LABEL}" font-family="Arial, sans-serif" font-size="8">'
        f'diagonal / not run</text>'
    )

    n_total = sum(1 for row in matrix for v in row if v is not None)
    n_hits = sum(1 for row in matrix for v in row if v is not None and v >= 0.5)
    summary = f"hits: {n_hits}/{n_total} ({n_hits / max(1, n_total):.0%})"
    parts.append(
        f'<text x="{canvas_w - pad - 4}" y="{legend_y + 4}" fill="{COLOR_LABEL}" '
        f'font-family="Menlo, Consolas, monospace" font-size="8" '
        f'text-anchor="end">{summary}</text>'
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
        "--title",
        type=str,
        default="Source -> Target swap outcomes",
        help="Plot title rendered in the corner.",
    )
    p.add_argument(
        "--cell-size", type=int, default=12, help="Cell size in pixels (default 12)."
    )
    args = p.parse_args()

    csv_path = Path(args.matrix_csv).resolve()
    if not csv_path.exists():
        raise SystemExit(f"matrix CSV not found: {csv_path}")
    out_path = (
        Path(args.output).resolve()
        if args.output
        else csv_path.with_name("swap_matrix.svg")
    )
    out_path.parent.mkdir(parents=True, exist_ok=True)
    svg = render_matrix_svg(csv_path, title=args.title, cell_size=args.cell_size)
    out_path.write_text(svg, encoding="utf-8")
    print(f"wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(_cli())
