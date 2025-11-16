#!/usr/bin/env python3
"""
Remote batch runner executed on GPU node.
Processes multiple seeds in a single activation sweep, downloading each SAE layer once.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import time
import traceback
from pathlib import Path
from typing import Any, Dict, List, Tuple

import torch
import gc

# ---------------------------------------------------------------------------
# Locate helpers (scripts/neuronpedia_activations/helpers.py)
# ---------------------------------------------------------------------------
PIPELINE_DIR = Path(__file__).resolve().parent
SCRIPTS_DIR = PIPELINE_DIR.parents[2]  # .../scripts
NEURONPEDIA_DIR = SCRIPTS_DIR / "neuronpedia_activations"
if str(NEURONPEDIA_DIR) not in sys.path:
    sys.path.insert(0, str(NEURONPEDIA_DIR))

from helpers import load_prompts, load_features  # type: ignore


def ensure_neuronpedia_repo() -> Path:
    """Clone neuronpedia repo if needed and return repo dir."""
    repo_url = "https://github.com/hijohnnylin/neuronpedia.git"
    repo_base = os.environ.get("NP_WORKDIR", "/content")
    repo_dir = Path(repo_base) / "neuronpedia"
    if not repo_dir.exists():
        import subprocess
        repo_dir.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["git", "clone", "-q", repo_url, str(repo_dir)], check=True)
    sys.path.append(str(repo_dir / "apps" / "inference"))
    sys.path.append(str(repo_dir / "packages" / "python" / "neuronpedia-inference-client"))
    return repo_dir


def cleanup_hf_cache(persist_cache: bool):
    """Optionally clean SAE cache to free space."""
    hf_home = os.environ.get("HF_HOME", os.path.expanduser("~/.cache/huggingface"))
    hf_cache_dir = Path(hf_home) / "hub"
    if persist_cache:
        print("PERSIST_SAE_CACHE=true → keeping existing SAE cache on disk")
        return
    if not hf_cache_dir.exists():
        return

    print("Pulizia cache Hugging Face (spazio disco)...")

    def get_dir_size(path: Path) -> float:
        total = 0
        for entry in os.scandir(path):
            entry_path = Path(entry.path)
            try:
                if entry.is_file(follow_symlinks=False):
                    total += entry_path.stat().st_size
                elif entry.is_dir(follow_symlinks=False):
                    total += get_dir_size(entry_path)
            except (PermissionError, FileNotFoundError):
                continue
        return total

    cache_size_gb = get_dir_size(hf_cache_dir) / 1024**3
    print(f"  Cache HF attuale: {cache_size_gb:.2f} GB")

    cleaned = 0.0
    for item in hf_cache_dir.iterdir():
        if "mntss--clt-" in item.name and item.is_dir():
            size_gb = get_dir_size(item) / 1024**3
            print(f"  Rimuovo cache SAE: {item.name} ({size_gb:.2f} GB)")
            shutil.rmtree(item, ignore_errors=True)
            cleaned += size_gb

    if cleaned > 0:
        print(f"  ✓ Liberati {cleaned:.2f} GB di spazio disco")
    else:
        print("  Cache SAE già pulita")


def setup_environment(model_id: str, source_set: str, chunk_by_layer: bool):
    """Initialize Config, TransformerLens model, and SAEManager."""
    ensure_neuronpedia_repo()

    from neuronpedia_inference.config import Config  # type: ignore
    from neuronpedia_inference.shared import Model  # type: ignore
    from neuronpedia_inference.sae_manager import SAEManager  # type: ignore
    from neuronpedia_inference.shared import STR_TO_DTYPE  # type: ignore
    from transformer_lens import HookedTransformer  # type: ignore
    try:
        from transformer_lens import HookedSAETransformer  # type: ignore
        use_sae_transformer = True
    except ImportError:
        HookedSAETransformer = None  # type: ignore
        use_sae_transformer = False

    device_guess = "cuda" if torch.cuda.is_available() else "cpu"
    os.environ.setdefault("MODEL_ID", model_id)
    os.environ.setdefault("SAE_SETS", json.dumps([source_set]))
    os.environ.setdefault("DEVICE", device_guess)
    os.environ.setdefault("TOKEN_LIMIT", "4096")
    os.environ.setdefault("MODEL_DTYPE", "bfloat16" if device_guess == "cuda" else "float32")
    os.environ.setdefault("SAE_DTYPE", "float32")

    Config._instance = None
    cfg = Config.__new__(Config)
    cfg.__init__(
        model_id=model_id,
        sae_sets=[source_set],
        device=device_guess,
        model_dtype=os.environ["MODEL_DTYPE"],
        sae_dtype=os.environ["SAE_DTYPE"],
        token_limit=int(os.environ["TOKEN_LIMIT"]),
    )
    Config._instance = cfg

    if chunk_by_layer:
        cfg.max_loaded_saes = 1

    print(f"Caricamento modello {model_id} su {cfg.device}...")
    if use_sae_transformer:
        model = HookedSAETransformer.from_pretrained(
            model_id,
            device=cfg.device,
            dtype=STR_TO_DTYPE[cfg.model_dtype],
            **cfg.model_kwargs,
        )
    else:
        model = HookedTransformer.from_pretrained(
            model_id,
            device=cfg.device,
            dtype=STR_TO_DTYPE[cfg.model_dtype],
            **cfg.model_kwargs,
        )
    Model.set_instance(model)
    print(f"✓ Modello caricato: {model.cfg.n_layers} layer")

    SAEManager._instance = None
    sae_mgr = SAEManager.__new__(SAEManager)
    sae_mgr.__init__(num_layers=model.cfg.n_layers, device=cfg.device)
    SAEManager._instance = sae_mgr

    print(f"SAEManager configurato: device={sae_mgr.device}, layers={sae_mgr.num_layers}")
    sae_mgr.load_saes()
    print("✓ SAE manager pronto (hook registrati)")

    return cfg, model, sae_mgr


def prepare_payloads(seeds_cfg: List[Dict[str, Any]], source_set: str) -> List[Dict[str, Any]]:
    """Load prompts/features per seed and prepare tracking structures."""
    payloads: List[Dict[str, Any]] = []
    for seed in seeds_cfg:
        slug = seed["slug"]
        prompts_path = seed["prompts_json"]
        features_path = seed["features_json"]
        out_path = seed["out_json"]

        prompts = load_prompts(prompts_path)
        features = load_features(features_path, source_set)

        results_by_prompt = {
            p["id"]: {"prompt": p["text"], "tokens": None, "counts": None, "activations": []}
            for p in prompts
        }

        features_by_layer: Dict[int, List[Dict[str, Any]]] = {}
        for feat in features:
            layer = int(feat["source"].split("-")[0])
            features_by_layer.setdefault(layer, []).append(feat)

        payloads.append(
            {
                "seed": seed,
                "slug": slug,
                "prompts": prompts,
                "features": features,
                "features_by_layer": features_by_layer,
                "results_by_prompt": results_by_prompt,
                "failed": False,
                "errors": [],
                "out_path": out_path,
            }
        )
    return payloads


def run_layer_sweep(
    payloads: List[Dict[str, Any]],
    model_id: str,
    source_set: str,
    include_zero: bool,
    persist_cache: bool,
):
    """Process all payloads layer-by-layer."""
    from neuronpedia_inference.endpoints.activation.all import ActivationProcessor  # type: ignore
    from neuronpedia_inference_client.models.activation_all_post_request import (  # type: ignore
        ActivationAllPostRequest,
    )
    from neuronpedia_inference.sae_manager import SAEManager  # type: ignore

    proc = ActivationProcessor()
    sae_mgr = SAEManager.get_instance()

    layers = sorted(
        {
            layer
            for payload in payloads
            for layer in payload["features_by_layer"].keys()
            if not payload["failed"]
        }
    )

    print(f"▶ Processing {len(layers)} layer(s) across {len(payloads)} seed(s)")

    for idx, layer in enumerate(layers, 1):
        sae_id = f"{layer}-{source_set}"
        print(f"  Layer {layer} [{idx}/{len(layers)}]...", flush=True)

        for payload in payloads:
            if payload["failed"]:
                continue
            feats = payload["features_by_layer"].get(layer, [])
            if not feats:
                continue

            for prompt in payload["prompts"]:
                pid, text = prompt["id"], prompt["text"]
                req = ActivationAllPostRequest(
                    prompt=text,
                    model=model_id,
                    source_set=source_set,
                    selected_sources=[sae_id],
                    ignore_bos=False,
                    sort_by_token_indexes=[],
                    num_results=100_000,
                )
                try:
                    resp = proc.process_activations(req)
                except Exception as exc:  # noqa: BLE001
                    payload["failed"] = True
                    payload["errors"].append(str(exc))
                    traceback.print_exc()
                    break

                results_entry = payload["results_by_prompt"][pid]
                if results_entry["tokens"] is None:
                    results_entry["tokens"] = list(resp.tokens)
                    results_entry["counts"] = [[float(x) for x in row] for row in resp.counts]

                want = {(f"{layer}-{source_set}", int(f["index"])) for f in feats}
                found = set()
                for a in resp.activations:
                    src = a.source
                    idx_feat = int(a.index)
                    if (src, idx_feat) in want:
                        obj = {
                            "source": src,
                            "index": idx_feat,
                            "values": list(a.values),
                            "sum_values": float(a.sum_values) if a.sum_values is not None else None,
                            "max_value": float(a.max_value),
                            "max_value_index": int(a.max_value_index),
                        }
                        if getattr(a, "dfa_values", None) is not None:
                            obj["dfa_values"] = list(a.dfa_values)
                            obj["dfa_target_index"] = int(a.dfa_target_index)
                            obj["dfa_max_value"] = float(a.dfa_max_value)
                        results_entry["activations"].append(obj)
                        found.add((src, idx_feat))

                if include_zero and results_entry["tokens"]:
                    num_tokens = len(results_entry["tokens"])
                    for feat in feats:
                        src = f"{layer}-{source_set}"
                        idx_feat = int(feat["index"])
                        if (src, idx_feat) not in found:
                            obj = {
                                "source": src,
                                "index": idx_feat,
                                "values": [0.0] * num_tokens,
                                "sum_values": 0.0,
                                "max_value": 0.0,
                                "max_value_index": 0,
                            }
                            results_entry["activations"].append(obj)

        if sae_id in sae_mgr.loaded_saes:
            sae_mgr.unload_sae(sae_id)

        if source_set == "clt-hp" and not persist_cache:
            try:
                hf_cache_dir = Path(os.path.expanduser("~/.cache/huggingface/hub"))
                if hf_cache_dir.exists():
                    for item in hf_cache_dir.iterdir():
                        if "mntss--clt-" in item.name and item.is_dir():
                            shutil.rmtree(item, ignore_errors=True)
                torch.cuda.empty_cache()
                gc.collect()
            except Exception:  # noqa: BLE001
                pass


def write_results(payloads: List[Dict[str, Any]], model_id: str, source_set: str) -> Dict[str, Any]:
    """Write activations_dump.json per payload and return summary."""
    device = os.environ.get("DEVICE", "cuda" if torch.cuda.is_available() else "cpu")
    summary = {"seeds": []}
    for payload in payloads:
        slug = payload["slug"]
        if payload["failed"]:
            summary["seeds"].append(
                {"slug": slug, "success": False, "error": "; ".join(payload["errors"])}
            )
            continue

        results = [
            {
                "probe_id": p["id"],
                "prompt": p["text"],
                "tokens": payload["results_by_prompt"][p["id"]]["tokens"] or [],
                "counts": payload["results_by_prompt"][p["id"]]["counts"] or [],
                "activations": payload["results_by_prompt"][p["id"]]["activations"],
            }
            for p in payload["prompts"]
        ]

        out_data = {
            "model": model_id,
            "source_set": source_set,
            "device": device,
            "n_prompts": len(results),
            "n_features_requested": len(payload["features"]),
            "results": results,
        }

        out_path = Path(payload["out_path"])
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(out_data, f, ensure_ascii=False, indent=2)

        summary["seeds"].append({"slug": slug, "success": True, "error": None, "out_json": str(out_path)})

    return summary


def main():
    parser = argparse.ArgumentParser(description="Remote multi-seed activation runner")
    parser.add_argument("--manifest", required=True, help="Path to batch manifest JSON")
    parser.add_argument("--results", required=True, help="Path to write batch results JSON")
    args = parser.parse_args()

    with open(args.manifest, "r", encoding="utf-8") as f:
        manifest = json.load(f)

    batch_id = manifest.get("batch_id", f"batch_{int(time.time())}")
    model_cfg = manifest["model"]
    activation_cfg = manifest.get("activation", {})
    seeds_cfg = manifest["seeds"]

    model_id = model_cfg["id"]
    source_set = model_cfg["source_set"]
    chunk_by_layer = activation_cfg.get("chunk_by_layer", True)
    include_zero = activation_cfg.get("include_zero", True)
    persist_cache = activation_cfg.get("persist_sae_cache", False)

    if not chunk_by_layer:
        raise ValueError("remote_batch_runner currently requires chunk_by_layer=true")

    os.environ.setdefault("MODEL_ID", model_id)
    os.environ.setdefault("SOURCE_SET", source_set)
    os.environ["CHUNK_BY_LAYER"] = "true"
    os.environ["INCLUDE_ZERO_ACTIVATIONS"] = "true" if include_zero else "false"
    os.environ["PERSIST_SAE_CACHE"] = "true" if persist_cache else "false"

    cleanup_hf_cache(persist_cache)
    cfg, model, sae_mgr = setup_environment(model_id, source_set, chunk_by_layer=True)
    _ = (cfg, model, sae_mgr)  # quiet linters

    payloads = prepare_payloads(seeds_cfg, source_set)

    success = True
    try:
        run_layer_sweep(payloads, model_id, source_set, include_zero, persist_cache)
    except Exception as exc:  # noqa: BLE001
        success = False
        traceback.print_exc()
        for payload in payloads:
            payload["failed"] = True
            payload["errors"].append(str(exc))

    summary = write_results(payloads, model_id, source_set)
    summary.update(
        {
            "batch_id": batch_id,
            "model_id": model_id,
            "source_set": source_set,
            "success": success and all(seed["success"] for seed in summary["seeds"]),
        }
    )

    results_path = Path(args.results)
    results_path.parent.mkdir(parents=True, exist_ok=True)
    with open(results_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    if not summary["success"]:
        raise SystemExit(1)


if __name__ == "__main__":
    main()

