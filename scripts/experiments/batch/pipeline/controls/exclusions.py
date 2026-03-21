"""
Exclusion helpers for control experiments.

When sampling random features as a null baseline, we must exclude the
features that constitute the labeled treatment to avoid leaking concept
signal into the control.
"""
from __future__ import annotations

from typing import Any, Dict, FrozenSet, List, Optional, Set

import pandas as pd


def feature_keys_from_interventions(
    features: List[Dict[str, Any]],
) -> FrozenSet[tuple]:
    """
    Extract unique (layer, index) keys from an intervention list.

    Position is intentionally omitted because the same (layer, index)
    should be excluded regardless of which position it was applied at.
    """
    return frozenset(
        (f["layer"], f["index"]) for f in features if "layer" in f and "index" in f
    )


def exclude_concept_matching_supernodes(
    grouping_df: pd.DataFrame,
    concepts: List[str],
    supernode_col: str = "supernode_name",
) -> Set[tuple]:
    """
    Return (layer, feature) keys for all features in supernodes whose name
    matches any of the given concepts (case-insensitive substring).

    This is broader than ``feature_keys_from_interventions``: it removes
    entire supernodes that could carry concept signal, not just the exact
    features used in the labeled intervention.
    """
    if grouping_df.empty or not concepts:
        return set()

    names = grouping_df[supernode_col].astype(str).str.lower()
    mask = pd.Series(False, index=grouping_df.index)
    for concept in concepts:
        c = concept.strip().lower()
        if c:
            mask |= names.str.contains(c, na=False)

    matched = grouping_df.loc[mask]
    return {
        (int(row["layer"]), int(row["feature"]))
        for _, row in matched.iterrows()
    }


def build_candidate_pool(
    grouping_df: pd.DataFrame,
    exclude_keys: Set[tuple],
) -> List[Dict[str, Any]]:
    """
    Build a list of candidate feature dicts from a grouping dataframe,
    excluding features in ``exclude_keys``.

    Each dict has at least ``layer``, ``index`` (aliased from ``feature``),
    ``supernode_name``, and ``position`` (defaults to -1 if absent).
    """
    has_position = "position" in grouping_df.columns
    candidates: List[Dict[str, Any]] = []
    for _, row in grouping_df.iterrows():
        key = (int(row["layer"]), int(row["feature"]))
        if key in exclude_keys:
            continue
        pos = int(row["position"]) if has_position and pd.notna(row.get("position")) else -1
        candidates.append({
            "layer": key[0],
            "index": key[1],
            "position": pos,
            "supernode_name": str(row.get("supernode_name", "")),
        })
    return candidates
