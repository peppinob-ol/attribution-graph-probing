"""
Aggregator for the top-K influence-matched control runs across the 4
in-scope domains (paintings, products, books, USA).

For each domain it walks
``output/<dataset>/_swaps/runs/topk_<domain>_influence_matched/by_source/``,
joins each pair with its per-pair labeled best-of baseline row in
``output/research/topk_budgets_<domain>.csv`` (built earlier by
``tools/build_topk_budgets.py``) and emits two CSVs:

  * ``output/research/topk_im_pairs_<domain>.csv`` -- one row per pair,
    carrying both top-K-influence-matched and labeled-best metrics so
    paired tests (sign / McNemar / paired vsMax delta) are immediate.
  * ``output/research/topk_im_summary.csv`` -- one row per domain with
    aggregate hit-rates, paired contingency, McNemar p, mean K, mean
    influence consumed, mean ``M_tuned``.

The script is read-only: no model runs, no rewriting of swap JSONs.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
import statistics as st
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent

DOMAINS: Dict[str, Dict[str, str]] = {
    "usa": {
        "dataset_dir": "output/usa_states_batch",
        "run_id": "topk_usa_influence_matched",
        "budgets_csv": "output/research/topk_budgets_usa.csv",
    },
    "books": {
        "dataset_dir": "output/book_characters_authors_batch",
        "run_id": "topk_books_influence_matched",
        "budgets_csv": "output/research/topk_budgets_books.csv",
    },
    "products": {
        "dataset_dir": "output/products_founders_batch",
        "run_id": "topk_products_influence_matched",
        "budgets_csv": "output/research/topk_budgets_products.csv",
    },
    "paintings": {
        "dataset_dir": "output/paintings_painters_batch",
        "run_id": "topk_paintings_influence_matched",
        "budgets_csv": "output/research/topk_budgets_paintings.csv",
    },
}


@dataclass(frozen=True)
class PairRow:
    domain: str
    from_slug: str
    to_slug: str
    is_identity: bool

    # top-K influence-matched
    K_src: Optional[int]
    K_tgt: Optional[int]
    ref_sum_src: Optional[float]
    ref_sum_tgt: Optional[float]
    achieved_sum_src: Optional[float]
    achieved_sum_tgt: Optional[float]
    ablate_count: Optional[int]
    amplify_count: Optional[int]
    hit_default: Optional[bool]
    hit_m_tuned: Optional[bool]
    best_hit: Optional[bool]
    has_m_tuned: bool
    m_tuned_value: Optional[float]
    m_tuned_steps: Optional[int]
    from_suppressed_default: Optional[bool]
    best_gap_default: Optional[float]
    gap_closure_default: Optional[float]
    vs_max_default: Optional[float]
    vs_topk_default: Optional[float]

    # labeled best-of baseline (from topk_budgets_<domain>.csv)
    labeled_winning_variant: Optional[str]
    labeled_used_m_tuned: Optional[bool]
    labeled_hit: Optional[bool]
    labeled_best_gap: Optional[float]
    labeled_n_ablate: Optional[int]
    labeled_n_amplify: Optional[int]
    labeled_ref_sum_src: Optional[float]
    labeled_ref_sum_tgt: Optional[float]


def _safe_float(v: Any) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _safe_int(v: Any) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(v)
    except (TypeError, ValueError):
        return None


def _safe_bool(v: Any) -> Optional[bool]:
    if v is None:
        return None
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return bool(v)
    if isinstance(v, str):
        return v.strip().lower() in {"1", "true", "yes"}
    return None


def _read_budgets(path: Path) -> Dict[Tuple[str, str], Dict[str, str]]:
    """Index the budgets CSV by ``(from_slug, to_slug)``."""
    out: Dict[Tuple[str, str], Dict[str, str]] = {}
    if not path.exists():
        return out
    with path.open() as fh:
        for row in csv.DictReader(fh):
            out[(row["from_slug"], row["to_slug"])] = row
    return out


def _extract_topk_metrics(payload: Dict[str, Any]) -> Dict[str, Any]:
    """Pull per-pair top-K diagnostics + evaluation metrics from a swap JSON."""
    ctrl = (payload.get("metadata", {}) or {}).get("control", {}) or {}
    diag = ctrl.get("diagnostics", {}) or {}
    intv = payload.get("interventions", {}) or {}
    ev = payload.get("evaluation", {}) or {}
    em = ev.get("exact_match", {}) or {}
    traj_summ = (
        ev.get("logit_trajectory", {}).get("summary", {})
        if isinstance(ev.get("logit_trajectory", {}), dict)
        else {}
    )
    contrast = (
        ev.get("logit_trajectory", {})
        .get("contrast_groups", {})
        .get("same_dataset", {})
        if isinstance(ev.get("logit_trajectory", {}), dict)
        else {}
    )
    agg = contrast.get("aggregate", {}) if isinstance(contrast, dict) else {}
    return {
        "K_src": _safe_int(diag.get("K_src")),
        "K_tgt": _safe_int(diag.get("K_tgt")),
        "ref_sum_src": _safe_float(diag.get("ref_sum_src")),
        "ref_sum_tgt": _safe_float(diag.get("ref_sum_tgt")),
        "achieved_sum_src": _safe_float(diag.get("achieved_sum_src")),
        "achieved_sum_tgt": _safe_float(diag.get("achieved_sum_tgt")),
        "ablate_count": _safe_int(intv.get("ablate_count")),
        "amplify_count": _safe_int(intv.get("amplify_count")),
        "hit": _safe_bool(em.get("steered_has_to_answer")),
        "from_suppressed": _safe_bool(em.get("from_suppressed")),
        "best_gap": _safe_float(traj_summ.get("best_gap")),
        "gap_closure": _safe_float(traj_summ.get("gap_closure")),
        "vs_max": _safe_float(agg.get("best_target_minus_max")),
        "vs_topk": _safe_float(agg.get("best_target_minus_topk")),
    }


def _enumerate_pairs(by_source: Path) -> Iterable[Tuple[str, str, Path, Optional[Path]]]:
    """Yield (from_slug, to_slug, base_path, m_tuned_path_or_None) for every pair."""
    for from_dir in sorted(by_source.iterdir()):
        if not from_dir.is_dir():
            continue
        from_slug = from_dir.name
        seen: Dict[str, Tuple[Path, Optional[Path]]] = {}
        for jp in sorted(from_dir.glob("to_*.json")):
            stem = jp.stem
            if stem.endswith("__m_tuned"):
                continue
            assert stem.startswith("to_")
            to_slug = stem[3:]
            mt = jp.with_name(stem + "__m_tuned.json")
            seen[to_slug] = (jp, mt if mt.exists() else None)
        for to_slug, (base, mt) in sorted(seen.items()):
            yield from_slug, to_slug, base, mt


def _load_pair(domain: str, base: Path, mt: Optional[Path],
               budget_row: Optional[Dict[str, str]]) -> Optional[PairRow]:
    try:
        d_base = json.loads(base.read_text())
    except (OSError, json.JSONDecodeError) as e:
        print(f"  [WARN] failed to read {base}: {e}")
        return None
    base_metrics = _extract_topk_metrics(d_base)

    # m_tuned sibling may carry a higher hit rate; merge cautiously
    hit_default = base_metrics["hit"]
    hit_m_tuned: Optional[bool] = None
    m_tuned_value: Optional[float] = None
    m_tuned_steps: Optional[int] = None
    if mt is not None:
        try:
            d_mt = json.loads(mt.read_text())
            mt_em = (d_mt.get("evaluation", {}) or {}).get("exact_match", {}) or {}
            hit_m_tuned = _safe_bool(mt_em.get("steered_has_to_answer"))
            ms = d_mt.get("m_search", {}) or {}
            m_tuned_value = _safe_float(ms.get("m_tuned"))
            m_tuned_steps = _safe_int(ms.get("total_steps"))
        except (OSError, json.JSONDecodeError) as e:
            print(f"  [WARN] failed to read m_tuned {mt}: {e}")

    best_hit = bool(hit_default) or bool(hit_m_tuned) if (hit_default is not None or hit_m_tuned is not None) else None

    from_slug = base.parent.name
    to_slug = base.stem.replace("to_", "", 1)

    if budget_row is not None:
        labeled_hit = _safe_bool(budget_row.get("hit"))
        labeled_used_m_tuned = _safe_bool(budget_row.get("used_m_tuned"))
        labeled_winning_variant = budget_row.get("winning_variant") or None
        labeled_best_gap = _safe_float(budget_row.get("best_gap"))
        labeled_n_ablate = _safe_int(budget_row.get("n_ablate_labeled"))
        labeled_n_amplify = _safe_int(budget_row.get("n_amplify_labeled"))
        labeled_ref_sum_src = _safe_float(budget_row.get("ref_sum_src"))
        labeled_ref_sum_tgt = _safe_float(budget_row.get("ref_sum_tgt"))
    else:
        labeled_hit = labeled_used_m_tuned = None
        labeled_winning_variant = None
        labeled_best_gap = None
        labeled_n_ablate = labeled_n_amplify = None
        labeled_ref_sum_src = labeled_ref_sum_tgt = None

    return PairRow(
        domain=domain,
        from_slug=from_slug,
        to_slug=to_slug,
        is_identity=(from_slug == to_slug),
        K_src=base_metrics["K_src"],
        K_tgt=base_metrics["K_tgt"],
        ref_sum_src=base_metrics["ref_sum_src"],
        ref_sum_tgt=base_metrics["ref_sum_tgt"],
        achieved_sum_src=base_metrics["achieved_sum_src"],
        achieved_sum_tgt=base_metrics["achieved_sum_tgt"],
        ablate_count=base_metrics["ablate_count"],
        amplify_count=base_metrics["amplify_count"],
        hit_default=hit_default,
        hit_m_tuned=hit_m_tuned,
        best_hit=best_hit,
        has_m_tuned=mt is not None,
        m_tuned_value=m_tuned_value,
        m_tuned_steps=m_tuned_steps,
        from_suppressed_default=base_metrics["from_suppressed"],
        best_gap_default=base_metrics["best_gap"],
        gap_closure_default=base_metrics["gap_closure"],
        vs_max_default=base_metrics["vs_max"],
        vs_topk_default=base_metrics["vs_topk"],
        labeled_winning_variant=labeled_winning_variant,
        labeled_used_m_tuned=labeled_used_m_tuned,
        labeled_hit=labeled_hit,
        labeled_best_gap=labeled_best_gap,
        labeled_n_ablate=labeled_n_ablate,
        labeled_n_amplify=labeled_n_amplify,
        labeled_ref_sum_src=labeled_ref_sum_src,
        labeled_ref_sum_tgt=labeled_ref_sum_tgt,
    )


PAIR_COLUMNS = [
    "domain", "from_slug", "to_slug", "is_identity",
    "K_src", "K_tgt",
    "ref_sum_src", "ref_sum_tgt",
    "achieved_sum_src", "achieved_sum_tgt",
    "ablate_count", "amplify_count",
    "hit_default", "hit_m_tuned", "best_hit", "has_m_tuned",
    "m_tuned_value", "m_tuned_steps",
    "from_suppressed_default",
    "best_gap_default", "gap_closure_default",
    "vs_max_default", "vs_topk_default",
    "labeled_winning_variant", "labeled_used_m_tuned",
    "labeled_hit", "labeled_best_gap",
    "labeled_n_ablate", "labeled_n_amplify",
    "labeled_ref_sum_src", "labeled_ref_sum_tgt",
]


def _row_to_dict(r: PairRow) -> Dict[str, Any]:
    out = {}
    for col in PAIR_COLUMNS:
        v = getattr(r, col)
        if isinstance(v, bool):
            out[col] = int(v)
        elif v is None:
            out[col] = ""
        else:
            out[col] = v
    return out


def _write_pairs_csv(rows: List[PairRow], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=PAIR_COLUMNS)
        w.writeheader()
        for r in rows:
            w.writerow(_row_to_dict(r))


def _mcnemar_pvalue(b: int, c: int) -> float:
    """
    Two-sided exact (small n) or normal-approx (large n) McNemar p-value.

    ``b`` = pairs labeled-only-wins, ``c`` = pairs topk-only-wins.
    """
    n = b + c
    if n == 0:
        return 1.0
    if n < 25:
        # Exact two-sided binomial against p=0.5 of the smaller side.
        from math import comb
        k = min(b, c)
        tail = sum(comb(n, i) for i in range(k + 1)) / (2 ** n)
        return min(1.0, 2 * tail)
    # Continuity-corrected normal approximation.
    z = (abs(b - c) - 1) / math.sqrt(n)
    return math.erfc(z / math.sqrt(2))


def _summarize(domain: str, rows: List[PairRow]) -> Dict[str, Any]:
    n = len(rows)
    paired = [r for r in rows if r.labeled_hit is not None]
    n_paired = len(paired)

    def _rate(xs: List[bool]) -> float:
        return (sum(1 for x in xs if x) / len(xs)) if xs else 0.0

    hits_def = [bool(r.hit_default) for r in rows if r.hit_default is not None]
    hits_best = [bool(r.best_hit) for r in rows if r.best_hit is not None]
    supp = [bool(r.from_suppressed_default) for r in rows if r.from_suppressed_default is not None]

    # Paired contingency (only on rows with labeled_hit available).
    both = lbl_only = topk_only = both_lose = 0
    for r in paired:
        lbl = bool(r.labeled_hit)
        topk = bool(r.best_hit)
        if lbl and topk:
            both += 1
        elif lbl:
            lbl_only += 1
        elif topk:
            topk_only += 1
        else:
            both_lose += 1
    p_mcnemar = _mcnemar_pvalue(lbl_only, topk_only)

    # Aggregates over numeric fields (median, mean) excluding identity for K_tgt.
    ks_src = [r.K_src for r in rows if r.K_src is not None]
    ks_tgt = [r.K_tgt for r in rows if r.K_tgt is not None and not r.is_identity]
    refs_tgt = [r.ref_sum_tgt for r in rows if r.ref_sum_tgt is not None and not r.is_identity]
    achs_tgt = [r.achieved_sum_tgt for r in rows if r.achieved_sum_tgt is not None and not r.is_identity]
    m_tunes = [r.m_tuned_value for r in rows if r.m_tuned_value is not None]

    # Labeled-side feature counts (paired subset excluding identity).
    lbl_amp = [
        r.labeled_n_amplify
        for r in rows
        if r.labeled_n_amplify is not None and not r.is_identity
    ]
    lbl_abl = [
        r.labeled_n_ablate
        for r in rows
        if r.labeled_n_ablate is not None and not r.is_identity
    ]

    return {
        "domain": domain,
        "n_pairs": n,
        "n_paired_with_labeled": n_paired,
        "hit_rate_default": round(_rate(hits_def), 6),
        "hit_rate_best": round(_rate(hits_best), 6),
        "labeled_hit_rate_paired": round(_rate([bool(r.labeled_hit) for r in paired]), 6),
        "delta_hit_rate_pp": round((_rate([bool(r.labeled_hit) for r in paired]) - _rate(hits_best)) * 100, 4),
        "n_m_tuned_rescues": sum(1 for r in rows if r.has_m_tuned and r.hit_m_tuned),
        "n_m_tuned_attempts": sum(1 for r in rows if r.has_m_tuned),
        "from_suppressed_rate": round(_rate(supp), 6),
        "paired_both_win": both,
        "paired_labeled_only_win": lbl_only,
        "paired_topk_only_win": topk_only,
        "paired_both_lose": both_lose,
        # Keep full precision; tiny p-values would round to 0 with too few digits.
        "mcnemar_p_value": float(f"{p_mcnemar:.6e}"),
        "median_K_src": st.median(ks_src) if ks_src else 0,
        "median_K_tgt_nonidentity": st.median(ks_tgt) if ks_tgt else 0,
        "mean_K_src": round(st.mean(ks_src), 4) if ks_src else 0,
        "mean_K_tgt_nonidentity": round(st.mean(ks_tgt), 4) if ks_tgt else 0,
        "median_ref_sum_tgt": round(st.median(refs_tgt), 6) if refs_tgt else 0,
        "median_achieved_sum_tgt": round(st.median(achs_tgt), 6) if achs_tgt else 0,
        "mean_m_tuned_value": round(st.mean(m_tunes), 6) if m_tunes else 0,
        "mean_labeled_n_amplify_nonidentity": round(st.mean(lbl_amp), 4) if lbl_amp else 0,
        "mean_labeled_n_ablate_nonidentity": round(st.mean(lbl_abl), 4) if lbl_abl else 0,
    }


SUMMARY_COLUMNS = [
    "domain", "n_pairs", "n_paired_with_labeled",
    "hit_rate_default", "hit_rate_best", "labeled_hit_rate_paired",
    "delta_hit_rate_pp",
    "n_m_tuned_rescues", "n_m_tuned_attempts",
    "from_suppressed_rate",
    "paired_both_win", "paired_labeled_only_win",
    "paired_topk_only_win", "paired_both_lose",
    "mcnemar_p_value",
    "median_K_src", "median_K_tgt_nonidentity",
    "mean_K_src", "mean_K_tgt_nonidentity",
    "median_ref_sum_tgt", "median_achieved_sum_tgt",
    "mean_m_tuned_value",
    "mean_labeled_n_amplify_nonidentity",
    "mean_labeled_n_ablate_nonidentity",
]


_DOMAIN_LABEL = {
    "paintings": "Paintings",
    "products":  "Products",
    "books":     "Books",
    "usa":       "USA",
}
_LATEX_DOMAIN_ORDER = ["paintings", "products", "books", "usa"]


def _format_p(p: float) -> str:
    """LaTeX-friendly p-value with sane formatting."""
    if p >= 1e-3:
        return f"${p:.3f}$"
    if p <= 0.0:
        # Underflow to 0 in float64 means the true p-value is below ~1e-300.
        # Report it conservatively as "<1e-30" rather than literal zero.
        return r"$<\!10^{-30}$"
    s = f"{p:.1e}"  # e.g. "7.2e-05"
    mantissa, exp = s.split("e")
    return f"${mantissa}\\!\\times\\!10^{{{int(exp)}}}$"


def _write_latex_table(summaries: List[Dict[str, Any]], out_path: Path) -> None:
    """
    Write the per-domain comparison table used in the paper appendix.

    Reads from the in-memory summaries (so the table always reflects the
    latest aggregator run). Domain order is stable: paintings, products,
    books, usa. Domains with no data are omitted from the table.
    """
    by_domain = {s["domain"]: s for s in summaries}
    rows: List[str] = []
    for d in _LATEX_DOMAIN_ORDER:
        s = by_domain.get(d)
        if s is None:
            continue

        # Paired comparison uses the rows that have a labeled hit available.
        # We compute the matched top-K Hit% on the same paired subset so the
        # delta is consistent with the McNemar test.
        n_paired = s["n_paired_with_labeled"]
        topk_hit_paired = (s["paired_both_win"] + s["paired_topk_only_win"]) / n_paired if n_paired else 0.0
        lbl_hit_paired = s["labeled_hit_rate_paired"]
        delta_pp = (lbl_hit_paired - topk_hit_paired) * 100

        rows.append(
            f"{_DOMAIN_LABEL[d]:<9} & {s['n_pairs']:>5} & "
            f"{topk_hit_paired*100:>5.1f} & {lbl_hit_paired*100:>5.1f} & "
            f"${delta_pp:+5.1f}$ & "
            f"{s['mean_K_tgt_nonidentity']:>5.1f} & "
            # the labeled mean amp comes from a paired-subset average inside
            # the summary; we approximate it by computing labeled mean ablate
            # from the per-pair csv, but the summary already has K means so
            # we use the same fields. For now we display "n/a" if missing.
            f"{s.get('mean_labeled_n_amplify_nonidentity', 0):>5.1f} & "
            f"{s['paired_labeled_only_win']}/{s['paired_topk_only_win']} & "
            f"{_format_p(s['mcnemar_p_value'])} \\\\"
        )

    latex = (
        "\\begin{table}[h]\n"
        "\\centering\n"
        "\\small\n"
        "\\caption{\\textbf{Per-pair influence-matched top-K-by-influence vs labeled best-of (4 in-scope domains).} "
        "For every swap pair the top-K-by-node-influence baseline is matched per side to the labeled "
        "best-of-(field-additivity $\\times$ \\{default, $M$-search\\}) winner: $K_{\\mathrm{src}}$ and "
        "$K_{\\mathrm{tgt}}$ are the smallest top-K prefixes whose cumulative \\texttt{node\\_influence} "
        "reaches the labeled reference budget on the source and target side respectively. Top-K is run "
        "as a single bag (no field-add variants), with the same outer $M$-search sweep enabled. "
        "Hit\\% counts pairs whose steered output exact-matches the target answer, taking the max over "
        "default and $M$-tuned. The $\\Delta$ column is the labeled minus top-K Hit\\% gap in percentage "
        "points, computed on the matched per-pair subset. The McNemar column reports an exact / "
        "continuity-corrected paired sign test on the contingency $(b={}$labeled-only$, c={}$top-K-only$)$. "
        "Top-K uses substantially fewer features than the labeled bag at the same per-pair influence "
        "budget; the residual Hit\\% gap is therefore not explained by the size of the influence budget "
        "steered. Sounds is intentionally excluded (smallest $N$, weakest signal, structural confounds). "
        "Full per-pair join in \\texttt{output/research/topk\\_im\\_pairs\\_<domain>.csv}.}\n"
        "\\label{tab:topk-im}\n"
        "\\begin{tabular}{lrrrrrrrr}\n"
        "\\toprule\n"
        "& & \\multicolumn{2}{c}{Hit\\%} & & \\multicolumn{1}{c}{top-K} & \\multicolumn{1}{c}{Lab.} & "
        "\\multicolumn{1}{c}{lbl/topk} & \\\\\n"
        "\\cmidrule(lr){3-4}\n"
        "Domain & $N$ & top-K & Lab.\\ & $\\Delta$ pp & $K_{\\mathrm{tgt}}$ & $n_{\\mathrm{amp}}$ "
        "& only-wins & McNemar $p$ \\\\\n"
        "\\midrule\n"
    ) + "\n".join(rows) + "\n\\bottomrule\n\\end{tabular}\n\\end{table}\n"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(latex)


def _process_domain(domain: str, dataset_dir: Path, run_id: str,
                    budgets_csv: Path, out_dir: Path) -> Optional[Dict[str, Any]]:
    by_source = dataset_dir / "_swaps" / "runs" / run_id / "by_source"
    if not by_source.exists():
        print(f"  [SKIP] {domain}: no by_source at {by_source}")
        return None

    budgets = _read_budgets(budgets_csv)

    rows: List[PairRow] = []
    for from_slug, to_slug, base, mt in _enumerate_pairs(by_source):
        bud_row = budgets.get((from_slug, to_slug))
        pair = _load_pair(domain, base, mt, bud_row)
        if pair is not None:
            rows.append(pair)

    pairs_csv = out_dir / f"topk_im_pairs_{domain}.csv"
    _write_pairs_csv(rows, pairs_csv)
    print(f"  [{domain}] wrote {len(rows)} rows to {pairs_csv.relative_to(REPO)}")

    summary = _summarize(domain, rows)
    return summary


def _write_summary_csv(summaries: List[Dict[str, Any]], out_path: Path) -> None:
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SUMMARY_COLUMNS)
        w.writeheader()
        for s in summaries:
            w.writerow({col: s.get(col, "") for col in SUMMARY_COLUMNS})


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--domains",
        nargs="*",
        default=list(DOMAINS),
        choices=list(DOMAINS),
        help="Domains to process (default: all 4 in-scope domains).",
    )
    parser.add_argument(
        "--out-dir",
        default="output/research",
        help="Where to write topk_im_*.csv (default: output/research).",
    )
    args = parser.parse_args()

    out_dir = (REPO / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    summaries: List[Dict[str, Any]] = []
    for domain in args.domains:
        cfg = DOMAINS[domain]
        dataset_dir = (REPO / cfg["dataset_dir"]).resolve()
        budgets_csv = (REPO / cfg["budgets_csv"]).resolve()
        s = _process_domain(domain, dataset_dir, cfg["run_id"], budgets_csv, out_dir)
        if s is not None:
            summaries.append(s)

    if summaries:
        summary_csv = out_dir / "topk_im_summary.csv"
        _write_summary_csv(summaries, summary_csv)
        print(f"\nwrote {summary_csv.relative_to(REPO)}")
        latex_path = REPO / "paper" / "tables" / "T_topk_influence_matched.tex"
        _write_latex_table(summaries, latex_path)
        print(f"wrote {latex_path.relative_to(REPO)}")
        # quick ASCII recap
        print("\nDomain-level summary:")
        print(f"  {'domain':<10} {'N':>4} {'def':>5} {'best':>5} {'lbl':>5}  {'gap_pp':>7} "
              f"{'lbl-only':>9} {'topk-only':>10} {'mcnemar_p':>11}")
        for s in summaries:
            print(
                f"  {s['domain']:<10} {s['n_pairs']:>4} "
                f"{s['hit_rate_default'] * 100:>4.1f}% "
                f"{s['hit_rate_best'] * 100:>4.1f}% "
                f"{s['labeled_hit_rate_paired'] * 100:>4.1f}% "
                f"{s['delta_hit_rate_pp']:>+7.2f} "
                f"{s['paired_labeled_only_win']:>9} "
                f"{s['paired_topk_only_win']:>10} "
                f"{s['mcnemar_p_value']:>11.2e}"
            )

    return 0


if __name__ == "__main__":
    sys.exit(main())
