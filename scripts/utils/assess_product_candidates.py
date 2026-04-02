#!/usr/bin/env python3
"""
Assess candidate product/founder entries for the products_founders dataset.

For each candidate, runs the seed prompt and reports:
  - rank and probability of the expected founder (first token)
  - top-1 prediction
  - first-token collisions with keep entries and within candidate set
  - near-duplicate founder-name similarity (SequenceMatcher >= 0.7)
  - product==company field collapse flag
  - cross-contamination: rank of each keep entry's founder first token in the
    candidate's prompt (flags any with rank <= 5 as baseline confusion risk)

Keep entries: 10 clean validated entries (twitter and nike_shoes removed).
Problem slots:
  - twitter   (Jack Dorsey): product==company AND first-token "Jack" clash with
    alibaba; both cross-pairs had baseline rank=1 (prob 34-36%)
  - nike_shoes (Phil Knight): baseline confusion -- "Bill" (Gates, windows) at
    rank=2 (prob=19.8%) in the nike_shoes prompt

Usage:
    python -m scripts.utils.assess_product_candidates
    python -m scripts.utils.assess_product_candidates --candidates scripts/utils/datasets/products_founders_candidates.json
    python -m scripts.utils.assess_product_candidates --min-prob 0.15 --top-k 20
"""

import argparse
import json
import os
from difflib import SequenceMatcher

from dotenv import load_dotenv

load_dotenv()

# Validated entries that remain after removing the two problem slugs.
KEEP_ENTRIES = [
    {"slug": "iphone",    "founder": "Steve Jobs",      "first_token": "Steve"},
    {"slug": "windows",   "founder": "Bill Gates",      "first_token": "Bill"},
    {"slug": "model_s",   "founder": "Elon Musk",       "first_token": "Elon"},
    {"slug": "facebook",  "founder": "Mark Zuckerberg", "first_token": "Mark"},
    {"slug": "oracle_db", "founder": "Larry Ellison",   "first_token": "Larry"},
    {"slug": "dell_xps",  "founder": "Michael Dell",    "first_token": "Michael"},
    {"slug": "alibaba",   "founder": "Jack Ma",         "first_token": "Jack"},
    {"slug": "dyson",     "founder": "James Dyson",     "first_token": "James"},
    {"slug": "wordpress", "founder": "Matt Mullenweg",  "first_token": "Matt"},
    {"slug": "oculus",    "founder": "Palmer Luckey",   "first_token": "Palmer"},
]

REPLACING_ENTRIES = [
    {
        "slug": "twitter",
        "founder": "Jack Dorsey",
        "first_token": "Jack",
        "reason": "product==company (both 'Twitter') AND first-token 'Jack' clash with alibaba; cross-pairs at baseline rank=1 (34-36%)",
    },
    {
        "slug": "nike_shoes",
        "founder": "Phil Knight",
        "first_token": "Phil",
        "reason": "baseline confusion: 'Bill' (windows/Gates) at rank=2 (prob=19.8%) in the nike_shoes prompt",
    },
]

DEFAULT_CANDIDATES = os.path.join(
    os.path.dirname(__file__),
    "datasets",
    "products_founders_candidates.json",
)
DEFAULT_MODEL = "google/gemma-2-2b"
DEFAULT_MIN_PROB = 0.15
DEFAULT_TOP_K = 30
NEAR_DUP_THRESHOLD = 0.7
CROSS_WARN_RANK = 5


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

    keep_token_ids: dict[str, int] = {}
    for entry in KEEP_ENTRIES:
        for prefix in (" ", ""):
            ids = tokenizer.encode(prefix + entry["first_token"], add_special_tokens=False)
            if ids:
                keep_token_ids[entry["first_token"]] = ids[0]
                break

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

        founder = candidate["founder"]
        best_rank, best_prob, best_token_id = None, 0.0, None
        for prefix in (" ", ""):
            ids = tokenizer.encode(prefix + founder, add_special_tokens=False)
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

        cross = {}
        for entry in KEEP_ENTRIES:
            tid = keep_token_ids.get(entry["first_token"])
            if tid is None:
                cross[entry["first_token"]] = {"rank": None, "prob": 0.0}
                continue
            p = float(probs[tid].item())
            rank = int((probs > p).sum().item() + 1)
            cross[entry["first_token"]] = {"rank": rank, "prob": p}

        results.append(
            {
                "slug": candidate["slug"],
                "product": candidate["product"],
                "company": candidate["company"],
                "founder": founder,
                "target_slot": candidate.get("target_slot", ""),
                "notes": candidate.get("notes", ""),
                "prompt": prompt,
                "rank": best_rank,
                "prob": best_prob,
                "top1_token": top1_token,
                "top1_prob": top1_prob,
                "first_token": first_token_str,
                "cross": cross,
            }
        )
    return results


def _name_sim(a: str, b: str) -> float:
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def compute_flags(results: list[dict]) -> list[dict]:
    keep_first_tokens = {e["first_token"] for e in KEEP_ENTRIES}
    keep_first_names = [e["first_token"] for e in KEEP_ENTRIES]

    candidate_token_map: dict[str, list[str]] = {}
    for r in results:
        ft = r["first_token"]
        candidate_token_map.setdefault(ft, []).append(r["slug"])

    candidate_name_map: dict[str, str] = {r["slug"]: r["first_token"] for r in results}

    for r in results:
        flags = []

        if r["product"] == r["company"]:
            flags.append("product-eq-company")

        if r["first_token"] in keep_first_tokens:
            matched = [e["slug"] for e in KEEP_ENTRIES if e["first_token"] == r["first_token"]]
            flags.append(f"token-clash-keep:{','.join(matched)}")

        for kn in keep_first_names:
            sim = _name_sim(r["first_token"], kn)
            if sim >= NEAR_DUP_THRESHOLD:
                keep_slug = next(e["slug"] for e in KEEP_ENTRIES if e["first_token"] == kn)
                flags.append(f"near-dup-keep:{keep_slug}(sim={sim:.2f})")

        token_peers = [s for s in candidate_token_map.get(r["first_token"], []) if s != r["slug"]]
        if token_peers:
            flags.append(f"token-clash-candidates:{','.join(token_peers)}")

        for other_slug, other_ft in candidate_name_map.items():
            if other_slug == r["slug"]:
                continue
            sim = _name_sim(r["first_token"], other_ft)
            if sim >= NEAR_DUP_THRESHOLD:
                flags.append(f"near-dup-candidates:{other_slug}(sim={sim:.2f})")

        for keep_ft, stats in r["cross"].items():
            rank = stats.get("rank")
            if rank is not None and rank <= CROSS_WARN_RANK:
                keep_slug = next(e["slug"] for e in KEEP_ENTRIES if e["first_token"] == keep_ft)
                flags.append(f"cross-rank-warn:{keep_slug}({keep_ft}@rank{rank},p={stats['prob']:.3f})")

        r["flags"] = flags
    return results


def _is_clean(r: dict, min_prob: float) -> bool:
    blocking = {"product-eq-company", "token-clash", "near-dup-keep", "cross-rank-warn"}
    bad_flags = [
        f for f in r["flags"]
        if any(f.startswith(b) for b in blocking)
    ]
    return r["rank"] == 1 and r["prob"] >= min_prob and not bad_flags


def print_report(results: list[dict], min_prob: float):
    print()
    print("=" * 120)
    print("PRODUCT CANDIDATE ASSESSMENT REPORT")
    print(f"Model threshold : rank=1, prob>={min_prob:.2f}, no clash/near-dup/product-eq-company/cross-rank-warn(rank<={CROSS_WARN_RANK})")
    print("=" * 120)

    print()
    print("Keep entries (reference):")
    print("-" * 70)
    for e in KEEP_ENTRIES:
        print(f"  {e['slug']:<18} {e['founder']:<24} first_token={e['first_token']}")
    print()
    print("Entries being replaced:")
    print("-" * 70)
    for e in REPLACING_ENTRIES:
        print(f"  {e['slug']:<18} {e['founder']:<24} reason: {e['reason']}")

    print()
    print("Candidate results (cross = rank of keep-entry first tokens in candidate's prompt):")
    print("-" * 120)
    header = (
        f"  {'slug':<22} {'founder':<22} {'rnk':>4} {'prob':>7}"
        f"  {'top1':<14} {'ft':<12} {'pass':<5}  flags"
    )
    print(header)
    print("-" * 120)

    cross_header = "    cross: " + "  ".join(
        f"{e['first_token']}" for e in KEEP_ENTRIES
    )

    prev_slot = None
    for r in sorted(results, key=lambda x: x["target_slot"]):
        slot = r["target_slot"]
        if slot != prev_slot:
            print(f"  -- slot: {slot} --")
            prev_slot = slot
        passed = _is_clean(r, min_prob)
        flag_str = ", ".join(r["flags"]) if r["flags"] else "ok"
        print(
            f"  {r['slug']:<22} {r['founder']:<22}"
            f" {(r['rank'] if r['rank'] else '?'):>4} {r['prob']:>7.4f}"
            f"  {repr(r['top1_token']):<14} {r['first_token']:<12}"
            f" {'PASS' if passed else 'FAIL':<5}  {flag_str}"
        )
        cross_vals = "  ".join(
            f"{e['first_token']}@{r['cross'].get(e['first_token'], {}).get('rank', '?')}"
            for e in KEEP_ENTRIES
        )
        print(f"    cross: {cross_vals}")
    print()


def print_recommendations(results: list[dict], min_prob: float):
    print("=" * 80)
    print("RECOMMENDATION SUMMARY")
    print("=" * 80)
    print()

    slot_labels = {
        "replace_twitter": "twitter (Jack Dorsey -- product==company + Jack clash with alibaba)",
        "replace_nike_shoes": "nike_shoes (Phil Knight -- Bill/Gates at rank=2 in baseline)",
        "replace_either": "replace_either slot (general additions)",
    }

    for slot, label in slot_labels.items():
        slot_candidates = [r for r in results if r["target_slot"] == slot]
        if not slot_candidates:
            continue
        clean = [r for r in slot_candidates if _is_clean(r, min_prob)]
        print(f"  Slot: {label}")
        if clean:
            best = max(clean, key=lambda x: x["prob"])
            print(f"    Top clean candidate: {best['slug']}")
            print(f"      product    : {best['product']}")
            print(f"      company    : {best['company']}")
            print(f"      founder    : {best['founder']}  (first_token='{best['first_token']}')")
            print(f"      rank={best['rank']}, prob={best['prob']:.4f}")
            if len(clean) > 1:
                others = [r for r in clean if r["slug"] != best["slug"]]
                print(f"    Other clean candidates: {', '.join(r['slug'] for r in others)}")
        else:
            print("    -> no clean candidate found for this slot")
        print()


def parse_args():
    parser = argparse.ArgumentParser(description="Assess product/founder candidate replacements")
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
