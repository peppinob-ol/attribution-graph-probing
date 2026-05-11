"""
Cross-run best-per-cell aggregator.

Scans all eligible (display_demo, dropdown-visible) runs for a dataset and
picks the winning configuration per matrix cell using a lexicographic
scoring tuple: tier > exact-match flags > target logit rank > VsMax.

The eligibility filter mirrors ``_is_dropdown_run`` from ``loader.py`` so
"Best across runs" only considers the runs the user can actually inspect.
Random-feature-matched runs are additionally excluded from the best
selection because they are baselines, not candidate configurations.

Cross-run cell pruning: the registry computes the intersection of entity
slugs across all visible runs (``DemoRegistry.get_allowed_slugs``). Cells
whose source or target are not in that intersection are skipped here, so
manually deleting a flawed entity in one run propagates to the cross-run
best matrix as well.
"""
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, TYPE_CHECKING
import json

from .loader import DataLoader, _is_dropdown_run

if TYPE_CHECKING:
    from .loader import DemoRegistry


def _get_vsmax(swap_data: Dict) -> Optional[float]:
    """Same as ``DataLoader._get_vsmax_from_swap`` (static method)."""
    return DataLoader._get_vsmax_from_swap(swap_data)


def _score_from_swap(
    swap_data: Dict, run_id: str, loader: "DataLoader"
) -> Tuple:
    """Build lexicographic comparison tuple from a swap JSON.

    Tier extraction is delegated to ``loader._get_tier_from_swap`` so the
    cross-run aggregator agrees bit-for-bit with the per-run "Best per
    cell" view -- including the word-level fallback that needs the
    domain word blacklist. Without this, runs that don't ship
    ``classification.tier`` (e.g. field-additivity) silently regress
    when bestMode is enabled.

    Components (all oriented so *higher* tuple = better):
      1. tier (float)
      2. steered_has_to_answer (bool -- True > False)
      3. steered_has_to_capital (bool)
      4. -target_rank (negated: rank 1 -> -1 beats rank 50 -> -50)
      5. vsmax (best_target_minus_max, higher is better)
      6. run_id (stable tie-break)
    """
    tier = loader._get_tier_from_swap(swap_data)
    if tier is None:
        tier = float("-inf")
    exact = swap_data.get("evaluation", {}).get("exact_match", {})
    has_to_answer = bool(exact.get("steered_has_to_answer"))
    has_to_capital = bool(exact.get("steered_has_to_capital"))

    baseline = swap_data.get("evaluation", {}).get("baseline_logits", {})
    target_rank = baseline.get("target", {}).get("rank")
    neg_rank = -target_rank if target_rank is not None else float("-inf")

    vsmax = _get_vsmax(swap_data)
    vsmax_val = vsmax if vsmax is not None else float("-inf")

    return (tier, has_to_answer, has_to_capital, neg_rank, vsmax_val, run_id)


def _extract_winner_meta(
    swap_data: Dict, score: Tuple, run_id: str, run_label: str, variant: str
) -> Dict[str, Any]:
    """Extract the fields surfaced in the winner payload."""
    neg_rank = score[3]
    target_rank = int(-neg_rank) if neg_rank != float("-inf") else None
    vsmax_val = score[4] if score[4] != float("-inf") else None

    ctrl = swap_data.get("metadata", {}).get("control", {})
    return {
        "run_id": run_id,
        "run_label": run_label,
        "variant": variant or None,
        "tier": score[0],
        "target_rank": target_rank,
        "vsmax": round(vsmax_val, 2) if vsmax_val is not None else None,
        "control_mode": ctrl.get("control_mode"),
        "fields_used": ctrl.get("concept_subsets_used"),
    }


class CrossRunBestAggregator:
    """Pick the best swap configuration per cell across multiple runs.

    Instantiated once per ``DemoRegistry`` and cached lazily per dataset.
    """

    def __init__(self, source):
        """*source* is either a ``DemoRegistry`` (preferred) or a raw
        ``{dataset_id: {"dir", "label", "runs"}}`` dict (legacy / tests).

        When a registry is passed, the aggregator queries it for the
        cross-run allowed-slug intersection so deletions in any one run
        propagate to the best matrix. With a raw dict no filtering is
        applied (every cell from every visible run participates).
        """
        if hasattr(source, "_datasets"):
            self._registry = source
            self._datasets = source._datasets
        else:
            self._registry = None
            self._datasets = source
        self._cache: Dict[str, Dict] = {}

    def invalidate(self, dataset_id: Optional[str] = None) -> None:
        if dataset_id:
            self._cache.pop(dataset_id, None)
        else:
            self._cache.clear()

    def get_best_matrix(self, dataset_id: str) -> Dict[str, Any]:
        """Return ``{"matrix", "winners", "considered_runs"}`` for the dataset.

        ``considered_runs`` is the list of runs that took part in the
        per-cell competition, in the order they were scanned. Each entry
        is ``{"id", "label", "control_mode"}`` and is intended for the
        UI badge that explains the cross-run-best mode.
        """
        if dataset_id in self._cache:
            return self._cache[dataset_id]

        ds = self._datasets.get(dataset_id)
        if not ds:
            return {"matrix": {}, "winners": {}, "considered_runs": []}

        eligible_runs = [
            r
            for r in ds["runs"]
            if _is_dropdown_run(r["id"], r.get("manifest", {}))
            and r.get("control_mode") != "random_feature_matched"
        ]
        if not eligible_runs:
            return {"matrix": {}, "winners": {}, "considered_runs": []}

        allowed = (
            self._registry.get_allowed_slugs(dataset_id)
            if self._registry is not None else None
        )

        run_labels: Dict[str, str] = {}
        best_per_cell: Dict[Tuple[str, str], Tuple] = {}
        considered: List[Dict[str, Any]] = []

        for run_info in eligible_runs:
            rid = run_info["id"]
            run_labels[rid] = run_info.get("semantic_label", rid)
            considered.append({
                "id": rid,
                "label": run_info.get("semantic_label", rid),
                "control_mode": run_info.get("control_mode", ""),
            })
            loader = DataLoader(ds["dir"], run_id=rid, allowed_slugs=allowed)
            self._scan_run(loader, rid, run_labels, best_per_cell, allowed)

        matrix: Dict[str, Dict[str, Optional[float]]] = {}
        winners: Dict[str, Dict[str, Dict]] = {}

        for (from_slug, to_slug), entry in best_per_cell.items():
            _score, _rid, _var, meta = entry
            matrix.setdefault(from_slug, {})[to_slug] = meta["tier"]
            winners.setdefault(from_slug, {})[to_slug] = meta

        result = {
            "matrix": matrix,
            "winners": winners,
            "considered_runs": considered,
        }
        self._cache[dataset_id] = result
        return result

    # ------------------------------------------------------------------

    def _scan_run(
        self,
        loader: DataLoader,
        run_id: str,
        run_labels: Dict[str, str],
        best: Dict[Tuple[str, str], Tuple],
        allowed: Optional[Set[str]] = None,
    ) -> None:
        """Scan one run and update *best* in-place (running max per cell).

        Cells whose source or target slug is missing from *allowed*
        (the cross-run intersection) are skipped, so deletions in any
        one run propagate to the synthetic best matrix.
        """
        idx = loader._build_variant_index()
        label = run_labels.get(run_id, run_id)

        for from_slug, targets in idx.items():
            if allowed is not None and from_slug not in allowed:
                continue
            for to_slug, records in targets.items():
                if allowed is not None and to_slug not in allowed:
                    continue
                hit = self._score_cell(records, run_id, label, loader)
                if hit is None:
                    continue
                score, variant, meta = hit
                key = (from_slug, to_slug)
                if key not in best or score > best[key][0]:
                    best[key] = (score, run_id, variant, meta)

        work_dir = loader.swaps_dir / "work"
        if not work_dir.exists():
            return
        for swap_file in work_dir.glob("*.json"):
            stem = swap_file.stem
            if "__to__" not in stem:
                continue
            from_slug, to_slug = stem.split("__to__", 1)
            if allowed is not None and (
                from_slug not in allowed or to_slug not in allowed
            ):
                continue
            key = (from_slug, to_slug)
            if key in best and best[key][1] == run_id:
                continue
            data = self._try_load(swap_file)
            if data is None:
                continue
            score = _score_from_swap(data, run_id, loader)
            meta = _extract_winner_meta(data, score, run_id, label, "")
            if key not in best or score > best[key][0]:
                best[key] = (score, run_id, "", meta)

    def _score_cell(
        self,
        records: List[Dict],
        run_id: str,
        run_label: str,
        loader: "DataLoader",
    ) -> Optional[Tuple[Tuple, str, Dict]]:
        """Score one (from, to) cell within a run.

        Considers the canonical record AND every variant on equal footing
        and returns the lexicographic max. Required so that the cross-run
        best is always >= the per-run "Best per cell" view (otherwise a
        run whose canonical happens to be a 3-field swap would mask its
        own field-additivity wins).

        Returns ``(score_tuple, variant_suffix, meta_dict)`` or None.
        """
        best: Optional[Tuple[Tuple, str, Dict]] = None
        for rec in records:
            data = self._try_load(rec["path"])
            if data is None:
                continue
            score = _score_from_swap(data, run_id, loader)
            suffix = "" if rec["is_canonical"] else rec.get("variant_suffix", "")
            if best is None or score > best[0]:
                meta = _extract_winner_meta(
                    data, score, run_id, run_label, suffix
                )
                best = (score, suffix, meta)
        return best

    @staticmethod
    def _try_load(path) -> Optional[Dict]:
        try:
            with open(path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except (json.JSONDecodeError, IOError):
            return None
