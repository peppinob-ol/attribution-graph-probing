#!/usr/bin/env python3
"""
Batch steering utility for CLT/SAE features using the local Neuronpedia inference stack.

This mirrors the structure of `scripts/neuronpedia_activations/batch_get_activations.py`,
but calls the steering endpoint logic (`run_batched_generate`) directly so we can use
SAE dictionaries such as `clt-hp` that are not exposed via the public API.

Inputs (via env vars or CLI):
  - PROMPTS_JSON_PATH: file with prompts (list of strings or [{"id","text"}, ...])
  - FEATURES_JSON_PATH: file describing steering features:
        [
          {"source": "0-clt-hp", "index": 123, "strength": 5.0},
          {"layer": 7, "index": 456, "strength": -3.0},
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
      "steered_logprobs": [...],
      "default_logprobs": [...]
    }

This script is intended to run on the remote GPU node (same as the activations batch)
and therefore clones the Neuronpedia repo, loads the requested SAE set, and executes
steering for all prompts in one shot.
"""

from __future__ import annotations

import argparse
import asyncio
import gc
import json
import os
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Tuple

import torch

# Allow importing helper utilities (load_prompts) from neuronpedia_activations
ROOT_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT_DIR not in sys.path:
    sys.path.append(ROOT_DIR)
from neuronpedia_activations.helpers import load_prompts  # type: ignore


# --------------------------------------------------------------------------------------
# Configuration defaults (overridable via env / CLI)
# --------------------------------------------------------------------------------------

MODEL_ID = os.environ.get("MODEL_ID", "gemma-2-2b")
SOURCE_SET = os.environ.get("SOURCE_SET", "clt-hp")
PROMPTS_JSON_PATH = os.environ.get("PROMPTS_JSON_PATH", "/content/prompts.json")
FEATURES_JSON_PATH = os.environ.get("FEATURES_JSON_PATH", "/content/features.json")
OUT_JSON_PATH = os.environ.get("OUT_JSON_PATH", "/content/steering_dump.json")

TEMPERATURE = float(os.environ.get("STEER_TEMPERATURE", "0.5"))
N_TOKENS = int(os.environ.get("STEER_N_TOKENS", "16"))
FREQ_PENALTY = float(os.environ.get("STEER_FREQ_PENALTY", "2.0"))
SEED = int(os.environ.get("STEER_SEED", "42"))
STRENGTH_MULTIPLIER = float(os.environ.get("STEER_STRENGTH_MULTIPLIER", "1.0"))
STEER_METHOD = os.environ.get("STEER_METHOD", "ORTHOGONAL_DECOMP")
N_LOGPROBS = int(os.environ.get("STEER_N_LOGPROBS", "5"))
NORMALIZE_STEERING = (
    os.environ.get("STEER_NORMALIZE", "false").lower() in ("1", "true", "yes")
)

NP_REPO_URL = os.environ.get(
    "NP_REPO_URL", "https://github.com/hijohnnylin/neuronpedia.git"
)
NP_WORKDIR = os.environ.get("NP_WORKDIR", "/content")
PERSIST_SAE_CACHE = (
    os.environ.get("PERSIST_SAE_CACHE", "false").lower() in ("1", "true", "yes")
)


# --------------------------------------------------------------------------------------
# Data classes for parsed feature configs
# --------------------------------------------------------------------------------------


@dataclass
class SteeringFeature:
    source: str
    index: int
    strength: float = 1.0


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch Neuronpedia steering utility.")
    parser.add_argument("--prompts", default=PROMPTS_JSON_PATH, help="prompts.json path")
    parser.add_argument(
        "--features", default=FEATURES_JSON_PATH, help="features.json path"
    )
    parser.add_argument("--output", default=OUT_JSON_PATH, help="Output JSON path")

    parser.add_argument("--model-id", default=MODEL_ID)
    parser.add_argument("--source-set", default=SOURCE_SET)
    parser.add_argument("--temperature", type=float, default=TEMPERATURE)
    parser.add_argument("--n-tokens", type=int, default=N_TOKENS)
    parser.add_argument("--freq-penalty", type=float, default=FREQ_PENALTY)
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument(
        "--strength-multiplier", type=float, default=STRENGTH_MULTIPLIER
    )
    parser.add_argument("--steer-method", default=STEER_METHOD)
    parser.add_argument("--n-logprobs", type=int, default=N_LOGPROBS)
    parser.add_argument(
        "--normalize-steering",
        action="store_true",
        default=NORMALIZE_STEERING,
        help="Enable normalization of steering vectors",
    )
    parser.add_argument(
        "--np-repo-url", default=NP_REPO_URL, help="Neuronpedia git repo URL"
    )
    parser.add_argument(
        "--np-workdir", default=NP_WORKDIR, help="Where to clone/load the repo"
    )
    parser.add_argument(
        "--persist-sae-cache",
        action="store_true",
        default=PERSIST_SAE_CACHE,
        help="Skip cleaning SAE cache between layers",
    )
    return parser.parse_args()


# --------------------------------------------------------------------------------------
# Feature loading / normalization
# --------------------------------------------------------------------------------------


def load_steering_features(
    path: str, source_set: str
) -> Tuple[List[SteeringFeature], Dict[str, List[SteeringFeature]]]:
    """
    Load steering features from JSON. Supports:
      - simple list: [{"source": "...", "index": 0, "strength": 1.5}, ...]
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

    global_features = _normalize_feature_list(global_list, source_set)
    per_prompt = {
        prompt_id: _normalize_feature_list(items, source_set)
        for prompt_id, items in per_prompt_raw.items()
    }
    return global_features, per_prompt


def _normalize_feature_list(
    items: List[Dict[str, Any]], source_set: str
) -> List[SteeringFeature]:
    normalized: List[SteeringFeature] = []
    for i, item in enumerate(items):
        if not isinstance(item, dict):
            raise ValueError(f"feature #{i}: expected object, got {type(item)}")

        strength = float(item.get("strength", 1.0))
        if "source" in item and "index" in item:
            source = str(item["source"])
            idx = int(item["index"])
            if "-" not in source:
                raise ValueError(
                    f"feature #{i}: expected 'source' to include layer-prefix (e.g. '0-{source_set}')"
                )
            suffix = source.split("-", 1)[1]
            if suffix != source_set:
                raise ValueError(
                    f"feature #{i}: source_set '{suffix}' != expected '{source_set}'"
                )
            normalized.append(SteeringFeature(source=source, index=idx, strength=strength))
        elif "layer" in item and "index" in item:
            layer = int(item["layer"])
            idx = int(item["index"])
            normalized.append(
                SteeringFeature(
                    source=f"{layer}-{source_set}", index=idx, strength=strength
                )
            )
        else:
            raise ValueError(
                f"feature #{i}: expected either ('source','index') or ('layer','index')"
            )
    return normalized


# --------------------------------------------------------------------------------------
# Repo + model initialization helpers
# --------------------------------------------------------------------------------------


def ensure_repo(np_repo_url: str, np_workdir: str) -> str:
    repo_dir = os.path.join(np_workdir, "neuronpedia")
    if not os.path.exists(repo_dir):
        os.makedirs(np_workdir, exist_ok=True)
        subprocess.run(["git", "clone", "-q", np_repo_url, repo_dir], check=True)
    return repo_dir


def setup_sys_path(repo_dir: str) -> None:
    inference_path = os.path.join(repo_dir, "apps", "inference")
    client_path = os.path.join(repo_dir, "packages", "python", "neuronpedia-inference-client")
    if inference_path not in sys.path:
        sys.path.append(inference_path)
    if client_path not in sys.path:
        sys.path.append(client_path)


def initialize_inference_stack(
    model_id: str,
    source_set: str,
    *,
    persist_sae_cache: bool = False,
) -> None:
    """
    Configure Config/Model/SAEManager singletons exactly as the Neuronpedia inference server does.
    """
    from neuronpedia_inference.config import Config  # type: ignore
    from neuronpedia_inference.shared import Model  # type: ignore
    from neuronpedia_inference.sae_manager import SAEManager  # type: ignore
    from neuronpedia_inference.shared import STR_TO_DTYPE  # type: ignore

    # Model + SAE dtype setup (mirrors batch_get_activations)
    device_override = os.environ.get("STEER_DEVICE")
    if device_override in ("cpu", "cuda"):
        device_guess = device_override
    else:
        device_guess = "cuda" if torch.cuda.is_available() else "cpu"
    os.environ.setdefault("MODEL_ID", model_id)
    os.environ.setdefault("SAE_SETS", json.dumps([source_set]))
    os.environ.setdefault("DEVICE", device_guess)
    os.environ.setdefault("TOKEN_LIMIT", "4096")
    os.environ.setdefault("MODEL_DTYPE", "bfloat16" if device_guess == "cuda" else "float32")
    os.environ.setdefault("SAE_DTYPE", "float32")

    Config._instance = None  # type: ignore[attr-defined]
    cfg = Config.__new__(Config)  # type: ignore
    cfg.__init__(
        model_id=model_id,
        sae_sets=[source_set],
        device=device_guess,
        model_dtype=os.environ["MODEL_DTYPE"],
        sae_dtype=os.environ["SAE_DTYPE"],
        token_limit=int(os.environ["TOKEN_LIMIT"]),
    )
    Config._instance = cfg

    # Load model
    try:
        from transformer_lens import HookedSAETransformer  # type: ignore

        model = HookedSAETransformer.from_pretrained(
            model_id,
            device=cfg.device,
            dtype=STR_TO_DTYPE[cfg.model_dtype],
            **cfg.model_kwargs,
        )
    except ImportError:
        from transformer_lens import HookedTransformer  # type: ignore

        model = HookedTransformer.from_pretrained(
            model_id,
            device=cfg.device,
            dtype=STR_TO_DTYPE[cfg.model_dtype],
            **cfg.model_kwargs,
        )
    Model.set_instance(model)

    # SAE Manager
    SAEManager._instance = None  # type: ignore[attr-defined]
    sae_mgr = SAEManager.__new__(SAEManager)  # type: ignore
    sae_mgr.__init__(num_layers=model.cfg.n_layers, device=cfg.device)
    SAEManager._instance = sae_mgr

    if persist_sae_cache:
        sae_mgr.load_saes()
    else:
        sae_mgr.load_saes()
        # Immediately unload to allow on-demand loading while keeping metadata
        for key in list(sae_mgr.loaded_saes.keys()):
            sae_mgr.unload_sae(key)


# --------------------------------------------------------------------------------------
# Steering execution
# --------------------------------------------------------------------------------------


def build_np_features(
    features: List[SteeringFeature], model_id: str
):
    from neuronpedia_inference_client.models.np_steer_feature import NPSteerFeature  # type: ignore

    return [
        NPSteerFeature(
            model=model_id,
            source=feat.source,
            index=int(feat.index),
            strength=float(feat.strength),
        )
        for feat in features
    ]


def run_generation(
    prompt: str,
    features,
    *,
    strength_multiplier: float,
    seed: int,
    temperature: float,
    freq_penalty: float,
    max_new_tokens: int,
    steer_method: str,
    normalize_steering: bool,
    n_logprobs: int,
):
    """
    Local steering runner that mirrors the Neuronpedia /steer/completion endpoint
    but uses HookedTransformer.generate instead of generate_stream.

    This avoids relying on generate_stream (which is unavailable in older
    transformer_lens versions) while keeping the steering math identical: we use
    the same steering_hook logic, OrthogonalProjector, and SAE hooks.
    """
    from neuronpedia_inference_client.models.np_steer_feature import (  # type: ignore
        NPSteerFeature,
    )
    from neuronpedia_inference_client.models.np_steer_method import (  # type: ignore
        NPSteerMethod,
    )
    from neuronpedia_inference_client.models.np_steer_type import NPSteerType  # type: ignore
    from neuronpedia_inference.config import Config  # type: ignore
    from neuronpedia_inference.inference_utils.steering import (  # type: ignore
        OrthogonalProjector,
    )
    from neuronpedia_inference.sae_manager import SAEManager  # type: ignore
    from neuronpedia_inference.shared import Model  # type: ignore

    steer_method_enum = NPSteerMethod(steer_method)
    steer_types = [NPSteerType.STEERED, NPSteerType.DEFAULT]

    model = Model.get_instance()
    sae_manager = SAEManager.get_instance()
    _ = Config.get_instance()  # currently unused, kept for parity/logging if needed

    if seed is not None:
        torch.manual_seed(seed)

    tokenized = model.to_tokens(
        prompt, prepend_bos=model.cfg.tokenizer_prepends_bos, truncate=False
    )[0]

    def steering_hook(activations: torch.Tensor, hook: Any) -> torch.Tensor:  # type: ignore[unused-argument]
        for i, flag in enumerate(steer_types):
            if flag == NPSteerType.STEERED:
                for feature in features:
                    steering_vector = torch.tensor(feature.steering_vector).to(
                        activations.device
                    )

                    if not torch.isfinite(steering_vector).all():
                        raise ValueError("Steering vector contains inf or nan values")

                    if normalize_steering:
                        norm = torch.norm(steering_vector)
                        if norm == 0:
                            raise ValueError("Zero norm steering vector")
                        steering_vector = steering_vector / norm

                    # If it's attention hook, reshape it to (n_heads, head_dim)
                    if isinstance(
                        feature, NPSteerFeature
                    ) and "attn.hook_z" in sae_manager.get_sae_hook(feature.source):
                        n_heads = model.cfg.n_heads
                        d_head = model.cfg.d_head
                        steering_vector = steering_vector.view(n_heads, d_head)

                    coeff = strength_multiplier * feature.strength

                    if steer_method_enum == NPSteerMethod.SIMPLE_ADDITIVE:
                        activations[i] += coeff * steering_vector
                    elif steer_method_enum == NPSteerMethod.ORTHOGONAL_DECOMP:
                        projector = OrthogonalProjector(steering_vector)
                        activations[i] = projector.project(activations[i], coeff)
        return activations

    generate_both = (
        NPSteerType.STEERED in steer_types and NPSteerType.DEFAULT in steer_types
    )

    outputs = []

    # Helper to run one generation (steered or default)
    def _run_single_generation(apply_steering: bool) -> str:
        if seed is not None:
            torch.manual_seed(seed)

        model.reset_hooks()
        if apply_steering:
            editing_hooks = [
                (
                    (
                        sae_manager.get_sae_hook(feature.source)
                        if isinstance(feature, NPSteerFeature)
                        else feature.hook
                    ),
                    steering_hook,
                )
                for feature in features
            ]
        else:
            editing_hooks = []

        with model.hooks(fwd_hooks=editing_hooks):  # type: ignore[arg-type]
            tokens = model.generate(
                input=tokenized.unsqueeze(0),
                max_new_tokens=max_new_tokens,
                stop_at_eos=(model.cfg.device != "mps"),
                do_sample=True,
                temperature=temperature,
                freq_penalty=freq_penalty,
                return_type="tokens",
            )

        # tokens includes the prompt; strip it off (same behavior as completion.py)
        return model.to_string(tokens[0][1:])

    if generate_both:
        steered_text = _run_single_generation(apply_steering=True)
        default_text = _run_single_generation(apply_steering=False)

        outputs.append(
            {
                "type": NPSteerType.STEERED.value,
                "output": steered_text,
                "logprobs": None if n_logprobs <= 0 else None,
            }
        )
        outputs.append(
            {
                "type": NPSteerType.DEFAULT.value,
                "output": default_text,
                "logprobs": None if n_logprobs <= 0 else None,
            }
        )
    else:
        # Only one of STEERED / DEFAULT requested; mirror completion.py semantics.
        apply_steering = steer_types[0] == NPSteerType.STEERED
        text = _run_single_generation(apply_steering=apply_steering)
        outputs.append(
            {
                "type": steer_types[0].value,
                "output": text,
                "logprobs": None if n_logprobs <= 0 else None,
            }
        )

    return {"outputs": outputs}


def summarize_outputs(raw_outputs: Dict[str, Any]) -> Dict[str, Any]:
    from neuronpedia_inference_client.models.np_steer_type import NPSteerType  # type: ignore

    outputs = raw_outputs.get("outputs", [])
    data = {}
    for item in outputs:
        item_type = item.get("type")
        text = item.get("output", "")
        logprobs = item.get("logprobs")
        data[item_type] = {"text": text, "logprobs": logprobs}

    return {
        "steered": data.get(NPSteerType.STEERED.value, {}).get("text", ""),
        "steered_logprobs": data.get(NPSteerType.STEERED.value, {}).get("logprobs"),
        "default": data.get(NPSteerType.DEFAULT.value, {}).get("text", ""),
        "default_logprobs": data.get(NPSteerType.DEFAULT.value, {}).get("logprobs"),
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

    repo_dir = ensure_repo(args.np_repo_url, args.np_workdir)
    setup_sys_path(repo_dir)
    initialize_inference_stack(
        args.model_id, args.source_set, persist_sae_cache=args.persist_sae_cache
    )

    prompts = load_prompts(args.prompts)
    global_features, per_prompt = load_steering_features(args.features, args.source_set)

    from neuronpedia_inference.inference_utils.steering import (  # type: ignore
        process_features_vectorized,
    )

    results = []
    for item in prompts:
        prompt_id = item["id"]
        text = item["text"]
        feats = list(global_features)
        feats.extend(per_prompt.get(prompt_id, []))
        np_features = build_np_features(feats, args.model_id)
        if np_features:
            process_features_vectorized(np_features)

        raw = run_generation(
            text,
            np_features,
            strength_multiplier=args.strength_multiplier,
            seed=args.seed,
            temperature=args.temperature,
            freq_penalty=args.freq_penalty,
            max_new_tokens=args.n_tokens,
            steer_method=args.steer_method,
            normalize_steering=args.normalize_steering,
            n_logprobs=args.n_logprobs,
        )
        summary = summarize_outputs(raw)
        results.append(
            {
                "probe_id": prompt_id,
                "prompt": text,
                **summary,
            }
        )

    payload = {
        "model": args.model_id,
        "source_set": args.source_set,
        "n_prompts": len(results),
        "results": results,
        "config": {
            "temperature": args.temperature,
            "n_tokens": args.n_tokens,
            "freq_penalty": args.freq_penalty,
            "seed": args.seed,
            "strength_multiplier": args.strength_multiplier,
            "steer_method": args.steer_method,
            "n_logprobs": args.n_logprobs,
            "normalize_steering": args.normalize_steering,
        },
    }

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)
    print(f"✓ Steering complete. Results saved to {args.output}")


if __name__ == "__main__":
    main()


