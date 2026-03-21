"""
Deterministic sampling helpers for control experiments.

Every random selection must be reproducible given a seed triple:
  (run_seed, pair_id, replicate_id)

This module provides the RNG construction and basic sampling
primitives that all randomized controls share.
"""
from __future__ import annotations

import hashlib
import random
from typing import Any, Dict, List, Optional, Sequence, TypeVar

T = TypeVar("T")


def make_control_rng(
    run_seed: int,
    pair_id: str,
    replicate_id: int = 0,
    mode: str = "",
) -> random.Random:
    """
    Create a deterministic RNG for a specific control replicate.

    The seed is a hash of the concatenated identifiers so that:
    - different pairs get different draws
    - different replicates of the same pair get different draws
    - the same triple always reproduces the same draw
    """
    seed_material = f"{run_seed}:{pair_id}:{replicate_id}:{mode}"
    digest = hashlib.sha256(seed_material.encode()).hexdigest()
    numeric_seed = int(digest[:16], 16)
    return random.Random(numeric_seed)


def sample_indices_matching_histogram(
    rng: random.Random,
    pool: List[T],
    pool_key_fn: Any,
    target_histogram: Dict[Any, int],
    fallback_uniform: bool = True,
) -> List[T]:
    """
    Sample from *pool* so the result matches *target_histogram*.

    Parameters
    ----------
    rng:
        Seeded RNG instance.
    pool:
        Candidate items to sample from.
    pool_key_fn:
        Callable that maps a pool item to its histogram bin key
        (e.g. ``lambda f: f["layer"]``).
    target_histogram:
        Maps bin key -> desired count.
    fallback_uniform:
        If a bin has fewer candidates than requested, sample the
        deficit uniformly from the remaining pool items.

    Returns
    -------
    List of sampled items (may be shorter than sum(target_histogram)
    if the pool is too small and fallback_uniform is False).
    """
    by_bin: Dict[Any, List[T]] = {}
    for item in pool:
        key = pool_key_fn(item)
        by_bin.setdefault(key, []).append(item)

    sampled: List[T] = []
    deficit = 0

    for bin_key, count in target_histogram.items():
        candidates = by_bin.get(bin_key, [])
        if len(candidates) >= count:
            sampled.extend(rng.sample(candidates, count))
        else:
            sampled.extend(candidates)
            deficit += count - len(candidates)

    if deficit > 0 and fallback_uniform:
        sampled_set = set(id(x) for x in sampled)
        remaining = [x for x in pool if id(x) not in sampled_set]
        take = min(deficit, len(remaining))
        if take > 0:
            sampled.extend(rng.sample(remaining, take))

    return sampled


def build_layer_histogram(features: List[Dict[str, Any]]) -> Dict[int, int]:
    """Count features per layer."""
    hist: Dict[int, int] = {}
    for f in features:
        layer = f.get("layer", -1)
        hist[layer] = hist.get(layer, 0) + 1
    return hist
