"""
Abstract base for intervention builders.

Every control mode must implement ``build_for_pair``.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Dict

from .types import InterventionResult


class InterventionBuilder(ABC):
    """
    Produces a list of intervention feature-dicts for one swap pair.

    Subclasses receive the full config so they can read control-specific
    parameters without changing the runner.
    """

    @abstractmethod
    def build_for_pair(
        self,
        *,
        ct_steering: Any,
        config: Dict[str, Any],
        pair: Any,
        data_from: Dict[str, Any],
        data_to: Dict[str, Any],
    ) -> InterventionResult:
        """
        Build intervention features for a single swap pair.

        Parameters
        ----------
        ct_steering:
            The dynamically loaded ``03_ct_steering`` module.
        config:
            Full swap config dict.
        pair:
            A ``SwapPair`` instance.
        data_from:
            Graph data for the source entity (grouping, metrics,
            activations_map, prompt, ...).
        data_to:
            Graph data for the target entity.

        Returns
        -------
        InterventionResult
            features list + metadata.
        """
