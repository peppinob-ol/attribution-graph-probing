"""
Pipeline tracer for debugging swap experiment results.

Traces *why* a swap behaves as it does by inspecting the upstream pipeline:
  Stage 0: Graph (nodes, error nodes, cumulative influence distribution)
  Stage 1: Probes and activations
  Stage 2: Node grouping (supernodes, classifications, review flags)
  Swap:    Concept-to-supernode matching, intervention feature list

Usage::

    from scripts.utils.pipeline_tracer import PipelineTracer

    t = PipelineTracer()

    # Full entity profile (graph quality, supernodes, error budget)
    profile = t.entity_profile("usa_states_batch", "mississippi_gulfport")
    t.print_entity_profile(profile)

    # Trace concept matching for a specific swap
    trace = t.trace_swap_matching(
        "usa_states_batch", "mississippi_gulfport", "arizona_tucson",
        concept_fields=["state"],
    )
    t.print_matching_trace(trace)

    # Compare grouping quality across entities
    table = t.grouping_quality_table("usa_states_batch")
    t.print_quality_table(table)
"""

from __future__ import annotations

import csv
import json
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from scripts.utils.swap_query import SwapQuery, _find_entity_dir


OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "output"


# ---------------------------------------------------------------------------
# Data containers
# ---------------------------------------------------------------------------

@dataclass
class GraphProfile:
    """Stage 0 summary for one entity's attribution graph."""
    slug: str
    total_nodes: int = 0
    clt_nodes: int = 0
    error_nodes: int = 0
    embedding_nodes: int = 0
    logit_nodes: int = 0
    error_node_pct: float = 0.0
    total_influence: float = 0.0
    error_influence: float = 0.0
    error_influence_pct: float = 0.0
    selected_features: int = 0
    cumulative_influence_coverage: float = 0.0
    top_feature_influence: List[Tuple[str, float]] = field(default_factory=list)


@dataclass
class GroupingProfile:
    """Stage 2 summary for one entity's node grouping."""
    slug: str
    total_rows: int = 0
    n_supernodes: int = 0
    classification_counts: Dict[str, int] = field(default_factory=dict)
    subtype_counts: Dict[str, int] = field(default_factory=dict)
    review_flagged: int = 0
    review_reasons: Dict[str, int] = field(default_factory=dict)
    supernode_breakdown: List[Dict[str, Any]] = field(default_factory=list)
    concept_supernodes: Dict[str, List[str]] = field(default_factory=dict)


@dataclass
class MatchingTrace:
    """Trace of concept-to-supernode matching for a swap."""
    from_slug: str
    to_slug: str
    concept_fields: List[str]
    source_matches: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    target_matches: Dict[str, Dict[str, Any]] = field(default_factory=dict)
    source_total_features: int = 0
    target_total_features: int = 0
    warnings: List[str] = field(default_factory=list)


@dataclass
class EntityQualityRow:
    """Per-entity quality summary for table display."""
    slug: str
    clt_nodes: int = 0
    error_nodes: int = 0
    error_influence_pct: float = 0.0
    selected_features: int = 0
    n_supernodes: int = 0
    review_flagged: int = 0
    concept_coverage: Dict[str, int] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Main tracer
# ---------------------------------------------------------------------------

class PipelineTracer:
    """Trace upstream pipeline data for debugging swap experiments."""

    def __init__(self, output_root=None):
        self.output_root = Path(output_root) if output_root else OUTPUT_ROOT

    # -- Entity profile (Stage 0 + 2 combined) -----------------------------

    def entity_profile(
        self, dataset: str, slug: str,
    ) -> Tuple[Optional[GraphProfile], Optional[GroupingProfile]]:
        """Load graph and grouping profiles for one entity."""
        ds_dir = self.output_root / dataset
        entity_dir = _find_entity_dir(ds_dir, slug)
        if entity_dir is None:
            return None, None
        gp = self._load_graph_profile(entity_dir, slug)
        grp = self._load_grouping_profile(entity_dir, slug)
        return gp, grp

    # -- Concept matching trace ---------------------------------------------

    def trace_swap_matching(
        self,
        dataset: str,
        from_slug: str,
        to_slug: str,
        concept_fields: Optional[List[str]] = None,
    ) -> MatchingTrace:
        """Trace how concept fields resolve to supernodes for a swap pair.

        If concept_fields is None, reads from the dataset config.
        """
        ds_dir = self.output_root / dataset
        if concept_fields is None:
            concept_fields = self._load_concept_fields(ds_dir)

        trace = MatchingTrace(
            from_slug=from_slug, to_slug=to_slug,
            concept_fields=concept_fields,
        )

        for role, slug, store in [
            ("source", from_slug, trace.source_matches),
            ("target", to_slug, trace.target_matches),
        ]:
            entity_dir = _find_entity_dir(ds_dir, slug)
            if entity_dir is None:
                trace.warnings.append(f"{role} entity dir not found: {slug}")
                continue
            grouping_rows = self._load_grouping_rows(entity_dir)
            if not grouping_rows:
                trace.warnings.append(f"{role} grouping empty: {slug}")
                continue

            entity_data = self._load_entity_data(ds_dir, slug)
            total_feats = 0
            for cf in concept_fields:
                concept_value = entity_data.get(cf, "")
                concept_lc = _concept_text(concept_value)
                if not concept_lc:
                    store[cf] = {
                        "field": cf, "value": concept_value,
                        "concept_normalized": "", "matched_supernodes": [],
                        "matched_features": 0, "note": "empty concept value",
                    }
                    continue

                matched_sns = []
                matched_feats = 0
                for sn_name, rows_in_sn in _group_by_supernode(grouping_rows).items():
                    sn_lower = sn_name.lower()
                    if _concept_matches_supernode(concept_lc, sn_lower):
                        n_feats = len(rows_in_sn)
                        matched_feats += n_feats
                        sample = rows_in_sn[0]
                        matched_sns.append({
                            "supernode": sn_name,
                            "n_features": n_feats,
                            "label": sample.get("pred_label", ""),
                            "subtype": sample.get("subtype", ""),
                            "layers": sorted(set(
                                r.get("layer", "?") for r in rows_in_sn)),
                        })

                total_feats += matched_feats
                store[cf] = {
                    "field": cf, "value": concept_value,
                    "concept_normalized": concept_lc,
                    "matched_supernodes": matched_sns,
                    "matched_features": matched_feats,
                }
                if not matched_sns:
                    trace.warnings.append(
                        f"{role} concept '{concept_lc}' ({cf}) matched "
                        f"no supernodes in {slug}")

            if role == "source":
                trace.source_total_features = total_feats
            else:
                trace.target_total_features = total_feats

        return trace

    # -- Quality table across all entities ----------------------------------

    def grouping_quality_table(
        self, dataset: str,
        concept_fields: Optional[List[str]] = None,
    ) -> List[EntityQualityRow]:
        """Build a per-entity quality table for a dataset."""
        ds_dir = self.output_root / dataset
        if concept_fields is None:
            concept_fields = self._load_concept_fields(ds_dir)

        rows: List[EntityQualityRow] = []
        for edir in sorted(ds_dir.iterdir()):
            if not edir.is_dir() or edir.name.startswith("_"):
                continue
            slug = edir.name.lower().replace(" ", "_")
            gp = self._load_graph_profile(edir, slug)
            grp = self._load_grouping_profile(edir, slug)

            concept_cov: Dict[str, int] = {}
            if grp:
                entity_data = self._load_entity_data(ds_dir, slug)
                grouping_rows = self._load_grouping_rows(edir)
                sn_groups = _group_by_supernode(grouping_rows) if grouping_rows else {}
                for cf in concept_fields:
                    cv = _concept_text(entity_data.get(cf, ""))
                    if not cv:
                        concept_cov[cf] = 0
                        continue
                    count = sum(
                        len(rs) for sn, rs in sn_groups.items()
                        if _concept_matches_supernode(cv, sn.lower())
                    )
                    concept_cov[cf] = count

            rows.append(EntityQualityRow(
                slug=slug,
                clt_nodes=gp.clt_nodes if gp else 0,
                error_nodes=gp.error_nodes if gp else 0,
                error_influence_pct=gp.error_influence_pct if gp else 0,
                selected_features=gp.selected_features if gp else 0,
                n_supernodes=grp.n_supernodes if grp else 0,
                review_flagged=grp.review_flagged if grp else 0,
                concept_coverage=concept_cov,
            ))
        return rows

    # -- Printers -----------------------------------------------------------

    @staticmethod
    def print_entity_profile(
        gp: Optional[GraphProfile], grp: Optional[GroupingProfile],
    ) -> str:
        lines: List[str] = []
        if gp:
            lines.append(f"=== Graph Profile: {gp.slug} ===")
            lines.append(f"  Nodes: {gp.total_nodes} total  "
                         f"({gp.clt_nodes} CLT, {gp.error_nodes} error, "
                         f"{gp.embedding_nodes} embed, {gp.logit_nodes} logit)")
            lines.append(f"  Error node %: {gp.error_nodes}/{gp.total_nodes} = "
                         f"{gp.error_nodes/gp.total_nodes*100:.1f}% of nodes")
            lines.append(f"  Error influence %: {gp.error_influence_pct:.2f}% "
                         f"of total node_influence")
            lines.append(f"  Selected features: {gp.selected_features}")
            if gp.top_feature_influence:
                lines.append("  Top features by node_influence:")
                for desc, inf in gp.top_feature_influence[:10]:
                    lines.append(f"    {desc:>50s}  inf={inf:.4f}")
        if grp:
            lines.append("")
            lines.append(f"=== Grouping Profile: {grp.slug} ===")
            lines.append(f"  Total rows: {grp.total_rows}  "
                         f"Supernodes: {grp.n_supernodes}")
            lines.append(f"  Classifications: {dict(grp.classification_counts)}")
            lines.append(f"  Subtypes: {dict(grp.subtype_counts)}")
            lines.append(f"  Review-flagged: {grp.review_flagged}")
            if grp.review_reasons:
                for reason, cnt in sorted(grp.review_reasons.items(),
                                          key=lambda x: -x[1])[:5]:
                    lines.append(f"    {cnt:>3d}x  {reason[:80]}")
            lines.append("")
            lines.append("  Supernodes:")
            for sn in grp.supernode_breakdown:
                lines.append(
                    f"    {sn['name']:>40s}  N={sn['count']:>3d}  "
                    f"label={sn['label']:12s}  subtype={sn['subtype']:25s}  "
                    f"layers={sn['layers']}")
        text = "\n".join(lines)
        print(text)
        return text

    @staticmethod
    def print_matching_trace(trace: MatchingTrace) -> str:
        lines = [
            f"=== Matching Trace: {trace.from_slug} -> {trace.to_slug} ===",
            f"  concept_fields: {trace.concept_fields}",
        ]
        for role, store, total in [
            ("SOURCE (ablate)", trace.source_matches, trace.source_total_features),
            ("TARGET (amplify)", trace.target_matches, trace.target_total_features),
        ]:
            lines.append(f"\n  --- {role} ({total} features total) ---")
            for cf, info in store.items():
                lines.append(
                    f"    {cf}: \"{info['value']}\" -> "
                    f"norm=\"{info['concept_normalized']}\"  "
                    f"matched={info['matched_features']} features")
                for sn in info.get("matched_supernodes", []):
                    lines.append(
                        f"      -> {sn['supernode']:30s}  N={sn['n_features']:>3d}  "
                        f"{sn['label']:12s}  layers={sn['layers']}")
                if info.get("note"):
                    lines.append(f"      NOTE: {info['note']}")
        if trace.warnings:
            lines.append("\n  WARNINGS:")
            for w in trace.warnings:
                lines.append(f"    ! {w}")
        text = "\n".join(lines)
        print(text)
        return text

    @staticmethod
    def print_quality_table(
        rows: List[EntityQualityRow],
        sort_by: str = "error_influence_pct",
        concept_fields: Optional[List[str]] = None,
    ) -> str:
        rows = sorted(rows, key=lambda r: getattr(r, sort_by, 0), reverse=True)
        cf_headers = concept_fields or []
        if not cf_headers and rows and rows[0].concept_coverage:
            cf_headers = sorted(rows[0].concept_coverage.keys())

        hdr = (f"{'slug':>30s}  {'CLT':>4s}  {'err':>4s}  {'err%':>6s}  "
               f"{'feat':>5s}  {'SN':>4s}  {'rev':>4s}")
        for cf in cf_headers:
            hdr += f"  {cf:>8s}"
        lines = [hdr, "-" * len(hdr)]
        for r in rows:
            line = (f"{r.slug:>30s}  {r.clt_nodes:>4d}  {r.error_nodes:>4d}  "
                    f"{r.error_influence_pct:>5.1f}%  "
                    f"{r.selected_features:>5d}  {r.n_supernodes:>4d}  "
                    f"{r.review_flagged:>4d}")
            for cf in cf_headers:
                line += f"  {r.concept_coverage.get(cf, 0):>8d}"
            lines.append(line)
        text = "\n".join(lines)
        print(text)
        return text

    # -- Internal loaders ---------------------------------------------------

    def _load_graph_profile(self, entity_dir: Path, slug: str) -> Optional[GraphProfile]:
        gp = GraphProfile(slug=slug)

        graph_path = entity_dir / "00 Graph Generation" / "graph.json"
        if graph_path.exists():
            with open(graph_path, "r", encoding="utf-8") as f:
                gdata = json.load(f)
            nodes = gdata.get("nodes", [])
            gp.total_nodes = len(nodes)
            types = Counter(n.get("feature_type", "unknown") for n in nodes)
            gp.clt_nodes = types.get("cross layer transcoder", 0)
            gp.error_nodes = types.get("mlp reconstruction error", 0)
            gp.embedding_nodes = types.get("embedding", 0)
            gp.logit_nodes = types.get("logit", 0)

        csv_path = (entity_dir / "00 Graph Generation"
                    / "graph_feature_static_metrics.csv")
        if csv_path.exists():
            with open(csv_path, "r", encoding="utf-8") as f:
                metrics = list(csv.DictReader(f))
            gp.selected_features = len(metrics)
            total_inf = 0.0
            error_inf = 0.0
            feature_infs = []
            for row in metrics:
                ni_str = (row.get("node_influence") or "").strip()
                if not ni_str:
                    continue
                ni = float(ni_str)
                total_inf += ni
                feat_id = row.get("feature", "")
                layer = row.get("layer", "?")
                token = row.get("token", "?")
                if feat_id == "-1":
                    error_inf += ni
                    feature_infs.append((f"ERROR L{layer} @{token}", ni))
                else:
                    feature_infs.append((f"L{layer}/F{feat_id} @{token}", ni))
            gp.total_influence = total_inf
            gp.error_influence = error_inf
            gp.error_influence_pct = (error_inf / total_inf * 100
                                      if total_inf > 0 else 0)
            gp.cumulative_influence_coverage = total_inf
            feature_infs.sort(key=lambda x: -x[1])
            gp.top_feature_influence = feature_infs[:15]

        sf_path = (entity_dir / "00 Graph Generation"
                   / "selected_features_with_nodes.json")
        if sf_path.exists() and gp.selected_features == 0:
            with open(sf_path, "r", encoding="utf-8") as f:
                sf = json.load(f)
            gp.selected_features = len(sf.get("features", []))

        return gp

    def _load_grouping_profile(
        self, entity_dir: Path, slug: str,
    ) -> Optional[GroupingProfile]:
        csv_path = entity_dir / "02 Node Grouping" / "node_grouping.csv"
        if not csv_path.exists():
            return None
        rows = self._load_grouping_rows(entity_dir)
        if not rows:
            return None

        grp = GroupingProfile(slug=slug, total_rows=len(rows))
        grp.classification_counts = dict(Counter(
            r.get("pred_label", "?") for r in rows))
        grp.subtype_counts = dict(Counter(
            r.get("subtype", "?") for r in rows))
        sn_groups = _group_by_supernode(rows)
        grp.n_supernodes = len(sn_groups)
        reviews = [r for r in rows if r.get("review", "").lower() == "true"]
        grp.review_flagged = len(reviews)
        grp.review_reasons = dict(Counter(
            r.get("why_review", "") for r in reviews))

        breakdown = []
        for sn_name, sn_rows in sorted(sn_groups.items(),
                                        key=lambda x: -len(x[1])):
            sample = sn_rows[0]
            breakdown.append({
                "name": sn_name,
                "count": len(sn_rows),
                "label": sample.get("pred_label", ""),
                "subtype": sample.get("subtype", ""),
                "layers": sorted(set(r.get("layer", "?") for r in sn_rows)),
            })
        grp.supernode_breakdown = breakdown
        return grp

    @staticmethod
    def _load_grouping_rows(entity_dir: Path) -> Optional[List[Dict[str, str]]]:
        csv_path = entity_dir / "02 Node Grouping" / "node_grouping.csv"
        if not csv_path.exists():
            return None
        with open(csv_path, "r", encoding="utf-8") as f:
            return list(csv.DictReader(f))

    def _load_entity_data(self, ds_dir: Path, slug: str) -> Dict[str, str]:
        """Load entity field values from any swap JSON (cheap lookup)."""
        runs_dir = ds_dir / "_swaps" / "runs"
        if not runs_dir.is_dir():
            return {}
        for run_dir in runs_dir.iterdir():
            by_src = run_dir / "by_source"
            if not by_src.is_dir():
                continue
            for src_dir in by_src.iterdir():
                if src_dir.name.lower().replace(" ", "_") == slug.lower():
                    for f in src_dir.iterdir():
                        if f.suffix == ".json":
                            with open(f, "r", encoding="utf-8") as fh:
                                data = json.load(fh)
                            return data.get("source", {})
                for f in src_dir.iterdir():
                    if f.suffix == ".json":
                        with open(f, "r", encoding="utf-8") as fh:
                            data = json.load(fh)
                        tgt = data.get("target", {})
                        if tgt.get("slug", "").lower().replace(" ", "_") == slug.lower():
                            return tgt
                        break
        return {}

    def _load_concept_fields(self, ds_dir: Path) -> List[str]:
        """Try to load concept_fields from any run's config_resolved.json."""
        runs_dir = ds_dir / "_swaps" / "runs"
        if not runs_dir.is_dir():
            return ["state", "capital", "city"]
        for run_dir in sorted(runs_dir.iterdir()):
            cfg_path = run_dir / "config_resolved.json"
            if cfg_path.exists():
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = json.load(f)
                fields = cfg.get("swap", {}).get("concept_fields")
                if fields:
                    return fields
        return ["state", "capital", "city"]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _concept_text(text: str) -> str:
    """Normalize concept value the same way the pipeline does."""
    t = (text or "").strip().lower()
    if t.endswith(" city"):
        t = t[: -len(" city")].strip()
    return t


def _group_by_supernode(rows: List[Dict[str, str]]) -> Dict[str, List[Dict]]:
    groups: Dict[str, List[Dict]] = defaultdict(list)
    for r in rows:
        groups[r.get("supernode_name", "")].append(r)
    return dict(groups)


_FUNCTION_WORDS = frozenset([
    "the", "of", "in", "is", "a", "an", "to", "for", "by", "on", "at",
    "and", "or", "de", "di", "le", "la", "el", "von", "van",
])


def _concept_matches_supernode(concept_lc: str, supernode_lc: str) -> bool:
    """Replicate the pipeline's concept matching logic (simplified)."""
    if not concept_lc or not supernode_lc:
        return False
    # Full concept match
    if concept_lc in supernode_lc:
        return True
    # Per-word fallback
    for word in concept_lc.split():
        word = word.strip().rstrip(".")
        if len(word) >= 3 and word not in _FUNCTION_WORDS:
            if word in supernode_lc or supernode_lc in word:
                return True
    return False
