"""
Test the hypothesis: specific target tokens (e.g. "Austin") are easier to
steer than generic tokens (e.g. "Jack").

We operationalise "specificity" two ways using only swap-side data:

(A) Per-pair baseline target logit (`baseline_logits.target.logit`):
    target token's logit at the SOURCE prompt position 0.
    A high value means the model already considers the target plausible
    at the wrong context. If hits correlate POSITIVELY with this, the
    intervention mostly tips already-warm tokens; if NEGATIVELY, the
    intervention can install cold tokens.

(B) Per-target MARGINAL baseline logit:
    for each unique target slug, the mean of `baseline_logits.target.logit`
    over all sources where this entity is the target (excluding identity).
    LOW marginal logit = token rarely competes anywhere => SPECIFIC.
    HIGH marginal logit = token is plausible across many contexts => GENERIC.
    We then ask whether per-target hit-rate correlates with this measure.

We also report the equivalent slice of the marginal baseline rank.

Comparison conditions:
    - `fullscale_<domain>_labeled` (canonical labeled, single variant per pair).
    - `fullscale_<domain>_field_add` reduced to per-pair BEST-of-variant
      (best == any variant whose `steered_has_to_answer` is true; ties
      broken by max `vs_max`). This mirrors the FA+M-search best-of
      construction in the paper headline.

Output: prints to stdout + writes a JSON+text report under
`output/research/target_logit_specificity/`.

Usage::

    PYTHONPATH=. python scripts/research/analyze_target_logit_specificity.py
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.utils.swap_query import SwapQuery, SwapSummary  # noqa: E402

OUT_DIR = REPO_ROOT / "output" / "research" / "target_logit_specificity"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DOMAINS: List[Tuple[str, str, str]] = [
    ("usa_states_batch", "fullscale_usa_labeled", "fullscale_usa_field_add"),
    ("book_characters_authors_batch",
     "fullscale_books_labeled", "fullscale_books_field_add"),
    ("products_founders_batch",
     "fullscale_products_labeled", "fullscale_products_field_add"),
    ("paintings_painters_batch",
     "fullscale_paintings_labeled", "fullscale_paintings_field_add"),
]


@dataclass
class PairRecord:
    dataset: str
    condition: str          # "labeled" or "fa_best"
    from_slug: str
    to_slug: str
    target_token: str       # first token text of the answer
    target_logit: Optional[float]
    target_prob: Optional[float]
    target_rank: Optional[int]
    hit: bool
    vs_max: Optional[float]


def _load_swap(path: Path) -> Optional[dict]:
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _extract_pair(data: dict) -> Optional[PairRecord]:
    """Pull the fields we need from a swap JSON dict."""
    src = data.get("source", {})
    tgt = data.get("target", {})
    if src.get("slug") == tgt.get("slug"):
        return None
    ev = data.get("evaluation", {})
    bl = ev.get("baseline_logits", {}).get("target", {})
    em = ev.get("exact_match", {})
    traj = ev.get("logit_trajectory", {})
    tokens = traj.get("tokens", {})
    target_token = tokens.get("target", "")
    contrast = (
        traj.get("contrast_groups", {})
        .get("same_dataset", {}).get("aggregate", {})
    )
    return PairRecord(
        dataset="",  # filled by caller
        condition="",
        from_slug=src.get("slug", ""),
        to_slug=tgt.get("slug", ""),
        target_token=target_token,
        target_logit=bl.get("logit"),
        target_prob=bl.get("prob"),
        target_rank=bl.get("rank"),
        hit=bool(em.get("steered_has_to_answer")),
        vs_max=contrast.get("best_target_minus_max"),
    )


def _scan_labeled_run(dataset: str, run: str) -> List[PairRecord]:
    by_source = (REPO_ROOT / "output" / dataset / "_swaps"
                 / "runs" / run / "by_source")
    if not by_source.is_dir():
        return []
    records: List[PairRecord] = []
    for src_dir in sorted(by_source.iterdir()):
        if not src_dir.is_dir():
            continue
        for fpath in sorted(src_dir.iterdir()):
            if not (fpath.name.startswith("to_") and fpath.suffix == ".json"):
                continue
            stem = fpath.stem.replace("to_", "", 1)
            if "__" in stem:
                continue
            data = _load_swap(fpath)
            if not data:
                continue
            rec = _extract_pair(data)
            if rec is None:
                continue
            rec.dataset = dataset
            rec.condition = "labeled"
            records.append(rec)
    return records


def _scan_fa_best_run(dataset: str, run: str) -> List[PairRecord]:
    """Per-pair best-of-variant from a field_add run.

    Best == any variant whose hit==True; ties broken by max vs_max.
    Baseline target logit is invariant across variants of the same pair
    (same source prompt + same target token), so we take the value from
    the chosen winner's file.
    """
    by_source = (REPO_ROOT / "output" / dataset / "_swaps"
                 / "runs" / run / "by_source")
    if not by_source.is_dir():
        return []
    by_pair: Dict[Tuple[str, str], List[PairRecord]] = defaultdict(list)
    for src_dir in sorted(by_source.iterdir()):
        if not src_dir.is_dir():
            continue
        for fpath in sorted(src_dir.iterdir()):
            if not (fpath.name.startswith("to_") and fpath.suffix == ".json"):
                continue
            data = _load_swap(fpath)
            if not data:
                continue
            rec = _extract_pair(data)
            if rec is None:
                continue
            rec.dataset = dataset
            rec.condition = "fa_best"
            by_pair[(rec.from_slug, rec.to_slug)].append(rec)
    out: List[PairRecord] = []
    for (_, _), variants in by_pair.items():
        hits = [r for r in variants if r.hit]
        pool = hits if hits else variants
        pool.sort(key=lambda r: (r.vs_max if r.vs_max is not None else -1e9),
                   reverse=True)
        out.append(pool[0])
    return out


def _spearman(xs: List[float], ys: List[float]) -> Optional[float]:
    n = len(xs)
    if n < 3:
        return None

    def _ranks(vs: List[float]) -> List[float]:
        order = sorted(range(len(vs)), key=lambda i: vs[i])
        ranks = [0.0] * len(vs)
        i = 0
        while i < len(vs):
            j = i
            while j + 1 < len(vs) and vs[order[j + 1]] == vs[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg
            i = j + 1
        return ranks

    rx, ry = _ranks(xs), _ranks(ys)
    mx = sum(rx) / n
    my = sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = math.sqrt(sum((r - mx) ** 2 for r in rx))
    dy = math.sqrt(sum((r - my) ** 2 for r in ry))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def _point_biserial(values: List[float], labels: List[bool]) -> Optional[float]:
    """Point-biserial correlation: continuous ~ binary."""
    if len(values) != len(labels) or len(values) < 5:
        return None
    a = [v for v, lb in zip(values, labels) if lb]
    b = [v for v, lb in zip(values, labels) if not lb]
    if len(a) < 2 or len(b) < 2:
        return None
    n = len(values)
    ma = statistics.mean(a)
    mb = statistics.mean(b)
    sd = statistics.stdev(values) if n >= 2 else 0
    if sd == 0:
        return None
    p = len(a) / n
    return (ma - mb) / sd * math.sqrt(p * (1 - p))


def _quintiles(values: List[float], k: int = 5) -> List[Tuple[float, float]]:
    if not values:
        return []
    vs = sorted(values)
    edges = [vs[int(i * (len(vs) - 1) / k)] for i in range(k + 1)]
    return list(zip(edges[:-1], edges[1:]))


def _assign_quintile(value: float, edges: List[Tuple[float, float]]) -> int:
    for i, (lo, hi) in enumerate(edges):
        if value <= hi:
            return i
    return len(edges) - 1


def _stratify_hit_by_quintile(
    records: List[PairRecord],
    key: str,
    k: int = 5,
) -> List[Dict[str, float]]:
    items = [(getattr(r, key), r.hit) for r in records
              if getattr(r, key) is not None]
    if len(items) < k:
        return []
    values = [v for v, _ in items]
    edges = _quintiles(values, k=k)
    buckets: Dict[int, List[bool]] = defaultdict(list)
    for v, hit in items:
        buckets[_assign_quintile(v, edges)].append(hit)
    out = []
    for qi in range(k):
        bools = buckets.get(qi, [])
        if not bools:
            continue
        n = len(bools)
        hits = sum(1 for b in bools if b)
        lo, hi = edges[qi]
        out.append({
            "quintile": qi + 1,
            "n": n,
            "lo": lo,
            "hi": hi,
            "mean_value": statistics.mean(
                [v for v, _ in items
                 if _assign_quintile(v, edges) == qi]),
            "hit_rate": hits / n,
        })
    return out


def _per_target_aggregate(records: List[PairRecord]) -> List[Dict]:
    """For each unique target slug, aggregate baseline logit + hit rate."""
    by_target: Dict[str, List[PairRecord]] = defaultdict(list)
    for r in records:
        by_target[r.to_slug].append(r)
    out = []
    for slug, group in by_target.items():
        logits = [g.target_logit for g in group if g.target_logit is not None]
        ranks = [g.target_rank for g in group if g.target_rank is not None]
        probs = [g.target_prob for g in group if g.target_prob is not None]
        if not logits:
            continue
        n = len(group)
        out.append({
            "to_slug": slug,
            "target_token": group[0].target_token,
            "n_pairs": n,
            "hit_rate": sum(1 for g in group if g.hit) / n,
            "marginal_target_logit": statistics.mean(logits),
            "median_target_logit": statistics.median(logits),
            "marginal_target_rank": statistics.mean(ranks) if ranks else None,
            "marginal_target_prob": statistics.mean(probs) if probs else None,
        })
    return out


def _hit_rate(records: List[PairRecord]) -> Tuple[int, int, float]:
    n = len(records)
    hits = sum(1 for r in records if r.hit)
    return hits, n, (hits / n if n else 0.0)


def _print_quintile_table(rows: List[Dict], header: str) -> List[str]:
    lines = [header,
             f"  {'Q':>3s}  {'N':>5s}  {'lo':>9s}  {'hi':>9s}  "
             f"{'mean':>9s}  {'hit%':>7s}"]
    for r in rows:
        lines.append(
            f"  {r['quintile']:>3d}  {r['n']:>5d}  "
            f"{r['lo']:>9.3f}  {r['hi']:>9.3f}  "
            f"{r['mean_value']:>9.3f}  {r['hit_rate']*100:>6.1f}%"
        )
    return lines


def _domain_block(domain_label: str, records: List[PairRecord],
                   condition_label: str) -> Dict:
    hits, n, hit_rate = _hit_rate(records)
    pair_logit_pb = _point_biserial(
        [r.target_logit for r in records if r.target_logit is not None],
        [r.hit for r in records if r.target_logit is not None],
    )
    pair_rank_pb = _point_biserial(
        [float(r.target_rank) for r in records if r.target_rank is not None],
        [r.hit for r in records if r.target_rank is not None],
    )
    pair_logit_quint = _stratify_hit_by_quintile(records, "target_logit")
    pair_rank_quint = _stratify_hit_by_quintile(records, "target_rank")

    per_tgt = _per_target_aggregate(records)
    if per_tgt:
        xs_logit = [t["marginal_target_logit"] for t in per_tgt]
        xs_rank = [t["marginal_target_rank"] for t in per_tgt
                    if t["marginal_target_rank"] is not None]
        ys = [t["hit_rate"] for t in per_tgt]
        ys_for_rank = [t["hit_rate"] for t in per_tgt
                        if t["marginal_target_rank"] is not None]
        rho_logit = _spearman(xs_logit, ys)
        rho_rank = _spearman(xs_rank, ys_for_rank)
    else:
        rho_logit = None
        rho_rank = None

    return {
        "domain": domain_label,
        "condition": condition_label,
        "n_pairs": n,
        "n_hits": hits,
        "hit_rate": hit_rate,
        "per_pair_target_logit": {
            "point_biserial_with_hit": pair_logit_pb,
            "quintile_hit_rates": pair_logit_quint,
        },
        "per_pair_target_rank": {
            "point_biserial_with_hit": pair_rank_pb,
            "quintile_hit_rates": pair_rank_quint,
        },
        "per_target": {
            "n_unique_targets": len(per_tgt),
            "spearman_marginal_logit_vs_hit_rate": rho_logit,
            "spearman_marginal_rank_vs_hit_rate": rho_rank,
            "rows_top10_generic": sorted(
                per_tgt, key=lambda r: -r["marginal_target_logit"])[:10],
            "rows_top10_specific": sorted(
                per_tgt, key=lambda r: r["marginal_target_logit"])[:10],
        },
    }


def main() -> None:
    q = SwapQuery()
    print(f"Output directory: {OUT_DIR}")
    full_report = []

    for dataset, labeled_run, fa_run in DOMAINS:
        labeled = _scan_labeled_run(dataset, labeled_run)
        fa_best = _scan_fa_best_run(dataset, fa_run)
        print(f"\n=== {dataset} ===")
        print(f"  labeled : {len(labeled):>5d} pairs, "
              f"hit_rate={_hit_rate(labeled)[2]*100:.1f}%")
        print(f"  fa_best : {len(fa_best):>5d} pairs, "
              f"hit_rate={_hit_rate(fa_best)[2]*100:.1f}%")
        full_report.append(_domain_block(dataset, labeled, "labeled"))
        full_report.append(_domain_block(dataset, fa_best, "fa_best"))

    out_json = OUT_DIR / "report.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(full_report, f, indent=2)
    print(f"\nWrote: {out_json}")

    # Console summary table
    text_lines: List[str] = []
    text_lines.append("=" * 84)
    text_lines.append("HYPOTHESIS: specific tokens (Austin) are easier to "
                       "steer than generic tokens (Jack)")
    text_lines.append("=" * 84)
    for block in full_report:
        text_lines.append("")
        text_lines.append(f"[{block['domain']}] [{block['condition']}]  "
                           f"N={block['n_pairs']}  "
                           f"hit_rate={block['hit_rate']*100:.1f}%  "
                           f"unique_targets="
                           f"{block['per_target']['n_unique_targets']}")
        text_lines.append(
            f"  per-pair PB(target_logit, hit) = "
            f"{block['per_pair_target_logit']['point_biserial_with_hit']}"
        )
        text_lines.append(
            f"  per-pair PB(target_rank,  hit) = "
            f"{block['per_pair_target_rank']['point_biserial_with_hit']}"
        )
        text_lines.append(
            f"  per-target Spearman(marginal_logit, hit_rate) = "
            f"{block['per_target']['spearman_marginal_logit_vs_hit_rate']}"
        )
        text_lines.append(
            f"  per-target Spearman(marginal_rank,  hit_rate) = "
            f"{block['per_target']['spearman_marginal_rank_vs_hit_rate']}"
        )
        text_lines.extend(_print_quintile_table(
            block["per_pair_target_logit"]["quintile_hit_rates"],
            "  per-pair quintiles by baseline target logit:",
        ))

    out_txt = OUT_DIR / "report.txt"
    with open(out_txt, "w", encoding="utf-8") as f:
        f.write("\n".join(text_lines) + "\n")
    print("\n".join(text_lines))
    print(f"\nWrote: {out_txt}")


if __name__ == "__main__":
    main()
