"""
Companion to `analyze_target_logit_specificity.py`. Tests a sharper
formulation of the "specific vs generic target" hypothesis:

   "specific"  == the target's first token is UNIQUE among all targets
                  in this domain (no collision; cleanly identifies one entity)
   "generic"   == the target's first token is SHARED across two or more
                  target entities in this domain (e.g. " Jack" is the first
                  token of both Jack Dorsey [twitter] and Jack Ma [alibaba])

If the user's hypothesis is right under this reading, hits should be
dominated by unique-token targets, and shared-token targets should fail
disproportionately.

We further look at "homonym density": for each target token, how many
distinct targets share it. We also break out the per-target hit rate.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OUT_DIR = REPO_ROOT / "output" / "research" / "target_logit_specificity"
OUT_DIR.mkdir(parents=True, exist_ok=True)

DOMAINS = [
    ("usa_states_batch", "fullscale_usa_labeled", "fullscale_usa_field_add"),
    ("book_characters_authors_batch",
     "fullscale_books_labeled", "fullscale_books_field_add"),
    ("products_founders_batch",
     "fullscale_products_labeled", "fullscale_products_field_add"),
    ("paintings_painters_batch",
     "fullscale_paintings_labeled", "fullscale_paintings_field_add"),
]


def _load(p: Path):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _per_pair_rows(dataset: str, run: str, fa_best: bool) -> List[Dict]:
    by_source = (REPO_ROOT / "output" / dataset / "_swaps"
                 / "runs" / run / "by_source")
    if not by_source.is_dir():
        return []
    rows: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)
    for src_dir in sorted(by_source.iterdir()):
        if not src_dir.is_dir():
            continue
        for fpath in sorted(src_dir.iterdir()):
            if not (fpath.name.startswith("to_") and fpath.suffix == ".json"):
                continue
            stem = fpath.stem.replace("to_", "", 1)
            if not fa_best and "__" in stem:
                continue
            data = _load(fpath)
            if not data:
                continue
            src = data.get("source", {})
            tgt = data.get("target", {})
            if src.get("slug") == tgt.get("slug"):
                continue
            ev = data.get("evaluation", {})
            tokens = ev.get("logit_trajectory", {}).get("tokens", {})
            target_token = tokens.get("target", "")
            em = ev.get("exact_match", {})
            cg = (ev.get("logit_trajectory", {})
                  .get("contrast_groups", {})
                  .get("same_dataset", {}).get("aggregate", {}))
            bl = ev.get("baseline_logits", {}).get("target", {})
            row = {
                "from": src.get("slug", ""),
                "to": tgt.get("slug", ""),
                "target_token": target_token,
                "target_logit": bl.get("logit"),
                "hit": bool(em.get("steered_has_to_answer")),
                "vs_max": cg.get("best_target_minus_max"),
            }
            rows[(row["from"], row["to"])].append(row)
    out: List[Dict] = []
    for (_, _), variants in rows.items():
        if not fa_best:
            out.extend(variants)
            continue
        hits = [r for r in variants if r["hit"]]
        pool = hits if hits else variants
        pool.sort(key=lambda r: r["vs_max"] or -1e9, reverse=True)
        out.append(pool[0])
    return out


def _token_collision_table(rows: List[Dict]) -> Dict[str, int]:
    """Map target_token -> number of DISTINCT target slugs that share it."""
    token_to_slugs: Dict[str, set] = defaultdict(set)
    for r in rows:
        if r["target_token"]:
            token_to_slugs[r["target_token"]].add(r["to"])
    return {t: len(s) for t, s in token_to_slugs.items()}


def _hit_rate(group: List[Dict]) -> Tuple[int, int, float]:
    n = len(group)
    h = sum(1 for r in group if r["hit"])
    return h, n, (h / n if n else 0.0)


def _two_sample_z(p1: float, n1: int, p2: float, n2: int) -> float:
    if n1 == 0 or n2 == 0:
        return float("nan")
    p_pool = (p1 * n1 + p2 * n2) / (n1 + n2)
    se = math.sqrt(p_pool * (1 - p_pool) * (1 / n1 + 1 / n2))
    if se == 0:
        return float("nan")
    return (p1 - p2) / se


def main() -> None:
    print(f"Output: {OUT_DIR}")
    blocks = []
    for dataset, labeled_run, fa_run in DOMAINS:
        for cond_label, run, fa_best in (
            ("labeled", labeled_run, False),
            ("fa_best", fa_run, True),
        ):
            rows = _per_pair_rows(dataset, run, fa_best)
            if not rows:
                continue
            collisions = _token_collision_table(rows)
            unique = [r for r in rows if collisions.get(r["target_token"], 0) == 1]
            shared = [r for r in rows if collisions.get(r["target_token"], 0) >= 2]
            unknown = [r for r in rows if not r["target_token"]]
            uh, un, ur = _hit_rate(unique)
            sh, sn, sr = _hit_rate(shared)
            kh, kn, kr = _hit_rate(unknown)
            z = _two_sample_z(ur, un, sr, sn) if (un > 0 and sn > 0) else float("nan")

            shared_tokens_ranked = []
            shared_tok_set = sorted({r["target_token"] for r in shared})
            for tok in shared_tok_set:
                tok_rows = [r for r in shared if r["target_token"] == tok]
                slugs = sorted({r["to"] for r in tok_rows})
                hr = sum(1 for r in tok_rows if r["hit"]) / len(tok_rows)
                shared_tokens_ranked.append({
                    "token": tok,
                    "n_slugs": len(slugs),
                    "slugs": slugs,
                    "n_pairs": len(tok_rows),
                    "hit_rate": hr,
                })
            shared_tokens_ranked.sort(key=lambda r: -r["n_pairs"])

            block = {
                "domain": dataset,
                "condition": cond_label,
                "n_total": len(rows),
                "n_unique_token": un,
                "n_shared_token": sn,
                "n_unknown_token": kn,
                "hit_rate_total": _hit_rate(rows)[2],
                "hit_rate_unique_token": ur,
                "hit_rate_shared_token": sr,
                "hit_rate_unknown_token": kr,
                "two_sample_z_unique_minus_shared": z,
                "shared_tokens": shared_tokens_ranked,
                "n_distinct_target_tokens": len(collisions),
                "n_distinct_target_slugs": len({r["to"] for r in rows}),
            }
            blocks.append(block)
    out_json = OUT_DIR / "collision_report.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump(blocks, f, indent=2)
    print(f"Wrote: {out_json}\n")

    # Console summary
    for b in blocks:
        print(f"\n[{b['domain']}] [{b['condition']}]  N={b['n_total']}")
        print(f"  unique_token : N={b['n_unique_token']:>4d}  "
              f"hit_rate={b['hit_rate_unique_token']*100:>5.1f}%")
        print(f"  shared_token : N={b['n_shared_token']:>4d}  "
              f"hit_rate={b['hit_rate_shared_token']*100:>5.1f}%")
        print(f"  unknown_token: N={b['n_unknown_token']:>4d}  "
              f"hit_rate={b['hit_rate_unknown_token']*100:>5.1f}%")
        z = b["two_sample_z_unique_minus_shared"]
        print(f"  z(unique - shared) = {z:.3f}"
              if not math.isnan(z) else "  z(unique - shared) = nan")
        if b["shared_tokens"]:
            print(f"  Shared tokens ({len(b['shared_tokens'])}):")
            for s in b["shared_tokens"]:
                print(f"    {s['token']!r:>14s}  shared by {s['n_slugs']} "
                      f"slugs ({', '.join(s['slugs'])})  hit_rate="
                      f"{s['hit_rate']*100:>5.1f}% (N={s['n_pairs']})")


if __name__ == "__main__":
    main()
