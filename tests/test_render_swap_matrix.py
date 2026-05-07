"""Smoke tests for tools.render_swap_matrix."""
from __future__ import annotations

from pathlib import Path

import pytest

from tools import render_swap_matrix as rsm


@pytest.fixture
def matrix_csv(tmp_path: Path) -> Path:
    csv = tmp_path / "tiny_matrix.csv"
    csv.write_text(
        "from_slug,alabama_birmingham,alaska_anchorage,arizona_tucson\n"
        "alabama_birmingham,,1.0,0.0\n"
        "alaska_anchorage,1.0,,0.0\n"
        "arizona_tucson,0.0,1.0,\n",
        encoding="utf-8",
    )
    return csv


def test_load_matrix_handles_blank_diagonals(matrix_csv: Path):
    rows, cols, mat = rsm._load_matrix(matrix_csv)
    assert rows == cols
    assert len(rows) == 3
    for i in range(3):
        assert mat[i][i] is None
    assert mat[0][1] == 1.0
    assert mat[0][2] == 0.0


def test_render_matrix_produces_valid_svg(matrix_csv: Path):
    svg = rsm.render_matrix_svg(matrix_csv, cell_size=12)
    assert svg.startswith('<svg')
    assert svg.rstrip().endswith('</svg>')
    assert rsm.CELL_SUCCESS in svg
    assert rsm.CELL_FAIL in svg
    assert rsm.CELL_DIAG in svg
    assert "AL" in svg
    assert "AZ" in svg
    # Title row and "hits" summary were intentionally removed: matrix now relies
    # on the surrounding LaTeX caption for that information.
    assert "hits:" not in svg
    assert "BEST ACROSS RUNS" not in svg.upper()


def test_slug_to_state_handles_compound_names():
    assert rsm._slug_to_state("california_oakland") == "CA"
    assert rsm._slug_to_state("new_york_new_york_city") == "NY"
    assert rsm._slug_to_state("south_carolina_charleston") == "SC"
    assert rsm._slug_to_state("rhode_island_warwick") == "RI"
    assert rsm._slug_to_state("west_virginia_huntington") == "WV"


def test_field_color_palette_lookup():
    """Palette is Okabe-Ito (colorblind-safe). Verify a few key lookups."""
    fill_default, label_default = rsm._field_color(["state", "capital", "city"])
    assert fill_default == "#D55E00"  # vermillion
    assert label_default == "state+capital+city"

    fill_sc, label_sc = rsm._field_color(["state", "capital"])
    assert fill_sc == "#E69F00"  # orange
    assert label_sc == "state+capital"

    fill_state, label_state = rsm._field_color(["state"])
    assert fill_state == "#56B4E9"  # sky blue
    assert label_state == "state only"

    fill_other, label_other = rsm._field_color(None)
    assert fill_other == rsm.FIELD_OTHER_COLOR
    assert label_other == "other"


def test_palette_is_okabe_ito_colorblind_safe():
    """Every field combination uses a distinct Okabe-Ito hue."""
    okabe_ito = {
        "#D55E00",  # vermillion
        "#E69F00",  # orange
        "#CC79A7",  # reddish purple
        "#009E73",  # bluish green
        "#56B4E9",  # sky blue
        "#0072B2",  # blue
        "#F0E442",  # yellow
    }
    palette_colors = {color for _combo, color, _label in rsm.FIELD_PALETTE}
    assert palette_colors == okabe_ito
    # "other" is a neutral grey distinct from the diagonal black and the
    # light-grey miss cell so the three categories cannot collide visually.
    assert rsm.FIELD_OTHER_COLOR not in {rsm.CELL_DIAG, rsm.CELL_FAIL}


def test_render_with_winners_colors_by_field_subset(matrix_csv: Path):
    winners = {
        "alabama_birmingham": {
            "alaska_anchorage": {"fields_used": ["state", "capital", "city"]},
        },
        "alaska_anchorage": {
            "alabama_birmingham": {"fields_used": ["state"]},
        },
        "arizona_tucson": {
            "alaska_anchorage": {"fields_used": ["capital", "city"]},
        },
    }
    svg = rsm.render_matrix_svg(matrix_csv, cell_size=12, winners=winners)
    assert svg.startswith('<svg')
    assert "#D55E00" in svg  # 3-field default fill (vermillion)
    assert "#56B4E9" in svg  # state-only fill (sky blue)
    assert "#009E73" in svg  # capital+city fill (bluish green)
    assert "state+capital+city" in svg
    assert "state only" in svg
    assert "miss" in svg
    assert "diagonal / not run" in svg


def test_load_winners_accepts_wrapped_or_flat_json(tmp_path: Path):
    flat = tmp_path / "flat.json"
    flat.write_text(
        '{"a": {"b": {"fields_used": ["state"]}}}', encoding="utf-8"
    )
    assert rsm._load_winners(flat) == {"a": {"b": {"fields_used": ["state"]}}}

    wrapped = tmp_path / "wrapped.json"
    wrapped.write_text(
        '{"winners": {"a": {"b": {"fields_used": ["city"]}}}}',
        encoding="utf-8",
    )
    assert rsm._load_winners(wrapped) == {"a": {"b": {"fields_used": ["city"]}}}
