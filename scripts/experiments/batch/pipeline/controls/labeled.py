"""
Labeled intervention builder -- the original concept-matched supernode path.

This is a direct extraction of ``prepare_swap_features()`` from
``run_batch_swaps.py`` with zero intended semantic change.  The helpers
``_concept_text``, ``_dedupe_preserve_order``, and ``_get_concept_fields``
are kept here as private utilities rather than in a shared module because
they encode domain conventions specific to the labeled path.
"""
from __future__ import annotations

from typing import Any, Dict, List

from .base import InterventionBuilder
from .types import InterventionResult


# ---------------------------------------------------------------------------
# Private helpers (verbatim from run_batch_swaps.prepare_swap_features)
# ---------------------------------------------------------------------------

def _concept_text(text: str) -> str:
    """Normalize concept string for supernode matching."""
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


def _get_concept_fields(swap_cfg: Dict[str, Any]) -> List[str]:
    """
    Which entity fields are used as concept strings for supernode matching.

    Backward compatibility: ``swap.include_capitals`` / ``include_capital``
    (bool) appends ``"capital"`` to the list.
    """
    raw = swap_cfg.get("concept_fields", None)
    if raw is None:
        fields: List[str] = ["state"]
    elif isinstance(raw, str):
        fields = [raw]
    elif isinstance(raw, list):
        fields = [str(x) for x in raw if str(x).strip()]
    else:
        raise ValueError("swap.concept_fields must be a string or list of strings")

    if bool(
        swap_cfg.get("include_capitals", False)
        or swap_cfg.get("include_capital", False)
    ):
        if "capital" not in fields:
            fields.append("capital")

    return fields


# ---------------------------------------------------------------------------
# Builder
# ---------------------------------------------------------------------------

class LabeledInterventionBuilder(InterventionBuilder):
    """Produces interventions by matching concept-labeled supernodes."""

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

        concept_fields = _get_concept_fields(swap_cfg)

        features: List[Dict[str, Any]] = []
        ablate_count = 0
        amplify_count = 0

        # --- source supernodes -> ABLATION ---
        source_concepts = _dedupe_preserve_order(
            [_concept_text(pair.from_entity.get(f, "")) for f in concept_fields]
        )

        for concept in source_concepts:
            if not concept:
                continue
            try:
                supernode_from = ct_steering.extract_ct_supernode(
                    grouping_df=data_from["grouping"],
                    metrics_df=data_from["metrics"],
                    concept=concept,
                    slug=pair.from_slug,
                )
                from_interventions = ct_steering.compute_ct_interventions(
                    supernode_from,
                    M_ablate,
                    steer_generated_tokens=steer_generated,
                    activations_map=None,
                    use_stored_as_base=False,
                )
                features.extend(from_interventions)
                ablate_count += len(from_interventions)
            except ValueError as e:
                print(
                    f"  Warning: Could not extract source supernode "
                    f"for concept '{concept}': {e}"
                )

        # --- target supernodes -> AMPLIFICATION ---
        if pair.from_slug != pair.to_slug:
            target_concepts = _dedupe_preserve_order(
                [_concept_text(pair.to_entity.get(f, "")) for f in concept_fields]
            )

            for concept in target_concepts:
                if not concept:
                    continue
                try:
                    supernode_to = ct_steering.extract_ct_supernode(
                        grouping_df=data_to["grouping"],
                        metrics_df=data_to["metrics"],
                        concept=concept,
                        slug=pair.to_slug,
                    )
                    activations_map_to = data_to.get("activations_map", {})
                    to_interventions = ct_steering.compute_ct_interventions(
                        supernode_to,
                        M_amplify,
                        steer_generated_tokens=steer_generated,
                        activations_map=(
                            activations_map_to if activations_map_to else None
                        ),
                        use_stored_as_base=True,
                    )
                    features.extend(to_interventions)
                    amplify_count += len(to_interventions)
                except ValueError as e:
                    print(
                        f"  Warning: Could not extract target supernode "
                        f"for concept '{concept}': {e}"
                    )

        return InterventionResult(
            features=features,
            ablate_count=ablate_count,
            amplify_count=amplify_count,
            control_mode="labeled",
            concept_subsets_used=concept_fields,
        )
