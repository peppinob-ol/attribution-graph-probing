"""
Circuit Tracer steering helpers for concept-based supernode interventions.

This is the Circuit Tracer equivalent of 03_neuronpedia_steering.py, providing:
    * Dataclasses for CT intervention features and supernodes
    * Utilities to extract supernodes and convert them to CT intervention format
    * Local steering execution using ReplacementModel.feature_intervention
    * Ablation and swap experiment helpers

Key differences from SAE-based steering (03_neuronpedia_steering.py):
1. Uses ReplacementModel with CrossLayerTranscoder (CLT)
2. Interventions are absolute values, not relative strengths
3. Features write to ALL subsequent layers (cross-layer)
4. Supports freeze_attention for constrained patching
5. Position-specific interventions
"""
from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Sequence, Tuple, Union

import pandas as pd
import torch


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CTFeatureRef:
    """Reference to a single CLT feature along with its activation info."""
    layer: int
    index: int
    position: int  # Token position where feature is active
    activation: float = 0.0  # Activation value at that position


@dataclass
class CTSupernodeSpec:
    """Collection of CLT features associated with a concept for a specific slug/prompt."""
    concept: str
    slug: str
    features: List[CTFeatureRef]
    meta: Dict[str, Any] = field(default_factory=dict)

    def ensure_non_empty(self) -> None:
        if not self.features:
            raise ValueError(
                f"Supernode '{self.concept}' ({self.slug}) does not contain any features."
            )


@dataclass
class CTSteeringConfig:
    """Configuration for Circuit Tracer steering."""
    model_id: str = "google/gemma-2-2b"
    transcoder_set: str = "gemma"
    temperature: float = 0.3
    n_tokens: int = 32
    freq_penalty: float = 2.0
    seed: int = 42
    freeze_attention: bool = False
    top_k: int = 5


@dataclass
class CTSteeringResult:
    """Result from a Circuit Tracer steering operation."""
    prompt: str
    steered_text: str
    default_text: str
    steered_topk: List[Dict[str, Any]]
    default_topk: List[Dict[str, Any]]
    intervention_count: int
    raw: Dict[str, Any] = field(default_factory=dict)

    def token_prob(self, token: str, *, default: bool = False) -> Optional[float]:
        """Return the probability for a token from top-k (exact string match)."""
        entries = self.default_topk if default else self.steered_topk
        if not entries:
            return None
        for entry in entries:
            if entry.get("token") == token:
                return entry.get("prob")
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
    # 1. Full concept match
    matches = grouping_df[names.str.contains(concept_lc, na=False, regex=False)]
    if not matches.empty:
        return matches

    if " " not in concept_lc:
        return matches  # single word, nothing more to try

    # 2. Per-word fallback
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
    return matches  # still empty


def extract_ct_supernode(
    grouping_df: pd.DataFrame,
    metrics_df: pd.DataFrame,
    concept: str,
    slug: str,
    *,
    supernode_col: str = "supernode_name",
    position_col: str = "position",
) -> CTSupernodeSpec:
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

    # Build activation lookup for quick access
    activation_lookup = _build_activation_lookup(metrics_df)

    feature_refs: Dict[Tuple[int, int, int], CTFeatureRef] = {}
    for _, row in matches.iterrows():
        layer = int(row["layer"])
        feature = int(row["feature"])
        
        # Get position - default to -1 (last token) if not available
        if position_col in row and pd.notna(row[position_col]):
            position = int(row[position_col])
        else:
            position = -1
        
        key = (layer, feature, position)
        if key in feature_refs:
            continue
        
        activation = activation_lookup.get((layer, feature, position), 0.0)
        feature_refs[key] = CTFeatureRef(
            layer=layer, index=feature, position=position, activation=activation
        )

    features = list(feature_refs.values())
    if not features:
        raise ValueError(
            f"After deduplication, supernode '{concept}' for slug '{slug}' had no features."
        )

    return CTSupernodeSpec(concept=concept, slug=slug, features=features)


def _build_activation_lookup(
    metrics_df: pd.DataFrame,
) -> Dict[Tuple[int, int, int], float]:
    """
    Map (layer, feature, position) -> activation using graph_feature_static_metrics CSV.
    Falls back to (layer, feature) -> max activation if position not available.
    """
    lut: Dict[Tuple[int, int, int], float] = {}
    
    required_cols = {"layer", "feature", "activation"}
    missing = required_cols - set(metrics_df.columns)
    if missing:
        raise KeyError(f"Metrics dataframe is missing columns: {', '.join(sorted(missing))}")

    has_position = "position" in metrics_df.columns

    for _, row in metrics_df.dropna(subset=["layer", "feature", "activation"]).iterrows():
        layer = int(row["layer"])
        feature = int(row["feature"])
        activation = float(row["activation"])
        
        if has_position and pd.notna(row.get("position")):
            position = int(row["position"])
            lut[(layer, feature, position)] = activation
        else:
            # Store with position -1 as fallback
            key = (layer, feature, -1)
            if key not in lut or activation > lut[key]:
                lut[key] = activation

    return lut


def compute_supernode_static_stats(
    supernode: CTSupernodeSpec,
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
# Intervention tuple generation
# ---------------------------------------------------------------------------


def compute_ct_interventions(
    supernode: CTSupernodeSpec,
    M: float,
    *,
    steer_generated_tokens: bool = False,
    activations_map: Optional[Dict[Tuple[int, int, int], float]] = None,
    use_stored_as_base: bool = False,
) -> List[Dict[str, Any]]:
    """
    Convert a supernode into Circuit Tracer intervention specifications.

    This follows the original circuit_tracer demo approach:
        new_value = M * activations[layer, pos, feature_idx]

    Args:
        supernode: The supernode to convert
        M: Multiplicative factor:
           - M=0: Full ablation (set to 0)
           - M=1: No change
           - M=2: Double the activation
           - M=10: 10x the activation (like in the demo)
           - M=-1: Negate the activation
        steer_generated_tokens: If True, apply to all generated tokens
        activations_map: Optional dict mapping (layer, feature, position) to stored activation values
                         from graph.json. If provided, stored_activation will be included in output.
        use_stored_as_base: If True, use stored_activation as the base value for M multiplication
                           (injection mode). If False, use live activation from current prompt
                           (multiplication mode). Injection mode is needed for cross-graph steering
                           where the target features may not be active on the current prompt.

    Returns:
        List of intervention dicts ready for batch_steering_ct.py
    """
    supernode.ensure_non_empty()
    
    interventions: List[Dict[str, Any]] = []
    
    for feature in supernode.features:
        # Use M directly (matches original demo: new_value = M * activation)
        entry = {
            "layer": feature.layer,
            "index": feature.index,
            "position": feature.position,
            "M": M,  # Multiplicative factor applied to activation
            "ablate": M == 0,  # Ablate flag for M=0 case
            "steer_generated_tokens": steer_generated_tokens,
        }
        
        # Include stored activation from graph.json if available
        # Handles position=-1 (relative) by searching for any matching (layer, feature, *)
        if activations_map is not None:
            key = (feature.layer, feature.index, feature.position)
            if key in activations_map:
                entry["stored_activation"] = activations_map[key]
            elif feature.position == -1:
                # Position is relative (-1 = last token) - search for any match
                for (l, f, p), val in activations_map.items():
                    if l == feature.layer and f == feature.index:
                        entry["stored_activation"] = val
                        break
        
        # Mark whether to use stored_activation as the base value (injection mode)
        if use_stored_as_base:
            entry["use_stored_as_base"] = True
        
        interventions.append(entry)
    
    return interventions


def build_intervention_tuples_from_activations(
    supernode: CTSupernodeSpec,
    M: float,
    activations: torch.Tensor,
    sequence_length: int,
    *,
    steer_generated_tokens: bool = False,
) -> List[Tuple[int, Union[int, slice], int, float]]:
    """
    Build intervention tuples directly from live activations.

    This is useful when you have the model loaded and want to use actual
    activation values rather than pre-computed ones.

    Args:
        supernode: The supernode to convert
        M: Multiplicative factor
        activations: Sparse/dense tensor [n_layers, n_pos, d_transcoder]
        sequence_length: Number of tokens in the prompt
        steer_generated_tokens: If True, apply to all generated tokens

    Returns:
        List of (layer, position, feature_idx, new_value) tuples
    """
    supernode.ensure_non_empty()
    
    if activations.is_sparse:
        activations = activations.to_dense()
    
    tuples = []
    
    for feature in supernode.features:
        # Resolve position
        pos = feature.position
        if pos < 0:
            pos = sequence_length + pos
        
        # Get actual activation
        try:
            original = float(activations[feature.layer, pos, feature.index])
        except IndexError:
            print(
                f"Warning: Could not get activation for {feature}. Using stored value."
            )
            original = feature.activation
        
        # Compute new value
        if M == 0:
            new_value = 0.0
        else:
            new_value = M * original
        
        # Determine steering position
        if steer_generated_tokens:
            steer_pos: Union[int, slice] = slice(sequence_length, None, None)
        else:
            steer_pos = pos
        
        tuples.append((feature.layer, steer_pos, feature.index, new_value))
    
    return tuples


# ---------------------------------------------------------------------------
# Local steering execution (requires model)
# ---------------------------------------------------------------------------


def ct_steer(
    prompt: str,
    interventions: List[Tuple[int, Union[int, slice], int, float]],
    model,
    cfg: CTSteeringConfig,
) -> CTSteeringResult:
    """
    Execute Circuit Tracer steering using a loaded ReplacementModel.

    Args:
        prompt: Input prompt
        interventions: List of (layer, position, feature_idx, new_value) tuples
        model: Loaded ReplacementModel
        cfg: Steering configuration

    Returns:
        CTSteeringResult with steered and default outputs
    """
    # Set seed
    if cfg.seed is not None:
        torch.manual_seed(cfg.seed)

    # Run default generation
    default_tokens = model.generate(
        prompt,
        do_sample=True,
        use_past_kv_cache=False,
        verbose=False,
        stop_at_eos=True,
        max_new_tokens=cfg.n_tokens,
        temperature=cfg.temperature,
        freq_penalty=cfg.freq_penalty,
        return_type="tokens",
    )
    if isinstance(default_tokens, tuple):
        default_tokens = default_tokens[0]
    default_text = model.tokenizer.decode(default_tokens[0], skip_special_tokens=False)

    # Reset seed
    if cfg.seed is not None:
        torch.manual_seed(cfg.seed)

    # Run steered generation
    if interventions:
        steered_result = model.feature_intervention_generate(
            prompt,
            interventions,
            freeze_attention=cfg.freeze_attention,
            do_sample=True,
            verbose=False,
            stop_at_eos=True,
            max_new_tokens=cfg.n_tokens + 1,
            temperature=cfg.temperature,
            freq_penalty=cfg.freq_penalty,
            return_type="tokens",
        )
        steered_tokens, steered_logits, _ = steered_result
        if isinstance(steered_tokens, tuple):
            steered_tokens = steered_tokens[0]
        steered_text = model.tokenizer.decode(
            steered_tokens[0], skip_special_tokens=False
        )
    else:
        steered_text = default_text
        steered_logits = None

    # Get top-k logits
    def get_topk(logits, k):
        probs = torch.softmax(logits.squeeze()[-1], dim=-1)
        topk = torch.topk(probs, k)
        return [
            {"token": model.tokenizer.decode([topk.indices[i].item()]), "prob": float(topk.values[i].item())}
            for i in range(k)
        ]

    steered_topk = []
    if steered_logits is not None:
        with torch.inference_mode():
            steered_topk = get_topk(steered_logits, cfg.top_k)

    default_topk = []
    with torch.inference_mode():
        default_logits = model(default_text)
        default_topk = get_topk(default_logits, cfg.top_k)

    return CTSteeringResult(
        prompt=prompt,
        steered_text=steered_text,
        default_text=default_text,
        steered_topk=steered_topk,
        default_topk=default_topk,
        intervention_count=len(interventions),
    )


# ---------------------------------------------------------------------------
# Experiment helpers
# ---------------------------------------------------------------------------


def run_ct_ablation_experiment(
    prompt: str,
    supernode: CTSupernodeSpec,
    Ms: Sequence[float],
    model,
    cfg: CTSteeringConfig,
    *,
    target_tokens: Optional[Sequence[str]] = None,
    steer_generated_tokens: bool = False,
) -> Dict[str, Any]:
    """
    Sweep over M values to ablate/amplify a supernode using CT interventions.
    """
    # Get activations once
    _, activations = model.get_activations(prompt, sparse=True)
    tokens = model.tokenizer(prompt, return_tensors="pt").input_ids
    seq_len = tokens.shape[1]

    # Baseline (M=1, no change)
    baseline_tuples = build_intervention_tuples_from_activations(
        supernode, 1.0, activations, seq_len, steer_generated_tokens=steer_generated_tokens
    )
    baseline = ct_steer(prompt, baseline_tuples, model, cfg)

    results: List[Dict[str, Any]] = []
    for M in Ms:
        intervention_tuples = build_intervention_tuples_from_activations(
            supernode, M, activations, seq_len, steer_generated_tokens=steer_generated_tokens
        )
        response = ct_steer(prompt, intervention_tuples, model, cfg)
        metrics = _compute_token_metrics(baseline, response, target_tokens)
        results.append({
            "M": M,
            "intervention_count": len(intervention_tuples),
            "token_metrics": metrics,
            "response": response,
        })

    return {"baseline": baseline, "results": results}


def run_ct_swap_experiment(
    prompt: str,
    supernode_from: CTSupernodeSpec,
    supernode_to: CTSupernodeSpec,
    M_ablate: float,
    M_amplify: float,
    model,
    cfg: CTSteeringConfig,
    *,
    target_tokens: Optional[Sequence[str]] = None,
    steer_generated_tokens: bool = False,
) -> Dict[str, Any]:
    """
    Apply ablation to supernode_from and amplification to supernode_to simultaneously.
    """
    # Get activations
    _, activations = model.get_activations(prompt, sparse=True)
    tokens = model.tokenizer(prompt, return_tensors="pt").input_ids
    seq_len = tokens.shape[1]

    # Baseline
    baseline_tuples = build_intervention_tuples_from_activations(
        supernode_from, 1.0, activations, seq_len, steer_generated_tokens=steer_generated_tokens
    )
    baseline = ct_steer(prompt, baseline_tuples, model, cfg)

    # Combined interventions
    ablate_tuples = build_intervention_tuples_from_activations(
        supernode_from, M_ablate, activations, seq_len, steer_generated_tokens=steer_generated_tokens
    )
    amplify_tuples = build_intervention_tuples_from_activations(
        supernode_to, M_amplify, activations, seq_len, steer_generated_tokens=steer_generated_tokens
    )
    combined_tuples = ablate_tuples + amplify_tuples

    response = ct_steer(prompt, combined_tuples, model, cfg)
    metrics = _compute_token_metrics(baseline, response, target_tokens)

    return {
        "baseline": baseline,
        "response": response,
        "token_metrics": metrics,
        "intervention_count": len(combined_tuples),
    }


def _compute_token_metrics(
    baseline: CTSteeringResult,
    steered: CTSteeringResult,
    tokens: Optional[Sequence[str]],
) -> Dict[str, Dict[str, Optional[float]]]:
    """Compute probability deltas for target tokens."""
    metrics: Dict[str, Dict[str, Optional[float]]] = {}
    if not tokens:
        return metrics
    for token in tokens:
        base_prob = baseline.token_prob(token)
        steered_prob = steered.token_prob(token)
        delta = None
        if base_prob is not None and steered_prob is not None:
            delta = steered_prob - base_prob
        metrics[token] = {"baseline": base_prob, "steered": steered_prob, "delta": delta}
    return metrics


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run Circuit Tracer concept-based steering on a single prompt."
    )
    parser.add_argument("--grouping", required=True, help="Path to node_grouping.csv")
    parser.add_argument(
        "--metrics", required=True, help="Path to graph_feature_static_metrics.csv"
    )
    parser.add_argument("--concept", required=True, help="Concept string to match.")
    parser.add_argument("--slug", required=True, help="Slug identifier for this prompt.")
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
        help="Token whose probability delta should be tracked (repeatable).",
    )
    parser.add_argument("--model-id", default="google/gemma-2-2b")
    parser.add_argument("--transcoder-set", default="gemma")
    parser.add_argument("--temperature", type=float, default=0.3)
    parser.add_argument("--n-tokens", type=int, default=32)
    parser.add_argument("--freq-penalty", type=float, default=2.0)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--freeze-attention", action="store_true", default=False)
    parser.add_argument("--top-k", type=int, default=5)
    parser.add_argument(
        "--steer-generated-tokens",
        action="store_true",
        default=False,
        help="Apply steering to generated tokens (not just prompt positions).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    
    # Load model
    from circuit_tracer.replacement_model import ReplacementModel
    
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    dtype = torch.bfloat16 if device.type == "cuda" else torch.float32
    
    print(f"Loading model {args.model_id} with transcoder {args.transcoder_set}...")
    model = ReplacementModel.from_pretrained(
        args.model_id, args.transcoder_set, device=device, dtype=dtype
    )
    
    # Load data
    grouping_df = pd.read_csv(args.grouping)
    metrics_df = pd.read_csv(args.metrics)

    supernode = extract_ct_supernode(
        grouping_df=grouping_df,
        metrics_df=metrics_df,
        concept=args.concept,
        slug=args.slug,
    )
    print(f"Extracted supernode '{args.concept}' with {len(supernode.features)} features")

    cfg = CTSteeringConfig(
        model_id=args.model_id,
        transcoder_set=args.transcoder_set,
        temperature=args.temperature,
        n_tokens=args.n_tokens,
        freq_penalty=args.freq_penalty,
        seed=args.seed,
        freeze_attention=args.freeze_attention,
        top_k=args.top_k,
    )

    sweep = run_ct_ablation_experiment(
        prompt=args.prompt,
        supernode=supernode,
        Ms=args.M,
        model=model,
        cfg=cfg,
        target_tokens=args.target_tokens,
        steer_generated_tokens=args.steer_generated_tokens,
    )

    print("\n=== Baseline ===")
    print(sweep["baseline"].steered_text)

    for result in sweep["results"]:
        M = result["M"]
        print(f"\n=== M = {M} ({result['intervention_count']} interventions) ===")
        print(result["response"].steered_text)
        for token, stats in (result["token_metrics"] or {}).items():
            print(
                f"  Token '{token}': baseline={stats['baseline']} "
                f"steered={stats['steered']} delta={stats['delta']}"
            )


if __name__ == "__main__":
    main()

