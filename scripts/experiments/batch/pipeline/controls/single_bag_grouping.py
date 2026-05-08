"""
Single-bag grouping intervention builder.

For each swap pair, builds a single bag of source ablation features and
target amplification features by taking *every* unique ``(layer, feature)``
row in the side's ``data["grouping"]`` DataFrame, with no concept-field
semantics, no ``supernode_name`` filtering, and no per-variant subsetting.

Use case: pair this control with a graphs root whose target-side grouping
has been pre-filtered (e.g. by ``tools/build_topk_dallas_conditions.py``)
to a specific subset like the top-K features by ``node_influence``. The
source side keeps its canonical grouping (via symlink) so the source
ablation is held constant across conditions and the only varying
quantity is the target bag.

This is the fair influence-only baseline against the labeled best-of
field-additivity reference: pure top-K ranking with no label-driven
boost. Outer M-search (if enabled) tunes ``M_amplify`` only.

Config block::

    control:
      mode: single_bag_grouping
"""
from __future__ import annotations

from typing import Any, Dict, List

from .base import InterventionBuilder
from .matching import build_intervention_dicts
from .types import InterventionResult


def _bag_from_grouping(grouping_df: Any, metrics_df: Any) -> List[Dict[str, Any]]:
    """
    Return the full deduped ``(layer, feature)`` bag from ``grouping_df``,
    each entry annotated with its max ``node_influence`` from ``metrics_df``
    when available (zero otherwise).

    Each returned entry is a dict::

        {"layer": int, "index": int, "node_influence": float}
    """
    if grouping_df is None or len(grouping_df) == 0:
        return []

    grp = grouping_df[["layer", "feature"]].copy()
    grp["layer"] = grp["layer"].astype(int)
    grp["feature"] = grp["feature"].astype(int)
    bag = grp.drop_duplicates().reset_index(drop=True)

    if metrics_df is not None and len(metrics_df) > 0:
        metrics = metrics_df[["layer", "id", "node_influence"]].copy()
        metrics["layer"] = metrics["layer"].astype(int)
        metrics["id"] = metrics["id"].astype(int)
        metrics = metrics[metrics["node_influence"].notna()]
        if len(metrics) > 0:
            inf_by_pair = (
                metrics.groupby(["layer", "id"], as_index=False)["node_influence"]
                .max()
                .rename(columns={"id": "feature"})
            )
            bag = bag.merge(inf_by_pair, how="left", on=["layer", "feature"])
        else:
            bag["node_influence"] = 0.0
    else:
        bag["node_influence"] = 0.0

    bag = bag.fillna({"node_influence": 0.0})
    bag = bag.sort_values("node_influence", ascending=False).reset_index(drop=True)

    out: List[Dict[str, Any]] = []
    for row in bag.itertuples(index=False):
        out.append(
            {
                "layer": int(row.layer),
                "index": int(row.feature),
                "node_influence": float(row.node_influence),
            }
        )
    return out


class SingleBagGroupingBuilder(InterventionBuilder):
    """
    Build per-pair single-bag interventions from raw ``data["grouping"]``.

    No concept-field semantics: every source-grouping ``(layer, feature)``
    is ablated, every target-grouping ``(layer, feature)`` is amplified.
    Outer M-search (if enabled) tunes ``M_amplify`` only.
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

        src_bag = _bag_from_grouping(
            data_from.get("grouping"),
            data_from.get("metrics"),
        )
        ablate_interventions = build_intervention_dicts(
            src_bag,
            M_ablate,
            steer_generated_tokens=steer_generated,
            use_stored_as_base=False,
        )

        amplify_interventions: List[Dict[str, Any]] = []
        tgt_bag: List[Dict[str, Any]] = []
        if pair.from_slug != pair.to_slug:
            tgt_bag = _bag_from_grouping(
                data_to.get("grouping"),
                data_to.get("metrics"),
            )
            activations_map_to = data_to.get("activations_map", {})
            amplify_interventions = build_intervention_dicts(
                tgt_bag,
                M_amplify,
                steer_generated_tokens=steer_generated,
                use_stored_as_base=True,
                activations_map=(
                    activations_map_to if activations_map_to else None
                ),
            )

        features = ablate_interventions + amplify_interventions

        diagnostics = {
            "n_src": len(src_bag),
            "n_tgt": len(tgt_bag),
            "achieved_sum_src": sum(f["node_influence"] for f in src_bag),
            "achieved_sum_tgt": sum(f["node_influence"] for f in tgt_bag),
        }

        return InterventionResult(
            features=features,
            ablate_count=len(ablate_interventions),
            amplify_count=len(amplify_interventions),
            control_mode="single_bag_grouping",
            diagnostics=diagnostics,
        )
