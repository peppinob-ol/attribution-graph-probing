"""
Matched random-feature control builder.

For each swap pair, constructs a structurally matched null intervention
by sampling:
  - source-side ablation features from the source graph
  - target-side amplification features from the target graph

while preserving:
  - exact feature count per role
  - layer distribution per role
  - intervention mode (live-multiply for source, stored-base for target)
  - exclusion of concept-matched labeled features

This is the primary specificity control described in the methodology:
it tests whether observed steering effects are specific to the labeled
supernodes or arise from any structurally comparable perturbation.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import InterventionBuilder
from .types import InterventionResult
from .concept_sets import get_concept_fields
from .exclusions import (
    exclude_concept_matching_supernodes,
    build_candidate_pool,
    feature_keys_from_interventions,
)
from .sampling import (
    make_control_rng,
    sample_indices_matching_histogram,
    build_layer_histogram,
)
from .matching import (
    build_intervention_dicts,
    compute_match_diagnostics,
)


def _concept_text(text: str) -> str:
    t = (text or "").strip().lower()
    if t.endswith(" city"):
        t = t[: -len(" city")].strip()
    return t


class RandomFeatureMatchedBuilder(InterventionBuilder):
    """
    Produces null interventions by sampling random features from the
    same graphs, matched on count and layer distribution per role.
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

        seed = control_cfg.get("seed", ct_config.get("seed", 42))
        replicate_id = control_cfg.get("_current_replicate", 0)
        match_layers = control_cfg.get("matching", {}).get("match_layers", True)
        exclude_labeled = control_cfg.get("exclusions", {}).get(
            "exclude_labeled_features", True
        )
        exclude_concept_supernodes = control_cfg.get("exclusions", {}).get(
            "exclude_concept_matching_supernodes", True
        )

        concept_fields = get_concept_fields(swap_cfg)
        rng = make_control_rng(
            seed, pair.swap_id, replicate_id, "random_feature_matched"
        )

        # --- Step 1: run the labeled builder to get the reference intervention ---
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

        # --- Step 2: build exclusion sets ---
        exclude_keys_from = set()
        exclude_keys_to = set()

        if exclude_labeled:
            exclude_keys_from |= set(feature_keys_from_interventions(ref_ablate))
            exclude_keys_to |= set(feature_keys_from_interventions(ref_amplify))

        if exclude_concept_supernodes:
            source_concepts = [
                _concept_text(pair.from_entity.get(f, ""))
                for f in concept_fields
            ]
            target_concepts = [
                _concept_text(pair.to_entity.get(f, ""))
                for f in concept_fields
            ]
            exclude_keys_from |= exclude_concept_matching_supernodes(
                data_from["grouping"], [c for c in source_concepts if c]
            )
            if pair.from_slug != pair.to_slug:
                exclude_keys_to |= exclude_concept_matching_supernodes(
                    data_to["grouping"], [c for c in target_concepts if c]
                )

        # --- Step 3: build candidate pools ---
        pool_from = build_candidate_pool(data_from["grouping"], exclude_keys_from)
        pool_to = (
            build_candidate_pool(data_to["grouping"], exclude_keys_to)
            if pair.from_slug != pair.to_slug
            else []
        )

        # --- Step 4: sample matched features ---
        diagnostics: Dict[str, Any] = {
            "pool_from_size": len(pool_from),
            "pool_to_size": len(pool_to),
            "exclusion_from_count": len(exclude_keys_from),
            "exclusion_to_count": len(exclude_keys_to),
            "ref_ablate_count": len(ref_ablate),
            "ref_amplify_count": len(ref_amplify),
        }

        if match_layers:
            ablate_hist = build_layer_histogram(ref_ablate)
            sampled_ablate = sample_indices_matching_histogram(
                rng, pool_from, lambda f: f["layer"], ablate_hist
            )
            ablate_diag = compute_match_diagnostics(
                ablate_hist, build_layer_histogram(
                    [{"layer": f["layer"]} for f in sampled_ablate]
                )
            )
            diagnostics["ablate_layer_match"] = ablate_diag
        else:
            n_ablate = len(ref_ablate)
            take = min(n_ablate, len(pool_from))
            sampled_ablate = rng.sample(pool_from, take) if take > 0 else []

        ablate_interventions = build_intervention_dicts(
            sampled_ablate,
            M_ablate,
            steer_generated_tokens=steer_generated,
            use_stored_as_base=False,
        )

        amplify_interventions: List[Dict[str, Any]] = []
        if pair.from_slug != pair.to_slug and pool_to:
            if match_layers:
                amplify_hist = build_layer_histogram(ref_amplify)
                sampled_amplify = sample_indices_matching_histogram(
                    rng, pool_to, lambda f: f["layer"], amplify_hist
                )
                amplify_diag = compute_match_diagnostics(
                    amplify_hist, build_layer_histogram(
                        [{"layer": f["layer"]} for f in sampled_amplify]
                    )
                )
                diagnostics["amplify_layer_match"] = amplify_diag
            else:
                n_amplify = len(ref_amplify)
                take = min(n_amplify, len(pool_to))
                sampled_amplify = rng.sample(pool_to, take) if take > 0 else []

            activations_map_to = data_to.get("activations_map", {})
            amplify_interventions = build_intervention_dicts(
                sampled_amplify,
                M_amplify,
                steer_generated_tokens=steer_generated,
                use_stored_as_base=True,
                activations_map=activations_map_to if activations_map_to else None,
            )

        features = ablate_interventions + amplify_interventions

        return InterventionResult(
            features=features,
            ablate_count=len(ablate_interventions),
            amplify_count=len(amplify_interventions),
            control_mode="random_feature_matched",
            concept_subsets_used=concept_fields,
            replicate_id=replicate_id,
            diagnostics=diagnostics,
        )
