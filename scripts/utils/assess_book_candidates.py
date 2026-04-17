#!/usr/bin/env python3
"""
Assess candidate book-character-author entries against the model.

For each candidate in a dataset file, runs the seed prompt and reports:
  - rank and probability of the expected author (first token)
  - top-1 prediction token
  - any structural flags (J.-initial author, character == book, duplicate author)
  - first-token collisions within the candidate set and with the kept entries

The kept entries are the non-problematic subset of the validated dataset.
Problematic entries being replaced: hermione_granger, frodo_baggins,
holden_caulfield, scout_finch, don_quixote, oliver_twist, anna_karenina.

Usage:
    python -m scripts.utils.assess_book_candidates
    python -m scripts.utils.assess_book_candidates --candidates scripts/utils/datasets/book_characters_authors_candidates.json
    python -m scripts.utils.assess_book_candidates --top-k 20 --min-prob 0.15
"""

import argparse
import json
import os
import sys

from dotenv import load_dotenv

load_dotenv()

KEEP_ENTRIES = [
    {"slug": "jay_gatsby",        "author": "F. Scott Fitzgerald", "first_token": "F"},
    {"slug": "elizabeth_bennet",  "author": "Jane Austen",          "first_token": "Jane"},
    {"slug": "huckleberry_finn",  "author": "Mark Twain",           "first_token": "Mark"},
    {"slug": "captain_ahab",      "author": "Herman Melville",      "first_token": "Herman"},
    {"slug": "raskolnikov",       "author": "Fyodor Dostoevsky",    "first_token": "Fy"},
    {"slug": "dracula",           "author": "Bram Stoker",          "first_token": "Bram"},
    {"slug": "katniss_everdeen",  "author": "Suzanne Collins",      "first_token": "Suzanne"},
    {"slug": "winston_smith",     "author": "George Orwell",        "first_token": "George"},
    {"slug": "atticus_finch",     "author": "Harper Lee",           "first_token": "Harper"},
]

REPLACING_SLUGS = {
    "hermione_granger", "frodo_baggins", "holden_caulfield",
    "scout_finch", "don_quixote", "oliver_twist", "anna_karenina",
}

DEFAULT_CANDIDATES = os.path.join(
    os.path.dirname(__file__),
    "datasets",
    "book_characters_authors_candidates.json",
)
DEFAULT_MODEL = "google/gemma-2-2b"
DEFAULT_MIN_PROB = 0.15
DEFAULT_TOP_K = 20


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

        author = candidate["author"]
        best_rank, best_prob, best_token_id = None, 0.0, None
        for prefix in (" ", ""):
            ids = tokenizer.encode(prefix + author, add_special_tokens=False)
            if not ids:
                continue
            tid = ids[0]
            p = float(probs[tid].item())
            if p > best_prob:
                best_prob = p
                best_token_id = tid
        if best_token_id is not None:
            best_rank = int((probs > best_prob).sum().item() + 1)

        author_first_token = (
            tokenizer.decode([best_token_id]).strip()
            if best_token_id is not None
            else "?"
        )

        results.append(
            {
                "slug": candidate["slug"],
                "character": candidate["character"],
                "book": candidate["book"],
                "author": author,
                "target_slot": candidate.get("target_slot", ""),
                "notes": candidate.get("notes", ""),
                "prompt": prompt,
                "rank": best_rank,
                "prob": best_prob,
                "top1_token": top1_token,
                "top1_prob": top1_prob,
                "author_first_token": author_first_token,
            }
        )
    return results


def compute_flags(results: list[dict]) -> list[dict]:
    keep_first_tokens = {e["first_token"] for e in KEEP_ENTRIES}
    keep_authors = {e["author"] for e in KEEP_ENTRIES}

    candidate_first_tokens: dict[str, list[str]] = {}
    for r in results:
        ft = r["author_first_token"]
        candidate_first_tokens.setdefault(ft, []).append(r["slug"])

    for r in results:
        flags = []
        if r["author"].startswith("J."):
            flags.append("J-initial-author")
        if r["character"] == r["book"]:
            flags.append("char-eq-book")
        if r["author"] in keep_authors:
            flags.append("author-already-kept")
        ft = r["author_first_token"]
        if ft in keep_first_tokens:
            flags.append(f"first-token-clash-keep:{ft}")
        if len(candidate_first_tokens.get(ft, [])) > 1:
            others = [s for s in candidate_first_tokens[ft] if s != r["slug"]]
            flags.append(f"first-token-clash-candidates:{','.join(others)}")
        r["flags"] = flags
    return results


def print_report(results: list[dict], min_prob: float):
    col_w = {
        "slug": 22,
        "author": 26,
        "rank": 5,
        "prob": 7,
        "top1_token": 12,
        "ft": 12,
        "pass": 5,
        "flags": 40,
    }
    header = (
        f"{'slug':<{col_w['slug']}} "
        f"{'author':<{col_w['author']}} "
        f"{'rnk':>{col_w['rank']}} "
        f"{'prob':>{col_w['prob']}} "
        f"{'top1':>{col_w['top1_token']}} "
        f"{'auth_ft':<{col_w['ft']}} "
        f"{'pass':<{col_w['pass']}} "
        f"flags"
    )
    print()
    print("=" * 120)
    print("CANDIDATE ASSESSMENT REPORT")
    print(f"Model threshold: rank=1, prob>={min_prob:.2f}")
    print("=" * 120)
    print()
    print("Kept entries (reference):")
    print("-" * 80)
    for e in KEEP_ENTRIES:
        print(f"  {e['slug']:<22} {e['author']:<26} first_token={e['first_token']}")
    print()
    print("Candidate results:")
    print("-" * 120)
    print(header)
    print("-" * 120)

    prev_slot = None
    for r in sorted(results, key=lambda x: x["target_slot"]):
        slot = r["target_slot"]
        if slot != prev_slot:
            print(f"  -- slot: {slot} --")
            prev_slot = slot
        passed = r["rank"] == 1 and r["prob"] >= min_prob and not any(
            f.startswith("J-initial") or f.startswith("char-eq-book") or "clash-keep" in f
            for f in r["flags"]
        )
        flag_str = ", ".join(r["flags"]) if r["flags"] else "ok"
        print(
            f"  {r['slug']:<{col_w['slug']}} "
            f"{r['author']:<{col_w['author']}} "
            f"{r['rank'] if r['rank'] is not None else '?':>{col_w['rank']}} "
            f"{r['prob']:>{col_w['prob']}.4f} "
            f"{repr(r['top1_token']):>{col_w['top1_token']}} "
            f"{r['author_first_token']:<{col_w['ft']}} "
            f"{'PASS' if passed else 'FAIL':<{col_w['pass']}} "
            f"{flag_str}"
        )
    print()


def print_recommendations(results: list[dict], min_prob: float):
    clean = [
        r for r in results
        if r["rank"] == 1
        and r["prob"] >= min_prob
        and not any(
            f.startswith("J-initial")
            or f.startswith("char-eq-book")
            or "clash-keep" in f
            for f in r["flags"]
        )
    ]

    print("=" * 80)
    print("RECOMMENDATION SUMMARY")
    print("=" * 80)
    print()
    print("Problematic slots and best-passing candidates (no intra-set first-token")
    print("clash check -- verify manually before choosing two Dickens candidates):")
    print()

    slot_map: dict[str, list[dict]] = {}
    for r in clean:
        slot_map.setdefault(r["target_slot"], []).append(r)

    replace_map = {
        "J_cluster_hermione":            "hermione_granger  (J.K. Rowling)",
        "J_cluster_frodo":               "frodo_baggins     (J.R.R. Tolkien)",
        "J_cluster_holden":              "holden_caulfield  (J.D. Salinger)",
        "J_cluster_any_or_char_eq_book": "any J. slot or char==book slot (edmond_dantes)",
        "scout_finch_dup":               "scout_finch       (Harper Lee dup)",
        "scout_finch_dup_alt":           "scout_finch alt",
        "char_eq_book_ot":               "oliver_twist      (char==book)",
        "char_eq_book_ot_alt1":          "oliver_twist alt1",
        "char_eq_book_ot_alt2":          "oliver_twist alt2",
        "char_eq_book_ak_or_dq":         "anna_karenina or don_quixote (char==book)",
        "char_eq_book_dq_alt":           "don_quixote alt",
        "char_eq_book_ak":               "anna_karenina     (char==book)",
        "char_eq_book_ak_alt":           "anna_karenina alt1",
        "char_eq_book_ak_alt2":          "anna_karenina alt2",
    }

    for slot, label in replace_map.items():
        candidates_for_slot = slot_map.get(slot, [])
        if candidates_for_slot:
            best = max(candidates_for_slot, key=lambda x: x["prob"])
            print(f"  Replace {label}")
            print(f"    -> {best['slug']} | {best['character']} | {best['book']} | {best['author']}")
            print(f"       rank={best['rank']}, prob={best['prob']:.4f}, auth_first_token={best['author_first_token']!r}")
        else:
            print(f"  Replace {label}")
            print(f"    -> no clean candidate found for this slot")
        print()


def parse_args():
    parser = argparse.ArgumentParser(description="Assess book candidate replacements")
    parser.add_argument(
        "--candidates",
        default=DEFAULT_CANDIDATES,
        help="Path to candidates JSON file",
    )
    parser.add_argument("--model-id", default=DEFAULT_MODEL)
    parser.add_argument("--device", default=None)
    parser.add_argument("--top-k", type=int, default=DEFAULT_TOP_K)
    parser.add_argument(
        "--min-prob",
        type=float,
        default=DEFAULT_MIN_PROB,
        help="Minimum probability to consider a candidate passing",
    )
    parser.add_argument("--json", action="store_true", help="Also dump raw results as JSON")
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
