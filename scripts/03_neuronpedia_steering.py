"""
Generic helpers for concept-based supernode steering via the Neuronpedia API.

This module provides:
    * Lightweight dataclasses describing features, supernodes, and steering configs.
    * Utilities to extract supernodes tied to arbitrary concepts (e.g., states).
    * Helpers to convert supernodes into Neuronpedia /steer payloads.
    * Thin wrappers around the completion steering endpoint.
    * Convenience functions for ablation and swap-style experiments.

It is intentionally generic so that higher-level experiments (state swaps,
concept swaps, etc.) can build on top of it without duplicating boilerplate.
"""
from __future__ import annotations

import argparse
import json
import math
import os
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, MutableMapping, Optional, Sequence, Tuple

import pandas as pd
import requests

STEER_ENDPOINT = "https://www.neuronpedia.org/api/steer"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class FeatureRef:
    """Reference to a single CLT/SAE feature along with its peak activation."""

    layer: int
    index: int
    activation_max: float = 0.0


@dataclass
class SupernodeSpec:
    """Collection of features associated with a concept for a specific slug/prompt."""

    concept: str
    slug: str
    features: List[FeatureRef]
    meta: Dict[str, Any] = field(default_factory=dict)

    def ensure_non_empty(self) -> None:
        if not self.features:
            raise ValueError(
                f"Supernode '{self.concept}' ({self.slug}) does not contain any features."
            )


@dataclass
class SteeringConfig:
    """All knobs required to call the Neuronpedia steering endpoint."""

    model_id: str = "gemma-2-2b"
    source_set: str = "clt-hp"
    steer_method: str = "ORTHOGONAL_DECOMP"
    temperature: float = 0.3
    n_tokens: int = 32
    freq_penalty: float = 2.0
    seed: int = 42
    strength_multiplier: float = 1.0


@dataclass
class SteeringResult:
    """Convenience wrapper for responses from the /steer endpoint."""

    prompt: str
    steered_text: str
    default_text: str
    steered_logprobs: List[Dict[str, Any]]
    default_logprobs: Optional[List[Dict[str, Any]]]
    raw: Dict[str, Any]

    def token_logprob(self, token: str, *, default: bool = False) -> Optional[float]:
        """Return the first logprob entry matching ``token`` (exact string match)."""
        entries = self.default_logprobs if default else self.steered_logprobs
        if not entries:
            return None
        for entry in entries:
            if entry.get("token") == token:
                return entry.get("logprob")
        return None


# ---------------------------------------------------------------------------
# Supernode extraction
# ---------------------------------------------------------------------------


def _parse_initial_letters(word: str) -> List[str]:
    """Extract unique letters from an initial-like token.

    "j.r.r." -> ["j", "r"]
    "j.k."   -> ["j", "k"]
    "f."     -> ["f"]
    Returns empty list if the word doesn't look like an initial.
    """
    if "." not in word:
        return []
    letters = [ch for ch in word if ch.isalpha()]
    seen: set = set()
    unique: List[str] = []
    for letter in letters:
        if letter not in seen:
            seen.add(letter)
            unique.append(letter)
    return unique


_FUNCTION_WORDS = frozenset({"a", "an", "at", "by", "de", "di", "du", "el",
                              "in", "la", "le", "of", "on", "or", "the", "to",
                              "van", "von", "y"})


def _match_concept_to_supernodes(
    grouping_df: pd.DataFrame,
    names: "pd.Series",
    concept_lc: str,
) -> pd.DataFrame:
    """Find rows in grouping_df whose supernode_name matches *concept_lc*.

    Strategy (in order):
    1. Substring match on the full concept string.
    2. Per-word fallback for multi-word concepts:
       a. Normal words (len >= 3, not a function word): substring match.
       b. Initials containing periods ("j.r.r.", "j.k."): extract each
          letter and look for exact supernode names or "Say (letter)" names.
    """
    matches = grouping_df[names.str.contains(concept_lc, na=False, regex=False)]
    if not matches.empty:
        return matches

    if " " not in concept_lc:
        return matches

    words = concept_lc.split()
    all_matches: List[pd.DataFrame] = []

    for word in words:
        initial_letters = _parse_initial_letters(word)
        if initial_letters:
            for letter in initial_letters:
                hit = grouping_df[
                    names.eq(letter) | names.eq(f"say ({letter})")
                ]
                if not hit.empty:
                    all_matches.append(hit)
        elif len(word) >= 3 and word not in _FUNCTION_WORDS:
            hit = grouping_df[names.str.contains(word, na=False, regex=False)]
            if not hit.empty:
                all_matches.append(hit)

    if all_matches:
        return pd.concat(all_matches).drop_duplicates()
    return matches


def extract_concept_supernode(
    grouping_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
    concept: str,
    slug: str,
    *,
    supernode_col: str = "supernode_name",
) -> SupernodeSpec:
    """
    Extract every feature whose supernode name matches ``concept``.

    Matching strategy (case-insensitive):
    1. Full concept substring match (e.g. "tolkien" in "Say (Tolkien)").
    2. Per-word fallback for multi-word concepts:
       - Normal words (>= 3 chars): substring match.
       - Initials with periods ("j.r.r."): extract each letter and match
         exact supernode names ("j") or Say patterns ("say (j)").
       - Common function words ("of", "the", "de", ...) are skipped.
    """
    if not concept.strip():
        raise ValueError("Concept string must be non-empty.")

    concept_lc = concept.strip().lower()
    if supernode_col not in grouping_df.columns:
        raise KeyError(f"Column '{supernode_col}' not found in grouping dataframe.")

    names = grouping_df[supernode_col].astype(str).str.lower()
    matches = _match_concept_to_supernodes(grouping_df, names, concept_lc)

    if matches.empty:
        raise ValueError(
            f"No supernode rows matched concept '{concept}' for slug '{slug}'."
        )

    # Build activation lookup for quick access.
    activation_lookup = _build_activation_lookup(metrics_df)

    feature_refs: Dict[Tuple[int, int], FeatureRef] = {}
    for _, row in matches.iterrows():
        layer = int(row["layer"])
        feature = int(row["feature"])
        key = (layer, feature)
        if key in feature_refs:
            continue
        activation_max = activation_lookup.get(key, 0.0)
        feature_refs[key] = FeatureRef(layer=layer, index=feature, activation_max=activation_max)

    features = list(feature_refs.values())
    if not features:
        raise ValueError(
            f"After deduplication, supernode '{concept}' for slug '{slug}' had no features."
        )

    return SupernodeSpec(concept=concept, slug=slug, features=features)


def _build_activation_lookup(metrics_df: pd.DataFrame) -> Dict[Tuple[int, int], float]:
    """
    Map (layer, feature) -> max activation using the graph_feature_static_metrics CSV.
    """
    required_cols = {"layer", "feature", "activation"}
    missing = required_cols - set(metrics_df.columns)
    if missing:
        raise KeyError(f"Metrics dataframe is missing columns: {', '.join(sorted(missing))}")

    lut: Dict[Tuple[int, int], float] = {}
    grouped = (
        metrics_df.dropna(subset=["layer", "feature", "activation"])
        .groupby(["layer", "feature"])["activation"]
        .max()
    )
    for (layer, feature), value in grouped.items():
        lut[(int(layer), int(feature))] = float(value)
    return lut


def compute_supernode_static_stats(
    supernode: SupernodeSpec,
    metrics_df: pd.DataFrame,
) -> Dict[str, float]:
    """
    Aggregate static graph metrics (node & cumulative influence) for a supernode.
    """
    required = {"layer", "feature", "node_influence", "cumulative_influence"}
    missing = required - set(metrics_df.columns)
    if missing:
        raise KeyError(
            f"Metrics dataframe is missing columns: {', '.join(sorted(missing))}"
        )

    grouped = (
        metrics_df.dropna(subset=["layer", "feature"])
        .groupby(["layer", "feature"])
        .agg(
            node_influence_sum=("node_influence", "sum"),
            cumulative_influence_sum=("cumulative_influence", "sum"),
        )
    )

    lookup = {
        (int(layer), int(feature)): row
        for (layer, feature), row in grouped.iterrows()
    }

    total_node = 0.0
    total_cum = 0.0
    missing_features = 0

    for feature in supernode.features:
        key = (feature.layer, feature.index)
        row = lookup.get(key)
        if row is None:
            missing_features += 1
            continue
        total_node += float(row["node_influence_sum"])
        total_cum += float(row["cumulative_influence_sum"])

    feature_count = len(supernode.features)
    present = feature_count - missing_features
    return {
        "feature_count": feature_count,
        "features_with_metrics": present,
        "missing_features": missing_features,
        "node_influence_sum": total_node,
        "node_influence_mean": total_node / present if present else 0.0,
        "cumulative_influence_sum": total_cum,
        "cumulative_influence_mean": total_cum / present if present else 0.0,
    }


# ---------------------------------------------------------------------------
# Feature strength mapping
# ---------------------------------------------------------------------------


def compute_supernode_strengths(
    supernode: SupernodeSpec,
    M: float,
    source_set: str,
    *,
    normalization: str = "none",
    ensure_non_empty: bool = False,
) -> List[Dict[str, Any]]:
    """
    Convert a supernode into a list of per-feature steering strengths.

    Current rule: strength = (M - 1) * activation_max.
    ``normalization`` is reserved for future extensions; currently it is recorded
    in the payload for transparency.
    """
    supernode.ensure_non_empty()
    payload: List[Dict[str, Any]] = []
    first_feature_entry: Optional[Dict[str, Any]] = None
    for feature in supernode.features:
        delta = (M - 1.0) * feature.activation_max
        entry = {
            "modelId": None,
            "layer": _format_source(feature.layer, source_set),
            "index": feature.index,
            "strength": delta,
            "normalization": normalization,
        }
        if first_feature_entry is None:
            first_feature_entry = dict(entry)
        if math.isclose(delta, 0.0, abs_tol=1e-9):
            continue
        payload.append(entry)

    if ensure_non_empty and not payload and first_feature_entry is not None:
        first_feature_entry["strength"] = 0.0
        payload.append(first_feature_entry)
    return payload


def _format_source(layer: int, source_set: str) -> str:
    """Match Neuronpedia's convention for referencing CLT layers."""
    return f"{layer}-{source_set}"


# ---------------------------------------------------------------------------
# Steering API helpers
# ---------------------------------------------------------------------------


def steer_completion(
    prompt: str,
    features: Sequence[Dict[str, Any]],
    cfg: SteeringConfig,
    *,
    api_key: Optional[str] = None,
    session: Optional[requests.Session] = None,
) -> SteeringResult:
    """
    Call the Neuronpedia /steer endpoint and return a ``SteeringResult``.
    """
    api_key = api_key or os.environ.get("NEURONPEDIA_API_KEY")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["x-api-key"] = api_key

    api_features = []
    for feature in features:
        entry = dict(feature)
        entry["modelId"] = cfg.model_id
        api_features.append(entry)

    payload = {
        "prompt": prompt,
        "modelId": cfg.model_id,
        "features": api_features,
        "temperature": cfg.temperature,
        "n_tokens": cfg.n_tokens,
        "freq_penalty": cfg.freq_penalty,
        "seed": cfg.seed,
        "strength_multiplier": cfg.strength_multiplier,
        "steer_method": cfg.steer_method,
    }

    client = session or requests
    response = client.post(STEER_ENDPOINT, headers=headers, data=json.dumps(payload), timeout=120)
    if response.status_code != 200:
        raise RuntimeError(
            f"Neuronpedia steering request failed (status={response.status_code}): {response.text}"
        )

    data = response.json()
    return SteeringResult(
        prompt=prompt,
        steered_text=data.get("STEERED", ""),
        default_text=data.get("DEFAULT", ""),
        steered_logprobs=data.get("steeredLogProbs", []) or [],
        default_logprobs=data.get("defaultLogProbs"),
        raw=data,
    )


def run_ablation_experiment(
    prompt: str,
    supernode: SupernodeSpec,
    Ms: Sequence[float],
    cfg: SteeringConfig,
    *,
    target_tokens: Optional[Sequence[str]] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Sweep over ``Ms`` to ablate/amplify a single supernode and report logprob deltas.
    """
    baseline_payload = compute_supernode_strengths(
        supernode, 1.0, cfg.source_set, ensure_non_empty=True
    )
    baseline = steer_completion(prompt, baseline_payload, cfg, api_key=api_key)

    results: List[Dict[str, Any]] = []
    for M in Ms:
        feature_payload = compute_supernode_strengths(
            supernode, M, cfg.source_set, ensure_non_empty=True
        )
        response = steer_completion(prompt, feature_payload, cfg, api_key=api_key)
        metrics = _compute_token_metrics(baseline, response, target_tokens)
        results.append(
            {
                "M": M,
                "feature_count": len(feature_payload),
                "token_metrics": metrics,
                "response": response,
            }
        )

    return {"baseline": baseline, "results": results}


def run_swap_experiment(
    prompt: str,
    supernode_from: SupernodeSpec,
    supernode_to: SupernodeSpec,
    M_ablate: float,
    M_amplify: float,
    cfg: SteeringConfig,
    *,
    target_tokens: Optional[Sequence[str]] = None,
    api_key: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Apply an ablation to ``supernode_from`` and an amplification to ``supernode_to`` simultaneously.
    """
    baseline_payload = compute_supernode_strengths(
        supernode_from, 1.0, cfg.source_set, ensure_non_empty=True
    )
    baseline = steer_completion(prompt, baseline_payload, cfg, api_key=api_key)

    payload = compute_supernode_strengths(
        supernode_from, M_ablate, cfg.source_set, ensure_non_empty=True
    ) + compute_supernode_strengths(
        supernode_to, M_amplify, cfg.source_set, ensure_non_empty=True
    )
    response = steer_completion(prompt, payload, cfg, api_key=api_key)
    metrics = _compute_token_metrics(baseline, response, target_tokens)
    return {
        "baseline": baseline,
        "response": response,
        "token_metrics": metrics,
        "payload_feature_count": len(payload),
    }


def _compute_token_metrics(
    baseline: SteeringResult,
    steered: SteeringResult,
    tokens: Optional[Sequence[str]],
) -> Dict[str, Dict[str, Optional[float]]]:
    """
    For each target token, compute baseline logprob, steered logprob, and delta.
    """
    metrics: Dict[str, Dict[str, Optional[float]]] = {}
    if not tokens:
        return metrics
    for token in tokens:
        base_lp = baseline.token_logprob(token)
        steered_lp = steered.token_logprob(token)
        delta = None
        if base_lp is not None and steered_lp is not None:
            delta = steered_lp - base_lp
        metrics[token] = {"baseline": base_lp, "steered": steered_lp, "delta": delta}
    return metrics


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run a concept-based steering sweep on a single prompt using Neuronpedia."
    )
    parser.add_argument("--grouping", required=True, help="Path to node_grouping.csv")
    parser.add_argument(
        "--metrics", required=True, help="Path to graph_feature_static_metrics.csv"
    )
    parser.add_argument("--concept", required=True, help="Concept string to match.")
    parser.add_argument(
        "--slug",
        required=True,
        help="Slug or identifier for this prompt (used only for logging).",
    )
    parser.add_argument("--prompt", required=True, help="Prompt text to steer.")
    parser.add_argument(
        "--M",
        nargs="+",
        type=float,
        default=[-1.0, 0.0, 2.0],
        help="List of multiplicative factors to sweep during ablation.",
    )
    parser.add_argument(
        "--target-token",
        action="append",
        dest="target_tokens",
        help="Token whose logprob delta should be tracked (repeatable).",
    )
    parser.add_argument("--model-id", default="gemma-2-2b")
    parser.add_argument("--source-set", default="clt-hp")
    parser.add_argument("--steer-method", default="ORTHOGONAL_DECOMP")
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--n-tokens", type=int, default=32)
    parser.add_argument("--freq-penalty", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--strength-multiplier", type=float, default=1.0)
    parser.add_argument(
        "--api-key",
        default=None,
        help="Optional Neuronpedia API key (falls back to NEURONPEDIA_API_KEY).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    grouping_df = pd.read_csv(args.grouping)
    metrics_df = pd.read_csv(args.metrics)

    supernode = extract_concept_supernode(
        grouping_df=grouping_df,
        metrics_df=metrics_df,
        concept=args.concept,
        slug=args.slug,
    )

    cfg = SteeringConfig(
        model_id=args.model_id,
        source_set=args.source_set,
        steer_method=args.steer_method,
        temperature=args.temperature,
        n_tokens=args.n_tokens,
        freq_penalty=args.freq_penalty,
        seed=args.seed,
        strength_multiplier=args.strength_multiplier,
    )

    sweep = run_ablation_experiment(
        prompt=args.prompt,
        supernode=supernode,
        Ms=args.M,
        cfg=cfg,
        target_tokens=args.target_tokens,
        api_key=args.api_key,
    )

    print("=== Baseline ===")
    print(sweep["baseline"].steered_text)

    for result in sweep["results"]:
        M = result["M"]
        print(f"\n=== M = {M} ({result['feature_count']} features) ===")
        print(result["response"].steered_text)
        for token, stats in (result["token_metrics"] or {}).items():
            print(
                f"  Token '{token}': baseline={stats['baseline']} steered={stats['steered']} delta={stats['delta']}"
            )


if __name__ == "__main__":
    main()

