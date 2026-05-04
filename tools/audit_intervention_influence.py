"""
Sanity check: are labeled and random interventions matched on
total per-feature node_influence (per role), or is there a systematic
imbalance that could explain the "labeled > random" finding?

For each swap pair (non-identity) in
    output/<dataset>/_swaps/runs/fullscale_<domain>_labeled
    output/<dataset>/_swaps/runs/fullscale_<domain>_random
this script:
  1. Reads the intervention feature list from work/<swap_id>/features.json
  2. Splits by role (M == M_ablate -> source-side; M == M_amplify -> target-side)
  3. Joins against the source/target entity's
     graph_feature_static_metrics.csv (deduped by (layer, id)
     taking max node_influence across ctx_idx)
  4. Computes sum(node_influence) per role
  5. Writes a per-swap CSV and prints aggregate + ratio stats

Usage:
    python tools/audit_intervention_influence.py                   # all domains
    python tools/audit_intervention_influence.py usa books         # subset
"""
from __future__ import annotations

import csv
import json
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent
RESEARCH_DIR = REPO / "output" / "research"

# Per-domain (dataset_dir_name, labeled_run, random_run)
DOMAINS: Dict[str, Tuple[str, str, str]] = {
    "usa":       ("usa_states_batch",              "fullscale_usa_labeled",       "fullscale_usa_random"),
    "books":     ("book_characters_authors_batch", "fullscale_books_labeled",     "fullscale_books_random"),
    "products":  ("products_founders_batch",       "fullscale_products_labeled",  "fullscale_products_random"),
    "paintings": ("paintings_painters_batch",      "fullscale_paintings_labeled", "fullscale_paintings_random"),
    "sounds":    ("sounds_colors_batch",           "fullscale_sounds_labeled",    "fullscale_sounds_random"),
}

M_ABLATE = -2
M_AMPLIFY = 20


def find_entity_dir(dataset_dir: Path, slug: str) -> Optional[Path]:
    direct = dataset_dir / slug
    if direct.exists():
        return direct
    slug_lower = slug.lower()
    for cand in dataset_dir.iterdir():
        if cand.is_dir() and cand.name.lower().replace(" ", "_") == slug_lower:
            return cand
    return None


_ni_cache: Dict[Tuple[str, str], Dict[Tuple[int, int], float]] = {}


def load_feature_influence(
    dataset_dir: Path, slug: str
) -> Dict[Tuple[int, int], float]:
    """Return {(layer, id): max node_influence} for one entity.
    Error-node rows (feature == -1 with id >= 0) are kept, since the
    intervention feature list can in principle index them (it doesn't
    in practice, but being explicit is safer).
    """
    cache_key = (str(dataset_dir), slug)
    if cache_key in _ni_cache:
        return _ni_cache[cache_key]
    edir = find_entity_dir(dataset_dir, slug)
    if edir is None:
        _ni_cache[cache_key] = {}
        return {}
    csv_path = edir / "00 Graph Generation" / "graph_feature_static_metrics.csv"
    if not csv_path.exists():
        _ni_cache[cache_key] = {}
        return {}
    out: Dict[Tuple[int, int], float] = {}
    with open(csv_path, newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                layer = int(row["layer"])
                fid = int(row["id"])
                ni = float(row["node_influence"])
            except (KeyError, ValueError):
                continue
            key = (layer, fid)
            if ni > out.get(key, -1.0):
                out[key] = ni
    _ni_cache[cache_key] = out
    return out


def parse_swap_filename(name: str) -> Optional[Tuple[str, str]]:
    """'to_arizona_tucson.json' -> ('arizona_tucson', '')
       'to_arizona_tucson__r0.json' -> ('arizona_tucson', 'r0')
       'to_arizona_tucson__m_tuned.json' -> None  (skip)
    """
    if not name.startswith("to_") or not name.endswith(".json"):
        return None
    core = name[len("to_") : -len(".json")]
    if "__" in core:
        to_slug, suffix = core.split("__", 1)
        if suffix == "m_tuned":
            return None
        return to_slug, suffix
    return core, ""


def work_features_path(
    runs_dir: Path, run: str, from_slug: str, to_slug: str, suffix: str
) -> Path:
    swap_id = f"{from_slug}__to__{to_slug}"
    if suffix:
        swap_id = f"{swap_id}__{suffix}"
    return runs_dir / run / "work" / swap_id / "features.json"


def score_intervention(
    dataset_dir: Path, from_slug: str, to_slug: str, feats: List[dict]
) -> Dict[str, float]:
    src_ni = load_feature_influence(dataset_dir, from_slug)
    dst_ni = load_feature_influence(dataset_dir, to_slug)

    sum_abl = 0.0
    sum_amp = 0.0
    n_abl = 0
    n_amp = 0
    missing_abl = 0
    missing_amp = 0

    for f in feats:
        layer = int(f["layer"])
        idx = int(f["index"])
        m = f.get("M")
        key = (layer, idx)
        if m == M_ABLATE:
            n_abl += 1
            val = src_ni.get(key)
            if val is None:
                missing_abl += 1
            else:
                sum_abl += val
        elif m == M_AMPLIFY:
            n_amp += 1
            val = dst_ni.get(key)
            if val is None:
                missing_amp += 1
            else:
                sum_amp += val

    return dict(
        n_ablate=n_abl,
        n_amplify=n_amp,
        sum_ni_ablate=sum_abl,
        sum_ni_amplify=sum_amp,
        missing_ablate=missing_abl,
        missing_amplify=missing_amp,
    )


def collect_swaps_for_run(runs_dir: Path, run: str) -> List[Tuple[str, str, str]]:
    """Return list of (from_slug, to_slug, suffix) for the run,
    skipping identity swaps and __m_tuned variants."""
    out: List[Tuple[str, str, str]] = []
    by_source = runs_dir / run / "by_source"
    if not by_source.exists():
        return out
    for from_dir in sorted(by_source.iterdir()):
        if not from_dir.is_dir():
            continue
        from_slug = from_dir.name
        for f in sorted(from_dir.iterdir()):
            parsed = parse_swap_filename(f.name)
            if parsed is None:
                continue
            to_slug, suffix = parsed
            if to_slug == from_slug:
                continue
            out.append((from_slug, to_slug, suffix))
    return out


def _describe(label: str, values: List[float]) -> None:
    if not values:
        print(f"  {label:30s}  (no data)")
        return
    vs = sorted(values)
    q25 = vs[len(vs) // 4]
    q75 = vs[(3 * len(vs)) // 4]
    print(
        f"  {label:30s}  N={len(vs):5d}  "
        f"mean={statistics.mean(vs):.4f}  "
        f"median={statistics.median(vs):.4f}  "
        f"Q25={q25:.4f}  Q75={q75:.4f}  "
        f"min={vs[0]:.4f}  max={vs[-1]:.4f}"
    )


def run_domain(domain: str) -> Dict[str, Dict[str, float]]:
    """Process one domain end-to-end. Returns a summary dict."""
    dataset_name, labeled_run, random_run = DOMAINS[domain]
    dataset_dir = REPO / "output" / dataset_name
    runs_dir = dataset_dir / "_swaps" / "runs"

    out_csv = RESEARCH_DIR / f"audit_intervention_influence_{domain}.csv"

    print()
    print("#" * 72)
    print(f"# Domain: {domain}  ({dataset_name})")
    print(f"#   labeled: {labeled_run}")
    print(f"#   random:  {random_run}")
    print("#" * 72)

    labeled_swaps = collect_swaps_for_run(runs_dir, labeled_run)
    random_swaps = collect_swaps_for_run(runs_dir, random_run)
    print(f"Labeled non-identity swaps: {len(labeled_swaps)}")
    print(f"Random non-identity swaps:  {len(random_swaps)}")

    rows: List[Dict[str, float]] = []
    missing_features_files = 0

    for run, swap_list in (
        (labeled_run, labeled_swaps),
        (random_run, random_swaps),
    ):
        for from_slug, to_slug, suffix in swap_list:
            fpath = work_features_path(runs_dir, run, from_slug, to_slug, suffix)
            if not fpath.exists():
                missing_features_files += 1
                continue
            with open(fpath) as f:
                feats = json.load(f)
            scores = score_intervention(dataset_dir, from_slug, to_slug, feats)
            rows.append(
                dict(
                    domain=domain,
                    run=run,
                    variant=suffix or "canonical",
                    from_slug=from_slug,
                    to_slug=to_slug,
                    **scores,
                )
            )

    if missing_features_files:
        print(f"WARNING: {missing_features_files} swaps missing features.json")

    RESEARCH_DIR.mkdir(parents=True, exist_ok=True)
    if rows:
        with open(out_csv, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
        print(f"Wrote per-swap data: {out_csv}  ({len(rows)} rows)")

    # Split by condition
    by_cond: Dict[str, List[Dict[str, float]]] = {}
    for r in rows:
        cond = "labeled" if r["run"] == labeled_run else f"random_{r['variant']}"
        by_cond.setdefault(cond, []).append(r)

    print("\n--- Sum of node_influence per intervention (per role) ---\n")
    for cond in sorted(by_cond.keys()):
        rs = by_cond[cond]
        print(f"[{cond}]  N_swaps={len(rs)}")
        _describe("sum_ni_ablate", [r["sum_ni_ablate"] for r in rs])
        _describe("sum_ni_amplify", [r["sum_ni_amplify"] for r in rs])
        _describe("n_ablate", [float(r["n_ablate"]) for r in rs])
        _describe("n_amplify", [float(r["n_amplify"]) for r in rs])
        print()

    pair_key = lambda r: (r["from_slug"], r["to_slug"])
    labeled_by_pair = {pair_key(r): r for r in by_cond.get("labeled", [])}

    print("--- Per-pair ratio labeled/random (sum node_influence) ---\n")
    for rcond in sorted(c for c in by_cond if c.startswith("random_")):
        rs = by_cond[rcond]
        ratios_abl: List[float] = []
        ratios_amp: List[float] = []
        for r in rs:
            lab = labeled_by_pair.get(pair_key(r))
            if lab is None:
                continue
            if r["sum_ni_ablate"] > 0:
                ratios_abl.append(lab["sum_ni_ablate"] / r["sum_ni_ablate"])
            if r["sum_ni_amplify"] > 0:
                ratios_amp.append(lab["sum_ni_amplify"] / r["sum_ni_amplify"])
        print(f"[{rcond}]  N={len(rs)}")
        _describe("ratio labeled/random ablate", ratios_abl)
        _describe("ratio labeled/random amplify", ratios_amp)
        print()

    print("--- Per-pair labeled - random differences (sum node_influence) ---\n")
    summary: Dict[str, Dict[str, float]] = {}
    for rcond in sorted(c for c in by_cond if c.startswith("random_")):
        rs = by_cond[rcond]
        dabl: List[float] = []
        damp: List[float] = []
        for r in rs:
            lab = labeled_by_pair.get(pair_key(r))
            if lab is None:
                continue
            dabl.append(lab["sum_ni_ablate"] - r["sum_ni_ablate"])
            damp.append(lab["sum_ni_amplify"] - r["sum_ni_amplify"])
        print(f"[{rcond}]  N={len(rs)}")
        _describe("labeled - random (ablate)", dabl)
        _describe("labeled - random (amplify)", damp)
        pos_abl = sum(1 for d in dabl if d > 0)
        pos_amp = sum(1 for d in damp if d > 0)
        pct_abl = 100 * pos_abl / len(dabl) if dabl else 0.0
        pct_amp = 100 * pos_amp / len(damp) if damp else 0.0
        print(
            f"    pairs where labeled > random:  "
            f"ablate {pos_abl}/{len(dabl)} ({pct_abl:.1f}%)  "
            f"amplify {pos_amp}/{len(damp)} ({pct_amp:.1f}%)"
        )
        print()

        lab_vals_abl = [r["sum_ni_ablate"] for r in by_cond["labeled"]]
        lab_vals_amp = [r["sum_ni_amplify"] for r in by_cond["labeled"]]
        rnd_vals_abl = [r["sum_ni_ablate"] for r in rs]
        rnd_vals_amp = [r["sum_ni_amplify"] for r in rs]
        summary[rcond] = dict(
            n_pairs_labeled=len(by_cond["labeled"]),
            n_pairs_random=len(rs),
            lab_mean_abl=statistics.mean(lab_vals_abl) if lab_vals_abl else 0.0,
            lab_med_abl=statistics.median(lab_vals_abl) if lab_vals_abl else 0.0,
            lab_mean_amp=statistics.mean(lab_vals_amp) if lab_vals_amp else 0.0,
            lab_med_amp=statistics.median(lab_vals_amp) if lab_vals_amp else 0.0,
            rnd_mean_abl=statistics.mean(rnd_vals_abl) if rnd_vals_abl else 0.0,
            rnd_med_abl=statistics.median(rnd_vals_abl) if rnd_vals_abl else 0.0,
            rnd_mean_amp=statistics.mean(rnd_vals_amp) if rnd_vals_amp else 0.0,
            rnd_med_amp=statistics.median(rnd_vals_amp) if rnd_vals_amp else 0.0,
            pct_labeled_higher_ablate=pct_abl,
            pct_labeled_higher_amplify=pct_amp,
        )

    return summary


def main() -> None:
    requested = sys.argv[1:] or list(DOMAINS.keys())
    bad = [d for d in requested if d not in DOMAINS]
    if bad:
        print(f"Unknown domains: {bad}. Available: {list(DOMAINS.keys())}")
        sys.exit(1)

    cross: Dict[str, Dict[str, Dict[str, float]]] = {}
    for domain in requested:
        cross[domain] = run_domain(domain)

    print()
    print("=" * 72)
    print("=== CROSS-DOMAIN SUMMARY: sum node_influence, labeled vs random ===")
    print("=" * 72)
    header = (
        f"{'domain':10s} {'rep':3s} {'N_lab':>5s} {'N_rnd':>5s} "
        f"{'lab_mean_amp':>12s} {'rnd_mean_amp':>12s} "
        f"{'lab/rnd_med_amp':>16s} {'%lab>rnd_amp':>13s}"
    )
    print(header)
    print("-" * len(header))
    for domain in requested:
        summ = cross.get(domain, {})
        for rcond in sorted(summ.keys()):
            s = summ[rcond]
            rep = rcond.replace("random_", "")
            ratio_med_amp = (
                s["lab_med_amp"] / s["rnd_med_amp"] if s["rnd_med_amp"] else 0.0
            )
            print(
                f"{domain:10s} {rep:3s} {s['n_pairs_labeled']:5d} "
                f"{s['n_pairs_random']:5d} "
                f"{s['lab_mean_amp']:12.4f} {s['rnd_mean_amp']:12.4f} "
                f"{ratio_med_amp:16.3f} {s['pct_labeled_higher_amplify']:12.1f}%"
            )


if __name__ == "__main__":
    main()
