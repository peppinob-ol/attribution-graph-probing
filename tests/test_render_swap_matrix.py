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
    assert "hits: 3/6" in svg


def test_slug_to_state_handles_compound_names():
    assert rsm._slug_to_state("california_oakland") == "CA"
    assert rsm._slug_to_state("new_york_new_york_city") == "NY"
    assert rsm._slug_to_state("south_carolina_charleston") == "SC"
    assert rsm._slug_to_state("rhode_island_warwick") == "RI"
    assert rsm._slug_to_state("west_virginia_huntington") == "WV"
