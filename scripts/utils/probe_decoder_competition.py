#!/usr/bin/env python3
"""
Decoder-competition probe for specificity-failure swap pairs.

Background
----------
Some hard-fail swap pairs (e.g. north_dakota_fargo -> north_carolina_charlotte
with target capital Raleigh) produce a non-target-but-state-consistent token
on the first generated step (e.g. " Chapel" -> " Hill"). Manual feature-set
ablation showed the capital token is present in the steered top-k at low M
but the model's sampler still selects the competitor.

This probe isolates whether the failure is purely *decoder competition*:

  Probe A -- Greedy decoding
      Re-run the same intervention (and feature set) but with do_sample=False,
      temperature=0.0, freq_penalty=0.0. If the target capital is the argmax
      at any tested M, greedy decoding will emit it.

  Probe B -- Competitor suppression
      Re-run with sampling but additively penalize the competitor token IDs
      (and their leading-space variants) on the FIRST generated step only.
      The penalty is applied directly to the steered logits returned by
      ``feature_intervention``, then we generate position 0 ourselves
      (argmax or sample) and let the model continue normally for the rest.

For each (pair, mode, M) we record:
    - first generated token / top-15 with probs
    - full continuation (16 tokens)
    - whether the target capital appears as the first-token argmax / fuzzy hit
    - rank of the target capital and the suppressed competitor

Outputs are written to ``output/research/_decoder_competition_probe.json``.

Typical invocation::

    .venv/bin/python scripts/utils/probe_decoder_competition.py \
        --pair north_dakota_fargo:north_carolina_charlotte \
        --variant add_state_capital \
        --m-values 4.472136 6 8 12 20 \
        --gpu-id 0
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Remove this script's own directory from sys.path so that the local
# scripts/utils/datasets/ folder (a JSON dataset registry) does not shadow the
# real HuggingFace `datasets` package which transformer_lens imports.
_SELF_DIR = str(Path(__file__).resolve().parent)
sys.path[:] = [p for p in sys.path if Path(p or ".").resolve() != Path(_SELF_DIR).resolve()]

import torch  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPTS_DIR = REPO_ROOT / "scripts"
NEURONPEDIA_DIR = SCRIPTS_DIR / "neuronpedia_steering"
for p in (SCRIPTS_DIR, NEURONPEDIA_DIR.parent):
    sp = str(p)
    if sp not in sys.path:
        sys.path.insert(0, sp)

from neuronpedia_steering.batch_steering_ct import (  # type: ignore
    CTInterventionFeature,
    build_intervention_tuples,
    get_dtype,
    load_replacement_model,
)


DATASET_RUN = (
    "usa_states_batch",
    "fullscale_usa_field_add",
)
COMPETITORS_BY_TARGET: Dict[str, List[str]] = {
    # North Carolina (Charlotte): suppress the cluster of NC non-capital cities
    # that out-compete Raleigh.
    "Raleigh": [
        "Chapel",
        "Cary",
        "Durham",
        "Greensboro",
        "Asheville",
        "Wilmington",
        "Winston",
        "Fayetteville",
        "Charlotte",
    ],
    # Vermont (Burlington -> capital Montpelier): suppress competing VT/NH
    # non-capitals seen in earlier probe runs.
    "Montpelier": [
        "Burlington",
        "Rutland",
        "Stowe",
        "Brattleboro",
        "Manchester",
        "Springfield",
    ],
    # Alaska (Anchorage -> capital Juneau): suppress AK non-capitals.
    # Many AK city names are multi-token (Soldotna, Wasilla, Anchorage), so we
    # also list their first sub-tokens (Sold, Was, Anch, Palmer, Ken).
    "Juneau": [
        "Soldotna",
        "Anchorage",
        "Fairbanks",
        "Wasilla",
        "Sitka",
        "Kodiak",
        "Kenai",
        "Palmer",
        # First-subtoken stems (with leading space these are single tokens
        # that frequently appear in the steered top-k).
        "Sold",
        "Was",
        "Anch",
        "Ken",
    ],
}


def _load_features(work_dir: Path) -> List[Dict[str, Any]]:
    fp = work_dir / "features.json"
    if not fp.exists():
        raise FileNotFoundError(f"features.json missing at {fp}")
    return json.loads(fp.read_text(encoding="utf-8"))


def _build_intervention_features(
    raw_features: List[Dict[str, Any]],
    m_amplify: float,
) -> List[CTInterventionFeature]:
    """Map raw feature dicts to CTInterventionFeature, overriding the
    amplification M for amplify (M>0) features. Ablate features (M<=0) keep
    their original M and use live activations (multiplication mode)."""
    out: List[CTInterventionFeature] = []
    for f in raw_features:
        m_orig = float(f.get("M", 1.0))
        if m_orig > 0:
            m = m_amplify
        else:
            m = m_orig
        stored = f.get("stored_activation")
        use_stored = bool(f.get("use_stored_as_base", False))
        out.append(
            CTInterventionFeature(
                layer=int(f["layer"]),
                index=int(f["index"]),
                position=int(f.get("position", -1)),
                steer_position=f.get("steer_position"),
                M=m,
                steer_generated_tokens=bool(f.get("steer_generated_tokens", False)),
                stored_activation=float(stored) if stored is not None else None,
                use_stored_as_base=use_stored,
            )
        )
    return out


def _resolve_token_ids(tokenizer, words: List[str]) -> List[Tuple[int, str]]:
    """Resolve each word to all its single-token variants we can find
    (e.g. with leading space, capitalized, lowercase)."""
    found: List[Tuple[int, str]] = []
    seen: set = set()
    for w in words:
        for variant in (f" {w}", w, f" {w.lower()}", w.lower()):
            try:
                ids = tokenizer.encode(variant, add_special_tokens=False)
            except Exception:
                continue
            if len(ids) == 1 and ids[0] not in seen:
                found.append((ids[0], variant))
                seen.add(ids[0])
    return found


def _topk(logits_1d: torch.Tensor, tokenizer, k: int) -> List[Dict[str, Any]]:
    probs = torch.softmax(logits_1d.float(), dim=-1)
    tk = torch.topk(probs, k)
    return [
        {
            "token": tokenizer.decode([int(tk.indices[i].item())]),
            "tok_id": int(tk.indices[i].item()),
            "prob": float(tk.values[i].item()),
        }
        for i in range(k)
    ]


def _rank_of(logits_1d: torch.Tensor, tok_id: int) -> int:
    return int(torch.sum(logits_1d > logits_1d[tok_id]).item()) + 1


def _decode_continuation(
    tokenizer,
    prompt_ids: torch.Tensor,
    extra_ids: List[int],
) -> str:
    full = torch.cat(
        [prompt_ids[0], torch.tensor(extra_ids, device=prompt_ids.device)],
        dim=0,
    )
    return tokenizer.decode(full.tolist(), skip_special_tokens=False)


def _continue_after_first(
    model,
    prompt: str,
    first_token_id: int,
    n_more_tokens: int,
    do_sample: bool,
    temperature: float,
    freq_penalty: float,
    seed: int,
) -> str:
    """Append first_token_id to the prompt then call model.generate for the
    remaining tokens. Used by Probe B so the manually-chosen first token is
    honored before letting the model continue normally."""
    torch.manual_seed(seed)
    seed_text = prompt + model.tokenizer.decode([first_token_id])
    out = model.generate(
        seed_text,
        do_sample=do_sample,
        use_past_kv_cache=True,
        verbose=False,
        stop_at_eos=True,
        max_new_tokens=n_more_tokens,
        temperature=temperature,
        freq_penalty=freq_penalty,
        return_type="str",
    )
    return out


def _run_intervention_first_step(
    model,
    prompt: str,
    interventions,
    freeze_attention: bool,
):
    """Call feature_intervention (single forward pass) and return the steered
    logits at the last prompt position."""
    out = model.feature_intervention(
        prompt,
        interventions,
        freeze_attention=freeze_attention,
        sparse=False,
        return_activations=False,
    )
    if isinstance(out, tuple):
        steered_logits = out[0]
    else:
        steered_logits = out
    last = steered_logits.squeeze()[-1]
    return last


def _decode_with_steering_only_first(
    model,
    prompt: str,
    interventions,
    freeze_attention: bool,
    do_sample: bool,
    temperature: float,
    freq_penalty: float,
    n_tokens: int,
    seed: int,
) -> Tuple[torch.Tensor, str]:
    """Use feature_intervention_generate to generate n_tokens with steering
    applied throughout. Returns (steered_logits[positions, vocab], decoded text).
    """
    if seed is not None:
        torch.manual_seed(seed)
    result = model.feature_intervention_generate(
        prompt,
        interventions,
        freeze_attention=freeze_attention,
        do_sample=do_sample,
        verbose=False,
        stop_at_eos=True,
        max_new_tokens=n_tokens,
        temperature=temperature,
        freq_penalty=freq_penalty,
        return_type="tokens",
    )
    if isinstance(result, tuple):
        steered_tokens, steered_logits, _ = result
    else:
        steered_tokens, steered_logits = result, None
    if isinstance(steered_tokens, tuple):
        steered_tokens = steered_tokens[0]
    text = model.tokenizer.decode(steered_tokens[0], skip_special_tokens=False)
    return steered_logits, text


def _run_probe_a_greedy(
    model,
    prompt: str,
    interventions,
    target_token: str,
    competitors: List[Tuple[int, str]],
    n_tokens: int,
) -> Dict[str, Any]:
    """Probe A: same intervention applied throughout, but greedy decoding
    (do_sample=False, T=0, no freq penalty). The first-token logits are read
    from a separate ``feature_intervention`` call so they are unambiguous."""
    first_logits = _run_intervention_first_step(
        model, prompt, interventions, freeze_attention=False
    ).float()

    _, text = _decode_with_steering_only_first(
        model,
        prompt,
        interventions,
        freeze_attention=False,
        do_sample=False,
        temperature=0.0,
        freq_penalty=0.0,
        n_tokens=n_tokens,
        seed=42,
    )

    target_id, _ = _single_id(model.tokenizer, target_token)
    target_rank = _rank_of(first_logits, target_id) if target_id is not None else None
    target_prob = (
        float(torch.softmax(first_logits, dim=-1)[target_id].item())
        if target_id is not None
        else None
    )
    comp_ranks = {name: _rank_of(first_logits, tid) for tid, name in competitors}
    return {
        "first_token": model.tokenizer.decode([int(torch.argmax(first_logits).item())]),
        "topk": _topk(first_logits, model.tokenizer, 15),
        "continuation": text,
        "target_rank": target_rank,
        "target_prob": target_prob,
        "competitor_ranks": comp_ranks,
    }


def _single_id(tokenizer, word: str) -> Tuple[Optional[int], Optional[str]]:
    """Return the single-token id for ``word`` if available. If the word is
    multi-token, return the FIRST sub-token id with a leading space (this is
    what greedy decoding will emit at position 0)."""
    for variant in (f" {word}", word, word.strip()):
        try:
            ids = tokenizer.encode(variant, add_special_tokens=False)
        except Exception:
            continue
        if len(ids) == 1:
            return ids[0], variant
    # Fallback: take first sub-token of the leading-space variant
    try:
        ids = tokenizer.encode(f" {word}", add_special_tokens=False)
        if ids:
            return ids[0], f" {word}[0]={tokenizer.decode([ids[0]])!r}"
    except Exception:
        pass
    return None, None


def _run_probe_b_suppress(
    model,
    prompt: str,
    interventions,
    target_token: str,
    competitor_ids: List[Tuple[int, str]],
    n_tokens: int,
    suppression_logit_penalty: float,
    do_sample: bool,
    temperature: float,
    freq_penalty: float,
    seed: int,
) -> Dict[str, Any]:
    """Probe B: get the first-token steered logits, subtract a penalty from
    each competitor token id, pick the next token (argmax/sample), then let
    the model continue normally."""
    # 1) one-shot intervention forward pass
    last_logits = _run_intervention_first_step(
        model, prompt, interventions, freeze_attention=False
    )

    # 2) penalize competitor tokens
    biased = last_logits.clone().float()
    for tid, _ in competitor_ids:
        biased[tid] = biased[tid] - suppression_logit_penalty

    # 3) pick the first token
    if do_sample and temperature > 0:
        torch.manual_seed(seed)
        probs = torch.softmax(biased / max(temperature, 1e-3), dim=-1)
        first_id = int(torch.multinomial(probs, num_samples=1).item())
    else:
        first_id = int(torch.argmax(biased).item())

    # 4) decode the rest WITHOUT steering (decoder-competition isolated)
    n_more = max(0, n_tokens - 1)
    cont_text = (
        _continue_after_first(
            model, prompt, first_id, n_more,
            do_sample=do_sample, temperature=temperature,
            freq_penalty=freq_penalty, seed=seed,
        )
        if n_more > 0
        else prompt + model.tokenizer.decode([first_id])
    )

    target_id, _ = _single_id(model.tokenizer, target_token)
    target_rank_pre = _rank_of(last_logits.float(), target_id) if target_id is not None else None
    target_rank_post = _rank_of(biased, target_id) if target_id is not None else None
    target_prob_post = (
        float(torch.softmax(biased, dim=-1)[target_id].item())
        if target_id is not None
        else None
    )

    return {
        "first_token": model.tokenizer.decode([first_id]),
        "topk_pre_suppression": _topk(last_logits.float(), model.tokenizer, 15),
        "topk_post_suppression": _topk(biased, model.tokenizer, 15),
        "continuation": cont_text,
        "target_rank_pre": target_rank_pre,
        "target_rank_post": target_rank_post,
        "target_prob_post_suppression": target_prob_post,
        "competitors_suppressed": [name for _, name in competitor_ids],
        "competitor_ids_used": [tid for tid, _ in competitor_ids],
    }


def _resolve_pair_dirs(dataset: str, run_name: str) -> Path:
    return REPO_ROOT / "output" / dataset / "_swaps" / "runs" / run_name


def _hit(text: str, target: str, source: Optional[str] = None) -> bool:
    t = text.lower()
    return target.lower() in t and (source is None or source.lower() not in t)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pair", required=True,
        help="from_slug:to_slug, e.g. north_dakota_fargo:north_carolina_charlotte",
    )
    parser.add_argument("--variant", default="add_state_capital")
    parser.add_argument("--target-capital", default=None,
                        help="Target capital token (default: read from result file)")
    parser.add_argument(
        "--m-values", nargs="*", type=float,
        default=[4.472136, 6.0, 8.0, 12.0, 20.0],
    )
    parser.add_argument("--gpu-id", type=int, default=0)
    parser.add_argument("--n-tokens", type=int, default=16)
    parser.add_argument("--suppression-penalty", type=float, default=8.0,
                        help="Logit penalty (subtracted) for competitor tokens in Probe B")
    parser.add_argument("--probe-b-temperature", type=float, default=0.5)
    parser.add_argument("--probe-b-freq-penalty", type=float, default=2.0)
    parser.add_argument("--probe-b-do-sample", action="store_true", default=True)
    parser.add_argument("--probe-b-greedy", dest="probe_b_do_sample", action="store_false")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--output", default=str(REPO_ROOT / "output" / "research" / "_decoder_competition_probe.json"),
    )
    parser.add_argument(
        "--transcoder-set",
        default="mntss/clt-gemma-2-2b-2.5M",
        help="Transcoder set name (must match the one used by the original swap run)",
    )
    parser.add_argument("--model-id", default="google/gemma-2-2b")
    args = parser.parse_args()

    from_slug, to_slug = args.pair.split(":")

    dataset, run = DATASET_RUN
    run_dir = _resolve_pair_dirs(dataset, run)
    work_dir = run_dir / "work" / f"{from_slug}__to__{to_slug}__{args.variant}"
    result_file = run_dir / "by_source" / from_slug / f"to_{to_slug}__{args.variant}.json"
    if not result_file.exists():
        raise FileNotFoundError(f"Result file missing: {result_file}")
    rd = json.loads(result_file.read_text(encoding="utf-8"))
    source = rd.get("source", {})
    target = rd.get("target", {})
    prompt = source.get("prompt", "")
    target_capital = args.target_capital or target.get("capital")
    source_capital = source.get("capital")

    raw_features = _load_features(work_dir)

    print(f"[probe] pair       = {from_slug} -> {to_slug}")
    print(f"[probe] variant    = {args.variant}")
    print(f"[probe] prompt     = {prompt!r}")
    print(f"[probe] target cap = {target_capital}")
    print(f"[probe] source cap = {source_capital}")
    print(f"[probe] n_features = {len(raw_features)}")
    print(f"[probe] M values   = {args.m_values}")

    # Pick competitors for the target capital
    competitor_words = COMPETITORS_BY_TARGET.get(target_capital, [])
    if not competitor_words:
        raise SystemExit(
            f"No competitor set defined for target capital {target_capital!r}. "
            f"Add it to COMPETITORS_BY_TARGET."
        )

    # Load model on chosen GPU
    os.environ.setdefault("PYTORCH_CUDA_ALLOC_CONF", "expandable_segments:True")
    torch.cuda.set_device(args.gpu_id)
    device = torch.device(f"cuda:{args.gpu_id}")
    dtype = get_dtype("bfloat16")
    model = load_replacement_model(
        args.model_id, args.transcoder_set, device, dtype,
    )
    competitor_ids = _resolve_token_ids(model.tokenizer, competitor_words)
    print(f"[probe] competitor token ids: {competitor_ids}")

    target_id, _ = _single_id(model.tokenizer, target_capital)
    print(f"[probe] target token id: {target_id}")

    results: Dict[str, Any] = {
        "pair": [from_slug, to_slug],
        "variant": args.variant,
        "prompt": prompt,
        "target_capital": target_capital,
        "source_capital": source_capital,
        "competitor_words": competitor_words,
        "competitor_ids": [list(t) for t in competitor_ids],
        "n_features_total": len(raw_features),
        "n_features_amplify": sum(1 for f in raw_features if f.get("M", 0) > 0),
        "n_features_ablate": sum(1 for f in raw_features if f.get("M", 0) < 0),
        "m_values": args.m_values,
        "suppression_penalty": args.suppression_penalty,
        "probe_a": [],  # greedy
        "probe_b": [],  # competitor suppression
    }

    # Get live activations once (needed by ablate/M<=0 features which use
    # multiplication mode against the live activation).
    print("[probe] computing live activations for prompt ...")
    with torch.inference_mode():
        _, live_activations = model.get_activations(prompt, sparse=True)

    for m in args.m_values:
        feats = _build_intervention_features(raw_features, m_amplify=m)
        n_seq = model.tokenizer(prompt, return_tensors="pt").input_ids.shape[1]
        interventions = build_intervention_tuples(feats, live_activations, n_seq)

        print(f"\n[probe][M={m}] running Probe A (greedy)...")
        try:
            pa = _run_probe_a_greedy(
                model, prompt, interventions, target_capital,
                competitor_ids, args.n_tokens,
            )
            pa["M"] = m
            pa["target_hit_in_continuation"] = _hit(
                pa["continuation"], target_capital, source_capital,
            )
            pa["argmax_is_target"] = (
                pa["first_token"].strip().lower() == target_capital.lower()
            )
            print(f"  first_token={pa['first_token']!r} target_rank={pa['target_rank']} "
                  f"hit={pa['target_hit_in_continuation']}")
            results["probe_a"].append(pa)
        except Exception as exc:  # pragma: no cover
            print(f"  Probe A failed for M={m}: {exc}")
            results["probe_a"].append({"M": m, "error": str(exc)})

        print(f"[probe][M={m}] running Probe B (competitor suppression)...")
        try:
            pb = _run_probe_b_suppress(
                model, prompt, interventions, target_capital,
                competitor_ids,
                n_tokens=args.n_tokens,
                suppression_logit_penalty=args.suppression_penalty,
                do_sample=args.probe_b_do_sample,
                temperature=args.probe_b_temperature,
                freq_penalty=args.probe_b_freq_penalty,
                seed=args.seed,
            )
            pb["M"] = m
            pb["target_hit_in_continuation"] = _hit(
                pb["continuation"], target_capital, source_capital,
            )
            pb["argmax_is_target_post"] = (
                pb["first_token"].strip().lower() == target_capital.lower()
            )
            print(f"  first_token={pb['first_token']!r} "
                  f"target_rank pre/post={pb['target_rank_pre']}/{pb['target_rank_post']} "
                  f"hit={pb['target_hit_in_continuation']}")
            results["probe_b"].append(pb)
        except Exception as exc:  # pragma: no cover
            print(f"  Probe B failed for M={m}: {exc}")
            results["probe_b"].append({"M": m, "error": str(exc)})

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    # If output exists, append to a list of probe runs keyed by pair+variant
    payload = []
    if out.exists():
        try:
            existing = json.loads(out.read_text(encoding="utf-8"))
            if isinstance(existing, list):
                payload = existing
            else:
                payload = [existing]
        except Exception:
            payload = []
    payload.append(results)
    out.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n[probe] wrote {out}")


if __name__ == "__main__":
    main()
