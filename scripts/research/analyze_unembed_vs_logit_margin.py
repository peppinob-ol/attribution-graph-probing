"""
Direct test of the geometric mechanism behind the user's hypothesis.

If `logit_t = RMSNorm(residual) . W_U[:, token_id_t]`, then for a fixed
amount of "residual push" toward the target, the achieved target logit
margin is bounded above by

      vs_max  ~  ||residual_push||  *  ||W_U[:, t]||  *  cos(.)

Therefore, even when the steering machinery installs the right direction,
low-||W_U|| tokens cannot reach a large vsMax. We test this by correlating
the per-pair best `vs_max` and `best_gap` against `||W_U[:, target]||`,
controlling for the baseline target logit (per-target marginal).
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
            tgt_summary = tgt_traj.get("summary", {})
            cg = (traj.get("contrast_groups", {}).get("same_dataset", {})
                  .get("aggregate", {}))
            traj_summ = traj.get("summary", {})
            bl = ev.get("baseline_logits", {}).get("target", {})
            row = {
                "from": src.get("slug", ""),
                "to": tgt.get("slug", ""),
                "target_token_id": tid,
                "target_token": traj.get("tokens", {}).get("target", ""),
                "vs_max": cg.get("best_target_minus_max"),
                "best_gap": traj_summ.get("best_gap"),
                "max_target_logit": max(
                    tgt_traj.get("trajectory", {}).get("logits", []),
                    default=None,
                ),
                "max_target_prob": tgt_summary.get("max_prob"),
                "min_target_rank": tgt_summary.get("min_rank"),
                "baseline_target_logit": bl.get("logit"),
                "hit": bool(ev.get("exact_match", {})
                            .get("steered_has_to_answer")),
            }
            grouped[(row["from"], row["to"])].append(row)
    out = []
    for variants in grouped.values():
        # take the variant with highest vs_max
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


def _pearson(xs, ys):
    n = len(xs)
    if n < 3:
        return None
    mx, my = sum(xs) / n, sum(ys) / n
    num = sum((xs[i] - mx) * (ys[i] - my) for i in range(n))
    dx = math.sqrt(sum((x - mx) ** 2 for x in xs))
    dy = math.sqrt(sum((y - my) ** 2 for y in ys))
    if dx == 0 or dy == 0:
        return None
    return num / (dx * dy)


def _ols2(xs1, xs2, ys):
    """Two-variable OLS: y = b0 + b1 x1 + b2 x2; return (b1, b2, R2).

    Used to check whether unembed_norm has predictive power beyond
    baseline target logit.
    """
    n = len(ys)
    if n < 5:
        return None, None, None
    sx1 = sum(xs1) / n
    sx2 = sum(xs2) / n
    sy = sum(ys) / n
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
        return None, None, None
    b1 = (sxx2 * sx1y - sx1x2 * sx2y) / det
    b2 = (sxx1 * sx2y - sx1x2 * sx1y) / det
    b0 = sy - b1 * sx1 - b2 * sx2
    yhat = [b0 + b1 * xs1[i] + b2 * xs2[i] for i in range(n)]
    ss_res = sum((ys[i] - yhat[i]) ** 2 for i in range(n))
    ss_tot = sum((y - sy) ** 2 for y in ys)
    r2 = 1 - ss_res / ss_tot if ss_tot else None
    return b1, b2, r2


def main():
    import torch
    from transformers import AutoModelForCausalLM

    all_rows = {}
    for dataset, run in DOMAINS:
        rows = _per_pair_best(dataset, run)
        all_rows[dataset] = rows
        print(f"  {dataset:>32s} : {len(rows)} pairs")
    token_ids = sorted({r["target_token_id"]
                         for rows in all_rows.values() for r in rows})

    print(f"\nLoading {MODEL_ID} ...", flush=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, torch_dtype=torch.float32, device_map="cpu",
    )
    embed = model.get_input_embeddings().weight.detach()
    norms = {tid: float(embed[tid].norm()) for tid in token_ids}

    print("\n" + "=" * 96)
    print("Unembedding norm vs achievable steered margin")
    print("=" * 96)
    blocks = []
    for dataset, _ in DOMAINS:
        rows = [r for r in all_rows[dataset]
                 if r["vs_max"] is not None
                    and r["max_target_logit"] is not None]
        for r in rows:
            r["unembed_norm"] = norms[r["target_token_id"]]
        norms_v = [r["unembed_norm"] for r in rows]
        vsmax = [r["vs_max"] for r in rows]
        bestgap = [r["best_gap"] for r in rows
                    if r["best_gap"] is not None]
        max_logit = [r["max_target_logit"] for r in rows]
        baseline = [r["baseline_target_logit"] for r in rows
                     if r["baseline_target_logit"] is not None]

        # Per-pair correlations
        sp_norm_vsmax = _spearman(norms_v, vsmax)
        pe_norm_vsmax = _pearson(norms_v, vsmax)
        sp_norm_maxlogit = _spearman(norms_v, max_logit)
        sp_baseline_vsmax = _spearman(
            [r["baseline_target_logit"] for r in rows
              if r["baseline_target_logit"] is not None],
            [r["vs_max"] for r in rows
              if r["baseline_target_logit"] is not None],
        )

        # Per-target aggregation
        per_target = defaultdict(list)
        for r in rows:
            per_target[r["to"]].append(r)
        per_tgt_rows = []
        for slug, group in per_target.items():
            vsx = [g["vs_max"] for g in group]
            mlx = [g["max_target_logit"] for g in group]
            blx = [g["baseline_target_logit"] for g in group
                    if g["baseline_target_logit"] is not None]
            per_tgt_rows.append({
                "to": slug,
                "token": group[0]["target_token"],
                "norm": group[0]["unembed_norm"],
                "n": len(group),
                "hit_rate": sum(1 for g in group if g["hit"]) / len(group),
                "mean_vs_max": statistics.mean(vsx),
                "mean_max_target_logit": statistics.mean(mlx),
                "marginal_baseline_logit": (statistics.mean(blx)
                                              if blx else None),
            })
        per_tgt_rho_norm_vsmax = _spearman(
            [t["norm"] for t in per_tgt_rows],
            [t["mean_vs_max"] for t in per_tgt_rows],
        )
        per_tgt_rho_norm_hitrate = _spearman(
            [t["norm"] for t in per_tgt_rows],
            [t["hit_rate"] for t in per_tgt_rows],
        )
        # OLS to control for baseline target logit
        per_tgt_with_base = [t for t in per_tgt_rows
                              if t["marginal_baseline_logit"] is not None]
        if len(per_tgt_with_base) >= 5:
            xs1 = [t["norm"] for t in per_tgt_with_base]
            xs2 = [t["marginal_baseline_logit"]
                    for t in per_tgt_with_base]
            ys = [t["hit_rate"] for t in per_tgt_with_base]
            b_norm, b_base, r2 = _ols2(xs1, xs2, ys)
        else:
            b_norm = b_base = r2 = None

        print(f"\n[{dataset}]  N={len(rows)} pairs  "
              f"unique_targets={len(per_tgt_rows)}")
        print(f"  per-pair  Spearman(unembed_norm, vs_max)         = "
              f"{sp_norm_vsmax}")
        print(f"  per-pair  Pearson(unembed_norm, vs_max)          = "
              f"{pe_norm_vsmax}")
        print(f"  per-pair  Spearman(unembed_norm, max_logit)      = "
              f"{sp_norm_maxlogit}")
        print(f"  per-pair  Spearman(baseline_logit, vs_max)       = "
              f"{sp_baseline_vsmax}  (reference)")
        print(f"  per-tgt   Spearman(unembed_norm, mean_vs_max)    = "
              f"{per_tgt_rho_norm_vsmax}")
        print(f"  per-tgt   Spearman(unembed_norm, hit_rate)       = "
              f"{per_tgt_rho_norm_hitrate}")
        print(f"  per-tgt   OLS hit_rate ~ unembed_norm + baseline:")
        print(f"            beta_unembed = {b_norm}")
        print(f"            beta_baseline = {b_base}")
        print(f"            R^2 = {r2}")

        blocks.append({
            "domain": dataset,
            "n_pairs": len(rows),
            "n_targets": len(per_tgt_rows),
            "per_pair_sp_norm_vsmax": sp_norm_vsmax,
            "per_pair_pearson_norm_vsmax": pe_norm_vsmax,
            "per_pair_sp_norm_max_logit": sp_norm_maxlogit,
            "per_pair_sp_baseline_vsmax": sp_baseline_vsmax,
            "per_target_sp_norm_vsmax": per_tgt_rho_norm_vsmax,
            "per_target_sp_norm_hitrate": per_tgt_rho_norm_hitrate,
            "ols": {"beta_unembed_norm": b_norm,
                     "beta_baseline_logit": b_base, "r2": r2},
            "per_target_rows": sorted(per_tgt_rows, key=lambda r: r["norm"]),
        })

    out = OUT_DIR / "unembed_vs_logit_margin.json"
    with open(out, "w", encoding="utf-8") as f:
        json.dump(blocks, f, indent=2)
    print(f"\nWrote: {out}")


if __name__ == "__main__":
    main()
