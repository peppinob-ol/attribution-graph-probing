"""
Query utility for swap experiment data.

Enables programmatic exploration of individual swap samples with filtering,
sorting, and comprehensive indicator display. Designed for agentic field
research on attribution graph interpretation.

Usage::

    from scripts.utils.swap_query import SwapQuery

    q = SwapQuery()

    # Find high-error-node samples in the additive run, state-only variant
    results = q.search(
        dataset="usa_states_batch",
        run="fullscale_usa_field_add",
        variant="add_state",
        sort_by="source_error_node_pct",
        top_n=5,
    )

    # Get full detail for one sample
    detail = q.get(
        "usa_states_batch", "fullscale_usa_field_add",
        "alabama_birmingham", "alaska_anchorage",
        variant="add_state",
    )

    # Pretty-print all indicators
    q.describe(detail)
"""

from __future__ import annotations

import csv
import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Sequence, Union


OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "output"


# ---------------------------------------------------------------------------
# Flat summary: lightweight representation for search/sort/filter
# ---------------------------------------------------------------------------

@dataclass
class SwapSummary:
    """Flat record with key indicators, suitable for sorting and filtering."""

    # identity
    dataset: str
    run_id: str
    variant: str
    from_slug: str
    to_slug: str
    swap_id: str
    file_path: str

    # entity-level
    source_error_node_pct: Optional[float] = None
    target_error_node_pct: Optional[float] = None

    # evaluation flags
    steered_has_to_answer: Optional[bool] = None
    from_suppressed: Optional[bool] = None
    first_token_matches_target: Optional[bool] = None

    # first token
    default_first_token: str = ""
    default_first_prob: Optional[float] = None
    steered_first_token: str = ""
    steered_first_prob: Optional[float] = None

    # trajectory
    flip_position: Optional[int] = None
    initial_gap: Optional[float] = None
    best_gap: Optional[float] = None
    gap_closure: Optional[float] = None
    control_stability_mean: Optional[float] = None

    # contrast group (same_dataset)
    vs_max: Optional[float] = None
    vs_topk: Optional[float] = None
    rank_in_group: Optional[int] = None

    # baseline logits
    target_baseline_rank: Optional[int] = None
    source_baseline_rank: Optional[int] = None

    # position 0
    flip_at_0: Optional[bool] = None
    gap_closure_0: Optional[float] = None
    target_rank_improvement: Optional[int] = None

    # intervention counts
    ablate_count: Optional[int] = None
    amplify_count: Optional[int] = None
    total_count: Optional[int] = None

    # control metadata
    control_mode: str = ""
    fields_used: List[str] = field(default_factory=list)

    # classification (if present)
    tier: Optional[float] = None

    # raw text (truncated for display)
    default_output_preview: str = ""
    steered_output_preview: str = ""

    def as_dict(self) -> Dict[str, Any]:
        d = {}
        for k in self.__dataclass_fields__:
            d[k] = getattr(self, k)
        return d


# ---------------------------------------------------------------------------
# Error node influence cache
# ---------------------------------------------------------------------------

class _ErrorNodeCache:
    """Lazily computes and caches error_node_influence_pct per entity."""

    def __init__(self):
        self._cache: Dict[str, Dict[str, Optional[float]]] = {}

    def get(self, dataset_dir: Path, slug: str) -> Optional[float]:
        ds_key = str(dataset_dir)
        if ds_key not in self._cache:
            self._cache[ds_key] = {}
        if slug in self._cache[ds_key]:
            return self._cache[ds_key][slug]
        pct = self._compute(dataset_dir, slug)
        self._cache[ds_key][slug] = pct
        return pct

    def preload(self, dataset_dir: Path) -> Dict[str, float]:
        """Pre-scan all entities in a dataset. Returns {slug: pct}."""
        ds_key = str(dataset_dir)
        if ds_key in self._cache and len(self._cache[ds_key]) > 5:
            return {k: v for k, v in self._cache[ds_key].items()
                    if v is not None}
        self._cache.setdefault(ds_key, {})
        result: Dict[str, float] = {}
        for edir in sorted(dataset_dir.iterdir()):
            if not edir.is_dir() or edir.name.startswith("_"):
                continue
            slug = edir.name.lower().replace(" ", "_")
            pct = self.get(dataset_dir, slug)
            if pct is not None:
                result[slug] = pct
        return result

    @staticmethod
    def _compute(dataset_dir: Path, slug: str) -> Optional[float]:
        entity_dir = _find_entity_dir(dataset_dir, slug)
        if entity_dir is None:
            return None
        # Try manifest first
        manifest_path = entity_dir / "manifest.json"
        if manifest_path.exists():
            try:
                with open(manifest_path, "r", encoding="utf-8") as f:
                    mf = json.load(f)
                pct = mf.get("graph_quality", {}).get("error_node_influence_pct")
                if pct is not None:
                    return float(pct)
            except (json.JSONDecodeError, IOError, ValueError):
                pass
        # Fallback: compute from CSV
        csv_path = (entity_dir / "00 Graph Generation"
                    / "graph_feature_static_metrics.csv")
        if not csv_path.exists():
            return None
        try:
            total = 0.0
            error = 0.0
            with open(csv_path, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    ni_str = (row.get("node_influence") or "").strip()
                    if not ni_str:
                        continue
                    ni = float(ni_str)
                    total += ni
                    if row.get("feature", "").strip() == "-1":
                        error += ni
            if total > 0:
                return round(error / total * 100, 2)
        except (IOError, ValueError):
            pass
        return None


def _find_entity_dir(dataset_dir: Path, slug: str) -> Optional[Path]:
    """Resolve entity directory with case-insensitive fallback."""
    direct = dataset_dir / slug
    if direct.exists():
        return direct
    slug_lower = slug.lower()
    for candidate in dataset_dir.iterdir():
        if (candidate.is_dir()
                and candidate.name.lower().replace(" ", "_") == slug_lower):
            return candidate
    return None


# ---------------------------------------------------------------------------
# Main query engine
# ---------------------------------------------------------------------------

class SwapQuery:
    """Query interface for swap experiment data on disk.

    Parameters
    ----------
    output_root : Path or str, optional
        Root output directory (default: ``<repo>/output``).
    """

    def __init__(self, output_root: Union[str, Path, None] = None):
        self.output_root = Path(output_root) if output_root else OUTPUT_ROOT
        self._error_cache = _ErrorNodeCache()

    # -- Discovery ----------------------------------------------------------

    def list_datasets(self) -> List[str]:
        """Return dataset directory names that contain ``_swaps/runs/``."""
        result = []
        for d in sorted(self.output_root.iterdir()):
            if d.is_dir() and (d / "_swaps" / "runs").is_dir():
                result.append(d.name)
        return result

    def list_runs(self, dataset: str) -> List[str]:
        """Return run IDs for a dataset."""
        runs_dir = self.output_root / dataset / "_swaps" / "runs"
        if not runs_dir.is_dir():
            return []
        return sorted(
            d.name for d in runs_dir.iterdir()
            if d.is_dir() and (d / "by_source").is_dir()
        )

    def list_variants(self, dataset: str, run: str) -> List[str]:
        """Return distinct variant suffixes found in a run."""
        by_source = (self.output_root / dataset / "_swaps" / "runs"
                     / run / "by_source")
        if not by_source.is_dir():
            return []
        variants = set()
        for src_dir in by_source.iterdir():
            if not src_dir.is_dir():
                continue
            for f in src_dir.iterdir():
                if not f.name.startswith("to_") or f.suffix != ".json":
                    continue
                stem = f.stem.replace("to_", "", 1)
                parts = stem.split("__", 1)
                if len(parts) == 2:
                    variants.add(parts[1])
                else:
                    variants.add("")
        return sorted(variants)

    def entity_error_nodes(self, dataset: str) -> Dict[str, float]:
        """Return {slug: error_node_influence_pct} for all entities."""
        ds_dir = self.output_root / dataset
        return self._error_cache.preload(ds_dir)

    # -- Single sample retrieval --------------------------------------------

    def get(
        self,
        dataset: str,
        run: str,
        from_slug: str,
        to_slug: str,
        variant: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Load full swap JSON and enrich with entity-level metrics.

        Returns the raw JSON dict with added ``_query`` block containing
        error_node_influence_pct for source/target and derived metrics.
        """
        fpath = self._resolve_swap_path(dataset, run, from_slug, to_slug,
                                        variant)
        if fpath is None or not fpath.exists():
            return None
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)
        ds_dir = self.output_root / dataset
        src_slug = data.get("source", {}).get("slug", from_slug)
        tgt_slug = data.get("target", {}).get("slug", to_slug)
        data["_query"] = {
            "file": str(fpath),
            "dataset": dataset,
            "run": run,
            "variant": variant or self._detect_variant(fpath),
            "source_error_node_pct": self._error_cache.get(
                ds_dir, src_slug.lower().replace(" ", "_")),
            "target_error_node_pct": self._error_cache.get(
                ds_dir, tgt_slug.lower().replace(" ", "_")),
        }
        return data

    # -- Search / filter ----------------------------------------------------

    def search(
        self,
        dataset: str,
        run: str,
        variant: Optional[str] = None,
        source: Optional[str] = None,
        target: Optional[str] = None,
        sort_by: str = "vs_max",
        ascending: bool = False,
        top_n: int = 10,
        where: Optional[Callable[[SwapSummary], bool]] = None,
        skip_identity: bool = True,
    ) -> List[SwapSummary]:
        """Scan swap files and return sorted/filtered summaries.

        Parameters
        ----------
        dataset, run : str
            Which dataset and run to query.
        variant : str, optional
            Filter to a specific variant suffix (e.g. ``"add_state"``).
            ``None`` returns all variants; ``""`` returns canonical (no suffix).
        source, target : str, optional
            Filter by source/target entity slug (substring match).
        sort_by : str
            Any numeric field on ``SwapSummary`` (e.g. ``"vs_max"``,
            ``"source_error_node_pct"``, ``"gap_closure"``).
        ascending : bool
            Sort order. Default descending (highest first).
        top_n : int
            Number of results to return.
        where : callable, optional
            Additional filter ``fn(summary) -> bool``.
        skip_identity : bool
            Exclude identity swaps (source == target).
        """
        by_source = (self.output_root / dataset / "_swaps" / "runs"
                     / run / "by_source")
        if not by_source.is_dir():
            return []

        ds_dir = self.output_root / dataset
        self._error_cache.preload(ds_dir)

        summaries: List[SwapSummary] = []
        for src_dir in sorted(by_source.iterdir()):
            if not src_dir.is_dir():
                continue
            if source and source.lower() not in src_dir.name.lower():
                continue
            for fpath in sorted(src_dir.iterdir()):
                if not fpath.name.startswith("to_") or fpath.suffix != ".json":
                    continue
                file_variant = self._detect_variant(fpath)
                if variant is not None and file_variant != variant:
                    continue
                if target:
                    to_part = fpath.stem.replace("to_", "", 1).split("__")[0]
                    if target.lower() not in to_part.lower():
                        continue
                try:
                    s = self._build_summary(fpath, dataset, run, ds_dir)
                except (json.JSONDecodeError, IOError, KeyError):
                    continue
                if skip_identity and s.from_slug == s.to_slug:
                    continue
                if where and not where(s):
                    continue
                summaries.append(s)

        sort_key = _make_sort_key(sort_by)
        summaries.sort(key=sort_key, reverse=not ascending)
        return summaries[:top_n]

    # -- Pretty print -------------------------------------------------------

    @staticmethod
    def describe(data: Dict[str, Any], max_output_len: int = 200) -> str:
        """Format a full swap dict (from ``get()``) as readable text."""
        lines: List[str] = []

        def _sec(title: str):
            lines.append("")
            lines.append(f"--- {title} ---")

        q = data.get("_query", {})
        src = data.get("source", {})
        tgt = data.get("target", {})
        ev = data.get("evaluation", {})
        meta = data.get("metadata", {})
        ctrl = meta.get("control", {})
        intv = data.get("interventions", {})
        cfg = data.get("config", {})

        # Header
        lines.append(f"=== {data.get('swap_id', '?')} "
                      f"[{q.get('variant', '')}] ===")
        lines.append(f"Dataset: {q.get('dataset')}  "
                      f"Run: {q.get('run')}")

        _sec("Entities")
        for label, obj, err_key in [
            ("Source", src, "source_error_node_pct"),
            ("Target", tgt, "target_error_node_pct"),
        ]:
            fields = {k: v for k, v in obj.items()
                      if k not in ("slug", "prompt", "concept",
                                   "neuronpedia_url", "error_node_influence_pct")}
            err = q.get(err_key) or obj.get("error_node_influence_pct")
            lines.append(
                f"  {label}: {obj.get('slug', '?')}  "
                f"{fields}  error_node={err}%")
        lines.append(f"  Prompt: {src.get('prompt', '?')}")

        _sec("Evaluation")
        lines.append(f"  answer_field={ev.get('answer_field')}  "
                      f"from={ev.get('from_answer')} -> "
                      f"to={ev.get('to_answer')}")
        em = ev.get("exact_match", {})
        lines.append(f"  Exact match: {_compact_dict(em)}")

        ft = ev.get("first_token", {})
        lines.append(
            f"  First token: default={ft.get('default')!r} "
            f"(p={ft.get('default_prob')})  "
            f"steered={ft.get('steered')!r} "
            f"(p={ft.get('steered_prob')})")

        tik = ev.get("target_in_topk", {})
        if tik:
            lines.append(f"  TopK: {_compact_dict(tik)}")

        _sec("Raw output")
        raw = ev.get("raw", {})
        lines.append(f"  Default: {_trunc(raw.get('default_output', ''), max_output_len)}")
        lines.append(f"  Steered: {_trunc(raw.get('steered_output', ''), max_output_len)}")

        _sec("Logit trajectory")
        traj = ev.get("logit_trajectory", {})
        summ = traj.get("summary", {})
        for k in ("flip_position", "initial_gap", "best_gap", "final_gap",
                   "gap_closure", "control_stability_mean",
                   "control_stability_max"):
            if k in summ:
                lines.append(f"  {k}: {summ[k]}")
        gap_traj = summ.get("gap_trajectory")
        if gap_traj:
            lines.append(f"  gap_trajectory: {gap_traj}")

        contrast = traj.get("contrast_groups", {})
        if contrast:
            _sec("Contrast groups")
            for gname, gdata in contrast.items():
                agg = gdata.get("aggregate", {})
                if agg:
                    lines.append(f"  {gname}: {_compact_dict(agg)}")

        bl = ev.get("baseline_logits", {})
        if bl:
            _sec("Baseline logits")
            for k, v in bl.items():
                lines.append(f"  {k}: {_compact_dict(v)}")

        p0 = ev.get("position_0_comparison", {})
        if p0:
            _sec("Position 0 comparison")
            lines.append(f"  {_compact_dict(p0)}")

        _sec("Intervention")
        lines.append(f"  mode={ctrl.get('control_mode')}  "
                      f"fields={ctrl.get('concept_subsets_used')}")
        diag = ctrl.get("diagnostics", {})
        if diag:
            lines.append(f"  active_fields={diag.get('active_fields')}  "
                          f"ablate={diag.get('ablate_fields')}  "
                          f"amplify={diag.get('amplify_fields')}")
        lines.append(f"  counts: ablate={intv.get('ablate_count')} "
                      f"amplify={intv.get('amplify_count')} "
                      f"total={intv.get('total_count')}")
        lines.append(f"  config: M_ablate={cfg.get('M_ablate')} "
                      f"M_amplify={cfg.get('M_amplify')} "
                      f"temp={cfg.get('temperature')}")

        cls = data.get("classification", {})
        if cls:
            _sec("Classification")
            lines.append(f"  tier={cls.get('tier')}  "
                          f"notes={cls.get('notes', '')!r}  "
                          f"manual={cls.get('manually_edited', False)}")

        lines.append("")
        text = "\n".join(lines)
        print(text)
        return text

    @staticmethod
    def describe_summary(s: SwapSummary) -> str:
        """One-line description of a SwapSummary for search results."""
        parts = [
            f"{s.from_slug} -> {s.to_slug}",
            f"[{s.variant}]",
            f"err_src={s.source_error_node_pct}%",
            f"err_tgt={s.target_error_node_pct}%",
            f"hit={s.steered_has_to_answer}",
            f"sup={s.from_suppressed}",
            f"flip@0={s.flip_at_0}",
            f"gap_cl={s.gap_closure}",
            f"vsMax={s.vs_max}",
            f"rkGrp={s.rank_in_group}",
            f"tier={s.tier}",
        ]
        line = "  ".join(parts)
        print(line)
        return line

    def describe_search(self, results: Sequence[SwapSummary]) -> str:
        """Print a numbered list of search results."""
        lines = [f"Found {len(results)} results:\n"]
        for i, s in enumerate(results, 1):
            lines.append(f"  {i:>3}. {s.from_slug} -> {s.to_slug}  "
                         f"[{s.variant}]  "
                         f"err_src={s.source_error_node_pct}%  "
                         f"vsMax={s.vs_max}  "
                         f"gap_cl={s.gap_closure}  "
                         f"rkGrp={s.rank_in_group}  "
                         f"hit={s.steered_has_to_answer}  "
                         f"tier={s.tier}")
        text = "\n".join(lines)
        print(text)
        return text

    # -- Internal helpers ---------------------------------------------------

    def _resolve_swap_path(
        self, dataset: str, run: str, from_slug: str, to_slug: str,
        variant: Optional[str],
    ) -> Optional[Path]:
        base = (self.output_root / dataset / "_swaps" / "runs"
                / run / "by_source" / from_slug)
        if variant:
            p = base / f"to_{to_slug}__{variant}.json"
            if p.exists():
                return p
        canonical = base / f"to_{to_slug}.json"
        if canonical.exists():
            return canonical
        # Try any matching file
        if base.is_dir():
            for f in base.iterdir():
                if f.name.startswith(f"to_{to_slug}") and f.suffix == ".json":
                    return f
        return None

    @staticmethod
    def _detect_variant(fpath: Path) -> str:
        stem = fpath.stem.replace("to_", "", 1)
        parts = stem.split("__", 1)
        return parts[1] if len(parts) == 2 else ""

    def _build_summary(
        self, fpath: Path, dataset: str, run: str, ds_dir: Path,
    ) -> SwapSummary:
        with open(fpath, "r", encoding="utf-8") as f:
            data = json.load(f)

        src = data.get("source", {})
        tgt = data.get("target", {})
        ev = data.get("evaluation", {})
        em = ev.get("exact_match", {})
        ft = ev.get("first_token", {})
        traj_summ = (ev.get("logit_trajectory", {}).get("summary", {}))
        contrast = (ev.get("logit_trajectory", {})
                    .get("contrast_groups", {})
                    .get("same_dataset", {}))
        agg = contrast.get("aggregate", {}) if isinstance(contrast, dict) else {}
        bl = ev.get("baseline_logits", {})
        p0 = ev.get("position_0_comparison", {})
        ctrl = data.get("metadata", {}).get("control", {})
        intv = data.get("interventions", {})
        cls = data.get("classification", {})
        raw = ev.get("raw", {})

        src_slug = src.get("slug", "")
        tgt_slug = tgt.get("slug", "")

        return SwapSummary(
            dataset=dataset,
            run_id=run,
            variant=self._detect_variant(fpath),
            from_slug=src_slug,
            to_slug=tgt_slug,
            swap_id=data.get("swap_id", ""),
            file_path=str(fpath),
            source_error_node_pct=self._error_cache.get(
                ds_dir, src_slug.lower().replace(" ", "_")),
            target_error_node_pct=self._error_cache.get(
                ds_dir, tgt_slug.lower().replace(" ", "_")),
            steered_has_to_answer=em.get("steered_has_to_answer"),
            from_suppressed=em.get("from_suppressed"),
            first_token_matches_target=em.get("first_token_matches_target"),
            default_first_token=ft.get("default", ""),
            default_first_prob=ft.get("default_prob"),
            steered_first_token=ft.get("steered", ""),
            steered_first_prob=ft.get("steered_prob"),
            flip_position=traj_summ.get("flip_position"),
            initial_gap=traj_summ.get("initial_gap"),
            best_gap=traj_summ.get("best_gap"),
            gap_closure=traj_summ.get("gap_closure"),
            control_stability_mean=traj_summ.get("control_stability_mean"),
            vs_max=agg.get("best_target_minus_max"),
            vs_topk=agg.get("best_target_minus_topk"),
            rank_in_group=agg.get("best_rank_within"),
            target_baseline_rank=bl.get("target", {}).get("rank"),
            source_baseline_rank=bl.get("source", {}).get("rank"),
            flip_at_0=p0.get("flip_at_0"),
            gap_closure_0=p0.get("gap_closure_0"),
            target_rank_improvement=p0.get("target_rank_improvement"),
            ablate_count=intv.get("ablate_count"),
            amplify_count=intv.get("amplify_count"),
            total_count=intv.get("total_count"),
            control_mode=ctrl.get("control_mode", ""),
            fields_used=ctrl.get("concept_subsets_used", []),
            tier=cls.get("tier"),
            default_output_preview=_trunc(raw.get("default_output", ""), 120),
            steered_output_preview=_trunc(raw.get("steered_output", ""), 120),
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _trunc(s: str, n: int) -> str:
    s = s.replace("\n", " ").replace("\r", "")
    return s[:n] + "..." if len(s) > n else s


def _compact_dict(d: Any) -> str:
    if not isinstance(d, dict):
        return str(d)
    parts = [f"{k}={v}" for k, v in d.items()]
    return "{" + ", ".join(parts) + "}"


def _make_sort_key(field_name: str) -> Callable[[SwapSummary], Any]:
    """Build a sort key that handles None values."""
    def key(s: SwapSummary):
        val = getattr(s, field_name, None)
        if val is None:
            return (1, 0)  # Nones sort last
        return (0, val)
    return key
