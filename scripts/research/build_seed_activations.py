"""
Generate per-seed activation dumps for the seed prompt of one or more entities.

Background. The figures produced by ``scripts/visualization/activation_heatmap.py``
stack the seed prompt above the probe rows. Until the bug fix that ships with
this script, the seed row was rebuilt from the *pruned* attribution graph in
``00 Graph Generation/graph.json`` -- which only retains nodes whose influence
on the target logit clears the pruning threshold. Diffuse features
(``Relationship``, multi-peak ``Sem-Conc``) therefore appeared sparser than
they really are on the seed row, while the probe rows (unpruned) showed the
full activation pattern.

This script materializes the missing artifact: for each requested
``<dump_path>::<feature_id>`` target, it runs gemma-2-2b on the seed prompt
(read from the entity's ``graph.json`` metadata), encodes the cached residual
activations through the layer's CLT transcoder, and writes the per-token
activations of the requested feature to a ``seed_activations_dump.json`` next
to the existing probe ``activations_dump.json``. The file follows the same
schema as the probe dump so the renderer auto-discovers it.

Targets are passed as ``<dump_path>::<feature_id>`` pairs, e.g.::

    output/usa_states_batch/delaware_Wilmington/01 Prompt Probing/activations_dump.json::7-clt-hp:66851

Multiple targets are processed in one run so the model is loaded once.
The ``--verify`` flag re-runs the extractor on the existing probe prompts and
asserts the extracted values match the existing dump within a tolerance --
catching layer/hookpoint mismatches before the seed row is committed.
"""

from __future__ import annotations

import argparse
import gc
import json
from pathlib import Path
from typing import Dict, List, Tuple

REPO = Path(__file__).resolve().parents[2]

BOS_PREFIXES = ("<bos>", "<|begin_of_text|>", "<|endoftext|>")
SAE_RELEASE = "mntss-gemma-2-2b-2.5m-clt-as-per-layer"


def parse_target(spec: str) -> Tuple[Path, str]:
    """Split ``<dump_path>::<feature_id>`` into ``(dump_path, feature_id)``."""
    if "::" not in spec:
        raise ValueError(
            f"Target must be '<dump_path>::<feature_id>', got: {spec!r}"
        )
    dump_str, feat = spec.split("::", 1)
    dump_path = Path(dump_str)
    if not dump_path.is_absolute():
        dump_path = (REPO / dump_path).resolve()
    if not dump_path.exists():
        raise FileNotFoundError(f"Dump not found: {dump_path}")
    if ":" not in feat or "-" not in feat.split(":", 1)[0]:
        raise ValueError(
            f"feature_id must look like '<layer>-<set>:<index>', got: {feat!r}"
        )
    return dump_path, feat


def feature_to_layer_index(feature_id: str) -> Tuple[int, int]:
    src, idx_str = feature_id.split(":", 1)
    return int(src.split("-", 1)[0]), int(idx_str)


def feature_to_source(feature_id: str) -> str:
    return feature_id.split(":", 1)[0]


def feature_source_set(feature_id: str) -> str:
    """Return the source-set label, e.g. 'clt-hp' for '7-clt-hp:66851'."""
    return feature_to_source(feature_id).split("-", 1)[1]


def read_seed_prompt(graph_json: Path) -> str:
    with open(graph_json, "r", encoding="utf-8") as f:
        graph = json.load(f)
    prompt = (graph.get("metadata") or {}).get("prompt", "")
    if not prompt:
        raise RuntimeError(f"No metadata.prompt found in {graph_json}")
    for prefix in BOS_PREFIXES:
        if prompt.startswith(prefix):
            prompt = prompt[len(prefix):]
            break
    return prompt


def load_model(model_id: str, device: str, dtype_str: str):
    """Load gemma-2-2b via transformer-lens with the SAE-friendly preprocessing.

    Matches the loader the probe pipeline uses (no LayerNorm folding, no
    weight processing) -- the CLT transcoders were trained against the raw
    residual stream so the model must be loaded the same way.
    """
    import torch
    from transformer_lens import HookedTransformer

    dtype = {"bfloat16": torch.bfloat16, "float16": torch.float16, "float32": torch.float32}[dtype_str]
    model = HookedTransformer.from_pretrained_no_processing(
        model_id, device=device, dtype=dtype, fold_ln=False,
    )
    model.eval()
    return model


def load_sae(layer: int, source_set: str, device: str):
    """Load the per-layer CLT transcoder for ``layer`` via sae-lens."""
    from sae_lens import SAE

    if source_set != "clt-hp":
        raise ValueError(
            f"Only source_set='clt-hp' is wired in this script (got {source_set!r}). "
            "Add a release mapping if you need another set."
        )
    sae = SAE.from_pretrained(
        release=SAE_RELEASE,
        sae_id=f"layer_{layer}",
        device=device,
    )
    # The probe pipeline uses neuronpedia_inference.saes.saelens.SaeLensSAE.load,
    # which calls fold_W_dec_norm() on every loaded SAE. We must do the same so
    # encoder activations are scaled identically; otherwise feature values come
    # out a constant factor smaller than what the existing probe dump records.
    if sae.cfg.architecture() not in ("temporal",):
        sae.fold_W_dec_norm()
    sae.eval()
    return sae


def extract_feature_activations(
    model,
    sae,
    prompt_text: str,
) -> Tuple[List[str], List[List[float]]]:
    """
    Run ``model`` on ``prompt_text``, capture activations at ``sae.cfg.hook_name``,
    encode them through the SAE, and return ``(tokens, feature_acts_per_token)``.

    ``feature_acts_per_token`` is a 2D Python list of shape
    ``[d_sae][n_tokens]``; per-token transposition lets the caller pluck a
    feature row in O(1).
    """
    import torch

    metadata = getattr(sae.cfg, "metadata", {}) or {}
    hook_name = metadata.get("hook_name") or getattr(sae.cfg, "hook_name", None)
    if hook_name is None:
        raise RuntimeError("Unable to discover hook_name from SAE config.")
    prepend_bos = bool(metadata.get("prepend_bos", True))
    tokens = model.to_tokens(prompt_text, prepend_bos=prepend_bos)
    # transformer-lens 3.1 has a Gemma-specific bug in HookedTransformer.to_str_tokens
    # (it unsqueezes the token tensor to 2-D and then can't int() the resulting
    # list-of-lists). We tokenize directly via the wrapped HF tokenizer instead;
    # batch_decode on each id reproduces the per-token string format
    # (\"<bos>\", \" capital\", ...) that the renderer expects.
    ids = tokens[0].tolist()
    str_tokens = [model.tokenizer.decode([tid], clean_up_tokenization_spaces=False) for tid in ids]

    captured: Dict[str, "torch.Tensor"] = {}

    def capture_hook(act, hook):  # transformer-lens passes the HookPoint as `hook=`
        captured["x"] = act.detach()
        return act

    with torch.no_grad():
        model.run_with_hooks(tokens, fwd_hooks=[(hook_name, capture_hook)])

    x = captured["x"]
    # (batch=1, seq, d_model) or (batch=1, seq, ...) - flatten to (seq, d_model)
    if x.ndim == 3:
        x = x[0]
    with torch.no_grad():
        feat = sae.encode(x)
    feat = feat.detach().float().cpu().numpy()  # (seq, d_sae)

    # Transpose to (d_sae, seq) so callers can index by feature index.
    feat_per_index = feat.T.tolist()
    return list(str_tokens), feat_per_index


def build_seed_dump(
    feature_id: str,
    seed_prompt: str,
    tokens: List[str],
    feat_per_index: List[List[float]],
    model_id: str,
    source_set: str,
) -> dict:
    layer, index = feature_to_layer_index(feature_id)
    if not (0 <= index < len(feat_per_index)):
        raise IndexError(
            f"Feature index {index} out of range (d_sae={len(feat_per_index)}) "
            f"for {feature_id}"
        )
    values = feat_per_index[index]
    max_val = max(values) if values else 0.0
    max_idx = values.index(max_val) if values else 0
    return {
        "model": model_id,
        "source_set": source_set,
        "n_prompts": 1,
        "n_features_requested": 1,
        "results": [
            {
                "probe_id": "seed",
                "prompt": seed_prompt,
                "tokens": tokens,
                "activations": [
                    {
                        "source": feature_to_source(feature_id),
                        "index": index,
                        "values": values,
                        "sum_values": float(sum(values)),
                        "max_value": float(max_val),
                        "max_value_index": int(max_idx),
                    }
                ],
            }
        ],
    }


def verify_against_probe_dump(
    model,
    sae,
    feature_id: str,
    probe_dump_path: Path,
    atol: float = 0.5,
    rtol: float = 0.05,
) -> None:
    """
    Re-extract feature activations for every probe in ``probe_dump_path`` and
    compare against the stored ``activations[*].values``. Raises if any mismatch
    exceeds ``atol + rtol * |stored|``. This catches layer/hook misconfigurations
    before we trust the extractor on the seed prompt.
    """
    layer, index = feature_to_layer_index(feature_id)
    with open(probe_dump_path, "r", encoding="utf-8") as f:
        dump = json.load(f)
    target_source = feature_to_source(feature_id)

    n_checked = 0
    for res in dump.get("results", []):
        prompt = res.get("prompt", "")
        if not prompt:
            continue
        stored = None
        for act in res.get("activations", []):
            if int(act.get("index", -1)) == index and act.get("source") == target_source:
                stored = [float(v) for v in act.get("values") or []]
                break
        if stored is None:
            continue

        tokens, feat_per_index = extract_feature_activations(model, sae, prompt)
        if len(tokens) != len(stored):
            raise AssertionError(
                f"Token-count mismatch for probe {res.get('probe_id')!r}: "
                f"extracted={len(tokens)} stored={len(stored)}"
            )
        recomputed = feat_per_index[index]
        max_dev = 0.0
        for s, r in zip(stored, recomputed):
            tol = atol + rtol * abs(s)
            dev = abs(s - r)
            if dev > tol:
                raise AssertionError(
                    f"Mismatch for {feature_id} on probe {res.get('probe_id')!r} "
                    f"prompt={prompt!r}: stored={stored} recomputed={recomputed}"
                )
            max_dev = max(max_dev, dev)
        n_checked += 1
        print(
            f"  verify OK: {res.get('probe_id'):<24} "
            f"max|delta|={max_dev:.3f} (max stored={max(stored):.2f})"
        )
    if n_checked == 0:
        raise AssertionError(
            f"No matching probe rows found in {probe_dump_path} for {feature_id}"
        )
    print(f"  verify PASSED on {n_checked} probe(s) for {feature_id}")


def process_target(
    dump_path: Path,
    feature_id: str,
    model,
    sae,
    model_id: str,
    source_set: str,
    verify: bool,
) -> Path:
    entity_dir = dump_path.parent.parent
    graph_json = entity_dir / "00 Graph Generation" / "graph.json"
    if not graph_json.exists():
        raise FileNotFoundError(f"Graph json not found: {graph_json}")

    if verify:
        print(f"Verifying extractor against probe dump for {feature_id} ...")
        verify_against_probe_dump(model, sae, feature_id, dump_path)

    seed_prompt = read_seed_prompt(graph_json)
    print(f"Extracting seed activations: {entity_dir.name} | {feature_id}")
    print(f"  seed prompt: {seed_prompt!r}")
    tokens, feat_per_index = extract_feature_activations(model, sae, seed_prompt)

    seed_dump = build_seed_dump(
        feature_id=feature_id,
        seed_prompt=seed_prompt,
        tokens=tokens,
        feat_per_index=feat_per_index,
        model_id=model_id,
        source_set=source_set,
    )
    out_path = dump_path.parent / "seed_activations_dump.json"
    with out_path.open("w", encoding="utf-8") as f:
        json.dump(seed_dump, f, ensure_ascii=False, indent=2)
    values = seed_dump["results"][0]["activations"][0]["values"]
    nonzero = sum(1 for v in values if v > 1e-4)
    print(
        f"  wrote {out_path} | n_tokens={len(tokens)} "
        f"max={max(values):.2f} nonzero={nonzero}/{len(values)}"
    )
    return out_path


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument(
        "--target",
        action="append",
        default=[],
        required=True,
        help="Repeatable. Format: '<dump_path>::<feature_id>', "
             "e.g. 'output/.../activations_dump.json::7-clt-hp:66851'.",
    )
    p.add_argument("--model-id", default="gemma-2-2b")
    p.add_argument(
        "--device",
        default=None,
        help="Defaults to 'cuda' if available, else 'cpu'.",
    )
    p.add_argument(
        "--dtype",
        default="bfloat16",
        choices=["bfloat16", "float16", "float32"],
    )
    p.add_argument(
        "--verify",
        action="store_true",
        help="Re-extract every probe in the existing dump and assert the "
             "extracted activations match within tolerance. Highly recommended "
             "the first time you run on a new layer/source-set.",
    )
    return p.parse_args()


def main() -> int:
    args = parse_args()
    targets = [parse_target(t) for t in args.target]

    source_sets = {feature_source_set(feat) for _, feat in targets}
    if len(source_sets) != 1:
        raise SystemExit(
            f"All targets must share one source-set; got {sorted(source_sets)}"
        )
    source_set = source_sets.pop()

    import torch
    device = args.device or ("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Loading {args.model_id} on {device} (dtype={args.dtype}) ...")
    model = load_model(args.model_id, device=device, dtype_str=args.dtype)

    # Process targets grouped by layer so each transcoder is loaded once and
    # unloaded before the next layer (each clt-hp SAE is ~20GB on GPU; loading
    # several together OOMs even on a 48GB A40).
    by_layer: Dict[int, List[Tuple[Path, str]]] = {}
    for t in targets:
        by_layer.setdefault(feature_to_layer_index(t[1])[0], []).append(t)

    failures: List[str] = []
    for layer in sorted(by_layer.keys()):
        print(f"Loading {source_set} transcoder for layer {layer} ...")
        sae = load_sae(layer, source_set, device=device)
        try:
            for dump_path, feature_id in by_layer[layer]:
                try:
                    process_target(
                        dump_path=dump_path,
                        feature_id=feature_id,
                        model=model,
                        sae=sae,
                        model_id=args.model_id,
                        source_set=source_set,
                        verify=args.verify,
                    )
                except Exception as e:
                    failures.append(f"{dump_path}::{feature_id}: {e}")
                    print(f"  FAILED: {e}")
        finally:
            del sae
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()

    del model
    gc.collect()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()

    if failures:
        print(f"\n{len(failures)} failure(s):")
        for f in failures:
            print(f"  {f}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
