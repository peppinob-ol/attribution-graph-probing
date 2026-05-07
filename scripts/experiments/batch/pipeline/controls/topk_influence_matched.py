"""
Top-K-by-influence intervention builder, per-pair influence-budget matched.

For each swap pair, builds a single bag of source ablation features and
target amplification features by ranking each entity's own
``graph_feature_static_metrics.csv`` rows by ``node_influence`` (descending,
deduped at ``(layer, id)``-level via max) and taking the smallest prefix
whose cumulative ``node_influence`` reaches the per-pair reference budget
read from a pre-computed CSV.

This is the fair influence-only baseline against the labeled best-of
field-additivity-with-adaptive-M reference: the bag has no concept-field
semantics, gets no per-variant subsetting, only an outer M-search sweep.

Config block::

    control:
      mode: topk_influence_matched
      budgets_csv: output/research/topk_budgets_<domain>.csv
      # Optional knobs (with defaults):
      min_K: 1                 # minimum number of features per side, even if budget == 0
      include_layer_minus_one: false  # whether to consider layer == -1 rows (embedding/logit)
"""
from __future__ import annotations

import csv
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .base import InterventionBuilder
from .matching import build_intervention_dicts
from .types import InterventionResult


# Module-level cache so repeated calls within a single run reuse the same
# parsed budget table (the runner instantiates the builder once but we
# keep it tolerant to multiple instances).
_BUDGET_CACHE: Dict[Path, Dict[Tuple[str, str], Dict[str, float]]] = {}


def _load_budgets(csv_path: Path) -> Dict[Tuple[str, str], Dict[str, float]]:
    csv_path = csv_path.resolve()
    cached = _BUDGET_CACHE.get(csv_path)
    if cached is not None:
        return cached
    if not csv_path.exists():
        raise FileNotFoundError(f"budgets_csv not found: {csv_path}")
    table: Dict[Tuple[str, str], Dict[str, float]] = {}
    with csv_path.open() as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            key = (row["from_slug"], row["to_slug"])
            try:
                table[key] = {
                    "ref_sum_src": float(row["ref_sum_src"]),
                    "ref_sum_tgt": float(row["ref_sum_tgt"]),
                    "n_ablate_labeled": float(row.get("n_ablate_labeled", 0) or 0),
                    "n_amplify_labeled": float(
                        row.get("n_amplify_labeled", 0) or 0
                    ),
                }
            except (TypeError, ValueError):
                continue
    _BUDGET_CACHE[csv_path] = table
    return table


def _resolve_budgets_csv(control_cfg: Dict[str, Any]) -> Path:
    raw = control_cfg.get("budgets_csv")
    if not raw:
        raise ValueError(
            "control.mode=topk_influence_matched requires control.budgets_csv"
        )
    p = Path(str(raw))
    if not p.is_absolute():
        # Resolve relative to the repo root (3 parents up from this file:
        # controls/ -> pipeline/ -> batch/ -> experiments/ -> scripts/ -> repo).
        repo_root = Path(__file__).resolve().parents[5]
        p = (repo_root / p).resolve()
    return p


def _topk_by_influence(
    metrics_df: Any,
    grouping_df: Any,
    budget: float,
    *,
    min_K: int = 1,
) -> List[Dict[str, int]]:
    """
    Return the smallest top-K prefix of ``(layer, feature_id)`` rows from
    ``metrics_df`` (sorted by max ``node_influence`` desc) whose cumulative
    influence reaches ``budget``.

    Universe restriction: features must appear in ``grouping_df`` (i.e.
    they are real steerable CLT features that the pipeline classified).
    This excludes scaffold/error rows (``feature == -1``) and embedding/
    logit-only rows (``layer == -1`` or ``layer >= n_transcoder_layers``)
    in one shot, mirroring the universe used by
    ``tools/build_topk_dallas_conditions.py``.

    Each returned entry is a dict::

        {"layer": int, "index": int, "node_influence": float}

    suitable for passing into ``build_intervention_dicts``.
    """
    if metrics_df is None or len(metrics_df) == 0:
        return []
    if grouping_df is None or len(grouping_df) == 0:
        return []

    metrics = metrics_df[["layer", "id", "node_influence"]].copy()
    metrics["layer"] = metrics["layer"].astype(int)
    metrics["id"] = metrics["id"].astype(int)
    metrics = metrics[metrics["node_influence"].notna()]
    if len(metrics) == 0:
        return []
    inf_by_pair = (
        metrics.groupby(["layer", "id"], as_index=False)["node_influence"]
        .max()
        .rename(columns={"id": "feature"})
    )

    grp = grouping_df[["layer", "feature"]].copy()
    grp["layer"] = grp["layer"].astype(int)
    grp["feature"] = grp["feature"].astype(int)
    bag = grp.drop_duplicates().reset_index(drop=True)

    merged = bag.merge(inf_by_pair, how="left", on=["layer", "feature"]).fillna(
        {"node_influence": 0.0}
    )
    merged = merged.sort_values("node_influence", ascending=False).reset_index(
        drop=True
    )

    if budget <= 0:
        prefix = merged.head(max(min_K, 0))
    else:
        cumulative = merged["node_influence"].cumsum().to_numpy()
        cutoff_idx = 0
        for i, c in enumerate(cumulative):
            if c >= budget:
                cutoff_idx = i + 1
                break
        else:
            cutoff_idx = len(merged)
        cutoff_idx = max(cutoff_idx, min_K)
        prefix = merged.head(cutoff_idx)

    out: List[Dict[str, int]] = []
    for row in prefix.itertuples(index=False):
        out.append(
            {
                "layer": int(row.layer),
                "index": int(row.feature),
                "node_influence": float(row.node_influence),
            }
        )
    return out


class TopKInfluenceMatchedBuilder(InterventionBuilder):
    """
    Build per-pair influence-budget-matched top-K-by-node-influence bags.

    No concept-field semantics: every selected source feature is ablated,
    every selected target feature is amplified. Outer M-search (if
    enabled in the config) tunes ``M_amplify`` only.
    """

    def build_for_pair(
        self,
        *,
        ct_steering: Any,
        config: Dict[str, Any],
        pair: Any,
        data_from: Dict[str, Any],
        data_to: Dict[str, Any],
    ) -> InterventionResult:
        ct_config = config.get("ct_steering", {})
        M_ablate = ct_config.get("M_ablate", 0.0)
        M_amplify = ct_config.get("M_amplify", 2.0)
        steer_generated = ct_config.get("steer_generated_tokens", False)

        control_cfg = config.get("control", {}) or {}
        min_K = int(control_cfg.get("min_K", 1))

        budgets_csv = _resolve_budgets_csv(control_cfg)
        budgets = _load_budgets(budgets_csv)

        key = (pair.from_slug, pair.to_slug)
        if key not in budgets:
            print(
                f"  Warning: no budget row for ({pair.from_slug}, "
                f"{pair.to_slug}) in {budgets_csv.name}; skipping pair."
            )
            return InterventionResult(
                features=[],
                ablate_count=0,
                amplify_count=0,
                control_mode="topk_influence_matched",
                diagnostics={"missing_budget": True},
            )
        ref = budgets[key]
        ref_sum_src = ref["ref_sum_src"]
        ref_sum_tgt = ref["ref_sum_tgt"]

        # Source side -> ABLATION
        src_topk = _topk_by_influence(
            data_from.get("metrics"),
            data_from.get("grouping"),
            ref_sum_src,
            min_K=min_K,
        )
        ablate_interventions = build_intervention_dicts(
            src_topk,
            M_ablate,
            steer_generated_tokens=steer_generated,
            use_stored_as_base=False,
        )

        # Target side -> AMPLIFICATION (skip on identity swaps)
        amplify_interventions: List[Dict[str, Any]] = []
        tgt_topk: List[Dict[str, int]] = []
        if pair.from_slug != pair.to_slug:
            tgt_topk = _topk_by_influence(
                data_to.get("metrics"),
                data_to.get("grouping"),
                ref_sum_tgt,
                min_K=min_K,
            )
            activations_map_to = data_to.get("activations_map", {})
            amplify_interventions = build_intervention_dicts(
                tgt_topk,
                M_amplify,
                steer_generated_tokens=steer_generated,
                use_stored_as_base=True,
                activations_map=(
                    activations_map_to if activations_map_to else None
                ),
            )

        features = ablate_interventions + amplify_interventions

        diagnostics = {
            "K_src": len(src_topk),
            "K_tgt": len(tgt_topk),
            "ref_sum_src": ref_sum_src,
            "ref_sum_tgt": ref_sum_tgt,
            "achieved_sum_src": sum(f["node_influence"] for f in src_topk),
            "achieved_sum_tgt": sum(f["node_influence"] for f in tgt_topk),
            "n_ablate_labeled_ref": int(ref.get("n_ablate_labeled", 0)),
            "n_amplify_labeled_ref": int(ref.get("n_amplify_labeled", 0)),
            "budgets_csv": str(budgets_csv),
        }

        return InterventionResult(
            features=features,
            ablate_count=len(ablate_interventions),
            amplify_count=len(amplify_interventions),
            control_mode="topk_influence_matched",
            diagnostics=diagnostics,
        )
