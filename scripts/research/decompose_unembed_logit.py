"""
Decompose `baseline_logit_t = ||r|| * ||W_U[t]|| * cos(r, W_U[t])` into

   ceiling   = ||W_U[:, t]||              (model-only, fixed per token)
   alignment = baseline_logit / ceiling    (~ ||r|| * cos; feature-driven)

and ask, per target, which one predicts hit_rate.

If `ceiling` (the user's hypothesis) is the dominant predictor in every
domain, we have a model-only diagnostic. If `alignment` dominates in some
domain, the diagnostic is NOT model-only; it requires the source prompt
or, equivalently, a feature-side measurement.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Tuple

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

OUT_DIR = REPO_ROOT / "output" / "research" / "target_logit_specificity"

DOMAINS = [
    ("usa_states_batch", "fullscale_usa_field_add"),
    ("book_characters_authors_batch", "fullscale_books_field_add"),
    ("products_founders_batch", "fullscale_products_field_add"),
    ("paintings_painters_batch", "fullscale_paintings_field_add"),
]
MODEL_ID = "google/gemma-2-2b"


def _load(p: Path):
    try:
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, IOError):
        return None


def _per_pair_best(dataset: str, run: str) -> List[Dict]:
    by_source = (REPO_ROOT / "output" / dataset / "_swaps"
                 / "runs" / run / "by_source")
    if not by_source.is_dir():
        return []
    grouped: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)
    for src_dir in sorted(by_source.iterdir()):
        if not src_dir.is_dir():
            continue
        for fpath in sorted(src_dir.iterdir()):
            if not (fpath.name.startswith("to_") and fpath.suffix == ".json"):
                continue
            data = _load(fpath)
            if not data:
                continue
            src = data.get("source", {})
            tgt = data.get("target", {})
            if src.get("slug") == tgt.get("slug"):
                continue
            ev = data.get("evaluation", {})
            traj = ev.get("logit_trajectory", {})
            tgt_traj = traj.get("trajectories", {}).get("target", {})
            tid = tgt_traj.get("token_id")
            if tid is None:
                continue
            cg = (traj.get("contrast_groups", {}).get("same_dataset", {})
                  .get("aggregate", {}))
            bl = ev.get("baseline_logits", {}).get("target", {})
            row = {
                "from": src.get("slug", ""),
                "to": tgt.get("slug", ""),
                "target_token_id": tid,
                "target_token": traj.get("tokens", {}).get("target", ""),
                "baseline_logit": bl.get("logit"),
                "vs_max": cg.get("best_target_minus_max"),
                "hit": bool(ev.get("exact_match", {})
                            .get("steered_has_to_answer")),
            }
            grouped[(row["from"], row["to"])].append(row)
    out = []
    for variants in grouped.values():
        variants.sort(key=lambda r: r["vs_max"] if r["vs_max"] is not None
                       else -1e9, reverse=True)
        out.append(variants[0])
    return out


def _spearman(xs, ys):
    n = len(xs)
    if n < 3:
        return None

    def _ranks(vs):
        order = sorted(range(len(vs)), key=lambda i: vs[i])
        ranks = [0.0] * len(vs)
        i = 0
        while i < len(vs):
            j = i
            while j + 1 < len(vs) and vs[order[j + 1]] == vs[order[i]]:
                j += 1
            avg = (i + j) / 2.0 + 1.0
            for k in range(i, j + 1):
                ranks[order[k]] = avg
            i = j + 1
        return ranks
    rx, ry = _ranks(xs), _ranks(ys)
    mx, my = sum(rx) / n, sum(ry) / n
    num = sum((rx[i] - mx) * (ry[i] - my) for i in range(n))
    dx = math.sqrt(sum((r - mx) ** 2 for r in rx))
    dy = math.sqrt(sum((r - my) ** 2 for r in ry))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def _ols2(xs1, xs2, ys):
    n = len(ys)
    if n < 5:
        return None, None, None, None
    sx1, sx2, sy = sum(xs1) / n, sum(xs2) / n, sum(ys) / n
    dx1 = [x - sx1 for x in xs1]
    dx2 = [x - sx2 for x in xs2]
    dy = [y - sy for y in ys]
    sxx1 = sum(d * d for d in dx1)
    sxx2 = sum(d * d for d in dx2)
    sx1x2 = sum(dx1[i] * dx2[i] for i in range(n))
    sx1y = sum(dx1[i] * dy[i] for i in range(n))
    sx2y = sum(dx2[i] * dy[i] for i in range(n))
    det = sxx1 * sxx2 - sx1x2 * sx1x2
    if det == 0:
        return None, None, None, None
    b1 = (sxx2 * sx1y - sx1x2 * sx2y) / det
    b2 = (sxx1 * sx2y - sx1x2 * sx1y) / det
    b0 = sy - b1 * sx1 - b2 * sx2
    yhat = [b0 + b1 * xs1[i] + b2 * xs2[i] for i in range(n)]
    ss_res = sum((ys[i] - yhat[i]) ** 2 for i in range(n))
    ss_tot = sum((y - sy) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot if ss_tot else None
    # standardize betas to make magnitudes comparable
    sd1 = math.sqrt(sxx1 / (n - 1)) if n > 1 else 0
    sd2 = math.sqrt(sxx2 / (n - 1)) if n > 1 else 0
    sdy = math.sqrt(ss_tot / (n - 1)) if n > 1 else 0
    b1_std = b1 * sd1 / sdy if sdy else None
    b2_std = b2 * sd2 / sdy if sdy else None
    return b1, b2, r2, (b1_std, b2_std)


def main() -> None:
    import torch
    from transformers import AutoModelForCausalLM
    rows_by_domain = {}
    for ds, run in DOMAINS:
        rows_by_domain[ds] = _per_pair_best(ds, run)
        print(f"  {ds:>32s} : {len(rows_by_domain[ds])} pairs")
    tids = sorted({r["target_token_id"] for rs in rows_by_domain.values()
                    for r in rs})

    print(f"\nLoading {MODEL_ID} ...", flush=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, torch_dtype=torch.float32, device_map="cpu",
    )
    embed = model.get_input_embeddings().weight.detach()
    norms = {tid: float(embed[tid].norm()) for tid in tids}

    print("\n" + "=" * 96)
    print("Decomposition: hit_rate ~ unembed_norm + alignment_proxy")
    print("alignment_proxy = baseline_logit / unembed_norm  (~ ||r|| * cos)")
    print("=" * 96)

    out_blocks = []
    for ds, _ in DOMAINS:
        rows = rows_by_domain[ds]
        # per-target aggregation
        per_tgt: Dict[str, List[Dict]] = defaultdict(list)
        for r in rows:
            r["unembed_norm"] = norms[r["target_token_id"]]
            if r["baseline_logit"] is not None:
                r["alignment_proxy"] = r["baseline_logit"] / r["unembed_norm"]
            else:
                r["alignment_proxy"] = None
            per_tgt[r["to"]].append(r)
        per_tgt_rows = []
        for slug, group in per_tgt.items():
            bls = [g["baseline_logit"] for g in group
                    if g["baseline_logit"] is not None]
            algs = [g["alignment_proxy"] for g in group
                     if g["alignment_proxy"] is not None]
            per_tgt_rows.append({
                "to": slug,
                "token": group[0]["target_token"],
                "n": len(group),
                "hit_rate": sum(1 for g in group if g["hit"]) / len(group),
                "ceiling": group[0]["unembed_norm"],
                "marginal_baseline_logit": (statistics.mean(bls)
                                              if bls else None),
                "alignment_proxy": (statistics.mean(algs)
                                      if algs else None),
            })
        per_tgt_rows.sort(key=lambda r: r["ceiling"])
        # univariate Spearmans
        sp_ceil = _spearman([t["ceiling"] for t in per_tgt_rows],
                              [t["hit_rate"] for t in per_tgt_rows])
        sp_align = _spearman([t["alignment_proxy"] for t in per_tgt_rows],
                              [t["hit_rate"] for t in per_tgt_rows])
        sp_base = _spearman([t["marginal_baseline_logit"]
                                for t in per_tgt_rows],
                              [t["hit_rate"] for t in per_tgt_rows])
        # OLS
        b_ceil, b_align, r2, std = _ols2(
            [t["ceiling"] for t in per_tgt_rows],
            [t["alignment_proxy"] for t in per_tgt_rows],
            [t["hit_rate"] for t in per_tgt_rows],
        )
        print(f"\n[{ds}]  N_targets={len(per_tgt_rows)}")
        print(f"  Spearman(ceiling, hit_rate)         = {sp_ceil}")
        print(f"  Spearman(alignment, hit_rate)       = {sp_align}")
        print(f"  Spearman(baseline_logit, hit_rate)  = {sp_base}  (= "
              f"||W_U||*alignment, i.e. ceiling*alignment)")
        print(f"  OLS hit_rate ~ ceiling + alignment:")
        print(f"    beta_ceiling   = {b_ceil}    (std beta = "
              f"{std[0] if std else None})")
        print(f"    beta_alignment = {b_align}    (std beta = "
              f"{std[1] if std else None})")
        print(f"    R^2 = {r2}")
        print(f"  per-target rows (sorted by ceiling):")
        print(f"  {'token':>14s}  {'ceil':>6s}  {'align':>7s}  "
              f"{'b_logit':>7s}  {'hit%':>6s}")
        for t in per_tgt_rows:
            print(f"  {t['token']!r:>14s}  {t['ceiling']:>6.3f}  "
                  f"{t['alignment_proxy']:>7.3f}  "
                  f"{t['marginal_baseline_logit']:>7.2f}  "
                  f"{t['hit_rate']*100:>5.1f}")
        out_blocks.append({
            "domain": ds,
            "n_targets": len(per_tgt_rows),
            "spearman_ceiling_vs_hit_rate": sp_ceil,
            "spearman_alignment_vs_hit_rate": sp_align,
            "spearman_baseline_logit_vs_hit_rate": sp_base,
            "ols_beta_ceiling": b_ceil,
            "ols_beta_alignment": b_align,
            "ols_std_beta": list(std) if std else None,
            "ols_r2": r2,
            "per_target_rows": per_tgt_rows,
        })
    out = OUT_DIR / "decomposition.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(out_blocks, f, indent=2)
    print(f"\nWrote: {out}")


if __name__ == "__main__":
    main()
