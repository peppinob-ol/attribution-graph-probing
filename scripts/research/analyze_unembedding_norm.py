"""
Test the user's sharper hypothesis: target tokens with small UNEMBEDDING
NORM are harder to steer.

Mechanism: in Gemma-2-2b the next-token logit is

    logit_t  =  RMSNorm(residual)  .  W_U[:, token_id_t]
              [+ optional logit soft-cap]

so for a fixed steering push in residual space, the achieved logit on
token t is proportional to the projection on W_U[:, t]. Tokens whose
unembedding row has small L2 norm receive a small logit increment per
unit of residual signal -- they are "structurally hard to steer".

Gemma-2 ties embeddings (lm_head.weight is embed_tokens.weight), so
the unembedding row equals the embedding row.

Per pair, per target, and quintile-stratified hit-rate by:
   - raw L2 norm  ||W_U[:, t]||
   - cosine-aware effective magnitude after RMSNorm scaling (rmsnorm
     gamma row * embedding row L2)

Outputs to `output/research/target_logit_specificity/unembed_*`.
"""

from __future__ import annotations

import json
import math
import statistics
import sys
from collections import defaultdict
from pathlib import Path
from typing import Dict, List, Optional, Tuple

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

MODEL_ID = "google/gemma-2-2b"


def _load_swap(p: Path):
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
    grouped: Dict[Tuple[str, str], List[Dict]] = defaultdict(list)
    for src_dir in sorted(by_source.iterdir()):
        if not src_dir.is_dir():
            continue
        for fpath in sorted(src_dir.iterdir()):
            if not (fpath.name.startswith("to_") and fpath.suffix == ".json"):
                continue
            stem = fpath.stem.replace("to_", "", 1)
            if not fa_best and "__" in stem:
                continue
            data = _load_swap(fpath)
            if not data:
                continue
            src = data.get("source", {})
            tgt = data.get("target", {})
            if src.get("slug") == tgt.get("slug"):
                continue
            ev = data.get("evaluation", {})
            traj = ev.get("logit_trajectory", {})
            tokens = traj.get("tokens", {})
            target_token = tokens.get("target", "")
            traj_full = traj.get("trajectories", {}).get("target", {})
            target_tid = traj_full.get("token_id")
            em = ev.get("exact_match", {})
            cg = (traj.get("contrast_groups", {}).get("same_dataset", {})
                  .get("aggregate", {}))
            bl = ev.get("baseline_logits", {}).get("target", {})
            row = {
                "from": src.get("slug", ""),
                "to": tgt.get("slug", ""),
                "target_token": target_token,
                "target_token_id": target_tid,
                "target_logit_baseline": bl.get("logit"),
                "hit": bool(em.get("steered_has_to_answer")),
                "vs_max": cg.get("best_target_minus_max"),
            }
            grouped[(row["from"], row["to"])].append(row)
    out: List[Dict] = []
    for variants in grouped.values():
        # Drop variants without a recorded token_id (M-search auxiliary files)
        with_tid = [r for r in variants if r["target_token_id"] is not None]
        if not with_tid:
            continue
        if not fa_best:
            out.extend(with_tid)
            continue
        hits = [r for r in with_tid if r["hit"]]
        pool = hits if hits else with_tid
        pool.sort(key=lambda r: r["vs_max"] or -1e9, reverse=True)
        best = pool[0]
        # If the chosen winner is from an m-tuned hit (token_id missing),
        # fall back to a non-m-tuned variant for consistent token_id source.
        out.append(best)
    return out


def _spearman(xs: List[float], ys: List[float]) -> Optional[float]:
    n = len(xs)
    if n < 3:
        return None

    def _ranks(vs: List[float]) -> List[float]:
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


def _point_biserial(values: List[float], labels: List[bool]) -> Optional[float]:
    if len(values) != len(labels) or len(values) < 5:
        return None
    a = [v for v, lb in zip(values, labels) if lb]
    b = [v for v, lb in zip(values, labels) if not lb]
    if len(a) < 2 or len(b) < 2:
        return None
    n = len(values)
    ma, mb = statistics.mean(a), statistics.mean(b)
    sd = statistics.stdev(values)
    if sd == 0:
        return None
    p = len(a) / n
    return (ma - mb) / sd * math.sqrt(p * (1 - p))


def _stratify(rows: List[Dict], key: str, k: int = 5) -> List[Dict]:
    items = [(r[key], r["hit"]) for r in rows if r[key] is not None]
    if len(items) < k:
        return []
    vs = sorted(v for v, _ in items)
    edges = [vs[int(i * (len(vs) - 1) / k)] for i in range(k + 1)]
    buckets: Dict[int, List[Tuple[float, bool]]] = defaultdict(list)
    for v, h in items:
        qi = next((i for i in range(k) if v <= edges[i + 1]), k - 1)
        buckets[qi].append((v, h))
    out = []
    for qi in range(k):
        bucket = buckets.get(qi, [])
        if not bucket:
            continue
        n = len(bucket)
        hits = sum(1 for _, h in bucket if h)
        out.append({
            "quintile": qi + 1,
            "n": n,
            "lo": edges[qi],
            "hi": edges[qi + 1],
            "mean": statistics.mean(v for v, _ in bucket),
            "hit_rate": hits / n,
        })
    return out


def _per_target(rows: List[Dict]) -> List[Dict]:
    by_target: Dict[str, List[Dict]] = defaultdict(list)
    for r in rows:
        by_target[r["to"]].append(r)
    out = []
    for slug, group in by_target.items():
        norms = [g["unembed_norm"] for g in group
                  if g.get("unembed_norm") is not None]
        eff = [g["effective_norm"] for g in group
                if g.get("effective_norm") is not None]
        if not norms:
            continue
        out.append({
            "to_slug": slug,
            "target_token": group[0]["target_token"],
            "target_token_id": group[0]["target_token_id"],
            "n_pairs": len(group),
            "hit_rate": sum(1 for g in group if g["hit"]) / len(group),
            "unembed_norm": statistics.mean(norms),
            "effective_norm": statistics.mean(eff) if eff else None,
            "marginal_baseline_logit": (
                statistics.mean([g["target_logit_baseline"] for g in group
                                  if g["target_logit_baseline"] is not None])
                if any(g["target_logit_baseline"] is not None for g in group)
                else None),
        })
    return out


def _gather_token_ids(all_rows: List[Dict]) -> List[int]:
    return sorted({r["target_token_id"] for r in all_rows
                    if r["target_token_id"] is not None})


def _load_norms(token_ids: List[int]) -> Tuple[Dict[int, float],
                                                Dict[int, float],
                                                Dict[str, float]]:
    """Return (raw_norm, effective_norm, summary) for each token_id.

    raw_norm:       L2 norm of W_U row (= embed_tokens row, weights tied).
    effective_norm: L2 norm * mean of |gamma| in final RMSNorm (a coarse
                    proxy for post-norm scaling). Strictly monotone in
                    raw_norm here since gamma is shared, so it is mostly
                    a sanity diagnostic.
    summary:        global stats over the full vocab for context.
    """
    import torch
    from transformers import AutoModelForCausalLM

    print(f"Loading {MODEL_ID} (CPU, float32) ...", flush=True)
    model = AutoModelForCausalLM.from_pretrained(
        MODEL_ID, torch_dtype=torch.float32, device_map="cpu",
    )
    embed = model.get_input_embeddings().weight.detach()
    final_norm_w = None
    norm_module = getattr(model.model, "norm", None)
    if norm_module is not None and hasattr(norm_module, "weight"):
        final_norm_w = norm_module.weight.detach()
    norms_all = embed.norm(dim=-1)
    raw = {tid: float(norms_all[tid]) for tid in token_ids}
    if final_norm_w is not None:
        gamma_mean = float(final_norm_w.abs().mean())
    else:
        gamma_mean = 1.0
    eff = {tid: raw[tid] * gamma_mean for tid in token_ids}
    summary = {
        "vocab_size": int(embed.shape[0]),
        "d_model": int(embed.shape[1]),
        "norm_min": float(norms_all.min()),
        "norm_max": float(norms_all.max()),
        "norm_mean": float(norms_all.mean()),
        "norm_median": float(norms_all.median()),
        "norm_p25": float(norms_all.quantile(0.25)),
        "norm_p75": float(norms_all.quantile(0.75)),
        "rmsnorm_gamma_mean_abs": gamma_mean,
        "weights_tied": bool(getattr(model.config, "tie_word_embeddings", True)),
    }
    return raw, eff, summary


def _domain_block(domain: str, condition: str, rows: List[Dict]) -> Dict:
    n = len(rows)
    hits = sum(1 for r in rows if r["hit"])
    pb_norm = _point_biserial(
        [r["unembed_norm"] for r in rows if r["unembed_norm"] is not None],
        [r["hit"] for r in rows if r["unembed_norm"] is not None],
    )
    pb_baseline = _point_biserial(
        [r["target_logit_baseline"] for r in rows
         if r["target_logit_baseline"] is not None],
        [r["hit"] for r in rows if r["target_logit_baseline"] is not None],
    )
    quint_norm = _stratify(rows, "unembed_norm")
    per_tgt = _per_target(rows)
    if per_tgt:
        rho_norm = _spearman(
            [t["unembed_norm"] for t in per_tgt],
            [t["hit_rate"] for t in per_tgt],
        )
        rho_base = _spearman(
            [t["marginal_baseline_logit"] for t in per_tgt
              if t["marginal_baseline_logit"] is not None],
            [t["hit_rate"] for t in per_tgt
              if t["marginal_baseline_logit"] is not None],
        )
    else:
        rho_norm = rho_base = None
    return {
        "domain": domain,
        "condition": condition,
        "n_pairs": n,
        "n_hits": hits,
        "hit_rate": hits / n if n else 0,
        "n_unique_targets": len({r["to"] for r in rows}),
        "per_pair_pb_unembed_norm_vs_hit": pb_norm,
        "per_pair_pb_baseline_logit_vs_hit": pb_baseline,
        "per_target_spearman_unembed_norm_vs_hitrate": rho_norm,
        "per_target_spearman_baseline_logit_vs_hitrate": rho_base,
        "per_pair_quintiles_by_unembed_norm": quint_norm,
        "per_target_rows_low_norm_first": sorted(
            per_tgt, key=lambda r: r["unembed_norm"])[:],
    }


def main() -> None:
    print(f"Output: {OUT_DIR}")
    all_rows_by_cell: List[Tuple[str, str, List[Dict]]] = []
    for dataset, labeled_run, fa_run in DOMAINS:
        for cond, run, fa_best in (("labeled", labeled_run, False),
                                     ("fa_best", fa_run, True)):
            rows = _per_pair_rows(dataset, run, fa_best)
            print(f"  {dataset:>32s} {cond:>8s} : "
                  f"{len(rows):>5d} pairs (with token_id)")
            all_rows_by_cell.append((dataset, cond, rows))

    flat_rows = [r for _, _, rows in all_rows_by_cell for r in rows]
    token_ids = _gather_token_ids(flat_rows)
    print(f"\nUnique target token_ids across all conditions: {len(token_ids)}")

    raw_norm, eff_norm, vocab_summary = _load_norms(token_ids)
    print(f"\nVocab norm summary: {vocab_summary}")

    for r in flat_rows:
        tid = r["target_token_id"]
        r["unembed_norm"] = raw_norm.get(tid)
        r["effective_norm"] = eff_norm.get(tid)

    blocks: List[Dict] = []
    for dataset, cond, rows in all_rows_by_cell:
        blocks.append(_domain_block(dataset, cond, rows))

    out_json = OUT_DIR / "unembed_report.json"
    with open(out_json, "w", encoding="utf-8") as f:
        json.dump({"vocab_summary": vocab_summary, "blocks": blocks}, f,
                   indent=2)
    print(f"\nWrote: {out_json}")

    print("\n" + "=" * 92)
    print("UNEMBEDDING NORM as predictor of steer success")
    print("=" * 92)
    for b in blocks:
        print(f"\n[{b['domain']}] [{b['condition']}]  N={b['n_pairs']}  "
              f"hit%={b['hit_rate']*100:.1f}  "
              f"unique_targets={b['n_unique_targets']}")
        print(f"  PB(unembed_norm , hit) = "
              f"{b['per_pair_pb_unembed_norm_vs_hit']}")
        print(f"  PB(baseline_logit, hit) = "
              f"{b['per_pair_pb_baseline_logit_vs_hit']}  (reference)")
        print(f"  Spearman_per_target(unembed_norm, hit_rate) = "
              f"{b['per_target_spearman_unembed_norm_vs_hitrate']}")
        print(f"  Spearman_per_target(baseline_logit, hit_rate) = "
              f"{b['per_target_spearman_baseline_logit_vs_hitrate']}  (ref)")
        for q in b["per_pair_quintiles_by_unembed_norm"]:
            print(f"    Q{q['quintile']}  N={q['n']:>4d}  "
                  f"norm in [{q['lo']:.3f}, {q['hi']:.3f}]  "
                  f"mean={q['mean']:.3f}  hit%={q['hit_rate']*100:.1f}")
    print()
    for b in blocks:
        if b["condition"] != "fa_best":
            continue
        print(f"\n[{b['domain']}] per-target rows (low unembed_norm first):")
        print(f"  {'slug':<28s} {'token':>14s}  {'norm':>8s}  "
              f"{'mlogit':>7s}  {'hit%':>6s}  N")
        for r in b["per_target_rows_low_norm_first"]:
            ml = r["marginal_baseline_logit"]
            ml_s = f"{ml:>7.2f}" if ml is not None else "    -  "
            print(f"  {r['to_slug']:<28s} {r['target_token']!r:>14s}  "
                  f"{r['unembed_norm']:>8.3f}  {ml_s}  "
                  f"{r['hit_rate']*100:>5.1f}%  {r['n_pairs']}")


if __name__ == "__main__":
    main()
