"""
Matching helpers for structurally-matched control interventions.

When sampling random features, we often want to match the layer
distribution, position distribution, or other structural properties
of the labeled intervention so the null is as comparable as possible.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple


def resolve_stored_activation(
    layer: int,
    index: int,
    position: int,
    activations_map: Dict[Tuple[int, int, int], float],
) -> Optional[float]:
    """
    Look up stored activation from an activations_map using the same
    resolution rules as the labeled path in ``compute_ct_interventions``:

    1. Exact ``(layer, index, position)`` match.
    2. Wildcard fallback when ``position == -1``: scan for any
       ``(layer, index, *)`` entry.

    Returns None if no match is found.
    """
    key = (layer, index, position)
    if key in activations_map:
        return activations_map[key]
    if position == -1:
        for (l, f, p), val in activations_map.items():
            if l == layer and f == index:
                return val
    return None


def compute_match_diagnostics(
    requested: Dict[int, int],
    achieved: Dict[int, int],
) -> Dict[str, Any]:
    """
    Compare requested vs achieved histograms and return diagnostics.

    Parameters
    ----------
    requested:
        e.g. layer histogram of the labeled intervention.
    achieved:
        e.g. layer histogram of the sampled control.

    Returns
    -------
    Dict with keys:
        - requested_total
        - achieved_total
        - deficit (requested - achieved)
        - bins_exact_match (count of bins with exact count)
        - per_bin (list of {bin, requested, achieved, delta})
    """
    all_bins = sorted(set(requested) | set(achieved))
    per_bin = []
    exact = 0
    for b in all_bins:
        r = requested.get(b, 0)
        a = achieved.get(b, 0)
        per_bin.append({"bin": b, "requested": r, "achieved": a, "delta": a - r})
        if r == a:
            exact += 1

    req_total = sum(requested.values())
    ach_total = sum(achieved.values())

    return {
        "requested_total": req_total,
        "achieved_total": ach_total,
        "deficit": req_total - ach_total,
        "bins_exact_match": exact,
        "total_bins": len(all_bins),
        "per_bin": per_bin,
    }


def build_intervention_dicts(
    sampled_features: List[Dict[str, Any]],
    M: float,
    *,
    position: int = -1,
    steer_generated_tokens: bool = False,
    use_stored_as_base: bool = False,
    stored_activation: Optional[float] = None,
    activations_map: Optional[Dict[Tuple[int, int, int], float]] = None,
) -> List[Dict[str, Any]]:
    """
    Convert sampled feature candidates into the intervention dict shape
    consumed by ``batch_steering_ct.py``.

    When ``activations_map`` is provided, each feature's stored_activation
    is resolved per-feature using the same lookup rules as the labeled
    path (exact key, then position=-1 wildcard).  This is the correct
    way to attach injection-mode activations for target-side controls.

    The scalar ``stored_activation`` parameter is a fallback applied
    uniformly when ``activations_map`` is not provided.
    """
    interventions: List[Dict[str, Any]] = []
    for feat in sampled_features:
        feat_pos = feat.get("position", position)
        entry: Dict[str, Any] = {
            "layer": feat["layer"],
            "index": feat["index"],
            "position": feat_pos,
            "M": M,
            "ablate": M == 0,
            "steer_generated_tokens": steer_generated_tokens,
        }
        if use_stored_as_base:
            entry["use_stored_as_base"] = True

        if activations_map is not None:
            act = resolve_stored_activation(
                feat["layer"], feat["index"], feat_pos, activations_map,
            )
            if act is not None:
                entry["stored_activation"] = act
        elif stored_activation is not None:
            entry["stored_activation"] = stored_activation

        interventions.append(entry)
    return interventions
