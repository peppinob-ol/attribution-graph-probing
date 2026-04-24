"""
Template-matched random-feature control builder.

This builder generalizes ``random_feature_matched`` so that the same
search budget used by labeled field-additivity runs (per-variant field
subsets and roles) can also be applied to the random null.  Instead of
always mirroring the full labeled intervention, the random control is
built against a *labeled template variant* specified by
``control.concept_subset``.

Concretely, for one swap pair and one template variant:

1. The labeled intervention is computed for the requested field/role
   subset (via :class:`AdditivityBuilder`).  This is the *template*.
2. The per-role layer histograms of the template (ablate and amplify)
   are extracted along with the set of concepts touched.
3. Random features are sampled from the per-graph candidate pools so
   they match those histograms exactly (when feasible), while excluding:
     - the template's own features (no label leakage), and
     - every supernode whose name matches any of the template's
       concept strings (no surface-level concept leakage).

The result carries a ``control_mode`` of ``"random_template_matched"``
plus diagnostics that record the template provenance (fields/roles,
per-role counts, replicate id, match quality), so downstream analysis
can pair each random run with the labeled variant it was matched
against.

Config shape::

    control:
      mode: random_template_matched
      seed: 42
      replicates: 3
      matching:
        match_layers: true
      exclusions:
        exclude_labeled_features: true
        exclude_concept_matching_supernodes: true
      # Optional: one template variant per run.  When absent, the
      # builder falls back to the full labeled template (all fields).
      runs:
        - fields: [state]
        - fields: [state, capital]
        - fields: [state, capital, city]
"""
from __future__ import annotations

import copy
from typing import Any, Dict, List

from .base import InterventionBuilder
from .types import InterventionResult
from .concept_sets import get_concept_fields
from .additivity import AdditivityBuilder
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


class RandomTemplateMatchedBuilder(InterventionBuilder):
    """
    Produces a random null that structurally matches a labeled template
    variant (field-subset or role-subset) rather than the full labeled
    intervention.
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
        control_cfg = config.get("control", {}) or {}

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
            seed, pair.swap_id, replicate_id, "random_template_matched"
        )

        # --- Step 1: build the labeled template via AdditivityBuilder ---
        # AdditivityBuilder handles both "fields" and "roles" subset
        # selection.  When no concept_subset is provided, we interpret
        # that as the full labeled template (all roles).
        template_config = copy.deepcopy(config)
        template_control = template_config.setdefault("control", {})
        template_control["mode"] = "additivity"
        subset_cfg = control_cfg.get("concept_subset")
        if subset_cfg is None:
            template_control["concept_subset"] = {
                "roles": ["source", "link", "target"],
            }
        else:
            template_control["concept_subset"] = copy.deepcopy(subset_cfg)

        template_result = AdditivityBuilder().build_for_pair(
            ct_steering=ct_steering,
            config=template_config,
            pair=pair,
            data_from=data_from,
            data_to=data_to,
        )

        ref_ablate = [
            f for f in template_result.features
            if f.get("M") == M_ablate or f.get("ablate")
        ]
        ref_amplify = [
            f for f in template_result.features
            if f.get("M") == M_amplify and not f.get("ablate")
        ]

        # The template provenance is authoritative for which fields are
        # actually "active" (it already resolved roles -> fields).
        active_fields: List[str] = list(template_result.concept_subsets_used or [])
        template_diag = dict(template_result.diagnostics or {})
        selection_mode = template_diag.get("selection_mode", "unknown")

        # --- Step 2: build exclusion sets based on the TEMPLATE ---
        exclude_keys_from = set()
        exclude_keys_to = set()

        if exclude_labeled:
            exclude_keys_from |= set(feature_keys_from_interventions(ref_ablate))
            exclude_keys_to |= set(feature_keys_from_interventions(ref_amplify))

        if exclude_concept_supernodes and active_fields:
            # Concept strings to exclude come from the same fields the
            # template actually touched; this keeps the random null
            # disjoint from the labeled signal for that variant.
            ablate_fields = template_diag.get("ablate_fields") or active_fields
            amplify_fields = template_diag.get("amplify_fields") or active_fields

            source_concepts = [
                _concept_text(pair.from_entity.get(f, ""))
                for f in ablate_fields
            ]
            target_concepts = [
                _concept_text(pair.to_entity.get(f, ""))
                for f in amplify_fields
            ]
            exclude_keys_from |= exclude_concept_matching_supernodes(
                data_from["grouping"], [c for c in source_concepts if c]
            )
            if pair.from_slug != pair.to_slug:
                exclude_keys_to |= exclude_concept_matching_supernodes(
                    data_to["grouping"], [c for c in target_concepts if c]
                )

        # --- Step 3: candidate pools ---
        pool_from = build_candidate_pool(data_from["grouping"], exclude_keys_from)
        pool_to = (
            build_candidate_pool(data_to["grouping"], exclude_keys_to)
            if pair.from_slug != pair.to_slug
            else []
        )

        diagnostics: Dict[str, Any] = {
            "template_selection_mode": selection_mode,
            "template_active_fields": active_fields,
            "template_ablate_fields": template_diag.get("ablate_fields"),
            "template_amplify_fields": template_diag.get("amplify_fields"),
            "template_ablate_count": len(ref_ablate),
            "template_amplify_count": len(ref_amplify),
            "pool_from_size": len(pool_from),
            "pool_to_size": len(pool_to),
            "exclusion_from_count": len(exclude_keys_from),
            "exclusion_to_count": len(exclude_keys_to),
        }

        # --- Step 4: sample matched ablation features ---
        if ref_ablate:
            if match_layers:
                ablate_hist = build_layer_histogram(ref_ablate)
                sampled_ablate = sample_indices_matching_histogram(
                    rng, pool_from, lambda f: f["layer"], ablate_hist,
                )
                diagnostics["ablate_layer_match"] = compute_match_diagnostics(
                    ablate_hist,
                    build_layer_histogram(
                        [{"layer": f["layer"]} for f in sampled_ablate]
                    ),
                )
            else:
                take = min(len(ref_ablate), len(pool_from))
                sampled_ablate = (
                    rng.sample(pool_from, take) if take > 0 else []
                )
        else:
            sampled_ablate = []

        ablate_interventions = build_intervention_dicts(
            sampled_ablate,
            M_ablate,
            steer_generated_tokens=steer_generated,
            use_stored_as_base=False,
        )

        # --- Step 5: sample matched amplification features ---
        amplify_interventions: List[Dict[str, Any]] = []
        if ref_amplify and pair.from_slug != pair.to_slug and pool_to:
            if match_layers:
                amplify_hist = build_layer_histogram(ref_amplify)
                sampled_amplify = sample_indices_matching_histogram(
                    rng, pool_to, lambda f: f["layer"], amplify_hist,
                )
                diagnostics["amplify_layer_match"] = compute_match_diagnostics(
                    amplify_hist,
                    build_layer_histogram(
                        [{"layer": f["layer"]} for f in sampled_amplify]
                    ),
                )
            else:
                take = min(len(ref_amplify), len(pool_to))
                sampled_amplify = (
                    rng.sample(pool_to, take) if take > 0 else []
                )

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
            control_mode="random_template_matched",
            concept_subsets_used=active_fields,
            replicate_id=replicate_id,
            diagnostics=diagnostics,
        )
