#!/usr/bin/env python3
"""
Assess candidate painting entries for the paintings_painters dataset.

For each candidate in the candidates file, runs the seed prompt and reports:
  - rank and probability of the expected first name (first token)
  - top-1 prediction
  - first-token ID collisions with keep entries and within candidate set
  - near-duplicate first-name string similarity (SequenceMatcher >= 0.7)

The kept entries are the 8 clean validated paintings.
Problem slots being replaced:
  - the_scream   (Edvard Munch):  first-token near-duplicate with nighthawks (Edward Hopper)
  - grande_jatte (Georges Seurat): baseline confusion -- Georges at rank=3 (6.3%) in water_lilies

Usage:
    python -m scripts.utils.assess_painting_candidates
    python -m scripts.utils.assess_painting_candidates --candidates scripts/utils/datasets/paintings_painters_candidates.json
    python -m scripts.utils.assess_painting_candidates --min-prob 0.15 --top-k 20
"""

import argparse
import json
import os
from difflib import SequenceMatcher

from dotenv import load_dotenv

load_dotenv()

# Current clean validated entries (keeping these, not replacing).
KEEP_ENTRIES = [
    {"slug": "water_lilies",          "first_name": "Claude",    "first_token": "Claude"},
    {"slug": "starry_night",          "first_name": "Vincent",   "first_token": "Vincent"},
    {"slug": "persistence_of_memory", "first_name": "Salvador",  "first_token": "Salvador"},
    {"slug": "campbells_soup",        "first_name": "Andy",      "first_token": "Andy"},
    {"slug": "guernica",              "first_name": "Pablo",     "first_token": "Pablo"},
    {"slug": "girl_pearl_earring",    "first_name": "Johannes",  "first_token": "Johannes"},
    {"slug": "birth_of_venus",        "first_name": "Sandro",    "first_token": "Sandro"},
    {"slug": "nighthawks",            "first_name": "Edward",    "first_token": "Edward"},
]

REPLACING_ENTRIES = [
    {
        "slug": "the_scream",
        "first_name": "Edvard",
        "first_token": "Ed",
        "reason": "near-duplicate with nighthawks (Edward), SequenceMatcher=0.83; first token 'Ed' is prefix of 'Edward'",
    },
    {
        "slug": "grande_jatte",
        "first_name": "Georges",
        "first_token": "Georges",
        "reason": "baseline confusion: 'Georges' at rank=3 (prob=6.3%) in water_lilies prompt before any intervention",
    },
]

DEFAULT_CANDIDATES = os.path.join(
    os.path.dirname(__file__),
    "datasets",
    "paintings_painters_candidates.json",
)
DEFAULT_MODEL = "google/gemma-2-2b"
DEFAULT_MIN_PROB = 0.15
DEFAULT_TOP_K = 20
NEAR_DUP_THRESHOLD = 0.7


def load_candidates(path: str) -> list[dict]:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    template = data["seed_prompt_template"]
    return [
        {**entity, "_prompt": template.format(**entity)}
        for entity in data["entities"]
    ]


def probe_all(model, tokenizer, device: str, candidates: list[dict], top_k: int) -> list[dict]:
    import torch

    results = []
    for candidate in candidates:
        prompt = candidate["_prompt"]
        encoded = tokenizer(prompt, return_tensors="pt")
        encoded = {k: v.to(device) for k, v in encoded.items()}
        with torch.no_grad():
            outputs = model(**encoded)
        last_logits = outputs.logits[0, -1]
        probs = torch.softmax(last_logits.float(), dim=-1)
        top_probs, top_ids = torch.topk(probs, k=top_k)
        top1_token = tokenizer.decode([top_ids[0].item()])
        top1_prob = float(top_probs[0].item())

        first_name = candidate["first_name"]
        best_rank, best_prob, best_token_id = None, 0.0, None
        for prefix in (" ", ""):
            ids = tokenizer.encode(prefix + first_name, add_special_tokens=False)
            if not ids:
                continue
            tid = ids[0]
            p = float(probs[tid].item())
            if p > best_prob:
                best_prob = p
                best_token_id = tid
        if best_token_id is not None:
            best_rank = int((probs > best_prob).sum().item() + 1)

        first_token_str = (
            tokenizer.decode([best_token_id]).strip()
            if best_token_id is not None
            else "?"
        )

        results.append(
            {
                "slug": candidate["slug"],
                "painting": candidate["painting"],
                "painter": candidate["painter"],
                "first_name": first_name,
                "target_slot": candidate.get("target_slot", ""),
                "notes": candidate.get("notes", ""),
                "prompt": prompt,
                "rank": best_rank,
                "prob": best_prob,
                "top1_token": top1_token,
                "top1_prob": top1_prob,
                "first_token": first_token_str,
            }
        )
    return results


def _name_sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def compute_flags(results: list[dict]) -> list[dict]:
    keep_first_tokens = {e["first_token"] for e in KEEP_ENTRIES}
    keep_first_names = [e["first_name"] for e in KEEP_ENTRIES]

    candidate_token_map: dict[str, list[str]] = {}
    for r in results:
        ft = r["first_token"]
        candidate_token_map.setdefault(ft, []).append(r["slug"])

    candidate_name_map: dict[str, str] = {r["slug"]: r["first_name"] for r in results}

    for r in results:
        flags = []

        if r["first_token"] in keep_first_tokens:
            matched = [e["slug"] for e in KEEP_ENTRIES if e["first_token"] == r["first_token"]]
            flags.append(f"token-clash-keep:{','.join(matched)}")

        for kn in keep_first_names:
            sim = _name_sim(r["first_name"], kn)
            if sim >= NEAR_DUP_THRESHOLD:
                keep_slug = next(e["slug"] for e in KEEP_ENTRIES if e["first_name"] == kn)
                flags.append(f"near-dup-keep:{keep_slug}(sim={sim:.2f})")

        token_peers = [s for s in candidate_token_map.get(r["first_token"], []) if s != r["slug"]]
        if token_peers:
            flags.append(f"token-clash-candidates:{','.join(token_peers)}")

        for other_slug, other_name in candidate_name_map.items():
            if other_slug == r["slug"]:
                continue
            sim = _name_sim(r["first_name"], other_name)
            if sim >= NEAR_DUP_THRESHOLD:
                flags.append(f"near-dup-candidates:{other_slug}(sim={sim:.2f})")

        r["flags"] = flags
    return results


def _is_clean(r: dict, min_prob: float) -> bool:
    return (
        r["rank"] == 1
        and r["prob"] >= min_prob
        and not any("clash" in f or "near-dup" in f for f in r["flags"])
    )


def print_report(results: list[dict], min_prob: float):
    print()
    print("=" * 110)
    print("PAINTING CANDIDATE ASSESSMENT REPORT")
    print(f"Model threshold : rank=1, prob>={min_prob:.2f}, no first-token or near-dup clash")
    print("=" * 110)

    print()
    print("Keep entries (reference):")
    print("-" * 70)
    for e in KEEP_ENTRIES:
        print(f"  {e['slug']:<26} first_name={e['first_name']:<12} first_token={e['first_token']}")
    print()
    print("Entries being replaced:")
    print("-" * 70)
    for e in REPLACING_ENTRIES:
        print(f"  {e['slug']:<26} first_name={e['first_name']:<12} reason: {e['reason']}")

    print()
    print("Candidate results:")
    print("-" * 110)
    header = (
        f"  {'slug':<30} {'first_name':<14} {'rnk':>4} {'prob':>7}"
        f"  {'top1':<14} {'ft':<14} {'pass':<5}  flags"
    )
    print(header)
    print("-" * 110)

    prev_slot = None
    for r in sorted(results, key=lambda x: x["target_slot"]):
        slot = r["target_slot"]
        if slot != prev_slot:
            print(f"  -- slot: {slot} --")
            prev_slot = slot
        passed = _is_clean(r, min_prob)
        flag_str = ", ".join(r["flags"]) if r["flags"] else "ok"
        print(
            f"  {r['slug']:<30} {r['first_name']:<14} {(r['rank'] if r['rank'] else '?'):>4}"
            f" {r['prob']:>7.4f}  {repr(r['top1_token']):<14} {r['first_token']:<14}"
            f" {'PASS' if passed else 'FAIL':<5}  {flag_str}"
        )
    print()


def print_recommendations(results: list[dict], min_prob: float):
    print("=" * 80)
    print("RECOMMENDATION SUMMARY")
    print("=" * 80)
    print()

    slot_labels = {
        "replace_the_scream": "the_scream (Edvard Munch -- near-dup with Edward/nighthawks)",
        "replace_grande_jatte": "grande_jatte (Georges Seurat -- baseline confusion in water_lilies)",
    }

    for slot, label in slot_labels.items():
        clean = [r for r in results if r["target_slot"] == slot and _is_clean(r, min_prob)]
        print(f"  Replace {label}")
        if clean:
            best = max(clean, key=lambda x: x["prob"])
            print(f"    Top clean candidate: {best['slug']}")
            print(f"      painting   : {best['painting']}")
            print(f"      painter    : {best['painter']}")
            print(f"      first_name : {best['first_name']}  (first_token='{best['first_token']}')")
            print(f"      rank={best['rank']}, prob={best['prob']:.4f}")
            if len(clean) > 1:
                others = [r for r in clean if r["slug"] != best["slug"]]
                print(f"    Other clean candidates: {', '.join(r['slug'] for r in others)}")
        else:
            print("    -> no clean candidate found for this slot")
        print()


def parse_args():
    parser = argparse.ArgumentParser(description="Assess painting candidate replacements")
    parser.add_argument("--candidates", default=DEFAULT_CANDIDATES)
    parser.add_argument("--model-id", default=DEFAULT_MODEL)
    parser.add_argument("--device", default=None)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument("--min-prob", type=float, default=DEFAULT_MIN_PROB)
    parser.add_argument("--json", action="store_true", help="Dump raw results as JSON")
    return parser.parse_args()


def main():
    args = parse_args()

    import torch
    from scripts.utils.prompt_probe import load_local_backend

    if args.device is None:
        args.device = "cuda" if torch.cuda.is_available() else "cpu"

    print(f"Loading model {args.model_id} on {args.device} ...")
    model, tokenizer = load_local_backend(args.model_id, args.device)

    print(f"Loading candidates from {args.candidates} ...")
    candidates = load_candidates(args.candidates)
    print(f"  {len(candidates)} candidates loaded.")

    print("Running probes ...")
    results = probe_all(model, tokenizer, args.device, candidates, args.top_k)
    results = compute_flags(results)

    print_report(results, args.min_prob)
    print_recommendations(results, args.min_prob)

    if args.json:
        out_path = args.candidates.replace(".json", "_assessment.json")
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(results, f, indent=2, ensure_ascii=False)
        print(f"Raw results written to {out_path}")


if __name__ == "__main__":
    main()
