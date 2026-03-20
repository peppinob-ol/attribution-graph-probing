#!/usr/bin/env python3
"""
Inspect next-token predictions for an ad hoc prompt or dataset template.

Examples:
    python -m scripts.utils.prompt_probe --prompt "The capital of the state containing Dallas is"
    python -m scripts.utils.prompt_probe --prompt "The capital of the state containing Dallas is" --positions 3 --top-k 10 --target Austin
    python -m scripts.utils.prompt_probe --dataset scripts/utils/datasets/songs_lead_singers.json --slug wonderwall
    python -m scripts.utils.prompt_probe --dataset scripts/utils/datasets/songs_lead_singers.json --slug wonderwall --probe-id probe_band
    python -m scripts.utils.prompt_probe --interactive --target Austin
"""

import argparse
import json
import math
import os

from dotenv import load_dotenv

load_dotenv()


def load_dataset(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_local_backend(model_id: str, device: str):
    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"Loading model {model_id} on {device} ...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)

    model_kwargs = {}
    if device.startswith("cuda"):
        model_kwargs["torch_dtype"] = torch.float16

    model = AutoModelForCausalLM.from_pretrained(model_id, **model_kwargs)
    model.to(device)
    model.eval()
    return model, tokenizer


def load_hf_api_backend(model_id: str, hf_token: str | None):
    from huggingface_hub import InferenceClient
    from transformers import AutoTokenizer

    token = hf_token or os.environ.get("HF_TOKEN")
    if not token:
        raise ValueError(
            "HF API backend requires a token. "
            "Set HF_TOKEN env var or pass --hf-token."
        )

    print(f"Using HF Inference API for {model_id}")
    tokenizer = AutoTokenizer.from_pretrained(model_id, token=token)
    client = InferenceClient(model=model_id, token=token)
    return client, tokenizer


def format_token(token: str) -> str:
    return repr(token)


def input_with_prefill(prompt_text: str, default_text: str) -> str:
    if not default_text:
        return input(prompt_text)

    try:
        import readline
    except ImportError:
        return input(prompt_text)

    def startup_hook():
        readline.insert_text(default_text)

    readline.set_startup_hook(startup_hook)
    try:
        return input(prompt_text)
    finally:
        readline.set_startup_hook(None)


def apply_interactive_edit(current_prompt: str, command: str) -> tuple[str, str]:
    if not command:
        if not current_prompt:
            raise ValueError("Prompt is empty. Type a prompt, or use /exit.")
        return current_prompt, "reused previous prompt"

    if command.startswith("+ "):
        if not current_prompt:
            raise ValueError("No existing prompt to extend. Type a full prompt first.")
        return current_prompt + command[1:], "appended text"

    if command.startswith("s/"):
        parts = command.split("/", 3)
        if len(parts) != 4:
            raise ValueError("Invalid substitution syntax. Use: s/old/new/")
        _, old, new, _ = parts
        if not old:
            raise ValueError("Substitution requires a non-empty 'old' string.")
        if old not in current_prompt:
            raise ValueError(f"Substring not found in current prompt: {old!r}")
        return current_prompt.replace(old, new, 1), f"replaced {old!r} with {new!r}"

    return command, "replaced prompt"


def truncate_text(text: str, max_len: int = 80) -> str:
    if len(text) <= max_len:
        return text
    return "..." + text[-(max_len - 3):]


def resolve_target_candidates(tokenizer, target: str) -> list[int]:
    candidates = []
    for prefix in (" ", ""):
        token_ids = tokenizer.encode(prefix + target, add_special_tokens=False)
        if token_ids and token_ids[0] not in candidates:
            candidates.append(token_ids[0])
    return candidates


def collect_target_stats_from_probs(tokenizer, probs, logits, target_texts: list[str]) -> list[dict]:
    target_stats = []
    for target_text in target_texts:
        candidate_ids = resolve_target_candidates(tokenizer, target_text)
        if not candidate_ids:
            target_stats.append(
                {
                    "target": target_text,
                    "matched": False,
                    "reason": "no_token_candidates",
                }
            )
            continue

        best_token_id = max(candidate_ids, key=lambda token_id: float(probs[token_id].item()))
        prob = float(probs[best_token_id].item())
        rank = int((probs > prob).sum().item() + 1)
        target_stats.append(
            {
                "target": target_text,
                "matched": True,
                "token_id": int(best_token_id),
                "token": tokenizer.decode([best_token_id]),
                "logit": float(logits[best_token_id].item()),
                "prob": prob,
                "rank": rank,
            }
        )
    return target_stats


def probe_prompt_local(
    model,
    tokenizer,
    device: str,
    prompt: str,
    positions: int,
    top_k: int,
    target_texts: list[str],
) -> dict:
    import torch

    encoded = tokenizer(prompt, return_tensors="pt")
    encoded = {key: value.to(device) for key, value in encoded.items()}

    with torch.no_grad():
        outputs = model(**encoded)

    input_ids = encoded["input_ids"][0]
    logits = outputs.logits[0]
    tokens = [tokenizer.decode([token_id]) for token_id in input_ids.tolist()]
    seq_len = len(tokens)
    positions = max(1, min(positions, seq_len))

    inspected_positions = []
    for token_index in range(seq_len - positions, seq_len):
        pos_logits = logits[token_index]
        probs = torch.softmax(pos_logits.float(), dim=-1)
        top_probs, top_ids = torch.topk(probs, k=top_k)

        top_predictions = []
        for rank_index, (token_id, prob) in enumerate(zip(top_ids.tolist(), top_probs.tolist()), start=1):
            top_predictions.append(
                {
                    "rank": rank_index,
                    "token_id": token_id,
                    "token": tokenizer.decode([token_id]),
                    "logit": float(pos_logits[token_id].item()),
                    "prob": float(prob),
                }
            )

        actual_next_token = tokenizer.decode([input_ids[token_index + 1].item()]) if token_index + 1 < seq_len else None
        inspected_positions.append(
            {
                "token_index": token_index,
                "prefix_tail": truncate_text(
                    tokenizer.decode(input_ids[: token_index + 1], skip_special_tokens=False)
                ),
                "prompt_token": tokens[token_index],
                "actual_next_token": actual_next_token,
                "top_predictions": top_predictions,
                "targets": collect_target_stats_from_probs(
                    tokenizer=tokenizer,
                    probs=probs,
                    logits=pos_logits,
                    target_texts=target_texts,
                ),
            }
        )

    return {
        "backend": "local",
        "prompt": prompt,
        "tokens": [{"index": i, "token": token} for i, token in enumerate(tokens)],
        "positions": inspected_positions,
    }


def probe_prompt_hf_api(
    client,
    tokenizer,
    prompt: str,
    top_k: int,
    target_texts: list[str],
) -> dict:
    response = client.text_generation(
        prompt,
        max_new_tokens=1,
        details=True,
        top_n_tokens=top_k,
        temperature=None,
    )
    top_tokens = response.details.top_tokens[0]

    top_predictions = []
    for rank_index, token_info in enumerate(top_tokens, start=1):
        top_predictions.append(
            {
                "rank": rank_index,
                "token_id": int(token_info.id),
                "token": token_info.text,
                "logprob": float(token_info.logprob),
                "prob": float(math.exp(token_info.logprob)),
            }
        )

    target_stats = []
    for target_text in target_texts:
        candidate_ids = resolve_target_candidates(tokenizer, target_text)
        matching_entries = [entry for entry in top_predictions if entry["token_id"] in candidate_ids]
        if not matching_entries:
            target_stats.append(
                {
                    "target": target_text,
                    "matched": False,
                    "reason": "not_in_top_k",
                }
            )
            continue
        best_entry = max(matching_entries, key=lambda entry: entry["prob"])
        target_stats.append(
            {
                "target": target_text,
                "matched": True,
                "token_id": best_entry["token_id"],
                "token": best_entry["token"],
                "logprob": best_entry["logprob"],
                "prob": best_entry["prob"],
                "rank": best_entry["rank"],
            }
        )

    encoded = tokenizer(prompt, add_special_tokens=True)
    tokens = [tokenizer.decode([token_id]) for token_id in encoded]

    return {
        "backend": "hf-api",
        "prompt": prompt,
        "tokens": [{"index": i, "token": token} for i, token in enumerate(tokens)],
        "positions": [
            {
                "token_index": len(tokens) - 1 if tokens else 0,
                "prefix_tail": truncate_text(prompt),
                "prompt_token": tokens[-1] if tokens else "",
                "actual_next_token": None,
                "top_predictions": top_predictions,
                "targets": target_stats,
            }
        ],
    }


def build_prompt_from_dataset(dataset_path: str, slug: str, probe_id: str | None) -> tuple[str, list[str], dict]:
    dataset = load_dataset(dataset_path)
    entity = next((item for item in dataset["entities"] if item["slug"] == slug), None)
    if entity is None:
        raise ValueError(f"Slug '{slug}' not found in {dataset_path}")

    if probe_id:
        template = next((item for item in dataset.get("probe_templates", []) if item["id"] == probe_id), None)
        if template is None:
            raise ValueError(f"Probe id '{probe_id}' not found in dataset")
        prompt = template["text"].format(**entity)
        targets = []
    else:
        prompt = dataset["seed_prompt_template"].format(**entity)
        expected_field = dataset.get("expected_field")
        targets = [entity[expected_field]] if expected_field and expected_field in entity else []

    metadata = {
        "dataset": dataset.get("name"),
        "slug": slug,
        "probe_id": probe_id,
        "entity": entity,
    }
    return prompt, targets, metadata


def print_report(report: dict):
    print()
    print("=" * 80)
    print(f"Prompt: {report['prompt']}")
    print(f"Backend: {report['backend']}")
    print("=" * 80)
    print("Prompt tokens:")
    for token_info in report["tokens"]:
        print(f"  [{token_info['index']:>2}] {format_token(token_info['token'])}")

    print()
    print("Inspected positions:")
    for position in report["positions"]:
        print("-" * 80)
        print(f"Token index     : {position['token_index']}")
        print(f"Prompt token    : {format_token(position['prompt_token'])}")
        if position["actual_next_token"] is not None:
            print(f"Actual next     : {format_token(position['actual_next_token'])}")
        print(f"Prefix tail     : {position['prefix_tail']}")
        print("Top predictions :")
        for prediction in position["top_predictions"]:
            if "logit" in prediction:
                print(
                    "  "
                    f"{prediction['rank']:>2}. "
                    f"{format_token(prediction['token'])} "
                    f"(id={prediction['token_id']}, logit={prediction['logit']:.4f}, prob={prediction['prob']:.6f})"
                )
            else:
                print(
                    "  "
                    f"{prediction['rank']:>2}. "
                    f"{format_token(prediction['token'])} "
                    f"(id={prediction['token_id']}, logprob={prediction['logprob']:.4f}, prob={prediction['prob']:.6f})"
                )

        if position["targets"]:
            print("Target tokens   :")
            for target in position["targets"]:
                if not target.get("matched"):
                    reason = target.get("reason", "unknown")
                    print(f"  {target['target']!r} -> not found ({reason})")
                    continue
                if "logit" in target:
                    print(
                        "  "
                        f"{target['target']!r} -> {format_token(target['token'])} "
                        f"(id={target['token_id']}, rank={target['rank']}, "
                        f"logit={target['logit']:.4f}, prob={target['prob']:.6f})"
                    )
                else:
                    print(
                        "  "
                        f"{target['target']!r} -> {format_token(target['token'])} "
                        f"(id={target['token_id']}, rank={target['rank']}, "
                        f"logprob={target['logprob']:.4f}, prob={target['prob']:.6f})"
                    )


def parse_args():
    parser = argparse.ArgumentParser(
        description="Inspect next-token probabilities for a prompt or dataset row"
    )
    parser.add_argument("--prompt", help="Prompt text to inspect")
    parser.add_argument("--dataset", help="Dataset JSON path")
    parser.add_argument("--slug", help="Entity slug inside dataset")
    parser.add_argument(
        "--probe-id",
        help="Optional dataset probe template id; default uses seed_prompt_template",
    )
    parser.add_argument(
        "--target",
        action="append",
        default=[],
        help="Token string to track explicitly; can be passed multiple times",
    )
    parser.add_argument("--model-id", default="google/gemma-2-2b")
    parser.add_argument("--top-k", type=int, default=10)
    parser.add_argument(
        "--positions",
        type=int,
        default=1,
        help="Inspect the last N prompt positions",
    )
    parser.add_argument(
        "--backend",
        choices=["local", "hf-api"],
        default="local",
        help="Inference backend",
    )
    parser.add_argument("--device", default=None, help="Device for local backend")
    parser.add_argument("--hf-token", default=None, help="HF token for hf-api backend")
    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Keep model loaded and inspect prompts from stdin",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Print JSON instead of formatted text",
    )
    return parser.parse_args()


def validate_args(args):
    if not args.prompt and not args.dataset and not args.interactive:
        raise ValueError("Provide --prompt, or --dataset with --slug, or use --interactive.")

    if args.dataset and not args.slug:
        raise ValueError("--dataset requires --slug")

    if args.slug and not args.dataset:
        raise ValueError("--slug requires --dataset")

    if args.backend == "hf-api" and args.positions != 1:
        raise ValueError("HF API backend currently supports only --positions 1")

    if args.top_k <= 0:
        raise ValueError("--top-k must be > 0")

    if args.positions <= 0:
        raise ValueError("--positions must be > 0")


def run_single_prompt(args, backend, tokenizer, prompt: str, target_texts: list[str], metadata: dict | None = None):
    if args.backend == "local":
        report = probe_prompt_local(
            model=backend,
            tokenizer=tokenizer,
            device=args.device,
            prompt=prompt,
            positions=args.positions,
            top_k=args.top_k,
            target_texts=target_texts,
        )
    else:
        report = probe_prompt_hf_api(
            client=backend,
            tokenizer=tokenizer,
            prompt=prompt,
            top_k=args.top_k,
            target_texts=target_texts,
        )

    if metadata:
        report["metadata"] = metadata

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        if metadata:
            print(f"Context: {json.dumps(metadata, ensure_ascii=True)}")
        print_report(report)


def main():
    args = parse_args()
    validate_args(args)

    if args.backend == "local":
        import torch

        if args.device is None:
            args.device = "cuda" if torch.cuda.is_available() else "cpu"
        backend, tokenizer = load_local_backend(args.model_id, args.device)
    else:
        backend, tokenizer = load_hf_api_backend(args.model_id, args.hf_token)

    if args.dataset:
        prompt, dataset_targets, metadata = build_prompt_from_dataset(
            dataset_path=args.dataset,
            slug=args.slug,
            probe_id=args.probe_id,
        )
        target_texts = args.target or dataset_targets
        run_single_prompt(args, backend, tokenizer, prompt, target_texts, metadata)
        return

    if args.prompt:
        run_single_prompt(args, backend, tokenizer, args.prompt, args.target)
        if not args.interactive:
            return

    if args.interactive:
        current_prompt = args.prompt or ""
        print("Interactive prompt probe.")
        print("The previous prompt is prefilled so you can edit it directly.")
        print("Press Enter to reuse it as-is.")
        print("If you want a command like /clear or /show, clear the line first.")
        print("Commands: /show prints the current prompt, /clear resets it, /exit quits.")
        while True:
            try:
                command = input_with_prefill("prompt> ", current_prompt)
            except EOFError:
                print()
                break

            command = command.strip()
            if command == "/exit":
                break

            if command == "/clear":
                current_prompt = ""
                print("Prompt cleared.")
                continue

            if command == "/show":
                if current_prompt:
                    print(f"Current prompt: {current_prompt}")
                else:
                    print("Current prompt is empty.")
                continue

            try:
                current_prompt, action = apply_interactive_edit(current_prompt, command)
            except ValueError as exc:
                print(exc)
                continue

            print(f"[{action}] {current_prompt}")
            run_single_prompt(args, backend, tokenizer, current_prompt, args.target)


if __name__ == "__main__":
    main()
