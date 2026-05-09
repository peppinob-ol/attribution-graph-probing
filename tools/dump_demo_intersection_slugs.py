#!/usr/bin/env python3
"""Dump the demo cross-run intersection slug list per dataset.

The matched-random M-search only needs to cover pairs that appear in
T2_headline (the demo intersection). This tool replicates the
``DemoRegistry.get_allowed_slugs`` logic standalone and writes one JSON
list of allowed slugs per dataset to ``output/research/``.

Usage:
    python tools/dump_demo_intersection_slugs.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List, Set

REPO = Path(__file__).resolve().parents[1]
DEMO_APP = REPO / "demo"
if str(DEMO_APP) not in sys.path:
    sys.path.insert(0, str(DEMO_APP))

from app.data.loader import _is_dropdown_run  # type: ignore  # noqa: E402

OUTPUT_ROOT = REPO / "output"
OUT_DIR = REPO / "output" / "research"

DATASETS = [
    "book_characters_authors_batch",
    "paintings_painters_batch",
    "products_founders_batch",
    "usa_states_batch",
]


def _collect_run_slugs(run_dir: Path) -> Set[str]:
    by_source = run_dir / "by_source"
    if not by_source.exists():
        return set()
    return {
        d.name for d in by_source.iterdir()
        if d.is_dir() and any(d.glob("to_*.json"))
    }


def compute_allowed_slugs(dataset_dir: Path) -> Set[str]:
    runs_dir = dataset_dir / "_swaps" / "runs"
    if not runs_dir.is_dir():
        return set()
    visible_runs: List[Path] = []
    for run_dir in sorted(runs_dir.iterdir()):
        if not run_dir.is_dir():
            continue
        manifest_path = run_dir / "run_manifest.json"
        if not manifest_path.exists():
            continue
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not manifest.get("display_demo"):
            continue
        if not _is_dropdown_run(run_dir.name, manifest):
            continue
        visible_runs.append(run_dir)

    per_run: List[Set[str]] = []
    for r in visible_runs:
        slugs = _collect_run_slugs(r)
        if slugs:
            per_run.append(slugs)

    if not per_run:
        return set()
    return set.intersection(*per_run)


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    summary: Dict[str, int] = {}
    for ds in DATASETS:
        allowed = sorted(compute_allowed_slugs(OUTPUT_ROOT / ds))
        out_path = OUT_DIR / f"demo_intersection_slugs_{ds}.json"
        out_path.write_text(json.dumps(allowed, indent=2), encoding="utf-8")
        summary[ds] = len(allowed)
        print(f"  {ds:40s} {len(allowed):4d} slugs -> {out_path.name}")
    print("\n" + json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
