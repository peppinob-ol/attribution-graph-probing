"""
Additivity control builder.

Supports two decomposition axes:

**Role-based** (``concept_subset.roles``): controls which *side* of the
intervention is active.  Source-role fields drive ablation; target-role
fields drive amplification.

  - roles: [source]               -- ablation only
  - roles: [target]               -- amplification only
  - roles: [source, target]       -- both sides

**Field-based** (``concept_subset.fields``): controls which *entity fields*
participate in both ablation and amplification simultaneously. Every
selected field is used on both sides, like the labeled builder but
restricted to a subset.

  - fields: [state]               -- swap only state supernodes
  - fields: [capital]             -- swap only capital supernodes
  - fields: [state, capital]      -- swap state + capital
  - fields: [state, capital, city] -- swap all three

Config examples::

    # Role-based: ablation only
    control:
      mode: additivity
      concept_subset:
        roles: [source]

    # Field-based: swap only state groupings
    control:
      mode: additivity
      concept_subset:
        fields: [state]

    # Multi-variant run: all field combinations
    control:
      mode: additivity
      runs:
        - fields: [state]
        - fields: [capital]
        - fields: [city]
        - fields: [state, capital]
        - fields: [state, city]
        - fields: [state, capital, city]
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from .base import InterventionBuilder
from .types import InterventionResult
from .concept_sets import get_concept_fields, resolve_concept_roles, select_concept_subset


def _concept_text(text: str) -> str:
    t = (text or "").strip().lower()
    if t.endswith(" city"):
        t = t[: -len(" city")].strip()
    return t


def _dedupe_preserve_order(items: List[str]) -> List[str]:
    seen: set = set()
    out: List[str] = []
    for x in items:
        if not x or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


class AdditivityBuilder(InterventionBuilder):
    """
    Runs the labeled intervention restricted to a subset of concept
    fields or roles.

    Two modes:

    **Field-based** (``concept_subset.fields``): selected fields are
    used for both ablation (from source entity) and amplification
    (from target entity), exactly like the labeled builder but
    restricted to a subset.

    **Role-based** (``concept_subset.roles``): source-role fields
    drive ablation only, target-role fields drive amplification only,
    link-role fields contribute to both.
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

        all_concept_fields = get_concept_fields(swap_cfg)
        subset_cfg = control_cfg.get("concept_subset", {})

        explicit_fields = subset_cfg.get("fields")
        if explicit_fields is not None:
            return self._build_field_based(
                ct_steering, config, pair, data_from, data_to,
                all_concept_fields, explicit_fields,
                M_ablate, M_amplify, steer_generated,
            )

        return self._build_role_based(
            ct_steering, config, pair, data_from, data_to,
            all_concept_fields, subset_cfg, control_cfg,
            M_ablate, M_amplify, steer_generated,
        )

    # ------------------------------------------------------------------
    # Field-based: selected fields used for both ablation and amplification
    # ------------------------------------------------------------------

    def _build_field_based(
        self,
        ct_steering: Any,
        config: Dict[str, Any],
        pair: Any,
        data_from: Dict[str, Any],
        data_to: Dict[str, Any],
        all_concept_fields: List[str],
        explicit_fields: List[str],
        M_ablate: float,
        M_amplify: float,
        steer_generated: bool,
    ) -> InterventionResult:

        active_fields = _dedupe_preserve_order(
            [f for f in explicit_fields if f in all_concept_fields or f in (
                pair.from_entity or pair.to_entity
            )]
        )

        features: List[Dict[str, Any]] = []
        ablate_count = 0
        amplify_count = 0

        source_concepts = _dedupe_preserve_order(
            [_concept_text(pair.from_entity.get(f, "")) for f in active_fields]
        )
        for concept in source_concepts:
            if not concept:
                continue
            try:
                supernode = ct_steering.extract_ct_supernode(
                    grouping_df=data_from["grouping"],
                    metrics_df=data_from["metrics"],
                    concept=concept,
                    slug=pair.from_slug,
                )
                interventions = ct_steering.compute_ct_interventions(
                    supernode, M_ablate,
                    steer_generated_tokens=steer_generated,
                    activations_map=None,
                    use_stored_as_base=False,
                )
                features.extend(interventions)
                ablate_count += len(interventions)
            except ValueError as e:
                print(
                    f"  Warning: Could not extract source supernode "
                    f"for concept '{concept}': {e}"
                )

        if pair.from_slug != pair.to_slug:
            target_concepts = _dedupe_preserve_order(
                [_concept_text(pair.to_entity.get(f, "")) for f in active_fields]
            )
            for concept in target_concepts:
                if not concept:
                    continue
                try:
                    supernode = ct_steering.extract_ct_supernode(
                        grouping_df=data_to["grouping"],
                        metrics_df=data_to["metrics"],
                        concept=concept,
                        slug=pair.to_slug,
                    )
                    activations_map_to = data_to.get("activations_map", {})
                    interventions = ct_steering.compute_ct_interventions(
                        supernode, M_amplify,
                        steer_generated_tokens=steer_generated,
                        activations_map=(
                            activations_map_to if activations_map_to else None
                        ),
                        use_stored_as_base=True,
                    )
                    features.extend(interventions)
                    amplify_count += len(interventions)
                except ValueError as e:
                    print(
                        f"  Warning: Could not extract target supernode "
                        f"for concept '{concept}': {e}"
                    )

        return InterventionResult(
            features=features,
            ablate_count=ablate_count,
            amplify_count=amplify_count,
            control_mode="additivity",
            concept_subsets_used=active_fields,
            diagnostics={
                "selection_mode": "fields",
                "requested_fields": list(explicit_fields),
                "active_fields": active_fields,
                "ablate_fields": active_fields,
                "amplify_fields": active_fields,
            },
        )

    # ------------------------------------------------------------------
    # Role-based: source roles -> ablation, target roles -> amplification
    # ------------------------------------------------------------------

    def _build_role_based(
        self,
        ct_steering: Any,
        config: Dict[str, Any],
        pair: Any,
        data_from: Dict[str, Any],
        data_to: Dict[str, Any],
        all_concept_fields: List[str],
        subset_cfg: Dict[str, Any],
        control_cfg: Dict[str, Any],
        M_ablate: float,
        M_amplify: float,
        steer_generated: bool,
    ) -> InterventionResult:

        roles_requested = subset_cfg.get("roles", ["source", "link", "target"])
        role_map = control_cfg.get("role_map")

        active_fields = select_concept_subset(
            all_concept_fields, roles_requested, role_map
        )
        roles = resolve_concept_roles(all_concept_fields, role_map)

        ablate_roles = {"source", "link"} & set(roles_requested)
        amplify_roles = {"target", "link"} & set(roles_requested)

        ablate_fields: List[str] = []
        for role in ("source", "link"):
            if role in ablate_roles:
                ablate_fields.extend(roles.get(role, []))
        ablate_fields = _dedupe_preserve_order(ablate_fields)

        amplify_fields: List[str] = []
        for role in ("target", "link"):
            if role in amplify_roles:
                amplify_fields.extend(roles.get(role, []))
        amplify_fields = _dedupe_preserve_order(amplify_fields)

        features: List[Dict[str, Any]] = []
        ablate_count = 0
        amplify_count = 0

        if ablate_fields:
            source_concepts = _dedupe_preserve_order(
                [_concept_text(pair.from_entity.get(f, "")) for f in ablate_fields]
            )
            for concept in source_concepts:
                if not concept:
                    continue
                try:
                    supernode = ct_steering.extract_ct_supernode(
                        grouping_df=data_from["grouping"],
                        metrics_df=data_from["metrics"],
                        concept=concept,
                        slug=pair.from_slug,
                    )
                    interventions = ct_steering.compute_ct_interventions(
                        supernode, M_ablate,
                        steer_generated_tokens=steer_generated,
                        activations_map=None,
                        use_stored_as_base=False,
                    )
                    features.extend(interventions)
                    ablate_count += len(interventions)
                except ValueError as e:
                    print(
                        f"  Warning: Could not extract source supernode "
                        f"for concept '{concept}': {e}"
                    )

        if amplify_fields and pair.from_slug != pair.to_slug:
            target_concepts = _dedupe_preserve_order(
                [_concept_text(pair.to_entity.get(f, "")) for f in amplify_fields]
            )
            for concept in target_concepts:
                if not concept:
                    continue
                try:
                    supernode = ct_steering.extract_ct_supernode(
                        grouping_df=data_to["grouping"],
                        metrics_df=data_to["metrics"],
                        concept=concept,
                        slug=pair.to_slug,
                    )
                    activations_map_to = data_to.get("activations_map", {})
                    interventions = ct_steering.compute_ct_interventions(
                        supernode, M_amplify,
                        steer_generated_tokens=steer_generated,
                        activations_map=(
                            activations_map_to if activations_map_to else None
                        ),
                        use_stored_as_base=True,
                    )
                    features.extend(interventions)
                    amplify_count += len(interventions)
                except ValueError as e:
                    print(
                        f"  Warning: Could not extract target supernode "
                        f"for concept '{concept}': {e}"
                    )

        return InterventionResult(
            features=features,
            ablate_count=ablate_count,
            amplify_count=amplify_count,
            control_mode="additivity",
            concept_subsets_used=active_fields,
            diagnostics={
                "selection_mode": "roles",
                "roles_requested": roles_requested,
                "ablate_fields": ablate_fields,
                "amplify_fields": amplify_fields,
                "role_map_used": roles,
            },
        )
