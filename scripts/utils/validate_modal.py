"""
Validate all datasets against gemma-2-2b on a Modal cloud GPU.

Sends all prompts to a remote T4 for inference, then runs validation
logic locally to produce reports + filtered datasets.

Usage:
    modal run scripts/utils/validate_modal.py
    modal run scripts/utils/validate_modal.py --min-prob 0.20
"""

import json
import os
import sys
from pathlib import Path

import modal

TOP_N = 50
MODEL_ID = "google/gemma-2-2b"

app = modal.App("dataset-validator")

gpu_image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("torch", "transformers", "accelerate", "huggingface_hub")
)


@app.function(gpu="T4", image=gpu_image, timeout=600)
def run_inference(
    prompts: list[str], model_id: str, hf_token: str
) -> list[list[dict]]:
    """Load model on GPU, run a single forward pass per prompt."""
    import os
    os.environ["HF_TOKEN"] = hf_token

    import torch
    from transformers import AutoModelForCausalLM, AutoTokenizer

    print(f"Loading {model_id} on GPU ...")
    tokenizer = AutoTokenizer.from_pretrained(model_id)
    model = AutoModelForCausalLM.from_pretrained(
        model_id, torch_dtype=torch.float16, device_map="cuda"
    )
    model.eval()
    print(f"Model loaded. Processing {len(prompts)} prompts ...")

    all_results = []
    for i, prompt in enumerate(prompts):
        inputs = tokenizer(prompt, return_tensors="pt").to("cuda")
        with torch.no_grad():
            logits = model(**inputs).logits[0, -1, :]
        probs = torch.softmax(logits.float(), dim=-1)
        top_vals, top_ids = torch.topk(probs, k=TOP_N)
        tokens = [
            {"id": tid.item(), "text": tokenizer.decode([tid.item()]), "prob": p.item()}
            for tid, p in zip(top_ids, top_vals)
        ]
        all_results.append(tokens)
        if (i + 1) % 20 == 0 or (i + 1) == len(prompts):
            print(f"  {i + 1}/{len(prompts)} done")

    return all_results


@app.local_entrypoint()
def main(min_prob: float = 0.15):
    from dotenv import load_dotenv

    load_dotenv()

    from transformers import AutoTokenizer

    from scripts.utils.validate_dataset import validate_dataset

    hf_token = os.environ.get("HF_TOKEN")
    if not hf_token:
        print("ERROR: HF_TOKEN not found. Save your .env file first.")
        sys.exit(1)

    datasets_dir = Path("scripts/utils/datasets")
    dataset_files = sorted(
        f for f in datasets_dir.glob("*.json")
        if "_validation" not in f.name and "_validated" not in f.name
    )

    if not dataset_files:
        print(f"No dataset files found in {datasets_dir}")
        sys.exit(1)

    datasets = []
    all_prompts = []
    for ds_file in dataset_files:
        ds = json.loads(ds_file.read_text(encoding="utf-8"))
        template = ds["seed_prompt_template"]
        for entity in ds["entities"]:
            all_prompts.append(template.format(**entity))
        datasets.append((ds_file, ds))

    print(f"Found {len(datasets)} datasets, {len(all_prompts)} total prompts")
    print(f"Model: {MODEL_ID}  |  min_prob: {min_prob}")
    print(f"Sending to Modal GPU ...\n")

    all_top_tokens = run_inference.remote(all_prompts, MODEL_ID, hf_token)

    cache = dict(zip(all_prompts, all_top_tokens))

    def cached_infer(prompt: str) -> list[dict]:
        return cache[prompt]

    print("Loading tokenizer locally ...")
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID, token=hf_token)

    for ds_file, ds in datasets:
        print(f"\n{'#' * 60}")
        print(f"# {ds_file.name}")
        print(f"{'#' * 60}\n")
        validate_dataset(str(ds_file), cached_infer, tokenizer, min_prob, MODEL_ID)

    print("\n\nAll datasets validated.")
