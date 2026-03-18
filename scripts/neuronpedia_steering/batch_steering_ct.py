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

# Trajectory tracking (fine-grained logit metrics)
TRACK_TRAJECTORY = os.environ.get("TRACK_TRAJECTORY", "false").lower() in ("1", "true", "yes")
TARGET_TOKEN = os.environ.get("TARGET_TOKEN", "")
SOURCE_TOKEN = os.environ.get("SOURCE_TOKEN", "")
CONTROL_TOKENS_RAW = os.environ.get("CONTROL_TOKENS", "")
CONTROL_TOKENS = [t.strip() for t in CONTROL_TOKENS_RAW.split(",") if t.strip()] if CONTROL_TOKENS_RAW else None


# --------------------------------------------------------------------------------------
# Data classes for parsed feature configs
# --------------------------------------------------------------------------------------


@dataclass
class CTInterventionFeature:
    """A single Circuit Tracer intervention specification.
    
    The intervention value is computed as: new_value = M * base_activation
    
    M values:
        M = 0.0  : Full ablation (zero out the feature)
        M = 1.0  : No change
        M = 2.0  : Double the activation (amplify)
        M = -1.0 : Reverse the direction
        M = -2.0 : Double and reverse
    
    Two modes of operation:
    
    1. MULTIPLICATION mode (use_stored_as_base=False, default):
       base_activation = live activation from get_activations() on current prompt
       Use for: Ablating/inhibiting features that ARE active on the current prompt
       Example: Reversing Texas features on a Dallas prompt
    
    2. INJECTION mode (use_stored_as_base=True):
       base_activation = stored_activation from graph.json
       Use for: Injecting features that are NOT active on the current prompt
       Example: Amplifying California features on a Dallas prompt
       Per Anthropic paper: "using activations significantly greater than typical"
    """
    layer: int
    index: int
    position: int  # Token position where the feature was originally active
    steer_position: Optional[int]  # Position to apply steering (None = same as position)
    M: float  # Multiplicative factor: new_value = M * base_activation
    steer_generated_tokens: bool = False  # If True, apply to all generated tokens
    stored_activation: Optional[float] = None  # Pre-computed activation from graph.json
    use_stored_as_base: bool = False  # If True, use stored_activation as base (injection mode)


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
        
        # Injection mode: use stored_activation as base instead of live activation
        use_stored_as_base = bool(item.get("use_stored_as_base", False))

        normalized.append(
            CTInterventionFeature(
                layer=layer,
                index=index,
                position=position,
                steer_position=steer_position,
                M=M,
                steer_generated_tokens=steer_generated_tokens,
                stored_activation=stored_activation,
                use_stored_as_base=use_stored_as_base,
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

    Supports two modes per feature:
    
    1. MULTIPLICATION mode (use_stored_as_base=False):
       base = live activation from get_activations() on current prompt
       new_value = M * live_activation
       Use for: Ablating features active on current prompt
    
    2. INJECTION mode (use_stored_as_base=True):
       base = stored_activation from graph.json  
       new_value = M * stored_activation
       Use for: Adding features NOT active on current prompt (cross-graph steering)

    Args:
        features: List of intervention specifications
        activations: Sparse tensor of shape [n_layers, n_pos, d_transcoder].
                     Can be None if all features use injection mode.
        sequence_length: Number of tokens in the prompt

    Returns:
        List of (layer, position, feature_idx, new_value) tuples
    """
    intervention_tuples = []
    n_injected = 0  # Features using stored_activation as base (injection mode)
    n_multiplied = 0  # Features using live activation as base (multiplication mode)
    n_fallback = 0  # Features using stored as fallback when live unavailable

    for feat in features:
        # Resolve negative positions
        token_pos = feat.position
        if token_pos < 0:
            token_pos = sequence_length + token_pos

        # Determine base activation value based on mode
        if feat.use_stored_as_base:
            # INJECTION mode: use stored_activation as base
            # For features not active on current prompt (e.g., California on Texas prompt)
            if feat.stored_activation is not None:
                original_value = feat.stored_activation
                n_injected += 1
            else:
                print(
                    f"Warning: use_stored_as_base=True but no stored_activation for "
                    f"layer={feat.layer}, index={feat.index}. Using 0.0"
                )
                original_value = 0.0
                n_injected += 1
        elif activations is not None:
            # MULTIPLICATION mode: use live activation from current prompt
            # For ablating features active on current prompt
            try:
                if activations.is_sparse:
                    dense_activations = activations.to_dense()
                else:
                    dense_activations = activations
                original_value = float(dense_activations[feat.layer, token_pos, feat.index])
                n_multiplied += 1
            except (IndexError, RuntimeError):
                print(
                    f"Warning: Could not get live activation for layer={feat.layer}, "
                    f"pos={token_pos}, index={feat.index}. Using 0.0"
                )
                original_value = 0.0
                n_multiplied += 1
        elif feat.stored_activation is not None:
            # Fallback: use stored if no live activations available
            original_value = feat.stored_activation
            n_fallback += 1
        else:
            print(
                f"Warning: No stored_activation and no activations tensor for "
                f"layer={feat.layer}, index={feat.index}. Using 0.0"
            )
            original_value = 0.0

        # Compute new value using M (multiplicative factor)
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

    # Report activation source breakdown
    parts = []
    if n_injected > 0:
        parts.append(f"{n_injected} injected (stored as base)")
    if n_multiplied > 0:
        parts.append(f"{n_multiplied} multiplied (live)")
    if n_fallback > 0:
        parts.append(f"{n_fallback} fallback (stored)")
    if parts:
        print(f"  [ACTIVATIONS] {' + '.join(parts)}")

    return intervention_tuples


def get_topk_logits(
    logits: torch.Tensor, tokenizer, k: int = 5, position: int = -1
) -> List[Dict[str, Any]]:
    """Get top-k token predictions from logits at a specific position.
    
    Args:
        logits: Model logits tensor [batch, seq_len, vocab_size] or [seq_len, vocab_size]
        tokenizer: Tokenizer for decoding tokens
        k: Number of top predictions to return
        position: Position in sequence to get predictions for (default: -1 = last)
    """
    squeezed = logits.squeeze()
    if squeezed.dim() == 1:
        probs = torch.softmax(squeezed, dim=-1)
    else:
        seq_len = squeezed.shape[0]
        if position >= seq_len:
            position = seq_len - 1
        probs = torch.softmax(squeezed[position], dim=-1)
    topk = torch.topk(probs, k)
    return [
        {
            "token": tokenizer.decode([topk.indices[i].item()]),
            "prob": float(topk.values[i].item()),
        }
        for i in range(k)
    ]


# =============================================================================
# Logit Trajectory Extraction (for fine-grained swap metrics)
# =============================================================================


def _resolve_token_id(tokenizer, token_str: str) -> Tuple[Optional[int], Optional[str]]:
    """
    Resolve a token string to its single-token ID.
    
    Returns:
        (token_id, resolved_token_str) or (None, None) if not found
    """
    variants = [
        f" {token_str}",  # With leading space (common)
        token_str,
        token_str.strip(),
        token_str.lower(),
        f" {token_str.lower()}",
    ]
    
    for variant in variants:
        try:
            encoded = tokenizer.encode(variant, add_special_tokens=False)
            if len(encoded) == 1:
                return encoded[0], variant
        except Exception:
            continue
    
    # Fallback: use first token of encoded sequence
    try:
        encoded = tokenizer.encode(f" {token_str}", add_special_tokens=False)
        if encoded:
            first_token = tokenizer.decode([encoded[0]])
            return encoded[0], first_token
    except Exception:
        pass
    
    return None, None


def _compute_rank(probs: torch.Tensor, token_id: int) -> int:
    """Compute rank of token (1 = highest probability)."""
    token_prob = probs[token_id]
    return int((probs > token_prob).sum().item()) + 1


def extract_logit_trajectory(
    logits: torch.Tensor,
    tokenizer,
    prompt_length: int,
    target_token: str,
    source_token: str,
    control_tokens: Optional[List[str]] = None,
    generated_token_ids: Optional[List[int]] = None,
) -> Dict[str, Any]:
    """
    Extract logit trajectory for target/source/control tokens from generation logits.
    
    This works with the logits tensor returned by feature_intervention_generate,
    which has shape [batch, prompt+generated, vocab_size].
    
    Positions:
        - logits[prompt_length-1] predicts first generated token
        - logits[prompt_length] predicts second generated token
        - etc.
    
    Args:
        logits: Logits tensor [batch, seq_len, vocab_size]
        tokenizer: Model tokenizer
        prompt_length: Number of tokens in the prompt
        target_token: Target token to track (e.g., "Atlanta")
        source_token: Source token to track (e.g., "Austin")
        control_tokens: Optional control tokens for specificity check
        generated_token_ids: List of actually generated token IDs (for tracking)
    
    Returns:
        Dict with trajectory data suitable for JSON serialization
    """
    if control_tokens is None:
        control_tokens = [" the", " is", " a", " of"]
    
    # Resolve token IDs
    target_id, target_resolved = _resolve_token_id(tokenizer, target_token)
    source_id, source_resolved = _resolve_token_id(tokenizer, source_token)
    control_ids: Dict[str, Tuple[int, str]] = {}
    for ctrl in control_tokens:
        tid, resolved = _resolve_token_id(tokenizer, ctrl)
        if tid is not None:
            control_ids[ctrl] = (tid, resolved)
    
    # Squeeze batch dimension
    logits_squeezed = logits.squeeze()
    if logits_squeezed.dim() == 1:
        # Single position - wrap in list
        logits_squeezed = logits_squeezed.unsqueeze(0)
    
    total_positions = logits_squeezed.shape[0]
    # Generation starts at position (prompt_length - 1) which predicts first new token
    first_gen_pos = prompt_length - 1
    n_gen_positions = total_positions - first_gen_pos
    
    # Initialize trajectory storage
    target_traj = {
        "token": target_resolved or target_token,
        "token_id": target_id,
        "positions": [],
        "logits": [],
        "probs": [],
        "ranks": [],
    }
    source_traj = {
        "token": source_resolved or source_token,
        "token_id": source_id,
        "positions": [],
        "logits": [],
        "probs": [],
        "ranks": [],
    }
    control_trajs = {
        ctrl: {
            "token": resolved,
            "token_id": tid,
            "positions": [],
            "logits": [],
            "probs": [],
            "ranks": [],
        }
        for ctrl, (tid, resolved) in control_ids.items()
    }
    
    # Extract trajectory at each generation position
    with torch.inference_mode():
        for step in range(n_gen_positions):
            pos = first_gen_pos + step
            if pos >= total_positions:
                break
            
            pos_logits = logits_squeezed[pos]
            probs = torch.softmax(pos_logits, dim=-1)
            
            # Target
            if target_id is not None:
                target_traj["positions"].append(step)
                target_traj["logits"].append(round(pos_logits[target_id].item(), 4))
                target_traj["probs"].append(round(probs[target_id].item(), 6))
                target_traj["ranks"].append(_compute_rank(probs, target_id))
            
            # Source
            if source_id is not None:
                source_traj["positions"].append(step)
                source_traj["logits"].append(round(pos_logits[source_id].item(), 4))
                source_traj["probs"].append(round(probs[source_id].item(), 6))
                source_traj["ranks"].append(_compute_rank(probs, source_id))
            
            # Controls
            for ctrl, traj in control_trajs.items():
                tid = traj["token_id"]
                if tid is not None:
                    traj["positions"].append(step)
                    traj["logits"].append(round(pos_logits[tid].item(), 4))
                    traj["probs"].append(round(probs[tid].item(), 6))
                    traj["ranks"].append(_compute_rank(probs, tid))
    
    # Compute summary metrics
    def first_below_threshold(ranks: List[int], threshold: int) -> Optional[int]:
        for i, r in enumerate(ranks):
            if r <= threshold:
                return i
        return None
    
    target_summary = {}
    if target_traj["ranks"]:
        target_summary = {
            "first_top1_position": first_below_threshold(target_traj["ranks"], 1),
            "first_top5_position": first_below_threshold(target_traj["ranks"], 5),
            "first_top10_position": first_below_threshold(target_traj["ranks"], 10),
            "max_prob": max(target_traj["probs"]) if target_traj["probs"] else None,
            "min_rank": min(target_traj["ranks"]) if target_traj["ranks"] else None,
            "final_rank": target_traj["ranks"][-1] if target_traj["ranks"] else None,
            "rank_improvement": target_traj["ranks"][0] - min(target_traj["ranks"]) if target_traj["ranks"] else 0,
        }
    
    source_summary = {}
    if source_traj["ranks"]:
        source_summary = {
            "first_top1_position": first_below_threshold(source_traj["ranks"], 1),
            "min_rank": min(source_traj["ranks"]) if source_traj["ranks"] else None,
            "final_rank": source_traj["ranks"][-1] if source_traj["ranks"] else None,
            "max_prob": max(source_traj["probs"]) if source_traj["probs"] else None,
        }
    
    # Compute gap trajectory
    gap_trajectory = []
    if target_traj["logits"] and source_traj["logits"]:
        for i in range(min(len(target_traj["logits"]), len(source_traj["logits"]))):
            gap = target_traj["logits"][i] - source_traj["logits"][i]
            gap_trajectory.append(round(gap, 4))
    
    # Determine flip position
    flip_position = None
    if target_traj["ranks"] and source_traj["ranks"]:
        for i in range(min(len(target_traj["ranks"]), len(source_traj["ranks"]))):
            if target_traj["ranks"][i] < source_traj["ranks"][i]:
                flip_position = i
                break
    
    # Find where target/source were actually generated
    target_appears_at = None
    source_appears_at = None
    if generated_token_ids:
        for i, tid in enumerate(generated_token_ids):
            if target_id is not None and tid == target_id and target_appears_at is None:
                target_appears_at = i
            if source_id is not None and tid == source_id and source_appears_at is None:
                source_appears_at = i
    
    # Control stability (mean absolute logit change from position 0)
    control_stability_mean = None
    control_stability_max = None
    if control_trajs:
        deltas = []
        max_delta = 0.0
        for traj in control_trajs.values():
            if len(traj["logits"]) >= 2:
                for logit in traj["logits"][1:]:
                    delta = abs(logit - traj["logits"][0])
                    deltas.append(delta)
                    max_delta = max(max_delta, delta)
        if deltas:
            control_stability_mean = round(sum(deltas) / len(deltas), 4)
            control_stability_max = round(max_delta, 4)
    
    # Decode generated tokens
    generated_tokens = []
    if generated_token_ids:
        generated_tokens = [tokenizer.decode([tid]) for tid in generated_token_ids]
    
    return {
        "tokens": {
            "target": target_resolved or target_token,
            "source": source_resolved or source_token,
            "controls": list(control_ids.keys()),
        },
        "n_positions": n_gen_positions,
        "generated_tokens": generated_tokens,
        "trajectories": {
            "target": {
                "token": target_traj["token"],
                "token_id": target_traj["token_id"],
                "trajectory": {
                    "positions": target_traj["positions"],
                    "logits": target_traj["logits"],
                    "probs": target_traj["probs"],
                    "ranks": target_traj["ranks"],
                },
                "summary": target_summary,
            } if target_id else None,
            "source": {
                "token": source_traj["token"],
                "token_id": source_traj["token_id"],
                "trajectory": {
                    "positions": source_traj["positions"],
                    "logits": source_traj["logits"],
                    "probs": source_traj["probs"],
                    "ranks": source_traj["ranks"],
                },
                "summary": source_summary,
            } if source_id else None,
            "controls": {
                ctrl: {
                    "token": traj["token"],
                    "token_id": traj["token_id"],
                    "trajectory": {
                        "positions": traj["positions"],
                        "logits": traj["logits"],
                        "probs": traj["probs"],
                        "ranks": traj["ranks"],
                    },
                }
                for ctrl, traj in control_trajs.items()
            },
        },
        "summary": {
            "target_appears_at": target_appears_at,
            "source_appears_at": source_appears_at,
            "flip_position": flip_position,
            "initial_gap": gap_trajectory[0] if gap_trajectory else None,
            "best_gap": max(gap_trajectory) if gap_trajectory else None,
            "final_gap": gap_trajectory[-1] if gap_trajectory else None,
            "gap_closure": (max(gap_trajectory) - gap_trajectory[0]) if gap_trajectory else None,
            "gap_trajectory": gap_trajectory,
            "control_stability_mean": control_stability_mean,
            "control_stability_max": control_stability_max,
        },
    }


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
    # Trajectory tracking (optional)
    track_trajectory: bool = False,
    target_token: Optional[str] = None,
    source_token: Optional[str] = None,
    control_tokens: Optional[List[str]] = None,
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
        track_trajectory: If True, extract full logit trajectory for target/source
        target_token: Token to track as target (e.g., target capital)
        source_token: Token to track as source (e.g., source capital)
        control_tokens: Tokens to track for specificity check

    Returns:
        Dict with steered/default outputs, logprobs, and optionally trajectory
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

    # Get baseline logits FIRST (before any generation pollutes state)
    # This gives us the model's prediction for the first token after the prompt
    with torch.inference_mode():
        baseline_logits = model(prompt)
    
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

    # Detect logits tensor format from circuit_tracer library.
    # New versions return [1 + gen_steps, vocab] (only last prompt position + generation).
    # Old versions returned [prompt_len + gen_steps, vocab] (full prompt included).
    # We detect by comparing the tensor size with the expected size for each format.
    effective_prompt_in_logits = sequence_length  # default: assume full prompt
    if steered_logits is not None:
        steered_ids_for_detect = model.tokenizer.encode(steered_text, add_special_tokens=False)
        approx_gen_count = max(len(steered_ids_for_detect) - sequence_length, 1)
        total_logit_positions = steered_logits.squeeze().shape[0]
        expected_compact = 1 + approx_gen_count
        expected_full = sequence_length + approx_gen_count
        if abs(total_logit_positions - expected_compact) < abs(total_logit_positions - expected_full):
            effective_prompt_in_logits = 1

    # Get top-k logits for FIRST generated token
    steered_topk = []
    if steered_logits is not None:
        with torch.inference_mode():
            first_gen_position = effective_prompt_in_logits - 1
            steered_topk = get_topk_logits(steered_logits, model.tokenizer, top_k, position=first_gen_position)

    # For default: use baseline logits captured BEFORE generation
    default_topk = []
    with torch.inference_mode():
        default_topk = get_topk_logits(baseline_logits, model.tokenizer, top_k, position=-1)

    result = {
        "steered": steered_text,
        "default": default_text,
        "steered_topk": steered_topk,
        "default_topk": default_topk,
        "intervention_count": len(intervention_tuples),
    }
    
    # Extract logit trajectory if requested
    if track_trajectory and steered_logits is not None and target_token and source_token:
        # Get generated token IDs from the steered output
        steered_token_ids = model.tokenizer.encode(steered_text, add_special_tokens=False)
        # Skip prompt tokens to get just generated tokens
        generated_token_ids = steered_token_ids[sequence_length:] if len(steered_token_ids) > sequence_length else []
        
        result["logit_trajectory"] = extract_logit_trajectory(
            logits=steered_logits,
            tokenizer=model.tokenizer,
            prompt_length=effective_prompt_in_logits,
            target_token=target_token,
            source_token=source_token,
            control_tokens=control_tokens,
            generated_token_ids=generated_token_ids,
        )
        
        # Also extract baseline trajectory for comparison (single position)
        if baseline_logits is not None:
            baseline_probs = torch.softmax(baseline_logits.squeeze()[-1], dim=-1)
            target_id, _ = _resolve_token_id(model.tokenizer, target_token)
            source_id, _ = _resolve_token_id(model.tokenizer, source_token)
            
            baseline_target_info = None
            baseline_source_info = None
            
            if target_id is not None:
                baseline_target_info = {
                    "logit": round(baseline_logits.squeeze()[-1][target_id].item(), 4),
                    "prob": round(baseline_probs[target_id].item(), 6),
                    "rank": _compute_rank(baseline_probs, target_id),
                }
            
            if source_id is not None:
                baseline_source_info = {
                    "logit": round(baseline_logits.squeeze()[-1][source_id].item(), 4),
                    "prob": round(baseline_probs[source_id].item(), 6),
                    "rank": _compute_rank(baseline_probs, source_id),
                }
            
            result["baseline_logits"] = {
                "target": baseline_target_info,
                "source": baseline_source_info,
            }
            
            # Compute baseline vs steered comparison (at position 0)
            if result.get("logit_trajectory") and baseline_target_info and baseline_source_info:
                traj = result["logit_trajectory"]
                steered_target = traj["trajectories"]["target"]
                steered_source = traj["trajectories"]["source"]
                
                if steered_target and steered_source:
                    steered_target_logit_0 = steered_target["trajectory"]["logits"][0] if steered_target["trajectory"]["logits"] else None
                    steered_source_logit_0 = steered_source["trajectory"]["logits"][0] if steered_source["trajectory"]["logits"] else None
                    steered_target_rank_0 = steered_target["trajectory"]["ranks"][0] if steered_target["trajectory"]["ranks"] else None
                    steered_source_rank_0 = steered_source["trajectory"]["ranks"][0] if steered_source["trajectory"]["ranks"] else None
                    
                    result["position_0_comparison"] = {
                        "target_logit_delta": round(steered_target_logit_0 - baseline_target_info["logit"], 4) if steered_target_logit_0 else None,
                        "source_logit_delta": round(steered_source_logit_0 - baseline_source_info["logit"], 4) if steered_source_logit_0 else None,
                        "baseline_gap": round(baseline_target_info["logit"] - baseline_source_info["logit"], 4),
                        "steered_gap_0": round(steered_target_logit_0 - steered_source_logit_0, 4) if (steered_target_logit_0 and steered_source_logit_0) else None,
                        "gap_closure_0": round((steered_target_logit_0 - steered_source_logit_0) - (baseline_target_info["logit"] - baseline_source_info["logit"]), 4) if (steered_target_logit_0 and steered_source_logit_0) else None,
                        "target_rank_improvement": baseline_target_info["rank"] - steered_target_rank_0 if steered_target_rank_0 else None,
                        "flip_at_0": steered_target_rank_0 < steered_source_rank_0 if (steered_target_rank_0 and steered_source_rank_0) else False,
                    }
    
    return result


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

    # Check for trajectory tracking from env vars
    track_trajectory = TRACK_TRAJECTORY
    target_token = TARGET_TOKEN or None
    source_token = SOURCE_TOKEN or None
    control_tokens = CONTROL_TOKENS or None
    
    if track_trajectory:
        print(f"[TRAJECTORY] Tracking enabled")
        if target_token:
            print(f"  Target token: {target_token}")
        if source_token:
            print(f"  Source token: {source_token}")
        if control_tokens:
            print(f"  Control tokens: {control_tokens}")

    results = []
    for item in prompts:
        prompt_id = item["id"]
        text = item["text"]

        # Per-prompt tokens override global env vars
        item_target = item.get("target_token", target_token)
        item_source = item.get("source_token", source_token)

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
            track_trajectory=track_trajectory,
            target_token=item_target,
            source_token=item_source,
            control_tokens=control_tokens,
        )

        result_entry = {
                "probe_id": prompt_id,
                "prompt": text,
                "steered": raw["steered"],
                "default": raw["default"],
                "steered_topk": raw["steered_topk"],
                "default_topk": raw["default_topk"],
                "intervention_count": raw["intervention_count"],
            }
        
        # Include trajectory data if present
        if "logit_trajectory" in raw:
            result_entry["logit_trajectory"] = raw["logit_trajectory"]
        if "baseline_logits" in raw:
            result_entry["baseline_logits"] = raw["baseline_logits"]
        if "position_0_comparison" in raw:
            result_entry["position_0_comparison"] = raw["position_0_comparison"]
        
        results.append(result_entry)

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

