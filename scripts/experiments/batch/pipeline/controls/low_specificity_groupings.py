"""
Low-specificity groupings control builder.

Instead of intervening on the concept-matched supernodes (which are
predicted to have high steering specificity), this control selects
supernodes predicted to have *low* steering specificity and swaps them
instead.

This tests the hypothesis: "does the steering effect depend on
selecting the *right* supernodes, or would any coherent grouping
of similar size produce comparable effects?"

Selection strategies (configurable):
  - ``predicted_low_specificity``: rank supernodes by a specificity
    score field in the grouping/metrics data, pick the lowest-scoring
    ones that match the labeled intervention's size.
  - ``random_supernode``: pick non-concept-matching supernodes at
    random (matched on member count).

Config example::

    control:
      mode: low_specificity_groupings
      seed: 42
      selector:
        strategy: random_supernode  # or predicted_low_specificity
        # For predicted_low_specificity:
        # score_field: steering_specificity_score
        # max_threshold: 0.2
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Set, Tuple

import pandas as pd

from .base import InterventionBuilder
from .types import InterventionResult
from .concept_sets import get_concept_fields
from .exclusions import exclude_concept_matching_supernodes
from .sampling import make_control_rng
from .matching import build_intervention_dicts


def _concept_text(text: str) -> str:
    t = (text or "").strip().lower()
    if t.endswith(" city"):
        t = t[: -len(" city")].strip()
    return t


def _collect_supernodes(
    grouping_df: pd.DataFrame,
    exclude_keys: Set[Tuple[int, int]],
    supernode_col: str = "supernode_name",
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group features by supernode name, excluding features in *exclude_keys*.

    Returns mapping from supernode name -> list of feature dicts.
    """
    has_position = "position" in grouping_df.columns
    supernodes: Dict[str, List[Dict[str, Any]]] = {}
    for _, row in grouping_df.iterrows():
        key = (int(row["layer"]), int(row["feature"]))
        if key in exclude_keys:
            continue
        name = str(row.get(supernode_col, "")).strip()
        if not name:
            continue
        pos = int(row["position"]) if has_position and pd.notna(row.get("position")) else -1
        supernodes.setdefault(name, []).append({
            "layer": key[0],
            "index": key[1],
            "position": pos,
        })
    return supernodes


def _select_supernodes_random(
    rng: Any,
    available: Dict[str, List[Dict[str, Any]]],
    target_feature_count: int,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Greedily pick random supernodes until we have >= target_feature_count
    features, then truncate to match exactly.
    """
    names = list(available.keys())
    rng.shuffle(names)
    selected_features: List[Dict[str, Any]] = []
    selected_names: List[str] = []
    for name in names:
        if len(selected_features) >= target_feature_count:
            break
        selected_features.extend(available[name])
        selected_names.append(name)

    if len(selected_features) > target_feature_count:
        selected_features = selected_features[:target_feature_count]
    return selected_features, selected_names


def _select_supernodes_low_score(
    available: Dict[str, List[Dict[str, Any]]],
    metrics_df: pd.DataFrame,
    target_feature_count: int,
    score_field: str,
) -> Tuple[List[Dict[str, Any]], List[str]]:
    """
    Pick supernodes with the lowest average score on *score_field*
    until we reach *target_feature_count*.
    """
    if score_field not in metrics_df.columns:
        return [], []

    scores: Dict[str, float] = {}
    for name, feats in available.items():
        feat_scores = []
        for f in feats:
            mask = (metrics_df["layer"] == f["layer"]) & (metrics_df["feature"] == f["index"])
            vals = metrics_df.loc[mask, score_field].dropna()
            if not vals.empty:
                feat_scores.append(float(vals.iloc[0]))
        if feat_scores:
            scores[name] = sum(feat_scores) / len(feat_scores)

    ranked = sorted(scores.keys(), key=lambda n: scores[n])

    selected_features: List[Dict[str, Any]] = []
    selected_names: List[str] = []
    for name in ranked:
        if len(selected_features) >= target_feature_count:
            break
        selected_features.extend(available[name])
        selected_names.append(name)

    if len(selected_features) > target_feature_count:
        selected_features = selected_features[:target_feature_count]
    return selected_features, selected_names


class LowSpecificityGroupingsBuilder(InterventionBuilder):
    """
    Selects supernodes predicted to have low steering specificity
    and uses them as the intervention set.
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
        swap_cfg = config.get("swap", {})
        control_cfg = config.get("control", {})
        selector_cfg = control_cfg.get("selector", {})
        strategy = selector_cfg.get("strategy", "random_supernode")

        seed = control_cfg.get("seed", ct_config.get("seed", 42))
        replicate_id = control_cfg.get("_current_replicate", 0)
        concept_fields = get_concept_fields(swap_cfg)

        rng = make_control_rng(
            seed, pair.swap_id, replicate_id, "low_specificity"
        )

        # Get the labeled reference for sizing
        from .labeled import LabeledInterventionBuilder

        labeled = LabeledInterventionBuilder()
        ref = labeled.build_for_pair(
            ct_steering=ct_steering,
            config=config,
            pair=pair,
            data_from=data_from,
            data_to=data_to,
        )
        ref_ablate = [f for f in ref.features if f.get("M") == M_ablate]
        ref_amplify = [f for f in ref.features if f.get("M") == M_amplify]

        # Build exclusion sets (exclude concept-matched supernodes)
        source_concepts = [
            _concept_text(pair.from_entity.get(f, "")) for f in concept_fields
        ]
        target_concepts = [
            _concept_text(pair.to_entity.get(f, "")) for f in concept_fields
        ]

        exclude_from = exclude_concept_matching_supernodes(
            data_from["grouping"], [c for c in source_concepts if c]
        )
        exclude_to = (
            exclude_concept_matching_supernodes(
                data_to["grouping"], [c for c in target_concepts if c]
            )
            if pair.from_slug != pair.to_slug
            else set()
        )

        available_from = _collect_supernodes(data_from["grouping"], exclude_from)
        available_to = (
            _collect_supernodes(data_to["grouping"], exclude_to)
            if pair.from_slug != pair.to_slug
            else {}
        )

        diagnostics: Dict[str, Any] = {
            "strategy": strategy,
            "available_supernodes_from": len(available_from),
            "available_supernodes_to": len(available_to),
            "ref_ablate_count": len(ref_ablate),
            "ref_amplify_count": len(ref_amplify),
        }

        # Select source-side features
        if strategy == "predicted_low_specificity":
            score_field = selector_cfg.get("score_field", "cumulative_influence")
            ablate_feats, ablate_names = _select_supernodes_low_score(
                available_from, data_from["metrics"], len(ref_ablate), score_field
            )
        else:
            ablate_feats, ablate_names = _select_supernodes_random(
                rng, available_from, len(ref_ablate)
            )

        diagnostics["selected_source_supernodes"] = ablate_names

        ablate_interventions = build_intervention_dicts(
            ablate_feats, M_ablate,
            steer_generated_tokens=steer_generated,
            use_stored_as_base=False,
        )

        # Select target-side features
        amplify_interventions: List[Dict[str, Any]] = []
        if pair.from_slug != pair.to_slug and available_to:
            if strategy == "predicted_low_specificity":
                amplify_feats, amplify_names = _select_supernodes_low_score(
                    available_to, data_to["metrics"], len(ref_amplify), score_field
                )
            else:
                amplify_feats, amplify_names = _select_supernodes_random(
                    rng, available_to, len(ref_amplify)
                )
            diagnostics["selected_target_supernodes"] = amplify_names

            activations_map_to = data_to.get("activations_map", {})
            amplify_interventions = build_intervention_dicts(
                amplify_feats, M_amplify,
                steer_generated_tokens=steer_generated,
                use_stored_as_base=True,
                activations_map=activations_map_to if activations_map_to else None,
            )

        features = ablate_interventions + amplify_interventions

        return InterventionResult(
            features=features,
            ablate_count=len(ablate_interventions),
            amplify_count=len(amplify_interventions),
            control_mode="low_specificity_groupings",
            concept_subsets_used=concept_fields,
            replicate_id=replicate_id,
            diagnostics=diagnostics,
        )
