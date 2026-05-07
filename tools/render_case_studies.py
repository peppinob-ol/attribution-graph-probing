#!/usr/bin/env python3
"""Render the strip-layout SVG/PDF for every appendix case study.

Each entry in :data:`CASE_STUDIES` corresponds to one ``\\paragraph`` block
under the ``\\section{Case Studies}`` heading in
``paper/sections/appendix.tex``. The renderer writes one PDF (vector,
camera-ready) and one SVG (web-ready) per case under
``paper/figures/case_studies/``.

For most pairs the result file lives in the same swap run as ``features.json``
and only ``run`` needs specifying. Books pairs and the all-fields USA case
override either ``features_path`` or ``result_path`` because their result/
feature files live in different runs (or use the field-additivity
``__add_<variant>`` filename convention).
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.render_swap_svg import render_swap_intervention  # noqa: E402

OUTPUT_DIR = REPO_ROOT / "paper" / "figures" / "case_studies"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)


@dataclass(frozen=True)
class CaseStudy:
    """One appendix case-study figure to render.

    Attributes:
        batch: directory under ``output/`` (e.g. ``usa_states_batch``).
        run: swap run name under ``output/<batch>/_swaps/runs/``.
        swap_id: ``<src_slug>__to__<tgt_slug>``.
        result_path: optional override (relative to ``REPO_ROOT``) when the
            result filename uses the field-additivity ``__add_<variant>``
            suffix.
        features_path: optional override (relative to ``REPO_ROOT``) when
            ``features.json`` is in a different run from the result file.
        out_basename: stem of the produced files; both ``<stem>.svg`` and
            ``<stem>.pdf`` are written.
        category: ``"success"`` or ``"failure"`` (purely for logging).
        description: short tag printed during rendering.
    """

    batch: str
    run: str
    swap_id: str
    out_basename: str
    category: str
    description: str
    result_path: str | None = None
    features_path: str | None = None


CASE_STUDIES: tuple[CaseStudy, ...] = (
    # ---------------- Success cases (5) ---------------- #
    CaseStudy(
        batch="usa_states_batch",
        run="fullscale_usa_field_add",
        swap_id="colorado_colorado_springs__to__michigan_detroit",
        result_path=(
            "output/usa_states_batch/_swaps/runs/fullscale_usa_field_add/"
            "by_source/colorado_colorado_springs/to_michigan_detroit__add_state_capital.json"
        ),
        features_path=(
            "output/usa_states_batch/_swaps/runs/fullscale_usa_field_add/work/"
            "colorado_colorado_springs__to__michigan_detroit__add_state_capital/features.json"
        ),
        out_basename="strip_colorado_colorado_springs__to__michigan_detroit",
        category="success",
        description="USA: Colorado Springs -> Detroit (state+capital variant)",
    ),
    CaseStudy(
        batch="book_characters_authors_batch",
        run="20260318_042511_book_characters_authors_swap_mab-2_mam20_seed42_cfg-95907f082e",
        swap_id="holden_caulfield__to__katniss_everdeen",
        features_path=(
            "output/book_characters_authors_batch/_swaps/runs/fullscale_books_field_add/work/"
            "holden_caulfield__to__katniss_everdeen__add_book_author/features.json"
        ),
        out_basename="strip_holden_caulfield__to__katniss_everdeen",
        category="success",
        description="Books: Holden Caulfield -> Katniss Everdeen (book+author variant)",
    ),
    CaseStudy(
        batch="products_founders_batch",
        run="20260318_042902_products_founders_swap_mab-2_mam20_seed42_cfg-b7490709a8",
        swap_id="nike_shoes__to__model_s",
        features_path=(
            "output/products_founders_batch/_swaps/runs/fullscale_products_field_add/work/"
            "nike_shoes__to__model_s__add_company_founder/features.json"
        ),
        out_basename="strip_nike_shoes__to__model_s",
        category="success",
        description="Products: Nike -> Tesla (company+founder variant)",
    ),
    CaseStudy(
        batch="paintings_painters_batch",
        run="20260318_042730_paintings_painters_swap_mab-2_mam20_seed42_cfg-d2f15c0c83",
        swap_id="grande_jatte__to__water_lilies",
        features_path=(
            "output/paintings_painters_batch/_swaps/runs/fullscale_paintings_field_add/work/"
            "grande_jatte__to__water_lilies__add_painter_first_name/features.json"
        ),
        out_basename="strip_grande_jatte__to__water_lilies",
        category="success",
        description="Paintings: La Grande Jatte -> Water Lilies (painter+first_name variant)",
    ),
    CaseStudy(
        batch="usa_states_batch",
        run="fullscale_usa_field_add",
        swap_id="minnesota_minneapolis__to__florida_miami",
        result_path=(
            "output/usa_states_batch/_swaps/runs/fullscale_usa_field_add/"
            "by_source/minnesota_minneapolis/to_florida_miami__add_state_capital_city.json"
        ),
        features_path=(
            "output/usa_states_batch/_swaps/runs/fullscale_usa_field_add/work/"
            "minnesota_minneapolis__to__florida_miami__add_state_capital_city/features.json"
        ),
        out_basename="strip_minnesota_minneapolis__to__florida_miami",
        category="success",
        description="USA all-fields: Minnesota -> Florida (state+capital+city variant)",
    ),
    # ---------------- Failure cases (6) ---------------- #
    CaseStudy(
        batch="usa_states_batch",
        run="full_50states_v1",
        swap_id="kansas_wichita__to__new_hampshire_manchester",
        out_basename="strip_kansas_wichita__to__new_hampshire_manchester",
        category="failure",
        description="USA: Kansas/Wichita -> New Hampshire/Manchester (feature specificity)",
    ),
    CaseStudy(
        batch="usa_states_batch",
        run="full_50states_v1",
        swap_id="utah_provo__to__iowa_cedar_rapids",
        out_basename="strip_utah_provo__to__iowa_cedar_rapids",
        category="failure",
        description="USA: Utah/Provo -> Iowa/Cedar Rapids (rank-hit misalignment)",
    ),
    CaseStudy(
        batch="usa_states_batch",
        run="full_50states_v1",
        swap_id="ohio_cleveland__to__oklahoma_tulsa",
        out_basename="strip_ohio_cleveland__to__oklahoma_tulsa",
        category="failure",
        description="USA: Ohio/Cleveland -> Oklahoma/Tulsa (regime D, rescuable at lower M)",
    ),
    CaseStudy(
        batch="book_characters_authors_batch",
        run="20260318_042511_book_characters_authors_swap_mab-2_mam20_seed42_cfg-95907f082e",
        swap_id="scout_finch__to__huckleberry_finn",
        features_path=(
            "output/book_characters_authors_batch/_swaps/runs/fullscale_books_field_add/work/"
            "scout_finch__to__huckleberry_finn__add_book_author/features.json"
        ),
        out_basename="strip_scout_finch__to__huckleberry_finn",
        category="failure",
        description="Books: Scout Finch -> Huckleberry Finn (substring confound)",
    ),
    CaseStudy(
        batch="products_founders_batch",
        run="fullscale_products_field_add",
        swap_id="windows__to__oculus",
        result_path=(
            "output/products_founders_batch/_swaps/runs/fullscale_products_field_add/"
            "by_source/windows/to_oculus__add_company.json"
        ),
        features_path=(
            "output/products_founders_batch/_swaps/runs/fullscale_products_field_add/work/"
            "windows__to__oculus__add_company/features.json"
        ),
        out_basename="strip_windows__to__oculus",
        category="failure",
        description="Products: Windows -> Oculus (company-only amplifies the product 'Rift')",
    ),
    CaseStudy(
        batch="paintings_painters_batch",
        run="fullscale_paintings_field_add",
        swap_id="girl_pearl_earring__to__guernica",
        result_path=(
            "output/paintings_painters_batch/_swaps/runs/fullscale_paintings_field_add/"
            "by_source/girl_pearl_earring/to_guernica__add_painter_first_name.json"
        ),
        features_path=(
            "output/paintings_painters_batch/_swaps/runs/fullscale_paintings_field_add/work/"
            "girl_pearl_earring__to__guernica__add_painter_first_name/features.json"
        ),
        out_basename="strip_girl_pearl_earring__to__guernica",
        category="failure",
        description="Paintings: Girl with a Pearl Earring -> Guernica (painter+first_name variant)",
    ),
)


def render_one(case: CaseStudy) -> Path:
    """Render one case study to ``<OUTPUT_DIR>/<out_basename>.{svg,pdf}``."""
    import cairosvg

    swap_run_dir = REPO_ROOT / "output" / case.batch / "_swaps" / "runs" / case.run
    svg_out = OUTPUT_DIR / f"{case.out_basename}.svg"
    pdf_out = OUTPUT_DIR / f"{case.out_basename}.pdf"

    feats = (REPO_ROOT / case.features_path) if case.features_path else None
    result = (REPO_ROOT / case.result_path) if case.result_path else None

    svg = render_swap_intervention(
        swap_run_dir,
        case.swap_id,
        output_svg_path=svg_out,
        max_per_row=2,
        layout="strip",
        features_path=feats,
        result_path=result,
    )
    cairosvg.svg2pdf(bytestring=svg.encode("utf-8"), write_to=str(pdf_out))
    return pdf_out


def main() -> int:
    print(f"Rendering {len(CASE_STUDIES)} case studies into {OUTPUT_DIR}\n")
    for case in CASE_STUDIES:
        try:
            pdf = render_one(case)
            print(f"  [{case.category:7s}] {case.description}\n             -> {pdf.relative_to(REPO_ROOT)}")
        except Exception as exc:
            print(f"  [FAIL ] {case.description}: {exc}")
            return 1
    print("\nAll case studies rendered.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
