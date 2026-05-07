"""Smoke test for tools/render_swap_svg.py on the existing _swaps run.

Skipped automatically if the swap artifacts are not present.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.render_swap_svg import render_swap_intervention  # noqa: E402
from tools.circuit_svg_compact import _wrap_label  # noqa: E402

SWAP_RUN = REPO_ROOT / "output" / "usa_states_batch" / "_swaps" / "runs" / "full_50states_v1"


def _label_in_svg(svg: str, label: str) -> bool:
    """True if a (possibly wrapped) supernode label appears in the SVG markup."""
    if label in svg:
        return True
    # Compact mode wraps long labels across multiple <text> spans; check pieces.
    return all(piece in svg for piece in _wrap_label(label, max_chars=11))


@pytest.mark.skipif(
    not (SWAP_RUN / "work" / "california_oakland__to__texas_dallas").exists(),
    reason="full_50states_v1 swap run not present; skipping",
)
def test_render_california_to_texas_swap(tmp_path: Path):
    out = tmp_path / "ca_to_tx.svg"
    svg = render_swap_intervention(
        SWAP_RUN,
        "california_oakland__to__texas_dallas",
        output_svg_path=out,
    )

    # Layout: Emb: Oakland (bottom), then concept row (California, Sacramento) ablated,
    # then Say-row (Say (Sacramento), Say (California)) ablated. Replacements above each.
    assert out.is_file()
    # Compact mode -> portrait canvas (taller than wide), matching the reference figure.
    assert 'width="480"' in svg and 'height="640"' in svg
    assert _label_in_svg(svg, "Emb: Oakland")
    # All four ablated supernodes are present
    for name in ("California", "Sacramento", "Say (Sacramento)", "Say (California)"):
        assert _label_in_svg(svg, name), f"missing ablated supernode {name!r}"
    # All four amplified replacement supernodes are present
    for name in ("Texas", "Austin", "Say (Austin)", "Say (Texas)"):
        assert _label_in_svg(svg, name), f"missing amplified supernode {name!r}"
    # Intervention badges from swap config (M_ablate=-2, M_amplify=+20)
    assert "-2x" in svg
    assert "+20x" in svg
    # Activations are normalised to [0..100]%; not the categorical 0/100 we had before.
    # At least one ablated and one amplified should NOT be 0% / 100%.
    nontrivial_pct = re.findall(r">(\d+)%<", svg)
    assert any(0 < int(p) < 100 for p in nontrivial_pct), (
        "expected at least one fractional activation %, got " + str(nontrivial_pct)
    )
    # Prompt + at least one steered top-token from the result JSON
    assert "Oakland" in svg
    assert "College" in svg  # steered first token for this swap


@pytest.mark.skipif(
    not (SWAP_RUN / "work" / "texas_dallas__to__california_oakland").exists(),
    reason="full_50states_v1 swap run not present; skipping",
)
def test_render_texas_to_california_swap(tmp_path: Path):
    out = tmp_path / "tx_to_ca.svg"
    svg = render_swap_intervention(
        SWAP_RUN,
        "texas_dallas__to__california_oakland",
        output_svg_path=out,
    )

    assert out.is_file()
    assert _label_in_svg(svg, "Emb: Dallas")
    for name in ("Texas", "Austin", "Say (Austin)", "Say (Texas)"):
        assert _label_in_svg(svg, name), f"missing ablated supernode {name!r}"
    for name in ("California", "Sacramento", "Say (Sacramento)", "Say (California)"):
        assert _label_in_svg(svg, name), f"missing amplified supernode {name!r}"
    # The reverse swap should produce Sacramento as the steered top token
    assert "Sacramento" in svg


@pytest.mark.skipif(
    not (SWAP_RUN / "work" / "indiana_fort_wayne__to__minnesota_minneapolis").exists(),
    reason="indiana->minnesota pair not present; skipping",
)
def test_render_v2_layout_with_position_plot(tmp_path: Path):
    """v2 layout: top strip, smaller header, graph, position-axis trajectory plot.

    Shares the same plot panel as the strip layout, so the assertions mirror
    those of ``test_render_strip_layout_with_position_plot``.
    """
    out = tmp_path / "v2.svg"
    svg = render_swap_intervention(
        SWAP_RUN,
        "indiana_fort_wayne__to__minnesota_minneapolis",
        output_svg_path=out,
        max_per_row=2,
        layout="v2",
    )

    assert out.is_file()
    # Portrait, taller canvas to accommodate top strip + graph + plot.
    assert 'width="480"' in svg and 'height="820"' in svg
    # Top strip headers
    assert "PROMPT" in svg
    assert "ORIGINAL" in svg and "PREDICTION" in svg
    assert "AFTER" in svg and "INTERVENTION" in svg
    # Smaller graph header still present
    assert "GRAPH &amp; INTERVENTIONS" in svg
    # Trajectory plot artefacts (shared with the strip layout):
    # title, y-axis caption, x-axis caption, and the unsteered<->steered annotation.
    assert "TARGET TRAJECTORY" in svg
    assert "Next Token Probability" in svg
    assert "Generated token position" in svg
    assert "unsteered" in svg
    assert "steered" in svg
    # At least one of the steered-generated tokens should appear as a tick label.
    assert "Saint" in svg or "Minnesota" in svg


@pytest.mark.skipif(
    not (SWAP_RUN / "work" / "indiana_fort_wayne__to__minnesota_minneapolis").exists(),
    reason="indiana->minnesota pair not present; skipping",
)
def test_render_strip_layout_with_position_plot(tmp_path: Path):
    """Strip layout: horizontal cards + outputs + features + per-position trajectory."""
    out = tmp_path / "strip.svg"
    svg = render_swap_intervention(
        SWAP_RUN,
        "indiana_fort_wayne__to__minnesota_minneapolis",
        output_svg_path=out,
        max_per_row=2,
        layout="strip",
    )

    assert out.is_file()
    # Landscape canvas (wider than tall) for the horizontal strip layout.
    assert 'width="1000"' in svg and 'height="220"' in svg
    # Panel headers
    assert "SOURCE" in svg and "TARGET" in svg
    assert "DEFAULT OUTPUT" in svg and "STEERED OUTPUT" in svg
    assert "ABLATED" in svg and "AMPLIFIED" in svg
    assert "TARGET TRAJECTORY" in svg
    # Source / target capitals appear as headlines
    assert "Indianapolis" in svg
    assert "Saint Paul" in svg
    # Intervention badges
    assert "-2x" in svg
    assert "+20x" in svg
    # Trajectory x-axis caption + at least one of the steered-generated tokens
    assert "Generated token position" in svg
    assert "Saint" in svg
    assert "Minnesota" in svg
    # The padded [unsteered] baseline column sits left of the steered tokens
    # and is annotated above the plot rather than as a tick label.
    assert "unsteered" in svg
    assert "steered" in svg


PRODUCTS_RUN = REPO_ROOT / "output" / "products_founders_batch" / "_swaps" / "runs" / "fullscale_products_labeled"


@pytest.mark.skipif(
    not (PRODUCTS_RUN / "work" / "nike_shoes__to__model_s").exists(),
    reason="Products nike->model_s pair not present; skipping",
)
def test_render_strip_layout_for_products_domain(tmp_path: Path):
    """Strip renderer must adapt the entity-card schema for non-USA domains.

    Products meta uses ``product``/``company``/``founder`` (not
    ``state``/``capital``/``city``); the headline should be the founder
    (the answer the steered model is supposed to produce) and the body
    should show the company and product fields.
    """
    out = tmp_path / "products_strip.svg"
    svg = render_swap_intervention(
        PRODUCTS_RUN,
        "nike_shoes__to__model_s",
        output_svg_path=out,
        max_per_row=2,
        layout="strip",
    )

    assert out.is_file()
    # Source / target headlines = answer fields (founder names)
    assert "Phil Knight" in svg
    assert "Elon Musk" in svg
    # Body fields render the domain's two non-answer slots
    assert "company" in svg and "product" in svg
    # Source/target accent words appear in the highlighted output text
    assert "Nike" in svg
    assert "Tesla" in svg or "Model" in svg
