"""
Per-pair influence-budget aggregator for the top-K influence-matched baseline.

For each domain in {usa, books, products, paintings}, walks the existing
``fullscale_<domain>_field_add`` swap run, picks for every (from, to) pair
the best variant across the 7 field-additivity choices x {default,
m_tuned}, then computes the cumulative ``node_influence`` over the
features that were ablated on the source side and amplified on the target
side. The resulting per-pair (ref_sum_src, ref_sum_tgt) defines the
budget that the matched top-K-by-influence baseline must consume on each
side.

Output: ``output/research/topk_budgets_<domain>.csv``.

The script is deterministic and read-only; it does not run the model.
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

REPO = Path(__file__).resolve().parent.parent

DOMAINS: Dict[str, Dict[str, str]] = {
    "usa": {
        "dataset_dir": "output/usa_states_batch",
        "run_id": "fullscale_usa_field_add",
    },
    "books": {
        "dataset_dir": "output/book_characters_authors_batch",
        "run_id": "fullscale_books_field_add",
    },
    "products": {
        "dataset_dir": "output/products_founders_batch",
        "run_id": "fullscale_products_field_add",
    },
    "paintings": {
        "dataset_dir": "output/paintings_painters_batch",
        "run_id": "fullscale_paintings_field_add",
    },
}


@dataclass(frozen=True)
class PairResult:
    from_slug: str
    to_slug: str
    variant: str
    used_m_tuned: bool
    hit: bool
    best_gap: float
    n_ablate: int
    n_amplify: int
    work_dir: Path


def _find_graph_dir_case_insensitive(graphs_root: Path, slug: str) -> Path:
    """Mirror of swap_loader._find_graph_dir_case_insensitive."""
    exact = graphs_root / slug
    if exact.exists():
        return exact
    slug_lower = slug.lower()
    if graphs_root.exists():
        for entry in graphs_root.iterdir():
            if entry.is_dir() and entry.name.lower() == slug_lower:
                return entry
    return exact


def _load_metrics_index(
    graphs_root: Path,
    slug: str,
    cache: Dict[str, Dict[Tuple[int, int], float]],
) -> Dict[Tuple[int, int], float]:
    """Return ``(layer, feature_id) -> max node_influence`` for an entity."""
    if slug in cache:
        return cache[slug]
    entity_dir = _find_graph_dir_case_insensitive(graphs_root, slug)
    metrics_csv = entity_dir / "00 Graph Generation" / "graph_feature_static_metrics.csv"
    influence: Dict[Tuple[int, int], float] = {}
    if not metrics_csv.exists():
        cache[slug] = influence
        return influence
    with metrics_csv.open() as f:
        reader = csv.DictReader(f)
        for row in reader:
            try:
                layer = int(row["layer"])
            except (TypeError, ValueError):
                continue
            if layer < 0:
                continue
            try:
                feat_id = int(row["id"])
            except (TypeError, ValueError):
                continue
            raw = row.get("node_influence")
            if raw is None or raw == "":
                continue
            try:
                v = float(raw)
            except ValueError:
                continue
            key = (layer, feat_id)
            if v > influence.get(key, 0.0):
                influence[key] = v
    cache[slug] = influence
    return influence


def _read_features_json(work_dir: Path) -> Optional[List[Dict[str, object]]]:
    p = work_dir / "features.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text())
    except json.JSONDecodeError:
        return None


def _split_features_by_role(
    features: List[Dict[str, object]],
) -> Tuple[List[Tuple[int, int]], List[Tuple[int, int]]]:
    """
    Split feature entries into (ablated_source_keys, amplified_target_keys).

    Convention in features.json (verified on existing runs):
      * M < 0 -> ablation (source-side feature).
      * M > 0 -> amplification (target-side feature).

    The ``ablate`` boolean is also carried but is set ``false`` on every
    entry observed; we follow the sign of ``M`` to match what the
    pipeline actually does at steering time.
    """
    abl: List[Tuple[int, int]] = []
    amp: List[Tuple[int, int]] = []
    for e in features:
        try:
            layer = int(e.get("layer"))  # type: ignore[arg-type]
            feat = int(e.get("index"))  # type: ignore[arg-type]
            m_val = float(e.get("M", 0.0))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            continue
        if m_val < 0:
            abl.append((layer, feat))
        elif m_val > 0:
            amp.append((layer, feat))
    return abl, amp


def _sum_influence(
    keys: Iterable[Tuple[int, int]],
    influence: Dict[Tuple[int, int], float],
) -> float:
    total = 0.0
    for k in keys:
        v = influence.get(k)
        if v is not None:
            total += v
    return total


def _enumerate_pair_jsons(by_source_dir: Path) -> Iterable[Tuple[str, str, str, Path]]:
    """Yield (from_slug, to_slug, variant, json_path) for every base swap JSON."""
    for from_dir in sorted(by_source_dir.iterdir()):
        if not from_dir.is_dir():
            continue
        from_slug = from_dir.name
        for jp in sorted(from_dir.glob("to_*.json")):
            stem = jp.stem
            if stem.endswith("__m_tuned"):
                continue
            assert stem.startswith("to_")
            tail = stem[3:]
            if "__" in tail:
                to_slug, variant = tail.split("__", 1)
            else:
                to_slug, variant = tail, ""
            yield from_slug, to_slug, variant, jp


def _read_eval_summary(json_path: Path) -> Tuple[bool, float]:
    try:
        d = json.loads(json_path.read_text())
    except (json.JSONDecodeError, OSError):
        return False, float("-inf")
    ev = d.get("evaluation", {}) or {}
    em = ev.get("exact_match", {}) or {}
    hit = bool(em.get("steered_has_to_answer"))
    summary = (
        ev.get("logit_trajectory", {}).get("summary", {})
        if isinstance(ev.get("logit_trajectory", {}), dict)
        else {}
    )
    best_gap = summary.get("best_gap")
    if best_gap is None:
        best_gap = float("-inf")
    return hit, float(best_gap)


def _pick_best_variant(
    base_path: Path,
    work_root: Path,
    from_slug: str,
    to_slug: str,
    variant: str,
) -> Tuple[Path, bool, bool, float]:
    """
    Pick between ``<base>.json`` and ``<base>__m_tuned.json``.

    Returns: (chosen_path, used_m_tuned, hit, best_gap).
    Prefers ``__m_tuned.json`` when present (per the plan). The hit is
    taken from the chosen JSON. The best_gap used for cross-variant
    tie-breaking is always taken from the base JSON, because m_tuned
    siblings do not carry ``logit_trajectory``; this keeps the ordering
    well-defined while still preferring an M-search rescue when one
    exists at the same variant.
    """
    m_tuned = base_path.with_name(base_path.stem + "__m_tuned.json")
    chosen = m_tuned if m_tuned.exists() else base_path
    used_m_tuned = chosen == m_tuned
    hit_chosen, _ = _read_eval_summary(chosen)
    _, gap_for_ranking = _read_eval_summary(base_path)
    return chosen, used_m_tuned, hit_chosen, gap_for_ranking


def _work_dir_for(
    work_root: Path,
    from_slug: str,
    to_slug: str,
    variant: str,
    used_m_tuned: bool,
) -> Path:
    """
    Resolve the work directory holding ``features.json`` for the chosen
    (variant, m_tuned) selection.

    Note: ``__m_tuned`` reruns reuse the base variant's feature bag with
    a different M_amplify, so the canonical work dir is the base one
    (without the ``__m_tuned`` suffix). We fall back to the m_tuned
    suffix only if the base one is missing for some reason.
    """
    base_id = f"{from_slug}__to__{to_slug}"
    if variant:
        base_id = f"{base_id}__{variant}"
    base_dir = work_root / base_id
    if base_dir.exists():
        return base_dir
    if used_m_tuned:
        return work_root / f"{base_id}__m_tuned"
    return base_dir


def _select_best_per_pair(
    by_source_dir: Path,
    work_root: Path,
) -> Dict[Tuple[str, str], PairResult]:
    """For each (from, to), choose the winning variant + m_tuned status."""
    best: Dict[Tuple[str, str], PairResult] = {}
    for from_slug, to_slug, variant, jp in _enumerate_pair_jsons(by_source_dir):
        chosen_path, used_m_tuned, hit, gap = _pick_best_variant(
            jp, work_root, from_slug, to_slug, variant
        )
        try:
            payload = json.loads(chosen_path.read_text())
        except (json.JSONDecodeError, OSError):
            continue
        n_abl = int(payload.get("interventions", {}).get("ablate_count", 0) or 0)
        n_amp = int(payload.get("interventions", {}).get("amplify_count", 0) or 0)
        wd = _work_dir_for(work_root, from_slug, to_slug, variant, used_m_tuned)
        candidate = PairResult(
            from_slug=from_slug,
            to_slug=to_slug,
            variant=variant,
            used_m_tuned=used_m_tuned,
            hit=hit,
            best_gap=gap,
            n_ablate=n_abl,
            n_amplify=n_amp,
            work_dir=wd,
        )
        key = (from_slug, to_slug)
        prev = best.get(key)
        if prev is None:
            best[key] = candidate
            continue
        # Selection rule: hit dominates; ties broken by best_gap.
        prev_score = (1 if prev.hit else 0, prev.best_gap)
        cand_score = (1 if candidate.hit else 0, candidate.best_gap)
        if cand_score > prev_score:
            best[key] = candidate
    return best


def _run(domain: str, dataset_dir: Path, run_id: str, out_csv: Path) -> int:
    by_source = dataset_dir / "_swaps" / "runs" / run_id / "by_source"
    work_root = dataset_dir / "_swaps" / "runs" / run_id / "work"
    if not by_source.exists():
        print(f"  [SKIP] {domain}: no by_source at {by_source}")
        return 1
    if not work_root.exists():
        print(f"  [SKIP] {domain}: no work dir at {work_root}")
        return 1

    print(f"  [{domain}] selecting best variant per pair...")
    best_per_pair = _select_best_per_pair(by_source, work_root)
    print(f"  [{domain}] {len(best_per_pair)} pairs")

    cache: Dict[str, Dict[Tuple[int, int], float]] = {}

    out_csv.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0
    skipped = 0
    skip_reasons: Dict[str, int] = {}
    with out_csv.open("w", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow([
            "from_slug",
            "to_slug",
            "winning_variant",
            "used_m_tuned",
            "hit",
            "best_gap",
            "n_ablate_labeled",
            "n_amplify_labeled",
            "n_ablate_in_features_json",
            "n_amplify_in_features_json",
            "ref_sum_src",
            "ref_sum_tgt",
            "src_total_influence",
            "tgt_total_influence",
        ])
        for (from_slug, to_slug), pr in sorted(best_per_pair.items()):
            features = _read_features_json(pr.work_dir)
            if features is None:
                skipped += 1
                skip_reasons["features_json_missing"] = skip_reasons.get(
                    "features_json_missing", 0
                ) + 1
                continue
            abl_keys, amp_keys = _split_features_by_role(features)
            src_inf = _load_metrics_index(dataset_dir, from_slug, cache)
            tgt_inf = _load_metrics_index(dataset_dir, to_slug, cache)
            if not src_inf:
                skipped += 1
                skip_reasons["no_src_metrics"] = skip_reasons.get(
                    "no_src_metrics", 0
                ) + 1
                continue
            if not tgt_inf:
                skipped += 1
                skip_reasons["no_tgt_metrics"] = skip_reasons.get(
                    "no_tgt_metrics", 0
                ) + 1
                continue
            ref_sum_src = _sum_influence(abl_keys, src_inf)
            ref_sum_tgt = _sum_influence(amp_keys, tgt_inf)
            src_total = sum(src_inf.values())
            tgt_total = sum(tgt_inf.values())
            writer.writerow([
                from_slug,
                to_slug,
                pr.variant,
                int(pr.used_m_tuned),
                int(pr.hit),
                f"{pr.best_gap:.6f}",
                pr.n_ablate,
                pr.n_amplify,
                len(abl_keys),
                len(amp_keys),
                f"{ref_sum_src:.6f}",
                f"{ref_sum_tgt:.6f}",
                f"{src_total:.6f}",
                f"{tgt_total:.6f}",
            ])
            rows_written += 1
    print(
        f"  [{domain}] wrote {rows_written} rows to {out_csv} "
        f"(skipped {skipped}: {skip_reasons or 'none'})"
    )
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--domains",
        nargs="*",
        default=list(DOMAINS),
        choices=list(DOMAINS),
        help="Domains to process (default: all 4 in-scope domains).",
    )
    parser.add_argument(
        "--out-dir",
        default="output/research",
        help="Where to write topk_budgets_<domain>.csv (default: output/research).",
    )
    args = parser.parse_args()

    out_dir = (REPO / args.out_dir).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)

    rc = 0
    for domain in args.domains:
        cfg = DOMAINS[domain]
        dataset_dir = (REPO / cfg["dataset_dir"]).resolve()
        out_csv = out_dir / f"topk_budgets_{domain}.csv"
        rc |= _run(domain, dataset_dir, cfg["run_id"], out_csv)
    return rc


if __name__ == "__main__":
    sys.exit(main())
