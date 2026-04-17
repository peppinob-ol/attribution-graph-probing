"""
Scalable cross-prompt robustness analysis.

Compares feature sets and supernode assignments across any two entities
in the same domain. Designed to scale from N=2 (original Dallas/Oakland)
to all 1,607 intra-domain entity pairs.

Metrics computed per pair:
  - Feature overlap (Jaccard and directional)
  - Activation stability (mean relative diff of activation_max)
  - Peak token agreement (same token, same token type)
  - Supernode grouping consistency (same, entity-appropriate, inconsistent)
  - Per-layer overlap (early/mid/late buckets + per-individual-layer)
  - Influence-weighted overlap

Usage::

    from scripts.experiments.cross_prompt_robustness_scalable import (
        CrossPromptComparator, compare_pair, compare_all_pairs,
    )

    comp = CrossPromptComparator("output")
    result = comp.compare("usa_states_batch", "texas_Dallas", "california_Oakland")
    print(result)

    # All pairs in a domain
    results = comp.compare_all("usa_states_batch")
"""

from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from itertools import combinations
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple

import numpy as np

OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "output"

LAYER_BUCKETS = {"early": (0, 5), "mid": (6, 14), "late": (15, 99)}


@dataclass
class PairResult:
    """All cross-prompt robustness metrics for one entity pair."""

    dataset: str
    slug_a: str
    slug_b: str

    n_features_a: int = 0
    n_features_b: int = 0
    n_shared: int = 0
    n_union: int = 0

    jaccard_overlap: float = 0.0
    directional_overlap_a: float = 0.0
    directional_overlap_b: float = 0.0

    activation_stability: float = 0.0
    activation_rel_diffs: List[float] = field(default_factory=list)

    peak_token_agreement: float = 0.0
    peak_type_agreement: float = 0.0

    same_supernode_rate: float = 0.0
    entity_regrouped_rate: float = 0.0
    inconsistent_rate: float = 0.0

    per_layer_overlap: Dict[int, float] = field(default_factory=dict)
    bucket_overlap: Dict[str, float] = field(default_factory=dict)

    influence_weighted_jaccard: float = 0.0

    n_supernodes_a: int = 0
    n_supernodes_b: int = 0
    n_shared_supernodes: int = 0

    def as_flat_dict(self) -> Dict[str, Any]:
        """Flatten for CSV output (no nested lists/dicts)."""
        d = {
            "dataset": self.dataset,
            "slug_a": self.slug_a,
            "slug_b": self.slug_b,
            "n_features_a": self.n_features_a,
            "n_features_b": self.n_features_b,
            "n_shared": self.n_shared,
            "n_union": self.n_union,
            "jaccard_overlap": self.jaccard_overlap,
            "directional_overlap_a": self.directional_overlap_a,
            "directional_overlap_b": self.directional_overlap_b,
            "activation_stability": self.activation_stability,
            "peak_token_agreement": self.peak_token_agreement,
            "peak_type_agreement": self.peak_type_agreement,
            "same_supernode_rate": self.same_supernode_rate,
            "entity_regrouped_rate": self.entity_regrouped_rate,
            "inconsistent_rate": self.inconsistent_rate,
            "influence_weighted_jaccard": self.influence_weighted_jaccard,
            "n_supernodes_a": self.n_supernodes_a,
            "n_supernodes_b": self.n_supernodes_b,
            "n_shared_supernodes": self.n_shared_supernodes,
        }
        for bucket in LAYER_BUCKETS:
            d[f"overlap_{bucket}"] = self.bucket_overlap.get(bucket, 0.0)
        return d


def _load_grouping(entity_dir: Path) -> Optional[List[Dict[str, str]]]:
    """Load node_grouping.csv rows."""
    csv_path = entity_dir / "02 Node Grouping" / "node_grouping.csv"
    if not csv_path.exists():
        return None
    with open(csv_path, "r", encoding="utf-8") as f:
        return list(csv.DictReader(f))



def _deduplicate_features(rows: List[Dict[str, str]]) -> Dict[str, Dict[str, Any]]:
    """Collapse multi-probe rows to one record per unique feature_key.

    For numeric fields we take the max across probes (activation_max) or
    the first value (layer, supernode_name, peak_token, peak_token_type).
    """
    features: Dict[str, Dict[str, Any]] = {}
    for r in rows:
        fk = r["feature_key"]
        if fk not in features:
            features[fk] = {
                "feature_key": fk,
                "layer": int(r.get("layer", 0)),
                "supernode_name": r.get("supernode_name", ""),
                "peak_token": r.get("peak_token", ""),
                "peak_token_type": r.get("peak_token_type", ""),
                "activation_max": float(r.get("activation_max", 0)),
                "node_influence": 0.0,
            }
        else:
            act = float(r.get("activation_max", 0))
            if act > features[fk]["activation_max"]:
                features[fk]["activation_max"] = act
    return features


def _add_influence(features: Dict[str, Dict[str, Any]],
                   entity_dir: Path) -> None:
    """Attach node_influence by mapping through graph.json + selected_features."""
    sf_path = entity_dir / "00 Graph Generation" / "selected_features_with_nodes.json"
    graph_path = entity_dir / "00 Graph Generation" / "graph.json"
    if not sf_path.exists() or not graph_path.exists():
        return

    with open(sf_path, "r", encoding="utf-8") as f:
        sf = json.load(f)
    with open(graph_path, "r", encoding="utf-8") as f:
        gdata = json.load(f)

    node_inf: Dict[str, float] = {}
    for n in gdata.get("nodes", []):
        if n.get("influence") is not None:
            node_inf[n["node_id"]] = float(n["influence"])

    node_ids = sf.get("node_ids", [])
    sf_features = sf.get("features", [])
    for i, feat in enumerate(sf_features):
        fk = f"{feat['layer']}_{feat['index']}"
        if fk in features and i < len(node_ids):
            features[fk]["node_influence"] = node_inf.get(node_ids[i], 0.0)


def _slug_tokens(slug: str) -> Set[str]:
    """Extract meaningful tokens from an entity slug for keyword detection."""
    parts = re.split(r"[_\s]+", slug.lower())
    return {p for p in parts if len(p) >= 3}


def _load_entity_fields(ds_dir: Path, slug: str) -> Dict[str, str]:
    """Load entity concept field values from swap JSONs (cheap)."""
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
    return {}


def _entity_keywords(slug: str, ds_dir: Path) -> Set[str]:
    """Build entity-specific keyword set from slug + concept field values."""
    keywords = _slug_tokens(slug)
    fields = _load_entity_fields(ds_dir, slug)
    for k, v in fields.items():
        if k in ("slug", "prompt", "answer"):
            continue
        if isinstance(v, str) and len(v) >= 3:
            for word in re.split(r"[\s_]+", v.lower()):
                if len(word) >= 3:
                    keywords.add(word)
    return keywords


_STRUCTURAL_SUPERNODES = frozenset([
    "punctuation", "is", "of", "the", "containing", "related",
    "capital", "seat", "entity", "literary", "famous",
])


def _classify_supernode(sn_name: str,
                        keywords_a: Set[str],
                        keywords_b: Set[str]) -> str:
    """Classify a supernode as 'structural', 'entity_a', 'entity_b', or 'mixed'."""
    sn_lower = sn_name.lower()
    sn_tokens = set(re.split(r"[\s_()]+", sn_lower)) - {"", "say"}

    if sn_lower in _STRUCTURAL_SUPERNODES:
        return "structural"

    hits_a = bool(sn_tokens & keywords_a)
    hits_b = bool(sn_tokens & keywords_b)

    if hits_a and hits_b:
        return "mixed"
    if hits_a:
        return "entity_a"
    if hits_b:
        return "entity_b"

    if sn_lower.startswith("say(") or sn_lower.startswith("say ("):
        return "entity_specific_output"

    return "structural"


def compare_pair(
    ds_dir: Path,
    slug_a: str,
    slug_b: str,
    dataset: str,
    keywords_a: Optional[Set[str]] = None,
    keywords_b: Optional[Set[str]] = None,
) -> Optional[PairResult]:
    """Compare two entities and return all robustness metrics."""

    dir_a = _find_entity_dir(ds_dir, slug_a)
    dir_b = _find_entity_dir(ds_dir, slug_b)
    if dir_a is None or dir_b is None:
        return None

    rows_a = _load_grouping(dir_a)
    rows_b = _load_grouping(dir_b)
    if rows_a is None or rows_b is None:
        return None

    feats_a = _deduplicate_features(rows_a)
    feats_b = _deduplicate_features(rows_b)

    _add_influence(feats_a, dir_a)
    _add_influence(feats_b, dir_b)

    keys_a = set(feats_a.keys())
    keys_b = set(feats_b.keys())
    shared = keys_a & keys_b
    union = keys_a | keys_b

    res = PairResult(
        dataset=dataset, slug_a=slug_a, slug_b=slug_b,
        n_features_a=len(keys_a), n_features_b=len(keys_b),
        n_shared=len(shared), n_union=len(union),
    )

    if not union:
        return res

    res.jaccard_overlap = len(shared) / len(union)
    res.directional_overlap_a = len(shared) / len(keys_a) if keys_a else 0.0
    res.directional_overlap_b = len(shared) / len(keys_b) if keys_b else 0.0

    # -- Activation stability --
    rel_diffs = []
    for fk in shared:
        act_a = feats_a[fk]["activation_max"]
        act_b = feats_b[fk]["activation_max"]
        denom = max(act_a, act_b, 1e-6)
        rel_diffs.append(abs(act_a - act_b) / denom)
    res.activation_rel_diffs = rel_diffs
    if rel_diffs:
        res.activation_stability = 1.0 - float(np.mean(rel_diffs))

    # -- Peak token agreement --
    same_peak = 0
    same_type = 0
    for fk in shared:
        if feats_a[fk]["peak_token"] == feats_b[fk]["peak_token"]:
            same_peak += 1
        if feats_a[fk]["peak_token_type"] == feats_b[fk]["peak_token_type"]:
            same_type += 1
    n_sh = len(shared) or 1
    res.peak_token_agreement = same_peak / n_sh
    res.peak_type_agreement = same_type / n_sh

    # -- Supernode consistency --
    if keywords_a is None:
        keywords_a = _entity_keywords(slug_a, ds_dir)
    if keywords_b is None:
        keywords_b = _entity_keywords(slug_b, ds_dir)

    same_sn = 0
    regrouped = 0
    inconsistent = 0
    for fk in shared:
        sn_a = feats_a[fk]["supernode_name"]
        sn_b = feats_b[fk]["supernode_name"]
        if sn_a == sn_b:
            same_sn += 1
        elif _is_entity_appropriate_regroup(sn_a, sn_b, keywords_a, keywords_b):
            regrouped += 1
        else:
            inconsistent += 1
    res.same_supernode_rate = same_sn / n_sh
    res.entity_regrouped_rate = regrouped / n_sh
    res.inconsistent_rate = inconsistent / n_sh

    # -- Per-layer overlap --
    layers_a: Dict[int, Set[str]] = defaultdict(set)
    layers_b: Dict[int, Set[str]] = defaultdict(set)
    for fk, f in feats_a.items():
        layers_a[f["layer"]].add(fk)
    for fk, f in feats_b.items():
        layers_b[f["layer"]].add(fk)
    all_layers = sorted(set(layers_a.keys()) | set(layers_b.keys()))
    for layer in all_layers:
        la = layers_a.get(layer, set())
        lb = layers_b.get(layer, set())
        u = la | lb
        res.per_layer_overlap[layer] = len(la & lb) / len(u) if u else 0.0

    for bucket, (lo, hi) in LAYER_BUCKETS.items():
        bucket_a: Set[str] = set()
        bucket_b: Set[str] = set()
        for layer in all_layers:
            if lo <= layer <= hi:
                bucket_a |= layers_a.get(layer, set())
                bucket_b |= layers_b.get(layer, set())
        u = bucket_a | bucket_b
        res.bucket_overlap[bucket] = len(bucket_a & bucket_b) / len(u) if u else 0.0

    # -- Influence-weighted Jaccard --
    inf_shared = 0.0
    inf_union = 0.0
    all_keys = keys_a | keys_b
    for fk in all_keys:
        ia = feats_a[fk]["node_influence"] if fk in feats_a else 0.0
        ib = feats_b[fk]["node_influence"] if fk in feats_b else 0.0
        inf_union += max(ia, ib)
        if fk in shared:
            inf_shared += min(ia, ib)
    res.influence_weighted_jaccard = inf_shared / inf_union if inf_union > 0 else 0.0

    # -- Supernode counts --
    sns_a = {feats_a[fk]["supernode_name"] for fk in keys_a}
    sns_b = {feats_b[fk]["supernode_name"] for fk in keys_b}
    res.n_supernodes_a = len(sns_a)
    res.n_supernodes_b = len(sns_b)
    res.n_shared_supernodes = len(sns_a & sns_b)

    return res


def _is_entity_appropriate_regroup(
    sn_a: str, sn_b: str,
    keywords_a: Set[str], keywords_b: Set[str],
) -> bool:
    """Check if sn_a -> sn_b is an entity-appropriate regrouping.

    E.g., Say(Austin) -> Say(Sacramento) when Austin is in keywords_a
    and Sacramento is in keywords_b.
    """
    toks_a = set(re.split(r"[\s_()]+", sn_a.lower())) - {"", "say"}
    toks_b = set(re.split(r"[\s_()]+", sn_b.lower())) - {"", "say"}

    a_is_entity_a = bool(toks_a & keywords_a) and not bool(toks_a & keywords_b)
    b_is_entity_b = bool(toks_b & keywords_b) and not bool(toks_b & keywords_a)

    if a_is_entity_a and b_is_entity_b:
        return True

    a_is_entity_b = bool(toks_a & keywords_b) and not bool(toks_a & keywords_a)
    b_is_entity_a = bool(toks_b & keywords_a) and not bool(toks_b & keywords_b)
    if a_is_entity_b and b_is_entity_a:
        return True

    return False


def _find_entity_dir(ds_dir: Path, slug: str) -> Optional[Path]:
    """Find entity directory by slug, preferring dirs with pipeline data."""
    slug_lc = slug.lower().replace(" ", "_")
    candidates = []
    for d in ds_dir.iterdir():
        if not d.is_dir() or d.name.startswith("_"):
            continue
        if d.name.lower().replace(" ", "_") == slug_lc:
            has_data = (d / "02 Node Grouping" / "node_grouping.csv").exists()
            candidates.append((d, has_data))
    candidates.sort(key=lambda x: (not x[1], x[0].name))
    return candidates[0][0] if candidates else None


class CrossPromptComparator:
    """Main entry point for scalable cross-prompt comparison."""

    def __init__(self, output_root: Optional[str] = None):
        self.output_root = Path(output_root) if output_root else OUTPUT_ROOT

    def list_entities(self, dataset: str) -> List[str]:
        """List entities with complete pipeline data (grouping + graph)."""
        ds_dir = self.output_root / dataset
        entities = []
        for d in sorted(ds_dir.iterdir()):
            if not d.is_dir() or d.name.startswith("_"):
                continue
            grouping = d / "02 Node Grouping" / "node_grouping.csv"
            graph = d / "00 Graph Generation" / "graph_feature_static_metrics.csv"
            if grouping.exists() and graph.exists():
                entities.append(d.name)
        return entities

    def compare(self, dataset: str, slug_a: str, slug_b: str) -> Optional[PairResult]:
        """Compare a single pair of entities."""
        ds_dir = self.output_root / dataset
        kw_a = _entity_keywords(slug_a, ds_dir)
        kw_b = _entity_keywords(slug_b, ds_dir)
        return compare_pair(ds_dir, slug_a, slug_b, dataset, kw_a, kw_b)

    def compare_all(self, dataset: str,
                    progress: bool = True) -> List[PairResult]:
        """Compare all intra-domain entity pairs."""
        ds_dir = self.output_root / dataset
        entities = self.list_entities(dataset)
        n_pairs = len(entities) * (len(entities) - 1) // 2

        if progress:
            print(f"[{dataset}] {len(entities)} entities, {n_pairs} pairs")

        kw_cache: Dict[str, Set[str]] = {}
        for slug in entities:
            kw_cache[slug] = _entity_keywords(slug, ds_dir)

        results: List[PairResult] = []
        done = 0
        for slug_a, slug_b in combinations(entities, 2):
            res = compare_pair(
                ds_dir, slug_a, slug_b, dataset,
                kw_cache[slug_a], kw_cache[slug_b],
            )
            if res is not None:
                results.append(res)
            done += 1
            if progress and done % 100 == 0:
                print(f"  {done}/{n_pairs} pairs done")

        if progress:
            print(f"  {done}/{n_pairs} pairs done (complete)")
        return results

    def save_results(self, results: List[PairResult],
                     output_path: Path) -> None:
        """Save results as CSV."""
        if not results:
            return
        output_path.parent.mkdir(parents=True, exist_ok=True)
        fields = list(results[0].as_flat_dict().keys())
        with open(output_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()
            for r in results:
                writer.writerow(r.as_flat_dict())

    def save_json(self, results: List[PairResult],
                  output_path: Path) -> None:
        """Save results as JSON."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        data = [asdict(r) for r in results]
        for d in data:
            d.pop("activation_rel_diffs", None)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, default=str)
