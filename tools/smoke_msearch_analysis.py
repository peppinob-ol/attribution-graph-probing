"""
Aggregate M-search results across the 4 Dallas-as-target conditions.

Walks each
  output/usa_states_fact_batch/_swap_conditions/{cond}/_swaps/runs/{run}/by_source/{src}/
and pulls:
  * canonical-M file:  to_<target>__<variant>.json
  * M-tuned file:      to_<target>__<variant>__m_tuned.json   (only present when
                       canonical missed AND M-search found a hit at lower M)

For each (condition, source, target, variant) cell records:
  - canonical hit (Austin)         (canonical-M file: exact_match.steered_has_to_answer)
  - canonical fuzzy hit            (...steered_has_to_answer_fuzzy)
  - canonical from-suppressed
  - M-tuned hit + m_tuned value + phase + total_steps (when present)
  - canonical & M-tuned steered completions
  - U+24E7 (CIRCLED LATIN SMALL LETTER X) presence in the *winning* completion
    (canonical-hit if any, otherwise M-tuned-hit)
  - 'austin' / 'texas' presence (case-insensitive substring on stripped text)
  - amplify/ablate counts

Also prints summary tables comparing conditions:
  * canonical hit rate
  * M-search incremental hit rate  (cells that went miss -> hit at lower M)
  * combined hit rate
  * fraction of hits with U+24E7 artifact
  * median m_tuned per condition

Outputs:
  - output/research/smoke_msearch_results.csv      (long form)
  - output/research/smoke_msearch_summary.csv      (condition x variant aggregate)
  - output/research/smoke_msearch_hits_clean.csv   (one row per actual Austin hit
                                                    with completion & artifact flags)
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

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
ARTIFACT_CHAR = "\u24e7"  # 'CIRCLED LATIN SMALL LETTER X' = ⓧ


def latest_run(cond_dir: Path) -> Optional[Path]:
    runs = sorted((cond_dir / "_swaps" / "runs").glob("2026*"))
    return runs[-1] if runs else None


_FNAME_TUNED = re.compile(r"^to_(?P<to>[a-z0-9_]+?)__(?P<var>add_[a-z_]+)__m_tuned$")
_FNAME_VAR = re.compile(r"^to_(?P<to>[a-z0-9_]+?)__(?P<var>add_[a-z_]+)$")


def parse_filename(p: Path) -> Dict[str, str]:
    name = p.stem
    m = _FNAME_TUNED.match(name)
    if m:
        return {"to_slug": m.group("to"), "variant": m.group("var"), "kind": "tuned"}
    m = _FNAME_VAR.match(name)
    if m:
        return {"to_slug": m.group("to"), "variant": m.group("var"), "kind": "canonical"}
    return {"to_slug": "", "variant": "", "kind": ""}


def _strip_prompt(text: str, default: str) -> str:
    """Return only the new-token portion produced by the steering run."""
    if not text:
        return ""
    if default and text.startswith(default):
        return text[len(default):]
    return text


def load_record(p: Path) -> Dict[str, Any]:
    d = json.loads(p.read_text())
    ev = d.get("evaluation", {})
    em = ev.get("exact_match", {})
    iv = d.get("interventions", {})
    msearch = d.get("m_search") or {}
    cont = d.get("continuations") or {}
    default = cont.get("default_text") or ""
    steered = cont.get("steered_text") or ""
    new_tokens = _strip_prompt(steered, default).strip()
    low = new_tokens.lower()
    return {
        "ablate_count": iv.get("ablate_count", 0),
        "amplify_count": iv.get("amplify_count", 0),
        "from_suppressed": int(bool(em.get("from_suppressed"))),
        "to_hit": int(bool(em.get("steered_has_to_answer"))),
        "to_hit_fuzzy": int(bool(em.get("steered_has_to_answer_fuzzy"))),
        "first_token_matches_target": int(bool(em.get("first_token_matches_target"))),
        "to_answer": ev.get("to_answer", ""),
        "from_answer": ev.get("from_answer", ""),
        "default_text": default,
        "steered_text": steered,
        "new_tokens": new_tokens,
        "has_artifact": int(ARTIFACT_CHAR in new_tokens),
        "has_austin": int("austin" in low),
        "has_texas": int("texas" in low),
        # m-search payload (only on tuned files, but harmless on canonical -> {})
        "m_tuned": msearch.get("m_tuned"),
        "m_phase": msearch.get("phase"),
        "m_total_steps": msearch.get("total_steps"),
    }


def collect_condition(cond: str) -> pd.DataFrame:
    cdir = COND_ROOT / cond
    run = latest_run(cdir)
    if run is None:
        return pd.DataFrame()
    rows: List[Dict[str, Any]] = []
    by_src = run / "by_source"
    if not by_src.exists():
        return pd.DataFrame()
    for src_dir in sorted(by_src.iterdir()):
        canonical: Dict[str, Dict[str, Any]] = {}
        tuned: Dict[str, Dict[str, Any]] = {}
        for f in sorted(src_dir.glob("to_*.json")):
            meta = parse_filename(f)
            if not meta["to_slug"] or not meta["variant"]:
                continue
            key = (meta["to_slug"], meta["variant"])
            try:
                rec = load_record(f)
            except (json.JSONDecodeError, FileNotFoundError):
                continue
            rec.update(meta)
            if meta["kind"] == "tuned":
                tuned[key] = rec
            else:
                canonical[key] = rec
        for key, can in canonical.items():
            tun = tuned.get(key)
            row = {
                "condition": cond,
                "from_slug": src_dir.name,
                "to_slug": key[0],
                "variant": key[1],
                "run_id": run.name,
                "ablate_count": can["ablate_count"],
                "amplify_count": can["amplify_count"],
                "to_answer": can["to_answer"],
                "from_answer": can["from_answer"],
                "default_text": can["default_text"],
                # canonical
                "canonical_hit": can["to_hit"],
                "canonical_hit_fuzzy": can["to_hit_fuzzy"],
                "canonical_from_suppressed": can["from_suppressed"],
                "canonical_first_token_match": can["first_token_matches_target"],
                "canonical_new_tokens": can["new_tokens"],
                "canonical_has_artifact": can["has_artifact"],
                "canonical_has_austin": can["has_austin"],
                "canonical_has_texas": can["has_texas"],
                # m-tuned (NaN where no tuned file)
                "tuned_present": int(tun is not None),
                "tuned_hit": tun["to_hit"] if tun else 0,
                "tuned_hit_fuzzy": tun["to_hit_fuzzy"] if tun else 0,
                "tuned_from_suppressed": tun["from_suppressed"] if tun else None,
                "tuned_new_tokens": tun["new_tokens"] if tun else "",
                "tuned_has_artifact": tun["has_artifact"] if tun else 0,
                "tuned_has_austin": tun["has_austin"] if tun else 0,
                "tuned_has_texas": tun["has_texas"] if tun else 0,
                "m_tuned": tun["m_tuned"] if tun else None,
                "m_phase": tun["m_phase"] if tun else None,
                "m_total_steps": tun["m_total_steps"] if tun else None,
            }
            rows.append(row)
    return pd.DataFrame(rows)


def main() -> None:
    all_dfs = [collect_condition(c) for c in CONDITIONS]
    full = pd.concat([d for d in all_dfs if not d.empty], ignore_index=True)
    if full.empty:
        print("No swap results yet.")
        return
    full = full.sort_values(["condition", "from_slug", "to_slug", "variant"]).reset_index(drop=True)

    # Combined hit: canonical OR (tuned hit when tuned file exists)
    full["any_hit"] = (full["canonical_hit"] | full["tuned_hit"]).astype(int)
    full["any_hit_fuzzy"] = (full["canonical_hit_fuzzy"] | full["tuned_hit_fuzzy"]).astype(int)

    # Hit-display columns: which completion to show as the "winning" hit
    def hit_completion(row: pd.Series) -> str:
        if row["canonical_hit"]:
            return row["canonical_new_tokens"]
        if row["tuned_hit"]:
            return row["tuned_new_tokens"]
        return ""

    def hit_artifact(row: pd.Series) -> int:
        if row["canonical_hit"]:
            return int(row["canonical_has_artifact"])
        if row["tuned_hit"]:
            return int(row["tuned_has_artifact"])
        return 0

    full["hit_completion"] = full.apply(hit_completion, axis=1)
    full["hit_has_artifact"] = full.apply(hit_artifact, axis=1)
    # NaN-marker column: artifact flag only on rows that actually hit (so .mean
    # over a group ignores misses).
    full["artifact_when_hit"] = full.apply(
        lambda r: r["hit_has_artifact"] if r["any_hit"] == 1 else float("nan"),
        axis=1,
    )

    out_csv = OUT_DIR / "smoke_msearch_results.csv"
    full.to_csv(out_csv, index=False)
    print(f"  rows={len(full)} -> {out_csv}")

    summary = full.groupby(["condition", "variant"]).agg(
        n=("to_slug", "count"),
        canonical_hit_rate=("canonical_hit", "mean"),
        canonical_hit_fuzzy_rate=("canonical_hit_fuzzy", "mean"),
        msearch_extra_hits=("tuned_hit", "sum"),
        any_hit_rate=("any_hit", "mean"),
        any_hit_fuzzy_rate=("any_hit_fuzzy", "mean"),
        suppression_rate=("canonical_from_suppressed", "mean"),
        artifact_rate_in_hits=("artifact_when_hit", "mean"),
        median_m_tuned=("m_tuned", "median"),
        mean_amplify=("amplify_count", "mean"),
    ).reset_index()
    out_summary = OUT_DIR / "smoke_msearch_summary.csv"
    summary.to_csv(out_summary, index=False)
    print(f"  summary -> {out_summary}\n")

    # Pivots
    def show_pivot(values: str, title: str, fmt: int = 3) -> None:
        piv = summary.pivot(index="variant", columns="condition", values=values)
        piv = piv.reindex(
            index=[v for v in VARIANT_NAMES if v in piv.index],
            columns=[c for c in CONDITIONS if c in piv.columns],
        )
        print(title)
        print(piv.round(fmt).to_string())
        print()

    show_pivot("canonical_hit_fuzzy_rate", "Canonical-M (M_amp=20) target hit rate (fuzzy):")
    show_pivot("msearch_extra_hits", "M-search rescued hits (count of miss -> hit at lower M):", fmt=0)
    show_pivot("any_hit_fuzzy_rate", "Combined hit rate (canonical OR M-tuned, fuzzy):")
    show_pivot("median_m_tuned", "Median M_amplify chosen by M-search (over rescued hits):", fmt=2)
    show_pivot("artifact_rate_in_hits", "Artifact (U+24E7) rate among any hits:")

    # Per-condition: cells that flipped miss -> hit
    hits_clean = full[full["any_hit"] == 1].copy()
    hits_clean = hits_clean[[
        "condition", "from_slug", "to_slug", "variant",
        "canonical_hit", "tuned_hit", "m_tuned", "m_phase", "m_total_steps",
        "hit_has_artifact", "hit_completion",
    ]]
    out_hits = OUT_DIR / "smoke_msearch_hits_clean.csv"
    hits_clean.to_csv(out_hits, index=False)
    print(f"All Austin hits (canonical or M-tuned) -> {out_hits}\n")

    print("=== EVERY HIT (canonical OR M-tuned), by condition ===")
    for cond in CONDITIONS:
        sub = hits_clean[hits_clean["condition"] == cond]
        print(f"\n--- {cond}  ({len(sub)} hits)")
        for _, r in sub.iterrows():
            origin = "canonical" if r["canonical_hit"] else f"M-tuned@{r['m_tuned']}"
            artifact = "  [U+24E7]" if r["hit_has_artifact"] else ""
            text = (r["hit_completion"] or "").replace("\n", "\\n")
            print(f"  {r['from_slug']:<25s} {r['variant']:<25s} {origin:<22s}{artifact}  '{text}'")


if __name__ == "__main__":
    main()
