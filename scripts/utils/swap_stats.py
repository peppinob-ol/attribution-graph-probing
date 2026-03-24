"""
Aggregate statistics and cross-condition comparison for swap experiments.

Companion to swap_query.py -- this module computes group-level stats,
cross-run comparisons, per-entity breakdowns, and basic statistical tests
for debunking and validating attribution graph interpretation claims.

Usage::

    from scripts.utils.swap_query import SwapQuery
    from scripts.utils.swap_stats import SwapStats

    q = SwapQuery()
    s = SwapStats(q)

    # Aggregate stats for one condition
    agg = s.aggregate("usa_states_batch", "fullscale_usa_field_add",
                       variant="add_state")
    s.print_aggregate(agg)

    # Compare labeled vs random
    comp = s.compare(
        a=dict(dataset="usa_states_batch", run="fullscale_usa_labeled"),
        b=dict(dataset="usa_states_batch", run="fullscale_usa_random"),
    )
    s.print_comparison(comp)

    # Per-entity breakdown
    ent = s.per_entity("usa_states_batch", "fullscale_usa_field_add",
                        variant="add_state", role="source")
    s.print_entity_table(ent)

    # Same pair across conditions
    paired = s.cross_run(
        "usa_states_batch", "mississippi_gulfport", "arizona_tucson",
        runs={"labeled": "fullscale_usa_labeled",
              "random": "fullscale_usa_random",
              "add_state": ("fullscale_usa_field_add", "add_state")},
    )
    s.print_cross_run(paired)
"""

from __future__ import annotations

import math
import random as _random
from collections import defaultdict
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Sequence, Tuple, Union

from scripts.utils.swap_query import SwapQuery, SwapSummary


# Numeric fields on SwapSummary suitable for aggregation
_NUMERIC_FIELDS = [
    "source_error_node_pct", "target_error_node_pct",
    "default_first_prob", "steered_first_prob",
    "flip_position", "initial_gap", "best_gap", "gap_closure",
    "control_stability_mean", "vs_max", "vs_topk", "rank_in_group",
    "target_baseline_rank", "source_baseline_rank",
    "gap_closure_0", "target_rank_improvement",
    "ablate_count", "amplify_count", "total_count", "tier",
]

_BOOL_FIELDS = [
    "steered_has_to_answer", "from_suppressed",
    "first_token_matches_target", "flip_at_0",
]


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class AggregateStats:
    """Summary statistics for a group of swaps."""
    label: str = ""
    n: int = 0
    rates: Dict[str, float] = field(default_factory=dict)
    means: Dict[str, Optional[float]] = field(default_factory=dict)
    medians: Dict[str, Optional[float]] = field(default_factory=dict)
    stds: Dict[str, Optional[float]] = field(default_factory=dict)
    p25: Dict[str, Optional[float]] = field(default_factory=dict)
    p75: Dict[str, Optional[float]] = field(default_factory=dict)


@dataclass
class ComparisonResult:
    """Side-by-side comparison of two conditions."""
    label_a: str
    label_b: str
    stats_a: AggregateStats
    stats_b: AggregateStats
    deltas: Dict[str, Optional[float]] = field(default_factory=dict)
    cohens_d: Dict[str, Optional[float]] = field(default_factory=dict)
    bootstrap_ci: Dict[str, Tuple[float, float]] = field(default_factory=dict)


@dataclass
class EntityRow:
    """Per-entity aggregate."""
    slug: str
    n: int = 0
    error_node_pct: Optional[float] = None
    hit_rate: float = 0.0
    suppression_rate: float = 0.0
    mean_gap_closure: Optional[float] = None
    mean_vs_max: Optional[float] = None
    mean_rank_in_group: Optional[float] = None
    median_rank_in_group: Optional[float] = None
    mean_tier: Optional[float] = None


# ---------------------------------------------------------------------------
# Core engine
# ---------------------------------------------------------------------------

class SwapStats:
    """Aggregate statistics and comparison utilities.

    Wraps a :class:`SwapQuery` instance and adds group-level computation.
    """

    def __init__(self, query: Optional[SwapQuery] = None):
        self.q = query or SwapQuery()

    # -- Aggregate ----------------------------------------------------------

    def aggregate(
        self,
        dataset: str,
        run: str,
        variant: Optional[str] = None,
        where: Optional[Callable[[SwapSummary], bool]] = None,
        label: str = "",
    ) -> AggregateStats:
        """Compute summary statistics over a filtered set of swaps."""
        samples = self.q.search(
            dataset=dataset, run=run, variant=variant,
            sort_by="vs_max", top_n=999_999, where=where,
        )
        return self._compute_agg(samples, label or f"{run}/{variant or '*'}")

    # -- Compare ------------------------------------------------------------

    def compare(
        self,
        a: Dict[str, Any],
        b: Dict[str, Any],
        metrics: Optional[List[str]] = None,
        bootstrap_n: int = 2000,
        seed: int = 42,
    ) -> ComparisonResult:
        """Compare two conditions (each a dict of aggregate() kwargs).

        Returns deltas, Cohen's d, and bootstrap 95% CIs for key metrics.
        """
        if metrics is None:
            metrics = ["vs_max", "vs_topk", "gap_closure",
                       "rank_in_group", "target_baseline_rank"]

        label_a = a.pop("label", str(a.get("run", "A")))
        label_b = b.pop("label", str(b.get("run", "B")))
        samples_a = self.q.search(**{**a, "sort_by": "vs_max", "top_n": 999_999})
        samples_b = self.q.search(**{**b, "sort_by": "vs_max", "top_n": 999_999})
        stats_a = self._compute_agg(samples_a, label_a)
        stats_b = self._compute_agg(samples_b, label_b)

        deltas: Dict[str, Optional[float]] = {}
        cohens: Dict[str, Optional[float]] = {}
        boot_ci: Dict[str, Tuple[float, float]] = {}

        for m in metrics:
            va = _extract_values(samples_a, m)
            vb = _extract_values(samples_b, m)
            deltas[m] = _safe_sub(stats_a.means.get(m), stats_b.means.get(m))
            cohens[m] = _cohens_d(va, vb)
            boot_ci[m] = _bootstrap_ci(va, vb, n=bootstrap_n, seed=seed)

        for bf in _BOOL_FIELDS:
            ra = stats_a.rates.get(bf, 0)
            rb = stats_b.rates.get(bf, 0)
            deltas[bf] = ra - rb

        return ComparisonResult(
            label_a=stats_a.label, label_b=stats_b.label,
            stats_a=stats_a, stats_b=stats_b,
            deltas=deltas, cohens_d=cohens, bootstrap_ci=boot_ci,
        )

    # -- Per-entity ---------------------------------------------------------

    def per_entity(
        self,
        dataset: str,
        run: str,
        variant: Optional[str] = None,
        role: str = "source",
        where: Optional[Callable[[SwapSummary], bool]] = None,
    ) -> List[EntityRow]:
        """Group swaps by entity (source or target) and compute per-entity stats."""
        samples = self.q.search(
            dataset=dataset, run=run, variant=variant,
            sort_by="vs_max", top_n=999_999, where=where,
        )
        groups: Dict[str, List[SwapSummary]] = defaultdict(list)
        for s in samples:
            key = s.from_slug if role == "source" else s.to_slug
            groups[key].append(s)

        err_field = "source_error_node_pct" if role == "source" else "target_error_node_pct"
        rows: List[EntityRow] = []
        for slug, group in sorted(groups.items()):
            n = len(group)
            hits = sum(1 for s in group if s.steered_has_to_answer)
            sups = sum(1 for s in group if s.from_suppressed)
            gc_vals = _extract_values(group, "gap_closure")
            vm_vals = _extract_values(group, "vs_max")
            rk_vals = _extract_values(group, "rank_in_group")
            tier_vals = _extract_values(group, "tier")
            rows.append(EntityRow(
                slug=slug, n=n,
                error_node_pct=getattr(group[0], err_field, None),
                hit_rate=hits / n if n else 0,
                suppression_rate=sups / n if n else 0,
                mean_gap_closure=_mean(gc_vals),
                mean_vs_max=_mean(vm_vals),
                mean_rank_in_group=_mean(rk_vals),
                median_rank_in_group=_median(rk_vals),
                mean_tier=_mean(tier_vals),
            ))
        return rows

    # -- Cross-run (same pair, multiple conditions) -------------------------

    def cross_run(
        self,
        dataset: str,
        from_slug: str,
        to_slug: str,
        runs: Dict[str, Union[str, Tuple[str, str]]],
    ) -> Dict[str, Optional[Dict[str, Any]]]:
        """Load the same entity pair across multiple runs/variants.

        Parameters
        ----------
        runs : dict
            ``{label: run_id}`` or ``{label: (run_id, variant)}``.

        Returns dict of ``{label: swap_detail_or_None}``.
        """
        results = {}
        for label, spec in runs.items():
            if isinstance(spec, tuple):
                run_id, variant = spec
            else:
                run_id, variant = spec, None
            detail = self.q.get(dataset, run_id, from_slug, to_slug,
                                variant=variant)
            results[label] = detail
        return results

    # -- Printers -----------------------------------------------------------

    @staticmethod
    def print_aggregate(agg: AggregateStats) -> str:
        lines = [f"=== {agg.label}  (N={agg.n}) ===", ""]
        lines.append("Rates:")
        for k, v in sorted(agg.rates.items()):
            lines.append(f"  {k:>30s}: {v:>8.1%}")
        lines.append("")
        lines.append(f"{'Metric':>30s}  {'mean':>10s}  {'median':>10s}  "
                      f"{'std':>10s}  {'p25':>10s}  {'p75':>10s}")
        lines.append("-" * 90)
        for k in _NUMERIC_FIELDS:
            if k in agg.means and agg.means[k] is not None:
                lines.append(
                    f"{k:>30s}  {_f(agg.means[k]):>10s}  "
                    f"{_f(agg.medians.get(k)):>10s}  "
                    f"{_f(agg.stds.get(k)):>10s}  "
                    f"{_f(agg.p25.get(k)):>10s}  "
                    f"{_f(agg.p75.get(k)):>10s}")
        text = "\n".join(lines)
        print(text)
        return text

    @staticmethod
    def print_comparison(comp: ComparisonResult) -> str:
        lines = [
            f"=== {comp.label_a} vs {comp.label_b} ===",
            f"    N_a={comp.stats_a.n}  N_b={comp.stats_b.n}", "",
        ]
        lines.append(f"{'Metric':>30s}  {'A':>10s}  {'B':>10s}  "
                      f"{'Delta':>10s}  {'Cohen_d':>10s}  {'95% CI':>20s}")
        lines.append("-" * 100)
        all_keys = set(comp.deltas.keys())
        for k in sorted(all_keys):
            ma = comp.stats_a.means.get(k) or comp.stats_a.rates.get(k)
            mb = comp.stats_b.means.get(k) or comp.stats_b.rates.get(k)
            d = comp.deltas.get(k)
            cd = comp.cohens_d.get(k)
            ci = comp.bootstrap_ci.get(k)
            ci_str = f"[{ci[0]:+.3f}, {ci[1]:+.3f}]" if ci else ""
            lines.append(
                f"{k:>30s}  {_f(ma):>10s}  {_f(mb):>10s}  "
                f"{_f(d, sign=True):>10s}  {_f(cd):>10s}  {ci_str:>20s}")
        text = "\n".join(lines)
        print(text)
        return text

    @staticmethod
    def print_entity_table(
        rows: List[EntityRow],
        sort_by: str = "error_node_pct",
        ascending: bool = False,
    ) -> str:
        rows = sorted(rows, key=lambda r: getattr(r, sort_by) or 0,
                       reverse=not ascending)
        lines = [
            f"{'slug':>30s}  {'N':>4s}  {'err%':>6s}  {'hit%':>6s}  "
            f"{'sup%':>6s}  {'gapCl':>8s}  {'vsMax':>8s}  "
            f"{'rkGrp':>8s}  {'tier':>6s}",
            "-" * 100,
        ]
        for r in rows:
            lines.append(
                f"{r.slug:>30s}  {r.n:>4d}  "
                f"{_f(r.error_node_pct):>6s}  "
                f"{r.hit_rate:>5.1%}  {r.suppression_rate:>5.1%}  "
                f"{_f(r.mean_gap_closure):>8s}  {_f(r.mean_vs_max):>8s}  "
                f"{_f(r.mean_rank_in_group):>8s}  {_f(r.mean_tier):>6s}")
        text = "\n".join(lines)
        print(text)
        return text

    @staticmethod
    def print_cross_run(paired: Dict[str, Optional[Dict[str, Any]]]) -> str:
        lines = []
        for label, data in paired.items():
            if data is None:
                lines.append(f"  {label}: NOT FOUND")
                continue
            ev = data.get("evaluation", {})
            em = ev.get("exact_match", {})
            ft = ev.get("first_token", {})
            traj = ev.get("logit_trajectory", {}).get("summary", {})
            cg = (ev.get("logit_trajectory", {})
                  .get("contrast_groups", {})
                  .get("same_dataset", {})
                  .get("aggregate", {}))
            ctrl = data.get("metadata", {}).get("control", {})
            lines.append(
                f"  {label:20s}: "
                f"hit={em.get('steered_has_to_answer')!s:>5s}  "
                f"sup={em.get('from_suppressed')!s:>5s}  "
                f"gap_cl={_f(traj.get('gap_closure')):>8s}  "
                f"vsMax={_f(cg.get('best_target_minus_max')):>8s}  "
                f"rkGrp={_f(cg.get('best_rank_within')):>6s}  "
                f"1st={ft.get('steered', '?')!r:>12s}  "
                f"fields={ctrl.get('concept_subsets_used', [])}")
        text = "\n".join(lines)
        print(text)
        return text

    # -- Internal -----------------------------------------------------------

    @staticmethod
    def _compute_agg(
        samples: List[SwapSummary], label: str,
    ) -> AggregateStats:
        agg = AggregateStats(label=label, n=len(samples))
        for bf in _BOOL_FIELDS:
            vals = [getattr(s, bf) for s in samples]
            true_count = sum(1 for v in vals if v is True)
            known = sum(1 for v in vals if v is not None)
            agg.rates[bf] = true_count / known if known else 0.0
        for nf in _NUMERIC_FIELDS:
            vals = _extract_values(samples, nf)
            agg.means[nf] = _mean(vals)
            agg.medians[nf] = _median(vals)
            agg.stds[nf] = _std(vals)
            agg.p25[nf] = _percentile(vals, 25)
            agg.p75[nf] = _percentile(vals, 75)
        return agg


# ---------------------------------------------------------------------------
# Statistics helpers (no numpy dependency)
# ---------------------------------------------------------------------------

def _extract_values(samples: Sequence[SwapSummary], field_name: str) -> List[float]:
    vals = []
    for s in samples:
        v = getattr(s, field_name, None)
        if v is not None and isinstance(v, (int, float)) and not math.isnan(v):
            vals.append(float(v))
    return vals


def _mean(vals: List[float]) -> Optional[float]:
    return sum(vals) / len(vals) if vals else None


def _median(vals: List[float]) -> Optional[float]:
    if not vals:
        return None
    s = sorted(vals)
    n = len(s)
    if n % 2 == 1:
        return s[n // 2]
    return (s[n // 2 - 1] + s[n // 2]) / 2


def _std(vals: List[float]) -> Optional[float]:
    if len(vals) < 2:
        return None
    m = sum(vals) / len(vals)
    return math.sqrt(sum((x - m) ** 2 for x in vals) / (len(vals) - 1))


def _percentile(vals: List[float], pct: int) -> Optional[float]:
    if not vals:
        return None
    s = sorted(vals)
    k = (len(s) - 1) * pct / 100
    lo = int(math.floor(k))
    hi = min(lo + 1, len(s) - 1)
    frac = k - lo
    return s[lo] + frac * (s[hi] - s[lo])


def _cohens_d(a: List[float], b: List[float]) -> Optional[float]:
    """Cohen's d effect size (pooled std)."""
    if len(a) < 2 or len(b) < 2:
        return None
    ma, mb = sum(a) / len(a), sum(b) / len(b)
    va = sum((x - ma) ** 2 for x in a) / (len(a) - 1)
    vb = sum((x - mb) ** 2 for x in b) / (len(b) - 1)
    pooled = math.sqrt(((len(a) - 1) * va + (len(b) - 1) * vb)
                       / (len(a) + len(b) - 2))
    if pooled == 0:
        return None
    return (ma - mb) / pooled


def _bootstrap_ci(
    a: List[float], b: List[float],
    n: int = 2000, ci: float = 0.95, seed: int = 42,
) -> Optional[Tuple[float, float]]:
    """Bootstrap CI for difference in means (A - B)."""
    if not a or not b:
        return None
    rng = _random.Random(seed)
    diffs = []
    for _ in range(n):
        sa = [rng.choice(a) for _ in range(len(a))]
        sb = [rng.choice(b) for _ in range(len(b))]
        diffs.append(sum(sa) / len(sa) - sum(sb) / len(sb))
    diffs.sort()
    alpha = (1 - ci) / 2
    lo_idx = int(math.floor(alpha * n))
    hi_idx = int(math.ceil((1 - alpha) * n)) - 1
    return (diffs[lo_idx], diffs[min(hi_idx, len(diffs) - 1)])


def _safe_sub(a: Optional[float], b: Optional[float]) -> Optional[float]:
    if a is None or b is None:
        return None
    return a - b


def _f(v: Optional[float], sign: bool = False) -> str:
    if v is None:
        return "-"
    if isinstance(v, int) or (isinstance(v, float) and v == int(v) and abs(v) < 1e6):
        fmt = f"{int(v):+d}" if sign else f"{int(v)}"
        return fmt
    fmt = f"{v:+.4f}" if sign else f"{v:.4f}"
    return fmt
