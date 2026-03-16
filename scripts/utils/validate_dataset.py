"""
Validate dataset entities against a language model.

Checks for each entity:
  1. Expected answer is the top-1 predicted token
  2. Probability of expected answer >= threshold
  3. No token overlap between prompt tokens and expected answer's first token

Backends:
  local  - loads the model locally (needs GPU or patience on CPU)
  hf-api - uses HuggingFace Inference API (needs HF_TOKEN env var or --hf-token)

Usage:
    python -m scripts.utils.validate_dataset scripts/utils/datasets/songs_lead_singers.json
    python -m scripts.utils.validate_dataset scripts/utils/datasets/*.json --backend hf-api
    python -m scripts.utils.validate_dataset scripts/utils/datasets/*.json --min-prob 0.20
"""

import argparse
import json
import math
import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

TOP_N = 50


def load_dataset(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Backend: local (transformers)
# ---------------------------------------------------------------------------

def _load_local_backend(model_id: str, device: str):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    print(f"Loading model {model_id} on {device} ...")
    model = AutoModelForCausalLM.from_pretrained(
        model_id, torch_dtype=torch.float16, device_map=device
    )
    model.eval()

    def infer(prompt: str) -> list[dict]:
        inputs = tokenizer(prompt, return_tensors="pt").to(device)
        with torch.no_grad():
            logits = model(**inputs).logits[0, -1, :]
        probs = torch.softmax(logits.float(), dim=-1)
        top_vals, top_ids = torch.topk(probs, k=TOP_N)
        return [
            {"id": tid.item(), "text": tokenizer.decode([tid.item()]), "prob": p.item()}
            for tid, p in zip(top_ids, top_vals)
        ]

    return infer, tokenizer


# ---------------------------------------------------------------------------
# Backend: HuggingFace Inference API
# ---------------------------------------------------------------------------

def _load_hf_api_backend(model_id: str, hf_token: str | None):
    from huggingface_hub import InferenceClient
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_id)
    token = hf_token or os.environ.get("HF_TOKEN")
    if not token:
        raise ValueError(
            "HF API backend requires a token. "
            "Set HF_TOKEN env var or pass --hf-token."
        )
    client = InferenceClient(model=model_id, token=token)
    print(f"Using HF Inference API for {model_id}")

    def infer(prompt: str) -> list[dict]:
        resp = client.text_generation(
            prompt,
            max_new_tokens=1,
            details=True,
            top_n_tokens=TOP_N,
            temperature=None,
        )
        position_tokens = resp.details.top_tokens[0]
        return [
            {"id": t.id, "text": t.text, "prob": math.exp(t.logprob)}
            for t in position_tokens
        ]

    return infer, tokenizer


# ---------------------------------------------------------------------------
# Validation logic (backend-agnostic)
# ---------------------------------------------------------------------------

def get_answer_token_candidates(tokenizer, expected_answer: str) -> list[int]:
    """First-token IDs for *expected_answer* (with/without leading space)."""
    candidates = []
    for prefix in (" ", ""):
        ids = tokenizer.encode(prefix + expected_answer, add_special_tokens=False)
        if ids and ids[0] not in candidates:
            candidates.append(ids[0])
    return candidates


def validate_entity(
    infer_fn, tokenizer, prompt: str, expected_answer: str, min_prob: float
) -> dict:
    prompt_token_ids = set(
        tokenizer.encode(prompt, add_special_tokens=False)
    )
    answer_candidates = get_answer_token_candidates(tokenizer, expected_answer)
    if not answer_candidates:
        return _fail("no_answer_tokens", prompt, expected_answer)

    non_overlapping = [t for t in answer_candidates if t not in prompt_token_ids]
    if not non_overlapping:
        overlaps = [tokenizer.decode([t]) for t in answer_candidates]
        return _fail("token_overlap", prompt, expected_answer, overlap_tokens=overlaps)

    answer_token_id = non_overlapping[0]

    top_tokens = infer_fn(prompt)

    top1 = top_tokens[0]
    expected_entry = next((t for t in top_tokens if t["id"] == answer_token_id), None)

    expected_prob = expected_entry["prob"] if expected_entry else 0.0
    expected_rank = (
        next(i for i, t in enumerate(top_tokens) if t["id"] == answer_token_id) + 1
        if expected_entry
        else TOP_N + 1
    )

    is_top1 = top1["id"] == answer_token_id
    passes_prob = expected_prob >= min_prob

    top5 = [
        {"token": t["text"].strip(), "prob": round(t["prob"], 4)}
        for t in top_tokens[:5]
    ]

    return {
        "pass": is_top1 and passes_prob,
        "is_top1": is_top1,
        "passes_prob": passes_prob,
        "expected_answer": expected_answer,
        "expected_token": tokenizer.decode([answer_token_id]),
        "expected_prob": round(expected_prob, 4),
        "expected_rank": expected_rank,
        "top1_token": top1["text"].strip(),
        "top1_prob": round(top1["prob"], 4),
        "top5": top5,
        "prompt": prompt,
    }


def _fail(reason, prompt, expected, **extra):
    return {"pass": False, "reason": reason, "prompt": prompt,
            "expected_answer": expected, **extra}


# ---------------------------------------------------------------------------
# Dataset-level validation
# ---------------------------------------------------------------------------

def validate_dataset(
    dataset_path: str, infer_fn, tokenizer, min_prob: float, model_id: str
):
    dataset = load_dataset(dataset_path)
    template = dataset["seed_prompt_template"]
    expected_field = dataset["expected_field"]
    entities = dataset["entities"]

    print(f"Validating {len(entities)} entities for '{dataset['name']}' ...")
    print(f"  Prompt template : {template}")
    print(f"  Expected field  : {expected_field}")
    print(f"  Min probability : {min_prob}")
    print()

    results = []
    passed = 0

    for entity in entities:
        prompt = template.format(**entity)
        expected = entity[expected_field]
        result = validate_entity(infer_fn, tokenizer, prompt, expected, min_prob)
        result["slug"] = entity["slug"]
        results.append(result)

        status = "PASS" if result["pass"] else "FAIL"
        detail = _format_detail(result, min_prob)
        print(f"  [{status}] {entity['slug']}: {expected}{detail}")

        if result["pass"]:
            passed += 1

    _write_reports(dataset, dataset_path, results, passed, model_id, min_prob)
    return results


def _format_detail(result: dict, min_prob: float) -> str:
    if result["pass"]:
        return ""
    reason = result.get("reason")
    if reason:
        return f" ({reason})"
    if not result.get("is_top1"):
        return (
            f" (rank={result['expected_rank']}, "
            f"top1='{result['top1_token']}' p={result['top1_prob']:.3f})"
        )
    if not result.get("passes_prob"):
        return f" (prob={result['expected_prob']:.4f} < {min_prob})"
    return ""


def _write_reports(
    dataset: dict, dataset_path: str,
    results: list, passed: int, model_id: str, min_prob: float,
):
    total = len(results)
    pct = 100 * passed / total if total else 0
    print(f"\n{'=' * 60}")
    print(f"Dataset : {dataset['name']}")
    print(f"Passed  : {passed}/{total} ({pct:.0f}%)")
    print(f"Min prob: {min_prob}")

    ds_path = Path(dataset_path)
    report = {
        "dataset": dataset["name"], "model_id": model_id,
        "min_prob": min_prob, "total": total, "passed": passed,
        "results": results,
    }
    report_path = ds_path.with_name(ds_path.stem + "_validation.json")
    with open(report_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2, ensure_ascii=False)
    print(f"Report  : {report_path}")

    if passed > 0:
        passing_slugs = {r["slug"] for r in results if r["pass"]}
        filtered = dict(dataset)
        filtered["entities"] = [
            e for e in dataset["entities"] if e["slug"] in passing_slugs
        ]
        filtered_path = ds_path.with_name(ds_path.stem + "_validated.json")
        with open(filtered_path, "w", encoding="utf-8") as f:
            json.dump(filtered, f, indent=2, ensure_ascii=False)
        print(f"Filtered: {filtered_path} ({passed} entities)")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Validate dataset entities against a language model"
    )
    parser.add_argument("datasets", nargs="+", help="Path(s) to dataset JSON file(s)")
    parser.add_argument("--model-id", default="google/gemma-2-2b")
    parser.add_argument("--min-prob", type=float, default=0.15)
    parser.add_argument(
        "--backend", choices=["local", "hf-api"], default="local",
        help="Inference backend: 'local' loads model, 'hf-api' uses HF Inference API",
    )
    parser.add_argument("--device", default=None, help="Device for local backend")
    parser.add_argument("--hf-token", default=None, help="HF token for hf-api backend")
    args = parser.parse_args()

    if args.backend == "local":
        import torch
        if args.device is None:
            args.device = "cuda" if torch.cuda.is_available() else "cpu"
        infer_fn, tokenizer = _load_local_backend(args.model_id, args.device)
    else:
        infer_fn, tokenizer = _load_hf_api_backend(args.model_id, args.hf_token)

    for ds_path in args.datasets:
        print(f"\n{'#' * 60}")
        print(f"# {ds_path}")
        print(f"{'#' * 60}\n")
        validate_dataset(ds_path, infer_fn, tokenizer, args.min_prob, args.model_id)


if __name__ == "__main__":
    main()
