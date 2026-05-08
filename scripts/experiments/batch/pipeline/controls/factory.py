"""
Factory that maps a swap config to the appropriate InterventionBuilder.

The contract: if no ``control`` block is present in the config, or if
``control.mode`` is ``"labeled"`` (or absent), the factory returns the
original labeled builder -- so every existing config keeps working.
"""
from __future__ import annotations

from typing import Any, Dict

from .base import InterventionBuilder
from .labeled import LabeledInterventionBuilder
from .random_feature_matched import RandomFeatureMatchedBuilder
from .random_template_matched import RandomTemplateMatchedBuilder
from .low_specificity_groupings import LowSpecificityGroupingsBuilder
from .additivity import AdditivityBuilder
from .topk_influence_matched import TopKInfluenceMatchedBuilder
from .single_bag_grouping import SingleBagGroupingBuilder

_REGISTRY: Dict[str, type] = {
    "labeled": LabeledInterventionBuilder,
    "random_feature_matched": RandomFeatureMatchedBuilder,
    "random_template_matched": RandomTemplateMatchedBuilder,
    "low_specificity_groupings": LowSpecificityGroupingsBuilder,
    "additivity": AdditivityBuilder,
    "topk_influence_matched": TopKInfluenceMatchedBuilder,
    "single_bag_grouping": SingleBagGroupingBuilder,
}


def register_control(name: str, cls: type) -> None:
    """Register a new control builder class under *name*."""
    _REGISTRY[name] = cls


def create_intervention_builder(config: Dict[str, Any]) -> InterventionBuilder:
    """
    Instantiate the builder indicated by ``config["control"]["mode"]``.

    Falls back to ``"labeled"`` when the key is absent.
    """
    control_cfg = config.get("control", {})
    mode = control_cfg.get("mode", "labeled") if control_cfg else "labeled"
    cls = _REGISTRY.get(mode)
    if cls is None:
        available = ", ".join(sorted(_REGISTRY))
        raise ValueError(
            f"Unknown control mode '{mode}'. Available: {available}"
        )
    return cls()
