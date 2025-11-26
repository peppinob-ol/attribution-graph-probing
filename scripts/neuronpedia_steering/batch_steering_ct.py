#!/usr/bin/env python3
"""
Batch steering utility using Circuit Tracer's ReplacementModel and feature_intervention.

This is the Circuit Tracer equivalent of batch_steering.py, using:
- ReplacementModel instead of HookedTransformer
- feature_intervention_generate instead of hook-based steering
- Cross-layer transcoder (CLT) decoder vectors that write to ALL subsequent layers
- Optional attention pattern freezing (constrained patching)

Key differences from SAE-based steering:
1. Features write to multiple layers (cross-layer)
2. Intervention is absolute (new_value) not relative (strength * vector)
3. Supports freeze_attention for mechanistic faithfulness
4. Position-specific interventions (not global)

Inputs (via env vars or CLI):
  - PROMPTS_JSON_PATH: file with prompts (list of strings or [{"id","text"}, ...])
  - FEATURES_JSON_PATH: file describing intervention features:
        [
          {"layer": 7, "index": 123, "position": -1, "delta": 5.0},
          {"layer": 7, "index": 456, "position": -1, "delta": 0, "ablate": true},
          ...
        ]
        or {"global": [...], "per_prompt": {"prompt_id": [...]}}
  - OUT_JSON_PATH: destination for steering_dump.json

Outputs:
  steering_dump.json with, for each prompt id:
    {
      "probe_id": "...",
      "prompt": "...",
      "steered": "...",
      "default": "...",
      "intervention_count": N
    }
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import dataclass
from typing import Any, Dict, List, Optional, Tuple, Union

import torch

# Allow importing helper utilities from neuronpedia_activations
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)
from neuronpedia_activations.helpers import load_prompts  # type: ignore


# --------------------------------------------------------------------------------------
# Configuration defaults (overridable via env / CLI)
# --------------------------------------------------------------------------------------

MODEL_ID = os.environ.get("MODEL_ID", "google/gemma-2-2b")
TRANSCODER_SET = os.environ.get("TRANSCODER_SET", "gemma")
PROMPTS_JSON_PATH = os.environ.get("PROMPTS_JSON_PATH", "/content/prompts.json")
FEATURES_JSON_PATH = os.environ.get("FEATURES_JSON_PATH", "/content/features.json")
OUT_JSON_PATH = os.environ.get("OUT_JSON_PATH", "/content/steering_dump.json")

TEMPERATURE = float(os.environ.get("STEER_TEMPERATURE", "0.5"))
N_TOKENS = int(os.environ.get("STEER_N_TOKENS", "16"))
FREQ_PENALTY = float(os.environ.get("STEER_FREQ_PENALTY", "2.0"))
SEED = int(os.environ.get("STEER_SEED", "42"))
FREEZE_ATTENTION = os.environ.get("FREEZE_ATTENTION", "false").lower() in ("1", "true", "yes")
TOP_K = int(os.environ.get("TOP_K", "5"))


# --------------------------------------------------------------------------------------
# Data classes for parsed feature configs
# --------------------------------------------------------------------------------------


@dataclass
class CTInterventionFeature:
    """A single Circuit Tracer intervention specification.
    
    The intervention value is computed as: new_value = M * original_activation
    
    M values:
        M = 0.0  : Full ablation (zero out the feature)
        M = 1.0  : No change
        M = 2.0  : Double the activation (amplify)
        M = -1.0 : Reverse the direction
        M = -2.0 : Double and reverse
    
    If stored_activation is provided (from graph.json), it will be used directly
    instead of calling get_activations() - this is more efficient and guarantees
    consistency with the original graph analysis.
    """
    layer: int
    index: int
    position: int  # Token position where the feature was originally active
    steer_position: Optional[int]  # Position to apply steering (None = same as position)
    M: float  # Multiplicative factor: new_value = M * original_activation
    steer_generated_tokens: bool = False  # If True, apply to all generated tokens
    stored_activation: Optional[float] = None  # Pre-computed activation from graph.json


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Batch Circuit Tracer steering utility."
    )
    parser.add_argument("--prompts", default=PROMPTS_JSON_PATH, help="prompts.json path")
    parser.add_argument(
        "--features", default=FEATURES_JSON_PATH, help="features.json path"
    )
    parser.add_argument("--output", default=OUT_JSON_PATH, help="Output JSON path")

    parser.add_argument("--model-id", default=MODEL_ID, help="HuggingFace model ID")
    parser.add_argument(
        "--transcoder-set", default=TRANSCODER_SET, help="Transcoder set name"
    )
    parser.add_argument("--temperature", type=float, default=TEMPERATURE)
    parser.add_argument("--n-tokens", type=int, default=N_TOKENS)
    parser.add_argument("--freq-penalty", type=float, default=FREQ_PENALTY)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--top-k", type=int, default=TOP_K, help="Top-k logits to return")
    parser.add_argument(
        "--freeze-attention",
        action="store_true",
        default=FREEZE_ATTENTION,
        help="Freeze attention patterns during intervention (constrained patching)",
    )
    parser.add_argument(
        "--device",
        default=None,
        help="Device override (cuda/cpu). Auto-detected if not set.",
    )
    parser.add_argument(
        "--dtype",
        default="bfloat16",
        choices=["float32", "float16", "bfloat16"],
        help="Model dtype",
    )
    return parser.parse_args()


# --------------------------------------------------------------------------------------
# Feature loading / normalization
# --------------------------------------------------------------------------------------


def load_ct_features(
    path: str,
) -> Tuple[List[CTInterventionFeature], Dict[str, List[CTInterventionFeature]]]:
    """
    Load Circuit Tracer intervention features from JSON. Supports:
      - simple list: [{"layer": 7, "index": 0, "position": -1, "delta": 1.5}, ...]
      - {"global": [...], "per_prompt": {"prompt_id": [...]}}
      - {"features": [...]}  (alias of "global")
    """
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)

    global_list: List[Dict[str, Any]] = []
    per_prompt_raw: Dict[str, List[Dict[str, Any]]] = {}

    if isinstance(data, list):
        global_list = data
    elif isinstance(data, dict):
        if "features" in data:
            global_list = data.get("features", [])
        else:
            global_list = data.get("global", [])
        per_prompt_raw = data.get("per_prompt", {})
    else:
        raise ValueError("Invalid features.json format.")

    global_features = _normalize_ct_feature_list(global_list)
    per_prompt = {
        prompt_id: _normalize_ct_feature_list(items)
        for prompt_id, items in per_prompt_raw.items()
    }
    return global_features, per_prompt


def _normalize_ct_feature_list(
    items: List[Dict[str, Any]],
) -> List[CTInterventionFeature]:
    """Normalize feature list to CTInterventionFeature objects."""
    normalized: List[CTInterventionFeature] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"feature #{i}: expected object, got {type(item)}")

        # Required fields
        if "layer" not in item:
            raise ValueError(f"feature #{i}: missing 'layer' field")
        if "index" not in item:
            raise ValueError(f"feature #{i}: missing 'index' field")

        layer = int(item["layer"])
        index = int(item["index"])

        # Position handling
        position = int(item.get("position", -1))
        steer_position = item.get("steer_position")
        if steer_position is not None:
            steer_position = int(steer_position)

        # M (multiplicative factor) and ablate
        # Support both "M" and legacy "delta" format
        if "M" in item:
            M = float(item["M"])
        elif "delta" in item:
            # Legacy delta format: assume delta was computed as (M-1)*activation
            # We can't recover M without knowing activation, so treat delta as M-1
            # This is a fallback - prefer using M directly
            print(f"Warning: feature #{i} uses legacy 'delta' format. Prefer 'M'.")
            M = 1.0  # Default to no change if only delta is provided
        else:
            M = 1.0  # Default: no change
        
        # Legacy 'ablate' field: if present and True, set M=0
        if item.get("ablate", False) and M != 0.0:
            print(f"Note: feature #{i} has ablate=True, setting M=0.0")
            M = 0.0
        
        steer_generated_tokens = bool(item.get("steer_generated_tokens", False))
        
        # Stored activation from graph.json (optional, for optimization)
        stored_activation = item.get("stored_activation")
        if stored_activation is not None:
            stored_activation = float(stored_activation)

        normalized.append(
            CTInterventionFeature(
                layer=layer,
                index=index,
                position=position,
                steer_position=steer_position,
                M=M,
                steer_generated_tokens=steer_generated_tokens,
                stored_activation=stored_activation,
            )
        )
    return normalized


# --------------------------------------------------------------------------------------
# Model initialization
# --------------------------------------------------------------------------------------


def get_device(device_override: Optional[str] = None) -> torch.device:
    """Determine the appropriate device for model loading."""
    if device_override:
        return torch.device(device_override)
    if torch.cuda.is_available():
        return torch.device("cuda")
    elif hasattr(torch.backends, "mps") and torch.backends.mps.is_available():
        return torch.device("mps")
    return torch.device("cpu")


def get_dtype(dtype_str: str) -> torch.dtype:
    """Convert string dtype to torch.dtype."""
    dtype_map = {
        "float32": torch.float32,
        "float16": torch.float16,
        "bfloat16": torch.bfloat16,
    }
    return dtype_map.get(dtype_str, torch.bfloat16)


def load_replacement_model(
    model_id: str,
    transcoder_set: str,
    device: torch.device,
    dtype: torch.dtype,
):
    """Load the Circuit Tracer ReplacementModel."""
    from circuit_tracer.replacement_model import ReplacementModel

    print(f"Loading ReplacementModel: {model_id} with transcoder: {transcoder_set}")
    print(f"  Device: {device}, Dtype: {dtype}")

    model = ReplacementModel.from_pretrained(
        model_id,
        transcoder_set,
        device=device,
        dtype=dtype,
    )
    print("Model loaded successfully.")
    return model


# --------------------------------------------------------------------------------------
# Steering execution
# --------------------------------------------------------------------------------------


def build_intervention_tuples(
    features: List[CTInterventionFeature],
    activations: Optional[torch.Tensor],
    sequence_length: int,
) -> List[Tuple[int, Union[int, slice], int, float]]:
    """
    Convert CTInterventionFeature list to circuit_tracer intervention tuples.

    Args:
        features: List of intervention specifications
        activations: Sparse tensor of shape [n_layers, n_pos, d_transcoder].
                     Can be None if all features have stored_activation.
        sequence_length: Number of tokens in the prompt

    Returns:
        List of (layer, position, feature_idx, new_value) tuples
    """
    intervention_tuples = []
    n_stored = 0
    n_live = 0

    for feat in features:
        # Resolve negative positions
        token_pos = feat.position
        if token_pos < 0:
            token_pos = sequence_length + token_pos

        # Get activation value: prefer stored_activation from graph.json
        if feat.stored_activation is not None:
            original_value = feat.stored_activation
            n_stored += 1
        elif activations is not None:
            # Fall back to live activations from get_activations()
            try:
                if activations.is_sparse:
                    dense_activations = activations.to_dense()
                else:
                    dense_activations = activations
                original_value = float(dense_activations[feat.layer, token_pos, feat.index])
                n_live += 1
            except (IndexError, RuntimeError):
                print(
                    f"Warning: Could not get activation for layer={feat.layer}, "
                    f"pos={token_pos}, index={feat.index}. Using 0.0"
                )
                original_value = 0.0
                n_live += 1
        else:
            print(
                f"Warning: No stored_activation and no activations tensor for "
                f"layer={feat.layer}, index={feat.index}. Using 0.0"
            )
            original_value = 0.0

        # Compute new value using M (multiplicative factor)
        # This matches the original demo: new_value = M * activations[feature]
        # M=0 means ablation, M<0 means reverse direction, M>1 means amplify
        new_value = feat.M * original_value

        # Determine steering position
        if feat.steer_generated_tokens:
            # Apply to all generated tokens
            steer_pos: Union[int, slice] = slice(sequence_length, None, None)
        elif feat.steer_position is not None:
            steer_pos = feat.steer_position
            if steer_pos < 0:
                steer_pos = sequence_length + steer_pos
        else:
            steer_pos = token_pos

        intervention_tuples.append((feat.layer, steer_pos, feat.index, new_value))

    if n_stored > 0 or n_live > 0:
        print(f"  [ACTIVATIONS] Using {n_stored} stored (graph.json) + {n_live} live (get_activations)")

    return intervention_tuples


def get_topk_logits(
    logits: torch.Tensor, tokenizer, k: int = 5
) -> List[Dict[str, Any]]:
    """Get top-k token predictions from logits."""
    probs = torch.softmax(logits.squeeze()[-1], dim=-1)
    topk = torch.topk(probs, k)
    return [
        {
            "token": tokenizer.decode([topk.indices[i].item()]),
            "prob": float(topk.values[i].item()),
        }
        for i in range(k)
    ]


def run_ct_generation(
    prompt: str,
    features: List[CTInterventionFeature],
    model,
    *,
    seed: int,
    temperature: float,
    freq_penalty: float,
    max_new_tokens: int,
    freeze_attention: bool,
    top_k: int,
) -> Dict[str, Any]:
    """
    Run Circuit Tracer intervention and compare steered vs default generation.

    Args:
        prompt: Input prompt text
        features: List of intervention specifications
        model: ReplacementModel instance
        seed: Random seed for reproducibility
        temperature: Sampling temperature
        freq_penalty: Frequency penalty
        max_new_tokens: Number of tokens to generate
        freeze_attention: Whether to freeze attention patterns
        top_k: Number of top logits to return

    Returns:
        Dict with steered/default outputs and logprobs
    """
    # Get sequence length
    tokens = model.tokenizer(prompt, return_tensors="pt").input_ids
    sequence_length = tokens.shape[1]

    # Check if we need to call get_activations (only if some features lack stored_activation)
    need_live_activations = any(f.stored_activation is None for f in features)
    
    if need_live_activations:
        # Get original activations from model (forward pass)
        _, activations = model.get_activations(prompt, sparse=True)
    else:
        # All features have stored_activation from graph.json - skip get_activations!
        activations = None
        print(f"  [OPTIMIZATION] Skipping get_activations - using {len(features)} stored activations")

    # Build intervention tuples
    intervention_tuples = build_intervention_tuples(
        features, activations, sequence_length
    )

    # Set seed for reproducibility
    if seed is not None:
        torch.manual_seed(seed)

    # Run default generation first
    default_tokens = model.generate(
        prompt,
        do_sample=True,
        use_past_kv_cache=False,
        verbose=False,
        stop_at_eos=True,
        max_new_tokens=max_new_tokens,
        temperature=temperature,
        freq_penalty=freq_penalty,
        return_type="tokens",
    )
    if isinstance(default_tokens, tuple):
        default_tokens = default_tokens[0]
    default_text = model.tokenizer.decode(default_tokens[0], skip_special_tokens=False)

    # Reset seed for steered generation
    if seed is not None:
        torch.manual_seed(seed)

    # Run steered generation
    if intervention_tuples:
        steered_result = model.feature_intervention_generate(
            prompt,
            intervention_tuples,
            freeze_attention=freeze_attention,
            do_sample=True,
            verbose=False,
            stop_at_eos=True,
            max_new_tokens=max_new_tokens + 1,  # +1 to match server behavior
            temperature=temperature,
            freq_penalty=freq_penalty,
            return_type="tokens",
        )
        steered_tokens, steered_logits, _ = steered_result
        if isinstance(steered_tokens, tuple):
            steered_tokens = steered_tokens[0]
        steered_text = model.tokenizer.decode(
            steered_tokens[0], skip_special_tokens=False
        )
    else:
        # No interventions - steered = default
        steered_text = default_text
        steered_logits = None

    # Get top-k logits for steered output
    steered_topk = []
    if steered_logits is not None:
        with torch.inference_mode():
            steered_topk = get_topk_logits(steered_logits, model.tokenizer, top_k)

    # Get top-k logits for default output
    default_topk = []
    with torch.inference_mode():
        default_logits = model(default_text)
        default_topk = get_topk_logits(default_logits, model.tokenizer, top_k)

    return {
        "steered": steered_text,
        "default": default_text,
        "steered_topk": steered_topk,
        "default_topk": default_topk,
        "intervention_count": len(intervention_tuples),
    }


# --------------------------------------------------------------------------------------
# Main entry point
# --------------------------------------------------------------------------------------


def main() -> None:
    args = parse_args()

    if not os.path.exists(args.prompts):
        raise FileNotFoundError(f"Prompts file not found: {args.prompts}")
    if not os.path.exists(args.features):
        raise FileNotFoundError(f"Features file not found: {args.features}")

    # Initialize model
    device = get_device(args.device)
    dtype = get_dtype(args.dtype)
    model = load_replacement_model(args.model_id, args.transcoder_set, device, dtype)

    # Load data
    prompts = load_prompts(args.prompts)
    global_features, per_prompt = load_ct_features(args.features)

    results = []
    for item in prompts:
        prompt_id = item["id"]
        text = item["text"]

        # Combine global and per-prompt features
        feats = list(global_features)
        feats.extend(per_prompt.get(prompt_id, []))

        print(f"Processing prompt '{prompt_id}' with {len(feats)} features...")

        raw = run_ct_generation(
            text,
            feats,
            model,
            seed=args.seed,
            temperature=args.temperature,
            freq_penalty=args.freq_penalty,
            max_new_tokens=args.n_tokens,
            freeze_attention=args.freeze_attention,
            top_k=args.top_k,
        )

        results.append(
            {
                "probe_id": prompt_id,
                "prompt": text,
                "steered": raw["steered"],
                "default": raw["default"],
                "steered_topk": raw["steered_topk"],
                "default_topk": raw["default_topk"],
                "intervention_count": raw["intervention_count"],
            }
        )

    payload = {
        "model": args.model_id,
        "transcoder_set": args.transcoder_set,
        "n_prompts": len(results),
        "results": results,
        "config": {
            "temperature": args.temperature,
            "n_tokens": args.n_tokens,
            "freq_penalty": args.freq_penalty,
            "seed": args.seed,
            "freeze_attention": args.freeze_attention,
            "top_k": args.top_k,
        },
    }

    os.makedirs(os.path.dirname(args.output) or ".", exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"[OK] CT Steering complete. Results saved to {args.output}")


if __name__ == "__main__":
    main()

