"""
Aggregate smoke-test SwapStats across the 4 Dallas conditions.

Walks each `output/usa_states_fact_batch/_swap_conditions/{cond}/_swaps/runs/{run}/by_source/texas_dallas/to_*.json`
and pulls the same metrics the main pipeline records:
  - exact_match.from_suppressed
  - exact_match.steered_has_to_answer (capital hit, strict)
  - exact_match.steered_has_to_answer_fuzzy
  - first_token.steered_prob (top-1 probability after intervention)
  - target_in_topk.to_answer_in_steered_topk (target token's prob in steered top-k)
  - interventions.ablate_count, amplify_count

Also computes a "Concept-Token Hit Rate" (CTHR): fraction of (target, variant)
pairs where the target's capital appears in steered output.

Outputs:
  - output/research/smoke_swap_results.csv  (one row per condition × pair × variant)
  - output/research/smoke_swap_summary.csv  (condition × variant; mean/std)
  - print summary
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Dict, List

import pandas as pd

REPO = Path(__file__).resolve().parent.parent
COND_ROOT = REPO / "output" / "usa_states_fact_batch" / "_swap_conditions"
OUT_DIR = REPO / "output" / "research"
OUT_DIR.mkdir(parents=True, exist_ok=True)

CONDITIONS = ["human_dallas", "auto_dallas", "auto_top21_dallas", "shuffled_labels_dallas"]
VARIANT_NAMES = [
    "add_state",
    "add_capital",
    "add_city",
    "add_state_capital",
    "add_state_city",
    "add_capital_city",
    "add_state_capital_city",
]


def latest_run(cond_dir: Path) -> Path | None:
    runs = sorted((cond_dir / "_swaps" / "runs").glob("2026*"))
    return runs[-1] if runs else None


def parse_filename(p: Path) -> Dict[str, str]:
    """to_california_oakland__add_state.json -> dict with to_slug + variant."""
    name = p.stem
    m = re.match(r"^to_(?P<to>[a-z0-9_]+?)__(?P<var>add_[a-z_]+)$", name)
    if m:
        return {"to_slug": m.group("to"), "variant": m.group("var")}
    m2 = re.match(r"^to_(?P<to>[a-z0-9_]+)$", name)
    if m2:
        return {"to_slug": m2.group("to"), "variant": ""}
    return {"to_slug": "", "variant": ""}


def load_swap_record(p: Path) -> Dict[str, float]:
    d = json.loads(p.read_text())
    ev = d.get("evaluation", {})
    em = ev.get("exact_match", {})
    ft = ev.get("first_token", {})
    tk = ev.get("target_in_topk", {})
    iv = d.get("interventions", {})
    return {
        "ablate_count": iv.get("ablate_count", 0),
        "amplify_count": iv.get("amplify_count", 0),
        "total_count": iv.get("total_count", 0),
        "from_suppressed": int(bool(em.get("from_suppressed"))),
        "to_capital_hit": int(bool(em.get("steered_has_to_answer"))),
        "to_capital_hit_fuzzy": int(bool(em.get("steered_has_to_answer_fuzzy"))),
        "first_token_matches_target": int(bool(em.get("first_token_matches_target"))),
        "first_token_steered": ft.get("steered", ""),
        "first_token_steered_prob": ft.get("steered_prob", 0.0),
        "to_in_steered_topk_prob": tk.get("to_answer_in_steered_topk") or 0.0,
        "from_in_steered_topk_prob": tk.get("from_answer_in_steered_topk") or 0.0,
        "to_answer": ev.get("to_answer", ""),
        "from_answer": ev.get("from_answer", ""),
    }


def collect_condition(cond: str) -> pd.DataFrame:
    cdir = COND_ROOT / cond
    run = latest_run(cdir)
    if run is None:
        return pd.DataFrame()
    rows = []
    for src_dir in (run / "by_source").iterdir():
        for f in sorted(src_dir.glob("to_*.json")):
            meta = parse_filename(f)
            if not meta["to_slug"]:
                continue
            rec = load_swap_record(f)
            rec["condition"] = cond
            rec["from_slug"] = src_dir.name
            rec["to_slug"] = meta["to_slug"]
            rec["variant"] = meta["variant"]
            rec["run_id"] = run.name
            rows.append(rec)
    return pd.DataFrame(rows)


def main():
    all_dfs = [collect_condition(c) for c in CONDITIONS]
    full = pd.concat([d for d in all_dfs if not d.empty], ignore_index=True)
    if full.empty:
        print("No swap results yet.")
        return
    full = full.sort_values(["condition", "variant", "from_slug", "to_slug"])
    out_csv = OUT_DIR / "smoke_swap_results.csv"
    full.to_csv(out_csv, index=False)
    print(f"  rows={len(full)} -> {out_csv}")

    summary = full.groupby(["condition", "variant"]).agg(
        n=("to_slug", "count"),
        suppressed_rate=("from_suppressed", "mean"),
        target_hit_rate=("to_capital_hit", "mean"),
        target_hit_fuzzy_rate=("to_capital_hit_fuzzy", "mean"),
        target_first_token_rate=("first_token_matches_target", "mean"),
        mean_to_topk_prob=("to_in_steered_topk_prob", "mean"),
        mean_from_topk_prob=("from_in_steered_topk_prob", "mean"),
        mean_ablate=("ablate_count", "mean"),
        mean_amplify=("amplify_count", "mean"),
    ).reset_index()
    out_summary = OUT_DIR / "smoke_swap_summary.csv"
    summary.to_csv(out_summary, index=False)
    print(f"  summary -> {out_summary}\n")

    pivot = summary.pivot(index="variant", columns="condition", values="target_hit_fuzzy_rate")
    pivot = pivot.reindex(index=[v for v in VARIANT_NAMES if v in pivot.index],
                          columns=[c for c in CONDITIONS if c in pivot.columns])
    print("Target-capital hit rate (fuzzy) by variant × condition:")
    print(pivot.fillna(float("nan")).round(3).to_string())

    print("\nFrom-capital suppression rate by variant × condition:")
    pivot2 = summary.pivot(index="variant", columns="condition", values="suppressed_rate")
    pivot2 = pivot2.reindex(index=[v for v in VARIANT_NAMES if v in pivot2.index],
                            columns=[c for c in CONDITIONS if c in pivot2.columns])
    print(pivot2.round(3).to_string())

    print("\nMean target-capital prob in steered top-k by variant × condition:")
    pivot3 = summary.pivot(index="variant", columns="condition", values="mean_to_topk_prob")
    pivot3 = pivot3.reindex(index=[v for v in VARIANT_NAMES if v in pivot3.index],
                            columns=[c for c in CONDITIONS if c in pivot3.columns])
    print(pivot3.round(3).to_string())


if __name__ == "__main__":
    main()
