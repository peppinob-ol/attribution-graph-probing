"""Re-score swap experiments with a position-0 distinctive-token hit metric.

Background
----------
Steering only fires at the prompt's last position. After token 0 the residual
stream is no longer perturbed, so the autoregressive continuation drifts back
toward the (un-steered) prompt context. The existing
``exact_match.steered_has_to_answer`` flag scans the full continuation and is
therefore biased against a successful pos-0 win that the model cannot sustain.

The legacy ``exact_match.first_token_matches_target`` flag judges only the
first token, but checks the loose substring ``steered_first in to_answer``,
which is too permissive (e.g. ``" of"`` substring-matches every multi-word
answer containing "of"). It is also blind to source-vs-target collisions
(see ``output/research/_LOG.md`` Flaw 4).

This module adds a stricter pos-0 flag that:

1. Tokenises ``to_answer`` and ``from_answer`` into substantive words
   (length >= 3 after punctuation strip).
2. Picks the *distinctive* target words (those NOT also in the source answer).
3. Counts a hit when the steered first token (lower-cased, stripped) matches
   any distinctive target word by either:
       a. ``first_token`` starts with the first 4 chars of the distinctive
          word (catches " Spring" -> "Springfield"), OR
       b. the distinctive word starts with ``first_token`` and ``first_token``
          is at least 3 chars long (catches " Dost" -> "Dostoevsky" via
          tokenizer subword splits).

The flag is written to ``evaluation.exact_match.pos0_distinctive_hit``
alongside the existing flags. Companion fields
``pos0_distinctive_match`` (the matched word) and
``pos0_distinctive_no_distinctive`` (True when source/target share all
substantive words) are written for debuggability.

Manual review pass
------------------
This metric is *automated* and judges only the topk[0] token. It can produce
false positives in two ways:
  - **topk vs rendered mismatch**: the topk metadata reports a token but the
    rendered ``steered_output`` starts with something else (a known artifact
    documented in ``output/research/_LOG.md`` Flaw 4).
  - **generic-suffix matches**: when the matched word is the LAST word of
    target and also appears as the last word of >=2 distinct target answers
    in the dataset (e.g. ``" City"`` in ``usa_states_batch``: matches Jefferson
    City, Kansas City, Oklahoma City, Salt Lake City).

After running this script, a manual-review pass demoted false-positive cases
by setting ``pos0_distinctive_hit=False`` and recording the verdict under
``evaluation.exact_match.pos0_manual_review = {verdict, reviewed, reason}``.
See ``output/research/_pos0_manual_rescore_summary.json`` for the curated
recovered-pair list.

Usage::

    python -m scripts.utils.rescore_pos0_distinctive            # all datasets
    python -m scripts.utils.rescore_pos0_distinctive --dry-run  # no writes
    python -m scripts.utils.rescore_pos0_distinctive --pairs /tmp/hard_fail_pairs.json
"""
from __future__ import annotations

import argparse
import json
import re
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = REPO_ROOT / "output"

DATASETS: Dict[str, Tuple[str, str]] = {
    "usa_states_batch":              ("fullscale_usa_labeled", "fullscale_usa_field_add"),
    "book_characters_authors_batch": ("fullscale_books_labeled", "fullscale_books_field_add"),
    "products_founders_batch":       ("fullscale_products_labeled", "fullscale_products_field_add"),
    "paintings_painters_batch":      ("fullscale_paintings_labeled", "fullscale_paintings_field_add"),
    "sounds_colors_batch":           ("fullscale_sounds_labeled", "fullscale_sounds_field_add"),
}

WORD_RE = re.compile(r"[^\w]+")


def _norm(text: str) -> str:
    return WORD_RE.sub("", (text or "").lower())


def pos0_distinctive_hit(
    steered_first_token: str,
    to_answer: str,
    from_answer: str,
    *,
    min_word_len: int = 4,
    min_subword_len: int = 3,
) -> Tuple[bool, Optional[str], bool]:
    """Return ``(hit, matched_word, no_distinctive)``.

    ``no_distinctive`` is True when target and source share every substantive
    word (e.g. answer-level identity pairs); a hit cannot be defined and the
    caller may want to mark the pair as not-applicable instead of False.
    """
    ft = _norm(steered_first_token)
    if not ft or len(ft) < 2 or not to_answer:
        return (False, None, False)

    tgt_words = [_norm(w) for w in to_answer.split()]
    tgt_words = [w for w in tgt_words if len(w) >= 3]
    src_words = {_norm(w) for w in (from_answer or "").split() if len(_norm(w)) >= 3}

    distinctive = [w for w in tgt_words if w not in src_words and len(w) >= min_word_len]
    if not distinctive:
        return (False, None, True)

    # Try longest distinctive words first to prefer specific matches.
    distinctive.sort(key=len, reverse=True)
    for d_w in distinctive:
        if len(ft) >= 4 and ft.startswith(d_w[: min_word_len]):
            return (True, d_w, False)
        if len(ft) >= min_subword_len and d_w.startswith(ft):
            return (True, d_w, False)
    return (False, None, False)


def _iter_swap_files(
    dataset: str,
    runs: List[str],
    pairs_filter: Optional[Set[Tuple[str, str]]] = None,
):
    ds_root = OUTPUT_ROOT / dataset / "_swaps" / "runs"
    for run in runs:
        run_root = ds_root / run / "by_source"
        if not run_root.is_dir():
            continue
        for src_dir in sorted(run_root.iterdir()):
            if not src_dir.is_dir():
                continue
            src_slug = src_dir.name
            for fpath in sorted(src_dir.glob("to_*.json")):
                stem = fpath.stem.replace("to_", "", 1)
                tgt_slug = stem.split("__", 1)[0]
                if pairs_filter is not None and (src_slug, tgt_slug) not in pairs_filter:
                    continue
                yield run, src_slug, tgt_slug, fpath


def rescore_file(fpath: Path, dry_run: bool = False) -> Dict[str, object]:
    with open(fpath, "r", encoding="utf-8") as fh:
        data = json.load(fh)

    ev = data.get("evaluation", {})
    em = ev.setdefault("exact_match", {})
    ft_obj = ev.get("first_token", {}) or {}
    raw = ev.get("raw", {}) or {}
    steered_topk = raw.get("steered_topk") or []
    steered_ft = ft_obj.get("steered") or (steered_topk[0].get("token") if steered_topk else "")
    to_answer = ev.get("to_answer", "")
    from_answer = ev.get("from_answer", "")

    hit, matched, no_distinctive = pos0_distinctive_hit(steered_ft, to_answer, from_answer)
    em["pos0_distinctive_hit"] = bool(hit)
    em["pos0_distinctive_match"] = matched
    em["pos0_distinctive_no_distinctive"] = bool(no_distinctive)

    if not dry_run:
        with open(fpath, "w", encoding="utf-8") as fh:
            json.dump(data, fh, indent=2, ensure_ascii=False)

    return {
        "hit": hit,
        "matched": matched,
        "no_distinctive": no_distinctive,
        "steered_first_token": steered_ft,
        "to_answer": to_answer,
        "from_answer": from_answer,
        "legacy_first_token_matches_target": em.get("first_token_matches_target"),
        "legacy_steered_has_to_answer": em.get("steered_has_to_answer"),
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--pairs", type=Path, default=None,
                    help="Optional JSON file mapping dataset -> [[src, tgt], ...].")
    ap.add_argument("--dry-run", action="store_true",
                    help="Compute the metric but do not write per-pair JSON files.")
    ap.add_argument("--datasets", nargs="*", default=None,
                    help="Subset of dataset slugs to process (default: all 5).")
    args = ap.parse_args()

    pairs_by_ds: Dict[str, Set[Tuple[str, str]]] = {}
    if args.pairs is not None:
        raw_map = json.loads(args.pairs.read_text())
        for ds, lst in raw_map.items():
            pairs_by_ds[ds] = {(p[0], p[1]) for p in lst}

    target_datasets = args.datasets or list(DATASETS.keys())

    grand_totals = defaultdict(int)
    per_dataset: Dict[str, Dict[str, int]] = {}
    flipped_examples: Dict[str, List[Dict[str, object]]] = defaultdict(list)

    for ds in target_datasets:
        runs = list(DATASETS[ds])
        flt = pairs_by_ds.get(ds) if pairs_by_ds else None
        seen_pair_hit: Dict[Tuple[str, str], bool] = defaultdict(bool)
        n_files = 0
        n_hits = 0
        n_no_distinctive = 0
        n_legacy_hits = 0
        n_recovered = 0  # pos0_distinctive_hit AND not legacy_steered_has_to_answer

        for run, src, tgt, fpath in _iter_swap_files(ds, runs, flt):
            info = rescore_file(fpath, dry_run=args.dry_run)
            n_files += 1
            if info["hit"]:
                n_hits += 1
                if not info["legacy_steered_has_to_answer"]:
                    n_recovered += 1
                if not seen_pair_hit[(src, tgt)] and len(flipped_examples[ds]) < 8:
                    if not info["legacy_steered_has_to_answer"]:
                        flipped_examples[ds].append({
                            "src": src, "tgt": tgt,
                            "ft": info["steered_first_token"],
                            "matched": info["matched"],
                            "to_answer": info["to_answer"],
                            "run": run,
                            "file": str(fpath.relative_to(OUTPUT_ROOT)),
                        })
                seen_pair_hit[(src, tgt)] = True
            if info["no_distinctive"]:
                n_no_distinctive += 1
            if info["legacy_steered_has_to_answer"]:
                n_legacy_hits += 1

        per_dataset[ds] = {
            "files_processed": n_files,
            "pos0_distinctive_hits": n_hits,
            "pos0_distinctive_no_distinctive": n_no_distinctive,
            "legacy_steered_has_to_answer_hits": n_legacy_hits,
            "newly_recovered_files": n_recovered,
            "newly_recovered_unique_pairs": sum(1 for v in seen_pair_hit.values() if v),
        }
        for k, v in per_dataset[ds].items():
            grand_totals[k] += v

    print("Re-scoring summary (per dataset):")
    print(f"{'dataset':35s} {'files':>7s} {'legacy_hit':>11s} {'pos0_hit':>9s} {'recovered':>10s}")
    for ds, stats in per_dataset.items():
        print(f"{ds:35s} {stats['files_processed']:>7d} "
              f"{stats['legacy_steered_has_to_answer_hits']:>11d} "
              f"{stats['pos0_distinctive_hits']:>9d} "
              f"{stats['newly_recovered_files']:>10d}")
    print(f"{'TOTAL':35s} {grand_totals['files_processed']:>7d} "
          f"{grand_totals['legacy_steered_has_to_answer_hits']:>11d} "
          f"{grand_totals['pos0_distinctive_hits']:>9d} "
          f"{grand_totals['newly_recovered_files']:>10d}")

    if args.dry_run:
        print("\n[dry-run] no JSON files were written.")
    else:
        print("\nWrote evaluation.exact_match.pos0_distinctive_hit to all processed files.")

    print("\nSample newly-recovered (legacy_miss -> pos0_hit) pairs:")
    for ds, ex in flipped_examples.items():
        if not ex:
            continue
        print(f"\n=== {ds} ===")
        for rec in ex:
            print(f"  {rec['src']:30s} -> {rec['tgt']:30s}  "
                  f"to_answer={rec['to_answer']!r:30s} ft={rec['ft']!r:25s} "
                  f"matched={rec['matched']!r}  ({rec['run']})")


if __name__ == "__main__":
    main()
