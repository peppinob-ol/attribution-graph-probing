#!/usr/bin/env python3
"""Aggregate matched-random + adaptive M-search results per pair.

For each of the 4 in-scope domains, scans the corresponding
``fullscale_<dom>_random`` run and picks, per ``(from_slug, to_slug)``,
the best across the up-to-6 candidates ``r0/r1/r2 x {default, __m_tuned}``.
The lexicographic score mirrors ``_collect_missed_pairs_additivity`` of
``run_m_search.py``: ``(steered_has_to_answer, steered_has_to_capital,
-target_rank, vsmax)``.

Outputs:
- ``output/research/random_msearch_best_<domain>.csv`` -- one row per pair
  with the winning candidate plus all the metrics the appendix tables need
  (Hit%, vsMax, Supp%, Flip%, RkGrp, MedRk, regime A/D).
- A stdout summary (per-domain ``N``, default-only Hit%, after-M-search
  Hit%, mean vsMax, M-distribution, regime A/D shares).

Restricts to the demo cross-run intersection slug list when one is found
under ``output/research/demo_intersection_slugs_<domain>.json``.
"""
from __future__ import annotations

import csv
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = REPO / "output"
RESEARCH_DIR = OUTPUT_ROOT / "research"

DATASETS = [
    ("usa_states_batch", "fullscale_usa_random", "usa"),
    ("book_characters_authors_batch", "fullscale_books_random", "books"),
    ("products_founders_batch", "fullscale_products_random", "products"),
    ("paintings_painters_batch", "fullscale_paintings_random", "paintings"),
]

# Per-domain blacklist of words that would match too easily under unified
# rule (iii). Mirrors ``DataLoader.TIER_WORD_BLACKLIST``.
TIER_WORD_BLACKLIST = {
    "usa": {"city"},
    "books": set(),
    "products": set(),
    "paintings": set(),
}

REGIME_FLAT_THRESHOLD = 1.0


# ---------------------------------------------------------------------------
# Per-file extraction
# ---------------------------------------------------------------------------

def _classify_regime(pos0: Dict[str, Any]) -> Optional[str]:
    if not pos0:
        return None
    tgt = pos0.get("target_logit_delta")
    src = pos0.get("source_logit_delta")
    flip = pos0.get("flip_at_0", False)
    if tgt is None or src is None:
        return None
    tgt_up = tgt > REGIME_FLAT_THRESHOLD
    tgt_down = tgt < -REGIME_FLAT_THRESHOLD
    src_down = src < -REGIME_FLAT_THRESHOLD
    src_up = src > REGIME_FLAT_THRESHOLD
    if tgt_up and src_down and flip:
        return "A"
    if tgt_up and src_up:
        return "B"
    if tgt_down and src_down and flip:
        return "C"
    if tgt_down and src_down and not flip:
        return "D"
    if not tgt_up and not tgt_down and src_down and flip:
        return "E"
    return None


def _unified_hit(data: Dict[str, Any], blacklist: set) -> bool:
    """Apply the four-rule unified hit detection (matches DataLoader._get_tier).

    Returns True iff any of:
      a) ``steered_has_to_capital`` or ``steered_has_to_answer`` is True
      b) the target string appears in the steered output (with '.' / '-' normalised)
      c) the steered first token (>=2 chars) is a substring of the target
      d) any word (>=3 chars, not in blacklist) of the target appears as a
         whole word in the steered output
    """
    ev = data.get("evaluation", {})
    exact = ev.get("exact_match", {})
    if exact.get("steered_has_to_capital") or exact.get("steered_has_to_answer"):
        return True

    to_answer = ev.get("to_answer", "") or ""
    steered_out = ev.get("raw", {}).get("steered_output", "") or ""

    if to_answer and steered_out:
        to_norm = to_answer.replace(".", "").replace("-", " ").lower()
        out_norm = steered_out.replace(".", "").replace("-", " ").lower()
        if to_norm and to_norm in out_norm:
            return True

    first_token = ev.get("first_token", {}) or {}
    steered_first_tok = (first_token.get("steered", "") or "").strip()
    if len(steered_first_tok) >= 2 and to_answer:
        answer_norm = to_answer.replace(".", "").lower()
        if steered_first_tok.lower() in answer_norm:
            return True

    if to_answer and steered_out:
        out_lower = steered_out.lower()
        for word in to_answer.replace(".", "").split():
            if len(word) >= 3 and word.lower() not in blacklist:
                pattern = r"\b" + re.escape(word.lower()) + r"\b"
                if re.search(pattern, out_lower):
                    return True

    return False


def _extract_metrics(data: Dict[str, Any], blacklist: set) -> Dict[str, Any]:
    """Pull the metrics needed for T2 + appendix tables out of a swap JSON."""
    ev = data.get("evaluation", {})
    em = ev.get("exact_match", {})
    bl = ev.get("baseline_logits", {})
    contrast = (
        ev.get("logit_trajectory", {})
        .get("contrast_groups", {})
        .get("same_dataset", {})
    )
    agg = contrast.get("aggregate", {}) if isinstance(contrast, dict) else {}
    pos0 = ev.get("position_0_comparison", {})
    traj_summ = ev.get("logit_trajectory", {}).get("summary", {})
    msearch = data.get("m_search", {}) or {}
    cfg = data.get("config", {}) or {}

    has_answer_strict = bool(em.get("steered_has_to_answer"))
    has_capital = bool(em.get("steered_has_to_capital"))
    hit_unified = _unified_hit(data, blacklist)
    target_rank = bl.get("target", {}).get("rank")
    vsmax = agg.get("best_target_minus_max")
    supp = bool(em.get("from_suppressed"))
    flip = (
        em.get("from_to_flipped")
        if "from_to_flipped" in em
        else (
            traj_summ.get("flip_position") is not None
            and traj_summ.get("flip_position") >= 0
        )
    )
    regime = _classify_regime(pos0)
    return {
        "hit": hit_unified,
        "hit_strict": has_answer_strict,
        "has_to_capital": has_capital,
        "target_rank": target_rank,
        "vsmax": vsmax,
        "from_suppressed": supp,
        "flipped": flip,
        "regime": regime,
        "rank_in_group": agg.get("best_rank_within"),
        "m_amplify": (
            msearch.get("m_tuned")
            if msearch.get("m_tuned") is not None
            else cfg.get("M_amplify")
        ),
    }


def _score_tuple(metrics: Dict[str, Any]) -> Tuple:
    """Lexicographic best-of score: hit > to_capital > -rank > vsmax.

    Uses the unified hit detection so the random selection rule mirrors the
    appendix unified hit definition used by the labeled FA+M-search column.
    """
    rank = metrics.get("target_rank")
    neg_rank = -rank if isinstance(rank, (int, float)) else float("-inf")
    vsmax = metrics.get("vsmax")
    vsmax_v = vsmax if isinstance(vsmax, (int, float)) else float("-inf")
    return (
        bool(metrics.get("hit")),
        bool(metrics.get("has_to_capital")),
        neg_rank,
        vsmax_v,
    )


# ---------------------------------------------------------------------------
# Per-domain aggregation
# ---------------------------------------------------------------------------

def _load_allowed_slugs(domain_dir_name: str) -> Optional[set]:
    f = RESEARCH_DIR / f"demo_intersection_slugs_{domain_dir_name}.json"
    if not f.exists():
        return None
    return set(json.loads(f.read_text(encoding="utf-8")))


def _candidate_files_for_pair(
    by_source: Path, from_slug: str, to_slug: str,
) -> List[Path]:
    """Return up to 6 candidate paths for one pair (3 reps x {default, m_tuned})."""
    src_dir = by_source / from_slug
    if not src_dir.is_dir():
        return []
    out: List[Path] = []
    for rep in ("r0", "r1", "r2"):
        base = src_dir / f"to_{to_slug}__{rep}.json"
        tuned = src_dir / f"to_{to_slug}__{rep}__m_tuned.json"
        if base.exists():
            out.append(base)
        if tuned.exists():
            out.append(tuned)
    return out


def aggregate_domain(
    dataset_dir: str, run_id: str, label: str,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    by_source = OUTPUT_ROOT / dataset_dir / "_swaps" / "runs" / run_id / "by_source"
    if not by_source.is_dir():
        raise FileNotFoundError(f"missing run dir: {by_source}")

    allowed = _load_allowed_slugs(dataset_dir)
    if allowed is None:
        raise FileNotFoundError(
            f"missing demo intersection slug list for {dataset_dir}; "
            f"run tools/dump_demo_intersection_slugs.py first."
        )
    blacklist = TIER_WORD_BLACKLIST.get(label, set())

    pairs: List[Tuple[str, str]] = []
    for from_slug in sorted(allowed):
        for to_slug in sorted(allowed):
            if from_slug == to_slug:
                continue
            pairs.append((from_slug, to_slug))

    rows: List[Dict[str, Any]] = []
    n_pairs = len(pairs)
    n_default_hits = 0          # per-pair: any of 3 reps hit at default
    n_after_hits = 0            # per-pair: best across reps x {default, m_tuned}
    n_no_data = 0
    # Per-replicate counts (for tab:fullscale-spec parity with prior table)
    n_replicates = 0
    n_replicate_hits_default = 0
    n_replicate_hits_after = 0  # per-replicate, best of {default, m_tuned} for that rep
    n_eligible_rescued = 0      # pairs with Before=0 that have any m_tuned hit

    for (from_slug, to_slug) in pairs:
        candidates = _candidate_files_for_pair(by_source, from_slug, to_slug)
        if not candidates:
            n_no_data += 1
            continue

        best_score = None
        best_meta = None
        best_path = None
        default_hit_for_pair = False
        rescued_for_pair = False
        # Group candidates by replicate (r0/r1/r2)
        by_rep: Dict[str, List[Tuple[Path, Dict[str, Any]]]] = defaultdict(list)
        for fp in candidates:
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                continue
            metrics = _extract_metrics(data, blacklist)
            stem_parts = fp.stem.split("__")
            rep = stem_parts[1] if len(stem_parts) > 1 else "r0"
            by_rep[rep].append((fp, metrics))
            score = _score_tuple(metrics)
            if best_score is None or score > best_score:
                best_score = score
                best_meta = metrics
                best_path = fp

        if best_meta is None:
            n_no_data += 1
            continue

        for rep, items in by_rep.items():
            n_replicates += 1
            default_hit = any(
                m["hit"] for fp, m in items if "__m_tuned" not in fp.stem
            )
            if default_hit:
                n_replicate_hits_default += 1
            if any(m["hit"] for fp, m in items):
                n_replicate_hits_after += 1
            if default_hit:
                default_hit_for_pair = True
        if any("__m_tuned" in fp.stem and m["hit"] for fp, m in
               [(fp, m) for items in by_rep.values() for fp, m in items]):
            rescued_for_pair = True

        if default_hit_for_pair:
            n_default_hits += 1
        else:
            if rescued_for_pair:
                n_eligible_rescued += 1
        if best_meta["hit"]:
            n_after_hits += 1

        # Decode winning replicate / source for the CSV row.
        stem = best_path.stem.replace("to_", "", 1)
        parts = stem.split("__")
        # parts[0] = to_slug, parts[1] = "r{N}", optional parts[2] = "m_tuned"
        winning_rep = parts[1] if len(parts) > 1 else ""
        winning_kind = "m_tuned" if "__m_tuned" in best_path.stem else "default"
        rows.append({
            "from_slug": from_slug,
            "to_slug": to_slug,
            "hit": int(best_meta["hit"]),
            "vsmax": best_meta["vsmax"],
            "target_rank": best_meta["target_rank"],
            "rank_in_group": best_meta["rank_in_group"],
            "from_suppressed": int(bool(best_meta["from_suppressed"])),
            "flipped": int(bool(best_meta["flipped"])),
            "regime": best_meta["regime"] or "",
            "winning_replicate": winning_rep,
            "winning_kind": winning_kind,
            "winning_M": best_meta["m_amplify"],
            "winning_source_file": str(best_path.relative_to(REPO)),
        })

    summary = _summarize(rows, n_pairs, n_default_hits, n_after_hits, n_no_data, label)
    summary.update({
        "n_replicates": n_replicates,
        "replicate_default_hit_count": n_replicate_hits_default,
        "replicate_default_hit_pct": (
            100.0 * n_replicate_hits_default / n_replicates if n_replicates else 0.0
        ),
        "replicate_after_hit_count": n_replicate_hits_after,
        "replicate_after_hit_pct": (
            100.0 * n_replicate_hits_after / n_replicates if n_replicates else 0.0
        ),
        "eligible_pairs_rescued": n_eligible_rescued,
        "eligible_pairs": n_pairs - n_default_hits,
        "rescue_pct_pairs": (
            100.0 * n_eligible_rescued / max(1, n_pairs - n_default_hits)
        ),
    })
    return rows, summary


def _summarize(
    rows: List[Dict[str, Any]],
    n_pairs: int,
    n_default_hits: int,
    n_after_hits: int,
    n_no_data: int,
    label: str,
) -> Dict[str, Any]:
    n_with_data = len(rows)

    def _mean(seq: List[float]) -> Optional[float]:
        seq = [v for v in seq if v is not None]
        return sum(seq) / len(seq) if seq else None

    def _median(seq: List[float]) -> Optional[float]:
        seq = sorted(v for v in seq if v is not None)
        if not seq:
            return None
        n = len(seq)
        if n % 2 == 1:
            return float(seq[n // 2])
        return (seq[n // 2 - 1] + seq[n // 2]) / 2

    vsmax = [r["vsmax"] for r in rows]
    rkgrp = [r["rank_in_group"] for r in rows if r["rank_in_group"] is not None]
    medrk = [r["target_rank"] for r in rows if r["target_rank"] is not None]
    n_supp = sum(1 for r in rows if r["from_suppressed"])
    n_flip = sum(1 for r in rows if r["flipped"])
    regimes = Counter(r["regime"] for r in rows)
    m_dist = Counter()
    for r in rows:
        m = r["winning_M"]
        if m is None:
            m_dist["unknown"] += 1
        elif isinstance(m, (int, float)):
            # Bucket: <2, 2-5, 5-10, 10-15, 15-20, 20, >20
            if m < 2:
                m_dist["<2"] += 1
            elif m < 5:
                m_dist["2-5"] += 1
            elif m < 10:
                m_dist["5-10"] += 1
            elif m < 15:
                m_dist["10-15"] += 1
            elif m < 20:
                m_dist["15-20"] += 1
            elif math.isclose(m, 20.0, abs_tol=0.01):
                m_dist["=20"] += 1
            else:
                m_dist[">20"] += 1

    def _pct(num: int) -> float:
        return 100.0 * num / n_with_data if n_with_data else 0.0

    return {
        "label": label,
        "N_pairs": n_pairs,
        "N_with_data": n_with_data,
        "N_no_data": n_no_data,
        "default_hit_count": n_default_hits,
        "default_hit_pct": _pct(n_default_hits),
        "after_hit_count": n_after_hits,
        "after_hit_pct": _pct(n_after_hits),
        "delta_pp": _pct(n_after_hits) - _pct(n_default_hits),
        "mean_vsmax": _mean(vsmax),
        "supp_pct": _pct(n_supp),
        "flip_pct": _pct(n_flip),
        "mean_rank_in_group": _mean(rkgrp),
        "median_target_rank": _median(medrk),
        "regime_counts": dict(regimes),
        "regime_A_pct": _pct(regimes.get("A", 0)),
        "regime_D_pct": _pct(regimes.get("D", 0)),
        "M_distribution": dict(m_dist),
    }


def _write_csv(rows: List[Dict[str, Any]], out_path: Path) -> None:
    if not rows:
        out_path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(rows)


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------

def main() -> None:
    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    summaries: Dict[str, Dict[str, Any]] = {}
    for dataset_dir, run_id, label in DATASETS:
        try:
            rows, summary = aggregate_domain(dataset_dir, run_id, label)
        except FileNotFoundError as exc:
            print(f"[{label}] SKIP: {exc}")
            continue
        out_path = RESEARCH_DIR / f"random_msearch_best_{label}.csv"
        _write_csv(rows, out_path)
        summaries[label] = summary
        print(f"[{label}] wrote {len(rows)} rows -> {out_path.relative_to(REPO)}")

    print("\n" + "=" * 78)
    print("Per-domain summary (matched-random under per-pair best of 3 reps x M-search)")
    print("=" * 78)
    print(f"{'domain':<10}  {'N':>5}  {'wD':>4}  "
          f"{'Hit@def':>8}  {'Hit@best':>9}  {'dpp':>6}  "
          f"{'vsMax':>7}  {'Supp%':>6}  {'Flip%':>6}  "
          f"{'RkGrp':>6}  {'MedRk':>6}  {'A%':>5}  {'D%':>5}")
    print("-" * 110)
    for label, s in summaries.items():
        print(
            f"{label:<10}  {s['N_pairs']:>5d}  {s['N_with_data']:>4d}  "
            f"{s['default_hit_pct']:>7.1f}%  {s['after_hit_pct']:>8.1f}%  "
            f"{s['delta_pp']:>+5.1f}  "
            f"{(s['mean_vsmax'] if s['mean_vsmax'] is not None else 0):>+7.2f}  "
            f"{s['supp_pct']:>5.1f}%  {s['flip_pct']:>5.1f}%  "
            f"{(s['mean_rank_in_group'] if s['mean_rank_in_group'] is not None else 0):>6.2f}  "
            f"{(s['median_target_rank'] if s['median_target_rank'] is not None else 0):>6.0f}  "
            f"{s['regime_A_pct']:>4.1f}%  {s['regime_D_pct']:>4.1f}%"
        )

    print("\nM-distribution (where adaptive M won the best-of):")
    for label, s in summaries.items():
        bucket_str = ", ".join(
            f"{b}={c}" for b, c in sorted(s["M_distribution"].items())
        )
        print(f"  {label}: {bucket_str}")

    # M-search rescue stats (per replicate AND per pair)
    print("\nM-search rescue (random control):")
    print(f"  {'domain':<10}  {'N_pair':>6}  {'Elig':>4}  "
          f"{'Resc':>4}  {'Resc%':>6}  "
          f"{'rep_def':>7}  {'rep_aft':>7}  {'pair_def':>8}  {'pair_aft':>8}")
    for label, s in summaries.items():
        print(
            f"  {label:<10}  {s['N_pairs']:>6d}  "
            f"{s['eligible_pairs']:>4d}  {s['eligible_pairs_rescued']:>4d}  "
            f"{s['rescue_pct_pairs']:>5.1f}%  "
            f"{s['replicate_default_hit_pct']:>6.2f}%  "
            f"{s['replicate_after_hit_pct']:>6.2f}%  "
            f"{s['default_hit_pct']:>7.2f}%  "
            f"{s['after_hit_pct']:>7.2f}%"
        )

    out_summary = RESEARCH_DIR / "random_msearch_best_summary.json"
    out_summary.write_text(json.dumps(summaries, indent=2), encoding="utf-8")
    print(f"\n  summary -> {out_summary.relative_to(REPO)}")

    # ---- Emit LaTeX fragments ready to paste ----
    _emit_latex_fragments(summaries)


def _fmt_signed(x: Optional[float], digits: int = 2) -> str:
    if x is None:
        return "--"
    sign = "+" if x >= 0 else ""
    return f"${sign}{x:.{digits}f}$"


def _emit_latex_fragments(summaries: Dict[str, Dict[str, Any]]) -> None:
    out = RESEARCH_DIR / "random_msearch_paper_fragments.tex"
    label_to_paper = {
        "usa": "USA",
        "books": "Books",
        "products": "Products",
        "paintings": "Paintings",
    }
    lines = []
    lines.append("% ---------------------------------------------------------------")
    lines.append("% Auto-generated by tools/build_random_msearch_best.py")
    lines.append("% Random + M-search updates for T2_headline, fullscale-spec,")
    lines.append("% msearch-rescue, and regime-prev tables.")
    lines.append("% ---------------------------------------------------------------\n")

    lines.append("% ---- T2_headline Rand. column (Hit% / vsMax) ----")
    for label in ("usa", "books", "products", "paintings"):
        s = summaries[label]
        lines.append(
            f"%   {label_to_paper[label]:<10}  "
            f"Hit% = {s['after_hit_pct']:5.1f}   "
            f"vsMax = {(s['mean_vsmax'] or 0):+.2f}   "
            f"(per-pair best across {{3 reps x adaptive-M}})"
        )
    lines.append("")

    lines.append("% ---- tab:fullscale-spec Random sub-row (per-replicate) ----")
    lines.append("%   columns: Cond | N | Hit% | Supp% | vsMax | RkGrp | MedRk | Flip%")
    for label in ("usa", "books", "products", "paintings"):
        s = summaries[label]
        lines.append(
            f"%   {label_to_paper[label]:<10}  random+M-srch  "
            f"N={s['N_pairs']:>4d} (per-pair) / {s['n_replicates']:>5d} (per-rep)  "
            f"Hit_pair={s['after_hit_pct']:5.2f}  "
            f"Hit_rep={s['replicate_after_hit_pct']:5.2f}  "
            f"Supp%={s['supp_pct']:5.1f}  "
            f"vsMax={(s['mean_vsmax'] or 0):+.2f}  "
            f"RkGrp={(s['mean_rank_in_group'] or 0):.2f}  "
            f"MedRk={(s['median_target_rank'] or 0):.0f}  "
            f"Flip%={s['flip_pct']:5.1f}"
        )
    lines.append("")

    lines.append("% ---- tab:msearch-rescue new Rand. rows ----")
    lines.append("%   Cond | Domain | Eligible | New hits | Hit% | Before | After | Delta")
    for label in ("usa", "books", "products", "paintings"):
        s = summaries[label]
        before = s["default_hit_pct"]
        after = s["after_hit_pct"]
        delta = after - before
        lines.append(
            f"%   Rand.\\  &  {label_to_paper[label]:<9} & "
            f"{s['eligible_pairs']:4d} & {s['eligible_pairs_rescued']:3d} & "
            f"{s['rescue_pct_pairs']:5.2f} & "
            f"{before:5.2f} & {after:5.2f} &  $+{delta:.2f}$ \\\\"
        )
    lines.append("")

    lines.append("% ---- tab:regime-prev random column update ----")
    lines.append("%   Domain | Regime A% (random) | Regime D% (random)")
    for label in ("usa", "books", "products", "paintings"):
        s = summaries[label]
        lines.append(
            f"%   {label_to_paper[label]:<10}  "
            f"A_random = {s['regime_A_pct']:5.2f}   "
            f"D_random = {s['regime_D_pct']:5.2f}"
        )

    out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"  LaTeX fragments -> {out.relative_to(REPO)}")


if __name__ == "__main__":
    main()
